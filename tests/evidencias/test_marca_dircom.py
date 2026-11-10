"""Marca «Validado por DIRCOM»: visible junto al nivel, sin cambiarlo (docs/03)."""

import pytest

from apps.evidencias.enums import EstadoValidacion
from apps.evidencias.importers.tabla_municipal import importar_tabla
from apps.evidencias.models import MARCA_VALIDACION, Evidencia
from apps.territorio.models import Municipio

from .test_tabla_municipal import FIXTURES, config_agua


@pytest.fixture
def importado(municipios_cv, empresas_gestoras, administrador):
    importar_tabla(FIXTURES / "agua_sintetico.csv", config_agua(estado="borrador"), administrador)
    return administrador


def _validar(ev, usuario):
    Evidencia.objects.filter(pk=ev.pk).update(
        estado_validacion=EstadoValidacion.VALIDADA,
        validado_por=usuario,
        validado_en="2026-11-10T10:00Z",
    )


def test_la_marca_solo_aparece_en_las_validadas(importado, client):
    client.force_login(importado)
    ev = Evidencia.objects.order_by("pk").first()
    assert not ev.validada_por_dircom
    assert MARCA_VALIDACION not in client.get(f"/evidencias/{ev.pk}/").content.decode()

    nivel_antes = ev.nivel
    _validar(ev, importado)
    ev.refresh_from_db()
    assert ev.validada_por_dircom
    assert ev.nivel == nivel_antes  # la marca no cambia el nivel de la fuente
    html = client.get(f"/evidencias/{ev.pk}/").content.decode()
    assert MARCA_VALIDACION in html and importado.email in html
    assert MARCA_VALIDACION in client.get("/evidencias/").content.decode()


def test_panel_municipal_muestra_la_marca(importado, client):
    client.force_login(importado)
    ev = Evidencia.objects.filter(municipios__isnull=False).order_by("pk").first()
    municipio = Municipio.objects.get(evidencias=ev)
    url = f"/municipios/{municipio.codigo_ine}/"
    assert MARCA_VALIDACION not in client.get(url, HTTP_HX_REQUEST="true").content.decode()
    _validar(ev, importado)
    assert MARCA_VALIDACION in client.get(url, HTTP_HX_REQUEST="true").content.decode()
