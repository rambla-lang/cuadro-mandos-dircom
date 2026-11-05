from .roles import Rol, tiene_rol


def roles(request):
    usuario = getattr(request, "user", None)
    if usuario is None or not usuario.is_authenticated:
        return {}
    return {
        "es_administrador": tiene_rol(usuario, Rol.ADMINISTRADOR),
        "es_analista": tiene_rol(usuario, Rol.ADMINISTRADOR, Rol.ANALISTA),
    }
