"""Paso 2 (ADR-010): Veolia e Hidraqua pasan a ser empresas gestoras con ficha, dentro del
grupo Veolia. Va en su propia migración: Postgres no admite cambiar datos y la tabla en la misma
transacción."""

from django.db import migrations


def veolia_como_una_mas(apps, schema_editor):
    Empresa = apps.get_model("entidades", "Empresa")
    Grupo = apps.get_model("entidades", "GrupoEmpresarial")
    propias = Empresa.objects.filter(es_propia=True)
    if not propias.exists():
        return
    grupo, _ = Grupo.objects.get_or_create(nombre="Veolia")
    propias.update(con_ficha=True, grupo=grupo)


class Migration(migrations.Migration):
    dependencies = [("entidades", "0002_empresas_gestoras")]

    operations = [migrations.RunPython(veolia_como_una_mas, migrations.RunPython.noop)]
