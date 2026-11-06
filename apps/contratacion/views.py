"""Contratación: buscador de expedientes, detalle y «Actualizar contratación» (ADR-007/008)."""

from datetime import date, timedelta

from django import forms
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Max, Min, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.evidencias.enums import Servicio
from apps.nucleo.models import TrabajoIngesta
from apps.nucleo.roles import Rol, rol_requerido
from apps.nucleo.trabajos import lanzar_ejecutor
from apps.territorio.models import Provincia

from .models import Expediente, FuenteContrato
from .trabajos import TIPO_PLACSP, TIPO_TED

ROLES_IMPORTAR = (Rol.ADMINISTRADOR, Rol.ANALISTA)


def expedientes(request):
    g = request.GET
    qs = Expediente.objects.select_related("organo__municipio").prefetch_related(
        "adjudicaciones__empresa"
    )
    if g.get("servicio") == "sin":
        qs = qs.filter(servicio_clasificado="")
    elif g.get("servicio") in Servicio.values:
        qs = qs.filter(servicio_clasificado=g["servicio"])
    elif not g.get("servicio"):
        qs = qs.exclude(servicio_clasificado="")
    if g.get("fuente") in FuenteContrato.values:
        qs = qs.filter(fuente=g["fuente"])
    if g.get("provincia"):
        qs = qs.filter(organo__municipio__provincia__codigo_ine=g["provincia"])
    if g.get("municipio"):
        qs = qs.filter(organo__municipio__codigo_ine=g["municipio"])
    if g.get("q"):
        qs = qs.filter(
            Q(objeto__icontains=g["q"])
            | Q(numero_expediente__icontains=g["q"])
            | Q(organo__nombre__icontains=g["q"])
            | Q(adjudicaciones__adjudicatario_texto__icontains=g["q"])
        ).distinct()
    rango = Expediente.objects.aggregate(
        desde=Min("fecha_publicacion"), hasta=Max("fecha_publicacion")
    )
    pagina = Paginator(qs, 50).get_page(g.get("pagina"))
    filtros = g.copy()
    filtros.pop("pagina", None)
    return render(
        request,
        "contratacion/expedientes.html",
        {
            "pagina": pagina,
            "servicios": Servicio.choices,
            "fuentes": FuenteContrato.choices,
            "provincias": Provincia.objects.all(),
            "g": g,
            "filtros": filtros.urlencode(),
            "rango": rango,
            "ultimo_trabajo": TrabajoIngesta.objects.filter(estado="terminado").first(),
        },
    )


def expediente(request, pk):
    exp = get_object_or_404(
        Expediente.objects.select_related("organo__municipio", "lote_importacion"), pk=pk
    )
    return render(
        request,
        "contratacion/expediente.html",
        {"e": exp, "adjudicaciones": exp.adjudicaciones.select_related("empresa", "lote")},
    )


class ActualizarForm(forms.Form):
    ted = forms.BooleanField(label="TED (avisos europeos)", required=False, initial=True)
    ted_desde = forms.DateField(label="TED desde", widget=forms.DateInput(attrs={"type": "date"}))
    ted_hasta = forms.DateField(label="TED hasta", widget=forms.DateInput(attrs={"type": "date"}))
    placsp = forms.BooleanField(
        label="PLACSP: ZIP mensual de perfiles de contratante (unos 200 MB; de 20 a 30 minutos)",
        required=False,
    )
    placsp_mes = forms.ChoiceField(label="Mes de PLACSP")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        hoy = date.today()
        actual = hoy.replace(day=1)
        anterior = (actual - timedelta(days=1)).replace(day=1)
        self.fields["placsp_mes"].choices = [
            (f"{m:%Y%m}", f"{m:%m/%Y}") for m in (actual, anterior)
        ]
        self.fields["ted_desde"].initial = hoy - timedelta(days=30)
        self.fields["ted_hasta"].initial = hoy

    def clean(self):
        d = super().clean()
        if not d.get("ted") and not d.get("placsp"):
            raise forms.ValidationError("Elige al menos una fuente.")
        if d.get("ted") and d.get("ted_desde") and d.get("ted_hasta"):
            if d["ted_desde"] > d["ted_hasta"]:
                raise forms.ValidationError("La fecha inicial de TED es posterior a la final.")
            if (d["ted_hasta"] - d["ted_desde"]).days > 366:
                raise forms.ValidationError("TED: como máximo un año por actualización.")
        return d


@rol_requerido(*ROLES_IMPORTAR)
@require_http_methods(["GET", "POST"])
def actualizar(request):
    activos = TrabajoIngesta.objects.filter(estado__in=["pendiente", "en_curso"])
    form = ActualizarForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        creados = []
        if d["ted"]:
            creados.append(
                TrabajoIngesta.objects.create(
                    tipo=TIPO_TED,
                    parametros={"desde": str(d["ted_desde"]), "hasta": str(d["ted_hasta"])},
                    usuario=request.user,
                )
            )
        if d["placsp"]:
            creados.append(
                TrabajoIngesta.objects.create(
                    tipo=TIPO_PLACSP, parametros={"mes": d["placsp_mes"]}, usuario=request.user
                )
            )
        lanzar_ejecutor()
        messages.success(request, f"Trabajos en cola: {len(creados)}.")
        return redirect("trabajos")
    return render(request, "contratacion/actualizar.html", {"form": form, "activos": activos})


@rol_requerido(*ROLES_IMPORTAR)
def trabajos(request):
    lista = TrabajoIngesta.objects.select_related("usuario")[:30]
    if any(t.activo for t in lista):
        lanzar_ejecutor()  # si el proceso se reinició, retoma el trabajo (ADR-007)
    plantilla = "contratacion/_trabajos.html" if request.htmx else "contratacion/trabajos.html"
    return render(
        request, plantilla, {"trabajos": lista, "hay_activos": any(t.activo for t in lista)}
    )


@rol_requerido(*ROLES_IMPORTAR)
def trabajo(request, pk):
    t = get_object_or_404(TrabajoIngesta, pk=pk)
    return render(request, "contratacion/trabajo.html", {"t": t})
