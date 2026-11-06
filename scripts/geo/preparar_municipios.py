# /// script
# requires-python = ">=3.12"
# dependencies = ["topojson==1.10", "shapely==2.1.1"]
# ///
"""Prepara el GeoJSON municipal simplificado de una comunidad (ADR-006).

Fuente (verificada el 06/11/2026, docs/04 §11):
  Servicio WFS INSPIRE «Unidades administrativas» del IGN
  https://www.ign.es/wfs-inspire/unidades-administrativas
  Tipo de objeto au:AdministrativeUnit. Licencia: CC BY 4.0 ign.es (AccessConstraints del
  servicio). Código INE del municipio = últimos 5 dígitos de `nationalCode`
  (34 + CCAA + provincia + código INE de 5 dígitos; por ejemplo 34100303076 → 03076).

Descarga (una petición por provincia, con pausa; no se hace aquí para no repetirla sin querer):

  curl -G -o au_03.geojson https://www.ign.es/wfs-inspire/unidades-administrativas \\
    --data-urlencode service=WFS --data-urlencode version=2.0.0 \\
    --data-urlencode request=GetFeature --data-urlencode typeNames=au:AdministrativeUnit \\
    --data-urlencode count=1000 --data-urlencode outputFormat=application/geo+json \\
    --data-urlencode srsName=http://www.opengis.net/def/crs/EPSG/0/4326 \\
    --data-urlencode 'FILTER=<fes:Filter xmlns:fes="http://www.opengis.net/fes/2.0"
      xmlns:au="http://inspire.ec.europa.eu/schemas/au/4.0"><fes:PropertyIsLike wildCard="*"
      singleChar="." escapeChar="!"><fes:ValueReference>au:nationalCode</fes:ValueReference>
      <fes:Literal>341003*</fes:Literal></fes:PropertyIsLike></fes:Filter>'

Uso:
  uv run scripts/geo/preparar_municipios.py au_03.geojson au_12.geojson au_46.geojson \\
    --salida static/geo/municipios_cv.json --fecha-descarga 2026-11-06

La simplificación conserva la topología (los bordes compartidos se simplifican una sola vez),
así que no aparecen huecos entre municipios vecinos.
"""

import argparse
import json
from pathlib import Path

import topojson

ATRIBUCION = (
    "Límites municipales: obra derivada del servicio WFS «Unidades administrativas» del IGN, "
    "CC BY 4.0 ign.es"
)


def leer_municipios(rutas: list[Path]) -> list[dict]:
    features = []
    for ruta in rutas:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        for f in datos["features"]:
            p = f["properties"]
            if p["nationalLevelName"]["LocalisedCharacterString"] != "Municipio":
                continue
            codigo = p["nationalCode"][-5:]
            nombre = p["name"]["GeographicalName"]["spelling"]["SpellingOfName"]["text"]
            features.append(
                {
                    "type": "Feature",
                    "properties": {"codigo_ine": codigo, "nombre": nombre},
                    "geometry": f["geometry"],
                }
            )
    return features


def redondear(coords, decimales):
    if isinstance(coords[0], (int, float)):
        return [round(coords[0], decimales), round(coords[1], decimales)]
    return [redondear(c, decimales) for c in coords]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("ficheros", nargs="+", type=Path)
    parser.add_argument("--salida", type=Path, required=True)
    parser.add_argument("--fecha-descarga", required=True)
    parser.add_argument("--tolerancia", type=float, default=0.0003, help="grados (≈ 30 m)")
    parser.add_argument("--decimales", type=int, default=4)
    args = parser.parse_args()

    features = leer_municipios(args.ficheros)
    coleccion = {"type": "FeatureCollection", "features": features}
    topo = topojson.Topology(coleccion, prequantize=False, toposimplify=args.tolerancia)
    simplificado = json.loads(topo.to_geojson())
    for f in simplificado["features"]:
        f.pop("id", None)
        f["geometry"]["coordinates"] = redondear(f["geometry"]["coordinates"], args.decimales)
    simplificado["features"].sort(key=lambda f: f["properties"]["codigo_ine"])
    simplificado["metadatos"] = {
        "fuente": "https://www.ign.es/wfs-inspire/unidades-administrativas",
        "fecha_descarga": args.fecha_descarga,
        "atribucion": ATRIBUCION,
        "tolerancia_grados": args.tolerancia,
        "municipios": len(simplificado["features"]),
    }
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(
        json.dumps(simplificado, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    print(f"{len(simplificado['features'])} municipios · {args.salida.stat().st_size} bytes")


if __name__ == "__main__":
    main()
