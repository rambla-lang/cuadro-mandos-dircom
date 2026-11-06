from django.contrib.auth import get_user_model
from django.core.management.base import CommandError

from apps.nucleo.models import TrabajoIngesta
from apps.nucleo.trabajos import ejecutar_hasta_terminar


def usuario(email):
    if not email:
        return None
    u = get_user_model().objects.filter(email__iexact=email).first()
    if u is None:
        raise CommandError(f"No existe el usuario {email}.")
    return u


def ejecutar(comando, tipo, parametros, email):
    trabajo = TrabajoIngesta.objects.create(
        tipo=tipo, parametros=parametros, usuario=usuario(email)
    )
    comando.stdout.write(f"Trabajo {trabajo.pk} ({tipo}) en marcha…")
    trabajo = ejecutar_hasta_terminar(trabajo)
    comando.stdout.write(trabajo.log)
    comando.stdout.write(
        f"Estado: {trabajo.get_estado_display()}. Contadores: {trabajo.contadores}"
    )
    if trabajo.estado != TrabajoIngesta.Estado.TERMINADO:
        raise CommandError("El trabajo no ha terminado bien; revisa el registro.")
    return trabajo
