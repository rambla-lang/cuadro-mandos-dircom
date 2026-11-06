"""Importador de PLACSP (docs/04 §1). CP-03, CP-04, CP-06, CP-14, CP-16 e idempotencia."""

import re

import pytest

from apps.contratacion.importers.placsp import ImportadorPlacsp, criterio_territorial, leer_entrada
from apps.contratacion.models import Adjudicacion, Expediente, OrganoContratacion
from apps.contratacion.services import (
    Clasificador,
    nombre_municipio_del_organo,
    sin_forma_juridica,
    vincular_organo,
)
from apps.evidencias.enums import NivelEvidencia
from apps.nucleo.models import ElementoRevision

from .conftest import ATOM, atom_con, entrada

ONDARA = "20815589"


def importar(tmp_path, texto=None, nombre="prueba.atom"):
    ruta = tmp_path / nombre
    ruta.write_text(texto if texto is not None else ATOM.read_text(encoding="utf-8"), "utf-8")
    return ImportadorPlacsp().procesar_atom(str(ruta), nombre)


def test_lee_rutas_verificadas():
    from lxml import etree

    raiz = etree.parse(str(ATOM))
    ns = {"a": "http://www.w3.org/2005/Atom"}
    e = next(
        x for x in raiz.findall("a:entry", ns) if x.findtext("a:id", namespaces=ns).endswith(ONDARA)
    )
    d = leer_entrada(e)
    assert d["numero"] == "2238/2024-1P" and d["estado"] == "RES"
    assert d["organo"]["nombre"] == "Junta de Gobierno del Ayuntamiento de Ondara"
    assert d["organo"]["nif"] == "P0309500G" and d["organo"]["dir3"] == "L01030955"
    assert d["organo"]["jerarquia"][:2] == ["Ondara", "Ayuntamientos"]
    assert str(d["importe"]) == "36000" and str(d["importe_con_iva"]) == "43560"
    assert d["cpv"] == ["50710000"] and d["nuts"] == ["ES521"]
    r = d["resultados"][0]
    assert r["adjudicatario"] == "CLECE FS SA" and r["nif"] == "A87045498"
    assert criterio_territorial(d) == "nuts_y_cp_organo"


def test_importa_solo_la_cv_y_vincula(base, tmp_path):
    c = importar(tmp_path)
    assert c.entradas == 5
    assert c.fuera_cv == 3  # nanoGUNE (Gipuzkoa) y las dos versiones de San Bartolomé
    assert c.nuevos == 2  # Ondara y Polop
    assert c.eliminados_desconocidos == 1  # la deleted-entry no estaba cargada
    ondara = Expediente.objects.get(id_externo__endswith=ONDARA)
    assert ondara.organo.municipio.nombre_oficial == "Ondara"
    assert ondara.organo.estado_vinculacion == OrganoContratacion.Vinculacion.AUTOMATICA
    assert ondara.iva_incluido == Expediente.Iva.NO
    # 50710000: mantenimiento de equipos eléctricos y mecánicos de edificios → energía/otro
    assert (ondara.servicio_clasificado, ondara.alcance_clasificado) == ("energia", "otro")
    adj = ondara.adjudicaciones.get()
    assert adj.adjudicatario_texto == "CLECE FS SA" and adj.empresa is None
    assert adj.nivel == NivelEvidencia.OFICIAL
    # Adjudicatario fuera del catálogo en un contrato de energía: a la bandeja.
    assert ElementoRevision.objects.filter(tipo="adjudicatario_no_resuelto").count() == 1
    polop = Expediente.objects.get(organo__municipio__nombre_oficial="Polop")
    assert polop.estado == "PUB" and not polop.adjudicaciones.exists()


def test_reimportar_no_duplica_ni_sobrescribe(base, tmp_path):
    importar(tmp_path)
    c = importar(tmp_path)
    assert c.nuevos == 0 and c.actualizados == 0 and c.antiguos == 2
    assert Expediente.objects.count() == 2
    assert Adjudicacion.objects.count() == 1


def test_cp14_entrada_mas_antigua_no_sobrescribe(base, tmp_path):
    importar(tmp_path)
    vieja = (
        entrada(ONDARA)
        .replace(
            "<updated>2026-10-30T19:29:56.115+01:00</updated>",
            "<updated>2026-10-01T10:00:00.000+02:00</updated>",
        )
        .replace(
            ">RES</cbc-place-ext:ContractFolderStatusCode>",
            ">ADJ</cbc-place-ext:ContractFolderStatusCode>",
        )
    )
    c = importar(tmp_path, atom_con(vieja), "vieja.atom")
    assert c.antiguos >= 1
    assert Expediente.objects.get(id_externo__endswith=ONDARA).estado == "RES"

    nueva = (
        entrada(ONDARA)
        .replace(
            "<updated>2026-10-30T19:29:56.115+01:00</updated>",
            "<updated>2026-11-02T10:00:00.000+01:00</updated>",
        )
        .replace("CLECE FS SA", "OTRA EMPRESA SL")
    )
    importar(tmp_path, atom_con(nueva), "nueva.atom")
    exp = Expediente.objects.get(id_externo__endswith=ONDARA)
    assert exp.adjudicaciones.get().adjudicatario_texto == "OTRA EMPRESA SL"


def test_cp06_adjudicado_sin_adjudicatario_publicado(base, tmp_path):
    sin_ganador = re.sub(
        r"<cac:WinningParty>.*?</cac:WinningParty>", "", entrada(ONDARA), flags=re.S
    )
    sin_ganador = sin_ganador.replace(f"/{ONDARA}</id>", "/99999999</id>")
    importar(tmp_path, atom_con(sin_ganador), "sin_ganador.atom")
    adj = Adjudicacion.objects.get(expediente__id_externo__endswith="99999999")
    assert adj.adjudicatario_texto == "" and adj.empresa is None
    assert adj.nivel == NivelEvidencia.PARCIAL


def test_entrada_eliminada_marca_sin_borrar(base, tmp_path):
    importar(tmp_path)
    borrado = (
        '<at:deleted-entry ref="https://contrataciondelestado.es/sindicacion/'
        f'licitacionesPerfilContratante/{ONDARA}" '
        'when="2026-11-03T10:00:00.000+01:00"><at:comment type="ANULADA"/></at:deleted-entry>'
    )
    c = importar(tmp_path, atom_con(borrado), "borrado.atom")
    assert c.eliminados == 1
    exp = Expediente.objects.get(id_externo__endswith=ONDARA)
    assert exp.eliminado_en_fuente and exp.estado == "ANUL"


@pytest.mark.parametrize(
    ("nombre", "cp", "esperado"),
    [
        ("Ayuntamiento de Llagostera", "17240", None),  # CP-03
        (
            "Junta de Gobierno del Ayuntamiento de Monforte del Cid",
            "03670",
            "Monforte del Cid",
        ),  # CP-04
        ("Ajuntament de l'Eliana", "46183", "Eliana, l'"),
        ("Pleno del Ayuntamiento de Alicante", "03002", "Alacant/Alicante"),
        ("Diputación Provincial de Alicante", "03005", None),
    ],
)
def test_cp03_cp04_vinculacion_de_organos(base, nombre, cp, esperado):
    organo = OrganoContratacion.objects.create(nombre=nombre, codigo_postal=cp)
    vincular_organo(organo)
    organo.refresh_from_db()
    assert (organo.municipio.nombre_oficial if organo.municipio else None) == esperado
    if nombre.startswith("Diputación"):
        assert organo.estado_vinculacion == OrganoContratacion.Vinculacion.NO_APLICA
    if esperado is None and "Ayuntamiento" in nombre:
        assert organo.estado_vinculacion == OrganoContratacion.Vinculacion.PENDIENTE
        assert ElementoRevision.objects.filter(tipo="vinculo_organo").exists()


def test_nombre_municipio_del_organo():
    assert nombre_municipio_del_organo("Alcaldía del Ayuntamiento de Agost") == "agost"
    assert nombre_municipio_del_organo("Universidad de Alicante") is None


@pytest.mark.parametrize(
    ("cpvs", "objeto", "esperado"),
    [
        (["09310000"], "", ("energia", "suministro_electrico")),  # CP-16
        (["90511100"], "", ("residuos", "recogida_rsu")),
        (["90610000"], "", ("residuos", "limpieza_viaria")),
        (["50232100"], "", ("energia", "alumbrado_publico")),
        (["90420000"], "", ("agua", "depuracion")),
        (["79412000"], "Servicio de recogida de residuos urbanos", ("residuos", "recogida_rsu")),
        (["79412000"], "Consultoría de gestión", ("", "")),
    ],
)
def test_clasificacion(reglas, cpvs, objeto, esperado):
    c = Clasificador().clasificar(cpvs, objeto)
    assert (c.servicio, c.alcance) == esperado


def test_clasificacion_ambigua(reglas):
    c = Clasificador().clasificar([], "Alumbrado público y recogida de residuos")
    assert c.ambigua and c.servicio == ""


def test_sin_forma_juridica():
    assert sin_forma_juridica("URBASER, S.A.") == "urbaser"
    assert sin_forma_juridica("IBERDROLA CLIENTES, S.A.U.") == "iberdrola clientes"
    assert sin_forma_juridica("Sequoia Gestion Ambiental SL") == "sequoia gestion ambiental"
