from django import forms

from apps.entidades.models import Empresa
from apps.evidencias.forms import opciones_servicio_alcance
from apps.territorio.models import Municipio


class VincularOrganoForm(forms.Form):
    municipio = forms.ModelChoiceField(
        Municipio.objects.select_related("provincia").order_by("nombre_oficial"),
        label="Municipio",
        to_field_name="codigo_ine",
    )
    comentario = forms.CharField(
        label="Comentario", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )


class ClasificarForm(forms.Form):
    servicio = forms.ChoiceField(label="Servicio y alcance")
    aplicar_a_iguales = forms.BooleanField(
        label="Aplicar a todos los pendientes con el mismo objeto", required=False
    )
    comentario = forms.CharField(
        label="Comentario", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        opciones = opciones_servicio_alcance()
        opciones[0] = ("", "No es de agua, residuos ni energía")
        self.fields["servicio"].choices = opciones


class AdjudicatarioForm(forms.Form):
    empresa = forms.ModelChoiceField(Empresa.objects.filter(activa=True), label="Empresa")
    guardar_alias = forms.BooleanField(
        label="Guardar el nombre (sin forma jurídica) como alias", required=False, initial=True
    )
    guardar_nif = forms.BooleanField(
        label="Guardar el NIF de la adjudicación en la empresa, si no tiene", required=False
    )
    aplicar_a_iguales = forms.BooleanField(
        label="Aplicar a todos los pendientes con el mismo texto", required=False, initial=True
    )
    comentario = forms.CharField(
        label="Comentario", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )
