import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
for p in (RAIZ / "src", Path(__file__).resolve().parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from modelo_sintetico import config_para, criar_artefato  # noqa: E402

from app.servico import criar_servico  # noqa: E402


@pytest.fixture(scope="session")
def pasta_artefato(tmp_path_factory):
    return criar_artefato(tmp_path_factory.mktemp("artefatos"))


@pytest.fixture
def config(pasta_artefato):
    return config_para(pasta_artefato)


@pytest.fixture(scope="session")
def servico(pasta_artefato):
    return criar_servico(config_para(pasta_artefato))
