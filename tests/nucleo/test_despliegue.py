"""Fase 8: comprobación de salud, datos de partida y descarga de informes sin disco."""

import io

from django.core.management import call_command

from apps.entidades.models import Empresa
from apps.territorio.models import Municipio


def test_salud_sin_sesion(client, db):
    r = client.get("/salud/")
    assert r.status_code == 200 and r.json() == {"estado": "ok"}


def test_preparar_piloto_idempotente(db):
    call_command("preparar_piloto", stdout=io.StringIO())
    call_command("preparar_piloto", stdout=io.StringIO())
    assert Municipio.objects.count() == 542
    assert Empresa.objects.count() == 15


def test_informe_se_regenera_si_falta_el_archivo(
    empresas_gestoras, municipios_cv, administrador, client, settings, tmp_path
):
    from datetime import date

    from apps.informes import services

    settings.MEDIA_ROOT = tmp_path
    informe = services.crear(
        Empresa.objects.filter(nombre="FACSA"),
        date(2026, 1, 1),
        date(2026, 12, 31),
        administrador,
        False,
    )
    services.publicar(informe, administrador)
    informe.refresh_from_db()
    (tmp_path / informe.archivo_pptx).unlink()
    client.force_login(administrador)
    r = client.get(f"/informes/{informe.pk}/descargar.pptx")
    assert r.status_code == 200 and b"".join(r.streaming_content)[:2] == b"PK"
