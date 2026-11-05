import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

pytestmark = pytest.mark.django_db

CLAVE = "una-clave-de-prueba-larga"


def test_anonimo_es_redirigido_al_login(client):
    """RF-01: un usuario sin sesión que entra en una página de la aplicación va al login."""
    respuesta = client.get(reverse("portada"))
    assert respuesta.status_code == 302
    assert respuesta.url == f"{reverse('login')}?next=/"


def test_anonimo_no_entra_en_el_panel_de_administracion(client):
    respuesta = client.get("/admin/")
    assert respuesta.status_code == 302
    assert "login" in respuesta.url


def test_url_inexistente_da_404_sin_contenido_de_la_aplicacion(client):
    """LoginRequiredMiddleware solo actúa sobre vistas que existen; una ruta desconocida es 404."""
    assert client.get("/cualquier/ruta/inexistente/").status_code == 404


def test_la_pagina_de_login_es_publica(client):
    respuesta = client.get(reverse("login"))
    assert respuesta.status_code == 200
    assert "Email" in respuesta.content.decode()


def test_login_con_email_lleva_a_la_portada(client):
    get_user_model().objects.create_user(email="ana@example.com", password=CLAVE)
    respuesta = client.post(
        reverse("login"), {"username": "Ana@Example.com", "password": CLAVE}, follow=True
    )
    assert respuesta.status_code == 200
    assert respuesta.context["user"].is_authenticated
    assert respuesta.redirect_chain[-1][0] == reverse("portada")


def test_login_con_clave_incorrecta_no_entra(client):
    get_user_model().objects.create_user(email="ana@example.com", password=CLAVE)
    respuesta = client.post(reverse("login"), {"username": "ana@example.com", "password": "mala"})
    assert respuesta.status_code == 200
    assert not respuesta.context["user"].is_authenticated


@pytest.mark.parametrize("url", ["/registro/", "/accounts/signup/"])
def test_no_hay_registro_publico(client, url):
    """RF-01/RF-03: no existe ninguna ruta de alta pública de usuarios."""
    assert client.get(url).status_code == 404
