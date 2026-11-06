"""Recortes PDF (docs/04 §5). CP-13. PDF generados en el test (sin recortes reales)."""

import pytest

from apps.documentos.models import Documento
from apps.medios.clipping import metadatos_de_nombre, subir_recorte
from apps.medios.models import MencionEmpresa, Pieza


def pdf(texto: str | None) -> bytes:
    """PDF mínimo de una página, con o sin texto."""
    contenido = b"BT /F1 11 Tf 40 760 Td (" + texto.encode("latin-1") + b") Tj ET" if texto else b""
    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length "
        + str(len(contenido)).encode()
        + b" >>\nstream\n"
        + contenido
        + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    salida = bytearray(b"%PDF-1.4\n")
    posiciones = []
    for i, o in enumerate(objetos, start=1):
        posiciones.append(len(salida))
        salida += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(salida)
    salida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    for p in posiciones:
        salida += f"{p:010d} 00000 n \n".encode()
    salida += (
        f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    )
    return bytes(salida)


@pytest.mark.parametrize(
    ("nombre", "esperado"),
    [
        ("LEVANTE-GENERAL-01_10_2026-7.pdf", ("LEVANTE", "GENERAL", "2026-10-01", 7)),
        ("El Mundo-Castellon-17_10_2026-27.pdf", ("El Mundo", "Castellon", "2026-10-17", 27)),
        ("El Mundo-Castellon-06_10_2026-40 (1).pdf", ("El Mundo", "Castellon", "2026-10-06", 40)),
        ("INFORMACION-ALICANTE-23_09_2026-19.pdf", ("INFORMACION", "ALICANTE", "2026-09-23", 19)),
        (
            "MEDITERRANEO-Mediterraneo-23_10_2026-8.pdf",
            ("MEDITERRANEO", "Mediterraneo", "2026-10-23", 8),
        ),
        ("VegaBaja-VegaBaja-18_10_2026-20.pdf", ("VegaBaja", "VegaBaja", "2026-10-18", 20)),
    ],
)
def test_nombres_reales_de_recortes(nombre, esperado):
    m = metadatos_de_nombre(nombre)
    assert (m["medio"], m["edicion"], m["fecha"], m["pagina"]) == esperado


@pytest.mark.parametrize("nombre", ["Las Provincias3.pdf", "ABC.pdf", "La Razón (Levante) (1).pdf"])
def test_nombres_sin_patron(nombre):
    assert metadatos_de_nombre(nombre) == {}


def test_recorte_con_texto(base_medios, settings, tmp_path):
    from apps.entidades.models import Empresa

    settings.MEDIA_ROOT = tmp_path
    texto = "Global Omnium presenta en Gandia su plan de agua. " * 6
    aqualia = Empresa.objects.get(nombre="Aqualia")
    r = subir_recorte(pdf(texto), "LEVANTE-GENERAL-01_10_2026-7.pdf", base_medios, aqualia)
    assert r.nuevo and not r.pendiente_ia
    doc = r.documento
    assert doc.lectura == Documento.Lectura.TEXTO and "Global Omnium" in doc.texto_extraido
    pieza = Pieza.objects.get()
    assert pieza.tipo == Pieza.Tipo.PRENSA_IMPRESA and pieza.medio.nombre == "LEVANTE"
    assert str(pieza.fecha_publicacion) == "2026-10-01"
    empresas = set(MencionEmpresa.objects.values_list("empresa__nombre", "metodo"))
    assert empresas == {("Aqualia", "manual"), ("Global Omnium", "alias")}
    # Mismo archivo otra vez: no se duplica (clave SHA-256).
    assert not subir_recorte(pdf(texto), "otro.pdf", base_medios).nuevo
    assert Documento.objects.count() == 1


def test_cp13_pdf_sin_capa_de_texto(base_medios, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    r = subir_recorte(pdf(None), "ABC.pdf", base_medios)
    assert r.pendiente_ia
    assert r.documento.lectura == Documento.Lectura.PENDIENTE_IA
    assert r.documento.metadatos == {}
    assert not MencionEmpresa.objects.exists()
