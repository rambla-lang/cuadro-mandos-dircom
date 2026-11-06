from django.contrib import admin

from .models import AuditoriaWeb, ObservacionDigital, PerfilDigital


class ObservacionInline(admin.TabularInline):
    model = ObservacionDigital
    extra = 0


@admin.register(PerfilDigital)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ("empresa", "red", "url", "cuenta_verificada")
    list_filter = ("red",)
    inlines = [ObservacionInline]


@admin.register(AuditoriaWeb)
class AuditoriaAdmin(admin.ModelAdmin):
    list_display = ("empresa", "fecha", "url")
