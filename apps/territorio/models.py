from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

from apps.nucleo.models import LoteImportacion, ModeloConFechas
from apps.nucleo.texto import normalizar_texto

solo_digitos_2 = RegexValidator(r"^\d{2}$", "Dos dígitos.")
solo_digitos_5 = RegexValidator(r"^\d{5}$", "Cinco dígitos.")


class Provincia(ModeloConFechas):
    codigo_ine = models.CharField(
        "código INE", max_length=2, unique=True, validators=[solo_digitos_2]
    )
    nombre = models.CharField("nombre", max_length=100)
    comunidad = models.CharField("comunidad autónoma", max_length=100)

    class Meta:
        verbose_name = "provincia"
        verbose_name_plural = "provincias"
        ordering = ["codigo_ine"]

    def __str__(self):
        return self.nombre


class Municipio(ModeloConFechas):
    codigo_ine = models.CharField(
        "código INE", max_length=5, unique=True, validators=[solo_digitos_5]
    )
    nombre_oficial = models.CharField("nombre oficial", max_length=200)
    nombres_alternativos = ArrayField(
        models.CharField(max_length=200),
        verbose_name="nombres alternativos",
        default=list,
        blank=True,
        help_text="Formas en castellano y valenciano, con o sin artículo. Una por elemento.",
    )
    # Derivado de nombre_oficial + nombres_alternativos; se recalcula al guardar.
    nombres_normalizados = ArrayField(
        models.CharField(max_length=200), default=list, editable=False
    )
    provincia = models.ForeignKey(
        Provincia, verbose_name="provincia", on_delete=models.PROTECT, related_name="municipios"
    )
    lote_importacion = models.ForeignKey(
        LoteImportacion,
        verbose_name="lote de importación",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        verbose_name = "municipio"
        verbose_name_plural = "municipios"
        ordering = ["nombre_oficial"]
        indexes = [GinIndex(fields=["nombres_normalizados"], name="municipio_nombres_norm_gin")]

    def __str__(self):
        return self.nombre_oficial

    def clean(self):
        super().clean()
        if (
            self.provincia_id
            and self.codigo_ine
            and not self.codigo_ine.startswith(self.provincia.codigo_ine)
        ):
            raise ValidationError({"codigo_ine": "Debe empezar por el código de su provincia."})

    def save(self, *args, **kwargs):
        formas = [self.nombre_oficial, *self.nombres_alternativos]
        self.nombres_normalizados = sorted({normalizar_texto(f) for f in formas if f.strip()})
        if "update_fields" in kwargs and kwargs["update_fields"] is not None:
            kwargs["update_fields"] = {*kwargs["update_fields"], "nombres_normalizados"}
        super().save(*args, **kwargs)


class EntidadSupramunicipal(ModeloConFechas):
    class Tipo(models.TextChoices):
        CONSORCIO = "consorcio", "Consorcio"
        MANCOMUNIDAD = "mancomunidad", "Mancomunidad"
        DIPUTACION = "diputacion", "Diputación"
        OTRO = "otro", "Otro"

    nombre = models.CharField("nombre", max_length=200, unique=True)
    tipo = models.CharField("tipo", max_length=20, choices=Tipo.choices)
    municipios = models.ManyToManyField(
        Municipio,
        verbose_name="municipios miembros",
        blank=True,
        related_name="entidades_supramunicipales",
    )

    class Meta:
        verbose_name = "entidad supramunicipal"
        verbose_name_plural = "entidades supramunicipales"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre
