from io import StringIO

import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from apps.entidades.models import AcotacionEmpresa, AliasEmpresa, Empresa, GrupoEmpresarial
from apps.entidades.services import cargar_empresas_gestoras
from apps.evidencias.models import Evidencia, Fuente
from tests.conftest import SEED

FICHERO = SEED / "empresas_gestoras_iniciales.json"
NIF_SINTETICO = "A12345678"  # pragma: allowlist secret
CON_FICHA = {
    "FACSA",
    "Aqualia",
    "Hozono Global",
    "Global Omnium",
    "Cox",
    "STV",
    "Urbaser",
    "PreZero",
    "Valoriza",
    "FCC",
    "ENGIE",
    "ACCIONA Energía",
    "Naturgy",
    "Veolia",
    "Hidraqua",
}


@pytest.fixture
def cargados(db):
    return cargar_empresas_gestoras(FICHERO)


def test_carga_las_15_empresas_gestoras_con_veolia_como_una_mas(cargados):
    assert set(Empresa.objects.filter(con_ficha=True).values_list("nombre", flat=True)) == CON_FICHA
    veolia = GrupoEmpresarial.objects.get(nombre="Veolia")
    assert set(veolia.empresas.values_list("nombre", flat=True)) == {"Veolia", "Hidraqua"}
    assert cargados.empresas_nuevas == 15


def test_grupo_nealis_y_alias(cargados):
    """RF-10: Nealis y FACSA pertenecen al mismo grupo."""
    facsa = Empresa.objects.get(nombre="FACSA")
    assert facsa.grupo == GrupoEmpresarial.objects.get(nombre="Nealis")
    assert set(facsa.alias.values_list("texto", flat=True)) == {"FACSA", "Nealis"}
    assert AliasEmpresa.objects.get(empresa__nombre="Cox", texto="Cox").requiere_contexto


def test_acotaciones(cargados):
    """RF-11 con las acotaciones del documento maestro."""
    acciona = AcotacionEmpresa.objects.get(empresa__nombre="ACCIONA Energía")
    assert acciona.servicios_incluidos == ["energia"]
    fcc = AcotacionEmpresa.objects.get(empresa__nombre="FCC")
    assert fcc.servicios_incluidos == ["residuos", "energia"]
    stv = AcotacionEmpresa.objects.get(empresa__nombre="STV")
    assert stv.ambito_geografico == "Elche" and "jardines" in stv.nota
    assert AcotacionEmpresa.objects.filter(empresa__nombre="Aqualia").exists()
    assert all(a.fuente for a in AcotacionEmpresa.objects.all())


def test_sin_nif_inventados(cargados):
    assert not Empresa.objects.exclude(nif=None).exists()


def test_idempotente_y_no_pisa_ediciones(cargados):
    facsa = Empresa.objects.get(nombre="FACSA")
    facsa.notas = "Editado a mano"
    facsa.save()
    acot = AcotacionEmpresa.objects.get(empresa__nombre="ACCIONA Energía")
    acot.nota = "Nota editada"
    acot.save()

    r = cargar_empresas_gestoras(FICHERO)

    assert (r.empresas_nuevas, r.alias_nuevos, r.acotaciones_nuevas) == (0, 0, 0)
    assert Empresa.objects.count() == 15
    assert Empresa.objects.get(nombre="FACSA").notas == "Editado a mano"
    assert AcotacionEmpresa.objects.get(empresa__nombre="ACCIONA Energía").nota == "Nota editada"


def test_comando(db):
    salida = StringIO()
    call_command("cargar_empresas_gestoras", stdout=salida)
    assert "Empresas nuevas 15" in salida.getvalue()


def test_nif_vacio_no_choca_y_se_normaliza(db):
    Empresa.objects.create(nombre="A", nif="")
    Empresa.objects.create(nombre="B", nif="  ")
    c = Empresa.objects.create(nombre="C", nif=f" {NIF_SINTETICO.lower()} ")
    assert c.nif == NIF_SINTETICO
    with pytest.raises(IntegrityError), transaction.atomic():
        Empresa.objects.create(nombre="D", nif=NIF_SINTETICO)


def test_alias_duplicado_normalizado(db):
    e = Empresa.objects.create(nombre="Global Omnium")
    AliasEmpresa.objects.create(empresa=e, texto="Global Omnium")
    with pytest.raises(IntegrityError), transaction.atomic():
        AliasEmpresa.objects.create(empresa=e, texto="GLOBAL  OMNIUM")


def test_empresa_con_evidencias_no_se_borra(db):
    e = Empresa.objects.create(nombre="Urbaser")
    f = Fuente.objects.create(tipo="prensa_digital", nombre="Medio")
    ev = Evidencia.objects.create(
        categoria="otra", titulo="t", fuente=f, nivel="parcial", origen="manual"
    )
    ev.empresas.add(e)
    with pytest.raises(ProtectedError):
        e.delete()


def test_admin_edita_acotacion_con_casillas(client, administrador, cargados):
    acot = AcotacionEmpresa.objects.get(empresa__nombre="FCC")
    client.force_login(administrador)
    url = f"/admin/entidades/acotacionempresa/{acot.pk}/change/"
    assert 'type="checkbox"' in client.get(url).content.decode()
    r = client.post(
        url,
        {
            "empresa": acot.empresa_id,
            "servicios_incluidos": ["residuos"],
            "ambito_geografico": "",
            "nota": "Solo residuos",
            "fuente": "x",
        },
    )
    assert r.status_code == 302
    acot.refresh_from_db()
    assert acot.servicios_incluidos == ["residuos"] and acot.nota == "Solo residuos"
