"""Mapa municipal (RF-50, docs/05 §1). CP-07: municipio sin registro → «No localizado»."""

import io
import json

import openpyxl
import pytest
from django.urls import reverse

from apps.cuadro import services
from apps.evidencias.enums import NivelEvidencia
from apps.evidencias.importers.tabla_municipal import importar_tabla
from tests.evidencias.test_tabla_municipal import FIXTURES, config_agua


@pytest.fixture
def con_datos(municipios_cv, competidores, administrador):
    importar_tabla(FIXTURES / "agua_sintetico.csv", config_agua(), administrador)
    return administrador


def _por_codigo(datos):
    return {m["codigo"]: m for m in datos["municipios"]}


def test_cp07_municipio_sin_registro_es_no_localizado(con_datos):
    datos = _por_codigo(services.datos_mapa(services.Filtro(servicio="agua")))
    assert len(datos) == 542
    onil = datos["03095"]  # Onil: sin ningún registro
    assert onil["nivel"] == NivelEvidencia.NO_LOCALIZADO
    assert onil["nivel_label"] == "No localizado"
    assert onil["categoria"] == "no_localizado"
    assert onil["operadores"] == []
    agost = datos["03002"]
    assert agost["nivel"] == NivelEvidencia.EMPRESA and agost["operadores"][0]["nombre"] == "Veolia"

    tabla = {f["codigo"]: f for f in services.tabla_equivalente()}
    assert tabla["03095"]["agua"] == {"texto": "No localizado", "nivel": "No localizado"}
    assert tabla["03095"]["residuos"]["texto"] == "No localizado"
    assert tabla["03002"]["agua"]["texto"] == "Veolia"

    ind = services.indicadores(list(datos.values()))
    assert ind["total"] == 542 and ind["con_operador"] == 3
    no_loc = next(n for n in ind["por_nivel"] if n["nivel"] == NivelEvidencia.NO_LOCALIZADO)
    assert no_loc["n"] == 539


def test_cp07_en_la_pagina_y_la_exportacion(con_datos, client):
    client.force_login(con_datos)
    r = client.get(reverse("mapa"))
    assert r.status_code == 200
    html = r.content.decode()
    assert "No localizado" in html
    datos = json.loads(
        html.split('id="datos-mapa" type="application/json">')[1].split("</script>")[0]
    )
    assert datos["03095"]["nivel_label"] == "No localizado"

    r = client.get(reverse("exportar_tabla", args=["csv"]))
    filas = r.content.decode("utf-8-sig").splitlines()
    onil = next(f for f in filas if f.startswith("03095"))
    assert onil.count("No localizado") == 6  # operador y nivel de los tres servicios
    assert ",0," not in onil

    r = client.get(reverse("exportar_tabla", args=["xlsx"]))
    libro = openpyxl.load_workbook(io.BytesIO(r.content))
    filas = list(libro["Municipios"].iter_rows(values_only=True))
    assert len(filas) == 543
    assert client.get(reverse("exportar_tabla", args=["pdf"])).status_code == 404


def test_borradores_ocultos_por_defecto(municipios_cv, competidores, administrador):
    importar_tabla(FIXTURES / "agua_sintetico.csv", config_agua(estado="borrador"), administrador)
    sin = _por_codigo(services.datos_mapa(services.Filtro(servicio="agua")))
    assert sin["03002"]["nivel"] == NivelEvidencia.NO_LOCALIZADO
    con = _por_codigo(
        services.datos_mapa(services.Filtro(servicio="agua", incluir_borradores=True))
    )
    assert con["03002"]["solo_borradores"] is True
    assert services.tabla_equivalente(borradores=True)[0]  # no falla
    fila = {f["codigo"]: f for f in services.tabla_equivalente(borradores=True)}["03002"]
    assert fila["agua"]["texto"] == "Veolia [borrador]"


def test_modo_operador_colores_estables(con_datos):
    filtro = services.Filtro(servicio="agua", modo="operador")
    datos = services.datos_mapa(filtro)
    assert [e.nombre for e in datos["resaltadas"]] == ["Veolia"]
    agost = _por_codigo(datos)["03002"]
    assert agost["color_operador"] == services.COLORES_OPERADOR[0]
    # Filtrar por provincia no cambia el color de la empresa.
    alicante = services.datos_mapa(
        services.Filtro(servicio="agua", modo="operador", provincia="03")
    )
    assert _por_codigo(alicante)["03002"]["color_operador"] == services.COLORES_OPERADOR[0]
    xixona = next(m for m in datos["municipios"] if m["nombre"].startswith("Xixona"))
    assert xixona["categoria"] == "otros"  # operador fuera del catálogo


def test_panel_municipio(con_datos, client, lector):
    client.force_login(lector)
    r = client.get(reverse("municipio", args=["03002"]), HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    html = r.content.decode()
    assert "Veolia" in html and "<html" not in html
    assert "admin/" not in html  # el lector no ve enlaces a la administración
    r = client.get(reverse("municipio", args=["03095"]))
    assert "No localizado" in r.content.decode()
    assert client.get(reverse("municipio", args=["99999"])).status_code == 404


def test_suministro_electrico_no_cuenta_como_energia(
    municipios_cv, competidores, administrador, tmp_path
):
    from tests.evidencias.test_tabla_municipal import _libro

    ruta = _libro(tmp_path, [["AGOST", "Iberdrola Clientes (2024)"]], ["MUNICIPIO", "SUMINISTRO"])
    config = config_agua(hoja="Municipios")
    config["bloques"] = [
        {
            "servicio": "energia",
            "alcance": "suministro_electrico",
            "columna_operador": "SUMINISTRO",
            "nivel_por_defecto": "parcial",
        }
    ]
    importar_tabla(ruta, config, administrador)
    energia = _por_codigo(services.datos_mapa(services.Filtro(servicio="energia")))
    assert energia["03002"]["nivel"] == NivelEvidencia.NO_LOCALIZADO
    suministro = _por_codigo(
        services.datos_mapa(services.Filtro(servicio="energia", alcance="suministro_electrico"))
    )
    assert suministro["03002"]["nivel"] == NivelEvidencia.PARCIAL
