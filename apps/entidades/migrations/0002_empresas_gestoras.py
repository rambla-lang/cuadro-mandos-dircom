"""Competidores → empresas gestoras (ADR-010), paso 1: renombra el campo."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("entidades", "0001_initial")]

    operations = [
        migrations.RemoveConstraint(model_name="empresa", name="empresa_propia_no_es_competidor"),
        migrations.RenameField(
            model_name="empresa", old_name="es_competidor_seguido", new_name="con_ficha"
        ),
    ]
