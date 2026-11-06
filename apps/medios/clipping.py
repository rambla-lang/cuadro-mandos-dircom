"""Recortes de prensa en PDF (docs/04 §5): metadatos del nombre del archivo y texto."""

import hashlib
import io
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone

from apps.documentos.models import Documento
from apps.evidencias.enums import EstadoValidacion
from apps.nucleo.services import registrar_auditoria

from .analisis import atribuir, cargar_alias, vinculo_territorial
from .models import Medio, Mencion, MencionEmpresa, Pieza

# MEDIO[-EDICION]-DD_MM_AAAA-PAGINA[ (n)].pdf; la edición es opcional y puede tener espacios.
PATRON_NOMBRE = re.compile(
    r"^(?P<medio>[^-]+?)(?:-(?P<edicion>.+?))?-(?P<dia>\d{2})_(?P<mes>\d{2})_(?P<anio>\d{4})"
    r"-(?P<pagina>\d+)(?:\s*\(\d+\))?\.pdf$",
    re.IGNORECASE,
)
MIN_CARACTERES_TEXTO = 200  # por debajo, sin capa de texto útil (docs/04 §5)


def metadatos_de_nombre(nombre: str) -> dict:
    """«INFORMACION-ALICANTE-23_09_2026-19.pdf» → medio, edición, fecha y página. Si el nombre
    no sigue el patrón («ABC.pdf»), devuelve {} y los datos se completan a mano."""
    m = PATRON_NOMBRE.match(Path(nombre).name.strip())
    if not m:
        return {}
    try:
        fecha = date(int(m["anio"]), int(m["mes"]), int(m["dia"]))
    except ValueError:
        return {}
    return {
        "medio": m["medio"].strip(),
        "edicion": (m["edicion"] or "").strip(),
        "fecha": fecha.isoformat(),
        "pagina": int(m["pagina"]),
    }


def extraer_texto(contenido: bytes) -> tuple[str, int]:
    from pypdf import PdfReader

    lector = PdfReader(io.BytesIO(contenido))
    textos = []
    for pagina in lector.pages:
        try:
            textos.append(pagina.extract_text() or "")
        except Exception:  # noqa: BLE001 - una página ilegible no para el documento
            textos.append("")
    return "\n".join(textos).strip(), len(lector.pages)


@dataclass
class ResultadoRecorte:
    documento: Documento
    nuevo: bool
    pendiente_ia: bool


def subir_recorte(contenido: bytes, nombre: str, usuario, empresa=None) -> ResultadoRecorte:
    """Clave natural: SHA-256. Crea el documento, la pieza de prensa impresa y su mención. La
    empresa indicada al subir cuenta como atribución manual validada; los alias del texto se
    añaden con las mismas reglas que Brandwatch. Sin capa de texto (CP-13): queda pendiente de
    lectura por IA, sin atribuciones por alias."""
    sha = hashlib.sha256(contenido).hexdigest()
    previo = Documento.objects.filter(sha256=sha).first()
    if previo:
        return ResultadoRecorte(previo, False, previo.lectura == Documento.Lectura.PENDIENTE_IA)
    try:
        texto, paginas = extraer_texto(contenido)
        lectura = (
            Documento.Lectura.TEXTO
            if len(texto) >= MIN_CARACTERES_TEXTO
            else Documento.Lectura.PENDIENTE_IA
        )
    except Exception:  # noqa: BLE001 - PDF dañado
        texto, paginas, lectura = "", None, Documento.Lectura.ERROR
    meta = metadatos_de_nombre(nombre)
    with transaction.atomic():
        ruta = ""
        if getattr(settings, "GUARDAR_ORIGINALES", True):
            ruta = default_storage.save(f"documentos/{sha}.pdf", ContentFile(contenido))
        doc = Documento.objects.create(
            tipo=Documento.Tipo.RECORTE,
            nombre_archivo=Path(nombre).name[:300],
            sha256=sha,
            ruta_almacen=ruta,
            paginas=paginas,
            texto_extraido=texto,
            lectura=lectura,
            metadatos=meta,
            empresa_propuesta=empresa,
            subido_por=usuario,
        )
        medio = None
        if meta.get("medio"):
            medio = Medio.objects.filter(
                nombre__iexact=meta["medio"], dominio__isnull=True
            ).first() or Medio.objects.create(nombre=meta["medio"], dominio=None)
        fecha = date.fromisoformat(meta["fecha"]) if meta.get("fecha") else None
        titulo = (texto.strip().splitlines() or [""])[0][:300] if texto else ""
        pieza = Pieza.objects.create(
            tipo=Pieza.Tipo.PRENSA_IMPRESA,
            medio=medio,
            titulo=titulo or doc.nombre_archivo,
            fecha_publicacion=fecha,
        )
        vinculo, motivo = (
            vinculo_territorial(texto)
            if lectura == Documento.Lectura.TEXTO
            else ("dudoso", "Sin texto todavía (pendiente de lectura)")
        )
        mencion = Mencion.objects.create(
            origen=Mencion.Origen.CLIPPING,
            titulo=pieza.titulo,
            extracto=" ".join(texto.split()[:120]),
            medio=medio,
            vinculo_territorial=vinculo,
            motivo_vinculo=motivo[:300],
            pieza=pieza,
            documento=doc,
            datos_fuente={"edicion": meta.get("edicion", ""), "pagina": meta.get("pagina")},
        )
        if fecha:
            mencion.fecha_publicacion = timezone.make_aware(
                timezone.datetime(fecha.year, fecha.month, fecha.day, 12, 0)
            )
            mencion.save(update_fields=["fecha_publicacion"])
        if empresa:
            MencionEmpresa.objects.create(
                mencion=mencion,
                empresa=empresa,
                metodo=MencionEmpresa.Metodo.MANUAL,
                estado_validacion=EstadoValidacion.VALIDADA,
                fragmento_detectado="Indicada al subir el recorte",
                validado_por=usuario,
                validado_en=timezone.now(),
            )
        if lectura == Documento.Lectura.TEXTO:
            from .importers.brandwatch import registrar_atribuciones

            coincidencias = atribuir(texto, cargar_alias())
            if empresa:
                coincidencias.pop(empresa.pk, None)
            registrar_atribuciones(mencion, coincidencias, usuario, None)
        registrar_auditoria(
            usuario,
            "importacion.recorte",
            doc,
            despues={"archivo": doc.nombre_archivo, "sha256": sha},
        )
    return ResultadoRecorte(doc, True, lectura == Documento.Lectura.PENDIENTE_IA)
