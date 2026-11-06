"""Visibilidad en medios (docs/05 §3). Unidad de recuento: la pieza.

- Solo piezas con vínculo territorial «si» (alguna de sus menciones) y con atribución validada.
- Una pieza compartida cuenta 1 en el total y 1 para cada empresa (CP-08): la suma por
  empresa puede superar el total.
- El sentimiento es el de Brandwatch, rotulado así.
- No se calcula audiencia ni valor publicitario.
- La concentración por medio se calcula sobre la prensa (digital e impresa): las redes
  sociales no son un medio.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date

from apps.evidencias.enums import EstadoValidacion

from .models import MencionEmpresa, Pieza


@dataclass
class Filtro:
    desde: date
    hasta: date
    solo_vinculo: bool = True
    incluir_propias: bool = False


def atribuciones(f: Filtro):
    qs = MencionEmpresa.objects.filter(
        estado_validacion=EstadoValidacion.VALIDADA,
        mencion__pieza__isnull=False,
        mencion__pieza__fecha_publicacion__gte=f.desde,
        mencion__pieza__fecha_publicacion__lte=f.hasta,
    )
    if not f.incluir_propias:
        qs = qs.filter(empresa__es_propia=False)
    return qs


def calcular(f: Filtro) -> dict:
    filas = list(
        atribuciones(f).values_list(
            "mencion__pieza_id", "empresa_id", "empresa__nombre", "mencion__sentimiento_fuente"
        )
    )
    piezas_ids = {p for p, *_ in filas}
    piezas = {
        p.pk: p
        for p in Pieza.objects.filter(pk__in=piezas_ids)
        .select_related("medio")
        .prefetch_related("menciones")
    }
    if f.solo_vinculo:
        piezas = {
            pk: p
            for pk, p in piezas.items()
            if any(m.vinculo_territorial == "si" for m in p.menciones.all())
        }
    por_empresa: dict[str, set] = defaultdict(set)
    tono: dict[str, Counter] = defaultdict(Counter)
    vistos = set()
    for pieza_id, _empresa_id, nombre, sentimiento in filas:
        if pieza_id not in piezas:
            continue
        por_empresa[nombre].add(pieza_id)
        if (pieza_id, nombre) not in vistos:
            vistos.add((pieza_id, nombre))
            tono[nombre][sentimiento or "sin dato"] += 1
    total = len(piezas)
    prensa = [
        p
        for p in piezas.values()
        if p.tipo in (Pieza.Tipo.PRENSA_DIGITAL, Pieza.Tipo.PRENSA_IMPRESA)
    ]
    medios = Counter(p.medio.nombre if p.medio else "Sin medio" for p in prensa)
    top3 = medios.most_common(3)
    meses = sorted(
        {p.fecha_publicacion.strftime("%Y-%m") for p in piezas.values() if p.fecha_publicacion}
    )
    if meses:
        a, m = map(int, meses[0].split("-"))
        fin = tuple(map(int, meses[-1].split("-")))
        meses = []
        while (a, m) <= fin:
            meses.append(f"{a:04d}-{m:02d}")
            a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    empresas = sorted(por_empresa, key=lambda n: (-len(por_empresa[n]), n))
    evolucion = {
        n: [
            sum(
                1
                for pid in por_empresa[n]
                if piezas[pid].fecha_publicacion
                and piezas[pid].fecha_publicacion.strftime("%Y-%m") == mes
            )
            for mes in meses
        ]
        for n in empresas
    }
    tipos = Counter(p.get_tipo_display() for p in piezas.values())
    total_por_mes = Counter(
        p.fecha_publicacion.strftime("%Y-%m") for p in piezas.values() if p.fecha_publicacion
    )
    return {
        "total": total,
        "suma_por_empresa": sum(len(v) for v in por_empresa.values()),
        "empresas": [
            {
                "nombre": n,
                "piezas": len(por_empresa[n]),
                "cuota": round(100 * len(por_empresa[n]) / total, 1) if total else 0,
                "medios": len({piezas[pid].medio_id for pid in por_empresa[n]}),
                "tono": dict(tono[n]),
            }
            for n in empresas
        ],
        "top_medios": top3,
        "piezas_prensa": len(prensa),
        "concentracion_top3": (
            round(100 * sum(n for _, n in top3) / len(prensa), 1) if prensa else None
        ),
        "medios_total": len(medios),
        "meses": meses,
        "evolucion": evolucion,
        "tipos": dict(tipos),
        "total_por_mes": {m: total_por_mes.get(m, 0) for m in meses},
    }
