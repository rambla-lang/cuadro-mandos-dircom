"""Normalización de URL, atribución por alias y vínculo territorial (docs/04 §4)."""

import functools
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.conf import settings

from apps.entidades.models import AliasEmpresa
from apps.nucleo.texto import normalizar_texto
from apps.territorio.models import Municipio

PARAMETROS_SEGUIMIENTO = re.compile(
    r"^(utm_.*|fbclid|gclid|dclid|mc_cid|mc_eid|igshid|_ga|ref|ref_src|cmpid|ocid|ito|s)$", re.I
)


def url_canonica(url: str) -> str:
    """Dominio en minúsculas, sin `www.`, sin parámetros de seguimiento, sin fragmento y sin
    barra final (docs/04 §4)."""
    url = (url or "").strip()
    if not url:
        return ""
    partes = urlsplit(url)
    if not partes.scheme or not partes.netloc:
        return url
    dominio = partes.netloc.lower()
    if dominio.startswith("www."):
        dominio = dominio[4:]
    consulta = urlencode(
        [
            (k, v)
            for k, v in parse_qsl(partes.query, keep_blank_values=True)
            if not PARAMETROS_SEGUIMIENTO.match(k)
        ]
    )
    ruta = partes.path.rstrip("/") or ""
    return urlunsplit(
        (
            "https" if partes.scheme in ("http", "https") else partes.scheme,
            dominio,
            ruta,
            consulta,
            "",
        )
    )


def dominio_de(url: str) -> str:
    netloc = urlsplit(url or "").netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


# --- Atribución por alias ------------------------------------------------------------------


@dataclass
class Coincidencia:
    empresa_id: int
    alias: str
    requiere_contexto: bool


def cargar_alias() -> list[tuple[re.Pattern, AliasEmpresa]]:
    salida = []
    for a in AliasEmpresa.objects.filter(empresa__activa=True).select_related("empresa"):
        if a.texto_normalizado:
            salida.append((re.compile(rf"(?<![\w']){re.escape(a.texto_normalizado)}(?![\w'])"), a))
    return salida


def atribuir(texto: str, alias: list) -> dict[int, Coincidencia]:
    """Empresas nombradas en el texto por alguno de sus alias, con límite de palabra. Si una
    empresa casa por un alias inequívoco, no se marca como dudosa aunque también case por uno
    que requiere contexto."""
    norm = normalizar_texto(texto)
    encontradas: dict[int, Coincidencia] = {}
    for patron, a in alias:
        if patron.search(norm):
            previa = encontradas.get(a.empresa_id)
            if previa is None or (previa.requiere_contexto and not a.requiere_contexto):
                encontradas[a.empresa_id] = Coincidencia(a.empresa_id, a.texto, a.requiere_contexto)
    return encontradas


# --- Vínculo territorial -------------------------------------------------------------------

# Nombres de municipio valencianos que también son palabras o nombres corrientes y no bastan
# para afirmar el vínculo (propuesta del equipo; se amplía si aparecen falsos positivos).
NOMBRES_AMBIGUOS = {
    "anna",
    "barracas",
    "calles",
    "canals",
    "casinos",
    "dolores",
    "el toro",
    "emperador",
    "higueras",
    "la mata",
    "la romana",
    "manuel",
    "marines",
    "miramar",
    "montserrat",
    "navajas",
    "oliva",
    "otos",
    "palmera",
    "palomar",
    "piles",
    "planes",
    "real",
    "salem",
    "salinas",
    "sella",
    "serra",
    "silla",
    "tales",
    "teresa",
    "toga",
    "tous",
}
# «cuenca» (hidrográfica) y «león» (nombre propio) no sirven para descartar el vínculo.
PROVINCIAS_AMBIGUAS = {"cuenca", "leon"}
TERMINOS_CV_GENERALES = [
    "comunitat valenciana",
    "comunidad valenciana",
    "generalitat valenciana",
    "pais valencia",
    "alicante",
    "alacant",
    "castellon",
    "castello",
    "valencia",
]


@functools.cache
def _patron_cv() -> re.Pattern:
    nombres = set(TERMINOS_CV_GENERALES)
    for m in Municipio.objects.filter(provincia__codigo_ine__in=["03", "12", "46"]):
        for n in m.nombres_normalizados:
            if len(n) >= 4 and n not in NOMBRES_AMBIGUOS:
                nombres.add(n)
    alternativas = "|".join(re.escape(n) for n in sorted(nombres, key=len, reverse=True))
    return re.compile(rf"(?<![\w'])({alternativas})(?![\w'])")


@functools.cache
def _patron_otras_provincias() -> re.Pattern:
    """Provincias de fuera de la CV, con los nombres del fichero del INE (docs/04 §10)."""
    import openpyxl

    libro = openpyxl.load_workbook(
        Path(settings.BASE_DIR) / "seed" / "ine" / "26codmun.xlsx", read_only=True
    )
    nombres = set()
    try:
        for hoja in libro.worksheets:
            if hoja.title in ("03", "12", "46"):
                continue
            fila = next(hoja.iter_rows(min_row=2, max_row=2, values_only=True))
            for parte in str(fila[0]).split("/"):
                n = normalizar_texto(parte.replace("Ciudad Autónoma de ", ""))
                if len(n) >= 4 and n not in PROVINCIAS_AMBIGUAS:
                    nombres.add(n)
    finally:
        libro.close()
    alternativas = "|".join(re.escape(n) for n in sorted(nombres, key=len, reverse=True))
    return re.compile(rf"(?<![\w'])({alternativas})(?![\w'])")


def limpiar_caches():
    _patron_cv.cache_clear()


# Nombres propios que contienen un topónimo valenciano sin implicar vínculo territorial.
FRASES_NO_TERRITORIALES = ["aguas de valencia", "valencia cf", "valencia basket"]


def vinculo_territorial(texto: str) -> tuple[str, str]:
    """(si|no|dudoso, motivo). «si»: nombra un municipio (salvo los ambiguos), una provincia o
    la comunidad valenciana; «no»: no nombra nada valenciano y sí otra provincia; «dudoso»: lo
    demás. El motivo cita el término encontrado."""
    norm = normalizar_texto(texto)
    for frase in FRASES_NO_TERRITORIALES:
        norm = norm.replace(frase, " ")
    m = _patron_cv().search(norm)
    if m:
        return "si", f"Menciona «{m.group(1)}»"
    otra = _patron_otras_provincias().search(norm)
    if otra:
        return "no", f"Menciona «{otra.group(1)}» y ningún lugar valenciano"
    return "dudoso", "No nombra ningún lugar reconocible"
