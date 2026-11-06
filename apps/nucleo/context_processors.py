from .roles import Rol, tiene_rol


def roles(request):
    usuario = getattr(request, "user", None)
    if usuario is None or not usuario.is_authenticated:
        return {}
    es_analista = tiene_rol(usuario, Rol.ADMINISTRADOR, Rol.ANALISTA)
    contexto = {
        "es_administrador": tiene_rol(usuario, Rol.ADMINISTRADOR),
        "es_analista": es_analista,
    }
    if es_analista:
        from .models import ElementoRevision

        contexto["pendientes_revision"] = ElementoRevision.objects.filter(
            estado=ElementoRevision.Estado.PENDIENTE
        ).count()
    return contexto
