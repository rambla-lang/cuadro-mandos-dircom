"""Paso 3 (ADR-010): fuera «empresa propia» y la acotación pasa a ser de empresa gestora."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("entidades", "0003_veolia_como_una_mas")]

    operations = [
        migrations.RemoveField(model_name="empresa", name="es_propia"),
        migrations.RenameModel(old_name="AcotacionCompetidor", new_name="AcotacionEmpresa"),
    ]
