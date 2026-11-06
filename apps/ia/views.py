"""Panel de uso de la IA y lanzamiento de lotes (docs/06, RNF-09)."""

from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.db.models import Count, Sum
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.contratacion.models import Expediente
from apps.documentos.models import Documento
from apps.evidencias.enums import EstadoValidacion
from apps.medios.models import Mencion
from apps.nucleo.models import ElementoRevision, TrabajoIngesta
from apps.nucleo.roles import Rol, rol_requerido
from apps.nucleo.trabajos import lanzar_ejecutor

from .cliente import estado, gasto_mes, modelo_de
from .models import LlamadaIA, PropuestaIA
from .trabajos import TIPO

ROLES = (Rol.ADMINISTRADOR, Rol.ANALISTA)
MAX_LOTE = 50


def candidatos():
    sin_atribuir = (
        Mencion.objects.filter(vinculo_territorial__in=["si", "dudoso"])
        .exclude(atribuciones__estado_validacion=EstadoValidacion.VALIDADA)
        .exclude(pk__in=PropuestaIA.objects.filter(llamada__tarea="T1").values("id_objetivo"))
        .order_by("-fecha_publicacion")
    )
    recortes = Documento.objects.filter(lectura=Documento.Lectura.PENDIENTE_IA).exclude(
        pk__in=PropuestaIA.objects.filter(llamada__tarea="T2").values("id_objetivo")
    )
    expedientes = Expediente.objects.filter(
        pk__in=ElementoRevision.objects.filter(
            tipo=ElementoRevision.Tipo.CLASIFICACION_SERVICIO, estado="pendiente"
        ).values("objeto_id")
    ).exclude(pk__in=PropuestaIA.objects.filter(llamada__tarea="T3").values("id_objetivo"))
    return {"T1": sin_atribuir, "T2": recortes, "T3": expedientes}


@rol_requerido(*ROLES)
def panel(request):
    inicio = timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    mes = LlamadaIA.objects.filter(creado__gte=inicio)
    por_tarea = mes.values("tarea", "modelo").annotate(
        n=Count("pk"),
        entrada=Sum("tokens_entrada"),
        salida=Sum("tokens_salida"),
        coste=Sum("coste_estimado"),
    )
    c = candidatos()
    disponibilidad = {t: estado(t) for t in ("clasificar", "extraer", "redactar")}
    return render(
        request,
        "ia/panel.html",
        {
            "disponibilidad": disponibilidad,
            "modelos": {t: modelo_de(t) or "—" for t in disponibilidad},
            "gasto": gasto_mes(),
            "limite": Decimal(str(settings.IA_LIMITE_MENSUAL_EUR or 0)),
            "por_tarea": por_tarea,
            "llamadas": LlamadaIA.objects.select_related("usuario")[:30],
            "candidatos": {k: v.count() for k, v in c.items()},
            "pendientes": PropuestaIA.objects.filter(estado_revision="pendiente").count(),
            "max_lote": MAX_LOTE,
        },
    )


@rol_requerido(*ROLES)
@require_POST
def lanzar(request):
    tarea = request.POST.get("tarea")
    c = candidatos()
    if tarea not in c:
        messages.error(request, "Tarea no válida.")
        return redirect("ia_panel")
    tipo_modelo = "extraer" if tarea == "T2" else "clasificar"
    disponible, motivo = estado(tipo_modelo)
    if not disponible:
        messages.error(request, f"No se lanza: {motivo}")
        return redirect("ia_panel")
    ids = list(c[tarea].values_list("pk", flat=True)[:MAX_LOTE])
    if not ids:
        messages.info(request, "No hay nada pendiente para esa tarea.")
        return redirect("ia_panel")
    TrabajoIngesta.objects.create(
        tipo=TIPO, parametros={"tarea": tarea, "ids": ids}, usuario=request.user
    )
    lanzar_ejecutor()
    messages.success(request, f"Lote de {len(ids)} en marcha. Las propuestas irán a la bandeja.")
    return redirect("trabajos")
