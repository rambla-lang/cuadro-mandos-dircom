import pytest
from django.contrib.auth.models import Group

from apps.nucleo.roles import Rol


def test_grupos_creados_tras_migrate(db):
    assert set(Group.objects.values_list("name", flat=True)) >= {
        "Administrador",
        "Analista",
        "Lector",
    }


def test_permisos_por_rol(db):
    def codenames(rol):
        return set(Group.objects.get(name=rol).permissions.values_list("codename", flat=True))

    lector, analista, admin = (
        codenames(Rol.LECTOR),
        codenames(Rol.ANALISTA),
        codenames(Rol.ADMINISTRADOR),
    )
    assert {"view_municipio", "view_empresa", "view_evidencia"} <= lector
    assert not any(c.split("_")[0] in ("add", "change", "delete") for c in lector)
    assert "importar_datos" not in lector and "validar_evidencia" not in lector
    assert {"change_evidencia", "importar_datos", "validar_evidencia"} <= analista
    assert "delete_empresa" not in analista
    assert "view_usuario" not in analista and "view_registroauditoria" not in lector
    assert {"add_usuario", "delete_empresa"} <= admin


@pytest.mark.urls("tests.urls_prueba")
@pytest.mark.parametrize("url", ["/prueba/importar/", "/prueba/importar-clase/"])
def test_cp11_lector_post_importar_403(client, lector, url):
    """CP-11: usuario lector que hace POST a importar → 403."""
    client.force_login(lector)
    assert client.post(url).status_code == 403


@pytest.mark.urls("tests.urls_prueba")
@pytest.mark.parametrize("url", ["/prueba/importar/", "/prueba/importar-clase/"])
def test_analista_y_admin_pueden_importar(client, analista, administrador, url):
    for u in (analista, administrador):
        client.force_login(u)
        assert client.post(url).status_code == 200


@pytest.mark.urls("tests.urls_prueba")
def test_usuario_sin_rol_403_y_anonimo_a_login(client, crear_usuario):
    assert client.post("/prueba/importar/").status_code == 302
    client.force_login(crear_usuario("sinrol@example.com"))
    assert client.post("/prueba/importar/").status_code == 403


@pytest.mark.urls("tests.urls_prueba")
def test_superusuario_cuenta_como_administrador(client, db):
    from apps.nucleo.models import Usuario

    su = Usuario.objects.create_superuser("su@example.com", "una-contrasena-larga-123")
    client.force_login(su)
    assert client.post("/prueba/importar/").status_code == 200
    assert client.get("/usuarios/").status_code == 200


@pytest.mark.parametrize("fixture", ["lector", "analista"])
def test_cp11_solo_admin_invita(client, request, fixture):
    client.force_login(request.getfixturevalue(fixture))
    assert client.get("/usuarios/").status_code == 403
    r = client.post("/usuarios/invitar/", {"email": "x@example.com", "rol": "Lector"})
    assert r.status_code == 403


def test_menu_segun_rol(client, lector, administrador):
    client.force_login(lector)
    html = client.get("/").content.decode()
    assert "/municipios/" in html and "/usuarios/" not in html and "/admin/" not in html
    client.force_login(administrador)
    html = client.get("/").content.decode()
    assert "/usuarios/" in html and "/admin/" in html


def test_lector_no_entra_en_admin(client, lector):
    client.force_login(lector)
    r = client.get("/admin/")
    assert r.status_code == 302 and "/admin/login/" in r["Location"]
