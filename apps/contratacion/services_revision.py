"""Bandeja de revisión para contratación: vínculo órgano-municipio, clasificación de servicio y
adjudicatario. Cada resolución queda auditada (RF-04)."""

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.entidades.models import AliasEmpresa, Empresa
from apps.evidencias.enums import ALCANCES_POR_SERVICIO, Servicio
from apps.evidencias.services_revision import _cerrar, _exigir_pendiente
from apps.nucleo.models import ElementoRevision
from apps.nucleo.services import registrar_auditoria
from apps.territorio.models import Municipio

from .models import Adjudicacion, Expediente, OrganoContratacion
from .services import sin_forma_juridica

Tipo = ElementoRevision.Tipo
Estado = ElementoRevision.Estado


@transaction.atomic
def vincular(elemento: ElementoRevision, municipio: Municipio, usuario, comentario="") -> None:
    _exigir_pendiente(elemento, Tipo.VINCULO_ORGANO)
    organo = elemento.objeto
    if organo is None:
        raise ValidationError("El órgano ya no existe.")
    organo.municipio = municipio
    organo.estado_vinculacion = OrganoContratacion.Vinculacion.VALIDADA
    organo.save()
    _cerrar(elemento, usuario, Estado.CORREGIDO, {"municipio": municipio.codigo_ine}, comentario)
    registrar_auditoria(
        usuario, "revision.organo", organo, despues={"municipio": municipio.codigo_ine}
    )


@transaction.atomic
def clasificar(elemento: ElementoRevision, valor: str, usuario, comentario="") -> None:
    """`valor` = «servicio|alcance», o vacío si el contrato no es de agua, residuos ni energía."""
    _exigir_pendiente(elemento, Tipo.CLASIFICACION_SERVICIO)
    exp: Expediente = elemento.objeto
    if exp is None:
        raise ValidationError("El expediente ya no existe.")
    servicio, _, alcance = (valor or "").partition("|")
    if servicio and (
        servicio not in Servicio.values
        or (alcance and alcance not in ALCANCES_POR_SERVICIO[Servicio(servicio)])
    ):
        raise ValidationError("Servicio o alcance no válido.")
    exp.servicio_clasificado = servicio
    exp.alcance_clasificado = alcance if servicio else ""
    exp.metodo_clasificacion = Expediente.Clasificacion.MANUAL
    exp.regla_clasificacion = f"Revisión de {usuario.email}"
    exp.save()
    _cerrar(
        elemento, usuario, Estado.CORREGIDO, {"servicio": servicio, "alcance": alcance}, comentario
    )
    registrar_auditoria(
        usuario, "revision.clasificacion", exp, despues={"servicio": servicio, "alcance": alcance}
    )


@transaction.atomic
def resolver_adjudicatario(
    elemento: ElementoRevision,
    empresa: Empresa,
    usuario,
    guardar_alias=False,
    guardar_nif=False,
    comentario="",
) -> None:
    _exigir_pendiente(elemento, Tipo.ADJUDICATARIO_NO_RESUELTO)
    adj: Adjudicacion = elemento.objeto
    if adj is None:
        raise ValidationError("La adjudicación ya no existe (el expediente se ha actualizado).")
    adj.empresa = empresa
    adj.save()
    if guardar_alias:
        texto = sin_forma_juridica(adj.adjudicatario_texto)
        AliasEmpresa.objects.get_or_create(
            empresa=empresa,
            texto_normalizado=texto,
            defaults={"texto": texto[:200], "tipo": AliasEmpresa.Tipo.RAZON_SOCIAL},
        )
    if guardar_nif and adj.adjudicatario_nif and "*" not in adj.adjudicatario_nif:
        if empresa.nif and empresa.nif != adj.adjudicatario_nif.upper():
            raise ValidationError(f"{empresa} ya tiene otro NIF ({empresa.nif}).")
        if not empresa.nif:
            empresa.nif = adj.adjudicatario_nif
            empresa.save()
    _cerrar(elemento, usuario, Estado.CORREGIDO, {"empresa": empresa.pk}, comentario)
    registrar_auditoria(
        usuario,
        "revision.adjudicatario",
        adj,
        despues={"empresa": empresa.nombre, "alias": guardar_alias, "nif": guardar_nif},
    )


def aplicar_resolucion_a_otras_adjudicaciones(empresa: Empresa) -> int:
    """Tras guardar un alias o un NIF, resuelve las adjudicaciones pendientes que ahora casan."""
    from .services import resolver_adjudicatario as resolver

    n = 0
    pendientes = ElementoRevision.objects.filter(
        tipo=Tipo.ADJUDICATARIO_NO_RESUELTO, estado=Estado.PENDIENTE
    )
    for el in pendientes:
        adj = el.objeto
        if adj is None or adj.empresa_id:
            continue
        if resolver(adj.adjudicatario_texto, adj.adjudicatario_nif) == empresa:
            adj.empresa = empresa
            adj.save()
            _cerrar(el, None, Estado.ACEPTADO, {"empresa": empresa.pk, "automatico": True})
            n += 1
    return n
