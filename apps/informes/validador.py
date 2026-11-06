"""Validador de los textos de un informe (docs/05 §4, paso 4). CP-09 y CP-10.

- Cada `[E-xxxxxx]` debe ser una evidencia aportada al informe (si no, se rechaza).
- Cada `[Mn]` debe ser una métrica calculada.
- Cada número del texto debe aparecer en las métricas o en las evidencias aportadas (también
  sus fechas); si no, la sección se marca para revisión.
- Ningún párrafo sin al menos una referencia a una evidencia o a una métrica.
"""

import re

REF_E = re.compile(r"\[(E-\d{6})\]")
REF_M = re.compile(r"\[(M\d+)\]")
NUMERO = re.compile(r"(?<![\w-])\d{1,3}(?:\.\d{3})+(?:,\d+)?|(?<![\w-])\d+(?:[.,]\d+)?")


def _normalizar(n: str) -> str:
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", n):
        n = n.replace(".", "")
    n = n.replace(",", ".")
    try:
        f = float(n)
    except ValueError:
        return n
    return str(int(f)) if f.is_integer() else f"{f:.1f}"


def numeros_permitidos(datos: dict) -> set[str]:
    permitidos = set()
    textos = [datos.get("desde", ""), datos.get("hasta", "")]
    for m in datos.get("metricas", []):
        permitidos.add(_normalizar(str(m["valor"])))
    for c in datos.get("competidores", []):
        for e in c["evidencias"]:
            textos += [e["titulo"], e["extracto"], e["fecha"], e["limites"]]
    for t in textos:
        for n in NUMERO.findall(t or ""):
            permitidos.add(_normalizar(n))
        for parte in re.findall(r"\d+", t or ""):
            permitidos.add(str(int(parte)))
    return permitidos


def validar_texto(texto: str, datos: dict, permitidos: set[str] | None = None) -> list[str]:
    permitidos = permitidos if permitidos is not None else numeros_permitidos(datos)
    codigos = {e["codigo"] for c in datos.get("competidores", []) for e in c["evidencias"]}
    metricas = {m["id"] for m in datos.get("metricas", [])}
    problemas = []
    parrafos = [p for p in re.split(r"\n\s*\n|\n", texto) if p.strip()]
    for i, p in enumerate(parrafos, start=1):
        refs_e, refs_m = REF_E.findall(p), REF_M.findall(p)
        for c in refs_e:
            if c not in codigos:
                problemas.append(
                    f"Párrafo {i}: cita [{c}], que no es una evidencia aportada al informe."
                )
        for m in refs_m:
            if m not in metricas:
                problemas.append(f"Párrafo {i}: cita [{m}], que no es una métrica calculada.")
        if not refs_e and not refs_m:
            problemas.append(f"Párrafo {i}: no cita ninguna evidencia ni métrica.")
        limpio = REF_M.sub(" ", REF_E.sub(" ", p))
        for n in NUMERO.findall(limpio):
            if _normalizar(n) not in permitidos:
                problemas.append(
                    f"Párrafo {i}: la cifra «{n}» no está en las métricas ni en las evidencias."
                )
    return problemas
