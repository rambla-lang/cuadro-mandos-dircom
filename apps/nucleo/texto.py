"""Normalización de textos para comparar nombres (municipios, alias de empresa)."""

import re
import unicodedata

_APOSTROFOS = str.maketrans({"’": "'", "‘": "'", "´": "'", "`": "'"})


def normalizar_texto(texto: str) -> str:
    """Forma comparable de un nombre: sin tildes, en minúsculas y con espacios simples.

    - Unifica los apóstrofos tipográficos y quita el espacio tras el apóstrofo ("l' Eliana").
    - Convierte la ele geminada valenciana ("l·l", "l.l") en "ll".
    - Trata los guiones como espacios.
    """
    if not texto:
        return ""
    t = texto.translate(_APOSTROFOS).lower()
    t = t.replace("l·l", "ll").replace("l.l", "ll")
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.replace("-", " ")
    t = re.sub(r"'\s+", "'", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()
