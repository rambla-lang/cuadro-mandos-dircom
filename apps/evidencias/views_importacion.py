"""Asistente de importación de tablas municipales (docs/04 §9). Las vistas solo orquestan:
la lógica está en importers/tabla_municipal.py."""

import uuid
from pathlib import Path

from django.contrib import messages
from django.core.files.storage import default_storage
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.nucleo.models import ElementoRevision, LoteImportacion
from apps.nucleo.roles import Rol, rol_requerido

from .forms import (
    OPCIONES_NIVEL,
    BloqueFormSet,
    ColumnasForm,
    HojaForm,
    SubidaForm,
    opciones_servicio_alcance,
)
from .importers.tabla_municipal import (
    DECIDIR,
    TIPO_LOTE,
    FormatoTablaError,
    hojas,
    importar_tabla,
    leer_tabla,
    proponer_nivel,
    valores_distintos,
)
from .models import PlantillaImportacion

CLAVE_SESION = "importacion_tabla"
ROLES = (Rol.ADMINISTRADOR, Rol.ANALISTA)
CAMPOS_BLOQUE = (
    "servicio",
    "alcance",
    "columna_servicio",
    "columna_operador",
    "columna_detalle",
    "columna_figura",
    "columna_fuente",
    "columna_anio",
    "columna_nivel",
    "nivel_por_defecto",
    "columnas_extra",
)


def _estado(request) -> dict | None:
    return request.session.get(CLAVE_SESION)


def _guardar_estado(request, estado: dict):
    request.session[CLAVE_SESION] = estado
    request.session.modified = True


def _ruta(estado) -> Path:
    return Path(default_storage.path(estado["almacen"]))


def _descartar(request):
    estado = request.session.pop(CLAVE_SESION, None)
    if estado and default_storage.exists(estado["almacen"]):
        default_storage.delete(estado["almacen"])


@rol_requerido(*ROLES)
def importar(request):
    lotes = LoteImportacion.objects.filter(tipo=TIPO_LOTE).select_related("usuario")[:20]
    return render(request, "evidencias/importar.html", {"lotes": lotes})


@rol_requerido(*ROLES)
@require_http_methods(["GET", "POST"])
def tabla_subir(request):
    form = SubidaForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        _descartar(request)
        archivo = form.cleaned_data["archivo"]
        sufijo = Path(archivo.name).suffix.lower()
        almacen = default_storage.save(
            f"importaciones/pendientes/{uuid.uuid4().hex}{sufijo}", archivo
        )
        plantilla = form.cleaned_data["plantilla"]
        config = dict(plantilla.configuracion) if plantilla else {}
        estado = {"almacen": almacen, "nombre": archivo.name, "config": config}
        _guardar_estado(request, estado)
        if sufijo == ".xlsx":
            return redirect("importar_tabla_hoja")
        config.update(hoja=None, fila_cabecera=config.get("fila_cabecera") or 1)
        _guardar_estado(request, estado)
        return redirect("importar_tabla_columnas")
    return render(request, "evidencias/tabla_subir.html", {"form": form})


@rol_requerido(*ROLES)
@require_http_methods(["GET", "POST"])
def tabla_hoja(request):
    estado = _estado(request)
    if not estado:
        return redirect("importar_tabla")
    lista = hojas(_ruta(estado))
    config = estado["config"]
    inicial = {
        "hoja": config.get("hoja") if config.get("hoja") in lista else lista[0],
        "fila_cabecera": config.get("fila_cabecera") or 1,
    }
    form = HojaForm(request.POST or None, hojas=lista, initial=inicial)
    if request.method == "POST" and form.is_valid():
        config.update(form.cleaned_data)
        _guardar_estado(request, estado)
        return redirect("importar_tabla_columnas")
    return render(
        request, "evidencias/tabla_paso.html", {"form": form, "paso": "Hoja", "estado": estado}
    )


def _leer(estado):
    config = estado["config"]
    return leer_tabla(_ruta(estado), config.get("hoja"), int(config.get("fila_cabecera") or 1))


@rol_requerido(*ROLES)
@require_http_methods(["GET", "POST"])
def tabla_columnas(request):
    estado = _estado(request)
    if not estado:
        return redirect("importar_tabla")
    config = estado["config"]
    try:
        cabeceras, filas = _leer(estado)
    except FormatoTablaError as e:
        messages.error(request, str(e))
        return redirect("importar_tabla")
    fuente = config.get("fuente") or {}
    inicial = {
        "columna_municipio": config.get("columna_municipio"),
        "columna_provincia": config.get("columna_provincia") or "",
        "fuente_tipo": fuente.get("tipo") or "documento_interno",
        "fuente_nombre": fuente.get("nombre") or estado["nombre"],
        "fecha_consulta": config.get("fecha_consulta"),
        "estado": config.get("estado") or "borrador",
    }
    bloques_iniciales = [
        {k: b.get(k) or ("" if k != "columnas_extra" else []) for k in CAMPOS_BLOQUE}
        for b in config.get("bloques") or []
    ]
    form = ColumnasForm(request.POST or None, columnas=cabeceras, initial=inicial)
    formset = BloqueFormSet(
        request.POST or None,
        initial=bloques_iniciales,
        form_kwargs={"columnas": cabeceras},
        prefix="bloque",
    )
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        d = form.cleaned_data
        bloques = []
        anteriores = {b.get("columna_operador"): b for b in config.get("bloques") or []}
        for f in formset:
            b = f.cleaned_data
            if not b or not b.get("columna_operador"):
                continue
            bloque = {k: b.get(k) or None for k in CAMPOS_BLOQUE}
            bloque["servicio"] = b.get("servicio") or ""
            bloque["alcance"] = b.get("alcance") or ""
            bloque["columnas_extra"] = b.get("columnas_extra") or []
            bloque["valores_servicio"] = anteriores.get(b["columna_operador"], {}).get(
                "valores_servicio", {}
            )
            bloques.append(bloque)
        if not bloques:
            messages.error(request, "Define al menos un bloque con columna de operador.")
        else:
            config.update(
                columna_municipio=d["columna_municipio"],
                columna_provincia=d["columna_provincia"] or None,
                fuente={"tipo": d["fuente_tipo"], "nombre": d["fuente_nombre"]},
                fecha_consulta=d["fecha_consulta"].isoformat(),
                estado=d["estado"],
                bloques=bloques,
            )
            _guardar_estado(request, estado)
            return redirect("importar_tabla_valores")
    return render(
        request,
        "evidencias/tabla_columnas.html",
        {
            "form": form,
            "formset": formset,
            "estado": estado,
            "muestra": filas[:5],
            "cabeceras": cabeceras,
        },
    )


@rol_requerido(*ROLES)
@require_http_methods(["GET", "POST"])
def tabla_valores(request):
    estado = _estado(request)
    if not estado or not estado["config"].get("bloques"):
        return redirect("importar_tabla")
    config = estado["config"]
    _, filas = _leer(estado)
    guardados = config.get("valores_nivel") or {}
    niveles = []
    for b in config["bloques"]:
        for v in valores_distintos(filas, b.get("columna_nivel")):
            if v not in {n["valor"] for n in niveles}:
                propuesto = guardados.get(v) or proponer_nivel(v) or DECIDIR
                niveles.append({"valor": v, "propuesto": propuesto})
    servicios = []
    for i, b in enumerate(config["bloques"]):
        if b.get("columna_servicio"):
            previos = b.get("valores_servicio") or {}
            for v in valores_distintos(filas, b["columna_servicio"]):
                p = previos.get(v)
                servicios.append(
                    {
                        "bloque": i,
                        "valor": v,
                        "propuesto": f"{p['servicio']}|{p.get('alcance', '')}" if p else "",
                    }
                )

    if request.method == "POST":
        config["valores_nivel"] = {
            n["valor"]: request.POST.get(f"nivel_{i}", DECIDIR) for i, n in enumerate(niveles)
        }
        for b in config["bloques"]:
            if b.get("columna_servicio"):
                b["valores_servicio"] = {}
        for i, s in enumerate(servicios):
            elegido = request.POST.get(f"servicio_{i}", "")
            if elegido:
                servicio, _, alcance = elegido.partition("|")
                config["bloques"][s["bloque"]]["valores_servicio"][s["valor"]] = {
                    "servicio": servicio,
                    "alcance": alcance,
                }
        nombre = request.POST.get("nombre_plantilla", "").strip()
        if nombre:
            PlantillaImportacion.objects.update_or_create(
                nombre=nombre,
                defaults={"configuracion": config, "creado_por": request.user},
            )
            messages.success(request, f"Plantilla «{nombre}» guardada.")
        _guardar_estado(request, estado)
        return redirect("importar_tabla_confirmar")

    return render(
        request,
        "evidencias/tabla_valores.html",
        {
            "estado": estado,
            "niveles": niveles,
            "servicios": servicios,
            "opciones_nivel": OPCIONES_NIVEL,
            "opciones_servicio": opciones_servicio_alcance(),
        },
    )


@rol_requerido(*ROLES)
@require_http_methods(["GET", "POST"])
def tabla_confirmar(request):
    estado = _estado(request)
    if not estado or not estado["config"].get("bloques"):
        return redirect("importar_tabla")
    aplicar = request.method == "POST" and "confirmar" in request.POST
    if request.method == "POST" and "cancelar" in request.POST:
        _descartar(request)
        messages.info(request, "Importación cancelada; el archivo subido se ha borrado.")
        return redirect("importar")
    try:
        resultado = importar_tabla(
            _ruta(estado), estado["config"], request.user, estado["nombre"], aplicar=aplicar
        )
    except FormatoTablaError as e:
        messages.error(request, str(e))
        return redirect("importar_tabla_columnas")
    if aplicar:
        _descartar(request)
        messages.success(request, "Importación terminada.")
        return redirect("lote_importacion", pk=resultado.lote_id)
    return render(request, "evidencias/tabla_confirmar.html", {"estado": estado, "r": resultado})


@rol_requerido(*ROLES)
def lote(request, pk):
    lote = get_object_or_404(LoteImportacion, pk=pk)
    pendientes = ElementoRevision.objects.filter(
        lote_importacion=lote, estado=ElementoRevision.Estado.PENDIENTE
    ).count()
    return render(request, "evidencias/lote.html", {"lote": lote, "pendientes": pendientes})
