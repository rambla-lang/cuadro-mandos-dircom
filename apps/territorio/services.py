"""Resolución de nombres de municipio (CP-05) y variantes de los nombres del INE."""

import difflib
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


def resolver_municipio_compuesto(
    texto: str, provincias: list[str] | None = None
) -> Municipio | None:
    """Como `resolver_municipio`, y además «Alcoy / Alcoi» o «JIJONA/XIXONA»: si el texto
    completo no casa, se resuelve cada parte separada por «/» y solo vale si todas dan el
    mismo municipio."""
    municipio = resolver_municipio(texto, provincias)
    if municipio or "/" not in texto:
        return municipio
    partes = [p.strip() for p in texto.split("/") if p.strip()]
    resueltos = [resolver_municipio(p, provincias) for p in partes]
    if all(resueltos) and len({m.pk for m in resueltos}) == 1:
        return resueltos[0]
    return None


def sugerencias_municipio(texto: str, limite: int = 8) -> list[Municipio]:
    """Candidatos para la bandeja: nombres que empiezan por el texto o lo contienen como
    palabras completas («TAVERNES» → Tavernes Blanques y Tavernes de la Valldigna). Solo
    orientan a quien revisa; nunca se asignan solos."""
    norm = normalizar_texto(texto)
    if not norm:
        return []
    partes = [normalizar_texto(p) for p in re.split(r"[/()¿?,-]", texto) if p.strip()]
    claves = {p for p in [norm, *partes] if len(p) >= 3}
    encontrados = []
    for m in Municipio.objects.select_related("provincia").order_by("nombre_oficial"):
        nombres = m.nombres_normalizados
        if any(
            n.startswith(c) or re.search(rf"\b{re.escape(c)}\b", n) or c.startswith(n + " ")
            for n in nombres
            for c in claves
        ):
            encontrados.append(m)
            if len(encontrados) >= limite:
                break
    if not encontrados:
        # Erratas o variantes («FORMENTERA DE SEGURA», «Torre Endomenech»): parecido de cadena.
        por_nombre = {}
        for m in Municipio.objects.order_by("nombre_oficial"):
            for n in m.nombres_normalizados:
                por_nombre.setdefault(n, m)
        for n in difflib.get_close_matches(norm, list(por_nombre), n=limite, cutoff=0.8):
            if por_nombre[n] not in encontrados:
                encontrados.append(por_nombre[n])
    return encontrados


def resolver_provincia(texto: str) -> str | None:
    """Código INE de la provincia nombrada en el texto, si es exactamente una
    («Castellón (según mi conocimiento geográfico)» → 12; «Valencia / Alicante» → None)."""
    from .models import Provincia

    norm = normalizar_texto(texto)
    if not norm:
        return None
    halladas = set()
    for p in Provincia.objects.all():
        for variante in p.nombre.split("/"):
            v = normalizar_texto(variante)
            if v and re.search(rf"\b{re.escape(v)}\b", norm):
                halladas.add(p.codigo_ine)
    return halladas.pop() if len(halladas) == 1 else None
