"""Núcleo de trazabilidad (docs/03): toda cifra visible sale de evidencias con fuente y nivel."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q

from apps.entidades.models import Empresa
from apps.nucleo.models import LoteImportacion, ModeloConFechas
from apps.nucleo.texto import normalizar_texto
from apps.territorio.models import Municipio

from .enums import (
    NIVELES_CONFIRMADOS,
    Alcance,
    CategoriaEvidencia,
    EstadoValidacion,
    Gestion,
    NivelEvidencia,
    Origen,
    Servicio,
    TipoFuente,
    Vigencia,
    q_alcance_coherente,
)

MAX_PALABRAS_EXTRACTO = 300


class Fuente(ModeloConFechas):
    tipo = models.CharField("tipo", max_length=30, choices=TipoFuente.choices)
    nombre = models.CharField("nombre", max_length=200)
    dominio = models.CharField("dominio", max_length=200, blank=True)
    url_base = models.URLField("URL base", max_length=500, blank=True)

    class Meta:
        verbose_name = "fuente"
        verbose_name_plural = "fuentes"
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(fields=["tipo", "nombre"], name="fuente_unica_tipo_nombre"),
        ]

    def __str__(self):
        return self.nombre


MARCA_VALIDACION = "Validado por DIRCOM"
"""Se muestra junto al nivel cuando una persona ha validado la evidencia. No cambia el nivel:
el nivel dice qué tipo de fuente respalda el dato; la marca, que la DIRCOM lo ha revisado."""


class Evidencia(ModeloConFechas):
    codigo = models.CharField("código", max_length=12, unique=True, editable=False, null=True)  # noqa: DJ001 (NULL hasta asignar E-xxxxxx; único)
    categoria = models.CharField("categoría", max_length=30, choices=CategoriaEvidencia.choices)
    titulo = models.CharField("título", max_length=500)
    extracto = models.TextField(
        "extracto",
        blank=True,
        help_text=f"Máximo {MAX_PALABRAS_EXTRACTO} palabras; no se guardan artículos completos.",
    )
    url_origen = models.URLField("URL de origen", max_length=1000, blank=True)
    fecha_publicacion = models.DateField("fecha de publicación", null=True, blank=True)
    fecha_evento = models.DateField(
        "fecha del evento",
        null=True,
        blank=True,
        help_text="Nunca sustituye a la fecha de publicación.",
    )
    fecha_consulta = models.DateField("fecha de consulta", null=True, blank=True)
    fuente = models.ForeignKey(
        Fuente, verbose_name="fuente", on_delete=models.PROTECT, related_name="evidencias"
    )
    empresas = models.ManyToManyField(
        Empresa,
        verbose_name="empresas",
        blank=True,
        through="EvidenciaEmpresa",
        related_name="evidencias",
    )
    municipios = models.ManyToManyField(
        Municipio,
        verbose_name="municipios",
        blank=True,
        through="EvidenciaMunicipio",
        related_name="evidencias",
    )
    servicio = models.CharField("servicio", max_length=20, choices=Servicio.choices, blank=True)
    alcance = models.CharField("alcance", max_length=30, choices=Alcance.choices, blank=True)
    nivel = models.CharField("nivel", max_length=20, choices=NivelEvidencia.choices)
    estado_validacion = models.CharField(
        "estado de validación",
        max_length=20,
        choices=EstadoValidacion.choices,
        default=EstadoValidacion.BORRADOR,
    )
    origen = models.CharField("origen", max_length=20, choices=Origen.choices)
    lote_importacion = models.ForeignKey(
        LoteImportacion,
        verbose_name="lote de importación",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="evidencias",
    )
    tratamiento_limites = models.TextField("tratamiento de límites", blank=True)
    datos_extra = models.JSONField("datos adicionales", default=dict, blank=True)
    clave_importacion = models.CharField(  # noqa: DJ001 (NULL si no viene de un importador; único)
        "clave de importación",
        max_length=80,
        unique=True,
        null=True,
        blank=True,
        editable=False,
        help_text="Clave natural del importador (docs/04): reimportar no duplica.",
    )
    validado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="validado por",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="evidencias_validadas",
    )
    validado_en = models.DateTimeField("validado en", null=True, blank=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="creado por",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="evidencias_creadas",
    )

    class Meta:
        verbose_name = "evidencia"
        verbose_name_plural = "evidencias"
        ordering = ["-fecha_publicacion", "-pk"]
        permissions = [("validar_evidencia", "Puede validar evidencias")]
        constraints = [
            models.CheckConstraint(
                condition=~Q(nivel=NivelEvidencia.OFICIAL) | ~Q(url_origen=""),
                name="evidencia_oficial_exige_url",
                violation_error_message="El nivel «oficial» exige una URL de origen oficial.",
            ),
            models.CheckConstraint(
                condition=~Q(
                    origen=Origen.IA,
                    nivel__in=[str(n) for n in NIVELES_CONFIRMADOS],
                    validado_por__isnull=True,
                ),
                name="evidencia_ia_no_confirma_sola",
                violation_error_message="Una evidencia propuesta por la IA no puede quedar "
                "confirmada sin que una persona la valide.",
            ),
            models.CheckConstraint(
                condition=~Q(estado_validacion=EstadoValidacion.VALIDADA)
                | Q(validado_por__isnull=False, validado_en__isnull=False),
                name="evidencia_validada_con_responsable",
                violation_error_message="Una evidencia validada exige quién y cuándo la validó.",
            ),
            models.CheckConstraint(
                condition=q_alcance_coherente(permitir_vacio=True)
                | Q(alcance="", servicio__in=[str(s) for s in Servicio]),
                name="evidencia_alcance_coherente",
                violation_error_message="El alcance no corresponde al servicio.",
            ),
        ]

    def __str__(self):
        return f"{self.codigo or 'E-(nueva)'} · {self.titulo[:80]}"

    @property
    def validada_por_dircom(self) -> bool:
        return self.estado_validacion == EstadoValidacion.VALIDADA and bool(self.validado_por_id)

    def clean(self):
        super().clean()
        if self.extracto and len(self.extracto.split()) > MAX_PALABRAS_EXTRACTO:
            raise ValidationError(
                {"extracto": f"El extracto supera las {MAX_PALABRAS_EXTRACTO} palabras."}
            )

    def save(self, *args, **kwargs):
        with transaction.atomic():
            super().save(*args, **kwargs)
            if not self.codigo:
                self.codigo = f"E-{self.pk:06d}"
                type(self).objects.filter(pk=self.pk).update(codigo=self.codigo)


class EvidenciaEmpresa(models.Model):
    evidencia = models.ForeignKey(Evidencia, on_delete=models.CASCADE)
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT)

    class Meta:
        verbose_name = "empresa de la evidencia"
        verbose_name_plural = "empresas de la evidencia"
        constraints = [
            models.UniqueConstraint(
                fields=["evidencia", "empresa"], name="evidencia_empresa_unica"
            ),
        ]

    def __str__(self):
        return f"{self.evidencia_id} · {self.empresa_id}"


class EvidenciaMunicipio(models.Model):
    evidencia = models.ForeignKey(Evidencia, on_delete=models.CASCADE)
    municipio = models.ForeignKey(Municipio, on_delete=models.PROTECT)

    class Meta:
        verbose_name = "municipio de la evidencia"
        verbose_name_plural = "municipios de la evidencia"
        constraints = [
            models.UniqueConstraint(
                fields=["evidencia", "municipio"], name="evidencia_municipio_unico"
            ),
        ]

    def __str__(self):
        return f"{self.evidencia_id} · {self.municipio_id}"


ORDEN_NIVEL = {
    NivelEvidencia.OFICIAL: 5,
    NivelEvidencia.PRENSA: 4,
    NivelEvidencia.EMPRESA: 3,
    NivelEvidencia.PARCIAL: 2,
    NivelEvidencia.NO_LOCALIZADO: 1,
}


def mejor_nivel(niveles) -> str | None:
    niveles = [n for n in niveles if n]
    return max(niveles, key=lambda n: ORDEN_NIVEL[n]) if niveles else None


class PrestacionServicio(ModeloConFechas):
    """Vista curada que alimenta el mapa (docs/03 y docs/05 §1).

    `empresa` es el operador resuelto contra el catálogo; `operador_texto` guarda el literal de
    la fuente (por ejemplo, «UTE Netial (FCC Medio Ambiente + PreZero)») y se muestra mientras
    el operador está pendiente de resolver en la bandeja. Un alcance vacío significa «sin
    especificar» (la fuente no lo concreta).
    """

    municipio = models.ForeignKey(
        Municipio, verbose_name="municipio", on_delete=models.PROTECT, related_name="prestaciones"
    )
    servicio = models.CharField("servicio", max_length=20, choices=Servicio.choices)
    alcance = models.CharField(
        "alcance",
        max_length=30,
        choices=Alcance.choices,
        blank=True,
        help_text="Vacío: la fuente no concreta el alcance.",
    )
    empresa = models.ForeignKey(
        Empresa,
        verbose_name="operador",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="prestaciones",
        help_text="Vacío si es gestión directa, no se ha localizado o está pendiente de resolver.",
    )
    operador_texto = models.CharField(
        "operador según la fuente",
        max_length=300,
        blank=True,
        help_text="Literal de la fuente, sin reinterpretar.",
    )
    operador_normalizado = models.CharField(max_length=300, blank=True, editable=False)
    gestion = models.CharField("gestión", max_length=20, choices=Gestion.choices)
    anio_referencia = models.PositiveSmallIntegerField("año de referencia", null=True, blank=True)
    vigencia_confirmada = models.CharField(
        "vigencia confirmada", max_length=12, choices=Vigencia.choices, default=Vigencia.DESCONOCIDA
    )
    nivel = models.CharField("nivel", max_length=20, choices=NivelEvidencia.choices)
    evidencias = models.ManyToManyField(
        Evidencia, verbose_name="evidencias", blank=True, related_name="prestaciones"
    )

    class Meta:
        verbose_name = "prestación de servicio"
        verbose_name_plural = "prestaciones de servicio"
        ordering = ["municipio__nombre_oficial", "servicio", "alcance"]
        constraints = [
            models.UniqueConstraint(
                fields=["municipio", "servicio", "alcance", "empresa"],
                condition=Q(empresa__isnull=False),
                name="prestacion_unica_empresa",
                violation_error_message="Ya existe esa prestación para el municipio.",
            ),
            models.UniqueConstraint(
                fields=["municipio", "servicio", "alcance", "operador_normalizado"],
                condition=Q(empresa__isnull=True),
                name="prestacion_unica_sin_empresa",
                violation_error_message="Ya existe esa prestación para el municipio.",
            ),
            models.CheckConstraint(
                condition=q_alcance_coherente(permitir_vacio=False)
                | Q(alcance="", servicio__in=[str(s) for s in Servicio]),
                name="prestacion_alcance_coherente",
                violation_error_message="El alcance no corresponde al servicio.",
            ),
        ]

    def __str__(self):
        alcance = self.get_alcance_display() or "alcance sin especificar"
        return f"{self.municipio} · {self.get_servicio_display()} · {alcance}"

    def save(self, *args, **kwargs):
        self.operador_normalizado = normalizar_texto(self.operador_texto)
        super().save(*args, **kwargs)

    @property
    def nombre_operador(self) -> str:
        if self.empresa_id:
            return self.empresa.nombre
        return self.operador_texto or self.get_gestion_display()

    def recalcular(self):
        """Nivel y año a partir de sus evidencias no rechazadas.

        Manda el mejor nivel entre las validadas; si no hay ninguna validada, el mejor entre
        los borradores (la prestación se considera entonces borrador).
        """
        evidencias = list(
            self.evidencias.exclude(estado_validacion=EstadoValidacion.RECHAZADA).values_list(
                "nivel", "estado_validacion", "datos_extra"
            )
        )
        validadas = [n for n, e, _ in evidencias if e == EstadoValidacion.VALIDADA]
        nivel = mejor_nivel(validadas) or mejor_nivel([n for n, _, _ in evidencias])
        if nivel:
            self.nivel = nivel
        anios = [d.get("anio") for _, _, d in evidencias if isinstance(d.get("anio"), int)]
        if anios:
            self.anio_referencia = max(anios)
        self.save()


class PlantillaImportacion(ModeloConFechas):
    """Correspondencia de columnas y valores guardable del asistente (docs/04 §9)."""

    nombre = models.CharField("nombre", max_length=200, unique=True)
    tipo = models.CharField("tipo", max_length=50, default="tabla_municipal")
    descripcion = models.TextField("descripción", blank=True)
    configuracion = models.JSONField("configuración", default=dict)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="creado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        verbose_name = "plantilla de importación"
        verbose_name_plural = "plantillas de importación"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre
