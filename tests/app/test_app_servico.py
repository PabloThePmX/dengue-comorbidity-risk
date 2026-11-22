"""Camada fina `app.servico`: só confere que delega ao núcleo e que o modo degradado vale."""

import pytest
from modelo_sintetico import config_para

from app.config import Config
from app.servico import AVISO, EntradaInvalida, ModeloIndisponivel, criar_servico, info_sistema
from dengue_sinan.servico import ConfigServico


def test_info_e_prever(servico):
    m1 = servico.info()["m1"]
    assert m1["identificador"] == "m1-sintetico-0.0.1"
    assert m1["variaveis"] == ["idade_anos", "sexo", "gestante"]
    assert m1["avaliacao_desenvolvimento"]["prevalencia"] == 0.0016
    assert m1["desfecho"] and m1["validacao"] == "SINTÉTICO"
    r = servico.prever_m1([{"idade_anos": 10, "sexo": "F"}, {"idade_anos": 80, "sexo": "M"}])
    assert [x["indice"] for x in r["resultados"]] == [0, 1]
    assert r["aviso"] == AVISO and r["resultados"][0]["alto_risco"] is None


def test_registro_invalido_nao_derruba_os_outros(servico):
    r = servico.prever_m1([{"idade_anos": 30}, {"idade_anos": 200}, {"sexo": "F"}])
    assert [x["status"] for x in r["resultados"]] == ["ok", "invalido", "invalido"]


def test_campo_desconhecido_levanta(servico):
    with pytest.raises(EntradaInvalida):
        servico.prever_m1([{"idade_anos": 30, "comorbidade": 1}])


def test_e1_indisponivel(servico):
    assert servico.estado_e1()["status"] == "indisponivel"
    with pytest.raises(ModeloIndisponivel):
        servico.prever_e1([])


def test_pasta_inexistente_fica_degradada(tmp_path):
    s = criar_servico(Config(servico=ConfigServico(tmp_path / "nao_existe", None, None)))
    assert s.saude()["status"] == "degradado"


def test_pino_correto_e_errado(pasta_artefato):
    import hashlib

    real = hashlib.sha256((pasta_artefato / "modelo.joblib").read_bytes()).hexdigest()
    assert criar_servico(config_para(pasta_artefato, m1_sha256=real)).saude()["status"] == "ok"
    ruim = criar_servico(config_para(pasta_artefato, m1_sha256="0" * 64))
    assert ruim.saude()["status"] == "degradado"


def test_info_sistema():
    assert info_sistema()["app"]
