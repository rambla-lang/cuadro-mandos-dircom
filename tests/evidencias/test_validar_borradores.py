"""Comando validar_borradores: validación en bloque autorizada por una persona."""

import pytest
from django.core.management import CommandError, call_command

from apps.evidencias.enums import EstadoValidacion, NivelEvidencia, Origen
from apps.evidencias.importers.tabla_municipal import importar_tabla
from apps.evidencias.models import Evidencia
from apps.nucleo.models import ElementoRevision, RegistroAuditoria

from .test_tabla_municipal import CABECERA_RESIDUOS, FIXTURES, _libro, config_agua, config_residuos

Tipo = ElementoRevision.Tipo


@pytest.fixture
def borradores(municipios_cv, competidores, administrador, tmp_path):
    importar_tabla(FIXTURES / "agua_sintetico.csv", config_agua(estado="borrador"), administrador)
    ruta = _libro(
        tmp_path,
        [["IBI", "Urbaser", "", "Acta del pleno", 2021, "Confirmado (fuente oficial)"]],
        CABECERA_RESIDUOS,
    )
    importar_tabla(ruta, config_residuos(estado="borrador"), administrador)
    return administrador


def test_simular_no_cambia_nada(borradores):
    call_command("validar_borradores", "--usuario", borradores.email, "--simular")
    assert not Evidencia.objects.filter(estado_validacion=EstadoValidacion.VALIDADA).exists()
    assert ElementoRevision.objects.filter(
        tipo=Tipo.NIVEL_POR_DECIDIR, estado=ElementoRevision.Estado.PENDIENTE
    ).exists()


def test_valida_todo_y_fija_el_nivel_pendiente_como_parcial(borradores):
    call_command("validar_borradores", "--usuario", borradores.email)

    assert not Evidencia.objects.exclude(estado_validacion=EstadoValidacion.VALIDADA).exists()
    assert not Evidencia.objects.filter(validado_por__isnull=True).exists()
    el = ElementoRevision.objects.get(tipo=Tipo.NIVEL_POR_DECIDIR)
    assert el.estado == ElementoRevision.Estado.CORREGIDO
    assert el.resolucion["nivel"] == NivelEvidencia.PARCIAL
    ev = el.objeto
    assert ev.nivel == NivelEvidencia.PARCIAL  # nunca «oficial» sin URL: no se inventa
    assert ev.prestaciones.get().nivel == NivelEvidencia.PARCIAL
    assert RegistroAuditoria.objects.filter(accion="evidencia.validar").count() == 4
    assert RegistroAuditoria.objects.filter(accion="revision.nivel").count() == 1


def test_no_valida_propuestas_de_la_ia(borradores):
    ev = Evidencia.objects.first()
    Evidencia.objects.filter(pk=ev.pk).update(origen=Origen.IA)
    call_command("validar_borradores", "--usuario", borradores.email)
    ev.refresh_from_db()
    assert ev.estado_validacion == EstadoValidacion.BORRADOR


def test_usuario_inexistente(db):
    with pytest.raises(CommandError):
        call_command("validar_borradores", "--usuario", "nadie@example.com")
