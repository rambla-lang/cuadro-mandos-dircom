from django import forms

from apps.entidades.models import Empresa


class RevisarPropuestaForm(forms.Form):
    empresas = forms.MultipleChoiceField(
        label="Empresas propuestas que aceptas", required=False, widget=forms.CheckboxSelectMultiple
    )
    comentario = forms.CharField(
        label="Comentario", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )

    def __init__(self, *args, propuesta=None, **kwargs):
        super().__init__(*args, **kwargs)
        ids = [
            e["empresa_id"] for e in (propuesta.propuesta.get("empresas", []) if propuesta else [])
        ]
        nombres = dict(Empresa.objects.filter(pk__in=ids).values_list("pk", "nombre"))
        self.fields["empresas"].choices = [
            (str(i), nombres.get(i, f"id {i} (no existe)")) for i in ids
        ]
        self.fields["empresas"].initial = [str(i) for i in ids if i in nombres]
        self._todas = {i for i in ids}
        if not ids:
            self.fields.pop("empresas")

    def clean(self):
        datos = super().clean()
        datos["empresas_todas"] = self._todas
        return datos
