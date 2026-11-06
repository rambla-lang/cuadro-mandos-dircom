"""Importador de tablas municipales (docs/04 §9)."""

from pathlib import Path

import openpyxl
import pytest

from apps.evidencias.enums import EstadoValidacion, Gestion, NivelEvidencia
from apps.evidencias.importers.tabla_municipal import (
    FormatoTablaError,
    importar_tabla,
    leer_tabla,
    proponer_nivel,
)
from apps.evidencias.models import Evidencia, PrestacionServicio
from apps.nucleo.models import ElementoRevision, LoteImportacion

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "tabla_municipal"
Tipo = ElementoRevision.Tipo


def config_agua(**extra):
    config = {
        "hoja": None,
        "fila_cabecera": 1,
        "columna_municipio": "MUNICIPIO",
        "columna_provincia": None,
        "fuente": {"tipo": "documento_interno", "nombre": "Tabla sintética de agua"},
        "fecha_consulta": "2026-11-03",
        "estado": "validada",
        "valores_nivel": {},
        "bloques": [
            {
                "servicio": "agua",
                "alcance": "",
                "columna_operador": "SERVICIO DE AGUAS",
                "nivel_por_defecto": "empresa",
            }
        ],
    }
    config.update(extra)
    return config


@pytest.fixture
def entorno(municipios_cv, competidores, administrador):
    return administrador


def test_lee_csv_con_punto_y_coma():
    cabeceras, filas = leer_tabla(FIXTURES / "agua_sintetico.csv")
    assert cabeceras == ["MUNICIPIO", "SERVICIO DE AGUAS", "SERVICIO DE RESIDUOS"]
    assert len(filas) == 5
    assert filas[1][1]["MUNICIPIO"] == "L'ELIANA"


def test_importa_csv_resuelve_y_manda_a_la_bandeja(entorno):
    res = importar_tabla(FIXTURES / "agua_sintetico.csv", config_agua(), entorno)

    assert res.evidencias_nuevas == 3  # Agost, l'Eliana y Xixona
    assert res.a_revision == {Tipo.MUNICIPIO_NO_RESUELTO: 2, Tipo.OPERADOR_NO_RESUELTO: 1}
    pendientes = set(
        ElementoRevision.objects.filter(tipo=Tipo.MUNICIPIO_NO_RESUELTO).values_list(
            "texto", flat=True
        )
    )
    assert pendientes == {"TAVERNES", "EL BOSQUE-CHIVA"}

    eliana = PrestacionServicio.objects.get(municipio__codigo_ine="46116")
    assert eliana.empresa.nombre == "Veolia"  # «AIGÜES DE L'HORTA (VEOLIA)»
    assert eliana.operador_texto == "AIGÜES DE L'HORTA (VEOLIA)"
    assert eliana.nivel == NivelEvidencia.EMPRESA
    xixona = PrestacionServicio.objects.get(municipio__nombre_oficial__startswith="Xixona")
    assert xixona.empresa is None and xixona.gestion == Gestion.INDIRECTA

    ev = eliana.evidencias.get()
    assert ev.estado_validacion == EstadoValidacion.VALIDADA
    assert ev.validado_por == entorno and ev.fecha_consulta.isoformat() == "2026-11-03"
    assert ev.codigo.startswith("E-") and ev.lote_importacion_id == res.lote_id


def test_reimportar_no_duplica(entorno):
    importar_tabla(FIXTURES / "agua_sintetico.csv", config_agua(), entorno)
    res = importar_tabla(FIXTURES / "agua_sintetico.csv", config_agua(), entorno)
    assert res.evidencias_nuevas == 0
    assert res.evidencias_existentes == 3
    assert res.total_revision == 0 and res.ya_en_revision == 2
    assert Evidencia.objects.count() == 3
    assert ElementoRevision.objects.count() == 3
    assert LoteImportacion.objects.filter(tipo="tabla_municipal").count() == 2


def test_simulacion_no_guarda_nada(entorno):
    res = importar_tabla(FIXTURES / "agua_sintetico.csv", config_agua(), entorno, aplicar=False)
    assert res.evidencias_nuevas == 3 and not res.aplicado
    assert Evidencia.objects.count() == 0
    assert ElementoRevision.objects.count() == 0
    assert not LoteImportacion.objects.filter(tipo="tabla_municipal").exists()


def test_configuracion_incompleta(entorno):
    with pytest.raises(FormatoTablaError, match="columna de municipio"):
        importar_tabla(FIXTURES / "agua_sintetico.csv", config_agua(columna_municipio="X"), entorno)


def _libro(tmp_path, filas, cabecera):
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.title = "Municipios"
    hoja.append(cabecera)
    for f in filas:
        hoja.append(f)
    ruta = tmp_path / "tabla.xlsx"
    libro.save(ruta)
    return ruta


CABECERA_RESIDUOS = ["MUNICIPIO", "RESIDUOS", "Detalle", "Fuente", "Año", "Nivel"]


def config_residuos(**extra):
    config = {
        "hoja": "Municipios",
        "fila_cabecera": 1,
        "columna_municipio": "MUNICIPIO",
        "fuente": {"tipo": "documento_interno", "nombre": "Excel sintético"},
        "fecha_consulta": "2026-11-03",
        "estado": "validada",
        "valores_nivel": {},
        "bloques": [
            {
                "servicio": "residuos",
                "alcance": "",
                "columna_operador": "RESIDUOS",
                "columna_detalle": "Detalle",
                "columna_fuente": "Fuente",
                "columna_anio": "Año",
                "columna_nivel": "Nivel",
                "nivel_por_defecto": "decidir",
            }
        ],
    }
    config.update(extra)
    return config


def test_excel_niveles_urls_y_casos_especiales(entorno, tmp_path):
    ruta = _libro(
        tmp_path,
        [
            # URL literal
            [
                "AGOST",
                "Urbaser",
                "Recogida",
                "TED 1-2022 (https://ted.europa.eu/x/1-2022)",
                2022,
                "Confirmado (fuente oficial)",
            ],
            # solo número de TED: se forma el enlace verificado
            [
                "SAX",
                "FCC (prórroga)",
                "Limpieza",
                "TED 302949-2021",
                2021,
                "Confirmado (fuente oficial) (contrato de 2019)",
            ],
            # oficial sin URL ni TED: a la bandeja, nivel provisional parcial en borrador
            [
                "IBI",
                "Urbaser (limpieza viaria)",
                "",
                "Acta del pleno",
                "—",
                "Confirmado (fuente oficial)",
            ],
            # varios operadores: a la bandeja de operador
            ["ELDA", "UTE Urbaser + FCC Medio Ambiente", "", "Prensa", 2020, "Parcial"],
            # gestión directa: sin empresa y sin bandeja
            ["ORIHUELA", "Gestión directa municipal", "", "Prensa", None, "Confirmado (prensa)"],
            # «No localizado» con detalle: se guarda como evidencia no_localizado
            [
                "MANUEL",
                "No localizado",
                "Adjudicación sin nombre",
                "TED 477621-2026",
                2026,
                "No localizado",
            ],
            # «No localizado» sin nada: no se guarda
            ["ONIL", "No localizado", None, None, None, "No localizado"],
            # alias ambiguo (ACCIONA requiere contexto): no se resuelve solo
            ["CATRAL", "ACCIONA", "", "Nota", 2023, "Confirmado por la empresa"],
        ],
        CABECERA_RESIDUOS,
    )
    res = importar_tabla(ruta, config_residuos(), entorno)

    assert res.celdas_sin_dato == 1
    assert res.evidencias_nuevas == 7
    assert res.a_revision == {Tipo.NIVEL_POR_DECIDIR: 1, Tipo.OPERADOR_NO_RESUELTO: 2}

    agost = Evidencia.objects.get(municipios__codigo_ine="03002")
    assert agost.url_origen == "https://ted.europa.eu/x/1-2022"
    assert agost.nivel == NivelEvidencia.OFICIAL
    assert agost.datos_extra["anio"] == 2022

    sax = Evidencia.objects.get(municipios__nombre_oficial="Sax")
    assert sax.url_origen == "https://ted.europa.eu/es/notice/-/detail/302949-2021"
    assert sax.datos_extra["url_derivada_de"] == "TED 302949-2021"
    assert sax.prestaciones.get().empresa.nombre == "FCC"

    ibi = Evidencia.objects.get(municipios__nombre_oficial="Ibi")
    assert ibi.nivel == NivelEvidencia.PARCIAL
    assert ibi.estado_validacion == EstadoValidacion.BORRADOR
    assert "no trae URL" in ibi.tratamiento_limites

    orihuela = PrestacionServicio.objects.get(municipio__nombre_oficial="Orihuela")
    assert orihuela.gestion == Gestion.DIRECTA_MUNICIPAL and orihuela.empresa is None

    manuel = PrestacionServicio.objects.get(municipio__nombre_oficial="Manuel")
    assert manuel.gestion == Gestion.NO_LOCALIZADA
    assert manuel.nivel == NivelEvidencia.NO_LOCALIZADO

    assert not PrestacionServicio.objects.filter(municipio__nombre_oficial="Onil").exists()
    operadores = set(
        ElementoRevision.objects.filter(tipo=Tipo.OPERADOR_NO_RESUELTO).values_list(
            "texto", flat=True
        )
    )
    assert operadores == {"UTE Urbaser + FCC Medio Ambiente", "ACCIONA"}


def test_formato_largo_borrador_y_provincia(entorno, tmp_path):
    ruta = _libro(
        tmp_path,
        [
            [
                "Nealis / FACSA",
                "Agua",
                "Almassora",
                "Castellón (según mi conocimiento)",
                "Confirmado",
            ],
            ["Aqualia", "Saneamiento (alcantarillado)", "Oropesa del Mar", "Castellón", "Parcial"],
            ["Aqualia", "Agua", "Alcoy / Alcoi", "Alicante", "Sin verificar figura"],
            [
                "Aqualia",
                "Agua",
                "Otros 22 municipios (sin identificar)",
                "Comunitat Valenciana",
                "Sin verificar figura",
            ],
            ["Aqualia", "Gas", "Alcoy / Alcoi", "Alicante", "Parcial"],
        ],
        ["Empresa", "Servicio", "Municipio", "Provincia", "Verificación"],
    )
    config = {
        "hoja": "Municipios",
        "columna_municipio": "Municipio",
        "columna_provincia": "Provincia",
        "fuente": {"tipo": "otra", "nombre": "Cruce sintético"},
        "fecha_consulta": "2026-11-01",
        "estado": "borrador",
        "valores_nivel": {
            "Confirmado": "decidir",
            "Parcial": "parcial",
            "Sin verificar figura": "parcial",
        },
        "bloques": [
            {
                "servicio": "",
                "columna_servicio": "Servicio",
                "valores_servicio": {
                    "Agua": {"servicio": "agua", "alcance": ""},
                    "Saneamiento (alcantarillado)": {"servicio": "agua", "alcance": "saneamiento"},
                },
                "columna_operador": "Empresa",
                "columna_nivel": "Verificación",
            }
        ],
    }
    res = importar_tabla(ruta, config, entorno)

    assert res.evidencias_nuevas == 3
    assert len(res.errores) == 1 and "Gas" in res.errores[0]
    assert res.a_revision == {Tipo.NIVEL_POR_DECIDIR: 1, Tipo.MUNICIPIO_NO_RESUELTO: 1}
    almassora = PrestacionServicio.objects.get(municipio__nombre_oficial="Almassora")
    assert almassora.empresa.nombre == "FACSA"  # «Nealis / FACSA»: todas las partes, FACSA
    oropesa = PrestacionServicio.objects.get(municipio__nombre_oficial__startswith="Orpesa")
    assert oropesa.alcance == "saneamiento"
    assert PrestacionServicio.objects.filter(municipio__codigo_ine="03009").exists()  # Alcoi
    assert not Evidencia.objects.filter(estado_validacion=EstadoValidacion.VALIDADA).exists()


@pytest.mark.parametrize(
    ("valor", "nivel"),
    [
        ("Confirmado (fuente oficial) (municipio de Chiva)", "oficial"),
        ("Confirmado (prensa) (fecha no consta)", "prensa"),
        ("Confirmado por la empresa", "empresa"),
        ("Parcial (renovación, no gestión)", "parcial"),
        ("No localizado", "no_localizado"),
        ("Confirmado", None),
        ("Sin verificar figura", None),
    ],
)
def test_proponer_nivel(valor, nivel):
    assert proponer_nivel(valor) == nivel
