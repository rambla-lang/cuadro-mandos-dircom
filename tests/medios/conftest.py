"""Datos sintéticos de Brandwatch con la cabecera real de seed/ (docs/09)."""

import csv
import io

import pytest

from tests.conftest import SEED

CABECERA = (SEED / "brandwatch_cabecera_ejemplo.csv").read_text(encoding="utf-8")


def fila(**v) -> dict:
    base = {
        "Query Id": "1",
        "Query Name": "MONITORIZACION COMPETENCIA",
        "Date": "2026-10-10 08:30:00.000",
        "Sentiment": "neutral",
        "Page Type": "news",
        "Language": "es",
        "Country": "Spain",
        "Region": "",
    }
    base.update(v)
    return base


def csv_brandwatch(filas: list[dict]) -> bytes:
    lineas = CABECERA.splitlines()
    cabecera = next(csv.reader([lineas[8]]))
    salida = io.StringIO()
    salida.write("\n".join(lineas[:8]) + "\n")
    w = csv.writer(salida, quoting=csv.QUOTE_ALL)
    w.writerow(cabecera)
    for i, f in enumerate(filas, start=1):
        w.writerow([str(i) if c == "" else f.get(c, "") for c in cabecera])
    return salida.getvalue().encode("utf-8")


FILAS = [
    fila(
        **{
            "Resource Id": "r1",
            "Title": "FACSA renueva la red de agua de Vila-real",
            "Snippet": "La empresa FACSA ejecutará las obras en Vila-real.",
            "Url": "https://www.diario-sintetico.es/noticia-1?utm_source=tw&id=5",
            "Domain": "diario-sintetico.es",
            "Sentiment": "positive",
        }
    ),
    fila(
        **{
            "Resource Id": "r2",
            "Title": "Aqualia y FACSA, en el foro del agua de Castelló",
            "Snippet": "Representantes de Aqualia y de FACSA debatieron en Castelló.",
            "Url": "https://otro-medio.es/foro",
            "Domain": "otro-medio.es",
        }
    ),
    fila(
        **{
            "Resource Id": "r3",
            "Title": "Cox estrena su planta solar",
            "Snippet": "La compañía Cox anuncia resultados.",
            "Url": "https://economia.es/cox",
            "Domain": "economia.es",
            "Language": "ca",
        }
    ),
    fila(
        **{
            "Resource Id": "r4",
            "Title": "Urbaser gana un contrato en Madrid",
            "Snippet": "Urbaser se adjudica la limpieza en Madrid.",
            "Url": "https://nacional.es/u",
            "Domain": "nacional.es",
            "Sentiment": "negative",
        }
    ),
    fila(
        **{
            "Resource Id": "r5",
            "Title": "La misma noticia, republicada",
            "Snippet": "FACSA ejecutará las obras en Vila-real.",
            "Url": "https://diario-sintetico.es/noticia-1/?id=5&fbclid=abc",
            "Domain": "diario-sintetico.es",
        }
    ),
    fila(
        **{
            "Resource Id": "r6",
            "Title": "Un tuit sin empresas",
            "Snippet": "Hola",
            "Url": "https://twitter.com/x/status/1",
            "Domain": "twitter.com",
            "Page Type": "twitter",
        }
    ),
]


@pytest.fixture
def base_medios(municipios_cv, empresas_gestoras, administrador):
    from apps.medios.analisis import limpiar_caches

    limpiar_caches()
    return administrador
