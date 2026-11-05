from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm

from .models import Usuario


class UsuarioCreationForm(AdminUserCreationForm):
    class Meta:
        model = Usuario
        fields = ("email",)


class UsuarioChangeForm(UserChangeForm):
    class Meta:
        model = Usuario
        fields = "__all__"


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    add_form = UsuarioCreationForm
    form = UsuarioChangeForm
    model = Usuario
    ordering = ("email",)
    list_display = ("email", "nombre", "is_active", "is_staff", "last_login")
    search_fields = ("email", "nombre")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Datos", {"fields": ("nombre",)}),
        ("Permisos", {"fields": ("is_active", "is_staff", "is_superuser", "groups")}),
        ("Fechas", {"fields": ("last_login", "fecha_alta")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),)
    filter_horizontal = ("groups",)
