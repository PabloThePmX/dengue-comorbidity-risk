"""Testes da interface com AppTest. A API é substituída por um cliente falso."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import app.cliente as cliente_mod
from app.cliente import ApiErro, ApiIndisponivel

CAMINHO = str(Path(__file__).resolve().parents[2] / "src" / "app" / "frontend" / "app.py")

VERSAO = {
    "sistema": {"app": "0.1.0", "python": "3.13"},
    "modelo": {
        "identificador": "m1-teste",
        "anos_desenvolvimento": [2022, 2023],
        "limitacoes": ["Limitação de teste."],
        "avaliacao_desenvolvimento": {
            "prevalencia": 0.0016,
            "pr_auc": 0.0086,
            "roc_auc": 0.65,
            "brier": 0.00161,
            "brier_referencia_prevalencia": 0.00162,
        },
    },
    "e1": {"disponivel": False, "motivo": "E1 ainda não existe (motivo de teste)."},
}


class ClienteFalso:
    versao_resp = VERSAO
    prever_resp = None
    erro_versao = None
    erro_prever = None
    chamadas: list = []

    def __init__(self, *a, **k):
        pass

    def versao(self):
        if self.erro_versao:
            raise self.erro_versao
        return self.versao_resp

    def prever(self, registros):
        type(self).chamadas.append(registros)
        if self.erro_prever:
            raise self.erro_prever
        return self.prever_resp or {
            "versao_modelo": "m1-teste",
            "aviso": "x",
            "previsoes": [{"indice": 0, "probabilidade": 0.0123, "status": "ok", "erro": ""}],
        }


@pytest.fixture
def falso(monkeypatch):
    class C(ClienteFalso):
        chamadas = []

    monkeypatch.setattr(cliente_mod, "ClienteAPI", C)
    return C


def _rodar():
    at = AppTest.from_file(CAMINHO, default_timeout=30)
    at.run()
    return at


def _textos(at):
    partes = []
    for lista in (at.warning, at.error, at.info, at.markdown, at.caption, at.subheader):
        partes += [e.value for e in lista]
    return "\n".join(partes)


def test_pagina_inicial_com_avisos(falso):
    at = _rodar()
    assert not at.exception
    assert at.title[0].value == "Risco de dengue grave"
    assert any("não substitui avaliação médica" in w.value for w in at.warning)
    assert len(at.tabs) == 4
    assert "Protótipo de pesquisa" in _textos(at)


def test_formulario_e_resultado(falso):
    at = _rodar()
    at.number_input(key="idade").set_value(55.0)
    at.selectbox(key="sexo").select("Feminino")
    at.checkbox(key="gestante").check()
    at.button[0].click().run()
    assert not at.exception
    assert falso.chamadas[-1] == [{"idade_anos": 55.0, "sexo": "F", "gestante": 1}]
    assert at.metric[0].value == "1,23%"
    assert at.dataframe  # histórico da sessão
    assert any("limitada" in w.value for w in at.warning)


def test_historico_acumula_e_limita(falso):
    at = _rodar()
    for _ in range(22):
        at.button[0].click().run()
    assert len(at.session_state["historico"]) == 20


def test_perfil_invalido_mostra_erro(falso):
    falso.prever_resp = {
        "versao_modelo": "m",
        "aviso": "x",
        "previsoes": [
            {"indice": 0, "probabilidade": None, "status": "invalido", "erro": "idade_anos: fora"}
        ],
    }
    at = _rodar()
    at.button[0].click().run()
    assert any("Perfil inválido: idade_anos: fora" in e.value for e in at.error)
    assert not at.metric


def test_api_fora_do_ar_na_partida(falso):
    falso.erro_versao = ApiIndisponivel("x")
    at = _rodar()
    assert not at.exception
    assert any("falar com a API" in e.value for e in at.error)
    assert not at.button  # sem API não há formulário


def test_api_cai_durante_o_calculo(falso):
    falso.erro_prever = ApiIndisponivel("x")
    at = _rodar()
    at.button[0].click().run()
    assert not at.exception
    assert any("não respondeu" in e.value for e in at.error)


def test_api_recusa_pedido(falso):
    falso.erro_prever = ApiErro(422, ["registro 1: idade_anos: tipo"])
    at = _rodar()
    at.button[0].click().run()
    assert any("recusou" in e.value and "idade_anos" in e.value for e in at.error)


def test_api_sem_modelo_na_partida(falso):
    falso.erro_versao = ApiErro(503, ["modelo indisponível: x"])
    at = _rodar()
    assert any("não está pronta" in e.value for e in at.error)


def test_aba_e1_indisponivel(falso):
    at = _rodar()
    assert any("E1 indisponível" in i.value and "motivo de teste" in i.value for i in at.info)


def test_limitacoes_trazem_metricas_e_leitura_honesta(falso):
    at = _rodar()
    todo = _textos(at)
    assert "não de desempenho em dado futuro" in todo
    assert any("PR-AUC" in m.value for m in at.markdown)
    assert at.table, "tabela de métricas ausente"
    assert not any(
        p in todo.lower() for p in ("validado", "pronto para uso", "recomendado para uso clínico")
    )


def test_alerta_sexo_masculino_e_gestante(falso):
    at = _rodar()
    at.selectbox(key="sexo").select("Masculino")
    at.checkbox(key="gestante").check()
    at.button[0].click().run()  # widgets de formulário só valem após o envio
    assert any("sexo masculino e gestante" in w.value for w in at.warning)


def test_masculino_gestante_bloqueia_calculo(falso):
    at = _rodar()
    at.selectbox(key="sexo").select("Masculino")
    at.checkbox(key="gestante").check()
    at.button[0].click().run()
    assert falso.chamadas == []
    assert any("bloqueado" in w.value for w in at.warning)
    assert not at.metric


def test_avisos_do_calculo_aparecem(falso):
    falso.prever_resp = {
        "versao_modelo": "m",
        "aviso": "x",
        "previsoes": [
            {
                "indice": 0,
                "probabilidade": 0.01,
                "status": "ok",
                "erro": "",
                "avisos": ["idade 3 e gestante"],
            }
        ],
    }
    at = _rodar()
    at.button[0].click().run()
    assert any("idade 3 e gestante" in w.value for w in at.warning)


def test_desfecho_e_validacao_ou_nao_informado(falso):
    at = _rodar()
    assert "não informado" in _textos(at)
    v = {
        **VERSAO,
        "modelo": {**VERSAO["modelo"], "desfecho": "dengue grave", "validacao": "CV por região"},
    }
    falso.versao_resp = v
    at = _rodar()
    todo = " ".join(m.value for m in at.markdown)
    assert "dengue grave" in todo and "CV por região" in todo
