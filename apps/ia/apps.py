from django.apps import AppConfig


class IaConfig(AppConfig):
    name = "apps.ia"
    label = "ia"
    verbose_name = "IA"

    def ready(self):
        from . import trabajos  # noqa: F401 - registra el tipo de trabajo
