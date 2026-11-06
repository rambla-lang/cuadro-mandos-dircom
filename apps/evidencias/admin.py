from django.contrib import admin

from apps.nucleo.services import instantanea, registrar_auditoria

from .enums import EstadoValidacion
from .models import (
    Evidencia,
    EvidenciaEmpresa,
    EvidenciaMunicipio,
    Fuente,
    PlantillaImportacion,
    PrestacionServicio,
)
from .services_revision import validar_evidencias


@admin.register(Fuente)
class FuenteAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tipo", "dominio")
    list_filter = ("tipo",)
    search_fields = ("nombre", "dominio")


class EvidenciaEmpresaInline(admin.TabularInline):
    model = EvidenciaEmpresa
    extra = 0
    autocomplete_fields = ("empresa",)


class EvidenciaMunicipioInline(admin.TabularInline):
    model = EvidenciaMunicipio
    extra = 0
    autocomplete_fields = ("municipio",)


@admin.register(Evidencia)
class EvidenciaAdmin(admin.ModelAdmin):
    list_display = (
        "codigo",
        "titulo",
        "categoria",
        "nivel",
        "estado_validacion",
        "origen",
        "fecha_publicacion",
    )
    list_filter = ("nivel", "estado_validacion", "origen", "categoria", "servicio")
    search_fields = ("codigo", "titulo", "extracto", "url_origen")
    readonly_fields = (
        "codigo",
        "clave_importacion",
        "lote_importacion",
        "validado_por",
        "validado_en",
        "creado_por",
        "creado",
        "modificado",
    )
    autocomplete_fields = ("fuente",)
    inlines = [EvidenciaEmpresaInline, EvidenciaMunicipioInline]
    actions = ["validar"]

    @admin.action(description="Validar las evidencias seleccionadas", permissions=["validar"])
    def validar(self, request, queryset):
        n = validar_evidencias(queryset, request.user)
        omitidas = queryset.count() - n
        self.message_user(
            request,
            f"Validadas: {n}. Sin cambios: {omitidas} (ya validadas o con el nivel pendiente "
            "de decidir en la bandeja).",
        )

    def has_validar_permission(self, request):
        return request.user.has_perm("evidencias.validar_evidencia")

    def save_model(self, request, obj, form, change):
        """docs/03: una evidencia validada solo se modifica dejando registro de auditoría."""
        antes = None
        if change:
            original = Evidencia.objects.get(pk=obj.pk)
            if original.estado_validacion == EstadoValidacion.VALIDADA:
                antes = instantanea(original)
        else:
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)
        if antes is not None:
            registrar_auditoria(
                request.user,
                "evidencia.editar_validada",
                obj,
                antes=antes,
                despues=instantanea(obj),
            )


@admin.register(PrestacionServicio)
class PrestacionServicioAdmin(admin.ModelAdmin):
    list_display = (
        "municipio",
        "servicio",
        "alcance",
        "empresa",
        "operador_texto",
        "gestion",
        "nivel",
    )
    list_filter = ("servicio", "nivel", "gestion")
    search_fields = ("municipio__nombre_oficial", "empresa__nombre", "operador_texto")
    autocomplete_fields = ("municipio", "empresa", "evidencias")


@admin.register(PlantillaImportacion)
class PlantillaImportacionAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tipo", "modificado")
    readonly_fields = ("creado_por", "creado", "modificado")
