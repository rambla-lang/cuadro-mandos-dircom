from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone


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
