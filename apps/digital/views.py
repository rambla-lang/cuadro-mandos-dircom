from django import forms
from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.medios.forms import VariosArchivosField
from apps.nucleo.roles import Rol, rol_requerido
from apps.nucleo.services import registrar_auditoria

from .models import AuditoriaWeb, ObservacionDigital, PerfilDigital
from .services import COLUMNAS, entero_o_nulo, importar_csv

ROLES = (Rol.ADMINISTRADOR, Rol.ANALISTA)


class PerfilForm(forms.ModelForm):
    class Meta:
        model = PerfilDigital
        fields = ("empresa", "red", "url", "cuenta_verificada")


class ObservacionForm(forms.Form):
    perfil = forms.ModelChoiceField(PerfilDigital.objects.select_related("empresa"), label="Perfil")
    fecha_observacion = forms.DateField(
        label="Fecha de observación", widget=forms.DateInput(attrs={"type": "date"})
    )
    seguidores = forms.CharField(label="Seguidores (o «no visible»)", max_length=20)
    publicaciones_observadas = forms.CharField(
        label="Publicaciones observadas (o «no visible»)", max_length=20, required=False
    )
    periodo_observado = forms.CharField(label="Periodo observado", max_length=100, required=False)
    historico_suficiente = forms.BooleanField(label="Histórico suficiente", required=False)
    notas = forms.CharField(label="Notas", required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def clean_seguidores(self):
        try:
            return entero_o_nulo(self.cleaned_data["seguidores"])
        except ValueError as e:
            raise forms.ValidationError(str(e)) from e

    def clean_publicaciones_observadas(self):
        try:
            return entero_o_nulo(self.cleaned_data["publicaciones_observadas"])
        except ValueError as e:
            raise forms.ValidationError(str(e)) from e


class AuditoriaForm(forms.ModelForm):
    class Meta:
        model = AuditoriaWeb
        fields = ("empresa", "url", "fecha", "tono", "contenidos_destacados", "usabilidad")
        widgets = {"fecha": forms.DateInput(attrs={"type": "date"})}


class CsvForm(forms.Form):
    archivos = VariosArchivosField(label="CSV de observaciones")


def panel(request):
    perfiles = PerfilDigital.objects.select_related("empresa").prefetch_related("observaciones")
    return render(
        request,
        "digital/panel.html",
        {
            "perfiles": perfiles,
            "auditorias": AuditoriaWeb.objects.select_related("empresa")[:30],
            "columnas": ", ".join(COLUMNAS),
        },
    )


@rol_requerido(*ROLES)
@require_http_methods(["GET", "POST"])
def nuevo(request):
    tipo = request.GET.get("tipo", "observacion")
    clase = {
        "perfil": PerfilForm,
        "observacion": ObservacionForm,
        "auditoria": AuditoriaForm,
        "csv": CsvForm,
    }.get(tipo, ObservacionForm)
    form = clase(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        if tipo == "csv":
            for a in form.cleaned_data["archivos"]:
                r = importar_csv(a.read(), request.user)
                messages.success(
                    request, f"{a.name}: {r.nuevas} nuevas, {r.actualizadas} actualizadas."
                )
                for e in r.errores[:10]:
                    messages.error(request, e)
        elif tipo == "observacion":
            d = form.cleaned_data
            obs, _ = ObservacionDigital.objects.update_or_create(
                perfil=d["perfil"],
                fecha_observacion=d["fecha_observacion"],
                defaults={
                    k: d[k]
                    for k in (
                        "seguidores",
                        "publicaciones_observadas",
                        "periodo_observado",
                        "historico_suficiente",
                        "notas",
                    )
                }
                | {"creado_por": request.user},
            )
            registrar_auditoria(request.user, "digital.observacion", obs)
            messages.success(request, "Observación guardada.")
        else:
            obj = form.save(commit=False)
            if hasattr(obj, "creado_por"):
                obj.creado_por = request.user
            obj.save()
            registrar_auditoria(request.user, f"digital.{tipo}", obj)
            messages.success(request, "Guardado.")
        return redirect("digital")
    return render(
        request, "digital/nuevo.html", {"form": form, "tipo": tipo, "columnas": ", ".join(COLUMNAS)}
    )
