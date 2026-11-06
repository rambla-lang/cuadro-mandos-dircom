from datetime import date

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone

from apps.nucleo.services import registrar_auditoria

from . import datos as calc
from .models import InformeGenerado
from .redaccion import redactar_con_ia, secciones_codigo
from .salida import generar_docx, generar_pptx
from .validador import validar_texto


@transaction.atomic
def crear(empresas, desde: date, hasta: date, usuario, usar_ia: bool) -> InformeGenerado:
    d = calc.calcular(list(empresas), desde, hasta)
    secciones = secciones_codigo(d)
    llamadas = []
    if usar_ia:
        secciones, llamadas = redactar_con_ia(d, secciones, usuario)
    informe = InformeGenerado.objects.create(
        titulo=f"Análisis de competencia · {desde:%d/%m/%Y} a {hasta:%d/%m/%Y}",
        parametros={
            "empresas": [e.pk for e in empresas],
            "desde": str(desde),
            "hasta": str(hasta),
            "ia": usar_ia,
        },
        datos=d,
        secciones=secciones,
        generado_por=usuario,
    )
    informe.evidencias_usadas.set(d["evidencias_ids"])
    informe.llamadas_ia.set(llamadas)
    registrar_auditoria(usuario, "informe.crear", informe, despues=informe.parametros)
    return informe


def guardar_texto(informe: InformeGenerado, clave: str, texto: str, usuario) -> None:
    if informe.estado == InformeGenerado.Estado.PUBLICADO:
        raise ValidationError("El informe ya está publicado.")
    for s in informe.secciones:
        if s["clave"] == clave:
            s["texto"] = texto
            s["origen"] = "manual" if s["origen"] != "manual" else s["origen"]
            s["problemas"] = validar_texto(texto, informe.datos) if s.get("validar", True) else []
    informe.save(update_fields=["secciones"])
    registrar_auditoria(usuario, "informe.editar", informe, despues={"seccion": clave})


@transaction.atomic
def publicar(informe: InformeGenerado, usuario) -> None:
    """Solo con todas las secciones validadas (paso 4 de docs/05 §4)."""
    if informe.secciones_con_problemas:
        raise ValidationError(
            "Hay secciones que no pasan el validador: corrígelas antes de publicar."
        )
    base = f"informes/{informe.pk}-{timezone.localtime():%Y%m%d-%H%M}"
    informe.archivo_docx = default_storage.save(f"{base}.docx", ContentFile(generar_docx(informe)))
    informe.archivo_pptx = default_storage.save(f"{base}.pptx", ContentFile(generar_pptx(informe)))
    informe.estado = InformeGenerado.Estado.PUBLICADO
    informe.publicado_por = usuario
    informe.publicado_en = timezone.now()
    informe.save()
    registrar_auditoria(usuario, "informe.publicar", informe)
