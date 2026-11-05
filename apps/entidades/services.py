"""Carga inicial de competidores (docs/00) como datos editables (RF-10, RF-11, RF-12)."""

import json
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
