from django import forms

from .models import Usuario, normalizar_email
from .roles import Rol


class InvitacionForm(forms.Form):
    email = forms.EmailField(label="Email")
    nombre = forms.CharField(label="Nombre", max_length=150, required=False)
    rol = forms.ChoiceField(label="Rol", choices=[(r.value, r.value) for r in Rol])

    def clean_email(self):
        email = normalizar_email(self.cleaned_data["email"])
        if Usuario.objects.filter(email=email).exists():
            raise forms.ValidationError("Ya existe un usuario con ese email.")
        return email
