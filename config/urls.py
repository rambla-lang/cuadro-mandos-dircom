from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from apps.contratacion import views as contratacion_views
from apps.cuadro import views as cuadro_views
from apps.digital import views as digital_views
from apps.documentos import views as documentos_views
from apps.evidencias import views as evidencias_views
from apps.evidencias import views_importacion, views_revision
from apps.ia import views as ia_views
from apps.informes import views as informes_views
from apps.medios import views as medios_views
from apps.nucleo import views as nucleo_views
from apps.territorio import views as territorio_views

urlpatterns = [
    path("", nucleo_views.portada, name="portada"),
    path("acceso/", auth_views.LoginView.as_view(), name="login"),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),
    path("usuarios/", nucleo_views.usuarios, name="usuarios"),
    path("usuarios/invitar/", nucleo_views.invitar, name="invitar"),
    path("usuarios/<int:pk>/enlace/", nucleo_views.generar_enlace, name="generar_enlace"),
    path(
        "invitacion/<uidb64>/<token>/",
        nucleo_views.InvitacionConfirmarView.as_view(),
        name="invitacion_confirmar",
    ),
    path(
        "invitacion/completada/",
        nucleo_views.InvitacionCompletadaView.as_view(),
        name="invitacion_completada",
    ),
    path("municipios/", territorio_views.municipios, name="municipios"),
    path("municipios/<str:codigo>/", cuadro_views.municipio_panel, name="municipio"),
    path("mapa/", cuadro_views.mapa, name="mapa"),
    path(
        "mapa/exportar.<str:formato>",
        cuadro_views.exportar_tabla,
        name="exportar_tabla",
    ),
    path("importar/", views_importacion.importar, name="importar"),
    path("importar/tabla-municipal/", views_importacion.tabla_subir, name="importar_tabla"),
    path(
        "importar/tabla-municipal/hoja/", views_importacion.tabla_hoja, name="importar_tabla_hoja"
    ),
    path(
        "importar/tabla-municipal/columnas/",
        views_importacion.tabla_columnas,
        name="importar_tabla_columnas",
    ),
    path(
        "importar/tabla-municipal/valores/",
        views_importacion.tabla_valores,
        name="importar_tabla_valores",
    ),
    path(
        "importar/tabla-municipal/confirmar/",
        views_importacion.tabla_confirmar,
        name="importar_tabla_confirmar",
    ),
    path("importar/lotes/<int:pk>/", views_importacion.lote, name="lote_importacion"),
    path("contratacion/", contratacion_views.expedientes, name="expedientes"),
    path("contratacion/<int:pk>/", contratacion_views.expediente, name="expediente"),
    path(
        "contratacion/actualizar/",
        contratacion_views.actualizar,
        name="actualizar_contratacion",
    ),
    path("trabajos/", contratacion_views.trabajos, name="trabajos"),
    path("trabajos/<int:pk>/", contratacion_views.trabajo, name="trabajo"),
    path("medios/", medios_views.visibilidad, name="visibilidad"),
    path("medios/piezas/", medios_views.piezas, name="piezas"),
    path("medios/menciones/", medios_views.menciones, name="menciones"),
    path("medios/menciones/<int:pk>/", medios_views.mencion, name="mencion"),
    path(
        "importar/brandwatch/",
        medios_views.importar_brandwatch_vista,
        name="importar_brandwatch",
    ),
    path("importar/recortes/", medios_views.importar_recortes, name="importar_recortes"),
    path("ia/", ia_views.panel, name="ia_panel"),
    path("ia/lanzar/", ia_views.lanzar, name="ia_lanzar"),
    path("competidores/", cuadro_views.competidores, name="competidores"),
    path("competidores/<int:pk>/", cuadro_views.ficha_competidor, name="ficha"),
    path("evidencias/", evidencias_views.lista, name="evidencias"),
    path("evidencias/nueva/", evidencias_views.editar, name="evidencia_nueva"),
    path("evidencias/<int:pk>/", evidencias_views.detalle, name="evidencia"),
    path("evidencias/<int:pk>/editar/", evidencias_views.editar, name="evidencia_editar"),
    path("evidencias/<int:pk>/validar/", evidencias_views.validar, name="evidencia_validar"),
    path("digital/", digital_views.panel, name="digital"),
    path("digital/nuevo/", digital_views.nuevo, name="digital_nuevo"),
    path("importar/word/", documentos_views.importar_word, name="importar_word"),
    path("informes/", informes_views.lista, name="informes"),
    path("informes/nuevo/", informes_views.nuevo, name="informe_nuevo"),
    path("informes/<int:pk>/", informes_views.detalle, name="informe"),
    path(
        "informes/<int:pk>/descargar.<str:formato>",
        informes_views.descargar,
        name="informe_descargar",
    ),
    path("revision/", views_revision.bandeja, name="revision"),
    path("revision/<int:pk>/", views_revision.elemento, name="revision_elemento"),
    path("admin/", admin.site.urls),
]
