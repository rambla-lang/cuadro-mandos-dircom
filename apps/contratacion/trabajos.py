"""Trabajos de ingesta de contratación (ADR-007, ADR-008). Una parte = un `.atom` del ZIP de
PLACSP o una página de TED. La carga histórica (más de un mes) solo por comando local."""

import tempfile
from datetime import date
from pathlib import Path

import httpx
from django.conf import settings
from django.utils import timezone

from apps.nucleo.models import LoteImportacion, TrabajoIngesta
from apps.nucleo.trabajos import registrar

from .importers.placsp import URL_ZIP_MENSUAL, ImportadorPlacsp, miembros_zip, procesar_miembro_zip
from .importers.ted import POR_PAGINA, ImportadorTed, pedir_pagina

TIPO_PLACSP = "placsp_zip"
TIPO_TED = "ted"


def _lote(trabajo: TrabajoIngesta, tipo: str) -> LoteImportacion:
    if trabajo.lote_importacion_id is None:
        trabajo.lote_importacion = LoteImportacion.objects.create(
            tipo=tipo, parametros=trabajo.parametros, usuario=trabajo.usuario
        )
    return trabajo.lote_importacion


def _cerrar_lote(trabajo: TrabajoIngesta):
    lote = trabajo.lote_importacion
    if lote is None:
        return
    c = trabajo.contadores
    lote.leidos = c.get("entradas", c.get("avisos", 0))
    lote.nuevos = c.get("nuevos", 0)
    lote.actualizados = c.get("actualizados", 0)
    lote.descartados = c.get("fuera_cv", 0) + c.get("no_valencianos", 0) + c.get("antiguos", 0)
    lote.errores = c.get("errores", 0)
    lote.log = trabajo.log
    lote.fin = timezone.now()
    lote.save()


def descargar_zip_mensual(mes: str) -> Path:
    """Descarga el ZIP mensual de perfiles a un fichero temporal (el servidor no admite
    reanudar; si se corta, se vuelve a empezar). Certificados de `certifi` vía httpx; la
    verificación TLS nunca se desactiva (docs/04 §1)."""
    destino_dir = Path(settings.MEDIA_ROOT) / "tmp"
    destino_dir.mkdir(parents=True, exist_ok=True)
    fd = tempfile.NamedTemporaryFile(  # noqa: SIM115 - se cierra en el with de abajo
        dir=destino_dir, prefix=f"placsp_{mes}_", suffix=".zip", delete=False
    )
    with fd, httpx.stream("GET", URL_ZIP_MENSUAL.format(mes=mes), timeout=120) as r:
        r.raise_for_status()
        for trozo in r.iter_bytes(1024 * 256):
            fd.write(trozo)
    return Path(fd.name)


@registrar(TIPO_PLACSP)
def parte_placsp(trabajo: TrabajoIngesta) -> bool:
    p = trabajo.progreso
    lote = _lote(trabajo, "placsp")
    if "zip" not in p:
        if trabajo.parametros.get("fichero"):
            ruta = Path(trabajo.parametros["fichero"])
        else:
            mes = trabajo.parametros["mes"]
            trabajo.anotar(f"Descargando el ZIP mensual {mes} de PLACSP…")
            ruta = descargar_zip_mensual(mes)
            p["descargado"] = True
        p["zip"] = str(ruta)
        if ruta.suffix == ".atom":
            p["miembros"] = [""]
        else:
            p["miembros"] = miembros_zip(ruta)
        p["i"] = 0
        trabajo.partes_total = len(p["miembros"])
        trabajo.anotar(f"{trabajo.partes_total} ficheros .atom en {ruta.name}.")
        return False
    miembro = p["miembros"][p["i"]]
    importador = ImportadorPlacsp(lote)
    if miembro:
        c = procesar_miembro_zip(Path(p["zip"]), miembro, importador)
    else:
        c = importador.procesar_atom(p["zip"], Path(p["zip"]).name)
    trabajo.sumar(**c.como_dict())
    for e in c.errores[:5]:
        trabajo.anotar(e)
    p["i"] += 1
    trabajo.partes_hechas = p["i"]
    if p["i"] < len(p["miembros"]):
        return False
    if p.get("descargado"):
        Path(p["zip"]).unlink(missing_ok=True)
    trabajo.anotar(f"Contadores: {trabajo.contadores}")
    _cerrar_lote(trabajo)
    return True


@registrar(TIPO_TED)
def parte_ted(trabajo: TrabajoIngesta) -> bool:
    p = trabajo.progreso
    lote = _lote(trabajo, "ted")
    desde = date.fromisoformat(trabajo.parametros["desde"])
    hasta = date.fromisoformat(trabajo.parametros["hasta"])
    pagina = p.get("pagina", 1)
    respuesta = pedir_pagina(desde, hasta, pagina)
    total = respuesta.get("totalNoticeCount") or 0
    if trabajo.partes_total is None:
        trabajo.partes_total = max(1, -(-total // POR_PAGINA))
        trabajo.anotar(f"TED: {total} avisos con lugar de ejecución ES52 en el periodo.")
        if total > 15000:
            trabajo.anotar(
                "Aviso: el modo por páginas de TED solo devuelve 15.000 avisos; acorta el periodo."
            )
    avisos = respuesta.get("notices") or []
    importador = ImportadorTed(lote)
    c = importador.procesar(avisos)
    trabajo.sumar(**c.como_dict())
    for ejemplo in c.descartados_ejemplos[:5]:
        trabajo.anotar(f"No valenciano (comprador fuera de la CV): {ejemplo}")
    p["pagina"] = pagina + 1
    trabajo.partes_hechas = pagina
    if not avisos or pagina * POR_PAGINA >= total or pagina * POR_PAGINA >= 15000:
        trabajo.anotar(f"Contadores: {trabajo.contadores}")
        _cerrar_lote(trabajo)
        return True
    return False
