"""Enumeraciones de docs/03 («valores fijos en código»). Su significado no cambia sin
actualizar docs/03-modelo-de-datos.md."""

from django.db import models
from django.db.models import Q


class NivelEvidencia(models.TextChoices):
    OFICIAL = "oficial", "Confirmado (fuente oficial)"
    PRENSA = "prensa", "Confirmado (prensa)"
    EMPRESA = "empresa", "Confirmado por la empresa"
    PARCIAL = "parcial", "Parcial"
    NO_LOCALIZADO = "no_localizado", "No localizado"


NIVELES_CONFIRMADOS = (NivelEvidencia.OFICIAL, NivelEvidencia.PRENSA, NivelEvidencia.EMPRESA)


class Servicio(models.TextChoices):
    AGUA = "agua", "Agua"
    RESIDUOS = "residuos", "Residuos"
    ENERGIA = "energia", "Energía"


class Alcance(models.TextChoices):
    # agua
    ABASTECIMIENTO = "abastecimiento", "Abastecimiento"
    SANEAMIENTO = "saneamiento", "Saneamiento"
    DEPURACION = "depuracion", "Depuración"
    CICLO_INTEGRAL = "ciclo_integral", "Ciclo integral"
    # residuos
    RECOGIDA_RSU = "recogida_rsu", "Recogida de RSU"
    LIMPIEZA_VIARIA = "limpieza_viaria", "Limpieza viaria"
    ECOPARQUE = "ecoparque", "Ecoparque o punto limpio"
    TRATAMIENTO = "tratamiento", "Tratamiento"
    TRANSPORTE = "transporte", "Transporte o transferencia"
    # energía
    ALUMBRADO_PUBLICO = "alumbrado_publico", "Mantenimiento de alumbrado público"
    GESTION_ENERGETICA = "gestion_energetica", "Gestión energética (ESE)"
    INSTALACIONES_TERMICAS = "instalaciones_termicas", "Instalaciones térmicas o climatización"
    MANTENIMIENTO_ELECTRICO = "mantenimiento_electrico", "Mantenimiento eléctrico"
    RENOVACION_EFICIENCIA = "renovacion_eficiencia", "Renovación o eficiencia (obra)"
    SUMINISTRO_ELECTRICO = "suministro_electrico", "Suministro eléctrico (comercializadora)"
    # común
    OTRO = "otro", "Otro"


ALCANCES_POR_SERVICIO = {
    Servicio.AGUA: (
        Alcance.ABASTECIMIENTO,
        Alcance.SANEAMIENTO,
        Alcance.DEPURACION,
        Alcance.CICLO_INTEGRAL,
        Alcance.OTRO,
    ),
    Servicio.RESIDUOS: (
        Alcance.RECOGIDA_RSU,
        Alcance.LIMPIEZA_VIARIA,
        Alcance.ECOPARQUE,
        Alcance.TRATAMIENTO,
        Alcance.TRANSPORTE,
        Alcance.OTRO,
    ),
    Servicio.ENERGIA: (
        Alcance.ALUMBRADO_PUBLICO,
        Alcance.GESTION_ENERGETICA,
        Alcance.INSTALACIONES_TERMICAS,
        Alcance.MANTENIMIENTO_ELECTRICO,
        Alcance.RENOVACION_EFICIENCIA,
        Alcance.SUMINISTRO_ELECTRICO,
        Alcance.OTRO,
    ),
}


def q_alcance_coherente(permitir_vacio: bool) -> Q:
    """Condición de BD: el alcance pertenece al servicio (o ambos vacíos si se permite)."""
    q = Q()
    for servicio, alcances in ALCANCES_POR_SERVICIO.items():
        q |= Q(servicio=servicio, alcance__in=[str(a) for a in alcances])
    if permitir_vacio:
        q |= Q(servicio="", alcance="")
    return q


class EstadoValidacion(models.TextChoices):
    BORRADOR = "borrador", "Borrador"
    VALIDADA = "validada", "Validada"
    RECHAZADA = "rechazada", "Rechazada"


class Origen(models.TextChoices):
    IMPORTADOR = "importador", "Importador"
    IA = "ia", "IA"
    MANUAL = "manual", "Manual"


class TipoFuente(models.TextChoices):
    CONTRATACION_OFICIAL = "contratacion_oficial", "Contratación oficial"
    BOLETIN_OFICIAL = "boletin_oficial", "Boletín oficial"
    ACTA_MUNICIPAL = "acta_municipal", "Acta municipal"
    PRENSA_DIGITAL = "prensa_digital", "Prensa digital"
    PRENSA_IMPRESA = "prensa_impresa", "Prensa impresa"
    RED_SOCIAL = "red_social", "Red social"
    WEB_CORPORATIVA = "web_corporativa", "Web corporativa"
    INFORME_EMPRESA = "informe_empresa", "Informe de la empresa"
    DOCUMENTO_INTERNO = "documento_interno", "Documento interno"
    OTRA = "otra", "Otra"


class CategoriaEvidencia(models.TextChoices):
    SERVICIO_MUNICIPAL = "servicio_municipal", "Servicio municipal"
    CONTRATO = "contrato", "Contrato"
    MENCION_MEDIOS = "mencion_medios", "Mención en medios"
    EVENTO = "evento", "Evento"
    PREMIO = "premio", "Premio"
    ALIANZA = "alianza", "Alianza"
    INNOVACION_FINANCIACION = "innovacion_financiacion", "Innovación y financiación"
    SOSTENIBILIDAD = "sostenibilidad", "Sostenibilidad"
    GRUPO_INTERES = "grupo_interes", "Grupo de interés"
    DIGITAL = "digital", "Digital"
    OTRA = "otra", "Otra"


class VinculoTerritorial(models.TextChoices):
    SI = "si", "Sí"
    NO = "no", "No"
    DUDOSO = "dudoso", "Dudoso"


class Gestion(models.TextChoices):
    INDIRECTA = "indirecta", "Indirecta"
    DIRECTA_MUNICIPAL = "directa_municipal", "Directa municipal"
    EMPRESA_PUBLICA = "empresa_publica", "Empresa pública"
    CONSORCIAL = "consorcial", "Consorcial"
    NO_LOCALIZADA = "no_localizada", "No localizada"


class Vigencia(models.TextChoices):
    SI = "si", "Sí"
    NO = "no", "No"
    DESCONOCIDA = "desconocida", "Desconocida"
