"""Retirada de T3 (clasificar expedientes) con el módulo de contratación (ADR-010). Se borran
sus propuestas; las llamadas se conservan porque son el registro de gasto."""

from django.db import migrations


def borrar_propuestas_t3(apps, schema_editor):
    PropuestaIA = apps.get_model("ia", "PropuestaIA")
    PropuestaIA.objects.filter(llamada__tarea="T3").delete()


class Migration(migrations.Migration):
    dependencies = [("ia", "0001_initial")]

    operations = [migrations.RunPython(borrar_propuestas_t3, migrations.RunPython.noop)]
