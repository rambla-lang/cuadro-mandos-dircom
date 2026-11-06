from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.contratacion.services import cargar_reglas


class Command(BaseCommand):
    help = "Carga las reglas de clasificación iniciales (no modifica las existentes)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fichero",
            type=Path,
            default=Path(settings.BASE_DIR) / "seed" / "reglas_clasificacion.json",
        )

    def handle(self, *args, **opts):
        nuevas, existentes = cargar_reglas(opts["fichero"])
        self.stdout.write(f"Reglas nuevas: {nuevas}; ya existentes: {existentes}.")
