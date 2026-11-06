"""Ejecutor de trabajos en proceso (ADR-007).

Un hilo del servidor web toma trabajos pendientes con `select_for_update(skip_locked=True)` y
los ejecuta parte a parte. Cada tipo de trabajo registra una función `parte(trabajo) -> bool`
que procesa una parte, guarda su estado en `trabajo.progreso` y devuelve True cuando ha
terminado. Los comandos `manage.py` usan `ejecutar_hasta_terminar` en el mismo proceso.
"""

import logging
import threading
import traceback
from collections.abc import Callable
from datetime import timedelta

from django.db import close_old_connections, transaction
from django.utils import timezone

from .models import TrabajoIngesta

log = logging.getLogger(__name__)
Estado = TrabajoIngesta.Estado

_REGISTRO: dict[str, Callable[[TrabajoIngesta], bool]] = {}
_hilo: threading.Thread | None = None
_cerrojo = threading.Lock()
LATIDO_CADUCADO = timedelta(minutes=3)


def registrar(tipo: str):
    def decorador(funcion):
        _REGISTRO[tipo] = funcion
        return funcion

    return decorador


def procesar_parte(trabajo: TrabajoIngesta) -> bool:
    """Procesa una parte y la confirma. Devuelve True si el trabajo ya no sigue."""
    funcion = _REGISTRO.get(trabajo.tipo)
    if funcion is None:
        trabajo.estado = Estado.ERROR
        trabajo.anotar(f"Tipo de trabajo desconocido: {trabajo.tipo}")
        trabajo.save()
        return True
    if trabajo.inicio is None:
        trabajo.inicio = timezone.now()
    trabajo.estado = Estado.EN_CURSO
    trabajo.latido = timezone.now()
    try:
        with transaction.atomic():
            terminado = funcion(trabajo)
            trabajo.latido = timezone.now()
            if terminado:
                trabajo.estado = Estado.TERMINADO
                trabajo.fin = timezone.now()
                trabajo.anotar("Terminado.")
            trabajo.save()
        return terminado
    except Exception as e:  # noqa: BLE001 - se registra y el trabajo queda en error
        trabajo.refresh_from_db()
        trabajo.estado = Estado.ERROR
        trabajo.fin = timezone.now()
        trabajo.anotar(f"Error: {e}")
        trabajo.anotar(traceback.format_exc(limit=3))
        trabajo.save()
        log.exception("Trabajo %s en error", trabajo.pk)
        return True


def ejecutar_hasta_terminar(trabajo: TrabajoIngesta) -> TrabajoIngesta:
    while not procesar_parte(trabajo):
        trabajo.refresh_from_db()
        if trabajo.estado == Estado.CANCELADO:
            break
    trabajo.refresh_from_db()
    return trabajo


def _tomar_siguiente() -> TrabajoIngesta | None:
    caducado = timezone.now() - LATIDO_CADUCADO
    with transaction.atomic():
        candidato = (
            TrabajoIngesta.objects.select_for_update(skip_locked=True)
            .filter(estado=Estado.PENDIENTE)
            .order_by("creado")
            .first()
        ) or (
            TrabajoIngesta.objects.select_for_update(skip_locked=True)
            .filter(estado=Estado.EN_CURSO, latido__lt=caducado)
            .order_by("creado")
            .first()
        )
        if candidato is None:
            return None
        candidato.estado = Estado.EN_CURSO
        candidato.latido = timezone.now()
        candidato.save(update_fields=["estado", "latido"])
        return candidato


def _bucle():
    try:
        while True:
            close_old_connections()
            trabajo = _tomar_siguiente()
            if trabajo is None:
                return
            while True:
                if procesar_parte(trabajo):
                    break
                trabajo.refresh_from_db()
                if trabajo.estado == Estado.CANCELADO:
                    break
    finally:
        close_old_connections()


def lanzar_ejecutor() -> bool:
    """Arranca el hilo ejecutor si no hay uno vivo. Devuelve True si lo arranca."""
    global _hilo
    with _cerrojo:
        if _hilo is not None and _hilo.is_alive():
            return False
        _hilo = threading.Thread(target=_bucle, name="ejecutor-trabajos", daemon=True)
        _hilo.start()
        return True
