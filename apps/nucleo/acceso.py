"""Utilidades de acceso: invitación con enlace de un solo uso y bloqueo (ADR-009)."""

from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .models import normalizar_email


class GeneradorTokenInvitacion(PasswordResetTokenGenerator):
    """Token de un solo uso: deja de valer al fijar la contraseña (cambia su hash) y caduca
    a las PASSWORD_RESET_TIMEOUT segundos (72 h)."""

    key_salt = "apps.nucleo.acceso.GeneradorTokenInvitacion"


token_invitacion = GeneradorTokenInvitacion()


def enlace_invitacion(request, usuario) -> str:
    uidb64 = urlsafe_base64_encode(force_bytes(usuario.pk))
    token = token_invitacion.make_token(usuario)
    ruta = reverse("invitacion_confirmar", kwargs={"uidb64": uidb64, "token": token})
    return request.build_absolute_uri(ruta)


def usuario_para_axes(request, credentials) -> str:
    """Axes cuenta los fallos por email normalizado, igual que el login."""
    credentials = credentials or {}
    email = credentials.get("username") or request.POST.get("username", "")
    return normalizar_email(email)
