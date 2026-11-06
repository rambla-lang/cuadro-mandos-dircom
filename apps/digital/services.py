"""Importación de observaciones digitales desde CSV (docs/04 §8). CP-12."""

import csv
import io
from dataclasses import dataclass, field
from datetime import date

from django.db import transaction

from apps.entidades.services import resolver_empresa
from apps.nucleo.services import registrar_auditoria

from .models import ObservacionDigital, PerfilDigital

COLUMNAS = [
    "perfil_url",
    "red",
    "fecha_observacion",
    "seguidores",
    "publicaciones_observadas",
    "periodo_observado",
    "historico_suficiente",
    "notas",
]
NO_VISIBLE = {"", "no visible", "no_visible", "n/v", "nv", "-", "—"}


def entero_o_nulo(valor: str) -> int | None:
    """«no visible» o vacío → None (nunca 0). «12.300» → 12300."""
    v = (valor or "").strip().lower()
    if v in NO_VISIBLE:
        return None
    v = v.replace(".", "").replace(" ", "")
    if not v.isdigit():
        raise ValueError(f"«{valor}» no es un número ni «no visible»")
    return int(v)


@dataclass
class Resultado:
    nuevas: int = 0
    actualizadas: int = 0
    errores: list = field(default_factory=list)


@transaction.atomic
def importar_csv(contenido: bytes, usuario) -> Resultado:
    """Columnas de docs/04 §8 y una opcional `empresa` para dar de alta el perfil si no existe."""
    texto = contenido.decode("utf-8-sig", errors="replace")
    dialecto = csv.Sniffer().sniff(texto[:2048], delimiters=",;\t") if texto.strip() else csv.excel
    filas = list(csv.DictReader(io.StringIO(texto), dialect=dialecto))
    res = Resultado()
    faltan = [
        c
        for c in ("perfil_url", "fecha_observacion", "seguidores")
        if c not in (filas[0] if filas else {})
    ]
    if faltan:
        res.errores.append(f"Faltan columnas: {', '.join(faltan)}.")
        return res
    for n, f in enumerate(filas, start=2):
        try:
            perfil = PerfilDigital.objects.filter(url=f["perfil_url"].strip()).first()
            if perfil is None:
                empresa = (
                    resolver_empresa(f.get("empresa", "")).empresa if f.get("empresa") else None
                )
                red = (f.get("red") or "").strip().lower()
                if empresa is None or red not in PerfilDigital.Red.values:
                    raise ValueError(
                        "perfil desconocido: añade las columnas «empresa» y «red» o créalo antes"
                    )
                perfil = PerfilDigital.objects.create(
                    empresa=empresa, red=red, url=f["perfil_url"].strip()
                )
            fecha = date.fromisoformat(f["fecha_observacion"].strip())
            _, creada = ObservacionDigital.objects.update_or_create(
                perfil=perfil,
                fecha_observacion=fecha,
                defaults={
                    "seguidores": entero_o_nulo(f.get("seguidores", "")),
                    "publicaciones_observadas": entero_o_nulo(
                        f.get("publicaciones_observadas", "")
                    ),
                    "periodo_observado": (f.get("periodo_observado") or "")[:100],
                    "historico_suficiente": (f.get("historico_suficiente") or "").strip().lower()
                    in ("si", "sí", "true", "1", "x"),
                    "notas": f.get("notas") or "",
                    "creado_por": usuario,
                },
            )
            res.nuevas += creada
            res.actualizadas += not creada
        except (ValueError, KeyError) as e:
            res.errores.append(f"Fila {n}: {e}")
    registrar_auditoria(
        usuario,
        "importacion.digital",
        None,
        despues={"nuevas": res.nuevas, "errores": len(res.errores)},
    )
    return res
