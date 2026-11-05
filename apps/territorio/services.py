"""Resolución de nombres de municipio (CP-05) y variantes de los nombres del INE."""

import re

from apps.nucleo.texto import normalizar_texto

from .models import Municipio

# Artículos que el INE pospone tras una coma: "Eliana, l'", "Montesinos, Los".
_ARTICULO_POSPUESTO = re.compile(
    r"^(?P<base>.+),\s*(?P<art>l'|el|la|els|les|los|las|lo)$", re.IGNORECASE
)


def variantes_nombre_ine(nombre_ine: str) -> tuple[list[str], list[str]]:
    """Devuelve (variantes_completas, variantes_sin_articulo) de un nombre del INE.

    "Agost"                 -> (["Agost"], [])
    "Eliana, l'"            -> (["Eliana, l'", "l'Eliana"], ["Eliana"])
    "Elx/Elche"             -> (["Elx", "Elche"], [])
    "Orxa, l'/Lorcha"       -> (["Orxa, l'", "l'Orxa", "Lorcha"], ["Orxa"])

    Las formas sin artículo se devuelven aparte porque pueden coincidir con otro municipio
    y el importador decide si las añade.
    """
    completas: list[str] = []
    sin_articulo: list[str] = []
    partes = [p.strip() for p in nombre_ine.split("/") if p.strip()]
    for parte in partes:
        completas.append(parte)
        m = _ARTICULO_POSPUESTO.match(parte)
        if m:
            base, art = m["base"].strip(), m["art"]
            completas.append(f"{art}{base}" if art.endswith("'") else f"{art} {base}")
            sin_articulo.append(base)
    return _sin_duplicados(completas), _sin_duplicados(sin_articulo)


def _sin_duplicados(formas: list[str]) -> list[str]:
    vistas, salida = set(), []
    for f in formas:
        if f not in vistas:
            vistas.add(f)
            salida.append(f)
    return salida


def candidatos_municipio(texto: str, provincias: list[str] | None = None):
    """Municipios cuyo nombre oficial o alternativo coincide exactamente (normalizado)."""
    norm = normalizar_texto(texto)
    if not norm:
        return Municipio.objects.none()
    qs = Municipio.objects.filter(nombres_normalizados__contains=[norm])
    if provincias:
        qs = qs.filter(provincia__codigo_ine__in=provincias)
    return qs


def resolver_municipio(texto: str, provincias: list[str] | None = None) -> Municipio | None:
    """El municipio si la coincidencia es exacta y única; si no, None (va a revisión).

    No hay coincidencias parciales: "Agost" no casa con "Llagostera" ni "Tavernes" con
    "Tavernes Blanques" (docs/04 §1 y §9).
    """
    candidatos = list(candidatos_municipio(texto, provincias)[:2])
    return candidatos[0] if len(candidatos) == 1 else None
