"""Métricas e evidencias de partida de un informe, calculadas en código (docs/05 §4, paso 2).

Cada métrica lleva un identificador `M<n>` que el texto cita y que el anexo explica con su
definición y el enlace a la lista de evidencias o piezas de la aplicación."""

from collections import Counter
from datetime import date

from django.db.models import Count, Q
from django.urls import reverse

from apps.cuadro import fichas
from apps.entidades.models import Empresa
from apps.evidencias.enums import EstadoValidacion
from apps.evidencias.models import MARCA_VALIDACION, Evidencia
from apps.medios import metricas as m_medios

MAX_EVIDENCIAS_POR_EMPRESA = 40


def _formato(valor) -> str:
    if isinstance(valor, float):
        return f"{valor:.1f}".replace(".", ",")
    return str(valor)


class Registro:
    def __init__(self):
        self.metricas: list[dict] = []

    def m(self, clave: str, valor, definicion: str, enlace: str = "") -> str:
        ident = f"M{len(self.metricas) + 1}"
        self.metricas.append(
            {
                "id": ident,
                "clave": clave,
                "valor": valor,
                "texto": _formato(valor),
                "definicion": definicion,
                "enlace": enlace,
            }
        )
        return ident


def _evidencia(e: Evidencia) -> dict:
    return {
        "codigo": e.codigo,
        "fecha": e.fecha_publicacion.isoformat() if e.fecha_publicacion else "",
        "fuente": e.fuente.nombre,
        "titulo": e.titulo,
        "extracto": e.extracto[:600],
        "url": e.url_origen,
        "nivel": e.get_nivel_display(),
        "validacion": MARCA_VALIDACION if e.validada_por_dircom else "",
        "categoria": e.get_categoria_display(),
        "limites": e.tratamiento_limites,
        "empresas": [x.nombre for x in e.empresas.all()],
    }


def calcular(empresas: list[Empresa], desde: date, hasta: date) -> dict:
    r = Registro()
    medios = m_medios.calcular(m_medios.Filtro(desde, hasta))
    por_nombre = {x["nombre"]: x for x in medios["empresas"]}
    q_medios = f"?desde={desde:%Y-%m-%d}&hasta={hasta:%Y-%m-%d}"
    total_piezas = r.m(
        "piezas_total",
        medios["total"],
        "Piezas distintas con vínculo con la CV y atribución validada en el periodo "
        "(todas las empresas seguidas)",
        reverse("piezas") + q_medios,
    )
    resultado = []
    evidencias_usadas = set()
    for e in empresas:
        f = fichas.ficha(e, desde, hasta)
        datos_medios = por_nombre.get(e.nombre, {"piezas": 0, "cuota": 0, "medios": 0})
        ids = {
            "piezas": r.m(
                f"piezas:{e.pk}",
                datos_medios["piezas"],
                f"Piezas de {e.nombre} en el periodo",
                reverse("piezas") + q_medios + f"&empresa={e.nombre}",
            ),
            "cuota": r.m(
                f"cuota:{e.pk}",
                float(datos_medios["cuota"]),
                f"Cuota de piezas de {e.nombre} (%; las compartidas cuentan para cada empresa)",
                reverse("visibilidad") + q_medios,
            ),
            "medios": r.m(
                f"medios:{e.pk}",
                datos_medios["medios"],
                f"Medios distintos con piezas de {e.nombre}",
            ),
            "municipios_total": r.m(
                f"municipios_total:{e.pk}",
                len({m for fila in f["municipios"] for m in fila["municipios"]}),
                f"Municipios distintos con algún servicio validado gestionado por {e.nombre}",
                reverse("ficha", args=[e.pk]) + "#bloque1",
            ),
        }
        municipios = {}
        for servicio, n in f["por_servicio"].items():
            municipios[servicio] = r.m(
                f"municipios:{e.pk}:{servicio}",
                n,
                f"Municipios con alguna evidencia validada de {servicio.lower()} de {e.nombre}",
                reverse("ficha", args=[e.pk]) + "#bloque1",
            )
        evs = list(
            Evidencia.objects.filter(empresas=e, estado_validacion=EstadoValidacion.VALIDADA)
            .select_related("fuente")
            .prefetch_related("empresas")
            .filter(
                Q(fecha_publicacion__isnull=True)
                | Q(fecha_publicacion__gte=desde, fecha_publicacion__lte=hasta)
            )
            .order_by("-fecha_publicacion")[:MAX_EVIDENCIAS_POR_EMPRESA]
        )
        evidencias_usadas.update(x.pk for x in evs)
        resultado.append(
            {
                "id": e.pk,
                "nombre": e.nombre,
                "metricas": ids,
                "municipios": municipios,
                "top_medios": f["medios"],
                "percepciones": [p.texto for p in f["percepciones"]],
                "evidencias": [_evidencia(x) for x in evs],
                "redes": [
                    {
                        "red": x["perfil"].get_red_display(),
                        "seguidores": None if not x["ultima"] else x["ultima"].seguidores,
                        "fecha": x["ultima"].fecha_observacion.isoformat() if x["ultima"] else None,
                    }
                    for x in f["redes"]
                ],
            }
        )
    base = Counter(
        Evidencia.objects.filter(pk__in=evidencias_usadas).values_list("categoria", flat=True)
    )
    return {
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "metricas": r.metricas,
        "total_piezas": total_piezas,
        "concentracion_top3": medios["concentracion_top3"],
        "empresas": resultado,
        "base_documental": dict(base),
        "evidencias_ids": sorted(evidencias_usadas),
        "n_evidencias_validadas": Evidencia.objects.filter(
            estado_validacion=EstadoValidacion.VALIDADA
        ).count(),
        "por_categoria": dict(
            Evidencia.objects.filter(estado_validacion=EstadoValidacion.VALIDADA)
            .values_list("categoria")
            .annotate(n=Count("pk"))
        ),
    }
