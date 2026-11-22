"""Ponta a ponta: servidor uvicorn real (thread) + cliente HTTP real + AppTest do Streamlit."""

import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from modelo_sintetico import config_para
from streamlit.testing.v1 import AppTest

from app.api.main import criar_app
from app.cliente import ApiErro, ApiIndisponivel, ClienteAPI

CAMINHO = str(Path(__file__).resolve().parents[2] / "src" / "app" / "frontend" / "app.py")


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def url(pasta_artefato):
    porta = _porta_livre()
    app = criar_app(config_para(pasta_artefato))  # carrega o artefato de verdade (hashes)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=porta, log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    assert server.started, "servidor não subiu"
    yield f"http://127.0.0.1:{porta}"
    server.should_exit = True
    t.join(timeout=5)


def test_cliente_contra_api_real(url):
    c = ClienteAPI(url)
    assert c.saude()["modelo_carregado"] is True
    assert c.versao()["modelo"]["identificador"] == "m1-sintetico-0.0.1"
    r = c.prever([{"idade_anos": 40, "sexo": "M", "gestante": 0}])
    assert r["previsoes"][0]["status"] == "ok"
    with pytest.raises(ApiErro) as e:
        c.prever([{"idade_anos": 40, "outro": 1}])
    assert e.value.status == 422 and any("outro" in i for i in e.value.itens)


def test_cliente_api_fora_do_ar():
    with pytest.raises(ApiIndisponivel):
        ClienteAPI(f"http://127.0.0.1:{_porta_livre()}", timeout_s=0.5).saude()


def test_fluxo_completo_frontend_api_modelo(url, monkeypatch):
    monkeypatch.setenv("DENGUE_APP_API_URL", url)
    at = AppTest.from_file(CAMINHO, default_timeout=30)
    at.run()
    assert not at.exception and not at.error
    at.number_input(key="idade").set_value(72.0)
    at.selectbox(key="sexo").select("Feminino")
    at.button[0].click().run()
    assert not at.exception and not at.error
    valor = at.metric[0].value
    assert valor.endswith("%") and 0 <= float(valor[:-1].replace(",", ".")) <= 100
    assert any("E1 indisponível" in i.value for i in at.info)


def test_fluxo_frontend_com_api_fora_do_ar(monkeypatch):
    monkeypatch.setenv("DENGUE_APP_API_URL", f"http://127.0.0.1:{_porta_livre()}")
    monkeypatch.setenv("DENGUE_APP_TIMEOUT_S", "0.5")
    at = AppTest.from_file(CAMINHO, default_timeout=30)
    at.run()
    assert not at.exception
    assert any("falar com a API" in e.value for e in at.error)


def test_tempo_20_perfis_menos_de_1_segundo(url):
    c = ClienteAPI(url)
    perfis = [
        {"idade_anos": 5 * i, "sexo": ("F", "M", "I")[i % 3], "gestante": i % 2} for i in range(20)
    ]
    c.prever(perfis)  # aquecimento
    melhor = min(_medir(c, perfis) for _ in range(5))
    assert melhor < 1.0, f"{melhor:.3f} s"


def _medir(c, perfis) -> float:
    t0 = time.perf_counter()
    r = c.prever(perfis)
    dt = time.perf_counter() - t0
    assert len(r["previsoes"]) == 20 and all(p["status"] == "ok" for p in r["previsoes"])
    return dt
