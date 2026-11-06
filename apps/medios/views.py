"""Medios: visibilidad (docs/05 §3), piezas, menciones e importación (docs/04 §4-5)."""

from datetime import date, timedelta

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.documentos.models import Documento
from apps.evidencias.enums import EstadoValidacion, VinculoTerritorial
from apps.nucleo.roles import Rol, rol_requerido, tiene_rol

from . import metricas
from . import services_revision as srv
from .clipping import subir_recorte
from .forms import AtribuirForm, SubirBrandwatchForm, SubirRecortesForm, VinculoForm
from .importers.brandwatch import FormatoBrandwatchError, importar_brandwatch
from .models import Mencion, MencionEmpresa, Pieza

ROLES = (Rol.ADMINISTRADOR, Rol.ANALISTA)


def _periodo(g):
    """Periodo por defecto: 12 meses móviles hasta hoy (propuesta de P-10)."""
    hoy = date.today()
    try:
        hasta = date.fromisoformat(g.get("hasta", "")) if g.get("hasta") else hoy
        desde = (
            date.fromisoformat(g.get("desde", ""))
            if g.get("desde")
            else hasta - timedelta(days=365)
        )
    except ValueError:
        hasta, desde = hoy, hoy - timedelta(days=365)
    return desde, hasta


def visibilidad(request):
    desde, hasta = _periodo(request.GET)
    f = metricas.Filtro(
        desde=desde,
        hasta=hasta,
        solo_vinculo=request.GET.get("vinculo", "si") == "si",
        incluir_propias=request.GET.get("propias") == "1",
    )
    datos = metricas.calcular(f)
    return render(
        request,
        "medios/visibilidad.html",
        {
            "d": datos,
            "f": f,
            "query": request.GET.urlencode(),
            "pendientes_lectura": Documento.objects.filter(lectura="pendiente_ia").count(),
        },
    )


def piezas(request):
    g = request.GET
    desde, hasta = _periodo(g)
    qs = Pieza.objects.filter(fecha_publicacion__gte=desde, fecha_publicacion__lte=hasta)
    validadas = Q(menciones__atribuciones__estado_validacion=EstadoValidacion.VALIDADA)
    if g.get("empresa"):
        qs = qs.filter(validadas, menciones__atribuciones__empresa__nombre=g["empresa"])
    if g.get("medio"):
        qs = qs.filter(medio__nombre=g["medio"])
    if g.get("mes"):
        try:
            a, m = map(int, g["mes"].split("-"))
            qs = qs.filter(fecha_publicacion__year=a, fecha_publicacion__month=m)
        except ValueError:
            pass
    if g.get("vinculo", "si") == "si":
        qs = qs.filter(menciones__vinculo_territorial="si")
    if g.get("q"):
        qs = qs.filter(titulo__icontains=g["q"])
    qs = qs.distinct().select_related("medio").prefetch_related("menciones__atribuciones__empresa")
    pagina = Paginator(qs, 50).get_page(g.get("pagina"))
    filtros = g.copy()
    filtros.pop("pagina", None)
    return render(
        request,
        "medios/piezas.html",
        {"pagina": pagina, "g": g, "desde": desde, "hasta": hasta, "filtros": filtros.urlencode()},
    )


def menciones(request):
    g = request.GET
    qs = Mencion.objects.select_related("medio").prefetch_related("atribuciones__empresa")
    if g.get("sin_atribuir"):
        qs = qs.exclude(atribuciones__estado_validacion=EstadoValidacion.VALIDADA)
    if g.get("vinculo") in VinculoTerritorial.values:
        qs = qs.filter(vinculo_territorial=g["vinculo"])
    if g.get("origen"):
        qs = qs.filter(origen=g["origen"])
    if g.get("q"):
        qs = qs.filter(Q(titulo__icontains=g["q"]) | Q(extracto__icontains=g["q"]))
    pagina = Paginator(qs.distinct(), 50).get_page(g.get("pagina"))
    filtros = g.copy()
    filtros.pop("pagina", None)
    return render(
        request, "medios/menciones.html", {"pagina": pagina, "g": g, "filtros": filtros.urlencode()}
    )


@require_http_methods(["GET", "POST"])
def mencion(request, pk):
    m = get_object_or_404(Mencion.objects.select_related("medio", "pieza", "documento"), pk=pk)
    puede = tiene_rol(request.user, *ROLES)
    if request.method == "POST":
        if not puede:
            return render(request, "403.html", status=403)
        accion = request.POST.get("accion")
        if accion == "atribuir":
            form = AtribuirForm(request.POST)
            if form.is_valid():
                srv.atribuir_manual(m, form.cleaned_data["empresa"], request.user)
        elif accion == "quitar":
            me = get_object_or_404(MencionEmpresa, pk=request.POST.get("atribucion"), mencion=m)
            srv.quitar_atribucion(me, request.user)
        elif accion == "vinculo":
            form = VinculoForm(request.POST)
            if form.is_valid():
                srv.fijar_vinculo(
                    m, form.cleaned_data["vinculo"], request.user, form.cleaned_data["comentario"]
                )
        messages.success(request, "Guardado.")
        return redirect("mencion", pk=m.pk)
    return render(
        request,
        "medios/mencion.html",
        {
            "m": m,
            "atribuciones": m.atribuciones.select_related("empresa"),
            "puede": puede,
            "form_atribuir": AtribuirForm(),
            "form_vinculo": VinculoForm(initial={"vinculo": m.vinculo_territorial}),
            "otras": Mencion.objects.filter(pieza=m.pieza).exclude(pk=m.pk) if m.pieza_id else [],
        },
    )


@rol_requerido(*ROLES)
@require_http_methods(["GET", "POST"])
def importar_brandwatch_vista(request):
    form = SubirBrandwatchForm(request.POST or None, request.FILES or None)
    resultados = []
    if request.method == "POST" and form.is_valid():
        for archivo in form.cleaned_data["archivos"]:
            try:
                r = importar_brandwatch(archivo.read(), archivo.name, request.user)
                resultados.append((archivo.name, r, None))
            except FormatoBrandwatchError as e:
                resultados.append((archivo.name, None, str(e)))
    return render(
        request, "medios/importar_brandwatch.html", {"form": form, "resultados": resultados}
    )


@rol_requerido(*ROLES)
@require_http_methods(["GET", "POST"])
def importar_recortes(request):
    form = SubirRecortesForm(request.POST or None, request.FILES or None)
    resultados = []
    if request.method == "POST" and form.is_valid():
        for archivo in form.cleaned_data["archivos"]:
            r = subir_recorte(
                archivo.read(), archivo.name, request.user, form.cleaned_data["empresa"]
            )
            resultados.append(r)
    documentos = Documento.objects.filter(tipo="recorte").select_related("empresa_propuesta")[:50]
    return render(
        request,
        "medios/importar_recortes.html",
        {"form": form, "resultados": resultados, "documentos": documentos},
    )
