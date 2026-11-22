import logging

import pytest
from fastapi.testclient import TestClient
from modelo_sintetico import config_para

from app.api.main import criar_app
from app.config import Config
from dengue_sinan.servico import ConfigServico


@pytest.fixture
def cliente(config, servico):
    with TestClient(criar_app(config, servico)) as c:
        yield c


def test_saude(cliente):
    r = cliente.get("/saude")
    assert r.status_code == 200
    assert r.json() == {
        "status": "ok",
        "modelo_carregado": True,
        "versao_modelo": "m1-sintetico-0.0.1",
        "e1_disponivel": False,
        "detalhe": None,
    }
    assert "x-request-id" in r.headers


def test_versao_e_contrato(cliente):
    v = cliente.get("/versao").json()
    assert v["modelo"]["identificador"] == "m1-sintetico-0.0.1"
    assert v["e1"]["disponivel"] is False and v["e1"]["motivo"]
    assert v["sistema"]["app"]
    campos = [c["nome"] for c in cliente.get("/contrato").json()["campos"]]
    assert campos == ["idade_anos", "sexo", "gestante"]


def test_prever_ok(cliente):
    r = cliente.post(
        "/prever",
        json={"registros": [{"idade_anos": 34, "sexo": "F", "gestante": 0}, {"idade_anos": 70}]},
    )
    assert r.status_code == 200
    corpo = r.json()
    assert (
        corpo["versao_modelo"] == "m1-sintetico-0.0.1"
        and "Não é ferramenta clínica" in corpo["aviso"]
    )
    assert "limiar" in corpo["alto_risco_motivo"]
    assert [p["status"] for p in corpo["previsoes"]] == ["ok", "ok"]
    assert all(0 <= p["probabilidade"] <= 1 for p in corpo["previsoes"])
    assert r.headers["x-request-id"]


def test_prever_aceita_booleano_em_gestante(cliente):
    r = cliente.post("/prever", json={"registros": [{"idade_anos": 30, "gestante": True}]})
    assert r.status_code == 200 and r.json()["previsoes"][0]["status"] == "ok"


def test_registro_com_valor_invalido_volta_marcado(cliente):
    r = cliente.post("/prever", json={"registros": [{"idade_anos": 130}, {"idade_anos": 5}]})
    assert r.status_code == 200
    p = r.json()["previsoes"]
    assert p[0]["status"] == "invalido" and p[0]["probabilidade"] is None and p[0]["erro"]
    assert p[1]["status"] == "ok"


@pytest.mark.parametrize(
    "corpo",
    [
        {"registros": []},
        {},
        {"registros": [{"idade_anos": 30, "diabetes": 1}]},
        {"registros": [{"idade_anos": "34"}]},
        {"registros": [{"idade_anos": True}]},
        {"registros": "x"},
        {"registros": [5]},
    ],
)
def test_esquema_invalido_da_422(cliente, corpo):
    r = cliente.post("/prever", json=corpo)
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], list) and r.json()["detail"][0]["motivo"]


def test_json_quebrado_da_422(cliente):
    r = cliente.post("/prever", content="{nao e json", headers={"content-type": "application/json"})
    assert r.status_code == 422


def test_limite_de_registros(pasta_artefato, servico):
    app = criar_app(config_para(pasta_artefato, limite_registros=2), None)
    with TestClient(app) as c:
        r = c.post("/prever", json={"registros": [{"idade_anos": 1}] * 3})
    assert r.status_code == 422 and "no máximo 2" in r.json()["detail"][0]["motivo"]


def test_e1_indisponivel_da_501(cliente):
    r = cliente.post("/e1/perfil")
    assert r.status_code == 501 and r.json()["status"] == "indisponivel"


def test_sem_modelo_da_503(tmp_path):
    cfg = Config(servico=ConfigServico(tmp_path / "nao_existe", None, None))
    with TestClient(criar_app(cfg)) as c:
        s = c.get("/saude")
        assert s.status_code == 503 and s.json()["modelo_carregado"] is False
        assert c.get("/versao").status_code == 503
        assert c.get("/relatorio").status_code == 503
        assert c.get("/contrato").status_code == 503
        assert c.post("/prever", json={"registros": [{"idade_anos": 1}]}).status_code == 503


def test_erro_interno_nao_vaza_detalhe(config, servico, monkeypatch):
    def quebra(_):
        raise RuntimeError("segredo-interno")

    monkeypatch.setattr(servico, "prever_m1", quebra)
    with TestClient(criar_app(config, servico), raise_server_exceptions=False) as c:
        r = c.post("/prever", json={"registros": [{"idade_anos": 1}]})
    assert r.status_code == 500 and r.json() == {"detail": "erro interno"}


def test_openapi_documenta_as_rotas(cliente):
    doc = cliente.get("/openapi.json").json()
    assert {"/saude", "/versao", "/contrato", "/prever", "/e1/perfil", "/relatorio"} <= set(
        doc["paths"]
    )
    assert "Registro" in doc["components"]["schemas"]


def test_logs_nao_trazem_dados_do_paciente(cliente, caplog):
    with caplog.at_level(logging.INFO, logger="app.api"):
        cliente.post("/prever", json={"registros": [{"idade_anos": 61.37, "sexo": "M"}]})
    texto = caplog.text
    assert "/prever" in texto and "61.37" not in texto


def test_relatorio(cliente):
    r = cliente.get("/relatorio")
    assert r.status_code == 200 and r.json()["texto"] and isinstance(r.json()["dados"], dict)


def test_aviso_de_plausibilidade_nao_bloqueia(cliente):
    r = cliente.post("/prever", json={"registros": [{"idade_anos": 3, "gestante": 1}]})
    p = r.json()["previsoes"][0]
    assert r.status_code == 200 and p["status"] == "ok" and p["avisos"]


def test_x_request_id_aceito_so_se_simples(cliente):
    ok = cliente.get("/saude", headers={"X-Request-ID": "abc-123_X"})
    assert ok.headers["x-request-id"] == "abc-123_X"
    for ruim in ("a b", "x" * 65, "<script>", "a;b"):
        r = cliente.get("/saude", headers={"X-Request-ID": ruim})
        assert r.headers["x-request-id"] != ruim and len(r.headers["x-request-id"]) == 12


def test_corpo_grande_da_413(pasta_artefato):
    cfg = config_para(pasta_artefato, max_corpo_bytes=1024)
    with TestClient(criar_app(cfg)) as c:
        grande = {"registros": [{"idade_anos": 30}] * 200}
        r = c.post("/prever", json=grande)
        assert r.status_code == 413
        assert c.post("/prever", json={"registros": [{"idade_anos": 30}]}).status_code == 200


def test_corpo_grande_sem_content_length_da_413(pasta_artefato):
    cfg = config_para(pasta_artefato, max_corpo_bytes=1024)

    def pedacos():
        for _ in range(50):
            yield b'{"registros": [{"idade_anos": 30}],' + b" " * 100

    with TestClient(criar_app(cfg)) as c:
        r = c.post("/prever", content=pedacos(), headers={"content-type": "application/json"})
    assert r.status_code == 413
