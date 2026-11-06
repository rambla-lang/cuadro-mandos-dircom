from django.apps import AppConfig


class ContratacionConfig(AppConfig):
    name = "apps.contratacion"
    label = "contratacion"
    verbose_name = "Contratación pública"

    def ready(self):
        from . import trabajos  # noqa: F401 - registra los tipos de trabajo
