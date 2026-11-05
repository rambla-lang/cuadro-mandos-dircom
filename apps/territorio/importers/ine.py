"""Importador de la «Relación de municipios y sus códigos por provincias» del INE.

Fuente y formato verificados el 05/11/2026 (docs/04 §10): un xlsx con una hoja por provincia
(nombre de la hoja = código de provincia), título en la fila 1, nombre de la provincia en la
fila 2, cabecera `CPRO, CMUN, DC, NOMBRE` en la fila 3 y un municipio por fila después.

Idempotente por `codigo_ine` (CPRO + CMUN). No borra municipios ni nombres alternativos
añadidos a mano: solo añade los que derivan del nombre del INE.
"""

import hashlib
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from django.db import transaction
from django.utils import timezone
from openpyxl import load_workbook

from apps.nucleo.models import LoteImportacion
from apps.nucleo.texto import normalizar_texto

from ..models import Municipio, Provincia
from ..services import variantes_nombre_ine

URL_FUENTE = "https://www.ine.es/daco/daco42/codmun/26codmun.xlsx"
CABECERA = ("CPRO", "CMUN", "DC", "NOMBRE")


class FormatoIneError(ValueError):
    pass


@dataclass
class FilaIne:
    codigo_ine: str
    nombre: str


@dataclass
class HojaIne:
    codigo: str
    nombre_provincia: str
    filas: list[FilaIne] = field(default_factory=list)


def leer_hojas(ruta: Path, provincias: list[str]) -> list[HojaIne]:
    libro = load_workbook(ruta, read_only=True, data_only=True)
    try:
        hojas = []
        for codigo in provincias:
            if codigo not in libro.sheetnames:
                raise FormatoIneError(f"El fichero no tiene la hoja de la provincia {codigo}.")
            filas = libro[codigo].iter_rows(values_only=True)
            next(filas, None)  # título
            nombre_prov = (next(filas, None) or [None])[0]
            cabecera = tuple(next(filas, None) or ())[:4]
            if cabecera != CABECERA or not nombre_prov:
                raise FormatoIneError(
                    f"Hoja {codigo}: cabecera {cabecera!r}; se esperaba {CABECERA!r}."
                )
            hoja = HojaIne(codigo=codigo, nombre_provincia=str(nombre_prov).strip())
            for fila in filas:
                if not fila or fila[0] is None:
                    continue
                cpro, cmun, _dc, nombre = (
                    str(v).strip() if v is not None else "" for v in fila[:4]
                )
                if cpro != codigo or not cmun.isdigit() or len(cmun) != 3 or not nombre:
                    raise FormatoIneError(f"Hoja {codigo}: fila inesperada {fila!r}.")
                hoja.filas.append(FilaIne(codigo_ine=cpro + cmun, nombre=nombre))
            hojas.append(hoja)
        return hojas
    finally:
        libro.close()


def sha256_de(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 16), b""):
            h.update(bloque)
    return h.hexdigest()


@transaction.atomic
def importar_municipios_ine(
    ruta: Path, provincias: list[str], comunidad: str, usuario=None
) -> LoteImportacion:
    ruta = Path(ruta)
    hojas = leer_hojas(ruta, provincias)
    lote = LoteImportacion.objects.create(
        tipo="municipios_ine",
        parametros={
            "fichero": ruta.name,
            "url_fuente": URL_FUENTE,
            "provincias": provincias,
            "comunidad": comunidad,
        },
        archivo_sha256=sha256_de(ruta),
        usuario=usuario,
    )

    # Variantes de cada municipio y recuento de formas normalizadas para detectar choques.
    variantes = {}
    usos = defaultdict(set)
    for hoja in hojas:
        for fila in hoja.filas:
            completas, sin_art = variantes_nombre_ine(fila.nombre)
            variantes[fila.codigo_ine] = (completas, sin_art)
            for forma in (fila.nombre, *completas, *sin_art):
                usos[normalizar_texto(forma)].add(fila.codigo_ine)

    for hoja in hojas:
        provincia, creada = Provincia.objects.get_or_create(
            codigo_ine=hoja.codigo,
            defaults={"nombre": hoja.nombre_provincia, "comunidad": comunidad},
        )
        if not creada and (provincia.nombre, provincia.comunidad) != (
            hoja.nombre_provincia,
            comunidad,
        ):
            provincia.nombre, provincia.comunidad = hoja.nombre_provincia, comunidad
            provincia.save()
        for fila in hoja.filas:
            lote.leidos += 1
            completas, sin_art = variantes[fila.codigo_ine]
            sin_art_ok = []
            for forma in sin_art:
                if usos[normalizar_texto(forma)] == {fila.codigo_ine}:
                    sin_art_ok.append(forma)
                else:
                    lote.anotar(
                        f"{fila.codigo_ine} {fila.nombre}: no se añade «{forma}» "
                        "porque coincide con otro municipio."
                    )
            derivadas = [f for f in (*completas, *sin_art_ok) if f != fila.nombre]

            municipio = Municipio.objects.filter(codigo_ine=fila.codigo_ine).first()
            if municipio is None:
                Municipio.objects.create(
                    codigo_ine=fila.codigo_ine,
                    nombre_oficial=fila.nombre,
                    nombres_alternativos=derivadas,
                    provincia=provincia,
                    lote_importacion=lote,
                )
                lote.nuevos += 1
                continue
            alternativos = list(municipio.nombres_alternativos)
            for forma in derivadas:
                if forma not in alternativos:
                    alternativos.append(forma)
            cambios = (
                municipio.nombre_oficial != fila.nombre
                or alternativos != municipio.nombres_alternativos
                or municipio.provincia_id != provincia.pk
            )
            if cambios:
                if municipio.nombre_oficial != fila.nombre:
                    lote.anotar(
                        f"{fila.codigo_ine}: nombre «{municipio.nombre_oficial}» → «{fila.nombre}»."
                    )
                municipio.nombre_oficial = fila.nombre
                municipio.nombres_alternativos = alternativos
                municipio.provincia = provincia
                municipio.lote_importacion = lote
                municipio.save()
                lote.actualizados += 1

    codigos_fichero = set(variantes)
    ausentes = Municipio.objects.filter(provincia__codigo_ine__in=provincias).exclude(
        codigo_ine__in=codigos_fichero
    )
    for m in ausentes:
        lote.anotar(f"{m.codigo_ine} {m.nombre_oficial}: no figura en el fichero; se conserva.")

    lote.fin = timezone.now()
    lote.save()
    return lote
