"""ADR-006: el GeoJSON estático tiene un polígono por municipio del INE, unidos por código."""

import json
from pathlib import Path

from django.conf import settings

from apps.territorio.models import Municipio

GEOJSON = Path(settings.BASE_DIR) / "static" / "geo" / "municipios_cv.json"


def test_geojson_casa_con_los_municipios_del_ine(municipios_cv):
    datos = json.loads(GEOJSON.read_text(encoding="utf-8"))
    codigos = [f["properties"]["codigo_ine"] for f in datos["features"]]
    assert len(codigos) == len(set(codigos)) == 542
    assert set(codigos) == set(Municipio.objects.values_list("codigo_ine", flat=True))
    assert all(f["geometry"]["coordinates"] for f in datos["features"])
    assert "CC BY 4.0 ign.es" in datos["metadatos"]["atribucion"]
    assert GEOJSON.stat().st_size < 2 * 1024 * 1024  # objetivo de ADR-006
