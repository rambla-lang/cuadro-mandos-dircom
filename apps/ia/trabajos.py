"""Lotes de IA como trabajos por partes (ADR-007): una parte = un objeto."""

from apps.contratacion.models import Expediente
from apps.documentos.models import Documento
from apps.medios.models import Mencion
from apps.nucleo.models import TrabajoIngesta
from apps.nucleo.trabajos import registrar

from . import tareas
from .cliente import IANoDisponible

TIPO = "ia_lote"
FUNCIONES = {
    "T1": (Mencion, tareas.t1_atribuir_mencion),
    "T2": (Documento, tareas.t2_leer_recorte),
    "T3": (Expediente, tareas.t3_clasificar_expediente),
}


@registrar(TIPO)
def parte_ia(trabajo: TrabajoIngesta) -> bool:
    p = trabajo.progreso
    ids = trabajo.parametros["ids"]
    i = p.get("i", 0)
    trabajo.partes_total = len(ids)
    if i >= len(ids):
        return True
    modelo, funcion = FUNCIONES[trabajo.parametros["tarea"]]
    obj = modelo.objects.filter(pk=ids[i]).first()
    if obj is not None:
        try:
            funcion(obj, trabajo.usuario)
            trabajo.sumar(propuestas=1)
        except IANoDisponible as e:
            trabajo.anotar(f"Parado: {e}")
            trabajo.sumar(bloqueadas=len(ids) - i)
            p["i"] = len(ids)
            trabajo.partes_hechas = i
            return True
        except Exception as e:  # noqa: BLE001 - un objeto con error no para el lote
            trabajo.anotar(f"{modelo.__name__} {ids[i]}: {e}")
            trabajo.sumar(errores=1)
    p["i"] = i + 1
    trabajo.partes_hechas = i + 1
    return p["i"] >= len(ids)
