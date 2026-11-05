from django.db.models import Q
from django.shortcuts import render

from apps.nucleo.texto import normalizar_texto

from .models import Municipio, Provincia


def municipios(request):
    """Lista de municipios cargados, para todos los roles."""
    provincia = request.GET.get("provincia", "")
    q = request.GET.get("q", "").strip()
    qs = Municipio.objects.select_related("provincia").order_by(
        "provincia__codigo_ine", "nombre_oficial"
    )
    if provincia:
        qs = qs.filter(provincia__codigo_ine=provincia)
    if q:
        qs = qs.filter(
            Q(nombres_normalizados__contains=[normalizar_texto(q)]) | Q(nombre_oficial__icontains=q)
        )
    return render(
        request,
        "territorio/municipios.html",
        {
            "municipios": list(qs),
            "provincias": Provincia.objects.all(),
            "provincia": provincia,
            "q": q,
        },
    )
