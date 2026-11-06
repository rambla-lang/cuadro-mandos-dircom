"""IA con cliente falso y respuestas grabadas (docs/06). CP-13 y CP-15."""

import json
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.documentos.models import Documento
from apps.ia import cliente, tareas
from apps.ia.models import LlamadaIA, PropuestaIA
from apps.medios.models import Mencion, MencionEmpresa
from apps.nucleo.models import ElementoRevision

MODELO = "claude-haiku-5-5"


class ClienteFalso:
    """Imita `client.messages.create` / `client.beta.messages.create` con respuestas grabadas."""

    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.peticiones = []
        self.messages = SimpleNamespace(create=self._crear)
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._crear))

    def _crear(self, **kw):
        self.peticiones.append(kw)
        r = self.respuestas.pop(0)
        texto = r if isinstance(r, str) else json.dumps(r)
        return SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text=texto)],
            usage=SimpleNamespace(
                input_tokens=1000,
                output_tokens=200,
                cache_read_input_tokens=0,
                cache_creation_input_tokens=0,
            ),
            _request_id="req_prueba",
        )


@pytest.fixture
def ia_activa(settings):
    settings.IA_ACTIVADA = True
    settings.ANTHROPIC_API_KEY = "clave-de-prueba"  # pragma: allowlist secret
    settings.IA_MODELO_CLASIFICAR = MODELO
    settings.IA_MODELO_EXTRAER = MODELO
    settings.IA_PRECIOS_JSON = {MODELO: {"entrada": 1.0, "salida": 5.0}}
    settings.IA_LIMITE_MENSUAL_EUR = 10
    settings.IA_FALLBACKS = True


@pytest.fixture
def mencion(competidores, municipios_cv):
    return Mencion.objects.create(
        origen="brandwatch",
        titulo="Cox Energía y Aqualia en Alcoi",
        extracto="La empresa Cox...",
        vinculo_territorial="dudoso",
    )


def falso(monkeypatch, respuestas):
    c = ClienteFalso(respuestas)
    monkeypatch.setattr(cliente, "obtener_cliente", lambda: c)
    return c


def test_t1_crea_propuesta_y_no_aplica_nada(ia_activa, mencion, monkeypatch, administrador):
    from apps.entidades.models import Empresa

    cox = Empresa.objects.get(nombre="Cox")
    c = falso(
        monkeypatch,
        [
            {
                "empresas": [
                    {"empresa_id": cox.pk, "fragmento": "Cox Energía", "confianza": "alta"}
                ],
                "vinculo_territorial": "si",
                "motivo": "Habla de Alcoi",
                "municipios": ["Alcoi"],
            }
        ],
    )
    propuesta = tareas.t1_atribuir_mencion(mencion, administrador)
    peticion = c.peticiones[0]
    assert peticion["model"] == MODELO and "fallbacks" not in peticion  # Haiku: sin fallbacks
    assert peticion["output_config"]["format"]["type"] == "json_schema"
    llamada = LlamadaIA.objects.get()
    assert llamada.estado == "ok" and llamada.coste_estimado == Decimal("0.00200")
    assert llamada.version_prompt == "comun_v1+t1_v1"
    assert not MencionEmpresa.objects.exists()  # la IA no confirma sola
    el = ElementoRevision.objects.get(tipo="propuesta_ia")
    # Al aceptarla, una persona la valida.
    tareas.aplicar(propuesta, administrador)
    me = MencionEmpresa.objects.get()
    assert me.empresa == cox and me.metodo == "ia" and me.validado_por == administrador
    mencion.refresh_from_db()
    assert mencion.vinculo_territorial == "si"
    assert el.objeto == propuesta


def test_salida_invalida_se_reintenta_y_falla(ia_activa, mencion, monkeypatch):
    falso(monkeypatch, ["no es json", "{}", "[1]"])
    with pytest.raises(cliente.ErrorIA):
        tareas.t1_atribuir_mencion(mencion)
    assert LlamadaIA.objects.filter(estado="error").count() == 3
    assert not PropuestaIA.objects.exists()


def test_cp15_limite_mensual_bloquea_sin_llamar(ia_activa, mencion, monkeypatch, settings):
    c = falso(monkeypatch, [])
    LlamadaIA.objects.create(tarea="T1", modelo=MODELO, estado="ok", coste_estimado=Decimal("10"))
    with pytest.raises(cliente.IANoDisponible, match="límite mensual"):
        tareas.t1_atribuir_mencion(mencion)
    assert c.peticiones == []
    assert LlamadaIA.objects.filter(estado="bloqueada").exists()


def test_sin_clave_o_sin_precio_no_se_llama(settings, mencion, monkeypatch, ia_activa):
    c = falso(monkeypatch, [])
    settings.IA_PRECIOS_JSON = {}
    with pytest.raises(cliente.IANoDisponible, match="precio"):
        tareas.t1_atribuir_mencion(mencion)
    settings.ANTHROPIC_API_KEY = ""
    assert cliente.estado()[0] is False and "clave" in cliente.estado()[1]
    assert c.peticiones == []


def test_cp13_recorte_sin_texto_queda_pendiente_sin_ia(base_ia_recorte, client, analista, settings):
    settings.ANTHROPIC_API_KEY = ""
    client.force_login(analista)
    r = client.get("/importar/recortes/")
    assert "pendientes hasta que se active" in r.content.decode()
    assert Documento.objects.get().lectura == "pendiente_ia"
    r = client.post("/ia/lanzar/", {"tarea": "T2"})
    assert r.status_code == 302
    from apps.nucleo.models import TrabajoIngesta

    assert not TrabajoIngesta.objects.exists()


def test_t2_lee_recorte_y_al_aceptar_completa_la_pieza(
    ia_activa, base_ia_recorte, monkeypatch, administrador
):
    from apps.entidades.models import Empresa

    doc = Documento.objects.get()
    go = Empresa.objects.get(nombre="Global Omnium")
    c = falso(
        monkeypatch,
        [
            {
                "texto": "Global Omnium invierte en Gandia. Texto literal del artículo.",
                "titular": "Global Omnium invierte en Gandia",
                "medio": "ABC",
                "fecha_publicacion": "2026-10-05",
                "pagina": 3,
                "resumen_breve": "Inversión en Gandia.",
                "empresas": [{"empresa_id": go.pk, "fragmento": "Global Omnium"}],
                "es_publicidad_identificada": False,
            }
        ],
    )
    settings_modelo_extraer = "claude-sonnet-5-5"
    from django.conf import settings

    settings.IA_MODELO_EXTRAER = settings_modelo_extraer
    settings.IA_PRECIOS_JSON = {
        **settings.IA_PRECIOS_JSON,
        settings_modelo_extraer: {"entrada": 2, "salida": 10},
    }
    propuesta = tareas.t2_leer_recorte(doc, administrador)
    bloque = c.peticiones[0]["messages"][0]["content"][0]
    assert bloque["type"] == "document" and bloque["source"]["media_type"] == "application/pdf"
    assert c.peticiones[0]["fallbacks"] == "default"  # Sonnet: reintento en otro modelo si rechaza
    tareas.aplicar(propuesta, administrador)
    doc.refresh_from_db()
    assert doc.lectura == "ia" and doc.texto_obtenido_por_ia
    m = doc.menciones.get()
    assert m.pieza.titulo == "Global Omnium invierte en Gandia"
    assert str(m.pieza.fecha_publicacion) == "2026-10-05" and m.pieza.medio.nombre == "ABC"
    assert m.vinculo_territorial == "si"
    assert MencionEmpresa.objects.get(mencion=m).empresa == go


def test_panel_ia(client, analista, lector, competidores):
    client.force_login(lector)
    assert client.get("/ia/").status_code == 403
    client.force_login(analista)
    r = client.get("/ia/")
    assert r.status_code == 200 and "No disponible" in r.content.decode()
