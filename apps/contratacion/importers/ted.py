"""Importador de TED: Search API v3 (docs/04 §2).

Campos verificados con peticiones reales (05/11/2026 y 06/11/2026). Clave natural:
`publication-number`. Cautelas aplicadas:
- `place-of-performance IN (ES52)` trae también contratos de ámbito nacional: solo se guardan
  los avisos cuyo comprador es valenciano (su identificador coincide con un órgano ya conocido
  de la CV o su ciudad es un municipio de la CV). Los demás se cuentan y se anotan.
- `winner-identifier` puede venir enmascarado: no se usa como NIF.
- `total-value` no tiene significado documentado: se guarda como «valor TED» sin interpretarlo.
"""

import time
from dataclasses import dataclass, field
from datetime import date

import httpx
from django.db.models import F

from apps.evidencias.enums import NivelEvidencia
from apps.territorio.services import resolver_municipio

from ..models import Adjudicacion, Expediente, FuenteContrato, OrganoContratacion
from ..services import (
    PROVINCIAS_CV,
    Clasificador,
    resolver_adjudicatario,
    revisar_adjudicatario,
    revisar_clasificacion,
    vincular_organo,
)

URL_BUSQUEDA = "https://api.ted.europa.eu/v3/notices/search"
CAMPOS = [
    "publication-number",
    "notice-type",
    "publication-date",
    "notice-title",
    "buyer-name",
    "buyer-identifier",
    "buyer-city",
    "classification-cpv",
    "winner-name",
    "total-value",
]
POR_PAGINA = 100
PAUSA_SEGUNDOS = 1.1  # máximo 1 petición por segundo (no hay límite publicado; docs/04 §2)
URL_AVISO = "https://ted.europa.eu/es/notice/-/detail/{numero}"


def consulta(desde: date, hasta: date) -> str:
    return (
        f"place-of-performance IN (ES52) AND publication-date>={desde:%Y%m%d} "
        f"AND publication-date<={hasta:%Y%m%d}"
    )


def pedir_pagina(
    desde: date, hasta: date, pagina: int, cliente: httpx.Client | None = None
) -> dict:
    cuerpo = {
        "query": consulta(desde, hasta),
        "fields": CAMPOS,
        "limit": POR_PAGINA,
        "page": pagina,
        "paginationMode": "PAGE_NUMBER",
    }
    propio = cliente is None
    cliente = cliente or httpx.Client(timeout=60)
    try:
        r = cliente.post(URL_BUSQUEDA, json=cuerpo)
        r.raise_for_status()
        return r.json()
    finally:
        if propio:
            cliente.close()
        time.sleep(PAUSA_SEGUNDOS)


def _primero(valor, idiomas=("spa", "mul", "eng")):
    if isinstance(valor, dict):
        for i in idiomas:
            if valor.get(i):
                v = valor[i]
                return v[0] if isinstance(v, list) else v
        for v in valor.values():
            return v[0] if isinstance(v, list) else v
    if isinstance(valor, list):
        return valor[0] if valor else ""
    return valor or ""


def _lista(valor, idiomas=("spa", "mul", "eng")) -> list[str]:
    if isinstance(valor, dict):
        for i in idiomas:
            if valor.get(i):
                return list(valor[i]) if isinstance(valor[i], list) else [valor[i]]
        return []
    return list(valor or [])


def _sin_repetir(valores):
    vistos, salida = set(), []
    for v in valores:
        if v not in vistos:
            vistos.add(v)
            salida.append(v)
    return salida


@dataclass
class ContadoresTed:
    avisos: int = 0
    no_valencianos: int = 0
    nuevos: int = 0
    existentes: int = 0
    clasificados: int = 0
    descartados_ejemplos: list = field(default_factory=list)

    def como_dict(self) -> dict:
        d = dict(self.__dict__)
        d.pop("descartados_ejemplos")
        return d


class ImportadorTed:
    def __init__(self, lote=None):
        self.lote = lote
        self.clasificador = Clasificador()
        self.c = ContadoresTed()

    def _organo(self, aviso) -> OrganoContratacion | None:
        identificadores = [i for i in _lista(aviso.get("buyer-identifier")) if i and "*" not in i]
        if identificadores:
            organo = (
                OrganoContratacion.objects.filter(id_plataforma__in=identificadores).first()
                or OrganoContratacion.objects.filter(nif__in=identificadores)
                .order_by(F("municipio").asc(nulls_last=True), "pk")
                .first()
            )
            if organo and organo.codigo_postal[:2] in PROVINCIAS_CV:
                return organo
            if organo and organo.municipio_id:
                return organo
        ciudad = _primero(aviso.get("buyer-city"))
        municipio = resolver_municipio(ciudad) if ciudad else None
        if municipio is None:
            return None
        nombre = _primero(aviso.get("buyer-name"))
        nif = next((i for i in identificadores if not i.isdigit()), "")
        organo = OrganoContratacion.objects.filter(
            nombre=nombre, nif=nif, id_plataforma__isnull=True
        ).first()
        if organo is None:
            organo = OrganoContratacion.objects.create(
                nombre=nombre[:500], nif=nif[:20], ciudad=ciudad[:200]
            )
            vincular_organo(organo, self.lote)
        return organo

    def procesar(self, avisos: list[dict]) -> ContadoresTed:
        for aviso in avisos:
            self.c.avisos += 1
            numero = aviso.get("publication-number", "")
            organo = self._organo(aviso)
            if organo is None:
                self.c.no_valencianos += 1
                if len(self.c.descartados_ejemplos) < 20:
                    comprador = _primero(aviso.get("buyer-name"))
                    ciudad = _primero(aviso.get("buyer-city"))
                    self.c.descartados_ejemplos.append(f"{numero} ({comprador}, {ciudad})")
                continue
            if Expediente.objects.filter(fuente=FuenteContrato.TED, id_externo=numero).exists():
                self.c.existentes += 1  # un aviso publicado no cambia
                continue
            titulo = _primero(aviso.get("notice-title"))
            cpvs = _sin_repetir(_lista(aviso.get("classification-cpv")))
            clasif = self.clasificador.clasificar(cpvs, titulo)
            fecha = aviso.get("publication-date", "")[:10]
            exp = Expediente.objects.create(
                fuente=FuenteContrato.TED,
                id_externo=numero,
                numero_expediente=numero,
                organo=organo,
                objeto=titulo,
                cpv=cpvs,
                estado=aviso.get("notice-type", ""),
                fecha_publicacion=date.fromisoformat(fecha) if fecha else None,
                url_origen=URL_AVISO.format(numero=numero),
                criterio_territorial="comprador_cv",
                servicio_clasificado=clasif.servicio,
                alcance_clasificado=clasif.alcance,
                metodo_clasificacion=clasif.metodo,
                regla_clasificacion=clasif.regla[:200],
                lote_importacion=self.lote,
                datos_fuente={
                    "valor_ted": aviso.get("total-value"),
                    "buyer_identifier": _lista(aviso.get("buyer-identifier")),
                    "nota_valor": "total-value de TED sin interpretar (docs/04 §2)",
                },
            )
            revisar_clasificacion(exp, clasif, self.lote)
            if exp.servicio_clasificado:
                self.c.clasificados += 1
            if aviso.get("notice-type", "").startswith("can"):
                ganadores = _sin_repetir(_lista(aviso.get("winner-name"))) or [""]
                for nombre in ganadores:
                    adj = Adjudicacion.objects.create(
                        expediente=exp,
                        adjudicatario_texto=nombre[:500],
                        empresa=resolver_adjudicatario(nombre, ""),
                        nivel=NivelEvidencia.OFICIAL if nombre else NivelEvidencia.PARCIAL,
                    )
                    revisar_adjudicatario(adj, self.lote)
            self.c.nuevos += 1
        return self.c
