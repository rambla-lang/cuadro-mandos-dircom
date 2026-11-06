"""Settings comunes. Todo lo que cambia entre entornos se lee de variables de entorno (RNF-11)."""

from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env", overwrite=False)

SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "django_htmx",
    "axes",
    "apps.nucleo",
    "apps.territorio",
    "apps.entidades",
    "apps.evidencias",
    "apps.contratacion",
    "apps.medios",
    "apps.documentos",
    "apps.digital",
    "apps.ia",
    "apps.informes",
    "apps.cuadro",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # RF-01: toda URL exige sesión salvo las marcadas con @login_not_required.
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    # ADR-009: bloqueo temporal tras intentos fallidos. Debe ir el último.
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.nucleo.context_processors.roles",
            ],
        },
    },
]

DATABASES = {"default": env.db("DATABASE_URL")}

# Usuario propio con email como identificador, desde la primera migración (docs/08).
AUTH_USER_MODEL = "nucleo.Usuario"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "portada"
LOGOUT_REDIRECT_URL = "login"

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",  # ADR-009; debe ir el primero
    "django.contrib.auth.backends.ModelBackend",
]

# Enlaces de invitación y de nueva contraseña (docs/08, P-04 sin SMTP): 72 horas.
PASSWORD_RESET_TIMEOUT = 72 * 3600

# ADR-009: bloqueo temporal por usuario tras 5 fallos seguidos, 15 minutos.
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_LOCKOUT_PARAMETERS = ["username"]
AXES_USERNAME_CALLABLE = "apps.nucleo.acceso.usuario_para_axes"
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = "registration/bloqueado.html"
# ADR-009: se bloquea por usuario, no por IP (detrás del proxy de Render la IP no es fiable
# hasta verificar sus cabeceras en la Fase 8). El aviso W006 se silencia a sabiendas.
SILENCED_SYSTEM_CHECKS = ["axes.W006"]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es"
TIME_ZONE = "Europe/Madrid"  # la interfaz muestra Europe/Madrid; la BD guarda UTC
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# ADR-003: en desarrollo, los archivos subidos van a media/ mediante default_storage.
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Subidas (docs/08)
SUBIDA_MAX_MB = env.int("SUBIDA_MAX_MB", default=50)
# ADR-003 (abierta): si se guardan los PDF y Word originales en MEDIA_ROOT. En el piloto local,
# sí; en Render Free el disco es efímero y se decidirá con ADR-003.
GUARDAR_ORIGINALES = env.bool("GUARDAR_ORIGINALES", default=True)

# IA (ADR-005): modelos por variable de entorno, nunca en el código.
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
IA_MODELO_CLASIFICAR = env("IA_MODELO_CLASIFICAR", default="")
IA_MODELO_EXTRAER = env("IA_MODELO_EXTRAER", default="")
IA_MODELO_REDACTAR = env("IA_MODELO_REDACTAR", default="")
IA_ACTIVADA = env.bool("IA_ACTIVADA", default=True)
IA_LIMITE_MENSUAL_EUR = env.float("IA_LIMITE_MENSUAL_EUR", default=0.0)  # 0 = sin llamadas
# Precios por millón de tokens, introducidos a mano desde la página oficial (docs/06):
# {"<modelo>": {"entrada": 0.0, "salida": 0.0}}
IA_PRECIOS_JSON = env.json("IA_PRECIOS_JSON", default={})
# Reintento automático en otro modelo si el elegido rechaza la petición (parámetro
# «fallbacks» de la API, beta). No aplica a la familia Haiku.
IA_FALLBACKS = env.bool("IA_FALLBACKS", default=True)
