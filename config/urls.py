from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from apps.nucleo import views as nucleo_views
from apps.territorio import views as territorio_views

urlpatterns = [
    path("", nucleo_views.portada, name="portada"),
    path("acceso/", auth_views.LoginView.as_view(), name="login"),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),
    path("usuarios/", nucleo_views.usuarios, name="usuarios"),
    path("usuarios/invitar/", nucleo_views.invitar, name="invitar"),
    path("usuarios/<int:pk>/enlace/", nucleo_views.generar_enlace, name="generar_enlace"),
    path(
        "invitacion/<uidb64>/<token>/",
        nucleo_views.InvitacionConfirmarView.as_view(),
        name="invitacion_confirmar",
    ),
    path(
        "invitacion/completada/",
        nucleo_views.InvitacionCompletadaView.as_view(),
        name="invitacion_completada",
    ),
    path("municipios/", territorio_views.municipios, name="municipios"),
    path("admin/", admin.site.urls),
]
