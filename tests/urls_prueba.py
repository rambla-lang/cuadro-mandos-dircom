"""URLconf de prueba: las rutas reales más una vista de importación ficticia para CP-11
(los importadores reales llegan en las Fases 3 y 4)."""

from django.http import HttpResponse
from django.urls import path
from django.views import View

from apps.nucleo.roles import Rol, RolRequeridoMixin, rol_requerido
from config.urls import urlpatterns as urls_reales


@rol_requerido(Rol.ADMINISTRADOR, Rol.ANALISTA)
def importar_ficticio(request):
    return HttpResponse("importado")


class ImportarFicticioView(RolRequeridoMixin, View):
    roles_requeridos = (Rol.ADMINISTRADOR, Rol.ANALISTA)

    def post(self, request):
        return HttpResponse("importado")


urlpatterns = [
    *urls_reales,
    path("prueba/importar/", importar_ficticio),
    path("prueba/importar-clase/", ImportarFicticioView.as_view()),
]
