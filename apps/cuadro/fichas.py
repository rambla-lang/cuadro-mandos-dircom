"""Ficha de empresa gestora (RF-51, docs/05 §2)."""

from collections import Counter
from datetime import date, timedelta

from django.db.models import Q

from apps.digital.models import AuditoriaWeb, PerfilDigital
from apps.documentos.models import PercepcionInterna
from apps.entidades.models import Empresa
from apps.evidencias.enums import Alcance, CategoriaEvidencia, EstadoValidacion, Servicio
from apps.evidencias.models import Evidencia, PrestacionServicio
from apps.medios.models import MencionEmpresa

AVISO_MUNICIPIOS = (
    "Los recuentos reflejan municipios con alguna evidencia; el alcance puede ser distinto "
    "(abastecimiento o redes, recogida municipal, suministro energético o tratamiento consorcial)."
)
SIN_REDES = "Actividad no caracterizable con la evidencia pública disponible."


def _evidencias(empresa, categorias):
    return (
        Evidencia.objects.filter(empresas=empresa, categoria__in=categorias)
        .exclude(estado_validacion=EstadoValidacion.RECHAZADA)
        .select_related("fuente", "validado_por")
        .order_by("-fecha_publicacion", "-pk")
    )


def municipios_y_servicios(empresa):
    prestaciones = (
        PrestacionServicio.objects.filter(
            empresa=empresa, evidencias__estado_validacion=EstadoValidacion.VALIDADA
        )
        .distinct()
        .select_related("municipio")
        .order_by("servicio", "alcance", "municipio__nombre_oficial")
    )
    grupos: dict[tuple, list] = {}
    for p in prestaciones:
        grupos.setdefault((p.servicio, p.alcance), []).append(p)
    filas = []
    for (servicio, alcance), lista in grupos.items():
        filas.append(
            {
                "servicio": Servicio(servicio).label,
                "alcance": Alcance(alcance).label if alcance else "Alcance sin especificar",
                # CP-16: el suministro eléctrico no cuenta como servicio energético.
                "complementario": alcance == Alcance.SUMINISTRO_ELECTRICO,
                "municipios": sorted({p.municipio.nombre_oficial for p in lista}),
                "prestaciones": lista,
            }
        )
    por_servicio = Counter()
    for f in filas:
        if not f["complementario"]:
            por_servicio[f["servicio"]] += len(f["municipios"])
    return filas, dict(por_servicio)


def medios_principales(empresa, desde, hasta, n=5):
    atribuciones = MencionEmpresa.objects.filter(
        empresa=empresa,
        estado_validacion=EstadoValidacion.VALIDADA,
        mencion__pieza__fecha_publicacion__gte=desde,
        mencion__pieza__fecha_publicacion__lte=hasta,
        mencion__pieza__tipo__in=["prensa_digital", "prensa_impresa"],
    ).values_list("mencion__pieza_id", "mencion__pieza__medio__nombre")
    piezas = {}
    for pieza_id, medio in atribuciones:
        piezas[pieza_id] = medio or "Sin medio"
    return Counter(piezas.values()).most_common(n), len(piezas)


def redes(empresa):
    salida = []
    for perfil in PerfilDigital.objects.filter(empresa=empresa).exclude(red="web"):
        ultima = perfil.observaciones.first()
        salida.append({"perfil": perfil, "ultima": ultima})
    return salida


def ficha(empresa: Empresa, desde: date | None = None, hasta: date | None = None) -> dict:
    hasta = hasta or date.today()
    desde = desde or hasta - timedelta(days=365)
    filas_mun, por_servicio = municipios_y_servicios(empresa)
    medios, total_piezas = medios_principales(empresa, desde, hasta)
    eventos = _evidencias(empresa, [CategoriaEvidencia.EVENTO, CategoriaEvidencia.PREMIO])
    return {
        "empresa": empresa,
        "desde": desde,
        "hasta": hasta,
        "percepciones": PercepcionInterna.objects.filter(empresa=empresa).prefetch_related(
            "evidencias_relacionadas"
        ),
        "municipios": filas_mun,
        "por_servicio": por_servicio,
        "aviso_municipios": AVISO_MUNICIPIOS,
        "medios": medios,
        "total_piezas": total_piezas,
        "eventos": eventos,
        "grupos_interes": _evidencias(
            empresa, [CategoriaEvidencia.ALIANZA, CategoriaEvidencia.GRUPO_INTERES]
        ),
        "innovacion": _evidencias(empresa, [CategoriaEvidencia.INNOVACION_FINANCIACION]),
        "sostenibilidad": _evidencias(empresa, [CategoriaEvidencia.SOSTENIBILIDAD]),
        "redes": redes(empresa),
        "sin_redes": SIN_REDES,
        "web": AuditoriaWeb.objects.filter(empresa=empresa).first(),
        "otras_evidencias": Evidencia.objects.filter(empresas=empresa)
        .exclude(Q(estado_validacion=EstadoValidacion.RECHAZADA))
        .count(),
    }
