"""Importador de tablas municipales en Excel o CSV (docs/04 §9).

Cada celda de operador de una fila produce, como mucho, una `Evidencia` (categoría servicio
municipal) y su `PrestacionServicio`. Lo que no se puede decidir sin una persona va a la bandeja
de revisión (`ElementoRevision`): municipios que no casan, operadores que no están en el
catálogo y niveles que la tabla no permite fijar.

Configuración (la guarda el asistente como `PlantillaImportacion`):

    {
      "hoja": "Municipios Veolia",          # None en CSV
      "fila_cabecera": 1,
      "columna_municipio": "MUNICIPIO",
      "columna_provincia": null,            # opcional; solo restringe la búsqueda
      "fuente": {"tipo": "documento_interno", "nombre": "..."},
      "fecha_consulta": "2026-11-03",       # cuándo se elaboró o consultó la tabla
      "estado": "validada" | "borrador",
      "valores_nivel": {"Confirmado (prensa)": "prensa", "Confirmado": "decidir", ...},
      "bloques": [
        {
          "servicio": "residuos",           # o "" si sale de columna_servicio
          "alcance": "",                    # "" = sin especificar
          "columna_servicio": null,         # formato largo: una fila por servicio
          "valores_servicio": {"Agua": {"servicio": "agua", "alcance": ""}, ...},
          "columna_operador": "SERVICIO DE RESIDUOS",
          "columna_detalle": "Residuos: detalle",
          "columna_figura": null,
          "columna_fuente": "Residuos: fuente",
          "columna_anio": "Residuos: año",
          "columna_nivel": "Residuos: nivel",
          "nivel_por_defecto": "decidir",   # si no hay columna de nivel o viene vacía
          "columnas_extra": ["PLACSP: residuos (04/11/2026)"]
        }
      ]
    }

Clave natural (idempotencia): fuente, hoja, municipio tal como viene, servicio, alcance y
operador tal como viene. Reimportar el mismo fichero no crea nada nuevo.
"""

import csv
import hashlib
import io
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from apps.entidades.services import resolver_empresa
from apps.nucleo.models import ElementoRevision, LoteImportacion
from apps.nucleo.services import registrar_auditoria
from apps.nucleo.texto import normalizar_texto
from apps.territorio.models import Municipio
from apps.territorio.services import (
    resolver_municipio_compuesto,
    resolver_provincia,
    sugerencias_municipio,
)

from ..enums import (
    ALCANCES_POR_SERVICIO,
    CategoriaEvidencia,
    EstadoValidacion,
    Gestion,
    NivelEvidencia,
    Origen,
    Servicio,
)
from ..models import (
    MAX_PALABRAS_EXTRACTO,
    Evidencia,
    EvidenciaEmpresa,
    EvidenciaMunicipio,
    Fuente,
    PrestacionServicio,
)

TIPO_LOTE = "tabla_municipal"
DECIDIR = "decidir"  # el nivel lo fija una persona en la bandeja
EXTENSIONES = (".csv", ".xlsx")

_URL = re.compile(r"https?://[^\s;,)]+")
# Número de publicación de TED tal como aparece en las tablas: «TED 421269-2022».
_TED = re.compile(r"\bTED\s+(\d{1,7}-\d{4})\b")
# Forma verificada del enlace a un aviso de TED (campo links.html.SPA de la Search API,
# tests/fixtures/ted/, docs/04 §2).
URL_AVISO_TED = "https://ted.europa.eu/es/notice/-/detail/{numero}"


class FormatoTablaError(ValueError):
    pass


# --- Lectura -----------------------------------------------------------------------------


def _texto_celda(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    if isinstance(valor, date):
        return valor.isoformat()
    return str(valor).strip()


def _cabeceras_unicas(fila) -> list[str]:
    salida, vistas = [], set()
    for i, valor in enumerate(fila, start=1):
        nombre = _texto_celda(valor) or f"Columna {i}"
        base, n = nombre, 2
        while nombre in vistas:
            nombre, n = f"{base} ({n})", n + 1
        vistas.add(nombre)
        salida.append(nombre)
    return salida


def hojas(ruta: Path) -> list[str]:
    """Nombres de las hojas de un .xlsx (lista vacía para CSV)."""
    if Path(ruta).suffix.lower() != ".xlsx":
        return []
    import openpyxl

    libro = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    try:
        return list(libro.sheetnames)
    finally:
        libro.close()


def _filas_crudas(ruta: Path, hoja: str | None):
    ruta = Path(ruta)
    sufijo = ruta.suffix.lower()
    if sufijo == ".csv":
        crudo = ruta.read_bytes()
        for codificacion in ("utf-8-sig", "cp1252"):
            try:
                texto = crudo.decode(codificacion)
                break
            except UnicodeDecodeError:
                continue
        else:  # pragma: no cover - cp1252 decodifica casi todo
            raise FormatoTablaError("No se reconoce la codificación del CSV.")
        try:
            dialecto = csv.Sniffer().sniff(texto[:4096], delimiters=",;\t")
        except csv.Error:
            dialecto = csv.excel
        return list(csv.reader(io.StringIO(texto), dialecto))
    if sufijo == ".xlsx":
        import openpyxl

        libro = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
        try:
            if hoja is None:
                hoja = libro.sheetnames[0]
            if hoja not in libro.sheetnames:
                raise FormatoTablaError(f"El libro no tiene la hoja «{hoja}».")
            return [list(f) for f in libro[hoja].iter_rows(values_only=True)]
        finally:
            libro.close()
    raise FormatoTablaError("Formato no admitido: solo .csv y .xlsx.")


def leer_tabla(
    ruta: Path, hoja: str | None = None, fila_cabecera: int = 1
) -> tuple[list[str], list[tuple[int, dict]]]:
    """(cabeceras, [(número de fila, {cabecera: texto})]); se saltan las filas vacías."""
    crudas = _filas_crudas(ruta, hoja)
    if len(crudas) < fila_cabecera:
        raise FormatoTablaError("La tabla no tiene la fila de cabecera indicada.")
    cabeceras = _cabeceras_unicas(crudas[fila_cabecera - 1])
    filas = []
    for n, fila in enumerate(crudas[fila_cabecera:], start=fila_cabecera + 1):
        valores = {c: _texto_celda(v) for c, v in zip(cabeceras, fila, strict=False)}
        if any(valores.values()):
            filas.append((n, valores))
    return cabeceras, filas


def valores_distintos(filas: list[tuple[int, dict]], columna: str | None) -> list[str]:
    if not columna:
        return []
    return sorted({v[columna] for _, v in filas if v.get(columna)})


def proponer_nivel(valor: str) -> str | None:
    """Propuesta para la correspondencia de valores: el nivel cuya etiqueta abre el texto
    («Confirmado (fuente oficial) (contrato de 2019)» → oficial). Solo es una propuesta: quien
    importa la confirma o la cambia en el asistente."""
    norm = normalizar_texto(valor)
    if not norm:
        return None
    candidatos = sorted(NivelEvidencia, key=lambda n: -len(n.label))
    for nivel in candidatos:
        if norm.startswith(normalizar_texto(nivel.label)):
            return str(nivel)
    return None


# --- Normalización de filas --------------------------------------------------------------


def _clave(fuente_id: int, hoja: str | None, fila: dict) -> str:
    base = "|".join(
        [
            str(fuente_id),
            hoja or "",
            normalizar_texto(fila["municipio_texto"]),
            fila["servicio"],
            fila["alcance"],
            normalizar_texto(fila["operador_texto"]),
        ]
    )
    return "tabla:" + hashlib.sha1(base.encode("utf-8")).hexdigest()


def _anio(valor: str) -> int | None:
    return int(valor) if re.fullmatch(r"(19|20)\d{2}", valor or "") else None


def _servicio_del_bloque(bloque: dict, valores: dict) -> tuple[str, str] | None:
    columna = bloque.get("columna_servicio")
    if not columna:
        return bloque["servicio"], bloque.get("alcance", "")
    destino = (bloque.get("valores_servicio") or {}).get(valores.get(columna, ""))
    if not destino:
        return None
    return destino["servicio"], destino.get("alcance", "")


def normalizar_filas(
    filas: list[tuple[int, dict]], config: dict, fuente_id: int
) -> tuple[list[dict], list[str], int]:
    """Convierte las filas en filas normalizadas (una por bloque con operador).

    Devuelve (filas_normalizadas, errores, celdas_sin_dato).
    """
    salida, errores, sin_dato = [], [], 0
    valores_nivel = config.get("valores_nivel") or {}
    for n, valores in filas:
        municipio_texto = valores.get(config["columna_municipio"], "")
        if not municipio_texto:
            errores.append(f"Fila {n}: sin municipio.")
            continue
        provincia = None
        if config.get("columna_provincia"):
            provincia = resolver_provincia(valores.get(config["columna_provincia"], ""))
        for bloque in config["bloques"]:
            operador = valores.get(bloque["columna_operador"], "")
            if not operador:
                continue
            destino = _servicio_del_bloque(bloque, valores)
            if destino is None:
                errores.append(
                    f"Fila {n}: el servicio «{valores.get(bloque['columna_servicio'], '')}» "
                    "no tiene correspondencia."
                )
                continue
            servicio, alcance = destino
            detalle = valores.get(bloque.get("columna_detalle") or "", "")
            fuente_texto = valores.get(bloque.get("columna_fuente") or "", "")
            if normalizar_texto(operador) == "no localizado" and not (detalle or fuente_texto):
                sin_dato += 1  # nada que trazar; el mapa ya lo muestra como «No localizado»
                continue
            nivel_original = valores.get(bloque.get("columna_nivel") or "", "")
            if nivel_original:
                nivel = valores_nivel.get(nivel_original) or proponer_nivel(nivel_original)
                if not nivel:
                    nivel = DECIDIR
            else:
                nivel = bloque.get("nivel_por_defecto") or DECIDIR
            fila = {
                "n": n,
                "municipio_texto": municipio_texto,
                "provincia": provincia,
                "servicio": servicio,
                "alcance": alcance or "",
                "operador_texto": operador,
                "detalle": detalle,
                "figura": valores.get(bloque.get("columna_figura") or "", ""),
                "fuente_texto": fuente_texto,
                "anio_texto": valores.get(bloque.get("columna_anio") or "", ""),
                "nivel_original": nivel_original,
                "nivel": nivel,
                "columnas_extra": {
                    c: valores[c] for c in bloque.get("columnas_extra") or [] if valores.get(c)
                },
            }
            fila["clave"] = _clave(fuente_id, config.get("hoja"), fila)
            salida.append(fila)
    return salida, errores, sin_dato


# --- Aplicación --------------------------------------------------------------------------


@dataclass
class Resultado:
    filas_leidas: int = 0
    celdas_sin_dato: int = 0
    evidencias_nuevas: int = 0
    evidencias_existentes: int = 0
    prestaciones_nuevas: int = 0
    descartadas_en_revision: int = 0
    ya_en_revision: int = 0
    a_revision: dict = field(default_factory=dict)
    errores: list = field(default_factory=list)
    lote_id: int | None = None
    aplicado: bool = False

    def sumar_revision(self, tipo: str):
        self.a_revision[str(tipo)] = self.a_revision.get(str(tipo), 0) + 1

    @property
    def total_revision(self) -> int:
        return sum(self.a_revision.values())


def _referencias(fuente_texto: str) -> tuple[str, list[str], str | None]:
    """(url_origen, referencias, número TED del que se derivó la URL o None)."""
    urls = [u.rstrip(".") for u in _URL.findall(fuente_texto or "")]
    teds = _TED.findall(fuente_texto or "")
    if urls:
        return urls[0], urls + [f"TED {t}" for t in teds], None
    if teds:
        return URL_AVISO_TED.format(numero=teds[0]), [f"TED {t}" for t in teds], teds[0]
    return "", [], None


def _interpretar_operador(texto: str):
    """(gestion, empresa, operador_texto, motivo_revision)."""
    norm = normalizar_texto(texto)
    if norm == "no localizado":
        return Gestion.NO_LOCALIZADA, None, "", ""
    if "gestion directa" in norm:
        return Gestion.DIRECTA_MUNICIPAL, None, texto, ""
    if "empresa municipal" in norm or "empresa publica" in norm:
        return Gestion.EMPRESA_PUBLICA, None, texto, ""
    resolucion = resolver_empresa(texto)
    return Gestion.INDIRECTA, resolucion.empresa, texto, resolucion.motivo


def _extracto(fila: dict) -> str:
    partes = [f"Operador según la tabla: {fila['operador_texto']}"]
    if fila["detalle"]:
        partes.append(f"Detalle: {fila['detalle']}")
    if fila["figura"]:
        partes.append(f"Figura: {fila['figura']}")
    if fila["fuente_texto"]:
        partes.append(f"Fuente indicada en la tabla: {fila['fuente_texto']}")
    if fila["anio_texto"]:
        partes.append(f"Año: {fila['anio_texto']}")
    if fila["nivel_original"]:
        partes.append(f"Nivel en la tabla: {fila['nivel_original']}")
    texto = "\n".join(partes)
    palabras = texto.split(" ")
    if len(texto.split()) > MAX_PALABRAS_EXTRACTO:
        texto = " ".join(palabras[:MAX_PALABRAS_EXTRACTO]) + " […]"
    return texto


def _abrir_revision(*, tipo, clave, texto, motivo, lote, objeto=None, datos=None, propuesta=None):
    elemento, creado = ElementoRevision.objects.get_or_create(
        clave=clave,
        defaults={
            "tipo": tipo,
            "texto": texto[:500],
            "motivo": motivo,
            "datos": datos or {},
            "propuesta": propuesta or {},
            "lote_importacion": lote,
            "objeto_tipo": ContentType.objects.get_for_model(objeto) if objeto else None,
            "objeto_id": objeto.pk if objeto else None,
        },
    )
    return elemento, creado


def aplicar_fila(fila: dict, municipio: Municipio, contexto: dict, usuario) -> str:
    """Crea la evidencia y la prestación de una fila ya resuelta. Devuelve "existente" o
    "nueva". `contexto` lleva fuente_id, estado, fecha_consulta, hoja y lote_id."""
    if Evidencia.objects.filter(clave_importacion=fila["clave"]).exists():
        return "existente"
    lote = LoteImportacion.objects.filter(pk=contexto.get("lote_id")).first()
    gestion, empresa, operador_texto, motivo_operador = _interpretar_operador(
        fila["operador_texto"]
    )
    url, referencias, ted_derivado = _referencias(fila["fuente_texto"])

    nivel, motivo_nivel = fila["nivel"], ""
    if nivel == DECIDIR:
        motivo_nivel = (
            f"La tabla dice «{fila['nivel_original'] or 'sin nivel'}». Hay que revisar la "
            "fuente y decidir el nivel (oficial, prensa, empresa o parcial)."
        )
    elif nivel == NivelEvidencia.OFICIAL and not url:
        motivo_nivel = (
            f"La tabla indica «{fila['nivel_original']}» pero no trae URL ni número de "
            "anuncio de TED. Añade la URL oficial o elige otro nivel."
        )
    if motivo_nivel:
        nivel = NivelEvidencia.PARCIAL  # provisional y en borrador hasta que se decida
    estado = EstadoValidacion.BORRADOR if motivo_nivel else contexto["estado"]
    validada = estado == EstadoValidacion.VALIDADA

    servicio_label = Servicio(fila["servicio"]).label
    datos_extra = {
        "fila": fila["n"],
        "hoja": contexto.get("hoja"),
        "municipio_texto": fila["municipio_texto"],
        "operador_texto": fila["operador_texto"],
        "nivel_original": fila["nivel_original"],
        "anio": _anio(fila["anio_texto"]),
        "referencias": referencias,
    }
    if ted_derivado:
        datos_extra["url_derivada_de"] = f"TED {ted_derivado}"
    if fila["columnas_extra"]:
        datos_extra["columnas_extra"] = fila["columnas_extra"]

    evidencia = Evidencia.objects.create(
        categoria=CategoriaEvidencia.SERVICIO_MUNICIPAL,
        titulo=(f"{servicio_label} en {municipio.nombre_oficial}: {fila['operador_texto']}")[:500],
        extracto=_extracto(fila),
        url_origen=url,
        fecha_consulta=date.fromisoformat(contexto["fecha_consulta"]),
        fuente_id=contexto["fuente_id"],
        servicio=fila["servicio"],
        alcance=fila["alcance"],
        nivel=nivel,
        estado_validacion=estado,
        origen=Origen.IMPORTADOR,
        lote_importacion=lote,
        tratamiento_limites=(
            f"Nivel provisional «parcial»: {motivo_nivel}" if motivo_nivel else ""
        ),
        datos_extra=datos_extra,
        clave_importacion=fila["clave"],
        creado_por=usuario,
        validado_por=usuario if validada else None,
        validado_en=timezone.now() if validada else None,
    )
    EvidenciaMunicipio.objects.create(evidencia=evidencia, municipio=municipio)
    if empresa:
        EvidenciaEmpresa.objects.create(evidencia=evidencia, empresa=empresa)

    filtro = {"municipio": municipio, "servicio": fila["servicio"], "alcance": fila["alcance"]}
    if empresa:
        filtro["empresa"] = empresa
    else:
        filtro.update(empresa=None, operador_normalizado=normalizar_texto(operador_texto))
    prestacion, creada = PrestacionServicio.objects.get_or_create(
        **filtro,
        defaults={"gestion": gestion, "operador_texto": operador_texto, "nivel": nivel},
    )
    prestacion.evidencias.add(evidencia)
    prestacion.recalcular()
    contexto.setdefault("_prestaciones_nuevas", 0)
    if creada:
        contexto["_prestaciones_nuevas"] += 1

    revisiones = contexto.setdefault("_revisiones", [])
    if gestion == Gestion.INDIRECTA and empresa is None:
        _, creado = _abrir_revision(
            tipo=ElementoRevision.Tipo.OPERADOR_NO_RESUELTO,
            clave=f"operador:{prestacion.pk}",
            texto=operador_texto,
            motivo=motivo_operador or "El operador no figura en el catálogo de empresas.",
            lote=lote,
            objeto=prestacion,
        )
        if creado:
            revisiones.append(ElementoRevision.Tipo.OPERADOR_NO_RESUELTO)
    if motivo_nivel:
        _abrir_revision(
            tipo=ElementoRevision.Tipo.NIVEL_POR_DECIDIR,
            clave=f"nivel:{fila['clave']}",
            texto=f"{evidencia.titulo} · {fila['nivel_original'] or 'sin nivel'}",
            motivo=motivo_nivel,
            lote=lote,
            objeto=evidencia,
            propuesta={"estado_al_validar": contexto["estado"]},
        )
        revisiones.append(ElementoRevision.Tipo.NIVEL_POR_DECIDIR)
    return "nueva"


class _Simulacion(Exception):
    pass


def validar_configuracion(config: dict, cabeceras: list[str]) -> list[str]:
    errores = []
    if config.get("columna_municipio") not in cabeceras:
        errores.append("Falta la columna de municipio.")
    if not config.get("fecha_consulta"):
        errores.append("Falta la fecha de consulta de la tabla.")
    if config.get("estado") not in (EstadoValidacion.VALIDADA, EstadoValidacion.BORRADOR):
        errores.append("El estado debe ser «validada» o «borrador».")
    if not (config.get("fuente") or {}).get("nombre"):
        errores.append("Falta el nombre de la fuente.")
    if not config.get("bloques"):
        errores.append("Define al menos un bloque de servicio.")
    for i, b in enumerate(config.get("bloques") or [], start=1):
        usadas = [
            b.get(k)
            for k in (
                "columna_operador",
                "columna_servicio",
                "columna_detalle",
                "columna_figura",
                "columna_fuente",
                "columna_anio",
                "columna_nivel",
            )
            if b.get(k)
        ] + list(b.get("columnas_extra") or [])
        for c in usadas:
            if c not in cabeceras:
                errores.append(f"Bloque {i}: la columna «{c}» no está en la tabla.")
        if not b.get("columna_operador"):
            errores.append(f"Bloque {i}: falta la columna de operador.")
        if not b.get("columna_servicio"):
            servicio = b.get("servicio")
            if servicio not in Servicio.values:
                errores.append(f"Bloque {i}: elige el servicio.")
            elif b.get("alcance") and b["alcance"] not in ALCANCES_POR_SERVICIO[servicio]:
                errores.append(f"Bloque {i}: el alcance no corresponde al servicio.")
    return errores


def importar_tabla(
    ruta: Path, config: dict, usuario, nombre_archivo: str = "", aplicar: bool = True
) -> Resultado:
    """Importa la tabla. Con `aplicar=False` lo simula todo y deshace los cambios (vista
    previa del asistente)."""
    ruta = Path(ruta)
    cabeceras, filas = leer_tabla(ruta, config.get("hoja"), int(config.get("fila_cabecera", 1)))
    errores_config = validar_configuracion(config, cabeceras)
    if errores_config:
        raise FormatoTablaError(" ".join(errores_config))
    sha256 = hashlib.sha256(ruta.read_bytes()).hexdigest()
    resultado = Resultado(filas_leidas=len(filas))
    try:
        with transaction.atomic():
            _importar(ruta, config, usuario, nombre_archivo, sha256, filas, resultado)
            if not aplicar:
                raise _Simulacion
    except _Simulacion:
        resultado.lote_id = None
        return resultado
    resultado.aplicado = True
    return resultado


def _importar(ruta, config, usuario, nombre_archivo, sha256, filas, resultado):
    fuente, _ = Fuente.objects.get_or_create(
        tipo=config["fuente"].get("tipo") or "documento_interno",
        nombre=config["fuente"]["nombre"],
    )
    lote = LoteImportacion.objects.create(
        tipo=TIPO_LOTE,
        parametros={"archivo": nombre_archivo or ruta.name, "configuracion": config},
        archivo_sha256=sha256,
        usuario=usuario,
        leidos=len(filas),
    )
    resultado.lote_id = lote.pk
    normalizadas, errores, sin_dato = normalizar_filas(filas, config, fuente.pk)
    resultado.errores.extend(errores)
    resultado.celdas_sin_dato = sin_dato
    contexto = {
        "fuente_id": fuente.pk,
        "estado": config["estado"],
        "fecha_consulta": config["fecha_consulta"],
        "hoja": config.get("hoja"),
        "lote_id": lote.pk,
    }
    for fila in normalizadas:
        if Evidencia.objects.filter(clave_importacion=fila["clave"]).exists():
            resultado.evidencias_existentes += 1
            continue
        provincias = [fila["provincia"]] if fila["provincia"] else None
        municipio = resolver_municipio_compuesto(fila["municipio_texto"], provincias)
        if municipio is None:
            previo = ElementoRevision.objects.filter(clave=f"municipio:{fila['clave']}").first()
            if previo and previo.estado == ElementoRevision.Estado.RECHAZADO:
                resultado.descartadas_en_revision += 1
                continue
            sugerencias = [m.codigo_ine for m in sugerencias_municipio(fila["municipio_texto"])]
            _, creado = _abrir_revision(
                tipo=ElementoRevision.Tipo.MUNICIPIO_NO_RESUELTO,
                clave=f"municipio:{fila['clave']}",
                texto=fila["municipio_texto"],
                motivo=(
                    "El nombre no coincide exactamente con ningún municipio del INE (o "
                    "coincide con varios)."
                ),
                lote=lote,
                datos={
                    "fila": fila,
                    "contexto": {k: v for k, v in contexto.items() if not k.startswith("_")},
                },
                propuesta={"sugerencias": sugerencias},
            )
            if creado:
                resultado.sumar_revision(ElementoRevision.Tipo.MUNICIPIO_NO_RESUELTO)
            else:
                resultado.ya_en_revision += 1
            continue
        estado = aplicar_fila(fila, municipio, contexto, usuario)
        if estado == "nueva":
            resultado.evidencias_nuevas += 1
        else:
            resultado.evidencias_existentes += 1
    for tipo in contexto.get("_revisiones", []):
        resultado.sumar_revision(tipo)
    resultado.prestaciones_nuevas = contexto.get("_prestaciones_nuevas", 0)

    lote.nuevos = resultado.evidencias_nuevas
    lote.descartados = resultado.celdas_sin_dato + resultado.descartadas_en_revision
    lote.errores = len(resultado.errores)
    lote.anotar(
        f"Filas leídas: {resultado.filas_leidas}. Evidencias nuevas: "
        f"{resultado.evidencias_nuevas}; ya existentes: {resultado.evidencias_existentes}. "
        f"Prestaciones nuevas: {resultado.prestaciones_nuevas}. Celdas «No localizado» sin "
        f"detalle ni fuente (no se guardan): {resultado.celdas_sin_dato}. A revisión: "
        f"{resultado.total_revision} {resultado.a_revision}; ya pendientes de una importación "
        f"anterior: {resultado.ya_en_revision}."
    )
    for e in resultado.errores:
        lote.anotar(e)
    lote.fin = timezone.now()
    lote.save()
    registrar_auditoria(
        usuario,
        "importacion.tabla_municipal",
        lote,
        despues={
            "archivo": nombre_archivo or ruta.name,
            "sha256": sha256,
            "evidencias_nuevas": resultado.evidencias_nuevas,
            "a_revision": resultado.a_revision,
        },
    )
