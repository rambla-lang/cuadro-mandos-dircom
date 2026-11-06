"""Informes generados (docs/03, docs/05 §4)."""

from django.conf import settings
from django.db import models


class InformeGenerado(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador: pendiente de revisión"
        PUBLICADO = "publicado", "Publicado"

    titulo = models.CharField("título", max_length=200)
    parametros = models.JSONField("parámetros", default=dict)
    datos = models.JSONField("métricas y evidencias de partida", default=dict)
    secciones = models.JSONField("secciones de texto", default=list)
    estado = models.CharField(
        "estado", max_length=20, choices=Estado.choices, default=Estado.BORRADOR
    )
    archivo_docx = models.CharField("informe Word", max_length=300, blank=True)
    archivo_pptx = models.CharField("presentación", max_length=300, blank=True)
    evidencias_usadas = models.ManyToManyField(
        "evidencias.Evidencia", blank=True, related_name="informes"
    )
    llamadas_ia = models.ManyToManyField("ia.LlamadaIA", blank=True, related_name="informes")
    generado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    publicado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    publicado_en = models.DateTimeField(null=True, blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "informe generado"
        verbose_name_plural = "informes generados"
        ordering = ["-creado"]

    def __str__(self):
        return self.titulo

    @property
    def secciones_con_problemas(self) -> int:
        return sum(1 for s in self.secciones if s.get("problemas"))
