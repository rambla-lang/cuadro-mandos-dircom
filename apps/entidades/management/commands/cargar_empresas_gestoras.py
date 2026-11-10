from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.entidades.services import cargar_empresas_gestoras

FICHERO_POR_DEFECTO = Path(settings.BASE_DIR) / "seed" / "empresas_gestoras_iniciales.json"


class Command(BaseCommand):
    help = "Carga las empresas gestoras de docs/00 con alias y acotaciones. Idempotente."

    def add_arguments(self, parser):
        parser.add_argument("--fichero", type=Path, default=FICHERO_POR_DEFECTO)

    def handle(self, *args, fichero, **opts):
        if not fichero.exists():
            raise CommandError(f"No existe el fichero {fichero}.")
        r = cargar_empresas_gestoras(fichero)
        self.stdout.write(
            self.style.SUCCESS(
                f"Empresas nuevas {r.empresas_nuevas} (ya existían {r.empresas_existentes}), "
                f"alias nuevos {r.alias_nuevos}, acotaciones nuevas {r.acotaciones_nuevas}."
            )
        )
