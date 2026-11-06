from django.contrib import admin

from .models import Hito, Medio, Mencion, MencionEmpresa, Pieza


@admin.register(Medio)
class MedioAdmin(admin.ModelAdmin):
    list_display = ("nombre", "dominio", "ambito", "grupo_editorial")
    list_filter = ("ambito",)
    search_fields = ("nombre", "dominio")


@admin.register(Pieza)
class PiezaAdmin(admin.ModelAdmin):
    list_display = (
        "codigo",
        "fecha_publicacion",
        "medio",
        "tipo",
        "titulo",
        "es_comunicado_propio",
    )
    list_filter = ("tipo", "es_comunicado_propio")
    search_fields = ("codigo", "titulo", "url_canonica")
    raw_id_fields = ("medio", "hito")


@admin.register(Hito)
class HitoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "fecha_evento")
    search_fields = ("nombre",)


class AtribucionInline(admin.TabularInline):
    model = MencionEmpresa
    extra = 0
    raw_id_fields = ("empresa",)
    readonly_fields = ("validado_por", "validado_en")


@admin.register(Mencion)
class MencionAdmin(admin.ModelAdmin):
    list_display = ("fecha_publicacion", "medio", "titulo", "origen", "vinculo_territorial")
    list_filter = ("origen", "vinculo_territorial", "tipo_pagina")
    search_fields = ("titulo", "extracto", "url", "resource_id")
    raw_id_fields = ("medio", "pieza", "documento", "lote_importacion")
    inlines = [AtribucionInline]
