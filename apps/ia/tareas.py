"""Tareas de IA (docs/06). Cada una crea una `PropuestaIA` y un elemento en la bandeja; nada se
aplica sin que una persona lo acepte."""

import base64
import contextlib
import json
from datetime import date

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone

from apps.contratacion.models import Expediente
from apps.documentos.models import Documento
from apps.entidades.models import Empresa
from apps.evidencias.enums import ALCANCES_POR_SERVICIO, EstadoValidacion, Servicio
from apps.medios.analisis import vinculo_territorial
from apps.medios.models import Medio, Mencion, MencionEmpresa, Pieza
from apps.nucleo.models import ElementoRevision
from apps.nucleo.services import registrar_auditoria

from . import esquemas
from .cliente import llamar
from .models import PropuestaIA

MAX_CARACTERES_EXTRACTO = 3000  # a la API solo van extractos de prensa (docs/06)


def catalogo_empresas() -> str:
    """Bloque fijo (se beneficia de la caché): empresas activas con alias y acotaciones."""
    lineas = []
    for e in Empresa.objects.filter(activa=True).prefetch_related("alias", "acotaciones"):
        alias = sorted({a.texto for a in e.alias.all()} - {e.nombre})
        ambiguos = sorted(a.texto for a in e.alias.all() if a.requiere_contexto)
        acot = "; ".join(a.nota for a in e.acotaciones.all() if a.nota)
        partes = [f"- id {e.pk}: {e.nombre}"]
        if alias:
            partes.append(f"alias: {', '.join(alias)}")
        if ambiguos:
            partes.append(f"alias ambiguos: {', '.join(ambiguos)}")
        if acot:
            partes.append(f"acotación: {acot}")
        lineas.append(" · ".join(partes))
    return "Empresas:\n" + "\n".join(lineas)


def _proponer(resultado, objetivo, tarea: str, texto: str, motivo: str) -> PropuestaIA:
    propuesta = PropuestaIA.objects.create(
        llamada=resultado.llamada,
        tipo_objetivo=ContentType.objects.get_for_model(objetivo),
        id_objetivo=objetivo.pk,
        propuesta=resultado.datos.model_dump(),
    )
    ElementoRevision.objects.create(
        clave=f"ia:{propuesta.pk}",
        tipo=ElementoRevision.Tipo.PROPUESTA_IA,
        texto=texto[:500],
        motivo=motivo,
        propuesta={"tarea": tarea, **resultado.datos.model_dump()},
        objeto_tipo=ContentType.objects.get_for_model(propuesta),
        objeto_id=propuesta.pk,
    )
    return propuesta


def t1_atribuir_mencion(mencion: Mencion, usuario=None) -> PropuestaIA:
    texto = f"Título: {mencion.titulo}\nExtracto: {mencion.extracto[:MAX_CARACTERES_EXTRACTO]}"
    r = llamar(
        tarea="T1",
        tipo_modelo="clasificar",
        prompt_tarea="t1_v1",
        contenido=[
            {"type": "text", "text": catalogo_empresas(), "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": f"Mención:\n{texto}"},
        ],
        esquema=esquemas.ESQUEMA_T1,
        validador=esquemas.SalidaT1,
        usuario=usuario,
        objeto=mencion,
        max_tokens=1500,
        esfuerzo="low",
    )
    return _proponer(
        r, mencion, "T1", mencion.titulo or mencion.url, "Atribución propuesta por la IA (T1)."
    )


def t2_leer_recorte(documento: Documento, usuario=None) -> PropuestaIA:
    if not documento.ruta_almacen or not default_storage.exists(documento.ruta_almacen):
        raise ValidationError("No se guardó el PDF original: no se puede enviar a la IA (ADR-003).")
    with default_storage.open(documento.ruta_almacen, "rb") as f:
        datos = base64.standard_b64encode(f.read()).decode("ascii")
    r = llamar(
        tarea="T2",
        tipo_modelo="extraer",
        prompt_tarea="t2_v1",
        contenido=[
            {
                "type": "document",
                "source": {"type": "base64", "media_type": "application/pdf", "data": datos},
            },
            {"type": "text", "text": catalogo_empresas()},
            {"type": "text", "text": f"Nombre del archivo: {documento.nombre_archivo}"},
        ],
        esquema=esquemas.ESQUEMA_T2,
        validador=esquemas.SalidaT2,
        usuario=usuario,
        objeto=documento,
        max_tokens=8000,
        esfuerzo="medium",
    )
    return _proponer(
        r, documento, "T2", documento.nombre_archivo, "Lectura del recorte por la IA (T2)."
    )


def t3_clasificar_expediente(exp: Expediente, usuario=None) -> PropuestaIA:
    texto = (
        f"Objeto: {exp.objeto}\nCPV: {', '.join(exp.cpv) or 'no consta'}\n"
        f"Órgano: {exp.organo.nombre if exp.organo else 'no consta'}\n"
        "Catálogo: "
        + json.dumps({s: [str(a) for a in al] for s, al in ALCANCES_POR_SERVICIO.items()})
    )
    r = llamar(
        tarea="T3",
        tipo_modelo="clasificar",
        prompt_tarea="t3_v1",
        contenido=[{"type": "text", "text": texto}],
        esquema=esquemas.ESQUEMA_T3,
        validador=esquemas.SalidaT3,
        usuario=usuario,
        objeto=exp,
        max_tokens=800,
        esfuerzo="low",
    )
    return _proponer(r, exp, "T3", exp.objeto, "Clasificación propuesta por la IA (T3).")


def t4_dividir_percepciones(documento: Documento, usuario=None) -> PropuestaIA:
    r = llamar(
        tarea="T4",
        tipo_modelo="extraer",
        prompt_tarea="t4_v1",
        contenido=[
            {"type": "text", "text": catalogo_empresas()},
            {"type": "text", "text": f"Documento:\n{documento.texto_extraido}"},
        ],
        esquema=esquemas.ESQUEMA_T4,
        validador=esquemas.SalidaT4,
        usuario=usuario,
        objeto=documento,
        max_tokens=16000,
        esfuerzo="medium",
    )
    return _proponer(
        r,
        documento,
        "T4",
        documento.nombre_archivo,
        "División por empresa propuesta por la IA (T4).",
    )


# --- Aplicación tras la revisión humana ----------------------------------------------------


def _atribuir(mencion, empresa_id, fragmento, usuario):
    if not Empresa.objects.filter(pk=empresa_id, activa=True).exists():
        return
    MencionEmpresa.objects.update_or_create(
        mencion=mencion,
        empresa_id=empresa_id,
        defaults={
            "metodo": MencionEmpresa.Metodo.IA,
            "estado_validacion": EstadoValidacion.VALIDADA,
            "fragmento_detectado": fragmento[:300],
            "validado_por": usuario,
            "validado_en": timezone.now(),
        },
    )


@transaction.atomic
def aplicar(propuesta: PropuestaIA, usuario, empresas_aceptadas: list[int] | None = None) -> None:
    """Aplica una propuesta aceptada por una persona (que valida así lo que la IA propuso)."""
    if propuesta.estado_revision != PropuestaIA.Estado.PENDIENTE:
        raise ValidationError("La propuesta ya está revisada.")
    datos, tarea, obj = propuesta.propuesta, propuesta.llamada.tarea, propuesta.objetivo
    if obj is None:
        raise ValidationError("El objeto de la propuesta ya no existe.")
    ids = {e["empresa_id"] for e in datos.get("empresas", [])}
    if empresas_aceptadas is not None:
        ids &= set(empresas_aceptadas)
    if tarea == "T1":
        for e in datos["empresas"]:
            if e["empresa_id"] in ids:
                _atribuir(obj, e["empresa_id"], e["fragmento"], usuario)
        obj.vinculo_territorial = datos["vinculo_territorial"]
        obj.motivo_vinculo = f"IA (validado por {usuario.email}): {datos['motivo']}"[:300]
        obj.save()
    elif tarea == "T2":
        _aplicar_t2(obj, datos, ids, usuario)
    elif tarea == "T3":
        servicio = "" if datos["servicio"] == "ninguno" else datos["servicio"]
        alcance = (
            datos["alcance"]
            if servicio and datos["alcance"] in ALCANCES_POR_SERVICIO[Servicio(servicio)]
            else ""
        )
        obj.servicio_clasificado = servicio
        obj.alcance_clasificado = alcance
        obj.metodo_clasificacion = Expediente.Clasificacion.IA
        obj.regla_clasificacion = f"IA validada por {usuario.email}: {datos['motivo']}"[:200]
        obj.save()
    propuesta.estado_revision = (
        PropuestaIA.Estado.ACEPTADA if empresas_aceptadas is None else PropuestaIA.Estado.CORREGIDA
    )
    propuesta.revisado_por = usuario
    propuesta.revisado_en = timezone.now()
    propuesta.save()
    registrar_auditoria(usuario, f"ia.aplicar_{tarea.lower()}", propuesta, despues=datos)


def _aplicar_t2(doc: Documento, datos: dict, ids: set, usuario):
    doc.texto_extraido = datos["texto"]
    doc.texto_obtenido_por_ia = True
    doc.lectura = Documento.Lectura.IA
    meta = dict(doc.metadatos)
    for campo in ("medio", "fecha_publicacion", "pagina"):
        if datos.get(campo) and not meta.get(campo if campo != "fecha_publicacion" else "fecha"):
            meta[campo if campo != "fecha_publicacion" else "fecha"] = datos[campo]
    doc.metadatos = meta
    doc.save()
    for mencion in doc.menciones.select_related("pieza"):
        mencion.extracto = " ".join(datos["texto"].split()[:120])
        mencion.titulo = (datos.get("titular") or mencion.titulo)[:1000]
        mencion.vinculo_territorial, mencion.motivo_vinculo = vinculo_territorial(datos["texto"])
        pieza = mencion.pieza
        if pieza:
            pieza.titulo = mencion.titulo
            if not pieza.fecha_publicacion and meta.get("fecha"):
                with contextlib.suppress(ValueError):
                    pieza.fecha_publicacion = date.fromisoformat(meta["fecha"])
            if not pieza.medio_id and meta.get("medio"):
                pieza.medio = Medio.objects.filter(
                    nombre__iexact=meta["medio"]
                ).first() or Medio.objects.create(nombre=meta["medio"], dominio=None)
                mencion.medio = pieza.medio
            if datos.get("es_publicidad_identificada"):
                pieza.tipo = Pieza.Tipo.COMUNICADO_PROPIO  # regla 5: separada de la prensa
            pieza.save()
        mencion.save()
        for e in datos.get("empresas", []):
            if e["empresa_id"] in ids:
                _atribuir(mencion, e["empresa_id"], e["fragmento"], usuario)


def rechazar(propuesta: PropuestaIA, usuario, comentario=""):
    propuesta.estado_revision = PropuestaIA.Estado.RECHAZADA
    propuesta.revisado_por = usuario
    propuesta.revisado_en = timezone.now()
    propuesta.comentario = comentario
    propuesta.save()
