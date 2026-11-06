from django.contrib import admin

from .models import Adjudicacion, Expediente, LoteContrato, OrganoContratacion, ReglaClasificacion


@admin.register(OrganoContratacion)
class OrganoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "nif", "municipio", "estado_vinculacion", "codigo_postal")
    list_filter = ("estado_vinculacion",)
    search_fields = ("nombre", "nif", "dir3", "id_plataforma")
    autocomplete_fields = ("municipio",)
    readonly_fields = ("id_plataforma", "jerarquia", "creado", "modificado")


class LoteInline(admin.TabularInline):
    model = LoteContrato
    extra = 0


class AdjudicacionInline(admin.TabularInline):
    model = Adjudicacion
    extra = 0
    autocomplete_fields = ("empresa",)


@admin.register(Expediente)
class ExpedienteAdmin(admin.ModelAdmin):
    list_display = ("numero_expediente", "fuente", "objeto", "servicio_clasificado", "estado")
    list_filter = ("fuente", "servicio_clasificado", "metodo_clasificacion", "estado")
    search_fields = ("objeto", "numero_expediente", "id_externo")
    readonly_fields = ("id_externo", "entrada_atom_id", "fichero_origen", "lote_importacion")
    raw_id_fields = ("organo",)
    inlines = [LoteInline, AdjudicacionInline]


@admin.register(ReglaClasificacion)
class ReglaAdmin(admin.ModelAdmin):
    list_display = ("tipo", "patron", "servicio", "alcance", "activa", "nota")
    list_filter = ("tipo", "servicio", "activa")
    search_fields = ("patron", "nota")
