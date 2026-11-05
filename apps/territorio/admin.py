from django.contrib import admin

from .models import EntidadSupramunicipal, Municipio, Provincia


@admin.register(Provincia)
class ProvinciaAdmin(admin.ModelAdmin):
    list_display = ("codigo_ine", "nombre", "comunidad")
    search_fields = ("nombre", "codigo_ine")


@admin.register(Municipio)
class MunicipioAdmin(admin.ModelAdmin):
    list_display = ("codigo_ine", "nombre_oficial", "provincia")
    list_filter = ("provincia",)
    search_fields = ("nombre_oficial", "codigo_ine", "nombres_normalizados")
    readonly_fields = ("nombres_normalizados", "lote_importacion", "creado", "modificado")
    fields = (
        "codigo_ine",
        "nombre_oficial",
        "nombres_alternativos",
        "provincia",
        "nombres_normalizados",
        "lote_importacion",
        "creado",
        "modificado",
    )


@admin.register(EntidadSupramunicipal)
class EntidadSupramunicipalAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tipo")
    list_filter = ("tipo",)
    search_fields = ("nombre",)
    autocomplete_fields = ("municipios",)
