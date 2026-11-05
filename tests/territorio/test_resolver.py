import pytest

from apps.territorio.models import Municipio, Provincia
from apps.territorio.services import resolver_municipio


@pytest.mark.parametrize("texto", ["L'Eliana", "l'Eliana", "Eliana", "ELIANA, L'", "l’Eliana"])
def test_cp05_formas_de_l_eliana(municipios_cv, texto):
    """CP-05: resuelven el mismo municipio si figuran en nombres_alternativos."""
    assert resolver_municipio(texto).codigo_ine == "46116"


def test_cp05_requiere_que_la_forma_este_en_alternativos(municipios_cv):
    eliana = Municipio.objects.get(codigo_ine="46116")
    eliana.nombres_alternativos = ["l'Eliana"]
    eliana.save()
    assert resolver_municipio("Eliana") is None
    assert resolver_municipio("l'Eliana") == eliana


def test_bilingues_y_mayusculas_de_las_semillas(municipios_cv):
    assert resolver_municipio("ALICANTE").codigo_ine == "03014"
    assert resolver_municipio("Alacant").codigo_ine == "03014"
    assert resolver_municipio("ELCHE").codigo_ine == "03065"
    assert resolver_municipio("CASTELLON DE LA PLANA").codigo_ine == "12040"


def test_sin_coincidencias_parciales(municipios_cv):
    """docs/04 §1: Agost no casa con Llagostera ni con la Llagosta."""
    girona = Provincia.objects.create(codigo_ine="17", nombre="Girona", comunidad="Catalunya")
    barcelona = Provincia.objects.create(codigo_ine="08", nombre="Barcelona", comunidad="Catalunya")
    Municipio.objects.create(codigo_ine="17095", nombre_oficial="Llagostera", provincia=girona)
    Municipio.objects.create(
        codigo_ine="08904",
        nombre_oficial="Llagosta, La",
        nombres_alternativos=["La Llagosta"],
        provincia=barcelona,
    )
    assert resolver_municipio("Agost").codigo_ine == "03002"
    assert resolver_municipio("Llagostera").codigo_ine == "17095"
    assert resolver_municipio("Agos") is None
    assert resolver_municipio("Ayuntamiento de Llagostera") is None


def test_tavernes_es_ambiguo_y_no_se_resuelve(municipios_cv):
    """docs/04 §9: «TAVERNES» no es un municipio; no se elige uno a ciegas."""
    assert resolver_municipio("TAVERNES") is None
    assert resolver_municipio("Tavernes de la Valldigna").codigo_ine == "46238"


def test_el_bosque_chiva_solo_con_alias_manual(municipios_cv):
    assert resolver_municipio("EL BOSQUE-CHIVA") is None
    chiva = Municipio.objects.get(codigo_ine="46111")
    chiva.nombres_alternativos = [*chiva.nombres_alternativos, "El Bosque-Chiva"]
    chiva.save()
    assert resolver_municipio("EL BOSQUE-CHIVA") == chiva


def test_homonimo_entre_provincias_no_se_resuelve_sin_filtro(municipios_cv):
    prov = Provincia.objects.create(codigo_ine="30", nombre="Murcia", comunidad="Región de Murcia")
    Municipio.objects.create(codigo_ine="30999", nombre_oficial="Agost", provincia=prov)
    assert resolver_municipio("Agost") is None
    assert resolver_municipio("Agost", provincias=["03", "12", "46"]).codigo_ine == "03002"


def test_texto_vacio(municipios_cv):
    assert resolver_municipio("") is None
    assert resolver_municipio("   ") is None


def test_vista_municipios_para_lector(client, lector, municipios_cv):
    client.force_login(lector)
    r = client.get("/municipios/", {"q": "eliana"})
    assert r.status_code == 200
    contenido = r.content.decode()
    assert "46116" in contenido and "Meliana" in contenido  # contiene «eliana»
    r = client.get("/municipios/", {"provincia": "12"})
    assert "135 municipios" in r.content.decode()
