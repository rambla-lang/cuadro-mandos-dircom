"""Documentos subidos: recortes PDF, valoraciones internas en Word e informes (docs/03)."""

from django.conf import settings
from django.db import models

from apps.entidades.models import Empresa
from apps.nucleo.models import ModeloConFechas


class Documento(ModeloConFechas):
    class Tipo(models.TextChoices):
        RECORTE = "recorte", "Recorte de prensa"
        VALORACION_INTERNA = "valoracion_interna", "Valoración interna"
        PUBLICACIONES = "publicaciones", "Lista de publicaciones"
        DOCUMENTO_MAESTRO = "documento_maestro", "Documento maestro"
        INFORME_SOSTENIBILIDAD = "informe_sostenibilidad", "Informe de sostenibilidad"
        OTRO = "otro", "Otro"

    class Lectura(models.TextChoices):
        TEXTO = "texto", "Texto extraído del archivo"
        PENDIENTE_IA = "pendiente_ia", "Sin capa de texto: pendiente de lectura por IA"
        IA = "ia", "Texto obtenido por IA"
        ERROR = "error", "Error de lectura"

    tipo = models.CharField("tipo", max_length=30, choices=Tipo.choices)
    nombre_archivo = models.CharField("nombre del archivo", max_length=300)
    sha256 = models.CharField("SHA-256", max_length=64, unique=True)
    ruta_almacen = models.CharField(
        "ruta en el almacén",
        max_length=500,
        blank=True,
        help_text="Vacía si no se guardan los originales (ADR-003).",
    )
    paginas = models.PositiveIntegerField("páginas", null=True, blank=True)
    texto_extraido = models.TextField("texto extraído", blank=True)
    texto_obtenido_por_ia = models.BooleanField("texto obtenido por IA", default=False)
    lectura = models.CharField(
        "lectura", max_length=20, choices=Lectura.choices, default=Lectura.TEXTO
    )
    metadatos = models.JSONField("metadatos", default=dict, blank=True)
    empresa_propuesta = models.ForeignKey(
        Empresa,
        verbose_name="empresa indicada al subir",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    subido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="subido por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        verbose_name = "documento"
        verbose_name_plural = "documentos"
        ordering = ["-creado"]

    def __str__(self):
        return self.nombre_archivo


class Fragmento(models.Model):
    documento = models.ForeignKey(Documento, on_delete=models.CASCADE, related_name="fragmentos")
    empresa = models.ForeignKey(
        Empresa, null=True, blank=True, on_delete=models.PROTECT, related_name="fragmentos"
    )
    pagina_inicio = models.PositiveIntegerField(null=True, blank=True)
    pagina_fin = models.PositiveIntegerField(null=True, blank=True)
    texto = models.TextField()

    class Meta:
        verbose_name = "fragmento"
        verbose_name_plural = "fragmentos"

    def __str__(self):
        return f"{self.documento} · {self.empresa or 'sin empresa'}"


class PercepcionInterna(ModeloConFechas):
    """Valoración interna. No es una evidencia ni un nivel: se muestra siempre separada
    (docs/03)."""

    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name="percepciones")
    texto = models.TextField("texto")
    documento_origen = models.ForeignKey(
        Documento, null=True, blank=True, on_delete=models.SET_NULL, related_name="percepciones"
    )
    contraste = models.TextField("contraste con evidencias", blank=True)
    evidencias_relacionadas = models.ManyToManyField(
        "evidencias.Evidencia", blank=True, related_name="percepciones"
    )

    class Meta:
        verbose_name = "percepción interna"
        verbose_name_plural = "percepciones internas"

    def __str__(self):
        return f"{self.empresa} · {self.texto[:60]}"
