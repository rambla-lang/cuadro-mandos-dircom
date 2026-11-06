"""Buscador global de evidencias y ficha de evidencia con su historial (docs/07)."""

from django import forms
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from apps.entidades.models import Empresa
from apps.nucleo.models import RegistroAuditoria
from apps.nucleo.roles import Rol, rol_requerido, tiene_rol
from apps.nucleo.services import instantanea, registrar_auditoria
from apps.territorio.models import Municipio

from .enums import CategoriaEvidencia, EstadoValidacion, NivelEvidencia, Origen, TipoFuente
from .models import Evidencia, EvidenciaEmpresa, EvidenciaMunicipio, Fuente
from .services_revision import validar_evidencias

ROLES = (Rol.ADMINISTRADOR, Rol.ANALISTA)


def lista(request):
    g = request.GET
    qs = Evidencia.objects.select_related("fuente").prefetch_related("empresas")
    if g.get("q"):
        qs = qs.filter(
            Q(titulo__icontains=g["q"]) | Q(extracto__icontains=g["q"]) | Q(codigo__iexact=g["q"])
        )
    for campo in ("categoria", "nivel", "estado_validacion", "servicio"):
        if g.get(campo):
            qs = qs.filter(**{campo: g[campo]})
    if g.get("empresa"):
        qs = qs.filter(empresas__pk=g["empresa"])
    pagina = Paginator(qs.distinct(), 50).get_page(g.get("pagina"))
    filtros = g.copy()
    filtros.pop("pagina", None)
    return render(
        request,
        "evidencias/lista.html",
        {
            "pagina": pagina,
            "g": g,
            "filtros": filtros.urlencode(),
            "categorias": CategoriaEvidencia.choices,
            "niveles": NivelEvidencia.choices,
            "estados": EstadoValidacion.choices,
            "empresas": Empresa.objects.filter(activa=True),
        },
    )


def detalle(request, pk):
    ev = get_object_or_404(
        Evidencia.objects.select_related("fuente", "validado_por", "creado_por"), pk=pk
    )
    historial = RegistroAuditoria.objects.filter(
        objeto_tipo=ContentType.objects.get_for_model(Evidencia), objeto_id=str(ev.pk)
    )
    return render(
        request,
        "evidencias/detalle.html",
        {
            "e": ev,
            "historial": historial,
            "puede_editar": tiene_rol(request.user, *ROLES),
            "puede_validar": request.user.has_perm("evidencias.validar_evidencia"),
            "prestaciones": ev.prestaciones.select_related("municipio", "empresa"),
        },
    )


class EvidenciaForm(forms.ModelForm):
    fuente_nombre = forms.CharField(label="Fuente (nombre)", max_length=200)
    fuente_tipo = forms.ChoiceField(label="Tipo de fuente", choices=TipoFuente.choices)
    empresas_sel = forms.ModelMultipleChoiceField(
        Empresa.objects.filter(activa=True),
        label="Empresas",
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    municipios_sel = forms.ModelMultipleChoiceField(
        Municipio.objects.order_by("nombre_oficial"),
        label="Municipios",
        required=False,
        widget=forms.SelectMultiple(attrs={"size": 6}),
    )

    class Meta:
        model = Evidencia
        fields = (
            "categoria",
            "titulo",
            "extracto",
            "url_origen",
            "fecha_publicacion",
            "fecha_evento",
            "fecha_consulta",
            "servicio",
            "alcance",
            "nivel",
            "tratamiento_limites",
        )
        widgets = {
            "fecha_publicacion": forms.DateInput(attrs={"type": "date"}),
            "fecha_evento": forms.DateInput(attrs={"type": "date"}),
            "fecha_consulta": forms.DateInput(attrs={"type": "date"}),
            "extracto": forms.Textarea(attrs={"rows": 4}),
            "tratamiento_limites": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["fuente_nombre"].initial = self.instance.fuente.nombre
            self.fields["fuente_tipo"].initial = self.instance.fuente.tipo
            self.fields["empresas_sel"].initial = list(self.instance.empresas.all())
            self.fields["municipios_sel"].initial = list(self.instance.municipios.all())

    def clean(self):
        d = super().clean()
        if d.get("nivel") == NivelEvidencia.OFICIAL and not d.get("url_origen"):
            raise forms.ValidationError("El nivel «oficial» exige una URL de origen oficial.")
        return d


@rol_requerido(*ROLES)
@require_http_methods(["GET", "POST"])
def editar(request, pk=None):
    ev = get_object_or_404(Evidencia, pk=pk) if pk else None
    form = EvidenciaForm(request.POST or None, instance=ev)
    if request.method == "POST" and form.is_valid():
        antes = (
            instantanea(ev) if ev and ev.estado_validacion == EstadoValidacion.VALIDADA else None
        )
        obj = form.save(commit=False)
        obj.fuente, _ = Fuente.objects.get_or_create(
            tipo=form.cleaned_data["fuente_tipo"], nombre=form.cleaned_data["fuente_nombre"]
        )
        if not ev:
            obj.origen = Origen.MANUAL
            obj.creado_por = request.user
            obj.estado_validacion = EstadoValidacion.BORRADOR
        obj.full_clean(exclude=["codigo"])
        obj.save()
        EvidenciaEmpresa.objects.filter(evidencia=obj).exclude(
            empresa__in=form.cleaned_data["empresas_sel"]
        ).delete()
        for e in form.cleaned_data["empresas_sel"]:
            EvidenciaEmpresa.objects.get_or_create(evidencia=obj, empresa=e)
        EvidenciaMunicipio.objects.filter(evidencia=obj).exclude(
            municipio__in=form.cleaned_data["municipios_sel"]
        ).delete()
        for m in form.cleaned_data["municipios_sel"]:
            EvidenciaMunicipio.objects.get_or_create(evidencia=obj, municipio=m)
        if antes is not None:
            registrar_auditoria(
                request.user,
                "evidencia.editar_validada",
                obj,
                antes=antes,
                despues=instantanea(obj),
            )
        else:
            registrar_auditoria(
                request.user, "evidencia.crear" if not ev else "evidencia.editar", obj
            )
        for p in obj.prestaciones.all():
            p.recalcular()
        messages.success(request, "Evidencia guardada.")
        return redirect("evidencia", pk=obj.pk)
    return render(request, "evidencias/editar.html", {"form": form, "e": ev})


@require_POST
def validar(request, pk):
    if not request.user.has_perm("evidencias.validar_evidencia"):
        return render(request, "403.html", status=403)
    ev = get_object_or_404(Evidencia, pk=pk)
    if request.POST.get("accion") == "rechazar":
        antes = instantanea(ev)
        ev.estado_validacion = EstadoValidacion.RECHAZADA
        ev.validado_por, ev.validado_en = request.user, timezone.now()
        ev.save()
        for p in ev.prestaciones.all():
            p.recalcular()
        registrar_auditoria(
            request.user, "evidencia.rechazar", ev, antes=antes, despues=instantanea(ev)
        )
        messages.success(request, "Evidencia rechazada.")
    else:
        n = validar_evidencias(Evidencia.objects.filter(pk=ev.pk), request.user)
        messages.success(
            request,
            "Evidencia validada."
            if n
            else "No se ha validado: ya lo estaba o tiene el nivel pendiente en la bandeja.",
        )
    return redirect("evidencia", pk=ev.pk)
