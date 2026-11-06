"""Bandeja de revisión (RF-60) para lo que deja el importador de tablas."""

import pytest
from django.core.exceptions import ValidationError

from apps.entidades.models import AliasEmpresa, Empresa
from apps.evidencias import services_revision as srv
from apps.evidencias.enums import EstadoValidacion, NivelEvidencia
from apps.evidencias.importers.tabla_municipal import importar_tabla
from apps.evidencias.models import Evidencia, PrestacionServicio
from apps.nucleo.models import ElementoRevision, RegistroAuditoria
from apps.territorio.models import Municipio

from .test_tabla_municipal import CABECERA_RESIDUOS, FIXTURES, _libro, config_agua, config_residuos

Tipo = ElementoRevision.Tipo


@pytest.fixture
def importado(municipios_cv, competidores, administrador):
    importar_tabla(FIXTURES / "agua_sintetico.csv", config_agua(), administrador)
    return administrador


def test_resolver_municipio_importa_la_fila_y_aprende_el_nombre(importado):
    el = ElementoRevision.objects.get(texto="TAVERNES")
    valldigna = Municipio.objects.get(nombre_oficial="Tavernes de la Valldigna")
    srv.resolver_municipio(el, valldigna, importado, guardar_nombre=True)

    el.refresh_from_db()
    assert el.estado == ElementoRevision.Estado.CORREGIDO and el.resuelto_por == importado
    p = PrestacionServicio.objects.get(municipio=valldigna)
    assert p.empresa.nombre == "Veolia"
    valldigna.refresh_from_db()
    assert "tavernes" in valldigna.nombres_normalizados
    assert RegistroAuditoria.objects.filter(accion="revision.municipio").exists()

    # La siguiente importación ya lo resuelve sola y no duplica.
    res = importar_tabla(FIXTURES / "agua_sintetico.csv", config_agua(), importado)
    assert res.evidencias_nuevas == 0 and res.ya_en_revision == 1  # queda EL BOSQUE-CHIVA


def test_rechazar_municipio_descarta_la_fila_en_reimportaciones(importado):
    el = ElementoRevision.objects.get(texto="EL BOSQUE-CHIVA")
    srv.rechazar(el, importado, "No es un municipio: urbanización de Chiva.")
    res = importar_tabla(FIXTURES / "agua_sintetico.csv", config_agua(), importado)
    assert res.descartadas_en_revision == 1
    with pytest.raises(ValidationError):
        srv.rechazar(el, importado, "otra vez")


def test_resolver_operador_con_alias_y_varias_empresas(importado, tmp_path):
    el = ElementoRevision.objects.get(tipo=Tipo.OPERADOR_NO_RESUELTO)
    otra = Empresa.objects.create(nombre="Operadora Inventada")
    srv.resolver_operador(el, [otra], importado, guardar_alias=True)
    p = PrestacionServicio.objects.get(municipio__nombre_oficial__startswith="Xixona")
    assert p.empresa == otra
    assert p.evidencias.get().empresas.get() == otra
    assert AliasEmpresa.objects.filter(empresa=otra, texto="OPERADORA INVENTADA SL").exists()

    ruta = _libro(
        tmp_path,
        [["ELDA", "UTE Urbaser + FCC Medio Ambiente", "", "Prensa", 2020, "Parcial"]],
        CABECERA_RESIDUOS,
    )
    importar_tabla(ruta, config_residuos(), importado)
    ute = ElementoRevision.objects.get(texto__startswith="UTE")
    urbaser, fcc = Empresa.objects.get(nombre="Urbaser"), Empresa.objects.get(nombre="FCC")
    srv.resolver_operador(ute, [urbaser, fcc], importado)
    elda = PrestacionServicio.objects.filter(municipio__nombre_oficial="Elda")
    assert {p.empresa.nombre for p in elda} == {"Urbaser", "FCC"}
    assert all(p.operador_texto == "UTE Urbaser + FCC Medio Ambiente" for p in elda)
    assert not elda.filter(empresa__isnull=True).exists()


def test_decidir_nivel_oficial_exige_url_y_valida(
    municipios_cv, competidores, administrador, tmp_path
):
    ruta = _libro(
        tmp_path,
        [["IBI", "Urbaser", "", "Acta del pleno", 2021, "Confirmado (fuente oficial)"]],
        CABECERA_RESIDUOS,
    )
    importar_tabla(ruta, config_residuos(), administrador)
    el = ElementoRevision.objects.get(tipo=Tipo.NIVEL_POR_DECIDIR)
    with pytest.raises(ValidationError):
        srv.decidir_nivel(el, NivelEvidencia.OFICIAL, administrador)

    # Antes de decidir el nivel, la validación en bloque la salta.
    assert srv.validar_evidencias(Evidencia.objects.all(), administrador) == 0

    ev = srv.decidir_nivel(
        el, NivelEvidencia.OFICIAL, administrador, url_origen="https://ejemplo.es/acta.pdf"
    )
    assert ev.nivel == NivelEvidencia.OFICIAL
    assert ev.estado_validacion == EstadoValidacion.VALIDADA  # la importación era «validada»
    assert ev.tratamiento_limites == ""
    assert ev.prestaciones.get().nivel == NivelEvidencia.OFICIAL
    assert RegistroAuditoria.objects.filter(accion="revision.nivel").exists()


def test_rechazar_nivel_deja_la_evidencia_fuera(
    municipios_cv, competidores, administrador, tmp_path
):
    ruta = _libro(
        tmp_path,
        [["IBI", "Urbaser", "", "Acta", 2021, "Confirmado (fuente oficial)"]],
        CABECERA_RESIDUOS,
    )
    importar_tabla(ruta, config_residuos(), administrador)
    el = ElementoRevision.objects.get(tipo=Tipo.NIVEL_POR_DECIDIR)
    srv.rechazar(el, administrador, "Fuente no localizada")
    assert Evidencia.objects.get().estado_validacion == EstadoValidacion.RECHAZADA


def test_validar_borradores(municipios_cv, competidores, administrador):
    importar_tabla(FIXTURES / "agua_sintetico.csv", config_agua(estado="borrador"), administrador)
    assert srv.validar_evidencias(Evidencia.objects.all(), administrador) == 3
    assert not Evidencia.objects.exclude(estado_validacion=EstadoValidacion.VALIDADA).exists()
