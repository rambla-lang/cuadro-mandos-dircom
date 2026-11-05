from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from openpyxl import Workbook

from apps.territorio.importers.ine import FormatoIneError, importar_municipios_ine
from apps.territorio.models import Municipio, Provincia
from tests.conftest import SEED

FICHERO = SEED / "ine" / "26codmun.xlsx"


def test_carga_los_542_municipios_valencianos(municipios_cv):
    lote = municipios_cv
    assert lote.leidos == 542 and lote.nuevos == 542 and lote.actualizados == 0
    assert Municipio.objects.count() == 542
    por_prov = {p.codigo_ine: p.municipios.count() for p in Provincia.objects.all()}
    assert por_prov == {"03": 141, "12": 135, "46": 266}
    assert set(Provincia.objects.values_list("comunidad", flat=True)) == {"Comunitat Valenciana"}
    assert Provincia.objects.get(codigo_ine="46").nombre == "Valencia/València"
    assert lote.archivo_sha256 and lote.fin is not None


def test_codigo_y_nombres(municipios_cv):
    eliana = Municipio.objects.get(codigo_ine="46116")
    assert eliana.nombre_oficial == "Eliana, l'"
    assert eliana.nombres_alternativos == ["l'Eliana", "Eliana"]
    elche = Municipio.objects.get(codigo_ine="03065")
    assert elche.nombres_alternativos == ["Elx", "Elche"]
    assert Municipio.objects.filter(lote_importacion=municipios_cv).count() == 542


def test_segunda_carga_no_duplica_y_respeta_alias_manuales(municipios_cv):
    chiva = Municipio.objects.get(codigo_ine="46111")
    chiva.nombres_alternativos = [*chiva.nombres_alternativos, "EL BOSQUE-CHIVA"]
    chiva.save()

    lote2 = importar_municipios_ine(FICHERO, ["03", "12", "46"], "Comunitat Valenciana")

    assert lote2.nuevos == 0 and lote2.actualizados == 0 and lote2.leidos == 542
    assert Municipio.objects.count() == 542
    chiva.refresh_from_db()
    assert "EL BOSQUE-CHIVA" in chiva.nombres_alternativos


def test_actualiza_nombre_si_cambia_en_el_ine(municipios_cv):
    Municipio.objects.filter(codigo_ine="03002").update(nombre_oficial="Agost (antiguo)")
    lote = importar_municipios_ine(FICHERO, ["03"], "Comunitat Valenciana")
    assert lote.actualizados == 1
    assert Municipio.objects.get(codigo_ine="03002").nombre_oficial == "Agost"
    assert "Agost (antiguo)" in lote.log


def test_comando(db):
    salida = StringIO()
    call_command(
        "cargar_municipios",
        "--provincias",
        "12",
        "--comunidad",
        "Comunitat Valenciana",
        stdout=salida,
    )
    assert "nuevos 135" in salida.getvalue()


def test_comando_fichero_inexistente(db, tmp_path):
    with pytest.raises(CommandError):
        call_command(
            "cargar_municipios",
            "--fichero",
            str(tmp_path / "no.xlsx"),
            "--provincias",
            "12",
            "--comunidad",
            "X",
        )


def test_formato_inesperado_no_carga_nada(db, tmp_path):
    ruta = tmp_path / "malo.xlsx"
    libro = Workbook()
    hoja = libro.active
    hoja.title = "12"
    hoja.append(["título"])
    hoja.append(["Castellón/Castelló"])
    hoja.append(["COD", "MUN", "NOMBRE"])
    libro.save(ruta)
    with pytest.raises(FormatoIneError):
        importar_municipios_ine(ruta, ["12"], "Comunitat Valenciana")
    assert Municipio.objects.count() == 0


def test_otra_comunidad_sin_cambiar_codigo(db):
    """RF-13: añadir otra comunidad solo exige cambiar los argumentos."""
    lote = importar_municipios_ine(FICHERO, ["30"], "Región de Murcia")
    assert lote.nuevos == Municipio.objects.filter(provincia__codigo_ine="30").count() > 0
