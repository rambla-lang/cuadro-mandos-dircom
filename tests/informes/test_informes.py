"""Informes (docs/05 §4). CP-09 y CP-10."""

import io
import json
from datetime import date

import docx
import pptx
import pytest

from apps.entidades.models import Empresa
from apps.evidencias.models import Evidencia, Fuente
from apps.informes import services
from apps.informes.models import InformeGenerado
from apps.informes.validador import validar_texto
from tests.ia.test_ia import ClienteFalso
from tests.medios.conftest import FILAS, csv_brandwatch

DESDE, HASTA = date(2026, 1, 1), date(2026, 12, 31)


@pytest.fixture
def base(competidores, municipios_cv, administrador, settings, tmp_path):
    from apps.medios.analisis import limpiar_caches
    from apps.medios.importers.brandwatch import importar_brandwatch

    settings.MEDIA_ROOT = tmp_path
    limpiar_caches()
    importar_brandwatch(csv_brandwatch(FILAS), "a.csv", administrador)
    facsa = Empresa.objects.get(nombre="FACSA")
    ev = Evidencia.objects.create(
        categoria="premio",
        titulo="Premio a la innovación 2026",
        fuente=Fuente.objects.create(tipo="prensa_digital", nombre="Medio"),
        nivel="prensa",
        estado_validacion="validada",
        validado_por=administrador,
        validado_en="2026-10-01T10:00Z",
        origen="manual",
        fecha_publicacion=date(2026, 10, 1),
        extracto="Concedido por la Cámara con 3 finalistas.",
    )
    ev.empresas.add(facsa)
    return administrador


def _informe(base, usar_ia=False):
    empresas = Empresa.objects.filter(nombre__in=["FACSA", "Aqualia"])
    return services.crear(empresas, DESDE, HASTA, base, usar_ia)


def test_borrador_con_plantilla_pasa_el_validador_y_se_publica(base):
    informe = _informe(base)
    assert informe.secciones_con_problemas == 0, [s["problemas"] for s in informe.secciones]
    facsa = next(s for s in informe.secciones if s["titulo"] == "FACSA")
    assert "[M" in facsa["texto"] and "[E-" in facsa["texto"]
    services.publicar(informe, base)
    informe.refresh_from_db()
    assert informe.estado == "publicado"
    from django.core.files.storage import default_storage

    d = docx.Document(default_storage.open(informe.archivo_docx))
    textos = "\n".join(p.text for p in d.paragraphs)
    assert "Resumen ejecutivo" in textos and "Valoración interna" not in textos  # sin percepciones
    anexos = [t for t in d.tables if t.rows[0].cells[0].text == "ID"]
    assert len(anexos) == 2  # métricas y evidencias
    p = pptx.Presentation(default_storage.open(informe.archivo_pptx))
    assert len(p.slides) == 2 + 3 * 2 + 2


def test_cp09_cifra_que_no_esta_en_las_metricas(base):
    informe = _informe(base)
    problemas = validar_texto("FACSA tiene 999 piezas [M1].", informe.datos)
    assert any("999" in p for p in problemas)
    # Las cifras de las evidencias sí valen (3 finalistas, año 2026).
    codigo = Evidencia.objects.get(categoria="premio").codigo
    assert validar_texto(f"Premio en 2026 con 3 finalistas [{codigo}].", informe.datos) == []
    services.guardar_texto(informe, "resumen", "Texto con 4242 piezas [M1].", base)
    informe.refresh_from_db()
    assert informe.secciones_con_problemas == 1
    with pytest.raises(Exception, match="validador"):
        services.publicar(informe, base)


def test_cp10_referencia_inexistente(base):
    informe = _informe(base)
    problemas = validar_texto("Afirmación [E-999999].", informe.datos)
    assert any("E-999999" in p for p in problemas)
    assert any("ninguna evidencia" in p for p in validar_texto("Sin referencias.", informe.datos))


def test_t6_con_ia_simulada(base, monkeypatch, settings):
    from apps.ia import cliente

    settings.IA_ACTIVADA, settings.ANTHROPIC_API_KEY = True, "x"  # pragma: allowlist secret
    settings.IA_MODELO_REDACTAR = "claude-opus-5-5"
    settings.IA_PRECIOS_JSON = {"claude-opus-5-5": {"entrada": 4, "salida": 20}}
    settings.IA_LIMITE_MENSUAL_EUR = 5
    codigo = Evidencia.objects.get(categoria="premio").codigo
    respuestas = [
        {"parrafos": [{"texto": "FACSA destaca por su premio.", "evidencias": [codigo]}]},
        {"parrafos": [{"texto": "Patrón común inventado con 77 casos.", "evidencias": []}]},
        {"parrafos": [{"texto": "Reforzar la presencia local.", "evidencias": ["E-999999"]}]},
    ]
    falso = ClienteFalso(respuestas)
    monkeypatch.setattr(cliente, "obtener_cliente", lambda: falso)
    informe = _informe(base, usar_ia=True)
    estado = {s["clave"]: (s["origen"], bool(s["problemas"])) for s in informe.secciones}
    assert estado["resumen"] == ("ia", False)
    assert estado["transversal"] == ("ia", True)  # CP-09: 77 y sin referencias
    assert estado["oportunidades"] == ("ia", True)  # CP-10: E-999999
    assert informe.llamadas_ia.count() == 3
    material = json.loads(falso.peticiones[0]["messages"][0]["content"][0]["text"])
    assert {"metricas", "evidencias", "periodo"} <= set(material)


def test_vistas_y_permisos(base, client, lector, analista):
    client.force_login(analista)
    facsa = Empresa.objects.get(nombre="FACSA")
    r = client.post(
        "/informes/nuevo/", {"desde": "2026-01-01", "hasta": "2026-12-31", "empresas": [facsa.pk]}
    )
    informe = InformeGenerado.objects.get()
    assert r.url == f"/informes/{informe.pk}/"
    assert client.get(r.url).status_code == 200
    client.force_login(lector)
    assert client.get(f"/informes/{informe.pk}/").status_code == 404  # borrador oculto al lector
    assert client.get("/informes/nuevo/").status_code == 403
    services.publicar(informe, base)
    assert client.get(f"/informes/{informe.pk}/").status_code == 200
    r = client.get(f"/informes/{informe.pk}/descargar.docx")
    assert r.status_code == 200
    docx.Document(io.BytesIO(b"".join(r.streaming_content)))
