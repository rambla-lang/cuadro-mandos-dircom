from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from apps.nucleo import views as nucleo_views

urlpatterns = [
    path("", nucleo_views.portada, name="portada"),
    path("acceso/", auth_views.LoginView.as_view(), name="login"),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),
    path("admin/", admin.site.urls),
]
