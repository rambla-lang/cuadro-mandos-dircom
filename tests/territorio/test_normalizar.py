import pytest

from apps.nucleo.texto import normalizar_texto
from apps.territorio.services import variantes_nombre_ine


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("L'Eliana", "l'eliana"),
        ("l’Eliana", "l'eliana"),
        ("l' Eliana", "l'eliana"),
        ("  ALACANT  ", "alacant"),
        ("Benicàssim", "benicassim"),
        ("Paterna", "paterna"),
        ("Vila-real", "vila real"),
        ("Castelló de la Plana", "castello de la plana"),
        ("Ontinyent", "ontinyent"),
        ("Alcalà de Xivert", "alcala de xivert"),
        ("Col·legi", "collegi"),
        ("", ""),
    ],
)
def test_normalizar_texto(entrada, esperado):
    assert normalizar_texto(entrada) == esperado


@pytest.mark.parametrize(
    ("nombre", "completas", "sin_articulo"),
    [
        ("Agost", ["Agost"], []),
        ("Eliana, l'", ["Eliana, l'", "l'Eliana"], ["Eliana"]),
        ("Elx/Elche", ["Elx", "Elche"], []),
        ("Orxa, l'/Lorcha", ["Orxa, l'", "l'Orxa", "Lorcha"], ["Orxa"]),
        ("Montesinos, Los", ["Montesinos, Los", "Los Montesinos"], ["Montesinos"]),
        (
            "Camp de Mirra, el/Campo de Mirra",
            ["Camp de Mirra, el", "el Camp de Mirra", "Campo de Mirra"],
            ["Camp de Mirra"],
        ),
        ("Useres, les/Useras", ["Useres, les", "les Useres", "Useras"], ["Useres"]),
    ],
)
def test_variantes_nombre_ine(nombre, completas, sin_articulo):
    assert variantes_nombre_ine(nombre) == (completas, sin_articulo)
