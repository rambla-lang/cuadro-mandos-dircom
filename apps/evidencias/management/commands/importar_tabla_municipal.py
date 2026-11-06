"""Importa una tabla municipal con una plantilla (el mismo servicio que el asistente web)."""

import json
from datetime import date
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.evidencias.importers.tabla_municipal import FormatoTablaError, importar_tabla
from apps.evidencias.models import PlantillaImportacion


class Command(BaseCommand):
    help = (
        "Importa una tabla municipal (CSV o Excel). --plantilla es un JSON de "
        "seed/plantillas_importacion/ o el nombre de una plantilla guardada."
    )

    def add_arguments(self, parser):
        parser.add_argument("--fichero", required=True, type=Path)
        parser.add_argument("--plantilla", required=True)
        parser.add_argument("--usuario", required=True, help="Email de quien importa (y valida).")
        parser.add_argument(
            "--fecha-consulta",
            help="AAAA-MM-DD. Obligatoria si la plantilla no la trae; por defecto, hoy.",
        )
        parser.add_argument("--simular", action="store_true", help="No guarda nada.")

    def handle(self, *args, **opts):
        usuario = get_user_model().objects.filter(email__iexact=opts["usuario"]).first()
        if usuario is None:
            raise CommandError(f"No existe el usuario {opts['usuario']}.")
        plantilla = self._plantilla(opts["plantilla"], usuario)
        config = dict(plantilla.configuracion)
        if opts["fecha_consulta"]:
            config["fecha_consulta"] = opts["fecha_consulta"]
        config["fecha_consulta"] = config.get("fecha_consulta") or date.today().isoformat()
        try:
            res = importar_tabla(
                opts["fichero"],
                config,
                usuario,
                nombre_archivo=opts["fichero"].name,
                aplicar=not opts["simular"],
            )
        except FormatoTablaError as e:
            raise CommandError(str(e)) from e
        modo = "Simulación (no se ha guardado nada)" if opts["simular"] else f"Lote {res.lote_id}"
        self.stdout.write(
            f"{modo}: filas {res.filas_leidas}; evidencias nuevas {res.evidencias_nuevas}, "
            f"ya existentes {res.evidencias_existentes}; prestaciones nuevas "
            f"{res.prestaciones_nuevas}; «No localizado» sin datos {res.celdas_sin_dato}; "
            f"a revisión {res.total_revision} {res.a_revision}; ya pendientes "
            f"{res.ya_en_revision}; errores {len(res.errores)}."
        )
        for e in res.errores:
            self.stdout.write(f"  {e}")

    def _plantilla(self, valor: str, usuario) -> PlantillaImportacion:
        ruta = Path(valor)
        if ruta.suffix == ".json" and ruta.exists():
            datos = json.loads(ruta.read_text(encoding="utf-8"))
            plantilla, creada = PlantillaImportacion.objects.get_or_create(
                nombre=datos["nombre"],
                defaults={
                    "descripcion": datos.get("descripcion", ""),
                    "configuracion": datos["configuracion"],
                    "creado_por": usuario,
                },
            )
            if not creada:
                self.stdout.write(
                    f"La plantilla «{plantilla.nombre}» ya existía: se usa la guardada "
                    "(puede estar editada)."
                )
            return plantilla
        plantilla = PlantillaImportacion.objects.filter(nombre=valor).first()
        if plantilla is None:
            raise CommandError(f"No existe la plantilla «{valor}».")
        return plantilla
