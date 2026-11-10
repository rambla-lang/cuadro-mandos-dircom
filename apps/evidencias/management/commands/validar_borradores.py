"""Valida en bloque las evidencias en borrador cuando una persona da los datos por buenos.

Usa los mismos servicios que la bandeja y el administrador (cada cambio queda en la auditoría
a nombre de --usuario). Las evidencias con el nivel pendiente de decidir reciben el nivel de
--nivel-pendiente (por defecto «parcial», el provisional: nunca se sube a «oficial» sin URL).
Las propuestas de la IA no se tocan: se aceptan una a una en la bandeja.
"""

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.evidencias import services_revision as srv
from apps.evidencias.enums import EstadoValidacion, NivelEvidencia, Origen
from apps.evidencias.models import Evidencia
from apps.nucleo.models import ElementoRevision


class _Simulacion(Exception):
    pass


class Command(BaseCommand):
    help = "Valida en bloque las evidencias en borrador (no las de la IA)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--usuario", required=True, help="Email de quien da los datos por buenos."
        )
        parser.add_argument(
            "--nivel-pendiente",
            default=NivelEvidencia.PARCIAL,
            choices=[NivelEvidencia.PARCIAL, NivelEvidencia.EMPRESA, NivelEvidencia.PRENSA],
            help="Nivel para las evidencias con el nivel pendiente de decidir.",
        )
        parser.add_argument(
            "--comentario", default="Validación en bloque autorizada por el usuario."
        )
        parser.add_argument("--simular", action="store_true", help="No guarda nada.")

    def handle(self, *args, **opts):
        usuario = get_user_model().objects.filter(email__iexact=opts["usuario"]).first()
        if usuario is None:
            raise CommandError(f"No existe el usuario {opts['usuario']}.")
        try:
            with transaction.atomic():
                niveles, validadas = self._validar(usuario, opts)
                if opts["simular"]:
                    raise _Simulacion
        except _Simulacion:
            pass
        modo = "Simulación (no se ha guardado nada)" if opts["simular"] else "Hecho"
        self.stdout.write(
            f"{modo}: nivel decidido en {niveles} evidencias "
            f"(«{opts['nivel_pendiente']}»); validadas {validadas}."
        )

    def _validar(self, usuario, opts):
        borradores = Evidencia.objects.filter(estado_validacion=EstadoValidacion.BORRADOR).exclude(
            origen=Origen.IA
        )
        pendientes = ElementoRevision.objects.filter(
            tipo=ElementoRevision.Tipo.NIVEL_POR_DECIDIR,
            estado=ElementoRevision.Estado.PENDIENTE,
            objeto_tipo=ContentType.objects.get_for_model(Evidencia),
            objeto_id__in=borradores.values_list("pk", flat=True),
        )
        niveles = 0
        for el in pendientes:
            srv.decidir_nivel(el, opts["nivel_pendiente"], usuario, comentario=opts["comentario"])
            niveles += 1
        validadas = srv.validar_evidencias(borradores, usuario)
        return niveles, validadas
