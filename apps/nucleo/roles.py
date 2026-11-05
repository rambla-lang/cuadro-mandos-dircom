"""Roles de la aplicación (docs/08) y comprobación en el servidor (RF-02)."""

from enum import StrEnum
from functools import wraps

from django.core.exceptions import PermissionDenied


class Rol(StrEnum):
    ADMINISTRADOR = "Administrador"
    ANALISTA = "Analista"
    LECTOR = "Lector"


def tiene_rol(usuario, *roles: Rol) -> bool:
    """El superusuario cuenta como administrador."""
    if not usuario.is_authenticated or not usuario.is_active:
        return False
    if usuario.is_superuser:
        return True
    nombres = {str(r) for r in roles}
    return usuario.groups.filter(name__in=nombres).exists()


def rol_requerido(*roles: Rol):
    """Decorador de vista: 403 si el usuario no tiene ninguno de los roles indicados."""

    def decorador(vista):
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            if not tiene_rol(request.user, *roles):
                raise PermissionDenied
            return vista(request, *args, **kwargs)

        return envoltura

    return decorador


class RolRequeridoMixin:
    """Mixin para vistas basadas en clase. Defina `roles_requeridos`."""

    roles_requeridos: tuple[Rol, ...] = ()

    def dispatch(self, request, *args, **kwargs):
        if not tiene_rol(request.user, *self.roles_requeridos):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


# Permisos por rol. Administrador: todos. Lector: solo "view".
APPS_DE_DATOS = ("territorio", "entidades", "evidencias", "nucleo")
MODELOS_SOLO_ADMIN = {("nucleo", "usuario"), ("nucleo", "registroauditoria")}
PERMISOS_EXTRA_ANALISTA = {
    ("nucleo", "importar_datos"),
    ("evidencias", "validar_evidencia"),
}


def sincronizar_roles(**kwargs):
    """Crea los grupos y les asigna permisos. Idempotente; se ejecuta tras cada migrate."""
    from django.contrib.auth.models import Group, Permission

    perms = Permission.objects.select_related("content_type")
    admin, _ = Group.objects.get_or_create(name=Rol.ADMINISTRADOR)
    admin.permissions.set(perms)

    de_datos = [
        p
        for p in perms.filter(content_type__app_label__in=APPS_DE_DATOS)
        if (p.content_type.app_label, p.content_type.model) not in MODELOS_SOLO_ADMIN
    ]
    analista, _ = Group.objects.get_or_create(name=Rol.ANALISTA)
    analista.permissions.set(
        [
            p
            for p in de_datos
            if p.codename.split("_")[0] in ("view", "add", "change")
            or (p.content_type.app_label, p.codename) in PERMISOS_EXTRA_ANALISTA
        ]
    )
    lector, _ = Group.objects.get_or_create(name=Rol.LECTOR)
    lector.permissions.set([p for p in de_datos if p.codename.startswith("view_")])
