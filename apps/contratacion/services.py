"""Clasificación de expedientes, vinculación de órganos y resolución de adjudicatarios."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from django.contrib.contenttypes.models import ContentType

from apps.entidades.models import Empresa
from apps.entidades.services import resolver_empresa
from apps.nucleo.models import ElementoRevision
from apps.nucleo.texto import normalizar_texto
from apps.territorio.services import resolver_municipio_compuesto

from .models import Adjudicacion, Expediente, OrganoContratacion, ReglaClasificacion

PROVINCIAS_CV = ("03", "12", "46")
Tipo = ElementoRevision.Tipo


# --- Reglas -------------------------------------------------------------------------------


def cargar_reglas(ruta: Path) -> tuple[int, int]:
    """Idempotente: crea las reglas que faltan y no toca las existentes (pueden estar
    editadas). Devuelve (nuevas, existentes)."""
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    nuevas = existentes = 0
    for r in datos["reglas"]:
        patron_norm = r["patron"].strip() if r["tipo"] == "cpv" else normalizar_texto(r["patron"])
        _, creada = ReglaClasificacion.objects.get_or_create(
            tipo=r["tipo"],
            patron_normalizado=patron_norm,
            defaults={
                "patron": r["patron"],
                "servicio": r["servicio"],
                "alcance": r.get("alcance", ""),
                "nota": r.get("nota", ""),
            },
        )
        nuevas += creada
        existentes += not creada
    return nuevas, existentes


@dataclass
class Clasificacion:
    servicio: str = ""
    alcance: str = ""
    metodo: str = Expediente.Clasificacion.SIN_CLASIFICAR
    regla: str = ""
    ambigua: bool = False


class Clasificador:
    """Carga las reglas activas una vez por lote."""

    def __init__(self):
        reglas = list(ReglaClasificacion.objects.filter(activa=True))
        self.cpv = sorted(
            (r for r in reglas if r.tipo == ReglaClasificacion.Tipo.CPV),
            key=lambda r: -len(r.patron_normalizado),
        )
        self.palabras = [r for r in reglas if r.tipo == ReglaClasificacion.Tipo.PALABRAS]

    def clasificar(self, cpvs: list[str], objeto: str) -> Clasificacion:
        """1) El primer CPV (en el orden de la fuente) que case con una regla, con el prefijo
        más largo. 2) Si ningún CPV casa, frases del objeto: solo si todas las que aparecen
        son del mismo servicio. Varias de servicios distintos = ambigua (a la bandeja)."""
        for cpv in cpvs:
            for r in self.cpv:
                if cpv.startswith(r.patron_normalizado):
                    return Clasificacion(r.servicio, r.alcance, "cpv", f"CPV {r.patron}")
        texto = f" {normalizar_texto(objeto)} "
        coincidencias = [
            r for r in self.palabras if re.search(rf"\b{re.escape(r.patron_normalizado)}\b", texto)
        ]
        servicios = {r.servicio for r in coincidencias}
        if len(servicios) == 1:
            alcances = {r.alcance for r in coincidencias}
            r = coincidencias[0]
            alcance = r.alcance if len(alcances) == 1 else ""
            return Clasificacion(r.servicio, alcance, "palabras_clave", f"«{r.patron}»")
        if len(servicios) > 1:
            return Clasificacion(
                ambigua=True,
                regla="; ".join(f"«{r.patron}» → {r.servicio}" for r in coincidencias),
            )
        return Clasificacion()


# --- Órganos ------------------------------------------------------------------------------

_MUNICIPAL = re.compile(r"\b(?:ayuntamiento|ajuntament)\s+(?:de\s+|d')(?P<nombre>.+)$")


def nombre_municipio_del_organo(nombre: str) -> str | None:
    """«Junta de Gobierno del Ayuntamiento de Monforte del Cid» → «monforte del cid»."""
    norm = normalizar_texto(nombre)
    coincidencias = list(_MUNICIPAL.finditer(norm))
    if not coincidencias:
        return None
    return coincidencias[-1]["nombre"].strip(" .,")


def vincular_organo(organo: OrganoContratacion, lote=None) -> None:
    """Vincula un órgano con su municipio solo si no hay duda (docs/04 §1, CP-03 y CP-04).

    Candidatos: el nombre que sigue a «Ayuntamiento de / Ajuntament de» al final del nombre del
    órgano y, si la jerarquía es «<municipio> › Ayuntamientos › …», el primer nivel. Se resuelven
    con coincidencia exacta y única, restringida a la provincia del código postal si es de la
    CV. Todos los candidatos resueltos deben dar el mismo municipio. Un órgano municipal que no
    se resuelve va a la bandeja; uno no municipal queda como «no aplica».
    """
    if organo.estado_vinculacion == OrganoContratacion.Vinculacion.VALIDADA:
        return
    candidatos = []
    nombre = nombre_municipio_del_organo(organo.nombre)
    if nombre:
        candidatos.append(nombre)
    jer = organo.jerarquia or []
    if len(jer) >= 2 and normalizar_texto(jer[1]) == "ayuntamientos":
        candidatos.append(jer[0])
    if not candidatos:
        organo.estado_vinculacion = OrganoContratacion.Vinculacion.NO_APLICA
        organo.municipio = None
        organo.save()
        return
    cp = organo.codigo_postal[:2]
    provincias = [cp] if cp in PROVINCIAS_CV else None
    resueltos = {m.pk: m for c in candidatos if (m := resolver_municipio_compuesto(c, provincias))}
    if len(resueltos) == 1:
        organo.municipio = next(iter(resueltos.values()))
        organo.estado_vinculacion = OrganoContratacion.Vinculacion.AUTOMATICA
        organo.save()
        return
    organo.municipio = None
    organo.estado_vinculacion = OrganoContratacion.Vinculacion.PENDIENTE
    organo.save()
    ElementoRevision.objects.get_or_create(
        clave=f"organo:{organo.pk}",
        defaults={
            "tipo": Tipo.VINCULO_ORGANO,
            "texto": organo.nombre[:500],
            "motivo": (
                "Órgano municipal sin municipio claro: "
                + (
                    "los candidatos dan municipios distintos."
                    if resueltos
                    else f"«{' / '.join(candidatos)}» no coincide exactamente con un municipio."
                )
            ),
            "propuesta": {"candidatos": candidatos},
            "objeto_tipo": ContentType.objects.get_for_model(organo),
            "objeto_id": organo.pk,
            "lote_importacion": lote,
        },
    )


# --- Adjudicatarios -----------------------------------------------------------------------

_FORMA_JURIDICA = re.compile(
    r"[\s,]+(s\.?\s?a\.?\s?u\.?|s\.?\s?l\.?\s?u\.?|s\.?\s?a\.?|s\.?\s?l\.?|s\.?\s?coop\.?(\s?v\.?)?)$"
)


def sin_forma_juridica(texto: str) -> str:
    """«URBASER, S.A.» → «urbaser». Solo quita la forma jurídica final."""
    norm = normalizar_texto(texto)
    anterior = None
    while anterior != norm:
        anterior = norm
        norm = _FORMA_JURIDICA.sub("", norm).strip(" ,.")
    return norm


def resolver_adjudicatario(texto: str, nif: str) -> Empresa | None:
    """Por NIF si alguna empresa del catálogo lo tiene; si no, por alias o nombre (las reglas
    de `resolver_empresa`) con y sin la forma jurídica final. Nunca por parecido."""
    nif = (nif or "").strip().upper()
    if nif and "*" not in nif:
        empresa = Empresa.objects.filter(nif=nif, activa=True).first()
        if empresa:
            return empresa
    if not texto:
        return None
    for variante in (texto, sin_forma_juridica(texto)):
        r = resolver_empresa(variante)
        if r.empresa:
            return r.empresa
    return None


def revisar_adjudicatario(adj: Adjudicacion, lote=None) -> None:
    """Un adjudicatario sin empresa en un contrato de agua, residuos o energía va a la bandeja
    (fuera de esos servicios no interesa resolverlo)."""
    if adj.empresa_id or not adj.adjudicatario_texto or not adj.expediente.servicio_clasificado:
        return
    ElementoRevision.objects.get_or_create(
        clave=f"adjudicatario:{adj.pk}",
        defaults={
            "tipo": Tipo.ADJUDICATARIO_NO_RESUELTO,
            "texto": adj.adjudicatario_texto[:500],
            "motivo": "El adjudicatario no está en el catálogo de empresas (ni por NIF ni por "
            "alias).",
            "propuesta": {"nif": adj.adjudicatario_nif},
            "objeto_tipo": ContentType.objects.get_for_model(adj),
            "objeto_id": adj.pk,
            "lote_importacion": lote,
        },
    )


def revisar_clasificacion(exp: Expediente, clasificacion: Clasificacion, lote=None) -> None:
    if not clasificacion.ambigua:
        return
    ElementoRevision.objects.get_or_create(
        clave=f"clasificacion:{exp.pk}",
        defaults={
            "tipo": Tipo.CLASIFICACION_SERVICIO,
            "texto": exp.objeto[:500] or exp.id_externo,
            "motivo": f"El objeto apunta a varios servicios: {clasificacion.regla}.",
            "objeto_tipo": ContentType.objects.get_for_model(exp),
            "objeto_id": exp.pk,
            "lote_importacion": lote,
        },
    )
