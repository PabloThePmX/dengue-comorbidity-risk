"""Entrada da demo (T-6.1, D-61): tradução para as features e recusa de entrada fora do domínio."""

import pandas as pd
import pytest
from app_sintetico import (
    CONTRATO_COMORBIDADES,
    CONTRATO_GESTANTE,
    CONTRATO_NIVEL,
    CONTRATO_SINAIS,
    bruta,
    frame_do_contrato,
)

from app import entrada
from dengue_sinan.config import load_config
from dengue_sinan.preprocess import FEATURES_PERMITIDAS
from dengue_sinan.profiling import COMORBIDADES, SINAIS

NIVEIS = ["sim", "nao", "ignorado"]


def _entrada_variada() -> dict:
    """Cada comorbidade e cada sintoma com um nível, em rodízio: nenhuma coluna igual à vizinha."""
    campos = [c for c, _ in CONTRATO_COMORBIDADES + CONTRATO_SINAIS]
    dados = {c: NIVEIS[i % 3] for i, c in enumerate(campos)}
    return {"idade_anos": 37, "sexo": "F", "gestante": "sim", "dias_ate_notificacao": 5, **dados}


# --- Tradução ----------------------------------------------------------------------------------

@pytest.mark.parametrize(("campo", "feature"), CONTRATO_COMORBIDADES + CONTRATO_SINAIS)
@pytest.mark.parametrize("nivel", NIVEIS)
def test_cada_campo_vira_a_feature_do_contrato_com_o_nivel_do_contrato(campo, feature, nivel):
    caso = entrada.validar_caso({**bruta(), campo: nivel})
    df = caso.para_frame()
    assert str(df.loc[0, feature]) == CONTRATO_NIVEL[nivel]
    # e só essa coluna mudou em relação ao caso "tudo não"
    base = entrada.validar_caso(bruta()).para_frame()
    mudou = [c for c in df.columns if str(df.loc[0, c]) != str(base.loc[0, c])]
    esperado = set() if nivel == "nao" else {feature}
    if nivel == "sim" and campo in dict(CONTRATO_COMORBIDADES):
        esperado.add("n_comorbidades")
    assert set(mudou) == esperado


@pytest.mark.parametrize("gestante", NIVEIS)
def test_gestante_sim_vira_1_e_nao_e_ignorado_viram_0(gestante):
    df = entrada.validar_caso(bruta(sexo="F", gestante=gestante)).para_frame()
    assert df.loc[0, "gestante"] == CONTRATO_GESTANTE[gestante]


def test_frame_inteiro_igual_ao_montado_a_mao_a_partir_do_contrato():
    for sexo, gestante, idade, dias in [("F", "sim", 37, 5), ("M", "nao", 0, 0),
                                        ("F", "ignorado", 120, 60)]:
        bruto = {**_entrada_variada(), "sexo": sexo, "gestante": gestante,
                 "idade_anos": idade, "dias_ate_notificacao": dias}
        obtido = entrada.validar_caso(bruto).para_frame()
        esperado = frame_do_contrato(bruto)
        assert set(obtido.columns) == set(esperado.columns)
        pd.testing.assert_frame_equal(obtido[list(esperado.columns)], esperado,
                                      check_dtype=False, check_categorical=False)


def test_n_comorbidades_e_o_numero_de_comorbidades_sim_e_nao_conta_sintomas():
    bruto = bruta(sim=("diabetes", "renal_cronica", "febre", "laco"), ignorado=("hepatopatia",))
    caso = entrada.validar_caso(bruto)
    assert caso.n_comorbidades == 2
    assert caso.para_frame().loc[0, "n_comorbidades"] == 2
    assert caso.marcadas == ("DIABETES", "RENAL")


def test_idade_e_dias_passam_iguais_e_o_frame_so_tem_features_permitidas_mais_ano():
    df = entrada.validar_caso(bruta(idade=73, dias=44)).para_frame()
    assert df.loc[0, "idade_anos"] == 73
    assert df.loc[0, "dias_ate_notificacao"] == 44
    assert set(df.columns) - {"ANO"} == set(FEATURES_PERMITIDAS)  # R4: nada além do dicionário
    assert set(COMORBIDADES) | set(SINAIS) <= set(df.columns)


def test_ano_do_frame_nunca_e_o_ano_de_teste():
    cfg = load_config()
    ano = entrada.validar_caso(bruta()).para_frame().loc[0, "ANO"]
    assert ano in cfg["anos_dev"] and ano != cfg["ano_teste"]  # R1


# --- Domínio -----------------------------------------------------------------------------------

@pytest.mark.parametrize(("campo", "valor"), [
    ("idade_anos", -1), ("idade_anos", 121), ("idade_anos", 40.5), ("idade_anos", "40"),
    ("idade_anos", True), ("idade_anos", None),
    ("dias_ate_notificacao", -1), ("dias_ate_notificacao", 61), ("dias_ate_notificacao", 2.5),
    ("sexo", "X"), ("sexo", "I"), ("sexo", "m"), ("sexo", None),
    ("gestante", "talvez"), ("gestante", True),
    ("diabetes", "talvez"), ("renal_cronica", "Sim"), ("autoimune", 1), ("febre", "Não"),
    ("laco", ""),
])
def test_entrada_fora_do_dominio_e_recusada_com_mensagem(campo, valor):
    with pytest.raises(entrada.EntradaInvalida) as erro:
        entrada.validar_caso({**bruta(), campo: valor})
    assert len(erro.value.erros) == 1
    assert erro.value.erros[0].endswith((".",))  # frase completa em pt-BR


def test_limites_do_dominio_sao_aceitos():
    for idade in (0, 120):
        for dias in (0, 60):
            entrada.validar_caso(bruta(idade=idade, dias=dias))


def test_gestante_com_sexo_m_e_recusada_mas_nao_ou_ignorado_com_sexo_m_passam():
    with pytest.raises(entrada.EntradaInvalida, match="só é possível com sexo F"):
        entrada.validar_caso(bruta(sexo="M", gestante="sim"))
    for gestante in ("nao", "ignorado"):
        assert entrada.validar_caso(bruta(sexo="M", gestante=gestante)).gestante == 0


def test_campo_obrigatorio_ausente_e_recusado_e_os_erros_vem_todos_de_uma_vez():
    bruto = bruta(idade=-5, dias=99)
    del bruto["sexo"]
    bruto["diabetes"] = "talvez"
    with pytest.raises(entrada.EntradaInvalida) as erro:
        entrada.validar_caso(bruto)
    assert len(erro.value.erros) == 4
    assert any("Sexo: campo obrigatório ausente" in e for e in erro.value.erros)


def test_perfil_aceita_so_sim_ou_nao_nas_comorbidades_e_traduz_os_campos():
    dados = {"idade_anos": 60, "sexo": "F", "gestante": "nao",
             **{c: "nao" for c, _ in CONTRATO_COMORBIDADES}}
    perfil = entrada.validar_perfil({**dados, "renal_cronica": "sim", "diabetes": "sim"})
    assert perfil.comorbidades == ("DIABETES", "RENAL")  # na ordem do dicionário de features
    assert (perfil.idade_anos, perfil.sexo, perfil.gestante) == (60, "F", 0)
    with pytest.raises(entrada.EntradaInvalida):
        entrada.validar_perfil({**dados, "diabetes": "ignorado"})
    with pytest.raises(entrada.EntradaInvalida, match="só é possível com sexo F"):
        entrada.validar_perfil({**dados, "sexo": "M", "gestante": "sim"})
    with pytest.raises(entrada.EntradaInvalida):
        entrada.validar_perfil({**dados, "idade_anos": 121})
    with pytest.raises(entrada.EntradaInvalida):
        entrada.validar_perfil({**dados, "hipertensao": "talvez"})


def test_ano_de_desenvolvimento_e_lido_do_config_uma_vez(monkeypatch):
    entrada._ano_de_desenvolvimento.cache_clear()
    chamadas = []
    real = entrada.load_config
    monkeypatch.setattr(entrada, "load_config", lambda: chamadas.append(1) or real())
    caso = entrada.validar_caso(bruta())
    for _ in range(3):
        caso.para_frame()
    assert len(chamadas) == 1
    entrada._ano_de_desenvolvimento.cache_clear()
