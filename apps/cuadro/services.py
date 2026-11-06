"""Mapa municipal (RF-50, docs/05 §1): datos por municipio, indicadores y tabla equivalente.

Reglas que no se negocian (CLAUDE.md, docs/05):
- Un municipio sin registro es «No localizado», nunca 0 ni «sin servicio» (CP-07).
- Por defecto solo cuentan las prestaciones con alguna evidencia validada; los borradores se
  muestran solo si se piden y siempre marcados.
- El suministro eléctrico (comercializadora) no cuenta como servicio energético salvo que se
  pida ese alcance expresamente (docs/03).
- Se cuentan municipios con alguna evidencia, no población ni alcance real.
"""

from collections import Counter
from dataclasses import dataclass, field

from django.db.models import Count, Q

from apps.entidades.models import Empresa
from apps.evidencias.enums import Alcance, EstadoValidacion, Gestion, NivelEvidencia, Servicio
from apps.evidencias.models import ORDEN_NIVEL, PrestacionServicio, mejor_nivel
from apps.territorio.models import Municipio

# Escala ordinal de un solo tono (azul 650 → 250) validada con scripts/validar_paleta.py
# --ordinal; «No localizado» en gris neutro (docs/07, docs/05 §1).
COLOR_NIVEL = {
    NivelEvidencia.OFICIAL: "#104281",
    NivelEvidencia.PRENSA: "#256abf",
    NivelEvidencia.EMPRESA: "#5598e7",
    NivelEvidencia.PARCIAL: "#86b6ef",
    NivelEvidencia.NO_LOCALIZADO: "#d9d8d2",
}
# Solo tres colores de identidad: en un mapa todos los municipios pueden ser vecinos y la
# paleta categórica solo supera la validación «todos los pares» con los tres primeros
# (docs/07 §3, resultado en docs/07).
COLORES_OPERADOR = ["#2a78d6", "#eb6834", "#1baf7a"]
COLOR_OTROS = "#9a9993"
COLOR_VARIOS = "#52514e"
COLOR_NO_LOCALIZADO = COLOR_NIVEL[NivelEvidencia.NO_LOCALIZADO]
MAX_RESALTADOS = len(COLORES_OPERADOR)
SERVICIOS_TABLA = (Servicio.AGUA, Servicio.RESIDUOS, Servicio.ENERGIA)


@dataclass
class Filtro:
    servicio: str = Servicio.AGUA
    alcance: str = ""
    provincia: str = ""
    incluir_borradores: bool = False
    modo: str = "nivel"  # nivel | operador
    resaltar: list[int] = field(default_factory=list)

    @classmethod
    def desde_get(cls, get) -> "Filtro":
        servicio = get.get("servicio") if get.get("servicio") in Servicio.values else "agua"
        alcance = get.get("alcance", "")
        if alcance and alcance not in Alcance.values:
            alcance = ""
        resaltar = [int(x) for x in get.getlist("resaltar") if x.isdigit()][:MAX_RESALTADOS]
        return cls(
            servicio=servicio,
            alcance=alcance,
            provincia=get.get("provincia", ""),
            incluir_borradores=get.get("borradores") == "1",
            modo="operador" if get.get("modo") == "operador" else "nivel",
            resaltar=resaltar,
        )


def prestaciones(servicio: str, alcance: str = "", provincia: str = "", borradores=False):
    qs = PrestacionServicio.objects.filter(servicio=servicio).annotate(
        n_validadas=Count(
            "evidencias", filter=Q(evidencias__estado_validacion=EstadoValidacion.VALIDADA)
        ),
        n_vivas=Count(
            "evidencias", filter=~Q(evidencias__estado_validacion=EstadoValidacion.RECHAZADA)
        ),
    )
    qs = qs.filter(n_vivas__gt=0)
    if not borradores:
        qs = qs.filter(n_validadas__gt=0)
    if alcance:
        qs = qs.filter(alcance=alcance)
    elif servicio == Servicio.ENERGIA:
        qs = qs.exclude(alcance=Alcance.SUMINISTRO_ELECTRICO)
    if provincia:
        qs = qs.filter(municipio__provincia__codigo_ine=provincia)
    return qs.select_related("empresa", "municipio")


def _municipios(provincia: str):
    qs = Municipio.objects.select_related("provincia").order_by("nombre_oficial")
    return qs.filter(provincia__codigo_ine=provincia) if provincia else qs


def _operador(p) -> dict:
    return {
        "nombre": p.nombre_operador,
        "empresa_id": p.empresa_id,
        "clave": f"e{p.empresa_id}" if p.empresa_id else f"t:{p.operador_normalizado or p.gestion}",
        "gestion": p.get_gestion_display(),
        "alcance": p.get_alcance_display() or "Alcance sin especificar",
        "anio": p.anio_referencia,
        "nivel": p.nivel,
        "nivel_label": NivelEvidencia(p.nivel).label,
        "borrador": p.n_validadas == 0,
        "localizado": p.gestion != Gestion.NO_LOCALIZADA,
    }


def operadores_destacados(servicio: str, alcance: str = "") -> list[Empresa]:
    """Los tres operadores con más municipios (evidencias validadas, toda la comunidad).

    No dependen del filtro de provincia ni de los borradores, para que filtrar no cambie los
    colores (el color sigue a la empresa, docs/07)."""
    municipios_por_empresa: dict[int, set] = {}
    for empresa_id, municipio_id in (
        prestaciones(servicio, alcance)
        .filter(empresa__isnull=False)
        .values_list("empresa_id", "municipio_id")
    ):
        municipios_por_empresa.setdefault(empresa_id, set()).add(municipio_id)
    conteo = {e: len(m) for e, m in municipios_por_empresa.items()}
    ids = [i for i, _ in sorted(conteo.items(), key=lambda x: (-x[1], x[0]))[:MAX_RESALTADOS]]
    empresas = {e.pk: e for e in Empresa.objects.filter(pk__in=ids)}
    return [empresas[i] for i in ids]


def datos_mapa(filtro: Filtro) -> dict:
    """Un registro por municipio del filtro, con su categoría de color en cada modo."""
    por_municipio: dict[int, list] = {}
    for p in prestaciones(
        filtro.servicio, filtro.alcance, filtro.provincia, filtro.incluir_borradores
    ):
        por_municipio.setdefault(p.municipio_id, []).append(_operador(p))

    resaltadas = (
        list(Empresa.objects.filter(pk__in=filtro.resaltar))
        if filtro.resaltar
        else operadores_destacados(filtro.servicio, filtro.alcance)
    )
    if filtro.resaltar:
        orden = {pk: i for i, pk in enumerate(filtro.resaltar)}
        resaltadas.sort(key=lambda e: orden[e.pk])
    color_empresa = {e.pk: COLORES_OPERADOR[i] for i, e in enumerate(resaltadas)}

    municipios = []
    for m in _municipios(filtro.provincia):
        operadores = sorted(
            por_municipio.get(m.pk, []), key=lambda o: (-ORDEN_NIVEL[o["nivel"]], o["nombre"])
        )
        localizados = [o for o in operadores if o["localizado"]]
        nivel = mejor_nivel([o["nivel"] for o in localizados]) or NivelEvidencia.NO_LOCALIZADO
        claves = {o["clave"] for o in localizados}
        if not claves:
            categoria, color_op = "no_localizado", COLOR_NO_LOCALIZADO
        elif len(claves) > 1:
            categoria, color_op = "varios", COLOR_VARIOS
        else:
            empresa_id = localizados[0]["empresa_id"]
            if empresa_id in color_empresa:
                categoria, color_op = f"e{empresa_id}", color_empresa[empresa_id]
            else:
                categoria, color_op = "otros", COLOR_OTROS
        municipios.append(
            {
                "codigo": m.codigo_ine,
                "nombre": m.nombre_oficial,
                "provincia": m.provincia.nombre,
                "nivel": nivel,
                "nivel_label": NivelEvidencia(nivel).label,
                "color_nivel": COLOR_NIVEL[nivel],
                "categoria": categoria,
                "color_operador": color_op,
                "operadores": operadores,
                "solo_borradores": bool(localizados) and all(o["borrador"] for o in localizados),
            }
        )

    leyenda_operador = [
        {"etiqueta": e.nombre, "color": color_empresa[e.pk]} for e in resaltadas
    ] + [
        {"etiqueta": "Otros operadores", "color": COLOR_OTROS},
        {"etiqueta": "Varios operadores", "color": COLOR_VARIOS},
        {"etiqueta": "No localizado", "color": COLOR_NO_LOCALIZADO},
    ]
    leyenda_nivel = [{"etiqueta": n.label, "color": COLOR_NIVEL[n]} for n in NivelEvidencia]
    return {
        "municipios": municipios,
        "resaltadas": resaltadas,
        "leyenda": leyenda_operador if filtro.modo == "operador" else leyenda_nivel,
    }


def indicadores(municipios: list[dict]) -> dict:
    total = len(municipios)
    con_operador = sum(1 for m in municipios if m["nivel"] != NivelEvidencia.NO_LOCALIZADO)
    por_nivel = Counter(m["nivel"] for m in municipios)
    top = Counter()
    for m in municipios:
        for nombre in {o["nombre"] for o in m["operadores"] if o["localizado"]}:
            top[nombre] += 1
    return {
        "total": total,
        "con_operador": con_operador,
        "pct_con_operador": round(100 * con_operador / total, 1) if total else None,
        "por_nivel": [
            {
                "nivel": n,
                "etiqueta": n.label,
                "color": COLOR_NIVEL[n],
                "n": por_nivel.get(n, 0),
                "pct": round(100 * por_nivel.get(n, 0) / total, 1) if total else 0,
            }
            for n in NivelEvidencia
        ],
        "top_operadores": top.most_common(8),
    }


def tabla_equivalente(provincia: str = "", borradores: bool = False) -> list[dict]:
    """Una fila por municipio y una columna por servicio, como la tabla de Veolia."""
    celdas: dict[tuple, list] = {}
    for servicio in SERVICIOS_TABLA:
        for p in prestaciones(servicio, "", provincia, borradores):
            celdas.setdefault((p.municipio_id, servicio), []).append(_operador(p))
    filas = []
    for m in _municipios(provincia):
        fila = {"codigo": m.codigo_ine, "nombre": m.nombre_oficial, "provincia": m.provincia.nombre}
        for servicio in SERVICIOS_TABLA:
            ops = [o for o in celdas.get((m.pk, servicio), []) if o["localizado"]]
            if not ops:
                fila[servicio] = {"texto": "No localizado", "nivel": "No localizado"}
                continue
            ops.sort(key=lambda o: (-ORDEN_NIVEL[o["nivel"]], o["nombre"]))
            textos = [f"{o['nombre']}{' [borrador]' if o['borrador'] else ''}" for o in ops]
            nivel = mejor_nivel([o["nivel"] for o in ops])
            fila[servicio] = {"texto": "; ".join(textos), "nivel": NivelEvidencia(nivel).label}
        filas.append(fila)
    return filas
