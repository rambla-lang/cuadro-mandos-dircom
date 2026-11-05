import re
from datetime import timedelta
from unittest import mock

import pytest

from apps.nucleo.models import RegistroAuditoria, Usuario

NUEVA = "una-contrasena-nueva-segura"  # pragma: allowlist secret


def invitar(client, administrador, email="nuevo@example.com", rol="Analista"):
    client.force_login(administrador)
    r = client.post("/usuarios/invitar/", {"email": email, "nombre": "Nuevo", "rol": rol})
    assert r.status_code == 200
    enlace = re.search(r'class="enlace">([^<]+)<', r.content.decode()).group(1)
    client.logout()
    return enlace.replace("http://testserver", "")


def fijar(client, enlace, contrasena=NUEVA):
    r = client.get(enlace)  # redirige a la URL interna con «set-password»
    assert r.status_code == 302
    url = r["Location"]
    return url, client.post(url, {"new_password1": contrasena, "new_password2": contrasena})


def test_admin_invita_y_el_usuario_fija_su_contrasena(client, administrador):
    enlace = invitar(client, administrador, email="Nuevo@Example.com ")
    u = Usuario.objects.get(email="nuevo@example.com")
    assert not u.has_usable_password()
    assert list(u.groups.values_list("name", flat=True)) == ["Analista"]
    assert not u.is_staff

    _, r = fijar(client, enlace)
    assert r.status_code == 302 and r["Location"] == "/invitacion/completada/"
    u.refresh_from_db()
    assert u.check_password(NUEVA)
    assert (
        client.post("/acceso/", {"username": "nuevo@example.com", "password": NUEVA}).status_code
        == 302
    )
    acciones = set(RegistroAuditoria.objects.values_list("accion", flat=True))
    assert {"usuario.invitar", "usuario.fijar_contrasena"} <= acciones


def test_enlace_de_un_solo_uso(client, administrador):
    enlace = invitar(client, administrador)
    fijar(client, enlace)
    client.cookies.clear()
    r = client.get(enlace)
    assert r.status_code == 200 and "Enlace no válido" in r.content.decode()


def test_enlace_caduca_a_las_72_horas(client, administrador):
    enlace = invitar(client, administrador)
    from apps.nucleo.acceso import token_invitacion

    futuro = token_invitacion._now() + timedelta(hours=72, minutes=1)
    with mock.patch.object(type(token_invitacion), "_now", return_value=futuro):
        r = client.get(enlace)
    assert r.status_code == 200 and "Enlace no válido" in r.content.decode()


def test_token_de_invitacion_no_sirve_como_token_de_django(client, administrador):
    """Salt propio: un token de invitación no vale en el generador por defecto."""
    from django.contrib.auth.tokens import default_token_generator

    enlace = invitar(client, administrador)
    token = enlace.rstrip("/").split("/")[-1]
    u = Usuario.objects.get(email="nuevo@example.com")
    assert not default_token_generator.check_token(u, token)


def test_invitar_administrador_le_da_acceso_al_panel(client, administrador):
    invitar(client, administrador, email="otro.admin@example.com", rol="Administrador")
    assert Usuario.objects.get(email="otro.admin@example.com").is_staff


def test_email_duplicado(client, administrador, lector):
    client.force_login(administrador)
    r = client.post("/usuarios/invitar/", {"email": "LECTOR@example.com", "rol": "Lector"})
    assert "Ya existe un usuario" in r.content.decode()


def test_contrasena_corta_rechazada(client, administrador):
    enlace = invitar(client, administrador)
    _, r = fijar(client, enlace, "corta")
    assert r.status_code == 200
    assert not Usuario.objects.get(email="nuevo@example.com").has_usable_password()


def test_generar_nuevo_enlace(client, administrador, lector):
    client.force_login(administrador)
    r = client.post(f"/usuarios/{lector.pk}/enlace/")
    assert r.status_code == 200 and "/invitacion/" in r.content.decode()
    assert RegistroAuditoria.objects.filter(accion="usuario.generar_enlace").exists()
    assert client.get(f"/usuarios/{lector.pk}/enlace/").status_code == 405


@pytest.mark.parametrize("url", ["/invitacion/completada/"])
def test_paginas_de_invitacion_publicas(client, db, url):
    assert client.get(url).status_code == 200
