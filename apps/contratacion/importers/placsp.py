"""Importador de PLACSP: ficheros ATOM de sindicación y sus ZIP (docs/04 §1, ADR-004, ADR-008).

Rutas XML verificadas en la Fase 0 con el ZIP real de octubre de 2026 (docs/04 §1). Clave
natural: `entry/id`. Se queda la versión con el `updated` mayor (CP-14). Las entradas
eliminadas (`at:deleted-entry`) marcan el expediente, no lo borran.
"""

import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from lxml import etree

from apps.evidencias.enums import NivelEvidencia
from apps.nucleo.models import ElementoRevision

from ..models import Adjudicacion, Expediente, FuenteContrato, LoteContrato, OrganoContratacion
from ..services import (
    PROVINCIAS_CV,
    Clasificador,
    resolver_adjudicatario,
    revisar_adjudicatario,
    revisar_clasificacion,
    vincular_organo,
)

NS = {
    "a": "http://www.w3.org/2005/Atom",
    "cbc": "urn:dgpe:names:draft:codice:schema:xsd:CommonBasicComponents-2",
    "cac": "urn:dgpe:names:draft:codice:schema:xsd:CommonAggregateComponents-2",
    "cacx": "urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonAggregateComponents-2",
    "cbcx": "urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonBasicComponents-2",
    "at": "http://purl.org/atompub/tombstones/1.0",
}
ENTRY = f"{{{NS['a']}}}entry"
DELETED = f"{{{NS['at']}}}deleted-entry"
ESTADOS_ADJUDICADOS = ("ADJ", "RES")
URL_ZIP_MENSUAL = (
    "https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_643/"
    "licitacionesPerfilesContratanteCompleto3_{mes}.zip"
)


def _t(el, ruta: str) -> str:
    if el is None:
        return ""
    v = el.findtext(ruta, namespaces=NS)
    return (v or "").strip()


def _dec(texto: str) -> Decimal | None:
    try:
        return Decimal(texto) if texto else None
    except InvalidOperation:
        return None


def _fecha(texto: str) -> date | None:
    try:
        return date.fromisoformat(texto[:10]) if texto else None
    except ValueError:
        return None


def _ids(party) -> dict[str, str]:
    salida = {}
    if party is None:
        return salida
    for i in party.findall("cac:PartyIdentification/cbc:ID", NS):
        salida.setdefault(i.get("schemeName", ""), (i.text or "").strip())
    return salida


def _cpvs(proyecto) -> list[str]:
    if proyecto is None:
        return []
    return [
        (c.text or "").strip()
        for c in proyecto.findall(
            "cac:RequiredCommodityClassification/cbc:ItemClassificationCode", NS
        )
        if c.text
    ]


def _nuts(proyecto) -> list[str]:
    if proyecto is None:
        return []
    return [
        (c.text or "").strip()
        for c in proyecto.findall("cac:RealizedLocation/cbc:CountrySubentityCode", NS)
        if c.text
    ]


def _duracion(proyecto) -> str:
    if proyecto is None:
        return ""
    d = proyecto.find("cac:PlannedPeriod/cbc:DurationMeasure", NS)
    if d is not None and d.text:
        return f"{d.text.strip()} {d.get('unitCode', '')}".strip()
    inicio = _t(proyecto, "cac:PlannedPeriod/cbc:StartDate")
    fin = _t(proyecto, "cac:PlannedPeriod/cbc:EndDate")
    return f"{inicio} a {fin}" if inicio or fin else ""


def leer_entrada(entry) -> dict:
    """Datos de una `entry` (sin tocar la base de datos)."""
    cfs = entry.find("cacx:ContractFolderStatus", NS)
    party_ext = cfs.find("cacx:LocatedContractingParty", NS) if cfs is not None else None
    party = party_ext.find("cac:Party", NS) if party_ext is not None else None
    jerarquia, nivel = [], party_ext
    while nivel is not None:
        nivel = nivel.find("cacx:ParentLocatedParty", NS)
        if nivel is not None:
            jerarquia.append(_t(nivel, "cac:PartyName/cbc:Name"))
    proyecto = cfs.find("cac:ProcurementProject", NS) if cfs is not None else None
    lotes = []
    for lote in cfs.findall("cac:ProcurementProjectLot", NS) if cfs is not None else []:
        pp = lote.find("cac:ProcurementProject", NS)
        lotes.append(
            {
                "numero": _t(lote, "cbc:ID"),
                "objeto": _t(pp, "cbc:Name"),
                "importe": _dec(_t(pp, "cac:BudgetAmount/cbc:TaxExclusiveAmount")),
                "cpv": _cpvs(pp),
                "nuts": _nuts(pp),
            }
        )
    resultados = []
    for r in cfs.findall("cac:TenderResult", NS) if cfs is not None else []:
        ganador = r.find("cac:WinningParty", NS)
        ids = _ids(ganador)
        resultados.append(
            {
                "codigo": _t(r, "cbc:ResultCode"),
                "fecha_adjudicacion": _fecha(_t(r, "cbc:AwardDate")),
                "fecha_formalizacion": _fecha(_t(r, "cac:Contract/cbc:IssueDate")),
                "adjudicatario": _t(ganador, "cac:PartyName/cbc:Name"),
                "nif": ids.get("NIF") or ids.get("OTROS", ""),
                "lote": _t(r, "cac:AwardedTenderedProject/cbc:ProcurementProjectLotID"),
                "importe": _dec(
                    _t(
                        r,
                        "cac:AwardedTenderedProject/cac:LegalMonetaryTotal/cbc:TaxExclusiveAmount",
                    )
                ),
                "pagable": _dec(
                    _t(r, "cac:AwardedTenderedProject/cac:LegalMonetaryTotal/cbc:PayableAmount")
                ),
            }
        )
    fechas_pub = sorted(
        f
        for f in (
            _fecha((d.text or "").strip())
            for d in (
                cfs.findall(".//cacx:AdditionalPublicationDocumentReference/cbc:IssueDate", NS)
                if cfs is not None
                else []
            )
        )
        if f
    )
    ted = ""
    if cfs is not None:
        for u in cfs.findall("cbc:UUID", NS):
            if u.get("schemeName") == "TED":
                ted = (u.text or "").strip()
    link = entry.find("a:link", NS)
    ids_organo = _ids(party)
    return {
        "id": _t(entry, "a:id"),
        "updated": datetime.fromisoformat(_t(entry, "a:updated")),
        "url": link.get("href", "") if link is not None else "",
        "titulo": _t(entry, "a:title"),
        "numero": _t(cfs, "cbc:ContractFolderID"),
        "estado": _t(cfs, "cbcx:ContractFolderStatusCode"),
        "organo": {
            "id_plataforma": ids_organo.get("ID_PLATAFORMA", ""),
            "nif": ids_organo.get("NIF", ""),
            "dir3": ids_organo.get("DIR3", ""),
            "nombre": _t(party, "cac:PartyName/cbc:Name"),
            "ciudad": _t(party, "cac:PostalAddress/cbc:CityName"),
            "codigo_postal": _t(party, "cac:PostalAddress/cbc:PostalZone"),
            "tipo_poder": _t(party_ext, "cbc:ContractingPartyTypeCode"),
            "jerarquia": jerarquia,
        },
        "objeto": _t(proyecto, "cbc:Name"),
        "tipo": _t(proyecto, "cbc:TypeCode"),
        "importe": _dec(_t(proyecto, "cac:BudgetAmount/cbc:TaxExclusiveAmount")),
        "importe_con_iva": _dec(_t(proyecto, "cac:BudgetAmount/cbc:TotalAmount")),
        "valor_estimado": _dec(_t(proyecto, "cac:BudgetAmount/cbc:EstimatedOverallContractAmount")),
        "cpv": _cpvs(proyecto),
        "nuts": _nuts(proyecto),
        "duracion": _duracion(proyecto),
        "lotes": lotes,
        "resultados": resultados,
        "fecha_publicacion": fechas_pub[0] if fechas_pub else None,
        "ted": ted,
    }


def criterio_territorial(datos: dict) -> str:
    """NUTS de ejecución ES52* o código postal del órgano en la CV (docs/04 §1)."""
    nuts = datos["nuts"] + [n for lote in datos["lotes"] for n in lote["nuts"]]
    por_nuts = any(n.startswith("ES52") for n in nuts)
    por_cp = datos["organo"]["codigo_postal"][:2] in PROVINCIAS_CV
    if por_nuts and por_cp:
        return "nuts_y_cp_organo"
    if por_nuts:
        return "nuts_ejecucion"
    if por_cp:
        return "cp_organo"
    return ""


@dataclass
class Contadores:
    entradas: int = 0
    fuera_cv: int = 0
    nuevos: int = 0
    actualizados: int = 0
    antiguos: int = 0
    eliminados: int = 0
    eliminados_desconocidos: int = 0
    clasificados: int = 0
    errores: list = field(default_factory=list)

    def como_dict(self) -> dict:
        d = dict(self.__dict__)
        d["errores"] = len(self.errores)
        return d


class ImportadorPlacsp:
    def __init__(self, lote=None):
        self.lote = lote
        self.clasificador = Clasificador()
        self.c = Contadores()
        self._organos: dict[str, OrganoContratacion] = {}

    # -- lectura --
    def procesar_atom(self, origen, nombre_fichero: str) -> Contadores:
        """`origen`: ruta o fichero binario abierto. Recorre en streaming y libera memoria."""
        parser_kwargs = {
            "events": ("end",),
            "tag": (ENTRY, DELETED),
            "resolve_entities": False,
            "no_network": True,
            "huge_tree": True,
        }
        for _, el in etree.iterparse(origen, **parser_kwargs):
            try:
                if el.tag == DELETED:
                    self._eliminada(el)
                else:
                    self.c.entradas += 1
                    self._entrada(leer_entrada(el), nombre_fichero)
            except Exception as e:  # noqa: BLE001 - una entrada rota no para el fichero
                self.c.errores.append(f"{nombre_fichero}: {e}")
            finally:
                el.clear()
                while el.getprevious() is not None:
                    del el.getparent()[0]
        return self.c

    # -- escritura --
    def _eliminada(self, el):
        ref = el.get("ref", "")
        cuando = datetime.fromisoformat(el.get("when"))
        exp = Expediente.objects.filter(fuente=FuenteContrato.PLACSP, id_externo=ref).first()
        if exp is None:
            self.c.eliminados_desconocidos += 1
            return
        if exp.fecha_actualizacion_fuente and exp.fecha_actualizacion_fuente >= cuando:
            self.c.antiguos += 1
            return
        exp.eliminado_en_fuente = True
        exp.estado = "ANUL"
        exp.fecha_actualizacion_fuente = cuando
        comentario = el.find("at:comment", NS)
        exp.datos_fuente = {
            **exp.datos_fuente,
            "eliminada": comentario.get("type") if comentario is not None else "",
        }
        exp.save()
        self.c.eliminados += 1

    def _organo(self, d: dict) -> OrganoContratacion | None:
        clave = d["id_plataforma"]
        if not clave:
            return None
        if clave in self._organos:
            return self._organos[clave]
        organo = OrganoContratacion.objects.filter(id_plataforma=clave).first()
        cambiado = organo is None or organo.nombre != d["nombre"]
        if organo is None:
            organo = OrganoContratacion(id_plataforma=clave)
        for campo in (
            "nif",
            "dir3",
            "nombre",
            "ciudad",
            "codigo_postal",
            "tipo_poder",
            "jerarquia",
        ):
            setattr(organo, campo, d[campo] or getattr(organo, campo))
        organo.save()
        if cambiado:
            vincular_organo(organo, self.lote)
        self._organos[clave] = organo
        return organo

    def _entrada(self, d: dict, nombre_fichero: str):
        criterio = criterio_territorial(d)
        if not criterio:
            self.c.fuera_cv += 1
            return
        exp = Expediente.objects.filter(fuente=FuenteContrato.PLACSP, id_externo=d["id"]).first()
        if (
            exp
            and exp.fecha_actualizacion_fuente
            and exp.fecha_actualizacion_fuente >= d["updated"]
        ):
            self.c.antiguos += 1  # CP-14: una versión más antigua no sobrescribe
            return
        nuevo = exp is None
        exp = exp or Expediente(fuente=FuenteContrato.PLACSP, id_externo=d["id"])
        exp.numero_expediente = d["numero"][:200]
        exp.organo = self._organo(d["organo"])
        exp.objeto = d["objeto"] or d["titulo"]
        exp.tipo_contrato = d["tipo"]
        exp.cpv = d["cpv"]
        exp.estado = d["estado"]
        exp.eliminado_en_fuente = False
        exp.importe_licitacion = d["importe"]
        exp.iva_incluido = (
            Expediente.Iva.NO if d["importe"] is not None else Expediente.Iva.DESCONOCIDO
        )
        exp.importe_licitacion_con_iva = d["importe_con_iva"]
        exp.valor_estimado = d["valor_estimado"]
        exp.fecha_publicacion = d["fecha_publicacion"]
        exp.fecha_actualizacion_fuente = d["updated"]
        exp.url_origen = d["url"][:1000]
        exp.nuts = d["nuts"]
        exp.criterio_territorial = criterio
        exp.entrada_atom_id = d["id"]
        exp.fichero_origen = nombre_fichero
        exp.lote_importacion = self.lote
        exp.datos_fuente = (
            {"ted": d["ted"], "duracion": d["duracion"]} if d["ted"] or d["duracion"] else {}
        )
        clasif = None
        if exp.metodo_clasificacion != Expediente.Clasificacion.MANUAL:
            cpvs = d["cpv"] + [c for lote in d["lotes"] for c in lote["cpv"]]
            objeto = " ".join([exp.objeto, *[lote["objeto"] for lote in d["lotes"]]])
            clasif = self.clasificador.clasificar(cpvs, objeto)
            exp.servicio_clasificado = clasif.servicio
            exp.alcance_clasificado = clasif.alcance
            exp.metodo_clasificacion = clasif.metodo
            exp.regla_clasificacion = clasif.regla[:200]
        exp.save()
        if clasif:
            revisar_clasificacion(exp, clasif, self.lote)
        if exp.servicio_clasificado:
            self.c.clasificados += 1
        self._lotes_y_adjudicaciones(exp, d)
        if nuevo:
            self.c.nuevos += 1
        else:
            self.c.actualizados += 1

    def _lotes_y_adjudicaciones(self, exp: Expediente, d: dict):
        previas = {
            (
                a.lote.numero if a.lote else "",
                a.adjudicatario_texto,
                a.adjudicatario_nif,
            ): a.empresa_id
            for a in exp.adjudicaciones.select_related("lote")
        }
        viejas = list(exp.adjudicaciones.values_list("pk", flat=True))
        if viejas:
            ElementoRevision.objects.filter(
                clave__in=[f"adjudicatario:{pk}" for pk in viejas],
                estado=ElementoRevision.Estado.PENDIENTE,
            ).delete()
        exp.adjudicaciones.all().delete()
        exp.lotes.all().delete()
        lotes = {}
        for lote in d["lotes"]:
            if lote["numero"] in lotes:
                continue
            lotes[lote["numero"]] = LoteContrato.objects.create(
                expediente=exp,
                numero=lote["numero"][:50],
                objeto=lote["objeto"],
                importe=lote["importe"],
                cpv=lote["cpv"],
            )
        resultados = d["resultados"]
        if not resultados and d["estado"] in ESTADOS_ADJUDICADOS:
            resultados = [
                {
                    "codigo": "",
                    "fecha_adjudicacion": None,
                    "fecha_formalizacion": None,
                    "adjudicatario": "",
                    "nif": "",
                    "lote": "",
                    "importe": None,
                    "pagable": None,
                }
            ]
        for r in resultados:
            texto, nif = r["adjudicatario"], r["nif"]
            empresa_id = previas.get((r["lote"], texto, nif))
            empresa = None if empresa_id else resolver_adjudicatario(texto, nif)
            adj = Adjudicacion.objects.create(
                expediente=exp,
                lote=lotes.get(r["lote"]),
                adjudicatario_texto=texto[:500],
                adjudicatario_nif=nif[:30],
                empresa_id=empresa_id or (empresa.pk if empresa else None),
                importe_adjudicacion=r["importe"],
                importe_pagable=r["pagable"],
                fecha_adjudicacion=r["fecha_adjudicacion"],
                fecha_formalizacion=r["fecha_formalizacion"],
                duracion_texto=d["duracion"][:200],
                codigo_resultado=r["codigo"][:10],
                # CP-06: sin adjudicatario publicado no se inventa nada; nivel parcial.
                nivel=NivelEvidencia.OFICIAL
                if texto and exp.url_origen
                else NivelEvidencia.PARCIAL,
            )
            revisar_adjudicatario(adj, self.lote)


def miembros_zip(ruta: Path) -> list[str]:
    with zipfile.ZipFile(ruta) as z:
        return sorted(n for n in z.namelist() if n.endswith(".atom"))


def procesar_miembro_zip(ruta: Path, miembro: str, importador: ImportadorPlacsp) -> Contadores:
    with zipfile.ZipFile(ruta) as z, z.open(miembro) as f:
        return importador.procesar_atom(f, f"{Path(ruta).name}:{miembro}")
