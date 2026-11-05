from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.territorio.importers.ine import FormatoIneError, importar_municipios_ine

FICHERO_POR_DEFECTO = Path(settings.BASE_DIR) / "seed" / "ine" / "26codmun.xlsx"


class Command(BaseCommand):
    help = (
        "Carga provincias y municipios desde la relación de municipios del INE (xlsx). "
        "Idempotente. Ejemplo: --provincias 03 12 46 --comunidad 'Comunitat Valenciana'."
    )

    def add_arguments(self, parser):
        parser.add_argument("--fichero", type=Path, default=FICHERO_POR_DEFECTO)
        parser.add_argument(
            "--provincias", nargs="+", required=True, help="Códigos INE de provincia (dos dígitos)."
        )
        parser.add_argument("--comunidad", required=True)

    def handle(self, *args, fichero, provincias, comunidad, **opts):
        if not fichero.exists():
            raise CommandError(f"No existe el fichero {fichero}.")
        try:
            lote = importar_municipios_ine(fichero, provincias, comunidad)
        except FormatoIneError as e:
            raise CommandError(str(e)) from e
        if lote.log:
            self.stdout.write(lote.log.rstrip())
        self.stdout.write(
            self.style.SUCCESS(
                f"Leídos {lote.leidos}, nuevos {lote.nuevos}, actualizados {lote.actualizados} "
                f"(lote {lote.pk})."
            )
        )
