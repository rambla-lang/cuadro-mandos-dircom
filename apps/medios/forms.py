from django import forms

from apps.entidades.models import Empresa
from apps.evidencias.enums import VinculoTerritorial


class ConfirmarAtribucionForm(forms.Form):
    aplicar_a_iguales = forms.BooleanField(
        label="Confirmar todas las pendientes con el mismo alias", required=False
    )
    comentario = forms.CharField(
        label="Comentario", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )


class VinculoForm(forms.Form):
    vinculo = forms.ChoiceField(
        label="Vínculo con la Comunitat Valenciana", choices=VinculoTerritorial.choices
    )
    comentario = forms.CharField(label="Motivo", required=False, max_length=300)


class AtribuirForm(forms.Form):
    empresa = forms.ModelChoiceField(Empresa.objects.filter(activa=True), label="Empresa")


class VariosArchivosInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class VariosArchivosField(forms.FileField):
    """Subida múltiple (patrón de la documentación de Django)."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", VariosArchivosInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        limpiar = super().clean
        if isinstance(data, list | tuple):
            return [limpiar(d, initial) for d in data]
        return [limpiar(data, initial)]


class SubirBrandwatchForm(forms.Form):
    archivos = VariosArchivosField(label="Exportaciones CSV de Brandwatch")

    def clean_archivos(self):
        archivos = self.cleaned_data["archivos"]
        for a in archivos:
            if not a.name.lower().endswith(".csv"):
                raise forms.ValidationError(f"{a.name}: solo se admiten ficheros .csv.")
        return archivos


class SubirRecortesForm(forms.Form):
    archivos = VariosArchivosField(label="Recortes en PDF")
    empresa = forms.ModelChoiceField(
        Empresa.objects.filter(activa=True),
        required=False,
        label="Empresa de la que tratan (propuesta inicial; se puede corregir)",
    )

    def clean_archivos(self):
        archivos = self.cleaned_data["archivos"]
        for a in archivos:
            if not a.name.lower().endswith(".pdf"):
                raise forms.ValidationError(f"{a.name}: solo se admiten ficheros .pdf.")
        return archivos
