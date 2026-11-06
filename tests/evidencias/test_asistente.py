"""Asistente web de importación (docs/04 §9) y permisos (CP-11)."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.evidencias.models import Evidencia, PlantillaImportacion
from apps.nucleo.models import ElementoRevision
from tests.evidencias.test_tabla_municipal import FIXTURES


@pytest.fixture
def cliente_analista(client, analista, municipios_cv, competidores):
    client.force_login(analista)
    return client


def _subir(client, **extra):
    contenido = (FIXTURES / "agua_sintetico.csv").read_bytes()
    archivo = SimpleUploadedFile("agua.csv", contenido, content_type="text/csv")
    return client.post(reverse("importar_tabla"), {"archivo": archivo, **extra})


def test_flujo_completo_csv(cliente_analista, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    c = cliente_analista
    r = _subir(c)
    assert r.status_code == 302 and r.url == reverse("importar_tabla_columnas")
    assert c.get(r.url).status_code == 200

    r = c.post(
        reverse("importar_tabla_columnas"),
        {
            "columna_municipio": "MUNICIPIO",
            "columna_provincia": "",
            "fuente_tipo": "documento_interno",
            "fuente_nombre": "Tabla de agua",
            "fecha_consulta": "2026-11-03",
            "estado": "validada",
            "bloque-TOTAL_FORMS": "2",
            "bloque-INITIAL_FORMS": "0",
            "bloque-MIN_NUM_FORMS": "0",
            "bloque-MAX_NUM_FORMS": "8",
            "bloque-0-servicio": "agua",
            "bloque-0-alcance": "",
            "bloque-0-columna_operador": "SERVICIO DE AGUAS",
            "bloque-0-nivel_por_defecto": "empresa",
            "bloque-1-nivel_por_defecto": "decidir",
        },
    )
    assert r.status_code == 302, r.content.decode()[:2000]
    assert c.get(reverse("importar_tabla_valores")).status_code == 200
    r = c.post(reverse("importar_tabla_valores"), {"nombre_plantilla": "Agua de prueba"})
    assert r.url == reverse("importar_tabla_confirmar")
    assert PlantillaImportacion.objects.filter(nombre="Agua de prueba").exists()

    r = c.get(r.url)
    assert r.status_code == 200 and Evidencia.objects.count() == 0
    assert r.context["r"].evidencias_nuevas == 3

    r = c.post(reverse("importar_tabla_confirmar"), {"confirmar": "1"})
    assert r.status_code == 302
    assert Evidencia.objects.count() == 3
    assert not list((tmp_path / "importaciones" / "pendientes").iterdir())  # archivo borrado
    assert c.get(r.url).status_code == 200  # detalle del lote

    # Bandeja: resolver TAVERNES desde la web.
    el = ElementoRevision.objects.get(texto="TAVERNES")
    assert c.get(reverse("revision")).status_code == 200
    r = c.post(
        reverse("revision_elemento", args=[el.pk]),
        {"resolver": "1", "municipio": "46238", "aplicar_a_iguales": "on", "comentario": ""},
    )
    assert r.status_code == 302
    el.refresh_from_db()
    assert el.estado == "corregido"


def test_rechaza_extension_no_admitida(cliente_analista):
    archivo = SimpleUploadedFile("tabla.pdf", b"%PDF", content_type="application/pdf")
    r = cliente_analista.post(reverse("importar_tabla"), {"archivo": archivo})
    assert r.status_code == 200 and "Solo se admiten" in r.content.decode()


@pytest.mark.parametrize(
    "nombre",
    [
        "importar",
        "importar_tabla",
        "importar_tabla_columnas",
        "importar_tabla_confirmar",
        "revision",
    ],
)
def test_cp11_lector_no_importa_ni_revisa(client, lector, nombre):
    client.force_login(lector)
    assert client.get(reverse(nombre)).status_code == 403
    assert client.post(reverse(nombre), {}).status_code == 403


def test_lector_ve_el_mapa(client, lector, municipios_cv):
    client.force_login(lector)
    r = client.get(reverse("mapa"))
    assert r.status_code == 200
    assert reverse("importar") not in r.content.decode()
