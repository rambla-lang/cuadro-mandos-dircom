import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

pytestmark = pytest.mark.django_db

CLAVE = "una-clave-de-prueba-larga"


def test_modelo_de_usuario_es_el_propio():
    assert get_user_model()._meta.label == "nucleo.Usuario"
    assert get_user_model().USERNAME_FIELD == "email"


def test_crear_usuario_con_email():
    u = get_user_model().objects.create_user(email="ana@example.com", password=CLAVE)
    assert u.email == "ana@example.com"
    assert u.check_password(CLAVE)
    assert not u.is_staff and not u.is_superuser and u.is_active


def test_email_se_normaliza_a_minusculas():
    u = get_user_model().objects.create_user(email="  Ana@Example.COM ", password=CLAVE)
    assert u.email == "ana@example.com"


def test_email_obligatorio():
    with pytest.raises(ValueError):
        get_user_model().objects.create_user(email="", password=CLAVE)


def test_email_unico_sin_distinguir_mayusculas():
    get_user_model().objects.create_user(email="ana@example.com", password=CLAVE)
    with pytest.raises(IntegrityError):
        get_user_model().objects.create_user(email="ANA@example.com", password=CLAVE)


def test_crear_superusuario():
    u = get_user_model().objects.create_superuser(email="admin@example.com", password=CLAVE)
    assert u.is_staff and u.is_superuser
