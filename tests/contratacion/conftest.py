import re
from pathlib import Path

import pytest
from django.conf import settings

FIXTURES = Path(settings.BASE_DIR) / "tests" / "fixtures"
ATOM = FIXTURES / "placsp" / "perfiles_contratante_202610_extracto.atom"


@pytest.fixture
def reglas(db):
    from apps.contratacion.services import cargar_reglas

    cargar_reglas(Path(settings.BASE_DIR) / "seed" / "reglas_clasificacion.json")


@pytest.fixture
def base(municipios_cv, competidores, reglas):
    return None


def atom_con(*entradas_extra: str) -> str:
    """El ATOM real recortado con entradas adicionales derivadas de él."""
    texto = ATOM.read_text(encoding="utf-8")
    return texto.replace("</feed>", "\n".join(entradas_extra) + "\n</feed>")


def entrada(id_: str) -> str:
    texto = ATOM.read_text(encoding="utf-8")
    for e in re.findall(r"<entry>.*?</entry>", texto, re.S):
        if e.split("</id>")[0].endswith(id_):
            return e
    raise KeyError(id_)
