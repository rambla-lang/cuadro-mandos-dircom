from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST

from .acceso import enlace_invitacion, token_invitacion
from .forms import InvitacionForm
from .models import TrabajoIngesta, Usuario
from .roles import Rol, rol_requerido
from .services import registrar_auditoria
from .services_usuarios import invitar_usuario, rol_de
from .trabajos import lanzar_ejecutor


def portada(request):
    """Portada provisional. Exige sesión por LoginRequiredMiddleware."""
    return render(request, "nucleo/portada.html")


@rol_requerido(Rol.ADMINISTRADOR)
def usuarios(request):
    lista = [
        {"u": u, "rol": rol_de(u), "pendiente": not u.has_usable_password()}
        for u in Usuario.objects.prefetch_related("groups")
    ]
    return render(request, "nucleo/usuarios.html", {"usuarios": lista})


@rol_requerido(Rol.ADMINISTRADOR)
def invitar(request):
    form = InvitacionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        usuario = invitar_usuario(
            email=form.cleaned_data["email"],
            nombre=form.cleaned_data["nombre"],
            rol=Rol(form.cleaned_data["rol"]),
            invitado_por=request.user,
        )
        return render(
            request,
            "nucleo/enlace_invitacion.html",
            {"usuario": usuario, "enlace": enlace_invitacion(request, usuario)},
        )
    return render(request, "nucleo/invitar.html", {"form": form})


@require_POST
@rol_requerido(Rol.ADMINISTRADOR)
def generar_enlace(request, pk):
    """Nuevo enlace para fijar contraseña (invitación caducada u olvido, sin SMTP)."""
    usuario = get_object_or_404(Usuario, pk=pk)
    if not usuario.is_active:
        messages.error(request, "El usuario está desactivado.")
        return redirect("usuarios")
    registrar_auditoria(request.user, "usuario.generar_enlace", usuario)
    return render(
        request,
        "nucleo/enlace_invitacion.html",
        {"usuario": usuario, "enlace": enlace_invitacion(request, usuario)},
    )


class InvitacionConfirmarView(auth_views.PasswordResetConfirmView):
    """El invitado fija su contraseña. Hereda login_not_required de Django."""

    token_generator = token_invitacion
    template_name = "registration/invitacion_confirmar.html"
    success_url = reverse_lazy("invitacion_completada")
    post_reset_login = False

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        registrar_auditoria(
            None, "usuario.fijar_contrasena", form.user, despues={"email": form.user.email}
        )
        return respuesta


class InvitacionCompletadaView(auth_views.PasswordResetCompleteView):
    template_name = "registration/invitacion_completada.html"


ROLES_TRABAJOS = (Rol.ADMINISTRADOR, Rol.ANALISTA)


@rol_requerido(*ROLES_TRABAJOS)
def trabajos(request):
    lista = TrabajoIngesta.objects.select_related("usuario")[:30]
    if any(t.activo for t in lista):
        lanzar_ejecutor()  # si el proceso se reinició, retoma el trabajo (ADR-007)
    plantilla = "nucleo/_trabajos.html" if request.htmx else "nucleo/trabajos.html"
    return render(
        request, plantilla, {"trabajos": lista, "hay_activos": any(t.activo for t in lista)}
    )


@rol_requerido(*ROLES_TRABAJOS)
def trabajo(request, pk):
    t = get_object_or_404(TrabajoIngesta, pk=pk)
    return render(request, "nucleo/trabajo.html", {"t": t})
