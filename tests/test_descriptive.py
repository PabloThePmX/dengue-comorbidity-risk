"""Testes da análise descritiva (T-2.6): só dados sintéticos calculados à mão (nenhum microdado)."""

import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from populacao_sintetica import cfg_sintetico, dados_sinteticos

from dengue_sinan import descriptive as d
from dengue_sinan.profiling import COMORBIDADES, FAIXAS_ROTULOS

A, B, C, D = "DIABETES", "HIPERTENSA", "RENAL", "HEMATOLOG"


def _nome(*comorbidades: str) -> str:
    """Nome de combinação na ordem de COMORBIDADES, como `combination_counts` escreve."""
    return " + ".join(c for c in COMORBIDADES if c in comorbidades)


def _caso(y: int, sim=(), ausente=(), faixa="15–39") -> dict:
    return {"y": y, "sim": tuple(sim), "ausente": tuple(ausente), "faixa": faixa}


def _df(casos: list[dict]) -> pd.DataFrame:
    """Linhas no formato de `carregar_desenvolvimento`, só com as colunas que a análise usa."""
    linhas = []
    for caso in casos:
        linha = {c: "Não" for c in COMORBIDADES}
        linha.update({c: "Sim" for c in caso["sim"]})
        linha.update({c: "Ausente" for c in caso["ausente"]})
        n = len(caso["sim"])
        linha.update({
            "y": caso["y"],
            "faixa_etaria": caso["faixa"],
            "ncomorb_grupo": ["0", "1", "2", "3 ou mais"][min(n, 3)],
            "n_comorbidades": n,
            "sexo": "F",
            "gestante_rotulo": "Não",
            "raca": "Parda",
            "idade_anos": 30.0,
        })
        linhas.append(linha)
    df = pd.DataFrame(linhas)
    df["faixa_etaria"] = pd.Categorical(df["faixa_etaria"], categories=FAIXAS_ROTULOS)
    return df


# --- IC de Wilson ----------------------------------------------------------------------------

def test_wilson_5_de_10_bate_com_valor_conhecido():
    inf, sup = d.wilson_ci(5, 10)
    assert inf == pytest.approx(0.237, abs=5e-4)
    assert sup == pytest.approx(0.763, abs=5e-4)


def test_wilson_0_de_10_tem_limite_inferior_zero_e_superior_z2_sobre_n_mais_z2():
    inf, sup = d.wilson_ci(0, 10)
    assert inf == 0.0
    assert sup == pytest.approx(3.8415 / 13.8415, abs=1e-4)  # ≈ 0,2775


def test_wilson_10_de_10_simetrico_ao_caso_0_de_10():
    inf, sup = d.wilson_ci(10, 10)
    assert sup == 1.0
    assert inf == pytest.approx(1 - 3.8415 / 13.8415, abs=1e-4)  # ≈ 0,7225


def test_wilson_sem_casos_devolve_nan():
    inf, sup = d.wilson_ci(0, 0)
    assert np.isnan(inf) and np.isnan(sup)


@pytest.mark.parametrize("k", range(0, 11))
def test_wilson_sempre_contem_a_proporcao_e_fica_em_0_1(k):
    inf, sup = d.wilson_ci(k, 10)
    assert 0.0 <= inf <= k / 10 <= sup <= 1.0


# --- Supressão (R7) ---------------------------------------------------------------------------

def test_supressao_suprime_celula_pequena_e_a_menor_das_outras_do_bloco():
    # 3 < 10 é suprimida; sem a complementar, o total publicado daria o 3 de volta.
    assert d._suprimidas([3, 50, 40], 10) == [True, False, True]


def test_supressao_com_duas_celulas_pequenas_nao_precisa_de_complementar():
    assert d._suprimidas([3, 4, 50], 10) == [True, True, False]


def test_supressao_zero_nao_conta_como_celula_suprimida_sem_outra_pequena():
    assert d._suprimidas([0, 50, 40], 10) == [False, False, False]


def test_formatar_riscos_nao_publica_contagem_pequena_nem_risco_derivado():
    tab = pd.DataFrame([
        {"bloco": "X", "nivel": "a", "casos": 5, "eventos": 1, "risco": 0.2,
         "ic_inf": 0.1, "ic_sup": 0.4},
        {"bloco": "X", "nivel": "b", "casos": 100, "eventos": 3, "risco": 0.03,
         "ic_inf": 0.01, "ic_sup": 0.09},
        {"bloco": "X", "nivel": "c", "casos": 200, "eventos": 40, "risco": 0.2,
         "ic_inf": 0.15, "ic_sup": 0.26},
    ])
    out = d.formatar_riscos(tab, 10).set_index("Nível")
    assert out.loc["a", "Casos"] == "—" and out.loc["a", "Risco bruto"] == "—"
    # b (100 casos) cai na supressão complementar: nada dele é publicado.
    assert out.loc["b", "Casos"] == "—" and out.loc["b", "Eventos"] == "—"
    assert out.loc["b", "IC 95% (Wilson)"] == "—"
    assert out.loc["c", "Casos"] == "200" and out.loc["c", "Eventos"] == "40"
    assert out.loc["c", "Risco bruto"] == "20,000%"


# --- Pares (21, contagem exata) ---------------------------------------------------------------

def test_pares_sao_21_e_contagem_bate_com_calculo_a_mao():
    df = _df([
        _caso(1, sim=(A, B)),        # par A-B: caso e evento
        _caso(0, sim=(A, B, C)),     # A-B, A-C e B-C: caso sem evento
        _caso(0, sim=(C,)),          # nenhum par
    ])
    pares = d.pair_event_counts(df).set_index(["comorbidade_1", "comorbidade_2"])
    assert len(pares) == 21
    assert pares.loc[(A, B), ["casos", "eventos"]].tolist() == [2, 1]
    assert pares.loc[(A, C), ["casos", "eventos"]].tolist() == [1, 0]
    # RENAL vem antes de HIPERTENSA em COMORBIDADES, então o par é guardado como (RENAL, HIPERT.)
    assert pares.loc[(C, B), ["casos", "eventos"]].tolist() == [1, 0]
    assert pares.loc[(A, D), ["casos", "eventos"]].tolist() == [0, 0]


def test_formatar_pares_marca_os_que_entram_no_e1():
    pares = pd.DataFrame([
        {"comorbidade_1": A, "comorbidade_2": B, "casos": 50, "eventos": 12},
        {"comorbidade_1": A, "comorbidade_2": C, "casos": 40, "eventos": 3},
        {"comorbidade_1": B, "comorbidade_2": C, "casos": 4, "eventos": 0},
    ])
    out = d.formatar_pares(pares, 10)
    assert out["Entra no E1 (≥ 10 eventos)"].tolist() == ["Sim", "Não", "Não"]
    assert out["Eventos"].tolist() == ["12", "<10", "0"]
    assert out["Casos"].tolist() == ["50", "40", "<10"]


# --- Combinações exatas de 3 ou mais -----------------------------------------------------------

def test_combinacoes_contam_a_combinacao_exata_e_nao_as_que_a_contem():
    df = _df([
        _caso(1, sim=(A, B, C)),                 # exatamente {A,B,C}
        _caso(0, sim=(A, B, C)),                 # exatamente {A,B,C}
        _caso(0, sim=(A, B, C), ausente=(D,)),   # Ausente não é Sim: ainda {A,B,C}
        _caso(0, sim=(A, B, C, D)),              # {A,B,C,D}: não conta em {A,B,C}
        _caso(1, sim=(A, B)),                    # 2 comorbidades: fora
    ])
    comb = d.combination_counts(df).set_index("combinacao")
    abc, abcd = _nome(A, B, C), _nome(A, B, C, D)
    assert list(comb.index) == [abc, abcd]
    assert comb.loc[abc, ["casos", "eventos", "n_comorbidades"]].tolist() == [3, 1, 3]
    assert comb.loc[abcd, ["casos", "eventos"]].tolist() == [1, 0]


# --- Riscos brutos -----------------------------------------------------------------------------

def test_tabela_riscos_conta_casos_eventos_e_risco_de_wilson():
    df = _df([
        _caso(1, sim=(A,)),
        _caso(0, sim=(A,)),
        _caso(0, sim=(A,)),
        _caso(0),
    ])
    tab = d.tabela_riscos(df).set_index(["bloco", "nivel"])
    linha = tab.loc[(A, "Sim")]
    assert (linha["casos"], linha["eventos"]) == (3, 1)
    assert linha["risco"] == pytest.approx(1 / 3)
    assert linha["ic_inf"] == pytest.approx(d.wilson_ci(1, 3)[0])
    assert tab.loc[("Nº de comorbidades", "0"), "casos"] == 1


# --- Integração: gerar() com dados sintéticos -------------------------------------------------

def test_carregar_recusa_2024_antes_de_ler_arquivo(tmp_path):
    cfg = dict(cfg_sintetico(tmp_path), anos_dev=[2022, 2024])
    with pytest.raises(RuntimeError, match="2024 é teste congelado"):
        d.carregar_desenvolvimento(cfg)


def test_gerar_publica_arquivos_sem_numeros_pequenos_e_guarda_contagens_fora_de_reports(tmp_path):
    cfg = dados_sinteticos(cfg_sintetico(tmp_path))  # 5 casos: tudo fica abaixo de 10
    resumo = d.gerar(cfg)

    pasta = Path(cfg["caminhos"]["relatorios"]) / "descritiva"
    for nome in ("tabela1.md", "riscos_brutos.md", "pares_comorbidades.md",
                 "riscos_comorbidades.png", "riscos_n_comorbidades.png",
                 "riscos_faixa_etaria.png"):
        assert (pasta / nome).exists(), nome
    assert (pasta / "riscos_comorbidades.png").read_bytes()[:4] == b"\x89PNG"
    riscos_md = (pasta / "riscos_brutos.md").read_text(encoding="utf-8")
    assert riscos_md.startswith("# Riscos brutos de y = 1 (descritivos)")
    assert "riscos brutos, descritivos; não substituem o E1" in riscos_md  # no topo
    assert "Não ou ausente" in riscos_md and "Exibição" in riscos_md
    assert "supressão complementar não impede dedução" in riscos_md  # fallback documentado
    tabela_md = (pasta / "tabela1.md").read_text(encoding="utf-8")
    linhas_tabela = [ln for ln in tabela_md.splitlines() if ln.startswith("|")]
    assert any("Não ou ausente" in ln for ln in linhas_tabela)
    assert not any("| Ausente |" in ln for ln in linhas_tabela)

    interno = Path(cfg["caminhos"]["dados"]) / "descritiva"
    assert (interno / "pares_comorbidades.csv").exists()
    assert (interno / "combinacoes_3_ou_mais.csv").exists()
    assert not list(Path(cfg["caminhos"]["relatorios"]).rglob("*.csv"))  # nada interno em reports/

    assert resumo["casos_total"] == 5
    assert resumo["pares_com_10_eventos"] == 0
    assert resumo["combinacoes_3_ou_mais_com_10_casos"] == 0


def test_formatos_publicados_nunca_mostram_contagem_de_1_a_9():
    df = _df([_caso(1, sim=(A,)), *[_caso(0, sim=(A,)) for _ in range(20)],
              *[_caso(0) for _ in range(3)]])
    minimo = 10
    riscos = d.formatar_riscos(d.agrupar_riscos(d.tabela_riscos(df)), minimo)
    pares = d.formatar_pares(d.pair_event_counts(df), minimo)
    tabela = d.formatar_tabela1(
        d.agrupar_caracteristicas(d.tabela_caracteristicas(df)), d.resumo_idade(df), minimo)

    def pequeno(valor: str) -> bool:
        return re.fullmatch(r"[1-9]\d?( \(.*)?", valor) is not None and int(
            re.match(r"\d+", valor).group()) < minimo

    for coluna in ("Casos", "Eventos"):
        assert not [v for v in riscos[coluna] if pequeno(v)]
        assert not [v for v in pares[coluna] if pequeno(v)]
    for coluna in tabela.columns[2:]:
        assert not [v for v in tabela[coluna] if pequeno(v)], coluna


# --- Fusão só para exibição (decisão do Programador) --------------------------------------------

def test_agrupar_riscos_funde_nao_e_ausente_e_mantem_o_sim_inalterado():
    df = _df([
        *[_caso(1, sim=(A,)) for _ in range(12)],   # Sim: 20 casos, 12 eventos
        *[_caso(0, sim=(A,)) for _ in range(8)],
        *[_caso(1) for _ in range(30)],             # Não: 30 eventos
        *[_caso(0, ausente=(A,)) for _ in range(4)],  # Ausente: 4 casos, sem eventos
        *[_caso(1, ausente=(A,))],                  # Ausente com 1 evento
    ])
    bruto = d.tabela_riscos(df).set_index(["bloco", "nivel"])
    exibido = d.agrupar_riscos(d.tabela_riscos(df)).set_index(["bloco", "nivel"])
    assert ("DIABETES", "Ausente") not in exibido.index
    sim = exibido.loc[("DIABETES", "Sim")]
    assert (sim["casos"], sim["eventos"]) == (bruto.loc[("DIABETES", "Sim"), "casos"],
                                              bruto.loc[("DIABETES", "Sim"), "eventos"])
    fundido = exibido.loc[("DIABETES", d.ROTULO_NAO_OU_AUSENTE)]
    # Não (30 eventos + 0 casos) e Ausente (5 casos, 1 evento) somam 35 casos e 31 eventos.
    assert (fundido["casos"], fundido["eventos"]) == (
        bruto.loc[("DIABETES", "Não"), "casos"] + bruto.loc[("DIABETES", "Ausente"), "casos"],
        bruto.loc[("DIABETES", "Não"), "eventos"] + bruto.loc[("DIABETES", "Ausente"), "eventos"])
    assert fundido["risco"] == pytest.approx(fundido["eventos"] / fundido["casos"])
    assert fundido["ic_inf"] == pytest.approx(d.wilson_ci(31, 35)[0])


def test_sim_de_comorbidade_com_10_eventos_nao_some_na_exibicao():
    df = _df([
        *[_caso(1, sim=(A,)) for _ in range(12)],  # Sim com 12 eventos
        *[_caso(0, sim=(A,)) for _ in range(8)],
        *[_caso(1) for _ in range(40)],            # Não ou ausente com muitos eventos
    ])
    exibido = d.formatar_riscos(d.agrupar_riscos(d.tabela_riscos(df)), 10)
    riscos = exibido.set_index(["Grupo", "Nível"])
    sim = riscos.loc[("DIABETES", "Sim")]
    assert sim["Eventos"] == "12"
    assert sim["Casos"] == "20"
    assert sim["Risco bruto"] == "60,000%"
    assert sim["IC 95% (Wilson)"] != "—"


def test_fusao_de_amarela_e_indigena_em_raca_cor():
    caracteristicas = pd.DataFrame([
        {"variavel": "Raça/cor", "categoria": "Amarela", "y": 1, "n": 6, "total": 100},
        {"variavel": "Raça/cor", "categoria": "Indígena", "y": 1, "n": 5, "total": 100},
        {"variavel": "Raça/cor", "categoria": "Parda", "y": 1, "n": 80, "total": 100},
        {"variavel": "Raça/cor", "categoria": "Amarela", "y": 0, "n": 7, "total": 200},
        {"variavel": "Raça/cor", "categoria": "Indígena", "y": 0, "n": 3, "total": 200},
    ])
    out = d.agrupar_caracteristicas(caracteristicas)
    amarela = out[out["categoria"] == d.ROTULO_AMARELA_OU_INDIGENA].set_index("y")
    assert amarela.loc[1, "n"] == 11 and amarela.loc[0, "n"] == 10
    assert amarela.loc[1, "total"] == 100  # total do desfecho não muda com a fusão
    assert "Indígena" not in set(out["categoria"])


def test_fusao_de_nao_e_ausente_em_caracteristicas_de_comorbidade():
    caracteristicas = pd.DataFrame([
        {"variavel": "DIABETES", "categoria": "Sim", "y": 1, "n": 12, "total": 40},
        {"variavel": "DIABETES", "categoria": "Não", "y": 1, "n": 27, "total": 40},
        {"variavel": "DIABETES", "categoria": "Ausente", "y": 1, "n": 1, "total": 40},
    ])
    out = d.agrupar_caracteristicas(caracteristicas).set_index(["categoria", "y"])
    assert out.loc[("Sim", 1), "n"] == 12
    assert out.loc[(d.ROTULO_NAO_OU_AUSENTE, 1), "n"] == 28
    assert ("Ausente", 1) not in out.index


def test_nota_de_ausentes_suprime_1_a_9_e_mostra_eventos_zero():
    tab = pd.DataFrame([
        {"bloco": "DIABETES", "nivel": "Ausente", "casos": 240, "eventos": 0,
         "risco": 0.0, "ic_inf": 0.0, "ic_sup": 0.0},
        {"bloco": "RENAL", "nivel": "Ausente", "casos": 5, "eventos": 3,
         "risco": 0.6, "ic_inf": 0.1, "ic_sup": 0.9},
        {"bloco": "HIPERTENSA", "nivel": "Ausente", "casos": 300, "eventos": 4,
         "risco": 0.01, "ic_inf": 0.0, "ic_sup": 0.02},
    ])
    out = d.ausentes_por_comorbidade(tab, 10).set_index("Comorbidade")
    assert out.loc["DIABETES", "Casos com ausente"] == "240"
    assert out.loc["DIABETES", "Eventos com ausente"] == "0"
    assert out.loc["RENAL", "Casos com ausente"] == "—"
    assert out.loc["HIPERTENSA", "Eventos com ausente"] == "—"


def test_gerar_grava_contagem_de_pares_interna_com_todos_os_21(tmp_path):
    cfg = dados_sinteticos(cfg_sintetico(tmp_path))
    d.gerar(cfg)
    csv = Path(cfg["caminhos"]["dados"], "descritiva", "pares_comorbidades.csv")
    assert len(pd.read_csv(csv)) == 21
