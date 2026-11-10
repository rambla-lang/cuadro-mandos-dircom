from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.evidencias.enums import Servicio
from apps.nucleo.models import ModeloConFechas
from apps.nucleo.texto import normalizar_texto


class GrupoEmpresarial(ModeloConFechas):
    nombre = models.CharField("nombre", max_length=200, unique=True)

    class Meta:
        verbose_name = "grupo empresarial"
        verbose_name_plural = "grupos empresariales"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Empresa(ModeloConFechas):
    """Empresa gestora de servicios municipales. No se borra si tiene evidencias: se desactiva
    (docs/03)."""

    nombre = models.CharField("nombre", max_length=200, unique=True)
    grupo = models.ForeignKey(
        GrupoEmpresarial,
        verbose_name="grupo",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="empresas",
    )
    nif = models.CharField("NIF", max_length=20, null=True, blank=True, unique=True)
    con_ficha = models.BooleanField(
        "con ficha",
        default=False,
        help_text="Empresa gestora con ficha y seguimiento en medios e informes.",
    )
    activa = models.BooleanField("activa", default=True)
    notas = models.TextField("notas", blank=True)

    class Meta:
        verbose_name = "empresa gestora"
        verbose_name_plural = "empresas gestoras"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        self.nif = (self.nif or "").strip().upper() or None
        super().save(*args, **kwargs)


class AliasEmpresa(ModeloConFechas):
    class Tipo(models.TextChoices):
        MARCA = "marca", "Marca"
        RAZON_SOCIAL = "razon_social", "Razón social"
        ABREVIATURA = "abreviatura", "Abreviatura"
        MARCA_LOCAL = "marca_local", "Marca local"

    empresa = models.ForeignKey(
        Empresa, verbose_name="empresa", on_delete=models.CASCADE, related_name="alias"
    )
    texto = models.CharField("texto", max_length=200)
    texto_normalizado = models.CharField(max_length=200, editable=False)
    tipo = models.CharField("tipo", max_length=20, choices=Tipo.choices, default=Tipo.MARCA)
    requiere_contexto = models.BooleanField(
        "requiere contexto",
        default=False,
        help_text="Alias ambiguo (por ejemplo, «Cox» también es un municipio): "
        "una coincidencia solo propone, no atribuye.",
    )

    class Meta:
        verbose_name = "alias de empresa"
        verbose_name_plural = "alias de empresa"
        ordering = ["empresa__nombre", "texto"]
        constraints = [
            models.UniqueConstraint(
                fields=["empresa", "texto_normalizado"], name="alias_unico_por_empresa"
            ),
        ]

    def __str__(self):
        return self.texto

    def save(self, *args, **kwargs):
        self.texto_normalizado = normalizar_texto(self.texto)
        super().save(*args, **kwargs)


class AcotacionEmpresa(ModeloConFechas):
    """Límite del análisis de una empresa gestora (RF-11). Es un dato editable, no código."""

    empresa = models.ForeignKey(
        Empresa, verbose_name="empresa", on_delete=models.CASCADE, related_name="acotaciones"
    )
    servicios_incluidos = ArrayField(
        models.CharField(max_length=20, choices=Servicio.choices),
        verbose_name="servicios incluidos",
        default=list,
        blank=True,
        help_text="Vacío: la acotación no limita por servicio (ver la nota).",
    )
    ambito_geografico = models.CharField("ámbito geográfico", max_length=200, blank=True)
    nota = models.TextField("nota")
    fuente = models.CharField(
        "fuente",
        max_length=300,
        blank=True,
        help_text="Documento o decisión de la que sale la acotación.",
    )

    class Meta:
        verbose_name = "acotación de empresa gestora"
        verbose_name_plural = "acotaciones de empresa gestora"
        ordering = ["empresa__nombre"]

    def __str__(self):
        return f"{self.empresa}: {self.nota[:60]}"
