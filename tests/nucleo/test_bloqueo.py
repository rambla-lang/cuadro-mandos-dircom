"""ADR-009: bloqueo temporal tras intentos fallidos."""

from tests.conftest import CONTRASENA


def intentar(client, email, password):
    return client.post("/acceso/", {"username": email, "password": password})


def test_bloqueo_tras_5_fallos(client, analista):
    for _ in range(4):
        assert intentar(client, analista.email, "mala").status_code == 200
    r = intentar(client, analista.email, "mala")
    assert r.status_code == 429
    # Bloqueado aunque ahora la contraseña sea correcta, también en mayúsculas.
    r = intentar(client, analista.email.upper(), CONTRASENA)
    assert r.status_code == 429 and "bloqueado" in r.content.decode().lower()


def test_el_bloqueo_no_afecta_a_otros_usuarios(client, analista, lector):
    for _ in range(5):
        intentar(client, analista.email, "mala")
    assert intentar(client, lector.email, CONTRASENA).status_code == 302


def test_exito_reinicia_el_contador(client, analista):
    for _ in range(4):
        intentar(client, analista.email, "mala")
    assert intentar(client, analista.email, CONTRASENA).status_code == 302
    client.logout()
    for _ in range(4):
        assert intentar(client, analista.email, "mala").status_code == 200
