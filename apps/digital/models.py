"""Presencia digital: datos públicos básicos introducidos a mano (docs/04 §8, RF-42)."""

from django.conf import settings
from django.db import models

from apps.entidades.models import Empresa
from apps.nucleo.models import ModeloConFechas


class PerfilDigital(ModeloConFechas):
    class Red(models.TextChoices):
        INSTAGRAM = "instagram", "Instagram"
        LINKEDIN = "linkedin", "LinkedIn"
        X = "x", "X"
        FACEBOOK = "facebook", "Facebook"
        YOUTUBE = "youtube", "YouTube"
        TIKTOK = "tiktok", "TikTok"
        WEB = "web", "Web"

    class Verificada(models.TextChoices):
        SI = "si", "Sí"
        NO = "no", "No"
        DESCONOCIDO = "desconocido", "Desconocido"

    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name="perfiles")
    red = models.CharField("red", max_length=20, choices=Red.choices)
    url = models.URLField("URL", max_length=500, unique=True)
    cuenta_verificada = models.CharField(
        "cuenta verificada",
        max_length=12,
        choices=Verificada.choices,
        default=Verificada.DESCONOCIDO,
    )

    class Meta:
        verbose_name = "perfil digital"
        verbose_name_plural = "perfiles digitales"
        ordering = ["empresa__nombre", "red"]

    def __str__(self):
        return f"{self.empresa} · {self.get_red_display()}"


class ObservacionDigital(ModeloConFechas):
    """CP-12: si un dato no es visible se guarda NULL, nunca 0."""

    perfil = models.ForeignKey(
        PerfilDigital, on_delete=models.CASCADE, related_name="observaciones"
    )
    fecha_observacion = models.DateField("fecha de observación")
    seguidores = models.PositiveIntegerField("seguidores", null=True, blank=True)
    publicaciones_observadas = models.PositiveIntegerField(
        "publicaciones observadas", null=True, blank=True
    )
    periodo_observado = models.CharField("periodo observado", max_length=100, blank=True)
    historico_suficiente = models.BooleanField("histórico suficiente", default=False)
    notas = models.TextField("notas", blank=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        verbose_name = "observación digital"
        verbose_name_plural = "observaciones digitales"
        ordering = ["-fecha_observacion"]
        constraints = [
            models.UniqueConstraint(
                fields=["perfil", "fecha_observacion"], name="observacion_unica_por_dia"
            )
        ]

    def __str__(self):
        return f"{self.perfil} · {self.fecha_observacion}"


class AuditoriaWeb(ModeloConFechas):
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name="auditorias_web")
    url = models.URLField("URL", max_length=500)
    fecha = models.DateField("fecha de observación")
    tono = models.TextField("tono", blank=True)
    contenidos_destacados = models.TextField("contenidos destacados", blank=True)
    usabilidad = models.TextField("usabilidad", blank=True, help_text="Cita lo observado.")
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        verbose_name = "auditoría web"
        verbose_name_plural = "auditorías web"
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.empresa} · {self.fecha}"
