import pytest

from apps.entidades.services import resolver_empresa


@pytest.mark.parametrize(
    ("texto", "esperada"),
    [
        ("VEOLIA", "Veolia"),
        ("AGUAS DE ALICANTE (VEOLIA)", "Veolia"),
        ("Urbaser (limpieza viaria)", "Urbaser"),
        ("FCC (prórroga)", "FCC"),
        ("STV Gestión", "STV"),
        ("Nealis / FACSA", "FACSA"),
        ("UTE Urbaser + FCC Medio Ambiente", None),
        ("SAV (recogida) / FCC Medio Ambiente (limpieza)", None),
        ("ACCIONA", None),  # alias que requiere contexto
        ("ACCIONA (Acciona Servicios Urbanos)", None),
        ("Fobesa (Fomento Benicasim, S.A.)", None),
        ("Iberdrola Clientes (2024)", None),
        ("", None),
    ],
)
def test_resolver_empresa(competidores, texto, esperada):
    r = resolver_empresa(texto)
    assert (r.empresa.nombre if r.empresa else None) == esperada
    if esperada is None:
        assert r.motivo


def test_motivo_de_alias_ambiguo(competidores):
    assert "ambiguo" in resolver_empresa("ACCIONA").motivo
    assert "varios operadores" in resolver_empresa("UTE Netial (FCC + PreZero)").motivo
