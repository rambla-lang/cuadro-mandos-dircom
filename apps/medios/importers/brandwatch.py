"""Importador de exportaciones CSV de Brandwatch (docs/04 §4). Clave natural: `Resource Id`.

CP-01: reimportar el mismo CSV no crea menciones. CP-02: los exports solapados no duplican.
"""

import csv
import hashlib
import io
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from apps.evidencias.enums import EstadoValidacion
from apps.nucleo.models import ElementoRevision, LoteImportacion
from apps.nucleo.services import registrar_auditoria

from ..analisis import atribuir, cargar_alias, dominio_de, url_canonica, vinculo_territorial
from ..models import Medio, Mencion, MencionEmpresa, Pieza

COLUMNAS_OBLIGATORIAS = ["Resource Id", "Date", "Title", "Snippet", "Url", "Domain", "Page Type"]
# Columnas útiles no modeladas que se guardan en datos_fuente (docs/04 §4). No se guarda
# `Author` mientras P-06 (autores particulares) esté sin decidir.
COLUMNAS_DATOS_FUENTE = [
    "Query Id",
    "Query Name",
    "Emotion",
    "Country",
    "City",
    "Thread Id",
    "Thread URL",
    "Publication Name",
    "Estimated Reach",
    "Potential Audience",
    "Impressions",
    "Engagement Score",
    "Likes",
    "Comments",
    "Shares",
    "Category Details",
    "Tags",
]
TIPOS_PRENSA = {"news", "blog"}
MAX_PALABRAS = 300
Tipo = ElementoRevision.Tipo


class FormatoBrandwatchError(ValueError):
    pass


def leer_csv(contenido: bytes) -> tuple[dict, list[dict]]:
    """(metadatos, filas). La cabecera se localiza buscando la fila que contiene a la vez
    «Query Id», «Resource Id» y «Url»: la línea 4 de metadatos también se llama «Query Id»."""
    texto = contenido.decode("utf-8-sig", errors="replace")
    filas = list(csv.reader(io.StringIO(texto)))
    try:
        i = next(
            n for n, f in enumerate(filas) if "Query Id" in f and "Resource Id" in f and "Url" in f
        )
    except StopIteration as e:
        raise FormatoBrandwatchError(
            "No se encuentra la cabecera de Brandwatch (Query Id, Resource Id, Url)."
        ) from e
    cabecera = filas[i]
    faltan = [c for c in COLUMNAS_OBLIGATORIAS if c not in cabecera]
    if faltan:
        raise FormatoBrandwatchError(f"Faltan columnas: {', '.join(faltan)}.")
    metadatos = {f[0]: f[1] for f in filas[:i] if len(f) >= 2 and f[0]}
    datos = [dict(zip(cabecera, f, strict=False)) for f in filas[i + 1 :] if any(f)]
    return metadatos, datos


def _fecha(texto: str) -> datetime | None:
    """`Date` llega sin zona (`2026-10-30 08:30:00.000`). Se interpreta como UTC hasta
    verificarlo (docs/04 §4); la interfaz lo avisa."""
    try:
        return datetime.strptime(texto.strip()[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
    except ValueError:
        return None


def _recortar(texto: str) -> str:
    palabras = texto.split()
    return " ".join(palabras[:MAX_PALABRAS]) + (" […]" if len(palabras) > MAX_PALABRAS else "")


@dataclass
class Resultado:
    filas: int = 0
    nuevas: int = 0
    existentes: int = 0
    sin_id: int = 0
    piezas_nuevas: int = 0
    atribuidas: int = 0
    dudosas: int = 0
    vinculo: dict = field(default_factory=dict)
    lote_id: int | None = None


def importar_brandwatch(contenido: bytes, nombre: str, usuario) -> Resultado:
    metadatos, filas = leer_csv(contenido)
    sha = hashlib.sha256(contenido).hexdigest()
    res = Resultado(filas=len(filas))
    alias = cargar_alias()
    with transaction.atomic():
        lote = LoteImportacion.objects.create(
            tipo="brandwatch",
            parametros={"archivo": nombre, "metadatos": metadatos},
            archivo_sha256=sha,
            usuario=usuario,
            leidos=len(filas),
        )
        res.lote_id = lote.pk
        medios: dict[str, Medio] = {}
        for f in filas:
            rid = (f.get("Resource Id") or "").strip()
            canon = url_canonica(f.get("Url", ""))
            if not rid and not canon:
                res.sin_id += 1
                continue
            existe = (
                Mencion.objects.filter(resource_id=rid).exists()
                if rid
                else Mencion.objects.filter(origen="brandwatch", url_canonica=canon).exists()
            )
            if existe:
                res.existentes += 1
                continue
            dominio = (f.get("Domain") or dominio_de(canon)).lower().removeprefix("www.")
            medio = medios.get(dominio)
            if medio is None and dominio:
                tipo_pag = (f.get("Page Type") or "").lower()
                medio, _ = Medio.objects.get_or_create(
                    dominio=dominio,
                    defaults={
                        "nombre": f.get("Publication Name") or dominio,
                        "ambito": Medio.Ambito.RED_SOCIAL
                        if tipo_pag not in TIPOS_PRENSA
                        else Medio.Ambito.DESCONOCIDO,
                    },
                )
                medios[dominio] = medio
            fecha = _fecha(f.get("Date", ""))
            titulo, extracto = (f.get("Title") or "").strip(), (f.get("Snippet") or "").strip()
            vinculo, motivo = vinculo_territorial(f"{titulo}\n{extracto}")
            res.vinculo[vinculo] = res.vinculo.get(vinculo, 0) + 1
            pieza = None
            if canon:
                tipo_pagina = (f.get("Page Type") or "").lower()
                pieza, creada = Pieza.objects.get_or_create(
                    url_canonica=canon,
                    defaults={
                        "tipo": Pieza.Tipo.PRENSA_DIGITAL
                        if tipo_pagina in TIPOS_PRENSA
                        else Pieza.Tipo.RED_SOCIAL,
                        "medio": medio,
                        "titulo": titulo[:1000],
                        "fecha_publicacion": timezone.localtime(fecha).date() if fecha else None,
                    },
                )
                res.piezas_nuevas += creada
            mencion = Mencion.objects.create(
                origen=Mencion.Origen.BRANDWATCH,
                resource_id=rid or None,
                url=(f.get("Url") or "")[:2000],
                url_canonica=canon[:1000],
                fecha_publicacion=fecha,
                titulo=titulo[:1000],
                extracto=_recortar(extracto),
                medio=medio,
                tipo_pagina=(f.get("Page Type") or "")[:30],
                idioma=(f.get("Language") or "")[:10],
                sentimiento_fuente=(f.get("Sentiment") or "")[:20],
                region_fuente=(f.get("Region") or "")[:100],
                datos_fuente={c: f[c] for c in COLUMNAS_DATOS_FUENTE if f.get(c)},
                vinculo_territorial=vinculo,
                motivo_vinculo=motivo[:300],
                pieza=pieza,
                lote_importacion=lote,
            )
            res.nuevas += 1
            registrar_atribuciones(
                mencion, atribuir(f"{titulo}\n{extracto}", alias), usuario, lote, res
            )
        lote.nuevos = res.nuevas
        lote.descartados = res.existentes + res.sin_id
        lote.anotar(
            f"Filas {res.filas}; menciones nuevas {res.nuevas}; ya existentes {res.existentes}; "
            f"sin identificador {res.sin_id}; piezas nuevas {res.piezas_nuevas}; atribuidas por "
            f"alias {res.atribuidas}; dudosas {res.dudosas}; vínculo {res.vinculo}. La columna "
            "Date se interpreta como UTC (por verificar, docs/04 §4)."
        )
        lote.fin = timezone.now()
        lote.save()
        registrar_auditoria(
            usuario,
            "importacion.brandwatch",
            lote,
            despues={"archivo": nombre, "sha256": sha, "nuevas": res.nuevas},
        )
    return res


def registrar_atribuciones(mencion, coincidencias, usuario, lote, res=None):
    """Alias inequívoco: atribución validada por la regla (quien importa la acepta). Alias que
    requiere contexto: borrador y a la bandeja. Una atribución en una mención sin vínculo
    territorial claro manda también el vínculo a la bandeja."""
    for c in coincidencias.values():
        validada = not c.requiere_contexto
        me = MencionEmpresa.objects.create(
            mencion=mencion,
            empresa_id=c.empresa_id,
            metodo=MencionEmpresa.Metodo.ALIAS,
            estado_validacion=EstadoValidacion.VALIDADA if validada else EstadoValidacion.BORRADOR,
            fragmento_detectado=c.alias[:300],
            validado_por=usuario if validada else None,
            validado_en=timezone.now() if validada else None,
        )
        if validada:
            if res:
                res.atribuidas += 1
        else:
            if res:
                res.dudosas += 1
            ElementoRevision.objects.get_or_create(
                clave=f"atribucion:{me.pk}",
                defaults={
                    "tipo": Tipo.ATRIBUCION_MENCION,
                    "texto": c.alias,
                    "motivo": f"«{c.alias}» es un alias que requiere contexto: confirma que la "
                    "mención habla de la empresa.",
                    "objeto_tipo": ContentType.objects.get_for_model(me),
                    "objeto_id": me.pk,
                    "lote_importacion": lote,
                },
            )
    if coincidencias and mencion.vinculo_territorial == "dudoso":
        ElementoRevision.objects.get_or_create(
            clave=f"vinculo:{mencion.pk}",
            defaults={
                "tipo": Tipo.VINCULO_TERRITORIAL,
                "texto": mencion.titulo[:500] or mencion.url[:500],
                "motivo": "Mención de una empresa gestora sin lugar reconocible: ¿tiene vínculo "
                "con la Comunitat Valenciana?",
                "objeto_tipo": ContentType.objects.get_for_model(mencion),
                "objeto_id": mencion.pk,
                "lote_importacion": lote,
            },
        )


def importar_fichero(ruta: Path, usuario) -> Resultado:
    return importar_brandwatch(Path(ruta).read_bytes(), Path(ruta).name, usuario)
