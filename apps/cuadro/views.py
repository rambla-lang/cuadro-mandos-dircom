import csv
import io

from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.contratacion.models import Expediente
from apps.entidades.models import Empresa
from apps.evidencias.enums import ALCANCES_POR_SERVICIO, EstadoValidacion, Servicio
from apps.evidencias.models import PrestacionServicio
from apps.territorio.models import Municipio, Provincia

from . import services

ATRIBUCION_LIMITES = (
    "Límites municipales: obra derivada del servicio WFS «Unidades administrativas» del IGN, "
    "CC BY 4.0 ign.es (descarga del 06/11/2026). Códigos y nombres: INE, a 1 de enero de 2026."
)


def mapa(request):
    filtro = services.Filtro.desde_get(request.GET)
    datos = services.datos_mapa(filtro)
    municipios = datos["municipios"]
    servicio = Servicio(filtro.servicio)
    return render(
        request,
        "cuadro/mapa.html",
        {
            "filtro": filtro,
            "servicios": Servicio.choices,
            "alcances": [(a, a.label) for a in ALCANCES_POR_SERVICIO[servicio]],
            "provincias": Provincia.objects.all(),
            "empresas": Empresa.objects.filter(activa=True),
            "resaltadas": datos["resaltadas"],
            "leyenda": datos["leyenda"],
            "ind": services.indicadores(municipios),
            "datos_json": {m["codigo"]: m for m in municipios},
            "tabla": services.tabla_equivalente(filtro.provincia, filtro.incluir_borradores),
            "atribucion": ATRIBUCION_LIMITES,
            "servicio_label": servicio.label,
            "query": request.GET.urlencode(),
        },
    )


def municipio_panel(request, codigo):
    municipio = get_object_or_404(Municipio.objects.select_related("provincia"), codigo_ine=codigo)
    prestaciones = (
        PrestacionServicio.objects.filter(municipio=municipio)
        .select_related("empresa")
        .prefetch_related("evidencias__fuente", "evidencias__validado_por")
        .order_by("servicio", "alcance")
    )
    filas = []
    for p in prestaciones:
        evidencias = [
            e for e in p.evidencias.all() if e.estado_validacion != EstadoValidacion.RECHAZADA
        ]
        if not evidencias:
            continue
        filas.append(
            {
                "p": p,
                "evidencias": evidencias,
                "borrador": all(
                    e.estado_validacion != EstadoValidacion.VALIDADA for e in evidencias
                ),
            }
        )
    expedientes = (
        Expediente.objects.filter(organo__municipio=municipio)
        .exclude(servicio_clasificado="")
        .prefetch_related("adjudicaciones__empresa")
        .order_by("-fecha_publicacion", "-pk")[:15]
    )
    total_expedientes = Expediente.objects.filter(organo__municipio=municipio).count()
    plantilla = "cuadro/_panel_municipio.html" if request.htmx else "cuadro/municipio.html"
    return render(
        request,
        plantilla,
        {
            "municipio": municipio,
            "filas": filas,
            "expedientes": expedientes,
            "total_expedientes": total_expedientes,
        },
    )


def exportar_tabla(request, formato):
    if formato not in ("csv", "xlsx"):
        raise Http404("Formato no admitido.")
    filtro = services.Filtro.desde_get(request.GET)
    filas = services.tabla_equivalente(filtro.provincia, filtro.incluir_borradores)
    cabecera = ["Código INE", "Municipio", "Provincia"]
    for s in services.SERVICIOS_TABLA:
        cabecera += [f"{s.label}: operador", f"{s.label}: nivel"]
    datos = [
        [f["codigo"], f["nombre"], f["provincia"]]
        + [v for s in services.SERVICIOS_TABLA for v in (f[s]["texto"], f[s]["nivel"])]
        for f in filas
    ]
    sello = timezone.localtime().strftime("%Y%m%d")
    notas = [
        f"Generado el {timezone.localtime():%d/%m/%Y %H:%M} desde el cuadro de mandos DIRCOM.",
        "«No localizado» significa que no hay evidencia registrada, no que no exista servicio.",
        "Solo evidencias validadas"
        + (" y borradores (marcados [borrador])." if filtro.incluir_borradores else "."),
        "Energía excluye el suministro eléctrico (comercializadora), que es dato complementario.",
        ATRIBUCION_LIMITES,
    ]
    if formato == "csv":
        salida = io.StringIO()
        escritor = csv.writer(salida)
        escritor.writerow(cabecera)
        escritor.writerows(datos)
        respuesta = HttpResponse("﻿" + salida.getvalue(), content_type="text/csv; charset=utf-8")
        respuesta["Content-Disposition"] = f'attachment; filename="mapa_municipal_{sello}.csv"'
        return respuesta
    import openpyxl

    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.title = "Municipios"
    hoja.append(cabecera)
    for fila in datos:
        hoja.append(fila)
    hoja_notas = libro.create_sheet("Notas")
    for n in notas:
        hoja_notas.append([n])
    salida = io.BytesIO()
    libro.save(salida)
    respuesta = HttpResponse(
        salida.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    respuesta["Content-Disposition"] = f'attachment; filename="mapa_municipal_{sello}.xlsx"'
    return respuesta


def competidores(request):
    from django.db.models import Count, Q

    from apps.evidencias.enums import EstadoValidacion

    lista = (
        Empresa.objects.filter(activa=True)
        .annotate(
            n_prestaciones=Count(
                "prestaciones",
                filter=Q(prestaciones__evidencias__estado_validacion=EstadoValidacion.VALIDADA),
                distinct=True,
            ),
            n_menciones=Count(
                "menciones",
                filter=Q(menciones__estado_validacion=EstadoValidacion.VALIDADA),
                distinct=True,
            ),
            n_adjudicaciones=Count("adjudicaciones", distinct=True),
        )
        .order_by("-es_competidor_seguido", "es_propia", "nombre")
    )
    return render(request, "cuadro/competidores.html", {"empresas": lista})


def ficha_competidor(request, pk):
    from datetime import date

    from . import fichas

    empresa = get_object_or_404(Empresa, pk=pk)
    try:
        desde = date.fromisoformat(request.GET["desde"]) if request.GET.get("desde") else None
        hasta = date.fromisoformat(request.GET["hasta"]) if request.GET.get("hasta") else None
    except ValueError:
        desde = hasta = None
    return render(request, "cuadro/ficha.html", fichas.ficha(empresa, desde, hasta))
