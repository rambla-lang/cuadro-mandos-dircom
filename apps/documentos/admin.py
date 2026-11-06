from django.contrib import admin

from .models import Documento, Fragmento, PercepcionInterna


@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = ("nombre_archivo", "tipo", "lectura", "paginas", "creado")
    list_filter = ("tipo", "lectura")
    search_fields = ("nombre_archivo", "sha256")
    readonly_fields = ("sha256", "ruta_almacen", "subido_por")


@admin.register(Fragmento)
class FragmentoAdmin(admin.ModelAdmin):
    list_display = ("documento", "empresa")
    raw_id_fields = ("documento", "empresa")


@admin.register(PercepcionInterna)
class PercepcionAdmin(admin.ModelAdmin):
    list_display = ("empresa", "documento_origen", "creado")
    search_fields = ("texto",)
    raw_id_fields = ("documento_origen",)
