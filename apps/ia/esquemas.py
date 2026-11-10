"""Esquemas JSON de salida por tarea (docs/06) y su validación con Pydantic.

El esquema se envía a la API como salida estructurada (`output_config.format`) y la respuesta
se vuelve a validar aquí: si no valida, la llamada es un error.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def _objeto(propiedades: dict) -> dict:
    return {
        "type": "object",
        "properties": propiedades,
        "required": list(propiedades),
        "additionalProperties": False,
    }


NULO_TEXTO = {"type": ["string", "null"]}

# --- T1 -------------------------------------------------------------------------------------
ESQUEMA_T1 = _objeto(
    {
        "empresas": {
            "type": "array",
            "items": _objeto(
                {
                    "empresa_id": {"type": "integer"},
                    "fragmento": {"type": "string"},
                    "confianza": {"type": "string", "enum": ["alta", "media", "baja"]},
                }
            ),
        },
        "vinculo_territorial": {"type": "string", "enum": ["si", "no", "dudoso"]},
        "motivo": {"type": "string"},
        "municipios": {"type": "array", "items": {"type": "string"}},
    }
)


class _Estricto(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmpresaT1(_Estricto):
    empresa_id: int
    fragmento: str
    confianza: Literal["alta", "media", "baja"]


class SalidaT1(_Estricto):
    empresas: list[EmpresaT1]
    vinculo_territorial: Literal["si", "no", "dudoso"]
    motivo: str
    municipios: list[str]


# --- T2 -------------------------------------------------------------------------------------
ESQUEMA_T2 = _objeto(
    {
        "texto": {"type": "string"},
        "titular": NULO_TEXTO,
        "medio": NULO_TEXTO,
        "fecha_publicacion": NULO_TEXTO,
        "pagina": {"type": ["integer", "null"]},
        "resumen_breve": {"type": "string"},
        "empresas": {
            "type": "array",
            "items": _objeto({"empresa_id": {"type": "integer"}, "fragmento": {"type": "string"}}),
        },
        "es_publicidad_identificada": {"type": "boolean"},
    }
)


class EmpresaT2(_Estricto):
    empresa_id: int
    fragmento: str


class SalidaT2(_Estricto):
    texto: str
    titular: str | None
    medio: str | None
    fecha_publicacion: str | None = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    pagina: int | None
    resumen_breve: str
    empresas: list[EmpresaT2]
    es_publicidad_identificada: bool


# --- T4 -------------------------------------------------------------------------------------
ESQUEMA_T4 = _objeto(
    {
        "fragmentos": {
            "type": "array",
            "items": _objeto(
                {"empresa_id": {"type": ["integer", "null"]}, "texto": {"type": "string"}}
            ),
        }
    }
)


class FragmentoT4(_Estricto):
    empresa_id: int | None
    texto: str


class SalidaT4(_Estricto):
    fragmentos: list[FragmentoT4]


# --- T6 -------------------------------------------------------------------------------------
ESQUEMA_T6 = _objeto(
    {
        "parrafos": {
            "type": "array",
            "items": _objeto(
                {
                    "texto": {"type": "string"},
                    "evidencias": {"type": "array", "items": {"type": "string"}},
                }
            ),
        }
    }
)


class ParrafoT6(_Estricto):
    texto: str
    evidencias: list[str]


class SalidaT6(_Estricto):
    parrafos: list[ParrafoT6]
