"""Tela da demo (T-6.1, T-6.4 parte de teste) com `streamlit.testing.v1.AppTest`.

Usa o E1 real (`models/e1`, versionado) e, quando existe, o M1 real (`models/m1_final`, fora do
git). Sem o M1, só os testes da aba Triagem com modelo são pulados.
"""

import logging
import re
import shutil
import time
import tomllib
from pathlib import Path

import pytest
from app_sintetico import CONTRATO_COMORBIDADES, CONTRATO_SINAIS
from streamlit.testing.v1 import AppTest
from test_app_servico import _escritas, _sem_rede, precisa_m1

from app import linguagem, servico
from dengue_sinan import explain

RAIZ = Path(__file__).resolve().parents[1]
SCRIPT = RAIZ / "src" / "app" / "streamlit_app.py"
AVISO = "Projeto acadêmico. Não é ferramenta clínica nem substitui avaliação médica."
LIMITE_S = 1.0  # NFR-06


def _app(monkeypatch=None, modelos=None, relatorios=None, modo="pro") -> AppTest:
    """A tela abre no modo Normal (D-96); os testes do modo Pro pedem `modo="pro"` (padrão aqui)."""
    if modelos is not None:
        monkeypatch.setenv(servico.ENV_MODELOS, str(modelos))
    if relatorios is not None:
        monkeypatch.setenv(servico.ENV_RELATORIOS, str(relatorios))
    at = AppTest.from_file(str(SCRIPT), default_timeout=120)
    if modo is not None:
        at.session_state["modo"] = modo
    return at


def _textos(at: AppTest) -> str:
    elementos = [*at.markdown, *at.caption, *at.info, *at.warning, *at.error, *at.success]
    return "\n".join(str(e.value) for e in elementos)


def _metricas(at: AppTest) -> dict[str, str]:
    return {m.label: m.value for m in at.metric}


@pytest.fixture
def so_e1(tmp_path, monkeypatch):
    """Instalação sem `m1_final` e sem `reports/teste`: só o E1 (que está no git)."""
    shutil.copytree(RAIZ / "models" / "e1", tmp_path / "modelos" / "e1")
    (tmp_path / "relatorios").mkdir()
    monkeypatch.setenv(servico.ENV_MODELOS, str(tmp_path / "modelos"))
    monkeypatch.setenv(servico.ENV_RELATORIOS, str(tmp_path / "relatorios"))


# --- Subida e conteúdo -------------------------------------------------------------------------

def test_app_sobe_sem_m1_final_e_sem_reports_teste(so_e1):
    at = _app().run()
    assert not at.exception
    texto = _textos(at)
    assert servico.MSG_M1_AUSENTE in texto  # a aba Triagem explica que o modelo não está aqui
    assert [t.label for t in at.tabs] == ["Perfil (E1)", "Triagem (M1)"]
    assert "Risco estimado (E1)" in _metricas(at)  # a aba Perfil funciona
    assert not [e for e in at.expander if "teste de 2024" in e.label]  # painel some, sem erro
    assert "Alto risco" not in _metricas(at)


def test_app_sobe_sem_nenhum_artefato(tmp_path, monkeypatch):
    at = _app(monkeypatch, tmp_path, tmp_path).run()
    assert not at.exception
    assert servico.MSG_E1_AUSENTE in _textos(at) and servico.MSG_M1_AUSENTE in _textos(at)


def test_aviso_fixo_e_frases_das_duas_abas(so_e1):
    at = _app().run()
    assert any(AVISO in i.value for i in at.info)  # aba Perfil
    assert any(AVISO in w.value for w in at.warning)  # aba Triagem, em destaque
    texto = _textos(at)
    assert "qual o risco de quem tem estas condições" in texto
    assert "qual o risco deste paciente, com estes sintomas, agora" in texto


def test_painel_do_teste_de_2024_aparece_aberto_com_os_numeros_do_arquivo():
    if not (RAIZ / "reports" / "teste" / "metricas.json").is_file():
        pytest.skip("reports/teste/metricas.json não existe")
    at = _app().run()
    [painel] = [e for e in at.expander if e.label == "O que o teste de 2024 mostrou"]
    texto = "\n".join(m.value for m in painel.markdown)
    assert "subestimou o risco em 2024" in texto and "possivelmente baixa" in texto
    assert "desfecho conhecido" in texto
    assert re.search(r"cerca de 14% dos casos", texto) and "SC-02" in texto
    assert "5.331.745" in texto  # números em pt-BR, vindos do arquivo


def test_sem_analytics_no_config_do_streamlit():
    cfg = tomllib.loads((RAIZ / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
    assert cfg["browser"]["gatherUsageStats"] is False


# --- Aba Perfil --------------------------------------------------------------------------------

def test_perfil_mostra_risco_ic_comparacao_e_or_batendo_com_explain(so_e1):
    at = _app().run()
    at.number_input(key="perfil_idade").set_value(60)
    at.checkbox(key="perfil_diabetes").check()
    at.checkbox(key="perfil_hipertensao").check().run()
    assert not at.exception
    e1 = servico.carregar_artefatos(RAIZ / "models").e1
    direto = explain.risco_perfil(e1, 60, "F", 0, ("DIABETES", "HIPERTENSA"))
    metricas = _metricas(at)
    assert metricas["Risco estimado (E1)"] == servico.porcentagem(direto["risco"])
    inf, sup = (servico.porcentagem(direto[k]) for k in ("ic_inferior", "ic_superior"))
    ic = f"[{inf}; {sup}]"
    assert ic in _textos(at)
    assert metricas["Sem comorbidades, mesma idade, sexo e gestação"]
    [tabela] = at.table
    assert list(tabela.value["Comorbidade"]) == ["Diabetes", "Hipertensão"]
    assert "vezes" in _textos(at)


def test_perfil_com_5_comorbidades_mostra_dados_insuficientes_e_nenhum_numero(so_e1):
    at = _app().run()
    for campo, _ in CONTRATO_COMORBIDADES[:5]:
        at.checkbox(key=f"perfil_{campo}").check()
    at.run()
    assert not at.exception
    assert any("dados insuficientes" in w.value for w in at.warning)
    assert "Risco estimado (E1)" not in _metricas(at) and len(at.table) == 0


def test_gestante_so_aparece_para_sexo_feminino(so_e1):
    at = _app().run()
    assert [c.key for c in at.checkbox if c.key == "perfil_gestante"]
    at.radio(key="perfil_sexo").set_value("M").run()
    assert not [c for c in at.checkbox if c.key == "perfil_gestante"]
    assert not at.exception


# --- Aba Triagem -------------------------------------------------------------------------------

@precisa_m1
def test_triagem_mostra_risco_alto_risco_b2_e_5_fatores_com_a_frase():
    at = _app().run()
    at.number_input(key="triagem_idade").set_value(70)
    at.selectbox(key="triagem_hipertensao").select("sim")
    at.selectbox(key="triagem_febre").select("sim")
    at.selectbox(key="triagem_vomito").select("sim").run()
    assert not at.exception
    metricas = _metricas(at)
    assert metricas["Risco estimado (M1, calibrado)"].endswith("%")
    assert metricas["Alto risco"] in ("Sim", "Não")
    assert metricas["Regra do protocolo (grupo B)"] == "Sim"  # > 65 anos
    tabela = at.table[-1].value  # a última tabela é a dos fatores
    assert len(tabela) == servico.N_FATORES
    assert set(tabela["Efeito"]) <= {"aumentou o risco", "reduziu o risco"}
    assert "contribuição no modelo, não causa" in _textos(at)
    assert "sinal de triagem de baixa precisão, não um diagnóstico" in _textos(at)
    assert "Sem IC por predição" in _textos(at)


# --- NFR-06: 20 perfis respondem em < 1 s ------------------------------------------------------

IDADES = [0, 1, 4, 15, 25, 30, 39, 45, 59, 60, 65, 66, 70, 79, 80, 90, 100, 120, 35, 50]
COMORBIDADES_20 = [(), ("diabetes",), ("hipertensao",), ("diabetes", "hipertensao"),
                   ("renal_cronica",), ("hematologica", "renal_cronica"),
                   ("diabetes", "renal_cronica", "hipertensao"),
                   ("hepatopatia", "autoimune", "diabetes", "renal_cronica"),
                   tuple(c for c, _ in CONTRATO_COMORBIDADES[:5]),
                   tuple(c for c, _ in CONTRATO_COMORBIDADES)]
SINTOMAS_20 = [(), ("febre",), ("febre", "mialgia", "cefaleia"), ("vomito", "nausea"),
               ("petequia_n", "laco"), tuple(c for c, _ in CONTRATO_SINAIS)]


def _perfis_20():
    return [{
        "idade": IDADES[i],
        "sexo": "F" if i % 2 == 0 else "M",
        "comorbidades": COMORBIDADES_20[i % len(COMORBIDADES_20)],
        "sintomas": SINTOMAS_20[i % len(SINTOMAS_20)],
        "dias": (i * 7) % 61,
    } for i in range(20)]


def test_os_20_perfis_da_medicao_sao_distintos():
    perfis = {(p["idade"], p["sexo"], p["comorbidades"], p["sintomas"], p["dias"])
              for p in _perfis_20()}
    assert len(perfis) == 20


def _aplicar(at: AppTest, p: dict, triagem: bool) -> None:
    at.number_input(key="perfil_idade").set_value(p["idade"])
    at.radio(key="perfil_sexo").set_value(p["sexo"])
    for campo, _ in CONTRATO_COMORBIDADES:
        caixa = at.checkbox(key=f"perfil_{campo}")
        caixa.check() if campo in p["comorbidades"] else caixa.uncheck()
    if triagem:
        at.number_input(key="triagem_idade").set_value(p["idade"])
        at.radio(key="triagem_sexo").set_value(p["sexo"])
        for campo, _ in CONTRATO_COMORBIDADES:
            at.selectbox(key=f"triagem_{campo}").select("sim" if campo in p["comorbidades"]
                                                        else "nao")
        for campo, _ in CONTRATO_SINAIS:
            at.selectbox(key=f"triagem_{campo}").select("sim" if campo in p["sintomas"] else "nao")
        at.number_input(key="triagem_dias").set_value(p["dias"])


def _rodar_perfis(triagem: bool) -> list[float]:
    at = _app().run()  # carga inicial (artefatos em cache depois dela): fora da medição
    assert not at.exception
    tempos = []
    for p in _perfis_20():
        _aplicar(at, p, triagem)
        inicio = time.perf_counter()
        at.run()
        tempos.append(time.perf_counter() - inicio)
        assert not at.exception
        metricas = _metricas(at)
        if len(p["comorbidades"]) <= explain.MAX_COMORBIDADES_ESTIMADAS:
            assert "Risco estimado (E1)" in metricas
        else:
            assert "Risco estimado (E1)" not in metricas  # dados insuficientes, sem número
        if triagem:
            assert "Risco estimado (M1, calibrado)" in metricas
    return tempos


def test_20_perfis_respondem_a_aba_perfil_em_menos_de_1_s():
    tempos = _rodar_perfis(triagem=False)
    assert len(tempos) == 20 and max(tempos) < LIMITE_S, tempos


@precisa_m1
def test_20_perfis_respondem_as_duas_abas_em_menos_de_1_s():
    """Cada `run` recalcula as duas abas (o Streamlit executa todas as abas a cada interação)."""
    tempos = _rodar_perfis(triagem=True)
    assert len(tempos) == 20 and max(tempos) < LIMITE_S, tempos


@precisa_m1
def test_triagem_sozinha_20_perfis_pelo_servico_em_menos_de_1_s():
    from app import entrada

    a = servico.carregar_artefatos()
    tempos = []
    for p in _perfis_20():
        bruto = {"idade_anos": p["idade"], "sexo": p["sexo"], "gestante": "nao",
                 "dias_ate_notificacao": p["dias"],
                 **{c: ("sim" if c in p["comorbidades"] else "nao")
                    for c, _ in CONTRATO_COMORBIDADES},
                 **{c: ("sim" if c in p["sintomas"] else "nao") for c, _ in CONTRATO_SINAIS}}
        inicio = time.perf_counter()
        servico.avaliar_caso(a.m1, entrada.validar_caso(bruto))
        tempos.append(time.perf_counter() - inicio)
    assert max(tempos) < LIMITE_S, tempos


# --- Privacidade na tela -----------------------------------------------------------------------

@precisa_m1
def test_usar_a_tela_nao_grava_em_disco_nao_loga_a_entrada_e_nao_abre_rede(monkeypatch, caplog,
                                                                         capsys):
    at = _app().run()  # aquecimento
    escritas = _escritas(monkeypatch)
    _sem_rede(monkeypatch)
    caplog.set_level(logging.DEBUG)
    at.number_input(key="perfil_idade").set_value(103)
    at.number_input(key="triagem_idade").set_value(103)
    at.number_input(key="triagem_dias").set_value(59)
    at.selectbox(key="triagem_febre").select("sim")
    at.checkbox(key="perfil_diabetes").check().run()
    assert not at.exception and _metricas(at)
    assert escritas == []
    textos = [r.getMessage() for r in caplog.records]
    assert not [t for t in textos if re.search(r"\b103\b|\b59\b|idade_anos|DIABETES", t)]
    saida = capsys.readouterr()
    assert not re.search(r"\b103\b|\b59\b", saida.out + saida.err)


def test_so_o_estado_dos_campos_fica_em_session_state(so_e1):
    at = _app().run()
    at.number_input(key="perfil_idade").set_value(61).run()
    chaves = set(at.session_state.keys())
    assert chaves and all(k == "modo" or k.startswith(("perfil_", "triagem_")) for k in chaves), \
        chaves


# --- Modos Normal e Pro (D-96) -----------------------------------------------------------------

JARGAO = ("IC 95%", "OR", "log-odds", "SHAP", "recall", "precisão", "limiar", "calibrado",
          "E1", "M1", "SC-02", "B2", "grupo B", "razão de chances", "método delta")


def _jargao_na_tela(at: AppTest) -> list[str]:
    texto = _textos(at) + "\n" + "\n".join(
        [m.label + " " + str(m.value) for m in at.metric]
        + [str(c) for t in at.table for c in t.value.columns]
        + [str(v) for t in at.table for v in t.value.to_numpy().ravel()]
        + [e.label for e in at.expander] + [t.label for t in at.tabs])
    return [j for j in JARGAO if re.search(rf"(?<![\wÀ-ú]){re.escape(j)}(?![\wÀ-ú])", texto)]


def test_o_app_abre_no_modo_normal_por_padrao(so_e1):
    at = _app(modo=None).run()
    assert not at.exception
    assert at.radio(key="modo").value == "normal"
    assert [t.label for t in at.tabs] == ["Perfil", "Triagem"]


def test_modo_normal_do_perfil_fala_em_frequencia_e_sem_jargao(so_e1):
    at = _app(modo="normal").run()
    at.number_input(key="perfil_idade").set_value(60)
    at.checkbox(key="perfil_diabetes").check().run()
    assert not at.exception
    e1 = servico.carregar_artefatos(RAIZ / "models").e1
    direto = explain.risco_perfil(e1, 60, "F", 0, ("DIABETES",))
    assert _metricas(at)["Risco estimado"] == linguagem.um_em(direto["risco"])
    assert "Risco estimado (E1)" not in _metricas(at) and len(at.table) == 0
    assert "vezes maior" in _textos(at)
    assert AVISO in _textos(at)
    assert _jargao_na_tela(at) == []


def test_modo_normal_do_perfil_sem_estimativa_diz_em_palavras(so_e1):
    at = _app(modo="normal").run()
    for campo, _ in CONTRATO_COMORBIDADES[:5]:
        at.checkbox(key=f"perfil_{campo}").check()
    at.run()
    assert not at.exception
    assert any(linguagem.SEM_ESTIMATIVA in w.value for w in at.warning)
    assert "Risco estimado" not in _metricas(at)


def test_trocar_para_pro_mostra_os_detalhes_e_voltar_esconde(so_e1):
    at = _app(modo="normal").run()
    at.checkbox(key="perfil_diabetes").check().run()
    assert "Risco estimado (E1)" not in _metricas(at)
    at.radio(key="modo").set_value("pro").run()
    assert "Risco estimado (E1)" in _metricas(at) and len(at.table) == 1
    assert [t.label for t in at.tabs] == ["Perfil (E1)", "Triagem (M1)"]
    at.radio(key="modo").set_value("normal").run()
    assert "Risco estimado (E1)" not in _metricas(at)


@precisa_m1
def test_modo_normal_da_triagem_nao_mostra_alto_risco_nem_regra_nem_jargao():
    at = _app(modo="normal").run()
    at.number_input(key="triagem_idade").set_value(70)
    at.selectbox(key="triagem_hipertensao").select("sim")
    at.selectbox(key="triagem_febre").select("sim").run()
    assert not at.exception
    metricas = _metricas(at)
    assert "Risco estimado" in metricas and "Alto risco" not in metricas
    assert "Regra do protocolo (grupo B)" not in metricas
    tabela = at.table[-1].value
    assert len(tabela) == servico.N_FATORES
    assert set(tabela["Efeito"]) <= {"aumenta o risco neste caso", "diminui o risco neste caso"}
    assert "contribuição no modelo, não causa" in _textos(at)
    assert AVISO in "\n".join(w.value for w in at.warning)  # aviso em destaque nos dois modos
    assert _jargao_na_tela(at) == []


def test_painel_do_teste_em_modo_normal_usa_palavras_simples_e_os_numeros_do_arquivo():
    if not (RAIZ / "reports" / "teste" / "metricas.json").is_file():
        pytest.skip("reports/teste/metricas.json não existe")
    at = _app(modo="normal").run()
    [painel] = [e for e in at.expander if e.label == "Como o programa se saiu no teste"]
    texto = "\n".join(m.value for m in painel.markdown)
    assert "5.331.745" in texto and "subestimou o risco" in texto
    assert "O programa não alcançou essa regra" in texto
    assert _jargao_na_tela(at) == []
