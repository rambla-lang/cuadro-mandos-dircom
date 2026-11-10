"""Fase 6: Word (docs/04 §6), digital (CP-12), evidencias y ficha de empresa gestora (docs/05 §2).
Los .docx se generan en el test con datos sintéticos."""

import io
from datetime import date

import docx
import pytest
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from apps.digital.models import ObservacionDigital, PerfilDigital
from apps.digital.services import importar_csv
from apps.documentos import word
from apps.documentos.models import PercepcionInterna
from apps.entidades.models import Empresa
from apps.evidencias.models import Evidencia
from apps.medios.models import MencionEmpresa


def _bytes(d) -> bytes:
    salida = io.BytesIO()
    d.save(salida)
    return salida.getvalue()


def _hipervinculo(parrafo, url, texto):
    r_id = parrafo.part.relate_to(url, RT.HYPERLINK, is_external=True)
    h = OxmlElement("w:hyperlink")
    h.set(qn("r:id"), r_id)
    run = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.text = texto
    run.append(t)
    h.append(run)
    parrafo._p.append(h)


@pytest.fixture
def base(empresas_gestoras, municipios_cv, administrador):
    return administrador


def test_percepciones_por_empresa(base):
    d = docx.Document()
    for t in [
        "PERCEPCIONES SINTÉTICAS",
        "Introducción sin empresa",
        "NEALIS /FACSA",
        "Texto uno de FACSA.",
        "Texto dos de FACSA.",
        "OTRA EMPRESA SL",
        "Esto no se atribuye.",
        "AQUALIA",
        "Texto de Aqualia.",
    ]:
        d.add_paragraph(t)
    r = word.importar_percepciones(_bytes(d), "p.docx", base)
    assert r.percepciones == 2
    textos = {p.empresa.nombre: p.texto for p in PercepcionInterna.objects.all()}
    assert textos == {
        "FACSA": "Texto uno de FACSA.\nTexto dos de FACSA.",
        "Aqualia": "Texto de Aqualia.",
    }
    assert not Evidencia.objects.exists()  # una percepción nunca es una evidencia
    assert not word.importar_percepciones(_bytes(d), "p.docx", base).nuevo


def test_publicaciones(base):
    d = docx.Document()
    for t in [
        "Publicaciones:",
        "FACSA (NEALIS):",
        "https://medio-a.es/nota-1",
        "COX",
        "https://medio-b.es/cox?utm_source=x",
        "IDRICA",
        "https://medio-c.es/otra",
    ]:
        d.add_paragraph(t)
    r = word.importar_publicaciones(_bytes(d), "pub.docx", base)
    assert r.urls == 3 and r.menciones_nuevas == 2 and r.sin_empresa == 1
    assert r.cabeceras_sin_empresa == ["IDRICA"]
    pares = set(MencionEmpresa.objects.values_list("empresa__nombre", "estado_validacion"))
    assert pares == {("FACSA", "validada"), ("Cox", "validada")}  # en cabecera, Cox tiene contexto


def test_anexo_documento_maestro(base):
    d = docx.Document()
    t = d.add_table(rows=1, cols=6)
    for c, h in zip(t.rows[0].cells, word.CABECERA_ANEXO, strict=True):
        c.text = h
    filas = [
        ("P001", "FACSA", "15/06/2026", "Medio Sintético", "Tema P", "Información municipal"),
        ("S001", "Cox", "Fecha relativa", "Cox", "Post", "Sin día validado"),
        (
            "D001",
            "Urbaser / PreZero",
            "02/02/2026",
            "Ayuntamiento Sintético",
            "Contrato",
            "Corroboración",
        ),
    ]
    for f in filas:
        celdas = t.add_row().cells
        for i, v in enumerate(f):
            if i == 4:
                _hipervinculo(celdas[4].paragraphs[0], f"https://ejemplo.es/{f[0]}", v)
            else:
                celdas[i].text = v
    r = word.importar_anexo_maestro(_bytes(d), "maestro.docx", base)
    assert r.nuevas == 3 and r.sin_empresa == []
    p1 = Evidencia.objects.get(clave_importacion="maestro:P001")
    assert p1.estado_validacion == "borrador" and p1.nivel == "prensa"
    assert p1.url_origen == "https://ejemplo.es/P001" and p1.fecha_publicacion == date(2026, 6, 15)
    s1 = Evidencia.objects.get(clave_importacion="maestro:S001")
    assert s1.nivel == "empresa" and s1.fecha_publicacion is None
    assert s1.datos_extra["fecha_texto"] == "Fecha relativa"
    d1 = Evidencia.objects.get(clave_importacion="maestro:D001")
    assert d1.nivel == "oficial"
    assert set(d1.empresas.values_list("nombre", flat=True)) == {"Urbaser", "PreZero"}
    assert word.importar_anexo_maestro(_bytes(d), "maestro.docx", base).existentes == 3


def test_cp12_seguidores_no_visibles(base, client, lector):
    facsa = Empresa.objects.get(nombre="FACSA")
    csv = (
        b"perfil_url,red,fecha_observacion,seguidores,publicaciones_observadas,periodo_observado,"
        b"historico_suficiente,notas,empresa\n"
        b"https://www.linkedin.com/company/sintetica,linkedin,2026-10-01,no visible,12,"
        b"octubre,no,,FACSA\n"
        b"https://www.linkedin.com/company/sintetica,linkedin,2026-11-01,1.250,,noviembre,si,,\n"
        b"https://x.com/otra,x,2026-11-01,diez,,,,,\n"
    )
    r = importar_csv(csv, base)
    assert r.nuevas == 2 and len(r.errores) == 1
    primera = ObservacionDigital.objects.get(fecha_observacion=date(2026, 10, 1))
    assert primera.seguidores is None and primera.publicaciones_observadas == 12
    assert ObservacionDigital.objects.get(fecha_observacion=date(2026, 11, 1)).seguidores == 1250
    assert PerfilDigital.objects.get().empresa == facsa
    client.force_login(lector)
    ObservacionDigital.objects.filter(fecha_observacion=date(2026, 11, 1)).delete()
    html = client.get(f"/empresas-gestoras/{facsa.pk}/").content.decode()
    assert "no visible" in html


def test_ficha_empresa_gestora(base, client, lector):
    import tempfile
    from pathlib import Path

    from apps.evidencias.importers.tabla_municipal import importar_tabla
    from tests.evidencias.test_tabla_municipal import _libro

    tmp = Path(tempfile.mkdtemp())
    ruta = _libro(tmp, [["AGOST", "Urbaser"], ["IBI", "Urbaser"]], ["MUNICIPIO", "RESIDUOS"])
    config = {
        "hoja": "Municipios",
        "columna_municipio": "MUNICIPIO",
        "fecha_consulta": "2026-11-01",
        "fuente": {"tipo": "documento_interno", "nombre": "Sintética"},
        "estado": "validada",
        "bloques": [
            {
                "servicio": "residuos",
                "alcance": "",
                "columna_operador": "RESIDUOS",
                "nivel_por_defecto": "empresa",
            }
        ],
    }
    importar_tabla(ruta, config, base)
    urbaser = Empresa.objects.get(nombre="Urbaser")
    client.force_login(lector)
    html = client.get(f"/empresas-gestoras/{urbaser.pk}/").content.decode()
    assert "Residuos</strong>: 2 municipios" in html
    assert "Contratación" not in html  # retirada (ADR-010)
    assert "Actividad no caracterizable" in html
    lista = client.get("/empresas-gestoras/").content.decode()
    assert "Empresas gestoras" in lista and "Veolia" in lista


def test_evidencia_manual_validar_y_auditar(base, client, analista, lector):
    client.force_login(analista)
    facsa = Empresa.objects.get(nombre="FACSA")
    datos = {
        "categoria": "premio",
        "titulo": "Premio sintético",
        "extracto": "",
        "url_origen": "https://ejemplo.es/p",
        "nivel": "prensa",
        "fuente_nombre": "Medio",
        "fuente_tipo": "prensa_digital",
        "empresas_sel": [facsa.pk],
        "servicio": "",
        "alcance": "",
    }
    r = client.post("/evidencias/nueva/", datos)
    assert r.status_code == 302
    ev = Evidencia.objects.get(titulo="Premio sintético")
    assert ev.estado_validacion == "borrador" and ev.origen == "manual"
    client.post(f"/evidencias/{ev.pk}/validar/")
    ev.refresh_from_db()
    assert ev.estado_validacion == "validada" and ev.validado_por == analista
    datos["titulo"] = "Premio sintético corregido"
    client.post(f"/evidencias/{ev.pk}/editar/", datos)
    from apps.nucleo.models import RegistroAuditoria

    assert RegistroAuditoria.objects.filter(accion="evidencia.editar_validada").exists()
    html = client.get(f"/empresas-gestoras/{facsa.pk}/").content.decode()
    assert "Premio sintético corregido" in html
    client.force_login(lector)
    assert client.get(f"/evidencias/{ev.pk}/").status_code == 200
    assert client.post(f"/evidencias/{ev.pk}/validar/").status_code == 403
    assert client.get("/evidencias/nueva/").status_code == 403
