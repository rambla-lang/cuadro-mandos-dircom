"""Resolución de la bandeja de revisión (RF-60) para lo que crean los importadores de tablas.

Cada acción deja registro de auditoría (RF-04). Nada se resuelve solo: siempre hay una persona.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.entidades.models import AliasEmpresa, Empresa
from apps.nucleo.models import ElementoRevision
from apps.nucleo.services import instantanea, registrar_auditoria
from apps.nucleo.texto import normalizar_texto
from apps.territorio.models import Municipio

from .enums import EstadoValidacion, NivelEvidencia
from .importers.tabla_municipal import aplicar_fila
from .models import Evidencia, EvidenciaEmpresa, PrestacionServicio

Tipo = ElementoRevision.Tipo
Estado = ElementoRevision.Estado


def iguales_pendientes(elemento: ElementoRevision):
    """Elementos pendientes del mismo tipo y con el mismo dato original (acción en bloque)."""
    return ElementoRevision.objects.filter(
        tipo=elemento.tipo,
        estado=Estado.PENDIENTE,
        texto_normalizado=elemento.texto_normalizado,
    )


def _cerrar(elemento, usuario, estado, resolucion, comentario=""):
    elemento.estado = estado
    elemento.resuelto_por = usuario
    elemento.resuelto_en = timezone.now()
    elemento.resolucion = resolucion
    elemento.comentario = comentario
    elemento.save()


def _exigir_pendiente(elemento, tipo):
    if elemento.tipo != tipo:
        raise ValidationError("El elemento no es de este tipo.")
    if elemento.estado != Estado.PENDIENTE:
        raise ValidationError("El elemento ya está resuelto.")


@transaction.atomic
def resolver_municipio(
    elemento: ElementoRevision,
    municipio: Municipio,
    usuario,
    guardar_nombre: bool = False,
    comentario: str = "",
) -> None:
    """Asigna el municipio a la fila pendiente y la importa. Con `guardar_nombre`, el texto
    se añade a los nombres alternativos del municipio y las próximas importaciones lo
    resolverán solas."""
    _exigir_pendiente(elemento, Tipo.MUNICIPIO_NO_RESUELTO)
    fila, contexto = elemento.datos["fila"], dict(elemento.datos["contexto"])
    resultado = aplicar_fila(fila, municipio, contexto, usuario)
    if guardar_nombre:
        guardar_nombre_alternativo(municipio, elemento.texto, usuario)
    _cerrar(
        elemento,
        usuario,
        Estado.CORREGIDO,
        {"municipio": municipio.codigo_ine, "fila": resultado, "nombre_guardado": guardar_nombre},
        comentario,
    )
    registrar_auditoria(
        usuario,
        "revision.municipio",
        elemento,
        despues={"texto": elemento.texto, "municipio": municipio.codigo_ine},
    )


def guardar_nombre_alternativo(municipio: Municipio, texto: str, usuario) -> bool:
    if normalizar_texto(texto) in municipio.nombres_normalizados:
        return False
    antes = list(municipio.nombres_alternativos)
    municipio.nombres_alternativos = [*antes, texto.strip()]
    municipio.save()
    registrar_auditoria(
        usuario,
        "municipio.nombre_alternativo",
        municipio,
        antes={"nombres_alternativos": antes},
        despues={"nombres_alternativos": municipio.nombres_alternativos},
    )
    return True


@transaction.atomic
def resolver_operador(
    elemento: ElementoRevision,
    empresas: list[Empresa],
    usuario,
    guardar_alias: bool = False,
    comentario: str = "",
) -> list[PrestacionServicio]:
    """Asigna una o varias empresas del catálogo a una prestación con operador sin resolver.

    Con varias (una UTE, por ejemplo), se crea o completa una prestación por empresa con las
    mismas evidencias. Si ya existía la prestación de esa empresa, se le suman las evidencias.
    """
    _exigir_pendiente(elemento, Tipo.OPERADOR_NO_RESUELTO)
    if not empresas:
        raise ValidationError("Elige al menos una empresa.")
    origen = elemento.objeto
    if origen is None:
        raise ValidationError("La prestación ya no existe.")
    evidencias = list(origen.evidencias.all())
    destinos = []
    for empresa in empresas:
        destino, _ = PrestacionServicio.objects.get_or_create(
            municipio=origen.municipio,
            servicio=origen.servicio,
            alcance=origen.alcance,
            empresa=empresa,
            defaults={
                "gestion": origen.gestion,
                "operador_texto": origen.operador_texto,
                "nivel": origen.nivel,
                "anio_referencia": origen.anio_referencia,
                "vigencia_confirmada": origen.vigencia_confirmada,
            },
        )
        destino.evidencias.add(*evidencias)
        for ev in evidencias:
            EvidenciaEmpresa.objects.get_or_create(evidencia=ev, empresa=empresa)
        destino.recalcular()
        destinos.append(destino)
    datos_origen = instantanea(origen)
    origen.delete()
    if guardar_alias and len(empresas) == 1:
        AliasEmpresa.objects.get_or_create(
            empresa=empresas[0],
            texto_normalizado=normalizar_texto(elemento.texto),
            defaults={"texto": elemento.texto[:200], "tipo": AliasEmpresa.Tipo.MARCA_LOCAL},
        )
    _cerrar(
        elemento,
        usuario,
        Estado.CORREGIDO,
        {"empresas": [e.pk for e in empresas], "alias_guardado": guardar_alias},
        comentario,
    )
    registrar_auditoria(
        usuario,
        "revision.operador",
        elemento,
        antes=datos_origen,
        despues={"empresas": [e.nombre for e in empresas]},
    )
    return destinos


@transaction.atomic
def decidir_nivel(
    elemento: ElementoRevision,
    nivel: str,
    usuario,
    url_origen: str = "",
    comentario: str = "",
) -> Evidencia:
    """Fija el nivel de una evidencia importada con nivel provisional. Si la importación era
    «validada», la decisión la valida; si era «borrador», sigue en borrador."""
    _exigir_pendiente(elemento, Tipo.NIVEL_POR_DECIDIR)
    evidencia = elemento.objeto
    if evidencia is None:
        raise ValidationError("La evidencia ya no existe.")
    if nivel not in NivelEvidencia.values:
        raise ValidationError("Nivel no válido.")
    url = (url_origen or "").strip() or evidencia.url_origen
    if nivel == NivelEvidencia.OFICIAL and not url:
        raise ValidationError("El nivel «oficial» exige una URL de origen oficial.")
    antes = instantanea(evidencia)
    evidencia.nivel = nivel
    evidencia.url_origen = url
    evidencia.tratamiento_limites = ""
    if elemento.propuesta.get("estado_al_validar") == EstadoValidacion.VALIDADA:
        evidencia.estado_validacion = EstadoValidacion.VALIDADA
        evidencia.validado_por = usuario
        evidencia.validado_en = timezone.now()
    evidencia.full_clean(exclude=["fuente", "codigo"])
    evidencia.save()
    for p in evidencia.prestaciones.all():
        p.recalcular()
    _cerrar(elemento, usuario, Estado.CORREGIDO, {"nivel": nivel, "url": url}, comentario)
    registrar_auditoria(
        usuario, "revision.nivel", evidencia, antes=antes, despues=instantanea(evidencia)
    )
    return evidencia


@transaction.atomic
def rechazar(elemento: ElementoRevision, usuario, comentario: str = "") -> None:
    """Municipio: la fila no se importa (no es un municipio, o agrupa varios). Operador: la
    prestación queda con el operador literal, sin empresa del catálogo. Nivel: la evidencia
    se marca como rechazada y deja de contar."""
    if elemento.estado != Estado.PENDIENTE:
        raise ValidationError("El elemento ya está resuelto.")
    if elemento.tipo == Tipo.NIVEL_POR_DECIDIR and elemento.objeto is not None:
        evidencia = elemento.objeto
        antes = instantanea(evidencia)
        evidencia.estado_validacion = EstadoValidacion.RECHAZADA
        evidencia.save()
        for p in evidencia.prestaciones.all():
            p.recalcular()
        registrar_auditoria(
            usuario, "evidencia.rechazar", evidencia, antes=antes, despues=instantanea(evidencia)
        )
    if elemento.tipo == Tipo.VINCULO_ORGANO and elemento.objeto is not None:
        organo = elemento.objeto
        organo.estado_vinculacion = "no_aplica"
        organo.save()
    _cerrar(elemento, usuario, Estado.RECHAZADO, {}, comentario)
    registrar_auditoria(usuario, "revision.rechazar", elemento, despues={"comentario": comentario})


@transaction.atomic
def validar_evidencias(evidencias, usuario) -> int:
    """Validación manual de borradores (acción del administrador de Django). Se saltan las
    que tienen el nivel pendiente de decidir en la bandeja: primero se decide el nivel."""
    n = 0
    con_nivel_pendiente = ElementoRevision.objects.filter(
        tipo=Tipo.NIVEL_POR_DECIDIR, estado=Estado.PENDIENTE
    ).values_list("objeto_id", flat=True)
    evidencias = evidencias.exclude(pk__in=list(con_nivel_pendiente))
    for ev in evidencias.exclude(estado_validacion=EstadoValidacion.VALIDADA):
        antes = instantanea(ev)
        ev.estado_validacion = EstadoValidacion.VALIDADA
        ev.validado_por = usuario
        ev.validado_en = timezone.now()
        ev.save()
        for p in ev.prestaciones.all():
            p.recalcular()
        registrar_auditoria(usuario, "evidencia.validar", ev, antes=antes, despues=instantanea(ev))
        n += 1
    return n
