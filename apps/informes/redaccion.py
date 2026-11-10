"""Secciones de texto del informe. Sin IA, un texto en código que solo usa las métricas y
evidencias calculadas; con IA (T6), la redacción de las secciones narrativas. En los dos casos
el validador decide si la sección puede publicarse."""

import json

from apps.ia.cliente import ErrorIA, IANoDisponible, llamar
from apps.ia.esquemas import ESQUEMA_T6, SalidaT6

from .validador import numeros_permitidos, validar_texto

METODO = (
    "Unidad de recuento en medios: la pieza (una URL periodística canónica o un recorte). Dos "
    "medios sobre el mismo acto son dos piezas y un hito. Las piezas compartidas cuentan para cada "
    "empresa, por lo que la suma por empresa puede superar el total.\n"
    "Niveles de evidencia: confirmado por fuente oficial, por prensa o por la empresa; parcial; y no "
    "localizado, que no equivale a «no existe».\n"
    "Las percepciones internas se presentan aparte como valoración interna y no son evidencias.\n"
    "Los textos redactados con IA se basan solo en las métricas calculadas y en evidencias "
    "validadas, y han pasado el validador de cifras y referencias antes de publicarse."
)
LIMITES = (
    "Los recuentos de municipios reflejan municipios con alguna evidencia validada; el alcance real "
    "puede ser distinto.\n"
    "La fecha de las menciones de Brandwatch se interpreta en UTC hasta verificarlo.\n"
    "No se estiman audiencias ni valor publicitario.\n"
    "Siguiente nivel de precisión: revisar las evidencias en borrador, completar la bandeja de "
    "revisión y ampliar la carga histórica de contratación."
)


def _seccion(clave, titulo, texto, datos, origen="codigo", validar=True):
    return {
        "clave": clave,
        "titulo": titulo,
        "texto": texto,
        "origen": origen,
        "validar": validar,
        "problemas": validar_texto(texto, datos) if validar else [],
    }


def _m(datos, ident):
    return next(m for m in datos["metricas"] if m["id"] == ident)["texto"]


def texto_empresa(c: dict, datos: dict) -> str:
    met = c["metricas"]
    lineas = [
        f"{c['nombre']} suma {_m(datos, met['piezas'])} piezas en el periodo [{met['piezas']}], una cuota "
        f"de piezas del {_m(datos, met['cuota'])} % [{met['cuota']}], en {_m(datos, met['medios'])} medios "
        f"distintos [{met['medios']}]."
    ]
    if c["municipios"]:
        partes = [
            f"{s.lower()} en {_m(datos, i)} municipios [{i}]" for s, i in c["municipios"].items()
        ]
        lineas.append(f"Con evidencia validada presta {', '.join(partes)}.")
    else:
        ident = met["municipios_total"]
        lineas.append(
            f"No tiene prestaciones municipales validadas en el cuadro (no localizado) [{ident}]."
        )
    for e in c["evidencias"][:5]:
        lineas.append(f"{e['titulo']} ({e['fuente']}) [{e['codigo']}].")
    return "\n".join(lineas)


def secciones_codigo(datos: dict) -> list[dict]:
    total = datos["total_piezas"]
    resumen = [
        f"En el periodo analizado hay {_m(datos, total)} piezas con vínculo con la Comunitat Valenciana "
        f"y atribución validada [{total}]."
    ]
    for c in sorted(
        datos["empresas"],
        key=lambda x: -float(_m(datos, x["metricas"]["piezas"]).replace(",", ".")),
    ):
        met = c["metricas"]
        resumen.append(f"{c['nombre']}: {_m(datos, met['piezas'])} piezas [{met['piezas']}].")
    secciones = [
        _seccion("resumen", "Resumen ejecutivo", "\n".join(resumen), datos),
        _seccion("metodo", "Alcance, fuentes y método", METODO, datos, validar=False),
    ]
    for c in datos["empresas"]:
        secciones.append(
            _seccion(f"empresa:{c['id']}", c["nombre"], texto_empresa(c, datos), datos)
        )
    secciones += [
        _seccion("transversal", "Lectura transversal", "\n".join(resumen[1:]) or resumen[0], datos),
        _seccion(
            "oportunidades",
            "Oportunidades",
            "Sección por redactar por el equipo de comunicación a partir de las fichas ["
            + total
            + "].",
            datos,
        ),
        _seccion(
            "limites", "Límites y siguiente nivel de precisión", LIMITES, datos, validar=False
        ),
    ]
    return secciones


SECCIONES_IA = {
    "resumen": "Resumen ejecutivo: cinco o seis frases con lo esencial para la dirección.",
    "transversal": "Lectura transversal: patrones comunes y diferencias entre las empresas gestoras.",
    "oportunidades": "Oportunidades: qué sugiere el análisis para la comunicación propia, sin cifras nuevas.",
}


def redactar_con_ia(datos: dict, secciones: list[dict], usuario) -> tuple[list[dict], list]:
    """Sustituye las secciones narrativas por la redacción de la IA (T6). Si la IA no está
    disponible o falla, se conserva el texto en código y se anota el motivo."""
    llamadas = []
    material = {
        "periodo": [datos["desde"], datos["hasta"]],
        "metricas": [{k: m[k] for k in ("id", "texto", "definicion")} for m in datos["metricas"]],
        "evidencias": [
            {k: e[k] for k in ("codigo", "fecha", "fuente", "titulo", "extracto", "empresas")}
            for c in datos["empresas"]
            for e in c["evidencias"]
        ],
    }
    permitidos = numeros_permitidos(datos)
    for s in secciones:
        if s["clave"] not in SECCIONES_IA:
            continue
        try:
            r = llamar(
                tarea="T6",
                tipo_modelo="redactar",
                prompt_tarea="t6_v1",
                contenido=[
                    {
                        "type": "text",
                        "text": json.dumps(material, ensure_ascii=False),
                        "cache_control": {"type": "ephemeral"},
                    },
                    {"type": "text", "text": f"Sección: {SECCIONES_IA[s['clave']]}"},
                ],
                esquema=ESQUEMA_T6,
                validador=SalidaT6,
                usuario=usuario,
                max_tokens=4000,
                esfuerzo="high",
            )
        except (IANoDisponible, ErrorIA) as e:
            s["nota"] = f"Texto en código: la IA no ha redactado esta sección ({e})."
            continue
        llamadas.append(r.llamada)
        texto = "\n".join(
            p.texto + "".join(f" [{c}]" for c in p.evidencias if f"[{c}]" not in p.texto)
            for p in r.datos.parrafos
        )
        s.update(texto=texto, origen="ia", problemas=validar_texto(texto, datos, permitidos))
    return secciones, llamadas
