from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.auth.models import Group

from apps.nucleo.models import Usuario
from apps.nucleo.roles import Rol

SEED = Path(settings.BASE_DIR) / "seed"
CONTRASENA = "contrasena-de-prueba-larga"  # pragma: allowlist secret


@pytest.fixture
def crear_usuario(db):
    def _crear(email, rol=None, **extra):
        u = Usuario.objects.create_user(email=email, password=CONTRASENA, **extra)
        if rol:
            u.groups.add(Group.objects.get(name=rol))
        return u

    return _crear


@pytest.fixture
def administrador(crear_usuario):
    return crear_usuario("admin@example.com", Rol.ADMINISTRADOR, is_staff=True)


@pytest.fixture
def analista(crear_usuario):
    return crear_usuario("analista@example.com", Rol.ANALISTA)


@pytest.fixture
def lector(crear_usuario):
    return crear_usuario("lector@example.com", Rol.LECTOR)


@pytest.fixture
def municipios_cv(db):
    from apps.territorio.importers.ine import importar_municipios_ine

    return importar_municipios_ine(
        SEED / "ine" / "26codmun.xlsx", ["03", "12", "46"], "Comunitat Valenciana"
    )
