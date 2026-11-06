"""Contratación pública (docs/03 «contratacion», docs/04 §1-2)."""

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import Q

from apps.entidades.models import Empresa
from apps.evidencias.enums import Alcance, NivelEvidencia, Servicio, q_alcance_coherente
from apps.nucleo.models import LoteImportacion, ModeloConFechas
from apps.nucleo.texto import normalizar_texto
from apps.territorio.models import EntidadSupramunicipal, Municipio


class FuenteContrato(models.TextChoices):
    PLACSP = "placsp", "PLACSP"
    TED = "ted", "TED"
    BOE = "boe", "BOE"


class OrganoContratacion(ModeloConFechas):
    class Vinculacion(models.TextChoices):
        AUTOMATICA = "automatica", "Automática"
        VALIDADA = "validada", "Validada"
        PENDIENTE = "pendiente", "Pendiente"
        NO_APLICA = "no_aplica", "No aplica (no es un órgano municipal)"

    id_plataforma = models.CharField(  # noqa: DJ001 (NULL si el órgano solo viene de TED)
        "ID en PLACSP", max_length=40, unique=True, null=True, blank=True
    )
    nif = models.CharField("NIF", max_length=20, blank=True, db_index=True)
    dir3 = models.CharField("DIR3", max_length=20, blank=True, db_index=True)
    nombre = models.CharField("nombre", max_length=500)
    ciudad = models.CharField("ciudad", max_length=200, blank=True)
    codigo_postal = models.CharField("código postal", max_length=10, blank=True)
    jerarquia = ArrayField(
        models.CharField(max_length=300), default=list, blank=True, verbose_name="jerarquía"
    )
    tipo_poder = models.CharField("tipo de poder adjudicador", max_length=10, blank=True)
    municipio = models.ForeignKey(
        Municipio,
        verbose_name="municipio",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="organos",
    )
    entidad_supramunicipal = models.ForeignKey(
        EntidadSupramunicipal,
        verbose_name="entidad supramunicipal",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="organos",
    )
    estado_vinculacion = models.CharField(
        "vinculación", max_length=20, choices=Vinculacion.choices, default=Vinculacion.PENDIENTE
    )

    class Meta:
        verbose_name = "órgano de contratación"
        verbose_name_plural = "órganos de contratación"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Expediente(ModeloConFechas):
    class Clasificacion(models.TextChoices):
        CPV = "cpv", "CPV"
        PALABRAS = "palabras_clave", "Palabras clave"
        IA = "ia", "IA"
        MANUAL = "manual", "Manual"
        SIN_CLASIFICAR = "sin_clasificar", "Sin clasificar"

    class Iva(models.TextChoices):
        SI = "si", "Con IVA"
        NO = "no", "Sin IVA"
        DESCONOCIDO = "desconocido", "Desconocido"

    fuente = models.CharField("fuente", max_length=10, choices=FuenteContrato.choices)
    id_externo = models.CharField("id en la fuente", max_length=300)
    numero_expediente = models.CharField("nº de expediente", max_length=200, blank=True)
    organo = models.ForeignKey(
        OrganoContratacion,
        verbose_name="órgano",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="expedientes",
    )
    objeto = models.TextField("objeto", blank=True)
    tipo_contrato = models.CharField("tipo de contrato", max_length=20, blank=True)
    cpv = ArrayField(models.CharField(max_length=12), default=list, blank=True, verbose_name="CPV")
    estado = models.CharField("estado", max_length=20, blank=True)
    eliminado_en_fuente = models.BooleanField("eliminado en la fuente", default=False)
    importe_licitacion = models.DecimalField(
        "importe de licitación", max_digits=16, decimal_places=2, null=True, blank=True
    )
    iva_incluido = models.CharField(
        "IVA", max_length=12, choices=Iva.choices, default=Iva.DESCONOCIDO
    )
    importe_licitacion_con_iva = models.DecimalField(
        "importe de licitación con IVA", max_digits=16, decimal_places=2, null=True, blank=True
    )
    valor_estimado = models.DecimalField(
        "valor estimado", max_digits=16, decimal_places=2, null=True, blank=True
    )
    fecha_publicacion = models.DateField("fecha de publicación", null=True, blank=True)
    fecha_actualizacion_fuente = models.DateTimeField(
        "actualización en la fuente", null=True, blank=True
    )
    url_origen = models.URLField("URL de origen", max_length=1000, blank=True)
    nuts = ArrayField(models.CharField(max_length=10), default=list, blank=True)
    criterio_territorial = models.CharField(
        "criterio territorial",
        max_length=40,
        blank=True,
        help_text="Qué hizo entrar al expediente: NUTS de ejecución, código postal del órgano "
        "o comprador valenciano (TED).",
    )
    servicio_clasificado = models.CharField(
        "servicio", max_length=20, choices=Servicio.choices, blank=True
    )
    alcance_clasificado = models.CharField(
        "alcance", max_length=30, choices=Alcance.choices, blank=True
    )
    metodo_clasificacion = models.CharField(
        "método de clasificación",
        max_length=20,
        choices=Clasificacion.choices,
        default=Clasificacion.SIN_CLASIFICAR,
    )
    regla_clasificacion = models.CharField("regla aplicada", max_length=200, blank=True)
    entrada_atom_id = models.CharField("entry/id", max_length=300, blank=True)
    fichero_origen = models.CharField("fichero de origen", max_length=300, blank=True)
    datos_fuente = models.JSONField("datos de la fuente", default=dict, blank=True)
    lote_importacion = models.ForeignKey(
        LoteImportacion,
        verbose_name="lote de importación",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="expedientes",
    )

    class Meta:
        verbose_name = "expediente"
        verbose_name_plural = "expedientes"
        ordering = ["-fecha_publicacion", "-pk"]
        constraints = [
            models.UniqueConstraint(fields=["fuente", "id_externo"], name="expediente_unico"),
            models.CheckConstraint(
                condition=q_alcance_coherente(True, "servicio_clasificado", "alcance_clasificado")
                | Q(alcance_clasificado="", servicio_clasificado__in=[str(s) for s in Servicio]),
                name="expediente_alcance_coherente",
            ),
        ]
        indexes = [models.Index(fields=["servicio_clasificado"], name="expediente_servicio")]

    def __str__(self):
        return f"{self.get_fuente_display()} {self.numero_expediente or self.id_externo}"


class LoteContrato(models.Model):
    expediente = models.ForeignKey(Expediente, on_delete=models.CASCADE, related_name="lotes")
    numero = models.CharField("número", max_length=50)
    objeto = models.TextField("objeto", blank=True)
    importe = models.DecimalField(
        "importe sin IVA", max_digits=16, decimal_places=2, null=True, blank=True
    )
    cpv = ArrayField(models.CharField(max_length=12), default=list, blank=True)

    class Meta:
        verbose_name = "lote del contrato"
        verbose_name_plural = "lotes del contrato"
        constraints = [
            models.UniqueConstraint(fields=["expediente", "numero"], name="lote_contrato_unico")
        ]

    def __str__(self):
        return f"Lote {self.numero}"


class Adjudicacion(models.Model):
    expediente = models.ForeignKey(
        Expediente, on_delete=models.CASCADE, related_name="adjudicaciones"
    )
    lote = models.ForeignKey(
        LoteContrato, null=True, blank=True, on_delete=models.CASCADE, related_name="adjudicaciones"
    )
    adjudicatario_texto = models.CharField(
        "adjudicatario (literal de la fuente)", max_length=500, blank=True
    )
    adjudicatario_nif = models.CharField("NIF del adjudicatario", max_length=30, blank=True)
    empresa = models.ForeignKey(
        Empresa,
        verbose_name="empresa",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="adjudicaciones",
    )
    importe_adjudicacion = models.DecimalField(
        "importe de adjudicación sin IVA", max_digits=16, decimal_places=2, null=True, blank=True
    )
    importe_pagable = models.DecimalField(
        "importe pagable", max_digits=16, decimal_places=2, null=True, blank=True
    )
    fecha_adjudicacion = models.DateField("fecha de adjudicación", null=True, blank=True)
    fecha_formalizacion = models.DateField("fecha de formalización", null=True, blank=True)
    duracion_texto = models.CharField("duración", max_length=200, blank=True)
    codigo_resultado = models.CharField("código de resultado", max_length=10, blank=True)
    nivel = models.CharField("nivel", max_length=20, choices=NivelEvidencia.choices)

    class Meta:
        verbose_name = "adjudicación"
        verbose_name_plural = "adjudicaciones"

    def __str__(self):
        return self.adjudicatario_texto or "Adjudicatario no publicado"


class ReglaClasificacion(ModeloConFechas):
    """Tabla editable de clasificación de expedientes (docs/04 §1).

    `cpv`: el patrón es un prefijo de CPV y gana el más largo. `palabras`: el patrón es una
    frase que debe aparecer completa en el objeto normalizado (sin tildes ni mayúsculas).
    """

    class Tipo(models.TextChoices):
        CPV = "cpv", "Prefijo CPV"
        PALABRAS = "palabras", "Palabras del objeto"

    tipo = models.CharField("tipo", max_length=10, choices=Tipo.choices)
    patron = models.CharField("patrón", max_length=200)
    patron_normalizado = models.CharField(max_length=200, editable=False)
    servicio = models.CharField("servicio", max_length=20, choices=Servicio.choices)
    alcance = models.CharField("alcance", max_length=30, choices=Alcance.choices, blank=True)
    activa = models.BooleanField("activa", default=True)
    nota = models.CharField("nota", max_length=300, blank=True)

    class Meta:
        verbose_name = "regla de clasificación"
        verbose_name_plural = "reglas de clasificación"
        ordering = ["tipo", "patron"]
        constraints = [
            models.UniqueConstraint(fields=["tipo", "patron_normalizado"], name="regla_unica"),
            models.CheckConstraint(
                condition=q_alcance_coherente(permitir_vacio=False)
                | Q(alcance="", servicio__in=[str(s) for s in Servicio]),
                name="regla_alcance_coherente",
            ),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} «{self.patron}» → {self.servicio}/{self.alcance or '—'}"

    def save(self, *args, **kwargs):
        self.patron_normalizado = (
            self.patron.strip() if self.tipo == self.Tipo.CPV else normalizar_texto(self.patron)
        )
        super().save(*args, **kwargs)
