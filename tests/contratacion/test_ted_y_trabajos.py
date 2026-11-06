"""TED (docs/04 §2), trabajos por partes (ADR-007), bandeja y vistas de contratación."""

import io
import json

from django.urls import reverse

from apps.contratacion import services_revision as srv
from apps.contratacion.importers.ted import ImportadorTed
from apps.contratacion.models import Expediente, OrganoContratacion
from apps.contratacion.trabajos import TIPO_PLACSP, TIPO_TED
from apps.entidades.models import AliasEmpresa, Empresa
from apps.nucleo.models import ElementoRevision, TrabajoIngesta
from apps.nucleo.trabajos import ejecutar_hasta_terminar

from .conftest import ATOM, FIXTURES

RESPUESTA = json.loads(
    (FIXTURES / "ted" / "search_es52_can_titulo_20261001.json").read_text(encoding="utf-8")
)


def test_ted_descarta_compradores_no_valencianos(base):
    c = ImportadorTed().procesar(RESPUESTA["notices"])
    assert c.avisos == 2 and c.no_valencianos == 1 and c.nuevos == 1  # Renfe (Madrid) fuera
    exp = Expediente.objects.get(fuente="ted")
    assert exp.id_externo == "675083-2026"
    assert exp.objeto.startswith("España – ")
    assert exp.url_origen == "https://ted.europa.eu/es/notice/-/detail/675083-2026"
    assert exp.datos_fuente["valor_ted"] == 1099615.5
    assert exp.importe_licitacion is None  # total-value no se interpreta como importe
    assert exp.organo.estado_vinculacion == OrganoContratacion.Vinculacion.NO_APLICA
    assert exp.adjudicaciones.count() == 6  # ganadores distintos, sin repetir
    # Reimportar no duplica.
    assert ImportadorTed().procesar(RESPUESTA["notices"]).existentes == 1


def test_trabajo_ted_por_paginas(base, monkeypatch):
    llamadas = []

    def falsa(desde, hasta, pagina, cliente=None):
        llamadas.append(pagina)
        return {**RESPUESTA, "totalNoticeCount": 2} if pagina == 1 else {"notices": []}

    monkeypatch.setattr("apps.contratacion.trabajos.pedir_pagina", falsa)
    t = TrabajoIngesta.objects.create(
        tipo=TIPO_TED, parametros={"desde": "2026-10-01", "hasta": "2026-10-03"}
    )
    t = ejecutar_hasta_terminar(t)
    assert t.estado == "terminado" and llamadas == [1]
    assert t.contadores["nuevos"] == 1 and t.lote_importacion.nuevos == 1


def test_trabajo_placsp_con_fichero_y_error(base, tmp_path):
    t = TrabajoIngesta.objects.create(tipo=TIPO_PLACSP, parametros={"fichero": str(ATOM)})
    t = ejecutar_hasta_terminar(t)
    assert t.estado == "terminado" and t.contadores["nuevos"] == 2
    assert t.partes_total == 1 and t.partes_hechas == 1

    roto = TrabajoIngesta.objects.create(
        tipo=TIPO_PLACSP, parametros={"fichero": str(tmp_path / "no.zip")}
    )
    roto = ejecutar_hasta_terminar(roto)
    assert roto.estado == "error" and "Error" in roto.log


def test_comando_ingest_placsp(base, tmp_path):
    import zipfile

    from django.core.management import call_command

    z = tmp_path / "mes.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.write(ATOM, "licitacionesPerfilesContratanteCompleto3.atom")
    call_command("ingest_placsp", "--fichero", str(z), stdout=io.StringIO())
    assert Expediente.objects.count() == 2


def test_resolver_adjudicatario_guarda_alias_y_resuelve_iguales(base, tmp_path, administrador):
    from .test_placsp import importar

    importar(tmp_path)
    el = ElementoRevision.objects.get(tipo="adjudicatario_no_resuelto")
    clece = Empresa.objects.create(nombre="Clece")
    srv.resolver_adjudicatario(el, clece, administrador, guardar_alias=True, guardar_nif=True)
    clece.refresh_from_db()
    assert clece.nif == "A87045498"
    assert AliasEmpresa.objects.filter(empresa=clece, texto="clece fs").exists()
    # La siguiente importación lo resuelve sola por NIF.
    Expediente.objects.all().delete()
    importar(tmp_path)
    assert (
        Expediente.objects.get(organo__municipio__nombre_oficial="Ondara")
        .adjudicaciones.get()
        .empresa
        == clece
    )


def test_vincular_y_clasificar_desde_la_bandeja(base, administrador):
    from apps.contratacion.services import vincular_organo
    from apps.territorio.models import Municipio

    organo = OrganoContratacion.objects.create(
        nombre="Alcaldía del Ayuntamiento de Herbés", codigo_postal="12317"
    )
    vincular_organo(organo)
    el = ElementoRevision.objects.get(tipo="vinculo_organo")
    herbers = Municipio.objects.get(nombre_oficial__startswith="Herbers")
    srv.vincular(el, herbers, administrador)
    organo.refresh_from_db()
    assert organo.municipio == herbers and organo.estado_vinculacion == "validada"

    exp = Expediente.objects.create(
        fuente="placsp", id_externo="x", objeto="Alumbrado público y recogida de residuos"
    )
    from apps.contratacion.services import Clasificador, revisar_clasificacion

    revisar_clasificacion(exp, Clasificador().clasificar([], exp.objeto))
    el = ElementoRevision.objects.get(tipo="clasificacion_servicio")
    srv.clasificar(el, "energia|alumbrado_publico", administrador)
    exp.refresh_from_db()
    assert exp.metodo_clasificacion == "manual" and exp.alcance_clasificado == "alumbrado_publico"


def test_vistas_y_permisos(base, client, lector, analista, tmp_path):
    from .test_placsp import importar

    importar(tmp_path)
    client.force_login(lector)
    r = client.get(reverse("expedientes"))
    assert r.status_code == 200 and "Ondara" in r.content.decode()
    exp = Expediente.objects.get(organo__municipio__nombre_oficial="Ondara")
    assert "CLECE FS SA" in client.get(reverse("expediente", args=[exp.pk])).content.decode()
    panel = client.get(
        reverse("municipio", args=[exp.organo.municipio.codigo_ine])
    ).content.decode()
    assert "climatitzaci" in panel
    assert client.get(reverse("actualizar_contratacion")).status_code == 403
    assert client.post(reverse("actualizar_contratacion"), {}).status_code == 403
    assert client.get(reverse("trabajos")).status_code == 403

    client.force_login(analista)
    assert client.get(reverse("actualizar_contratacion")).status_code == 200
    r = client.post(
        reverse("actualizar_contratacion"),
        {"ted_desde": "2026-10-01", "ted_hasta": "2026-09-01", "ted": "on", "placsp_mes": "x"},
    )
    assert r.status_code == 200  # formulario con errores, no crea trabajos
    assert not TrabajoIngesta.objects.exists()
