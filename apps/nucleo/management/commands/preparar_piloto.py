"""Datos de partida idempotentes del piloto: municipios del INE, competidores y reglas de
clasificación. Se ejecuta en cada arranque en Render (no hay comando previo al despliegue en el
plan gratuito) y no modifica lo que ya exista."""

from django.core.management import call_command
from django.core.management.base import BaseCommand

from apps.territorio.models import Municipio


class Command(BaseCommand):
    help = "Carga (si faltan) municipios, competidores y reglas de clasificación."

    def handle(self, *args, **opts):
        if Municipio.objects.count() < 542:
            call_command(
                "cargar_municipios",
                "--provincias",
                "03",
                "12",
                "46",
                "--comunidad",
                "Comunitat Valenciana",
                stdout=self.stdout,
            )
        call_command("cargar_competidores_iniciales", stdout=self.stdout)
        call_command("cargar_reglas_clasificacion", stdout=self.stdout)
