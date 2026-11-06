"""Importación de documentos Word (docs/04 §6): percepciones internas, lista de publicaciones y
anexo de evidencias del documento maestro. Clave natural del documento: SHA-256."""

import hashlib
import io
import re
from dataclasses import dataclass, field
from datetime import date

from django.db import transaction
from django.utils import timezone

from apps.entidades.models import AliasEmpresa, Empresa
from apps.entidades.services import resolver_empresa
from apps.evidencias.enums import (
    CategoriaEvidencia,
    EstadoValidacion,
    NivelEvidencia,
    Origen,
    TipoFuente,
)
from apps.evidencias.models import Evidencia, EvidenciaEmpresa, Fuente
from apps.medios.analisis import dominio_de, url_canonica
from apps.medios.models import Medio, Mencion, MencionEmpresa, Pieza
from apps.nucleo.services import registrar_auditoria
from apps.nucleo.texto import normalizar_texto

from .models import Documento, PercepcionInterna

_URL = re.compile(r"https?://\S+")


def _abrir(contenido: bytes):
    from docx import Document as DocxDocument

    return DocxDocument(io.BytesIO(contenido))


def _documento(
    contenido: bytes, nombre: str, tipo: str, usuario, texto: str
) -> tuple[Documento, bool]:
    sha = hashlib.sha256(contenido).hexdigest()
    doc, creado = Documento.objects.get_or_create(
        sha256=sha,
        defaults={
            "tipo": tipo,
            "nombre_archivo": nombre[:300],
            "texto_extraido": texto,
            "lectura": Documento.Lectura.TEXTO,
            "subido_por": usuario,
        },
    )
    return doc, creado


def es_cabecera(linea: str) -> bool:
    texto = linea.strip().rstrip(":").strip()
    return bool(texto) and texto.isupper() and len(texto) <= 80 and not _URL.search(texto)


def empresa_de_cabecera(linea: str) -> Empresa | None:
    """Cabecera de empresa en mayúsculas («NEALIS /FACSA», «FACSA (NEALIS):», «COX»).

    En una cabecera el contexto es explícito (es una lista de competidores), así que también
    valen los alias que requieren contexto, siempre con coincidencia exacta."""
    texto = linea.strip().rstrip(":").strip()
    if not texto or not texto.isupper() or len(texto) > 80:
        return None
    r = resolver_empresa(texto)
    if r.empresa:
        return r.empresa
    for parte in re.split(r"\s*(?:/|\(|\))\s*", texto):
        norm = normalizar_texto(parte)
        if not norm:
            continue
        alias = AliasEmpresa.objects.filter(
            texto_normalizado=norm, empresa__activa=True
        ).select_related("empresa")
        empresas = {a.empresa for a in alias}
        if len(empresas) == 1:
            return empresas.pop()
    return None


# --- Percepciones --------------------------------------------------------------------------


@dataclass
class ResultadoPercepciones:
    documento: Documento
    nuevo: bool
    percepciones: int = 0
    ignorados: list = field(default_factory=list)


@transaction.atomic
def importar_percepciones(contenido: bytes, nombre: str, usuario) -> ResultadoPercepciones:
    """Una `PercepcionInterna` por empresa: el texto bajo cada línea en mayúsculas que nombra a
    una empresa del catálogo. Nunca se crea una `Evidencia` (docs/03)."""
    parrafos = [p.text.strip() for p in _abrir(contenido).paragraphs if p.text.strip()]
    doc, nuevo = _documento(
        contenido, nombre, Documento.Tipo.VALORACION_INTERNA, usuario, "\n".join(parrafos)
    )
    res = ResultadoPercepciones(doc, nuevo)
    if not nuevo:
        res.percepciones = doc.percepciones.count()
        return res
    bloques: dict[int, list[str]] = {}
    empresas: dict[int, Empresa] = {}
    actual = None
    for p in parrafos:
        if es_cabecera(p):
            # Una cabecera que no es del catálogo (por ejemplo, otra empresa) cierra el bloque
            # anterior: su texto no se atribuye a nadie.
            actual = empresa_de_cabecera(p)
            if actual:
                empresas[actual.pk] = actual
                bloques.setdefault(actual.pk, [])
            else:
                res.ignorados.append(f"Cabecera sin empresa del catálogo: {p[:80]}")
            continue
        if actual is None:
            res.ignorados.append(p[:120])
        else:
            bloques[actual.pk].append(p)
    for empresa_id, lineas in bloques.items():
        if lineas:
            PercepcionInterna.objects.create(
                empresa=empresas[empresa_id], texto="\n".join(lineas), documento_origen=doc
            )
            res.percepciones += 1
    registrar_auditoria(
        usuario, "importacion.percepciones", doc, despues={"percepciones": res.percepciones}
    )
    return res


# --- Lista de publicaciones ----------------------------------------------------------------


@dataclass
class ResultadoPublicaciones:
    documento: Documento
    nuevo: bool
    urls: int = 0
    menciones_nuevas: int = 0
    ya_existentes: int = 0
    sin_empresa: int = 0
    cabeceras_sin_empresa: list = field(default_factory=list)


@transaction.atomic
def importar_publicaciones(contenido: bytes, nombre: str, usuario) -> ResultadoPublicaciones:
    """Cada URL bajo una cabecera de empresa → mención manual con esa empresa (atribución de quien
    elaboró la lista, validada). Si la URL ya existe (por ejemplo, de Brandwatch), solo se añade
    la atribución. Sin título ni extracto, el vínculo territorial queda «dudoso»."""
    parrafos = [p.text.strip() for p in _abrir(contenido).paragraphs if p.text.strip()]
    doc, nuevo = _documento(
        contenido, nombre, Documento.Tipo.PUBLICACIONES, usuario, "\n".join(parrafos)
    )
    res = ResultadoPublicaciones(doc, nuevo)
    actual = None
    for p in parrafos:
        if es_cabecera(p):
            actual = empresa_de_cabecera(p)
            if actual is None:
                res.cabeceras_sin_empresa.append(p[:80])
            continue
        for url in _URL.findall(p):
            res.urls += 1
            if actual is None:
                res.sin_empresa += 1
                continue
            canon = url_canonica(url)
            mencion = Mencion.objects.filter(url_canonica=canon).first()
            if mencion is None:
                dominio = dominio_de(canon)
                medio = None
                if dominio:
                    medio, _ = Medio.objects.get_or_create(
                        dominio=dominio, defaults={"nombre": dominio}
                    )
                pieza, _ = Pieza.objects.get_or_create(
                    url_canonica=canon,
                    defaults={"tipo": Pieza.Tipo.PRENSA_DIGITAL, "medio": medio, "titulo": ""},
                )
                mencion = Mencion.objects.create(
                    origen=Mencion.Origen.MANUAL,
                    url=url[:2000],
                    url_canonica=canon[:1000],
                    medio=medio,
                    pieza=pieza,
                    documento=doc,
                    vinculo_territorial="dudoso",
                    motivo_vinculo="Lista de publicaciones sin título ni extracto",
                )
                res.menciones_nuevas += 1
            else:
                res.ya_existentes += 1
            MencionEmpresa.objects.get_or_create(
                mencion=mencion,
                empresa=actual,
                defaults={
                    "metodo": MencionEmpresa.Metodo.MANUAL,
                    "estado_validacion": EstadoValidacion.VALIDADA,
                    "fragmento_detectado": f"Lista «{nombre[:200]}»",
                    "validado_por": usuario,
                    "validado_en": timezone.now(),
                },
            )
    registrar_auditoria(usuario, "importacion.publicaciones", doc, despues={"urls": res.urls})
    return res


# --- Anexo de evidencias del documento maestro ---------------------------------------------

CABECERA_ANEXO = [
    "ID",
    "Marca",
    "Fecha / control temporal",
    "Fuente",
    "Tema y enlace",
    "Tratamiento / límites",
]
SERIES = {
    "P": (CategoriaEvidencia.MENCION_MEDIOS, TipoFuente.PRENSA_DIGITAL),
    "S": (CategoriaEvidencia.DIGITAL, TipoFuente.RED_SOCIAL),
    "D": (CategoriaEvidencia.OTRA, TipoFuente.OTRA),
}
OFICIALES = re.compile(
    r"^(ayuntamiento|ajuntament|boe|diputaci|generalitat|universit|consell|dogv|bop)", re.I
)


def _enlaces(celda) -> list[str]:
    """URLs de los hipervínculos de una celda (relaciones del documento)."""
    urls = []
    rels = celda.part.rels
    for h in celda._tc.iter(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}hyperlink"
    ):
        rid = h.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        if rid and rid in rels and rels[rid].is_external:
            urls.append(rels[rid].target_ref)
    return urls + _URL.findall(celda.text)


def _nivel_propuesto(serie: str, fuente: str, empresas: list[Empresa], url: str) -> str:
    """Propuesta de nivel para el borrador (se revisa al validar): prensa para P; para D, oficial
    si la fuente es una administración y hay URL; empresa si la fuente es la propia empresa;
    parcial en otro caso."""
    if serie == "P":
        return NivelEvidencia.PRENSA
    norm = normalizar_texto(fuente)
    if serie == "D" and OFICIALES.match(norm) and url:
        return NivelEvidencia.OFICIAL
    alias = {
        normalizar_texto(a)
        for e in empresas
        for a in [e.nombre, *e.alias.values_list("texto", flat=True)]
    }
    if norm in alias:
        return NivelEvidencia.EMPRESA
    return NivelEvidencia.PARCIAL


@dataclass
class ResultadoMaestro:
    documento: Documento
    filas: int = 0
    nuevas: int = 0
    existentes: int = 0
    sin_empresa: list = field(default_factory=list)


@transaction.atomic
def importar_anexo_maestro(contenido: bytes, nombre: str, usuario) -> ResultadoMaestro:
    """Importación única del anexo (tablas P, S y D) como evidencias en **borrador**. Clave natural
    `maestro:<ID>`: repetirla no duplica nada."""
    d = _abrir(contenido)
    texto = "\n".join(p.text for p in d.paragraphs if p.text.strip())
    doc, _ = _documento(contenido, nombre, Documento.Tipo.DOCUMENTO_MAESTRO, usuario, texto)
    res = ResultadoMaestro(doc)
    for tabla in d.tables:
        cabecera = [c.text.strip() for c in tabla.rows[0].cells]
        if cabecera != CABECERA_ANEXO:
            continue
        for fila in tabla.rows[1:]:
            celdas = fila.cells
            ident = celdas[0].text.strip()
            if not ident or ident[0] not in SERIES:
                continue
            res.filas += 1
            clave = f"maestro:{ident}"
            if Evidencia.objects.filter(clave_importacion=clave).exists():
                res.existentes += 1
                continue
            marca, fecha_txt, fuente_txt = (c.text.strip() for c in celdas[1:4])
            tema, limites = celdas[4].text.strip(), celdas[5].text.strip()
            urls = _enlaces(celdas[4])
            empresas = [
                e
                for e in (empresa_de_cabecera(p.upper()) for p in re.split(r"\s*/\s*", marca))
                if e
            ]
            if not empresas:
                res.sin_empresa.append(f"{ident} ({marca})")
            categoria, tipo_fuente = SERIES[ident[0]]
            fuente, _ = Fuente.objects.get_or_create(
                tipo=tipo_fuente, nombre=fuente_txt[:200] or "Sin fuente"
            )
            m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", fecha_txt)
            fecha = date(int(m[3]), int(m[2]), int(m[1])) if m else None
            url = urls[0][:1000] if urls else ""
            ev = Evidencia.objects.create(
                categoria=categoria,
                titulo=tema[:500] or ident,
                extracto="",
                url_origen=url,
                fecha_publicacion=fecha,
                fecha_consulta=None,
                fuente=fuente,
                nivel=_nivel_propuesto(ident[0], fuente_txt, empresas, url),
                estado_validacion=EstadoValidacion.BORRADOR,
                origen=Origen.IMPORTADOR,
                tratamiento_limites=limites,
                datos_extra={
                    "id_documento_maestro": ident,
                    "marca": marca,
                    "fecha_texto": fecha_txt,
                    "enlaces": urls,
                    "nota": "Nivel propuesto al importar; se revisa al validar.",
                },
                clave_importacion=clave,
                creado_por=usuario,
            )
            for e in empresas:
                EvidenciaEmpresa.objects.get_or_create(evidencia=ev, empresa=e)
            res.nuevas += 1
    registrar_auditoria(
        usuario, "importacion.documento_maestro", doc, despues={"nuevas": res.nuevas}
    )
    return res
