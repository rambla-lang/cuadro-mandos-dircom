"""Settings comunes. Todo lo que cambia entre entornos se lee de variables de entorno (RNF-11)."""

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
    "django_htmx",
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

# IA (ADR-005): modelos por variable de entorno, nunca en el código.
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
IA_MODELO_CLASIFICAR = env("IA_MODELO_CLASIFICAR", default="")
IA_MODELO_EXTRAER = env("IA_MODELO_EXTRAER", default="")
IA_MODELO_REDACTAR = env("IA_MODELO_REDACTAR", default="")
