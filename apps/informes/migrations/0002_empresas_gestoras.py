"""Competidores → empresas gestoras (ADR-010): renombra las claves de los informes guardados y
de las secciones. Las métricas antiguas se conservan para que sus referencias [M..] sigan
validando."""

from django.db import migrations


def renombrar(apps, schema_editor):
    Informe = apps.get_model("informes", "InformeGenerado")
    for informe in Informe.objects.all():
        datos = dict(informe.datos or {})
        if "competidores" in datos:
            datos["empresas"] = datos.pop("competidores")
        for s in informe.secciones or []:
            if str(s.get("clave", "")).startswith("competidor:"):
                s["clave"] = "empresa:" + s["clave"].split(":", 1)[1]
        informe.datos = datos
        informe.save(update_fields=["datos", "secciones"])


class Migration(migrations.Migration):
    dependencies = [("informes", "0001_initial")]

    operations = [migrations.RunPython(renombrar, migrations.RunPython.noop)]
