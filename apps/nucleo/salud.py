from django.contrib.auth.decorators import login_not_required
from django.db import connection
from django.http import JsonResponse


@login_not_required
def salud(request):
    """Comprobación de salud para Render (healthCheckPath): responde si hay base de datos."""
    with connection.cursor() as c:
        c.execute("SELECT 1")
    return JsonResponse({"estado": "ok"})
