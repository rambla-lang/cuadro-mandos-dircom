from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
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
