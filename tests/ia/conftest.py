import pytest

from tests.medios.test_recortes import pdf


@pytest.fixture
def base_ia_recorte(empresas_gestoras, municipios_cv, administrador, settings, tmp_path):
    from apps.medios.clipping import subir_recorte

    settings.MEDIA_ROOT = tmp_path
    subir_recorte(pdf(None), "ABC.pdf", administrador)
