"""Único punto de llamada a la API de Claude (ADR-005). Ninguna otra parte del código la usa.

- Desactivada si falta la clave, el modelo o `IA_ACTIVADA=false`: la llamada se registra como
  bloqueada y no se envía.
- Límite mensual (RNF-09, CP-15): si el gasto estimado del mes ya alcanza
  `IA_LIMITE_MENSUAL_EUR`, se bloquea antes de enviar. Sin precio configurado para el modelo no
  se puede controlar el gasto y también se bloquea.
- Salida estructurada con esquema JSON y validación con Pydantic; como mucho 2 reintentos.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models import Sum
from django.utils import timezone
from pydantic import BaseModel, ValidationError

from .models import LlamadaIA

PROMPTS = Path(__file__).parent / "prompts"
MODELOS = {
    "clasificar": "IA_MODELO_CLASIFICAR",
    "extraer": "IA_MODELO_EXTRAER",
    "redactar": "IA_MODELO_REDACTAR",
}
MAX_REINTENTOS = 2
# Multiplicadores de caché sobre el precio de entrada (referencia oficial del SDK de Anthropic:
# escribir en caché ~1,25×, leer de caché ~0,1×). Solo afectan a la estimación.
FACTOR_ESCRITURA_CACHE = Decimal("1.25")
FACTOR_LECTURA_CACHE = Decimal("0.1")


class IANoDisponible(Exception):
    """IA desactivada, sin configurar o límite mensual alcanzado. No se ha enviado nada."""


class ErrorIA(Exception):
    pass


def prompt(nombre: str) -> tuple[str, str]:
    """(texto, versión) de `prompts/<nombre>.md`."""
    return (PROMPTS / f"{nombre}.md").read_text(encoding="utf-8").strip(), nombre


def gasto_mes() -> Decimal:
    inicio = timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total = LlamadaIA.objects.filter(creado__gte=inicio).aggregate(s=Sum("coste_estimado"))["s"]
    return total or Decimal("0")


def modelo_de(tipo: str) -> str:
    return getattr(settings, MODELOS[tipo], "") or ""


def estado(tipo: str = "clasificar") -> tuple[bool, str]:
    """(disponible, motivo si no lo está)."""
    if not settings.IA_ACTIVADA:
        return False, "La IA está desactivada (IA_ACTIVADA=false)."
    if not settings.ANTHROPIC_API_KEY:
        return False, "Falta la clave de la API de Anthropic (ANTHROPIC_API_KEY)."
    modelo = modelo_de(tipo)
    if not modelo:
        return False, f"Falta el modelo para «{tipo}» ({MODELOS[tipo]})."
    if modelo not in (settings.IA_PRECIOS_JSON or {}):
        return (
            False,
            f"Falta el precio de {modelo} en IA_PRECIOS_JSON: no se puede controlar el gasto.",
        )
    limite = Decimal(str(settings.IA_LIMITE_MENSUAL_EUR or 0))
    if gasto_mes() >= limite:
        return False, f"Se ha alcanzado el límite mensual de IA ({limite} €)."
    return True, ""


def coste(modelo: str, uso) -> Decimal:
    precio = (settings.IA_PRECIOS_JSON or {}).get(modelo) or {}
    entrada = Decimal(str(precio.get("entrada", 0))) / 1_000_000
    salida = Decimal(str(precio.get("salida", 0))) / 1_000_000
    escritura = Decimal(getattr(uso, "cache_creation_input_tokens", 0) or 0)
    lectura = Decimal(getattr(uso, "cache_read_input_tokens", 0) or 0)
    return (
        Decimal(uso.input_tokens) * entrada
        + escritura * entrada * FACTOR_ESCRITURA_CACHE
        + lectura * entrada * FACTOR_LECTURA_CACHE
        + Decimal(uso.output_tokens) * salida
    ).quantize(Decimal("0.00001"))


def obtener_cliente():
    """Se sustituye en los tests por un cliente falso."""
    import anthropic

    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


@dataclass
class Resultado:
    datos: BaseModel
    llamada: LlamadaIA


def llamar(
    *,
    tarea: str,
    tipo_modelo: str,
    prompt_tarea: str,
    contenido: list,
    esquema: dict,
    validador: type[BaseModel],
    usuario=None,
    objeto=None,
    max_tokens: int = 4000,
    esfuerzo: str = "low",
) -> Resultado:
    comun, v_comun = prompt("comun_v1")
    texto_tarea, v_tarea = prompt(prompt_tarea)
    modelo = modelo_de(tipo_modelo)
    base = {
        "tarea": tarea,
        "modelo": modelo,
        "version_prompt": f"{v_comun}+{v_tarea}",
        "usuario": usuario,
        "objeto_tipo": ContentType.objects.get_for_model(objeto) if objeto is not None else None,
        "objeto_id": objeto.pk if objeto is not None else None,
    }
    disponible, motivo = estado(tipo_modelo)
    if not disponible:
        LlamadaIA.objects.create(**base, estado=LlamadaIA.Estado.BLOQUEADA, error=motivo)
        raise IANoDisponible(motivo)

    cliente = obtener_cliente()
    peticion = {
        "model": modelo,
        "max_tokens": max_tokens,
        "system": [
            {
                "type": "text",
                "text": f"{comun}\n\n{texto_tarea}",
                "cache_control": {"type": "ephemeral"},
            }
        ],
        "messages": [{"role": "user", "content": contenido}],
        "output_config": {"format": {"type": "json_schema", "schema": esquema}, "effort": esfuerzo},
    }
    ultimo_error = ""
    for _intento in range(MAX_REINTENTOS + 1):
        try:
            if settings.IA_FALLBACKS and "haiku" not in modelo:
                r = cliente.beta.messages.create(
                    betas=["server-side-fallback-2026-07-01"], fallbacks="default", **peticion
                )
            else:
                r = cliente.messages.create(**peticion)
        except Exception as e:  # noqa: BLE001 - errores de red o de la API se registran
            LlamadaIA.objects.create(**base, estado=LlamadaIA.Estado.ERROR, error=str(e)[:2000])
            raise ErrorIA(f"La API devolvió un error: {e}") from e
        uso = r.usage
        registro = {
            **base,
            "tokens_entrada": uso.input_tokens
            + (getattr(uso, "cache_creation_input_tokens", 0) or 0),
            "tokens_salida": uso.output_tokens,
            "tokens_cache_lectura": getattr(uso, "cache_read_input_tokens", 0) or 0,
            "coste_estimado": coste(modelo, uso),
            "id_peticion": getattr(r, "_request_id", "") or "",
        }
        if r.stop_reason == "refusal":
            LlamadaIA.objects.create(**registro, estado=LlamadaIA.Estado.RECHAZADA, error="refusal")
            raise ErrorIA("El modelo ha rechazado la petición.")
        texto = next((b.text for b in r.content if getattr(b, "type", "") == "text"), "")
        try:
            if r.stop_reason == "max_tokens":
                raise ValueError("respuesta cortada por max_tokens")
            datos = validador.model_validate(json.loads(texto))
        except (ValueError, ValidationError) as e:
            ultimo_error = f"Salida no válida: {e}"[:2000]
            LlamadaIA.objects.create(**registro, estado=LlamadaIA.Estado.ERROR, error=ultimo_error)
            continue
        llamada = LlamadaIA.objects.create(**registro, estado=LlamadaIA.Estado.OK)
        return Resultado(datos, llamada)
    raise ErrorIA(ultimo_error)
