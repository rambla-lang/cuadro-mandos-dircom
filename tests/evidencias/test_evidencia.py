import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.entidades.models import Empresa
from apps.evidencias.models import Evidencia, Fuente, PrestacionServicio
from apps.nucleo.models import RegistroAuditoria
from apps.territorio.models import Municipio, Provincia


@pytest.fixture
def fuente(db):
    return Fuente.objects.create(tipo="contratacion_oficial", nombre="PLACSP")


@pytest.fixture
def municipio(db):
    p = Provincia.objects.create(
        codigo_ine="03", nombre="Alicante/Alacant", comunidad="Comunitat Valenciana"
    )
    return Municipio.objects.create(codigo_ine="03002", nombre_oficial="Agost", provincia=p)


def crear(fuente, **kw):
    datos = {
        "categoria": "contrato",
        "titulo": "Adjudicación",
        "fuente": fuente,
        "nivel": "parcial",
        "origen": "importador",
    }
    datos.update(kw)
    return Evidencia.objects.create(**datos)


def test_codigo_legible_correlativo(fuente):
    e1, e2 = crear(fuente), crear(fuente)
    assert e1.codigo == f"E-{e1.pk:06d}"
    assert Evidencia.objects.get(pk=e2.pk).codigo == f"E-{e2.pk:06d}"


def test_oficial_exige_url(fuente):
    with pytest.raises(IntegrityError), transaction.atomic():
        crear(fuente, nivel="oficial")
    assert crear(fuente, nivel="oficial", url_origen="https://contrataciondelestado.es/x").pk


@pytest.mark.parametrize("nivel", ["oficial", "prensa", "empresa"])
def test_ia_no_confirma_sin_validacion_humana(fuente, nivel):
    with pytest.raises(IntegrityError), transaction.atomic():
        crear(fuente, origen="ia", nivel=nivel, url_origen="https://ejemplo.es/a")


def test_ia_puede_proponer_parcial_y_una_persona_confirma(fuente, analista):
    e = crear(fuente, origen="ia", nivel="parcial")
    e.nivel = "prensa"
    e.url_origen = "https://ejemplo.es/a"
    e.estado_validacion = "validada"
    e.validado_por = analista
    e.validado_en = timezone.now()
    e.save()
    assert Evidencia.objects.get(pk=e.pk).nivel == "prensa"


def test_validada_exige_responsable(fuente):
    with pytest.raises(IntegrityError), transaction.atomic():
        crear(fuente, estado_validacion="validada")


def test_alcance_coherente_con_servicio(fuente):
    with pytest.raises(IntegrityError), transaction.atomic():
        crear(fuente, servicio="agua", alcance="recogida_rsu")
    with pytest.raises(IntegrityError), transaction.atomic():
        crear(fuente, servicio="", alcance="abastecimiento")
    assert crear(fuente, servicio="energia", alcance="suministro_electrico").pk
    assert crear(fuente, servicio="agua", alcance="").pk


def test_extracto_limitado_a_300_palabras(fuente):
    e = Evidencia(
        categoria="otra",
        titulo="t",
        fuente=fuente,
        nivel="parcial",
        origen="manual",
        extracto="palabra " * 301,
    )
    with pytest.raises(ValidationError):
        e.full_clean()


def test_prestacion_unica_tambien_sin_empresa(municipio):
    datos = {
        "municipio": municipio,
        "servicio": "agua",
        "alcance": "abastecimiento",
        "gestion": "no_localizada",
        "nivel": "no_localizado",
    }
    PrestacionServicio.objects.create(**datos)
    with pytest.raises(IntegrityError), transaction.atomic():
        PrestacionServicio.objects.create(**datos)
    e = Empresa.objects.create(nombre="Aqualia")
    PrestacionServicio.objects.create(
        **{**datos, "empresa": e, "gestion": "indirecta", "nivel": "parcial"}
    )


def test_prestacion_alcance_coherente(municipio):
    with pytest.raises(IntegrityError), transaction.atomic():
        PrestacionServicio.objects.create(
            municipio=municipio,
            servicio="residuos",
            alcance="depuracion",
            gestion="indirecta",
            nivel="parcial",
        )


def test_municipio_con_evidencias_no_se_borra(fuente, municipio):
    from django.db.models import ProtectedError

    crear(fuente).municipios.add(municipio)
    with pytest.raises(ProtectedError):
        municipio.delete()


def test_editar_evidencia_validada_en_admin_deja_auditoria(client, administrador, fuente):
    e = crear(
        fuente, estado_validacion="validada", validado_por=administrador, validado_en=timezone.now()
    )
    client.force_login(administrador)
    url = f"/admin/evidencias/evidencia/{e.pk}/change/"
    datos = {
        "categoria": "contrato",
        "titulo": "Título corregido",
        "extracto": "",
        "url_origen": "",
        "fuente": fuente.pk,
        "servicio": "",
        "alcance": "",
        "nivel": "parcial",
        "estado_validacion": "validada",
        "origen": "importador",
        "tratamiento_limites": "",
        "datos_extra": "{}",
        "evidenciaempresa_set-TOTAL_FORMS": "0",
        "evidenciaempresa_set-INITIAL_FORMS": "0",
        "evidenciamunicipio_set-TOTAL_FORMS": "0",
        "evidenciamunicipio_set-INITIAL_FORMS": "0",
    }
    r = client.post(url, datos)
    assert r.status_code == 302, r.content.decode()[:2000]
    reg = RegistroAuditoria.objects.get(accion="evidencia.editar_validada")
    assert reg.antes["titulo"] == "Adjudicación"
    assert reg.despues["titulo"] == "Título corregido"
    assert reg.usuario == administrador
