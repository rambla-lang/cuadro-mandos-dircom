"""Carga inicial de competidores (docs/00) como datos editables (RF-10, RF-11, RF-12)."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from django.db import transaction

from apps.nucleo.texto import normalizar_texto

from .models import AcotacionCompetidor, AliasEmpresa, Empresa, GrupoEmpresarial


@dataclass
class ResultadoCarga:
    empresas_nuevas: int = 0
    empresas_existentes: int = 0
    alias_nuevos: int = 0
    acotaciones_nuevas: int = 0


@transaction.atomic
def cargar_competidores(ruta: Path) -> ResultadoCarga:
    """Idempotente. Crea lo que falta y no modifica lo existente (puede estar editado).

    Las acotaciones de una empresa solo se crean si la empresa aún no tiene ninguna.
    """
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    fuente = datos.get("fuente", "")
    res = ResultadoCarga()
    grupos = {n: GrupoEmpresarial.objects.get_or_create(nombre=n)[0] for n in datos["grupos"]}

    for e in datos["empresas"]:
        empresa, creada = Empresa.objects.get_or_create(
            nombre=e["nombre"],
            defaults={
                "grupo": grupos.get(e.get("grupo")),
                "es_propia": e.get("propia", False),
                "es_competidor_seguido": e.get("competidor", False),
                "notas": f"Carga inicial. Fuente: {fuente}",
            },
        )
        if creada:
            res.empresas_nuevas += 1
        else:
            res.empresas_existentes += 1

        alias = [
            {
                "texto": e["nombre"],
                "tipo": AliasEmpresa.Tipo.MARCA,
                "requiere_contexto": e.get("alias_requiere_contexto", False),
            },
            *e.get("alias", []),
        ]
        for a in alias:
            _, nuevo = AliasEmpresa.objects.get_or_create(
                empresa=empresa,
                texto_normalizado=normalizar_texto(a["texto"]),
                defaults={
                    "texto": a["texto"],
                    "tipo": a.get("tipo", AliasEmpresa.Tipo.MARCA),
                    "requiere_contexto": a.get("requiere_contexto", False),
                },
            )
            res.alias_nuevos += nuevo

        if e.get("acotaciones") and not empresa.acotaciones.exists():
            for ac in e["acotaciones"]:
                AcotacionCompetidor.objects.create(
                    empresa=empresa,
                    servicios_incluidos=ac.get("servicios", []),
                    ambito_geografico=ac.get("ambito", ""),
                    nota=ac["nota"],
                    fuente=fuente,
                )
                res.acotaciones_nuevas += 1
    return res


# --- Resolución de nombres de operador (docs/04 §9) ---------------------------------------

_SEPARADORES_OPERADOR = re.compile(r"\s*(?:/|\+)\s*")
_PARENTESIS = re.compile(r"^(?P<fuera>[^()]*)\((?P<dentro>[^()]*)\)\s*$")


@dataclass
class ResolucionEmpresa:
    empresa: Empresa | None
    motivo: str = ""


def _por_texto_exacto(texto: str) -> tuple[Empresa | None, str]:
    norm = normalizar_texto(texto)
    if not norm:
        return None, "texto vacío"
    alias = list(
        AliasEmpresa.objects.filter(texto_normalizado=norm, empresa__activa=True).select_related(
            "empresa"
        )
    )
    empresas = {a.empresa_id: a for a in alias}
    if len(empresas) > 1:
        return None, f"«{texto}» es alias de varias empresas"
    if empresas:
        a = next(iter(empresas.values()))
        if a.requiere_contexto:
            return None, f"«{texto}» es un alias ambiguo (requiere contexto)"
        return a.empresa, ""
    for e in Empresa.objects.filter(activa=True):
        if normalizar_texto(e.nombre) == norm:
            return e, ""
    return None, f"«{texto}» no figura en el catálogo de empresas"


def resolver_empresa(texto: str) -> ResolucionEmpresa:
    """Empresa del catálogo para un literal de operador, solo si no hay duda.

    Reglas, en este orden (sin coincidencias parciales):
    1. Texto completo igual a un alias o nombre (normalizado). Un alias marcado
       `requiere_contexto` no resuelve.
    2. Si empieza por «UTE» o lleva «/» o «+», se resuelve cada parte; solo si todas dan la
       misma empresa («Nealis / FACSA» → FACSA). Si dan empresas distintas, son varios
       operadores y se decide en la bandeja.
    3. «X (Y)»: se prueba X y, si no resuelve, Y («AIGÜES DE L'HORTA (VEOLIA)» → Veolia;
       «Urbaser (limpieza viaria)» → Urbaser).
    """
    texto = (texto or "").strip()
    empresa, motivo = _por_texto_exacto(texto)
    if empresa or "ambiguo" in motivo or "varias empresas" in motivo:
        return ResolucionEmpresa(empresa, motivo)

    norm = normalizar_texto(texto)
    partes = [p for p in _SEPARADORES_OPERADOR.split(texto) if p.strip()]
    if norm.startswith("ute ") or len(partes) > 1:
        if len(partes) > 1:
            resueltas = [resolver_empresa(p).empresa for p in partes]
            if all(resueltas) and len({e.pk for e in resueltas}) == 1:
                return ResolucionEmpresa(resueltas[0])
        return ResolucionEmpresa(None, f"«{texto}» nombra varios operadores (UTE o lista)")

    m = _PARENTESIS.match(texto)
    if m:
        for parte in (m["fuera"], m["dentro"]):
            e, _ = _por_texto_exacto(parte.strip())
            if e:
                return ResolucionEmpresa(e)
    return ResolucionEmpresa(None, motivo)
