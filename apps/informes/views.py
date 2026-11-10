import io
from datetime import date, timedelta

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.entidades.models import Empresa
from apps.ia.cliente import estado as ia_estado
from apps.nucleo.roles import Rol, rol_requerido, tiene_rol

from . import services
from .models import InformeGenerado
from .salida import generar_docx, generar_pptx

ROLES = (Rol.ADMINISTRADOR, Rol.ANALISTA)


class NuevoForm(forms.Form):
    desde = forms.DateField(label="Desde", widget=forms.DateInput(attrs={"type": "date"}))
    hasta = forms.DateField(label="Hasta", widget=forms.DateInput(attrs={"type": "date"}))
    empresas = forms.ModelMultipleChoiceField(
        Empresa.objects.filter(activa=True, con_ficha=True),
        label="Empresas gestoras",
        widget=forms.CheckboxSelectMultiple,
    )
    usar_ia = forms.BooleanField(
        label="Redactar las secciones narrativas con IA (T6)", required=False
    )

    def clean(self):
        d = super().clean()
        if d.get("desde") and d.get("hasta") and d["desde"] > d["hasta"]:
            raise forms.ValidationError("La fecha inicial es posterior a la final.")
        return d


def lista(request):
    puede = tiene_rol(request.user, *ROLES)
    qs = InformeGenerado.objects.select_related("generado_por")
    if not puede:
        qs = qs.filter(estado=InformeGenerado.Estado.PUBLICADO)
    return render(request, "informes/lista.html", {"informes": qs[:50], "puede": puede})


@rol_requerido(*ROLES)
@require_http_methods(["GET", "POST"])
def nuevo(request):
    hoy = date.today()
    form = NuevoForm(
        request.POST or None,
        initial={
            "desde": hoy - timedelta(days=365),
            "hasta": hoy,
            "empresas": Empresa.objects.filter(activa=True, con_ficha=True),
        },
    )
    disponible, motivo = ia_estado("redactar")
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        informe = services.crear(
            d["empresas"], d["desde"], d["hasta"], request.user, d["usar_ia"] and disponible
        )
        messages.success(request, "Borrador generado: revisa las secciones antes de publicar.")
        return redirect("informe", pk=informe.pk)
    return render(
        request,
        "informes/nuevo.html",
        {"form": form, "ia_disponible": disponible, "ia_motivo": motivo},
    )


@require_http_methods(["GET", "POST"])
def detalle(request, pk):
    informe = get_object_or_404(InformeGenerado, pk=pk)
    puede = tiene_rol(request.user, *ROLES)
    if not puede and informe.estado != InformeGenerado.Estado.PUBLICADO:
        raise Http404
    if request.method == "POST":
        if not puede:
            return render(request, "403.html", status=403)
        try:
            if "publicar" in request.POST:
                services.publicar(informe, request.user)
                messages.success(
                    request, "Informe publicado: ya se pueden descargar el Word y la presentación."
                )
            else:
                services.guardar_texto(
                    informe,
                    request.POST.get("clave", ""),
                    request.POST.get("texto", ""),
                    request.user,
                )
                messages.success(request, "Sección guardada y validada de nuevo.")
        except ValidationError as e:
            messages.error(request, " ".join(e.messages))
        return redirect("informe", pk=informe.pk)
    return render(request, "informes/detalle.html", {"i": informe, "puede": puede})


def descargar(request, pk, formato):
    informe = get_object_or_404(InformeGenerado, pk=pk, estado=InformeGenerado.Estado.PUBLICADO)
    if formato not in ("docx", "pptx"):
        raise Http404
    ruta = {"docx": informe.archivo_docx, "pptx": informe.archivo_pptx}[formato]
    nombre = f"informe-empresas-gestoras-{informe.pk}.{formato}"
    if ruta and default_storage.exists(ruta):
        return FileResponse(default_storage.open(ruta, "rb"), as_attachment=True, filename=nombre)
    # En Render Free el disco es efímero: el informe se regenera desde lo guardado en la base de
    # datos (secciones y métricas publicadas), con el mismo contenido.
    contenido = generar_docx(informe) if formato == "docx" else generar_pptx(informe)
    return FileResponse(io.BytesIO(contenido), as_attachment=True, filename=nombre)
