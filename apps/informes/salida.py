"""Generación del informe Word y la presentación PowerPoint (docs/05 §4)."""

import io
from datetime import date

from django.utils import timezone

from .redaccion import _m


def _fecha(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%d/%m/%Y") if iso else "—"


def generar_docx(informe) -> bytes:
    from docx import Document
    from docx.shared import Pt

    d = informe.datos
    doc = Document()
    estilo = doc.styles["Normal"]
    estilo.font.name = "Calibri"
    estilo.font.size = Pt(10.5)

    doc.add_heading(informe.titulo, 0)
    doc.add_paragraph(
        f"Periodo: {_fecha(d['desde'])} a {_fecha(d['hasta'])}. Ámbito: Comunitat Valenciana."
    )
    revision = (
        timezone.localtime(informe.publicado_en).date()
        if informe.publicado_en
        else timezone.localdate()
    )
    doc.add_paragraph(f"Fecha de revisión: {revision:%d/%m/%Y}.")
    base = (
        ", ".join(f"{k}: {v}" for k, v in sorted(d["base_documental"].items())) or "sin evidencias"
    )
    doc.add_paragraph(f"Base documental (evidencias validadas usadas, por categoría): {base}.")

    secciones = {s["clave"]: s for s in informe.secciones}

    def escribir(clave, nivel=1):
        s = secciones.get(clave)
        if not s:
            return
        doc.add_heading(s["titulo"], nivel)
        for linea in s["texto"].splitlines():
            if linea.strip():
                doc.add_paragraph(linea.strip())

    escribir("resumen")
    escribir("metodo")
    doc.add_heading("Análisis por competidor", 1)
    for c in d["competidores"]:
        escribir(f"competidor:{c['id']}", 2)
        if c["percepciones"]:
            p = doc.add_paragraph()
            p.add_run("Valoración interna, no verificada: ").bold = True
            p.add_run(" ".join(c["percepciones"])[:1500])
    doc.add_heading("Matriz comparativa", 1)
    t = doc.add_table(rows=1, cols=5)
    t.style = "Table Grid"
    for celda, texto in zip(
        t.rows[0].cells,
        ["Empresa", "Piezas", "Cuota de piezas", "Medios", "Adjudicaciones"],
        strict=True,
    ):
        celda.text = texto
    for c in d["competidores"]:
        met = c["metricas"]
        fila = t.add_row().cells
        fila[0].text = c["nombre"]
        fila[1].text = f"{_m(d, met['piezas'])} [{met['piezas']}]"
        fila[2].text = f"{_m(d, met['cuota'])} % [{met['cuota']}]"
        fila[3].text = f"{_m(d, met['medios'])} [{met['medios']}]"
        fila[4].text = f"{_m(d, met['adjudicaciones'])} [{met['adjudicaciones']}]"
    escribir("transversal")
    escribir("oportunidades")
    escribir("limites")

    doc.add_heading("Anexo: métricas", 1)
    t = doc.add_table(rows=1, cols=4)
    t.style = "Table Grid"
    for celda, texto in zip(
        t.rows[0].cells, ["ID", "Valor", "Definición", "Dónde ver las evidencias"], strict=True
    ):
        celda.text = texto
    for m in d["metricas"]:
        fila = t.add_row().cells
        fila[0].text, fila[1].text, fila[2].text, fila[3].text = (
            m["id"],
            m["texto"],
            m["definicion"],
            m["enlace"],
        )
    doc.add_heading("Anexo: evidencias", 1)
    t = doc.add_table(rows=1, cols=6)
    t.style = "Table Grid"
    for celda, texto in zip(
        t.rows[0].cells,
        ["ID", "Marca", "Fecha", "Fuente", "Tema y enlace", "Tratamiento / límites"],
        strict=True,
    ):
        celda.text = texto
    vistos = set()
    for c in d["competidores"]:
        for e in c["evidencias"]:
            if e["codigo"] in vistos:
                continue
            vistos.add(e["codigo"])
            fila = t.add_row().cells
            fila[0].text = e["codigo"]
            fila[1].text = ", ".join(e["empresas"])
            fila[2].text = _fecha(e["fecha"]) if e["fecha"] else "No consta"
            fila[3].text = f"{e['fuente']} ({e['nivel']})" + (
                f" · {e['validacion']}" if e.get("validacion") else ""
            )
            fila[4].text = f"{e['titulo']} {e['url']}".strip()
            fila[5].text = e["limites"]
    salida = io.BytesIO()
    doc.save(salida)
    return salida.getvalue()


def generar_pptx(informe) -> bytes:
    from pptx import Presentation
    from pptx.util import Pt

    d = informe.datos
    secciones = {s["clave"]: s for s in informe.secciones}
    prs = Presentation()

    def diapositiva(titulo, lineas, nota=""):
        s = prs.slides.add_slide(prs.slide_layouts[1])
        s.shapes.title.text = titulo
        cuerpo = s.placeholders[1].text_frame
        cuerpo.clear()
        for i, linea in enumerate([x for x in lineas if x.strip()][:9]):
            p = cuerpo.paragraphs[0] if i == 0 else cuerpo.add_paragraph()
            p.text = linea.strip()
            p.font.size = Pt(14)
        if nota:
            s.notes_slide.notes_text_frame.text = nota

    portada = prs.slides.add_slide(prs.slide_layouts[0])
    portada.shapes.title.text = informe.titulo
    portada.placeholders[
        1
    ].text = f"{_fecha(d['desde'])} a {_fecha(d['hasta'])} · Comunitat Valenciana"
    resumen = secciones.get("resumen", {}).get("texto", "").splitlines()
    diapositiva("Mensaje principal", resumen[:4])
    for c in d["competidores"]:
        bloque1 = secciones.get(f"competidor:{c['id']}", {}).get("texto", "").splitlines()
        diapositiva(
            f"{c['nombre']}: presencia y servicios",
            bloque1[:4],
            "Valoración interna, no verificada: " + " ".join(c["percepciones"])[:800]
            if c["percepciones"]
            else "",
        )
        diapositiva(
            f"{c['nombre']}: evidencias recientes",
            [f"{e['titulo']} ({e['fuente']}) [{e['codigo']}]" for e in c["evidencias"][:6]]
            or ["Sin evidencias validadas en el periodo."],
        )
        redes = [
            f"{r['red']}: {'no visible' if r['seguidores'] is None else r['seguidores']} seguidores ({_fecha(r['fecha']) if r['fecha'] else 'sin observación'})"
            for r in c["redes"]
        ]
        diapositiva(
            f"{c['nombre']}: presencia digital",
            redes or ["Actividad no caracterizable con la evidencia pública disponible."],
        )
    diapositiva("Recomendaciones", secciones.get("oportunidades", {}).get("texto", "").splitlines())
    diapositiva(
        "Método y evidencias",
        secciones.get("metodo", {}).get("texto", "").splitlines()[:3]
        + ["Detalle de métricas y evidencias en el anexo del informe Word."],
    )
    salida = io.BytesIO()
    prs.save(salida)
    return salida.getvalue()
