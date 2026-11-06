from django.contrib import admin

from .models import LlamadaIA, PropuestaIA


@admin.register(LlamadaIA)
class LlamadaAdmin(admin.ModelAdmin):
    list_display = (
        "creado",
        "tarea",
        "modelo",
        "estado",
        "tokens_entrada",
        "tokens_salida",
        "coste_estimado",
    )
    list_filter = ("tarea", "estado", "modelo")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(PropuestaIA)
class PropuestaAdmin(admin.ModelAdmin):
    list_display = ("creado", "llamada", "estado_revision", "revisado_por")
    list_filter = ("estado_revision",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
