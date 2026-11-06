"""Ingesta de TED (Search API v3) para un rango de fechas de publicación."""

from datetime import date

from django.core.management.base import BaseCommand, CommandError

from apps.contratacion.trabajos import TIPO_TED

from ._comun import ejecutar


class Command(BaseCommand):
    help = "Carga avisos de TED con lugar de ejecución ES52 y comprador valenciano."

    def add_arguments(self, parser):
        parser.add_argument("--desde", required=True, help="AAAA-MM-DD")
        parser.add_argument("--hasta", required=True, help="AAAA-MM-DD")
        parser.add_argument("--usuario", help="Email de quien lanza la carga (opcional).")

    def handle(self, *args, **opts):
        try:
            desde, hasta = date.fromisoformat(opts["desde"]), date.fromisoformat(opts["hasta"])
        except ValueError as e:
            raise CommandError("Fechas con la forma AAAA-MM-DD.") from e
        if desde > hasta:
            raise CommandError("--desde es posterior a --hasta.")
        ejecutar(self, TIPO_TED, {"desde": str(desde), "hasta": str(hasta)}, opts["usuario"])
