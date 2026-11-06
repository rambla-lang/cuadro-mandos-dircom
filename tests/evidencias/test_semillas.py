"""Las tres tablas de seed/ con sus plantillas (prueba de aceptación de la Fase 2)."""

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.urls import reverse

from apps.evidencias.enums import EstadoValidacion
from apps.evidencias.models import Evidencia, PlantillaImportacion, PrestacionServicio
from apps.nucleo.models import ElementoRevision
from tests.conftest import SEED

PLANTILLAS = SEED / "plantillas_importacion"


def _importar(fichero, plantilla, *extra):
    salida = io.StringIO()
    call_command(
        "importar_tabla_municipal",
        "--fichero",
        str(SEED / fichero),
        "--plantilla",
        str(PLANTILLAS / plantilla),
        "--usuario",
        "admin@example.com",
        *extra,
        stdout=salida,
    )
    return salida.getvalue()


@pytest.fixture
def base(municipios_cv, competidores, administrador):
    return administrador


def test_semillas_completas(base):
    salida = _importar("municipios_veolia_agua.csv", "veolia_agua_csv.json")
    assert "evidencias nuevas 69" in salida
    pendientes = set(
        ElementoRevision.objects.filter(tipo="municipio_no_resuelto").values_list(
            "texto", flat=True
        )
    )
    assert {"TAVERNES", "EL BOSQUE-CHIVA"} <= pendientes
    assert (
        PrestacionServicio.objects.filter(servicio="agua", empresa__nombre="Veolia").count() == 69
    )

    _importar("Municipios_Veolia_agua_residuos_energia.xlsx", "veolia_residuos_energia_xlsx.json")
    # El resumen del propio Excel: 31 residuos con fuente oficial. Los que no casan
    # (TAVERNES, EL BOSQUE-CHIVA…) o no traen URL quedan en la bandeja.
    oficiales = Evidencia.objects.filter(
        servicio="residuos", nivel="oficial", estado_validacion=EstadoValidacion.VALIDADA
    ).count()
    assert 0 < oficiales <= 31

    _importar("cruce_servicios_municipales_CV.xlsx", "cruce_servicios_cv_xlsx.json")
    cruce = Evidencia.objects.filter(fuente__nombre__startswith="Cruce")
    assert cruce.exists()
    assert not cruce.filter(estado_validacion=EstadoValidacion.VALIDADA).exists()

    # Segunda pasada completa: nada nuevo.
    total = Evidencia.objects.count()
    assert "evidencias nuevas 0" in _importar("municipios_veolia_agua.csv", "veolia_agua_csv.json")
    assert Evidencia.objects.count() == total


def test_simular_y_errores_del_comando(base):
    assert "Simulación" in _importar(
        "municipios_veolia_agua.csv", "veolia_agua_csv.json", "--simular"
    )
    assert Evidencia.objects.count() == 0
    assert PlantillaImportacion.objects.count() == 1  # la plantilla sí queda guardada
    with pytest.raises(CommandError):
        call_command(
            "importar_tabla_municipal",
            "--fichero",
            str(SEED / "municipios_veolia_agua.csv"),
            "--plantilla",
            "no existe",
            "--usuario",
            "admin@example.com",
        )
    with pytest.raises(CommandError):
        call_command(
            "importar_tabla_municipal",
            "--fichero",
            str(SEED / "municipios_veolia_agua.csv"),
            "--plantilla",
            "no existe",
            "--usuario",
            "nadie@example.com",
        )


def test_asistente_excel_con_plantilla_pasa_por_la_hoja(base, client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    _importar("municipios_veolia_agua.csv", "veolia_agua_csv.json", "--simular")
    call_command(
        "importar_tabla_municipal",
        "--fichero",
        str(SEED / "cruce_servicios_municipales_CV.xlsx"),
        "--plantilla",
        str(PLANTILLAS / "cruce_servicios_cv_xlsx.json"),
        "--usuario",
        "admin@example.com",
        "--simular",
        stdout=io.StringIO(),
    )
    plantilla = PlantillaImportacion.objects.get(nombre__startswith="Cruce")
    client.force_login(base)
    archivo = SimpleUploadedFile(
        "cruce.xlsx", (SEED / "cruce_servicios_municipales_CV.xlsx").read_bytes()
    )
    r = client.post(reverse("importar_tabla"), {"archivo": archivo, "plantilla": plantilla.pk})
    assert r.url == reverse("importar_tabla_hoja")
    r = client.get(r.url)
    assert "Municipios" in r.content.decode()
    r = client.post(reverse("importar_tabla_hoja"), {"hoja": "Municipios", "fila_cabecera": 1})
    assert r.url == reverse("importar_tabla_columnas")
    r = client.get(r.url)
    assert r.status_code == 200 and "Nealis / FACSA" in r.content.decode()
    r = client.get(reverse("importar_tabla_valores"))
    html = r.content.decode()
    assert "Sin verificar figura" in html and "Saneamiento (alcantarillado)" in html
    r = client.post(reverse("importar_tabla_confirmar"), {"cancelar": "1"})
    assert r.url == reverse("importar")
    assert not list((tmp_path / "importaciones" / "pendientes").iterdir())
