"""Retirada del módulo de contratación (ADR-010): fuera los elementos de la bandeja y los
trabajos de PLACSP y TED."""

from django.db import migrations, models

TIPOS_RETIRADOS = ["vinculo_organo", "clasificacion_servicio", "adjudicatario_no_resuelto"]
TRABAJOS_RETIRADOS = ["placsp_zip", "ted"]


def borrar_restos(apps, schema_editor):
    ElementoRevision = apps.get_model("nucleo", "ElementoRevision")
    TrabajoIngesta = apps.get_model("nucleo", "TrabajoIngesta")
    ElementoRevision.objects.filter(tipo__in=TIPOS_RETIRADOS).delete()
    TrabajoIngesta.objects.filter(tipo__in=TRABAJOS_RETIRADOS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('nucleo', '0006_alter_elementorevision_tipo'),
    ]

    operations = [
        migrations.RunPython(borrar_restos, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='elementorevision',
            name='tipo',
            field=models.CharField(choices=[('municipio_no_resuelto', 'Municipio no resuelto'), ('operador_no_resuelto', 'Operador no resuelto'), ('nivel_por_decidir', 'Nivel de evidencia por decidir'), ('atribucion_mencion', 'Atribución de mención dudosa'), ('vinculo_territorial', 'Vínculo territorial dudoso'), ('propuesta_ia', 'Propuesta de la IA')], max_length=40, verbose_name='tipo'),
        ),
    ]
