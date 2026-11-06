"""Bandeja de revisión (RF-60, docs/05 §5)."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.contratacion import services_revision as srv_contratacion
from apps.contratacion.forms import AdjudicatarioForm, ClasificarForm, VincularOrganoForm
from apps.medios import services_revision as srv_medios
from apps.medios.forms import ConfirmarAtribucionForm, VinculoForm
from apps.nucleo.models import ElementoRevision
from apps.nucleo.roles import Rol, rol_requerido
from apps.territorio.models import Municipio

from . import services_revision as srv
from .forms import DecidirNivelForm, RechazarForm, ResolverMunicipioForm, ResolverOperadorForm

ROLES = (Rol.ADMINISTRADOR, Rol.ANALISTA)
Tipo = ElementoRevision.Tipo
Estado = ElementoRevision.Estado

FORMULARIOS = {
    Tipo.MUNICIPIO_NO_RESUELTO: ResolverMunicipioForm,
    Tipo.OPERADOR_NO_RESUELTO: ResolverOperadorForm,
    Tipo.NIVEL_POR_DECIDIR: DecidirNivelForm,
    Tipo.VINCULO_ORGANO: VincularOrganoForm,
    Tipo.CLASIFICACION_SERVICIO: ClasificarForm,
    Tipo.ADJUDICATARIO_NO_RESUELTO: AdjudicatarioForm,
    Tipo.ATRIBUCION_MENCION: ConfirmarAtribucionForm,
    Tipo.VINCULO_TERRITORIAL: VinculoForm,
}


@rol_requerido(*ROLES)
def bandeja(request):
    tipo = request.GET.get("tipo", "")
    estado = request.GET.get("estado", Estado.PENDIENTE)
    q = request.GET.get("q", "").strip()
    qs = ElementoRevision.objects.select_related("lote_importacion")
    if estado:
        qs = qs.filter(estado=estado)
    if tipo:
        qs = qs.filter(tipo=tipo)
    if q:
        qs = qs.filter(texto__icontains=q)
    conteo = dict(
        ElementoRevision.objects.filter(estado=Estado.PENDIENTE)
        .values_list("tipo")
        .annotate(n=Count("pk"))
    )
    pagina = Paginator(qs, 50).get_page(request.GET.get("pagina"))
    return render(
        request,
        "evidencias/bandeja.html",
        {
            "pagina": pagina,
            "tipos": [(t, t.label, conteo.get(t, 0)) for t in Tipo],
            "estados": Estado.choices,
            "tipo": tipo,
            "estado": estado,
            "q": q,
        },
    )


def _formulario(elemento, datos=None):
    clase = FORMULARIOS[elemento.tipo]
    inicial = {}
    if elemento.tipo == Tipo.NIVEL_POR_DECIDIR and elemento.objeto:
        inicial = {"url_origen": elemento.objeto.url_origen}
    return clase(datos, initial=inicial)


@rol_requerido(*ROLES)
@require_http_methods(["GET", "POST"])
def elemento(request, pk):
    el = get_object_or_404(ElementoRevision, pk=pk)
    iguales = srv.iguales_pendientes(el).exclude(pk=el.pk) if el.estado == Estado.PENDIENTE else []
    form = _formulario(el, request.POST if "resolver" in request.POST else None)
    rechazo = RechazarForm(request.POST if "rechazar" in request.POST else None)
    if request.method == "POST":
        try:
            if "rechazar" in request.POST and rechazo.is_valid():
                objetivos = [el, *iguales] if request.POST.get("aplicar_a_iguales") else [el]
                for e in objetivos:
                    srv.rechazar(e, request.user, rechazo.cleaned_data["comentario"])
                messages.success(request, f"Rechazados: {len(objetivos)}.")
                return redirect(_siguiente(el))
            if "resolver" in request.POST and form.is_valid():
                n = _resolver(el, list(iguales), form.cleaned_data, request.user)
                messages.success(request, f"Resueltos: {n}.")
                return redirect(_siguiente(el))
        except ValidationError as e:
            messages.error(request, " ".join(e.messages))
    sugerencias = Municipio.objects.filter(
        codigo_ine__in=el.propuesta.get("sugerencias", [])
    ).select_related("provincia")
    return render(
        request,
        "evidencias/elemento_revision.html",
        {
            "el": el,
            "objeto": el.objeto,
            "form": form,
            "rechazo": rechazo,
            "iguales": len(iguales),
            "sugerencias": sugerencias,
            "fila": (el.datos or {}).get("fila"),
        },
    )


def _resolver(el, iguales, datos, usuario) -> int:
    objetivos = [el, *iguales] if datos.get("aplicar_a_iguales") else [el]
    for e in objetivos:
        if el.tipo == Tipo.MUNICIPIO_NO_RESUELTO:
            srv.resolver_municipio(
                e,
                datos["municipio"],
                usuario,
                guardar_nombre=datos["guardar_nombre"] and e is el,
                comentario=datos["comentario"],
            )
        elif el.tipo == Tipo.OPERADOR_NO_RESUELTO:
            srv.resolver_operador(
                e,
                list(datos["empresas"]),
                usuario,
                guardar_alias=datos["guardar_alias"] and e is el,
                comentario=datos["comentario"],
            )
        elif el.tipo == Tipo.NIVEL_POR_DECIDIR:
            srv.decidir_nivel(e, datos["nivel"], usuario, datos["url_origen"], datos["comentario"])
        elif el.tipo == Tipo.VINCULO_ORGANO:
            srv_contratacion.vincular(e, datos["municipio"], usuario, datos["comentario"])
        elif el.tipo == Tipo.CLASIFICACION_SERVICIO:
            srv_contratacion.clasificar(e, datos["servicio"], usuario, datos["comentario"])
        elif el.tipo == Tipo.ADJUDICATARIO_NO_RESUELTO:
            srv_contratacion.resolver_adjudicatario(
                e,
                datos["empresa"],
                usuario,
                guardar_alias=datos["guardar_alias"] and e is el,
                guardar_nif=datos["guardar_nif"] and e is el,
                comentario=datos["comentario"],
            )
        elif el.tipo == Tipo.ATRIBUCION_MENCION:
            srv_medios.confirmar_atribucion(e, usuario, datos["comentario"])
        elif el.tipo == Tipo.VINCULO_TERRITORIAL:
            srv_medios.fijar_vinculo(e.objeto, datos["vinculo"], usuario, datos["comentario"], e)
    if el.tipo == Tipo.ADJUDICATARIO_NO_RESUELTO and (
        datos.get("guardar_alias") or datos.get("guardar_nif")
    ):
        n = srv_contratacion.aplicar_resolucion_a_otras_adjudicaciones(datos["empresa"])
        return len(objetivos) + n
    return len(objetivos)


def _siguiente(el):
    siguiente = (
        ElementoRevision.objects.filter(estado=Estado.PENDIENTE, tipo=el.tipo)
        .order_by("pk")
        .first()
    )
    if siguiente:
        return reverse("revision_elemento", args=[siguiente.pk])
    return reverse("revision")
