"""Alta de usuarios por invitación (RF-03). Sin SMTP (P-04): el enlace se muestra al
administrador, que lo comparte por otro canal."""

from django.contrib.auth.models import Group
from django.db import transaction

from .models import Usuario
from .roles import Rol
from .services import registrar_auditoria


@transaction.atomic
def invitar_usuario(*, email: str, nombre: str, rol: Rol, invitado_por) -> Usuario:
    usuario = Usuario(email=email, nombre=nombre, is_staff=(rol == Rol.ADMINISTRADOR))
    usuario.set_unusable_password()
    usuario.save()
    usuario.groups.set([Group.objects.get(name=rol)])
    registrar_auditoria(
        invitado_por,
        "usuario.invitar",
        usuario,
        despues={"email": email, "nombre": nombre, "rol": str(rol)},
    )
    return usuario


def rol_de(usuario) -> str:
    if usuario.is_superuser:
        return "Administrador (superusuario)"
    nombres = list(usuario.groups.values_list("name", flat=True))
    return ", ".join(nombres) or "Sin rol"
