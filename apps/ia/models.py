"""Registro de llamadas y propuestas de IA (docs/03, docs/06)."""

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import models


class LlamadaIA(models.Model):
    class Estado(models.TextChoices):
        OK = "ok", "Correcta"
        ERROR = "error", "Error"
        BLOQUEADA = "bloqueada", "Bloqueada (IA desactivada o límite mensual)"
        RECHAZADA = "rechazada", "Rechazada por el modelo"

    tarea = models.CharField("tarea", max_length=10)
    modelo = models.CharField("modelo", max_length=100, blank=True)
    version_prompt = models.CharField("versión del prompt", max_length=40, blank=True)
    tokens_entrada = models.PositiveIntegerField("tokens de entrada", default=0)
    tokens_salida = models.PositiveIntegerField("tokens de salida", default=0)
    tokens_cache_lectura = models.PositiveIntegerField("tokens leídos de caché", default=0)
    coste_estimado = models.DecimalField(
        "coste estimado (€)", max_digits=10, decimal_places=5, default=0
    )
    estado = models.CharField("estado", max_length=20, choices=Estado.choices)
    error = models.TextField("error", blank=True)
    id_peticion = models.CharField("id de la petición", max_length=100, blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    objeto_tipo = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.SET_NULL)
    objeto_id = models.PositiveBigIntegerField(null=True, blank=True)
    creado = models.DateTimeField("fecha", auto_now_add=True)

    class Meta:
        verbose_name = "llamada a la IA"
        verbose_name_plural = "llamadas a la IA"
        ordering = ["-creado"]

    def __str__(self):
        return f"{self.tarea} · {self.modelo} · {self.get_estado_display()}"


class PropuestaIA(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        ACEPTADA = "aceptada", "Aceptada"
        CORREGIDA = "corregida", "Corregida"
        RECHAZADA = "rechazada", "Rechazada"

    llamada = models.ForeignKey(LlamadaIA, on_delete=models.PROTECT, related_name="propuestas")
    tipo_objetivo = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    id_objetivo = models.PositiveBigIntegerField()
    propuesta = models.JSONField("propuesta (validada con su esquema)")
    estado_revision = models.CharField(
        "estado", max_length=20, choices=Estado.choices, default=Estado.PENDIENTE
    )
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    revisado_en = models.DateTimeField(null=True, blank=True)
    comentario = models.TextField("comentario", blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "propuesta de la IA"
        verbose_name_plural = "propuestas de la IA"
        ordering = ["-creado"]

    def __str__(self):
        return f"{self.llamada.tarea} · {self.get_estado_revision_display()}"

    @property
    def objetivo(self):
        return self.tipo_objetivo.model_class().objects.filter(pk=self.id_objetivo).first()
