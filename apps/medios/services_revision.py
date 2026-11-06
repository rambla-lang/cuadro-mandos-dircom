"""Bandeja y acciones manuales sobre menciones (RF-60). Todo queda auditado."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.evidencias.enums import EstadoValidacion, VinculoTerritorial
from apps.evidencias.services_revision import _cerrar, _exigir_pendiente
from apps.nucleo.models import ElementoRevision
from apps.nucleo.services import registrar_auditoria

from .models import Mencion, MencionEmpresa

Tipo = ElementoRevision.Tipo
Estado = ElementoRevision.Estado


@transaction.atomic
def confirmar_atribucion(elemento, usuario, comentario=""):
    _exigir_pendiente(elemento, Tipo.ATRIBUCION_MENCION)
    me: MencionEmpresa = elemento.objeto
    if me is None:
        raise ValidationError("La atribución ya no existe.")
    me.estado_validacion = EstadoValidacion.VALIDADA
    me.validado_por = usuario
    me.validado_en = timezone.now()
    me.save()
    _cerrar(elemento, usuario, Estado.ACEPTADO, {"empresa": me.empresa_id}, comentario)
    registrar_auditoria(usuario, "revision.atribucion", me, despues={"validada": True})


def rechazar_atribucion(elemento, usuario):
    me = elemento.objeto
    if me is not None:
        me.estado_validacion = EstadoValidacion.RECHAZADA
        me.validado_por = usuario
        me.validado_en = timezone.now()
        me.save()


@transaction.atomic
def fijar_vinculo(mencion: Mencion, vinculo: str, usuario, motivo: str = "", elemento=None):
    if vinculo not in VinculoTerritorial.values:
        raise ValidationError("Vínculo no válido.")
    antes = {"vinculo": mencion.vinculo_territorial, "motivo": mencion.motivo_vinculo}
    mencion.vinculo_territorial = vinculo
    mencion.motivo_vinculo = (motivo or f"Revisado por {usuario.email}")[:300]
    mencion.save()
    if elemento is not None:
        _exigir_pendiente(elemento, Tipo.VINCULO_TERRITORIAL)
        _cerrar(elemento, usuario, Estado.CORREGIDO, {"vinculo": vinculo}, motivo)
    else:
        ElementoRevision.objects.filter(
            clave=f"vinculo:{mencion.pk}", estado=Estado.PENDIENTE
        ).update(estado=Estado.CORREGIDO, resuelto_por=usuario, resuelto_en=timezone.now())
    registrar_auditoria(
        usuario, "mencion.vinculo", mencion, antes=antes, despues={"vinculo": vinculo}
    )


@transaction.atomic
def atribuir_manual(mencion: Mencion, empresa, usuario) -> MencionEmpresa:
    me, _ = MencionEmpresa.objects.update_or_create(
        mencion=mencion,
        empresa=empresa,
        defaults={
            "metodo": MencionEmpresa.Metodo.MANUAL,
            "estado_validacion": EstadoValidacion.VALIDADA,
            "validado_por": usuario,
            "validado_en": timezone.now(),
            "fragmento_detectado": "Atribución manual",
        },
    )
    registrar_auditoria(usuario, "mencion.atribuir", mencion, despues={"empresa": empresa.nombre})
    return me


@transaction.atomic
def quitar_atribucion(me: MencionEmpresa, usuario):
    me.estado_validacion = EstadoValidacion.RECHAZADA
    me.validado_por = usuario
    me.validado_en = timezone.now()
    me.save()
    registrar_auditoria(
        usuario, "mencion.quitar_atribucion", me.mencion, despues={"empresa": me.empresa.nombre}
    )
