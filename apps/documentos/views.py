from django import forms
from django.contrib import messages
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from apps.ia.cliente import estado as ia_estado
from apps.medios.forms import VariosArchivosField
from apps.nucleo.roles import Rol, rol_requerido

from . import word
from .models import Documento

ROLES = (Rol.ADMINISTRADOR, Rol.ANALISTA)
TIPOS = [
    ("percepciones", "Valoración interna (percepciones): una empresa por cabecera en mayúsculas"),
    ("publicaciones", "Lista de publicaciones en prensa: URL agrupadas por empresa"),
    ("maestro", "Documento maestro: anexo de evidencias (P, S y D) como borradores"),
]


class WordForm(forms.Form):
    tipo = forms.ChoiceField(label="Qué es", choices=TIPOS, widget=forms.RadioSelect)
    archivos = VariosArchivosField(label="Documento Word (.docx)")

    def clean_archivos(self):
        for a in self.cleaned_data["archivos"]:
            if not a.name.lower().endswith(".docx"):
                raise forms.ValidationError(f"{a.name}: solo se admiten ficheros .docx.")
        return self.cleaned_data["archivos"]


@rol_requerido(*ROLES)
@require_http_methods(["GET", "POST"])
def importar_word(request):
    form = WordForm(request.POST or None, request.FILES or None)
    resultados = []
    if request.method == "POST" and form.is_valid():
        funcion = {
            "percepciones": word.importar_percepciones,
            "publicaciones": word.importar_publicaciones,
            "maestro": word.importar_anexo_maestro,
        }[form.cleaned_data["tipo"]]
        for a in form.cleaned_data["archivos"]:
            try:
                resultados.append((a.name, funcion(a.read(), a.name, request.user), None))
            except Exception as e:  # noqa: BLE001 - un .docx dañado no debe romper la página
                resultados.append((a.name, None, f"No se ha podido leer: {e}"))
        if resultados:
            messages.success(request, "Importación terminada.")
    documentos = Documento.objects.exclude(tipo="recorte").select_related("subido_por")[:30]
    return render(
        request,
        "documentos/importar_word.html",
        {
            "form": form,
            "resultados": resultados,
            "documentos": documentos,
            "ia": ia_estado("extraer"),
        },
    )
