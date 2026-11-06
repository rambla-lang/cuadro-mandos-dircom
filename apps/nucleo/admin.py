from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm

from .models import ElementoRevision, LoteImportacion, RegistroAuditoria, Usuario


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


@admin.register(LoteImportacion)
class LoteImportacionAdmin(admin.ModelAdmin):
    list_display = ("tipo", "inicio", "fin", "leidos", "nuevos", "actualizados", "errores")
    list_filter = ("tipo",)
    readonly_fields = [f.name for f in LoteImportacion._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(RegistroAuditoria)
class RegistroAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("fecha", "usuario_email", "accion", "objeto_repr")
    list_filter = ("accion",)
    search_fields = ("usuario_email", "accion", "objeto_repr")
    readonly_fields = [f.name for f in RegistroAuditoria._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ElementoRevision)
class ElementoRevisionAdmin(admin.ModelAdmin):
    """Consulta. Se resuelve desde la bandeja (/revision/), que aplica los cambios y audita."""

    list_display = ("tipo", "texto", "estado", "resuelto_por", "resuelto_en")
    list_filter = ("tipo", "estado")
    search_fields = ("texto",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
