"""Ingesta de PLACSP (ADR-008): un ZIP o .atom ya descargado, o el ZIP mensual de un mes."""

import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.contratacion.trabajos import TIPO_PLACSP

from ._comun import ejecutar


class Command(BaseCommand):
    help = (
        "Carga expedientes de PLACSP de la Comunitat Valenciana. --fichero acepta un ZIP mensual "
        "o anual ya descargado o un .atom; --mes AAAAMM descarga el ZIP mensual (unos 200 MB)."
    )

    def add_arguments(self, parser):
        grupo = parser.add_mutually_exclusive_group(required=True)
        grupo.add_argument("--fichero", type=Path)
        grupo.add_argument("--mes", help="AAAAMM")
        parser.add_argument("--usuario", help="Email de quien lanza la carga (opcional).")

    def handle(self, *args, **opts):
        if opts["fichero"]:
            if not opts["fichero"].exists():
                raise CommandError(f"No existe {opts['fichero']}.")
            parametros = {"fichero": str(opts["fichero"].resolve())}
        else:
            if not re.fullmatch(r"20\d{2}(0[1-9]|1[0-2])", opts["mes"] or ""):
                raise CommandError("--mes debe tener la forma AAAAMM.")
            parametros = {"mes": opts["mes"]}
        ejecutar(self, TIPO_PLACSP, parametros, opts["usuario"])
