"""Plantilla del juego de evaluación de T1 (docs/06, P-12): 50 menciones reales para anotar a
mano. Se escribe fuera del repositorio (media/eval/) porque contiene extractos de prensa."""

import csv
import random
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.medios.models import Mencion

COLUMNAS = [
    "mencion_id",
    "titulo",
    "extracto",
    "url",
    "empresas_correctas (nombres separados por ;)",
    "vinculo_correcto (si/no/dudoso)",
    "notas",
]


class Command(BaseCommand):
    help = "Exporta 50 menciones al azar (semilla fija) para anotarlas y evaluar T1."

    def add_arguments(self, parser):
        parser.add_argument("--n", type=int, default=50)
        parser.add_argument("--semilla", type=int, default=2026)
        parser.add_argument(
            "--salida", type=Path, default=Path(settings.MEDIA_ROOT) / "eval" / "menciones_t1.csv"
        )

    def handle(self, *args, **o):
        ids = sorted(Mencion.objects.filter(origen="brandwatch").values_list("pk", flat=True))
        elegidos = sorted(random.Random(o["semilla"]).sample(ids, min(o["n"], len(ids))))
        o["salida"].parent.mkdir(parents=True, exist_ok=True)
        with o["salida"].open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(COLUMNAS)
            for m in Mencion.objects.filter(pk__in=elegidos).order_by("pk"):
                w.writerow([m.pk, m.titulo, m.extracto, m.url, "", "", ""])
        self.stdout.write(
            f"{len(elegidos)} menciones en {o['salida']}. Rellena las dos columnas de respuesta."
        )
