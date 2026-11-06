"""Medios (docs/03 «medios», docs/04 §4-5, docs/05 §3). La unidad de recuento es la pieza."""

from django.conf import settings
from django.db import models, transaction

from apps.entidades.models import Empresa
from apps.evidencias.enums import EstadoValidacion, VinculoTerritorial
from apps.nucleo.models import LoteImportacion, ModeloConFechas


class Medio(ModeloConFechas):
    class Ambito(models.TextChoices):
        LOCAL = "local", "Local"
        COMARCAL = "comarcal", "Comarcal"
        REGIONAL = "regional", "Regional"
        NACIONAL = "nacional", "Nacional"
        SECTORIAL = "sectorial", "Sectorial"
        AGENCIA = "agencia", "Agencia"
        RED_SOCIAL = "red_social", "Red social"
        DESCONOCIDO = "desconocido", "Sin clasificar"

    nombre = models.CharField("nombre", max_length=200)
    dominio = models.CharField(  # noqa: DJ001 (NULL en prensa impresa sin dominio; único)
        "dominio", max_length=200, unique=True, null=True, blank=True
    )
    ambito = models.CharField(
        "ámbito", max_length=20, choices=Ambito.choices, default=Ambito.DESCONOCIDO
    )
    grupo_editorial = models.CharField("grupo editorial", max_length=200, blank=True)

    class Meta:
        verbose_name = "medio"
        verbose_name_plural = "medios"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Hito(ModeloConFechas):
    """Acto o noticia de fondo que agrupa varias piezas (dos medios, mismo acto: dos piezas y
    un hito)."""

    nombre = models.CharField("nombre", max_length=300)
    fecha_evento = models.DateField("fecha del acto", null=True, blank=True)
    descripcion = models.TextField("descripción", blank=True)

    class Meta:
        verbose_name = "hito"
        verbose_name_plural = "hitos"
        ordering = ["-fecha_evento", "nombre"]

    def __str__(self):
        return self.nombre


class Pieza(ModeloConFechas):
    class Tipo(models.TextChoices):
        PRENSA_DIGITAL = "prensa_digital", "Prensa digital"
        PRENSA_IMPRESA = "prensa_impresa", "Prensa impresa"
        RED_SOCIAL = "red_social", "Redes sociales"
        COMUNICADO_PROPIO = "comunicado_propio", "Comunicado propio u oficial"

    codigo = models.CharField(  # noqa: DJ001 (NULL hasta asignar P000123; único)
        "código", max_length=12, unique=True, null=True, editable=False
    )
    tipo = models.CharField("tipo de fuente", max_length=20, choices=Tipo.choices)
    medio = models.ForeignKey(
        Medio,
        verbose_name="medio",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="piezas",
    )
    url_canonica = models.URLField(  # noqa: DJ001 (NULL en recortes impresos; única)
        "URL canónica", max_length=1000, unique=True, null=True, blank=True
    )
    titulo = models.CharField("título", max_length=1000, blank=True)
    fecha_publicacion = models.DateField("fecha de publicación", null=True, blank=True)
    es_comunicado_propio = models.BooleanField("comunicado propio", default=False)
    hito = models.ForeignKey(
        Hito,
        verbose_name="hito",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="piezas",
    )

    class Meta:
        verbose_name = "pieza"
        verbose_name_plural = "piezas"
        ordering = ["-fecha_publicacion", "-pk"]

    def __str__(self):
        return f"{self.codigo or 'P-(nueva)'} · {self.titulo[:80]}"

    def save(self, *args, **kwargs):
        with transaction.atomic():
            super().save(*args, **kwargs)
            if not self.codigo:
                self.codigo = f"P{self.pk:06d}"
                type(self).objects.filter(pk=self.pk).update(codigo=self.codigo)


class Mencion(ModeloConFechas):
    class Origen(models.TextChoices):
        BRANDWATCH = "brandwatch", "Brandwatch"
        CLIPPING = "clipping", "Recorte de prensa"
        MANUAL = "manual", "Manual"

    origen = models.CharField("origen", max_length=20, choices=Origen.choices)
    resource_id = models.CharField(  # noqa: DJ001 (NULL fuera de Brandwatch; único)
        "Resource Id", max_length=100, unique=True, null=True, blank=True
    )
    url = models.URLField("URL", max_length=2000, blank=True)
    url_canonica = models.URLField("URL canónica", max_length=1000, blank=True, db_index=True)
    fecha_publicacion = models.DateTimeField("fecha de publicación", null=True, blank=True)
    titulo = models.CharField("título", max_length=1000, blank=True)
    extracto = models.TextField("extracto", blank=True)
    medio = models.ForeignKey(
        Medio,
        verbose_name="medio",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="menciones",
    )
    tipo_pagina = models.CharField("tipo de página", max_length=30, blank=True)
    idioma = models.CharField("idioma", max_length=10, blank=True)
    sentimiento_fuente = models.CharField(
        "sentimiento según la fuente",
        max_length=20,
        blank=True,
        help_text="Lo que dice Brandwatch, sin reinterpretar.",
    )
    region_fuente = models.CharField("región según la fuente", max_length=100, blank=True)
    datos_fuente = models.JSONField("datos de la fuente", default=dict, blank=True)
    vinculo_territorial = models.CharField(
        "vínculo territorial",
        max_length=10,
        choices=VinculoTerritorial.choices,
        default=VinculoTerritorial.DUDOSO,
    )
    motivo_vinculo = models.CharField("motivo del vínculo", max_length=300, blank=True)
    pieza = models.ForeignKey(
        Pieza,
        verbose_name="pieza",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="menciones",
    )
    documento = models.ForeignKey(
        "documentos.Documento",
        verbose_name="documento",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="menciones",
    )
    lote_importacion = models.ForeignKey(
        LoteImportacion,
        verbose_name="lote de importación",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="menciones",
    )

    class Meta:
        verbose_name = "mención"
        verbose_name_plural = "menciones"
        ordering = ["-fecha_publicacion", "-pk"]

    def __str__(self):
        return self.titulo[:80] or self.url


class MencionEmpresa(models.Model):
    class Metodo(models.TextChoices):
        ALIAS = "alias", "Alias"
        IA = "ia", "IA"
        MANUAL = "manual", "Manual"

    mencion = models.ForeignKey(Mencion, on_delete=models.CASCADE, related_name="atribuciones")
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name="menciones")
    metodo = models.CharField("método", max_length=10, choices=Metodo.choices)
    estado_validacion = models.CharField(
        "estado",
        max_length=20,
        choices=EstadoValidacion.choices,
        default=EstadoValidacion.BORRADOR,
    )
    fragmento_detectado = models.CharField("fragmento detectado", max_length=300, blank=True)
    validado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    validado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "atribución de mención"
        verbose_name_plural = "atribuciones de menciones"
        constraints = [
            models.UniqueConstraint(fields=["mencion", "empresa"], name="mencion_empresa_unica"),
        ]

    def __str__(self):
        return f"{self.mencion_id} → {self.empresa}"
