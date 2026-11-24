"""Textos do modo Normal (D-96): funções puras de `app.linguagem`."""

import pytest

from app import linguagem, servico


@pytest.mark.parametrize(("fracao", "esperado"), [
    (0.0016, "cerca de 1 em 620"),       # 1/0,0016 = 625 -> dois algarismos significativos
    (0.001, "cerca de 1 em 1.000"),
    (0.0004, "cerca de 1 em 2.500"),
    (0.05, "cerca de 1 em 20"),
    (0.02, "cerca de 1 em 50"),
    (0.1, "cerca de 10 em cada 100"),
    (0.25, "cerca de 25 em cada 100"),
])
def test_um_em_arredonda_para_dois_algarismos_e_usa_pt_br(fracao, esperado):
    assert linguagem.um_em(fracao) == esperado


def test_um_em_sem_risco_nao_divide_por_zero():
    assert linguagem.um_em(0.0) == "praticamente nenhum caso"
    assert linguagem.um_em(-0.1) == "praticamente nenhum caso"


def test_frase_risco_nao_promete_nada_sobre_a_pessoa():
    frase = linguagem.frase_risco(0.002)
    assert "cerca de 1 em 500" in frase and "evolui" in frase


def test_frase_comparacao_nas_tres_situacoes():
    sem = linguagem.frase_comparacao(0.002, 0.002, 1.0, tem_comorbidade=False)
    assert "próprio perfil de comparação" in sem
    maior = linguagem.frase_comparacao(0.006, 0.002, 3.0, tem_comorbidade=True)
    assert "cerca de 1 em 500" in maior and "3,0 vezes maior" in maior
    igual = linguagem.frase_comparacao(0.002, 0.002, 1.05, tem_comorbidade=True)
    assert "pequena" in igual
    menor = linguagem.frase_comparacao(0.001, 0.002, 0.5, tem_comorbidade=True)
    assert "2,0 vezes menor" in menor and "acaso" in menor


def test_efeito_dos_fatores():
    assert linguagem.efeito(True) == "aumenta o risco neste caso"
    assert linguagem.efeito(False) == "diminui o risco neste caso"


def _painel(**kw) -> servico.PainelTeste:
    base = dict(casos=5_331_745, eventos=11_338, limiar=0.002155, fracao_alto_risco=0.1424,
                precisao=0.00975, recall=0.6528, precisao_b2=0.00529, recall_b2=0.6601,
                obs_esp_m1=1.30, obs_esp_e1=1.19, sc02_passou=False, sc02_dif_recall=-0.0072,
                sc02_dif_recall_ic=(-0.0151, 0.0005))
    base.update(kw)
    return servico.PainelTeste(**base)


def test_aviso_de_subestimativa_so_quando_o_teste_mostrou_isso():
    assert "subestimou o risco" in linguagem.aviso_subestimado(_painel())
    assert linguagem.aviso_subestimado(_painel(obs_esp_m1=0.9)) is None
    assert linguagem.aviso_subestimado(None) is None


def test_painel_em_palavras_traz_os_numeros_e_o_resultado_negativo():
    texto = "\n".join(linguagem.linhas_painel(_painel()))
    assert "5.331.745" in texto and "11.338" in texto
    assert "cerca de 14%" in texto and "cerca de 65%" in texto
    assert "cerca de 99% dos apontados não ficaram graves" in texto
    assert "subestimou o risco" in texto
    assert "não alcançou essa regra" in texto


def test_painel_em_palavras_nao_diz_que_falhou_se_o_criterio_passou():
    texto = "\n".join(linguagem.linhas_painel(_painel(sc02_passou=True)))
    assert "não alcançou essa regra" not in texto


@pytest.mark.parametrize("texto", [linguagem.COMO_LER, linguagem.NAO_E_CAUSA,
                                   linguagem.SEM_ESTIMATIVA, linguagem.EXPLICACAO_INDISPONIVEL])
def test_textos_fixos_sem_jargao(texto):
    for termo in ("OR ", "IC 95%", "log-odds", "SHAP", "recall", "limiar", "E1", "M1"):
        assert termo not in texto
