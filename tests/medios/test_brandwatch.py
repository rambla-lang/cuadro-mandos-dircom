"""Brandwatch (docs/04 §4). CP-01, CP-02 y CP-08."""

from datetime import date

import pytest

from apps.evidencias.enums import EstadoValidacion
from apps.medios import metricas
from apps.medios.analisis import url_canonica, vinculo_territorial
from apps.medios.importers.brandwatch import FormatoBrandwatchError, importar_brandwatch, leer_csv
from apps.medios.models import Mencion, MencionEmpresa, Pieza
from apps.nucleo.models import ElementoRevision

from .conftest import FILAS, csv_brandwatch


def test_lee_la_cabecera_real_aunque_haya_metadatos_query_id():
    meta, filas = leer_csv(csv_brandwatch(FILAS))
    assert meta["Query Id"] == "[2004165123]"
    assert len(filas) == 6 and filas[0]["Resource Id"] == "r1"


def test_rechaza_un_csv_que_no_es_de_brandwatch():
    with pytest.raises(FormatoBrandwatchError):
        leer_csv(b"a,b,c\n1,2,3\n")


def test_importa_atribuye_y_deduplica(base_medios):
    r = importar_brandwatch(csv_brandwatch(FILAS), "mentions (8).csv", base_medios)
    assert r.nuevas == 6 and r.existentes == 0
    # r1 y r5 son la misma URL canónica: una pieza y dos menciones.
    assert r.piezas_nuevas == 5
    assert (
        Mencion.objects.get(resource_id="r1").pieza == Mencion.objects.get(resource_id="r5").pieza
    )
    facsa = MencionEmpresa.objects.filter(empresa__nombre="FACSA")
    assert facsa.count() == 3 and all(m.estado_validacion == "validada" for m in facsa)
    # «Cox» requiere contexto: borrador y a la bandeja.
    cox = MencionEmpresa.objects.get(empresa__nombre="Cox")
    assert cox.estado_validacion == EstadoValidacion.BORRADOR
    assert ElementoRevision.objects.filter(tipo="atribucion_mencion").count() == 1
    # Vínculo territorial: Vila-real sí; Madrid no; el tuit sin lugar, dudoso.
    assert Mencion.objects.get(resource_id="r1").vinculo_territorial == "si"
    assert Mencion.objects.get(resource_id="r4").vinculo_territorial == "no"
    assert Mencion.objects.get(resource_id="r6").vinculo_territorial == "dudoso"
    # Author no se guarda (P-06); Estimated Reach iría a datos_fuente pero no se usa.
    assert "Author" not in Mencion.objects.get(resource_id="r1").datos_fuente


def test_cp01_reimportar_el_mismo_csv(base_medios):
    contenido = csv_brandwatch(FILAS)
    importar_brandwatch(contenido, "a.csv", base_medios)
    r = importar_brandwatch(contenido, "a.csv", base_medios)
    assert r.nuevas == 0 and r.existentes == 6
    assert Mencion.objects.count() == 6


def test_cp02_exports_solapados(base_medios):
    importar_brandwatch(csv_brandwatch(FILAS[:4]), "mentions (8).csv", base_medios)
    r = importar_brandwatch(csv_brandwatch(FILAS[2:]), "mentions (9).csv", base_medios)
    assert r.existentes == 2 and r.nuevas == 2
    assert Mencion.objects.count() == 6


def test_cp08_pieza_compartida(base_medios):
    importar_brandwatch(csv_brandwatch(FILAS), "a.csv", base_medios)
    d = metricas.calcular(metricas.Filtro(date(2026, 1, 1), date(2026, 12, 31)))
    por_empresa = {e["nombre"]: e["piezas"] for e in d["empresas"]}
    # Piezas con vínculo «si»: noticia-1 (FACSA, dos menciones) y foro (Aqualia + FACSA).
    assert d["total"] == 2
    assert por_empresa == {"FACSA": 2, "Aqualia": 1}
    assert d["suma_por_empresa"] == 3  # la compartida cuenta para cada empresa
    assert next(e for e in d["empresas"] if e["nombre"] == "Aqualia")["cuota"] == 50.0
    # Sin filtro de vínculo entra Urbaser (Madrid); Cox sigue fuera por estar sin validar.
    todas = metricas.calcular(
        metricas.Filtro(date(2026, 1, 1), date(2026, 12, 31), solo_vinculo=False)
    )
    assert {e["nombre"] for e in todas["empresas"]} == {"FACSA", "Aqualia", "Urbaser"}


@pytest.mark.parametrize(
    ("url", "esperada"),
    [
        ("https://www.Medio.es/a/b/?utm_source=x&utm_medium=y", "https://medio.es/a/b"),
        ("http://medio.es/a?id=3&fbclid=zz#arriba", "https://medio.es/a?id=3"),
        ("https://medio.es/", "https://medio.es"),
    ],
)
def test_url_canonica(url, esperada):
    assert url_canonica(url) == esperada


def test_vinculo_no_se_engana_con_nombres_ambiguos(base_medios):
    assert vinculo_territorial("Manuel y Teresa visitan Barcelona")[0] == "no"
    assert vinculo_territorial("Aguas de Valencia gana en Barcelona")[0] == "no"
    assert vinculo_territorial("Obras en l'Eliana")[0] == "si"


def test_vistas_medios(base_medios, client, lector, analista):
    importar_brandwatch(csv_brandwatch(FILAS), "a.csv", base_medios)
    client.force_login(lector)
    r = client.get("/medios/?desde=2026-01-01&hasta=2026-12-31")
    assert r.status_code == 200 and "FACSA" in r.content.decode()
    assert (
        client.get("/medios/piezas/?desde=2026-01-01&hasta=2026-12-31&empresa=FACSA").status_code
        == 200
    )
    m = Mencion.objects.get(resource_id="r1")
    assert client.get(f"/medios/menciones/{m.pk}/").status_code == 200
    assert (
        client.post(
            f"/medios/menciones/{m.pk}/", {"accion": "vinculo", "vinculo": "no"}
        ).status_code
        == 403
    )
    assert client.get("/importar/brandwatch/").status_code == 403

    client.force_login(analista)
    from apps.entidades.models import Empresa

    stv = Empresa.objects.get(nombre="STV")
    client.post(f"/medios/menciones/{m.pk}/", {"accion": "atribuir", "empresa": stv.pk})
    assert MencionEmpresa.objects.get(mencion=m, empresa=stv).metodo == "manual"
    from django.core.files.uploadedfile import SimpleUploadedFile

    archivo = SimpleUploadedFile("b.csv", csv_brandwatch(FILAS), content_type="text/csv")
    r = client.post("/importar/brandwatch/", {"archivos": [archivo]})
    assert r.status_code == 200 and "Ya existentes" in r.content.decode()
    assert Pieza.objects.count() == 5
