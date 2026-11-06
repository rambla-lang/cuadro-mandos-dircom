"""Juego de evaluación de T1 (docs/06). Llama a la API real: solo a mano, con `-m externo`.

Prepara la plantilla con `manage.py preparar_eval_menciones`, anota las dos columnas y ejecuta
`uv run pytest -m externo tests/eval`. Anota el resultado en apps/ia/prompts/CHANGELOG.md.
"""

import csv
from pathlib import Path

import pytest
from django.conf import settings

FICHERO = Path(settings.MEDIA_ROOT) / "eval" / "menciones_t1.csv"


@pytest.mark.externo
@pytest.mark.django_db(transaction=True)
def test_precision_t1():
    if not FICHERO.exists():
        pytest.skip("Falta media/eval/menciones_t1.csv (manage.py preparar_eval_menciones).")
    from apps.ia.tareas import t1_atribuir_mencion
    from apps.medios.models import Mencion

    filas = [
        f
        for f in csv.DictReader(FICHERO.open(encoding="utf-8-sig"))
        if f.get("vinculo_correcto (si/no/dudoso)")
    ]
    if not filas:
        pytest.skip("El juego de evaluación está sin anotar (P-12).")
    aciertos_vinculo = aciertos_empresas = 0
    for f in filas:
        p = t1_atribuir_mencion(Mencion.objects.get(pk=f["mencion_id"])).propuesta
        aciertos_vinculo += p["vinculo_territorial"] == f["vinculo_correcto (si/no/dudoso)"].strip()
        esperadas = {
            e.strip().lower()
            for e in f["empresas_correctas (nombres separados por ;)"].split(";")
            if e.strip()
        }
        from apps.entidades.models import Empresa

        propuestas = {
            n.lower()
            for n in Empresa.objects.filter(
                pk__in=[e["empresa_id"] for e in p["empresas"]]
            ).values_list("nombre", flat=True)
        }
        aciertos_empresas += propuestas == esperadas
    n = len(filas)
    print(f"T1: vínculo {aciertos_vinculo}/{n}, empresas exactas {aciertos_empresas}/{n}")
