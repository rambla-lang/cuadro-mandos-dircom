from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

from .texto import normalizar_texto


def normalizar_email(email: str) -> str:
    """El email identifica al usuario: se guarda sin espacios y en minúsculas."""
    return (email or "").strip().lower()


class UsuarioManager(BaseUserManager):
    use_in_migrations = True

    def _crear(self, email, password, **extra):
        email = normalizar_email(email)
        if not email:
            raise ValueError("El email es obligatorio.")
        usuario = self.model(email=email, **extra)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._crear(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra["is_staff"] = True
        extra["is_superuser"] = True
        return self._crear(email, password, **extra)

    def get_by_natural_key(self, email):
        return self.get(email=normalizar_email(email))


class Usuario(AbstractBaseUser, PermissionsMixin):
    """Usuario de la aplicación. Inicio de sesión con email (docs/08). Sin registro público."""

    email = models.EmailField("email", unique=True)
    nombre = models.CharField("nombre", max_length=150, blank=True)
    is_active = models.BooleanField("activo", default=True)
    is_staff = models.BooleanField("acceso al panel de administración", default=False)
    fecha_alta = models.DateTimeField("fecha de alta", default=timezone.now)

    objects = UsuarioManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        ordering = ["email"]

    def __str__(self):
        return self.email

    def clean(self):
        super().clean()
        self.email = normalizar_email(self.email)

    def save(self, *args, **kwargs):
        self.email = normalizar_email(self.email)
        super().save(*args, **kwargs)


class ModeloConFechas(models.Model):
    """Campos comunes de docs/03: creado y modificado."""

    creado = models.DateTimeField("creado", auto_now_add=True)
    modificado = models.DateTimeField("modificado", auto_now=True)

    class Meta:
        abstract = True


class LoteImportacion(models.Model):
    """Una ejecución de un importador (docs/03). Todo registro importado apunta a su lote."""

    tipo = models.CharField("tipo", max_length=50)
    parametros = models.JSONField("parámetros", default=dict, blank=True)
    archivo_sha256 = models.CharField("SHA-256 del archivo", max_length=64, blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="usuario",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="lotes_importacion",
    )
    inicio = models.DateTimeField("inicio", default=timezone.now)
    fin = models.DateTimeField("fin", null=True, blank=True)
    leidos = models.PositiveIntegerField("leídos", default=0)
    nuevos = models.PositiveIntegerField("nuevos", default=0)
    actualizados = models.PositiveIntegerField("actualizados", default=0)
    descartados = models.PositiveIntegerField("descartados", default=0)
    errores = models.PositiveIntegerField("errores", default=0)
    log = models.TextField("registro", blank=True)

    class Meta:
        verbose_name = "lote de importación"
        verbose_name_plural = "lotes de importación"
        ordering = ["-inicio"]
        permissions = [("importar_datos", "Puede importar datos")]

    def __str__(self):
        return f"{self.tipo} · {self.inicio:%d/%m/%Y %H:%M}"

    def anotar(self, linea: str):
        self.log = f"{self.log}{linea}\n"


class RegistroAuditoria(models.Model):
    """RF-04: importaciones, validaciones, ediciones de evidencias, informes y altas de usuario."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="usuario",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    usuario_email = models.CharField("email del usuario", max_length=254, blank=True)
    accion = models.CharField("acción", max_length=60)
    objeto_tipo = models.ForeignKey(
        ContentType,
        verbose_name="tipo de objeto",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    objeto_id = models.CharField("id del objeto", max_length=64, blank=True)
    objeto_repr = models.CharField("objeto", max_length=300, blank=True)
    antes = models.JSONField("antes", null=True, blank=True)
    despues = models.JSONField("después", null=True, blank=True)
    fecha = models.DateTimeField("fecha", auto_now_add=True)

    class Meta:
        verbose_name = "registro de auditoría"
        verbose_name_plural = "registro de auditoría"
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.fecha:%d/%m/%Y %H:%M} · {self.usuario_email} · {self.accion}"


class ElementoRevision(ModeloConFechas):
    """Bandeja de revisión (RF-60, docs/05 §5): lo que un importador no puede decidir solo.

    `datos` guarda lo necesario para completar la operación al resolverlo (por ejemplo, la
    fila normalizada de una tabla municipal cuyo municipio no se ha podido resolver).
    """

    class Tipo(models.TextChoices):
        MUNICIPIO_NO_RESUELTO = "municipio_no_resuelto", "Municipio no resuelto"
        OPERADOR_NO_RESUELTO = "operador_no_resuelto", "Operador no resuelto"
        NIVEL_POR_DECIDIR = "nivel_por_decidir", "Nivel de evidencia por decidir"

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        ACEPTADO = "aceptado", "Aceptado"
        CORREGIDO = "corregido", "Corregido"
        RECHAZADO = "rechazado", "Rechazado"

    tipo = models.CharField("tipo", max_length=40, choices=Tipo.choices)
    estado = models.CharField(
        "estado", max_length=20, choices=Estado.choices, default=Estado.PENDIENTE
    )
    clave = models.CharField(
        "clave", max_length=120, unique=True, help_text="Evita duplicar el elemento al reimportar."
    )
    texto = models.CharField("dato original", max_length=500)
    texto_normalizado = models.CharField(max_length=500, editable=False)
    motivo = models.TextField("motivo")
    propuesta = models.JSONField("propuesta", default=dict, blank=True)
    datos = models.JSONField("datos", default=dict, blank=True)
    objeto_tipo = models.ForeignKey(
        ContentType, verbose_name="tipo de objeto", null=True, blank=True, on_delete=models.CASCADE
    )
    objeto_id = models.PositiveBigIntegerField("id del objeto", null=True, blank=True)
    lote_importacion = models.ForeignKey(
        LoteImportacion,
        verbose_name="lote de importación",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="elementos_revision",
    )
    resuelto_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="resuelto por",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    resuelto_en = models.DateTimeField("resuelto en", null=True, blank=True)
    resolucion = models.JSONField("resolución", default=dict, blank=True)
    comentario = models.TextField("comentario", blank=True)

    class Meta:
        verbose_name = "elemento de revisión"
        verbose_name_plural = "bandeja de revisión"
        ordering = ["tipo", "texto_normalizado", "pk"]
        indexes = [models.Index(fields=["estado", "tipo"], name="revision_estado_tipo")]

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.texto[:80]}"

    def save(self, *args, **kwargs):
        self.texto_normalizado = normalizar_texto(self.texto)[:500]
        super().save(*args, **kwargs)

    @property
    def objeto(self):
        if not self.objeto_tipo_id or not self.objeto_id:
            return None
        modelo = self.objeto_tipo.model_class()
        return modelo.objects.filter(pk=self.objeto_id).first()
