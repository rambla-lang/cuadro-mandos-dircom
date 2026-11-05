"""Servicios comunes: auditoría (RF-04)."""

import json

from django.contrib.contenttypes.models import ContentType
from django.core.serializers.json import DjangoJSONEncoder
from django.forms.models import model_to_dict

from .models import RegistroAuditoria


def instantanea(obj) -> dict:
    """Campos de un modelo en un dict serializable a JSON (para `antes` y `despues`)."""
    datos = model_to_dict(obj)
    return json.loads(json.dumps(datos, cls=DjangoJSONEncoder, default=str))


def registrar_auditoria(usuario, accion: str, objeto=None, antes=None, despues=None):
    autenticado = usuario is not None and getattr(usuario, "is_authenticated", False)
    return RegistroAuditoria.objects.create(
        usuario=usuario if autenticado else None,
        usuario_email=usuario.email if autenticado else "",
        accion=accion,
        objeto_tipo=ContentType.objects.get_for_model(objeto) if objeto is not None else None,
        objeto_id=str(objeto.pk) if objeto is not None else "",
        objeto_repr=str(objeto)[:300] if objeto is not None else "",
        antes=antes,
        despues=despues,
    )
