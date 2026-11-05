from django import forms
from django.contrib import admin

from apps.evidencias.enums import Servicio

from .models import AcotacionCompetidor, AliasEmpresa, Empresa, GrupoEmpresarial


class AliasInline(admin.TabularInline):
    model = AliasEmpresa
    extra = 1
    fields = ("texto", "tipo", "requiere_contexto")


class AcotacionForm(forms.ModelForm):
    servicios_incluidos = forms.MultipleChoiceField(
        label="Servicios incluidos",
        choices=Servicio.choices,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Ninguno marcado: la acotación no limita por servicio (ver la nota).",
    )

    class Meta:
        model = AcotacionCompetidor
        fields = ("empresa", "servicios_incluidos", "ambito_geografico", "nota", "fuente")


class AcotacionInline(admin.StackedInline):
    model = AcotacionCompetidor
    form = AcotacionForm
    extra = 0
    fields = ("servicios_incluidos", "ambito_geografico", "nota", "fuente")


@admin.register(GrupoEmpresarial)
class GrupoEmpresarialAdmin(admin.ModelAdmin):
    search_fields = ("nombre",)


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "grupo", "es_competidor_seguido", "es_propia", "activa")
    list_filter = ("es_competidor_seguido", "es_propia", "activa", "grupo")
    search_fields = ("nombre", "nif", "alias__texto")
    inlines = [AliasInline, AcotacionInline]


@admin.register(AliasEmpresa)
class AliasEmpresaAdmin(admin.ModelAdmin):
    list_display = ("texto", "empresa", "tipo", "requiere_contexto")
    list_filter = ("tipo", "requiere_contexto")
    search_fields = ("texto", "empresa__nombre")
    autocomplete_fields = ("empresa",)


@admin.register(AcotacionCompetidor)
class AcotacionCompetidorAdmin(admin.ModelAdmin):
    form = AcotacionForm
    list_display = ("empresa", "servicios_incluidos", "ambito_geografico", "nota")
    search_fields = ("empresa__nombre", "nota")
    autocomplete_fields = ("empresa",)
