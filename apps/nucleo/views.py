from django.shortcuts import render


def portada(request):
    """Portada provisional (Fase 0). Exige sesión por LoginRequiredMiddleware."""
    return render(request, "nucleo/portada.html")
