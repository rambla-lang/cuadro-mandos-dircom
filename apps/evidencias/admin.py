from django.contrib import admin

from apps.nucleo.services import instantanea, registrar_auditoria

from .enums import EstadoValidacion
from .models import Evidencia, EvidenciaEmpresa, EvidenciaMunicipio, Fuente, PrestacionServicio


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
        "lote_importacion",
        "validado_por",
        "validado_en",
        "creado_por",
        "creado",
        "modificado",
    )
    autocomplete_fields = ("fuente",)
    inlines = [EvidenciaEmpresaInline, EvidenciaMunicipioInline]

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
    list_display = ("municipio", "servicio", "alcance", "empresa", "gestion", "nivel")
    list_filter = ("servicio", "nivel", "gestion")
    search_fields = ("municipio__nombre_oficial", "empresa__nombre")
    autocomplete_fields = ("municipio", "empresa", "evidencias")
