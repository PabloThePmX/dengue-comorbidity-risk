import pytest

from app.config import MAX_CORPO_PADRAO, ConfigInvalida, carregar_config


def test_padroes():
    c = carregar_config({})
    assert c.api_url == "http://127.0.0.1:8000"
    assert c.log_nivel == "INFO" and c.max_corpo_bytes == MAX_CORPO_PADRAO
    assert c.servico.limite_registros == 1000 and c.servico.m1_sha256 is None


def test_variaveis_de_ambiente():
    pino = "a" * 64
    c = carregar_config(
        {
            "DENGUE_APP_API_URL": "http://localhost:9000/",
            "DENGUE_LIMITE_REGISTROS": "50",
            "DENGUE_APP_LOG_NIVEL": "debug",
            "DENGUE_APP_TIMEOUT_S": "2.5",
            "DENGUE_APP_MAX_CORPO_BYTES": "2048",
            "DENGUE_ARTEFATOS": "/tmp/x",
            "DENGUE_M1": "m1-teste",
            "DENGUE_APP_MODELO_SHA256": pino.upper(),
        }
    )
    assert c.api_url == "http://localhost:9000"
    assert c.log_nivel == "DEBUG" and c.timeout_s == 2.5 and c.max_corpo_bytes == 2048
    assert c.servico.limite_registros == 50 and c.servico.m1 == "m1-teste"
    assert str(c.servico.pasta_artefatos) == "/tmp/x" and c.servico.m1_sha256 == pino


@pytest.mark.parametrize(
    "env",
    [
        {"DENGUE_LIMITE_REGISTROS": "0"},
        {"DENGUE_APP_TIMEOUT_S": "0"},
        {"DENGUE_APP_TIMEOUT_S": "abc"},
        {"DENGUE_APP_MAX_CORPO_BYTES": "10"},
        {"DENGUE_APP_LOG_NIVEL": "barulho"},
        {"DENGUE_APP_API_URL": "ftp://x"},
        {"DENGUE_APP_MODELO_SHA256": "curto"},
    ],
)
def test_valores_invalidos_falham(env):
    with pytest.raises(ConfigInvalida):
        carregar_config(env)
