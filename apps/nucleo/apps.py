from django.apps import AppConfig
from django.db.models.signals import post_migrate


class NucleoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.nucleo"
    label = "nucleo"
    verbose_name = "Núcleo"

    def ready(self):
        from .roles import sincronizar_roles

        post_migrate.connect(sincronizar_roles, dispatch_uid="nucleo_sincronizar_roles")
