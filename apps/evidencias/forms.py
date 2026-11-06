from pathlib import Path

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

from apps.entidades.models import Empresa
from apps.territorio.models import Municipio

from .enums import (
    ALCANCES_POR_SERVICIO,
    Alcance,
    EstadoValidacion,
    NivelEvidencia,
    Servicio,
    TipoFuente,
)
from .importers.tabla_municipal import DECIDIR, EXTENSIONES
from .models import PlantillaImportacion

OPCION_DECIDIR = (DECIDIR, "Decidir en la bandeja de revisión")
OPCIONES_NIVEL = [*NivelEvidencia.choices, OPCION_DECIDIR]
OPCIONES_ESTADO = [
    (EstadoValidacion.VALIDADA, "Validada: la tabla ya la ha revisado una persona"),
    (EstadoValidacion.BORRADOR, "Borrador: hay que validar cada registro"),
]


def opciones_servicio_alcance():
    """«agua|» = agua con alcance sin especificar; «agua|saneamiento», etc."""
    opciones = [("", "Ignorar estas filas")]
    for servicio, alcances in ALCANCES_POR_SERVICIO.items():
        opciones.append((f"{servicio}|", f"{servicio.label} · alcance sin especificar"))
        opciones += [(f"{servicio}|{a}", f"{servicio.label} · {a.label}") for a in alcances]
    return opciones


class SubidaForm(forms.Form):
    archivo = forms.FileField(label="Archivo (.xlsx o .csv)")
    plantilla = forms.ModelChoiceField(
        PlantillaImportacion.objects.filter(tipo="tabla_municipal"),
        required=False,
        label="Plantilla de correspondencia (opcional)",
        empty_label="Ninguna: definir columnas a mano",
    )

    def clean_archivo(self):
        archivo = self.cleaned_data["archivo"]
        if Path(archivo.name).suffix.lower() not in EXTENSIONES:
            raise ValidationError("Solo se admiten ficheros .xlsx y .csv.")
        if archivo.size > settings.SUBIDA_MAX_MB * 1024 * 1024:
            raise ValidationError(f"El archivo supera {settings.SUBIDA_MAX_MB} MB.")
        return archivo


class HojaForm(forms.Form):
    hoja = forms.ChoiceField(label="Hoja")
    fila_cabecera = forms.IntegerField(label="Fila de cabecera", min_value=1, initial=1)

    def __init__(self, *args, hojas=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["hoja"].choices = [(h, h) for h in hojas]


class _ConColumnas(forms.Form):
    def __init__(self, *args, columnas=(), **kwargs):
        super().__init__(*args, **kwargs)
        opciones = [("", "—"), *[(c, c) for c in columnas]]
        for nombre, campo in self.fields.items():
            if nombre.startswith("columna"):
                campo.choices = opciones if not campo.required else opciones[1:]
        if "columnas_extra" in self.fields:
            self.fields["columnas_extra"].choices = [(c, c) for c in columnas]


class ColumnasForm(_ConColumnas):
    columna_municipio = forms.ChoiceField(label="Columna de municipio")
    columna_provincia = forms.ChoiceField(
        label="Columna de provincia (opcional, solo restringe la búsqueda)", required=False
    )
    fuente_tipo = forms.ChoiceField(label="Tipo de fuente", choices=TipoFuente.choices)
    fuente_nombre = forms.CharField(label="Nombre de la fuente", max_length=200)
    fecha_consulta = forms.DateField(
        label="Fecha de elaboración o consulta de la tabla",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    estado = forms.ChoiceField(label="Estado al importar", choices=OPCIONES_ESTADO)


class BloqueForm(_ConColumnas):
    servicio = forms.ChoiceField(
        label="Servicio",
        required=False,
        choices=[("", "Según una columna (formato largo)"), *Servicio.choices],
    )
    alcance = forms.ChoiceField(
        label="Alcance",
        required=False,
        choices=[("", "Sin especificar"), *Alcance.choices],
    )
    columna_servicio = forms.ChoiceField(label="Columna de servicio", required=False)
    columna_operador = forms.ChoiceField(label="Columna de operador", required=False)
    columna_detalle = forms.ChoiceField(label="Columna de detalle", required=False)
    columna_figura = forms.ChoiceField(label="Columna de figura", required=False)
    columna_fuente = forms.ChoiceField(label="Columna de fuente", required=False)
    columna_anio = forms.ChoiceField(label="Columna de año", required=False)
    columna_nivel = forms.ChoiceField(label="Columna de nivel", required=False)
    nivel_por_defecto = forms.ChoiceField(
        label="Nivel si no hay columna o viene vacía", choices=OPCIONES_NIVEL, initial=DECIDIR
    )
    columnas_extra = forms.MultipleChoiceField(
        label="Columnas que se guardan como datos adicionales",
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    def clean(self):
        datos = super().clean()
        if not datos.get("columna_operador"):
            return datos
        if datos.get("servicio") and datos.get("columna_servicio"):
            raise ValidationError("Elige un servicio fijo o una columna de servicio, no ambos.")
        if not datos.get("servicio") and not datos.get("columna_servicio"):
            raise ValidationError("Elige el servicio o la columna que lo indica.")
        alcance = datos.get("alcance")
        servicio = datos.get("servicio")
        if alcance and servicio and alcance not in ALCANCES_POR_SERVICIO[Servicio(servicio)]:
            raise ValidationError("El alcance no corresponde al servicio.")
        return datos


BloqueFormSet = forms.formset_factory(BloqueForm, extra=1, max_num=8)


class ResolverMunicipioForm(forms.Form):
    municipio = forms.ModelChoiceField(
        Municipio.objects.select_related("provincia").order_by("nombre_oficial"),
        label="Municipio",
        to_field_name="codigo_ine",
    )
    guardar_nombre = forms.BooleanField(
        label="Guardar el texto como nombre alternativo del municipio", required=False
    )
    aplicar_a_iguales = forms.BooleanField(
        label="Aplicar a todos los pendientes con el mismo texto", required=False, initial=True
    )
    comentario = forms.CharField(
        label="Comentario", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )


class ResolverOperadorForm(forms.Form):
    empresas = forms.ModelMultipleChoiceField(
        Empresa.objects.filter(activa=True),
        label="Empresa o empresas del catálogo (varias si es una UTE)",
        widget=forms.CheckboxSelectMultiple,
    )
    guardar_alias = forms.BooleanField(
        label="Guardar el texto como alias (solo si es una única empresa)", required=False
    )
    aplicar_a_iguales = forms.BooleanField(
        label="Aplicar a todos los pendientes con el mismo texto", required=False, initial=True
    )
    comentario = forms.CharField(
        label="Comentario", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )

    def clean(self):
        datos = super().clean()
        if datos.get("guardar_alias") and len(datos.get("empresas") or []) != 1:
            raise ValidationError("El alias solo se puede guardar para una única empresa.")
        return datos


class DecidirNivelForm(forms.Form):
    nivel = forms.ChoiceField(label="Nivel", choices=NivelEvidencia.choices)
    url_origen = forms.URLField(
        label="URL de origen (obligatoria para «oficial»)", required=False, max_length=1000
    )
    comentario = forms.CharField(
        label="Comentario", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )


class RechazarForm(forms.Form):
    comentario = forms.CharField(
        label="Motivo", widget=forms.Textarea(attrs={"rows": 2}), max_length=1000
    )
