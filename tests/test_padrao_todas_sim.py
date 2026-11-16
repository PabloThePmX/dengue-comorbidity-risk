"""Testes da investigação e da sensibilidade do padrão "todas as 7 comorbidades = Sim".

Dados sintéticos (nenhum microdado real, nada de `data/`). Os casos do padrão são forçados nas
primeiras linhas. Coberto: detecção do padrão, concentração com contas à mão, markdown sem célula
de 1 a 9 e sem código de unidade, e a equivalência exata entre excluir o grupo e um indicador por
padrão de covariáveis (saturado).
"""

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from test_explain import _cfg, _escrever_pares, _populacao_sintetica

from dengue_sinan import explain
from dengue_sinan.profiling import COMORBIDADES, FAIXAS, FAIXAS_ROTULOS

N = 8000
N_PADRAO = 300


def _df_com_padrao(n: int = N, n_padrao: int = N_PADRAO) -> pd.DataFrame:
    """População sintética com diagnóstico e as primeiras `n_padrao` linhas com as 7 = Sim."""
    rng = np.random.default_rng(7)
    df = _populacao_sintetica(n=n)
    df.loc[: n_padrao - 1, list(COMORBIDADES)] = "Sim"
    df["faixa_etaria"] = pd.cut(df["idade_anos"], FAIXAS, right=False, labels=FAIXAS_ROTULOS)
    df["n_comorbidades"] = sum((df[c] == "Sim").astype(np.int64) for c in COMORBIDADES)
    df["SG_UF_NOT"] = rng.choice(["SP", "RJ", "MG"], size=n)
    df["DT_NOTIFIC"] = rng.choice(["20220105", "20230310", "20221201"], size=n)
    df["ID_UNIDADE"] = rng.choice(["U1", "U2", "U3", "U4", "U5"], size=n).astype(object)
    df["ID_UNIDADE"] = df["ID_UNIDADE"].mask(rng.uniform(size=n) < 0.05)
    df["ID_MUNICIP"] = rng.choice(["M1", "M2"], size=n).astype(object)
    return df


def _n_padrao_real(df: pd.DataFrame) -> int:
    """Nº de linhas com as 7 = Sim (as forçadas mais as que o gerador já trouxe por acaso)."""
    return int((df[list(COMORBIDADES)] == "Sim").all(axis=1).sum())


def test_padrao_marca_so_os_casos_com_as_sete_sim():
    df = _df_com_padrao()
    marcado = explain.padrao_todas_sim(df)
    assert marcado.iloc[:N_PADRAO].all()
    assert int(marcado.sum()) == _n_padrao_real(df)
    assert int(marcado.sum()) >= N_PADRAO
    # Cada linha marcada tem as 7 comorbidades = Sim, e nenhuma outra linha tem.
    assert ((df.loc[marcado, list(COMORBIDADES)] == "Sim").all().all())
    assert (df.loc[~marcado, list(COMORBIDADES)] != "Sim").any(axis=1).all()


def test_concentracao_bate_a_conta_a_mao():
    # Padrão: 50, 30, 10, 5, 5 casos em 5 unidades (total 100).
    # Cumulativo: 0,5; 0,8; 0,9; 0,95; 1,0. N50 = 1; N90 = 3 (0,9 não é < 0,9).
    # HHI = 0,5² + 0,3² + 0,1² + 0,05² + 0,05² = 0,355. Geral igual, com 100 em cada unidade.
    tab = pd.DataFrame({"casos_padrao": [50, 30, 10, 5, 5],
                        "casos": [100, 100, 100, 100, 100]},
                       index=["a", "b", "c", "d", "e"])
    c = explain.concentracao(tab)
    assert c["padrao"]["n_50"] == 1
    assert c["padrao"]["n_90"] == 3
    assert c["padrao"]["top1"] == pytest.approx(0.5)
    assert c["padrao"]["hhi"] == pytest.approx(0.355)
    assert c["geral"]["n_50"] == 3  # 5 unidades iguais: 3 são necessárias para passar de 50%
    assert c["unidades_com_padrao"] == 5


def test_concentracao_nao_conta_sem_codigo():
    tab = pd.DataFrame({"casos_padrao": [10, 10, 0],
                        "casos": [10, 10, 500]},
                       index=["a", "b", explain.SEM_CODIGO])
    c = explain.concentracao(tab)
    assert c["padrao"]["n_50"] == 1
    assert c["unidades_com_casos"] == 2


def test_resumo_conta_o_padrao_e_nao_cita_codigo_no_markdown():
    df = _df_com_padrao()
    resumo = explain.resumo_padrao(df)
    assert resumo["escalares"]["casos_padrao"] == _n_padrao_real(df)
    texto = "\n".join(explain._md_investigacao(resumo, minimo=10))
    for codigo in ("U1", "U2", "M1", "M2"):
        assert codigo not in texto
    assert "associação, não causa" in texto


def test_markdown_nao_publica_celula_de_1_a_9():
    df = _df_com_padrao()
    # Uma UF com só 4 casos (todos do padrão): a célula tem que sair como "—", sem o número 4.
    df.loc[df.index[:4], "SG_UF_NOT"] = "AC"
    resumo = explain.resumo_padrao(df)
    texto = "\n".join(explain._md_investigacao(resumo, minimo=10))
    # Tabelas de casos. A seção de concentração conta unidades (não casos) e fica de fora.
    tabelas_de_casos = texto.split("## Concentração")[0]
    for linha in tabelas_de_casos.splitlines():
        if linha.startswith("|"):
            celulas = [c.strip() for c in linha.split("|")][2:]  # a 1ª é o rótulo, não contagem
            for valor in celulas:
                assert not (valor.isdigit() and 1 <= int(valor) <= 9), linha


# Varredura de prosa (R7): um inteiro de 1 a 9 em texto corrido só passa se estiver num rótulo
# que não é contagem de casos ou eventos (nº de comorbidades, pares, posições, casas decimais,
# referências D-/R/P/T). Tabelas são varridas célula a célula, acima.
_DIGITO_SOLTO = re.compile(r"(?<![\w.,/%+\-–])([1-9])(?![\w.,/%+\-–])")
_ROTULO = re.compile(
    r"(comorbidade|\bpar(es)?\b|casas?\b|posiç|grupo|nível|níveis|faixa|unidade|município|"
    r"termo|parâmetro|perfil|linha|sexo|combinaç|coluna|dobra|\b[RPTD]-?\d|FR-|= ?Sim|"
    r"ranking|dias?\b|interaç|IC 95|perfis?\b|razão|\bOR\b|RERI|1 a 9|\(\d+ perfis\))",
    re.IGNORECASE)


def contagens_1_a_9_em_prosa(texto: str) -> list[str]:
    """Linhas de prosa (fora das tabelas) com 1 a 9 que pode ser contagem de casos ou eventos."""
    suspeitas = []
    for linha in texto.splitlines():
        if linha.startswith("|"):
            continue
        for m in _DIGITO_SOLTO.finditer(linha):
            janela = linha[max(0, m.start() - 40): m.end() + 40]
            if not _ROTULO.search(janela):
                suspeitas.append(linha.strip())
                break
    return suspeitas


def test_prosa_nao_publica_contagem_de_1_a_9():
    df = _df_com_padrao()
    df.loc[explain.padrao_todas_sim(df), "y"] = 0
    df.loc[:2, "y"] = 1  # exatamente 3 eventos com o padrão: não pode sair em nenhum texto
    resumo = explain.resumo_padrao(df)
    texto = "\n".join(explain._md_investigacao(resumo, minimo=10))
    assert contagens_1_a_9_em_prosa(texto) == []
    assert "3 de" not in texto
    assert contagens_1_a_9_em_prosa("posições 2 e 3 do ranking; 1,00 de razão") == []
    assert contagens_1_a_9_em_prosa("Eventos com o padrão: 3 de 3985.") != []


def test_exclusao_remove_o_padrao_e_so_ele():
    df = _df_com_padrao()
    nos = {"idade": explain._nos(df["idade_anos"].to_numpy(dtype=float), explain.GL_IDADE),
           "idade_interacao": explain._nos(df["idade_anos"].to_numpy(dtype=float),
                                           explain.GL_IDADE_INTERACAO)}
    padrao = explain.padrao_todas_sim(df).to_numpy()
    incl, excl = explain._pares_de(df.loc[~padrao])
    a = explain._ajustar_sobre(df.loc[~padrao], nos, incl, excl)
    assert a.n_casos == len(df) - int(padrao.sum())


def test_indicador_por_padrao_equivale_a_excluir_o_grupo():
    # Cada padrão de covariáveis do grupo ganha o seu indicador: os demais coeficientes ficam
    # iguais aos da exclusão. Um indicador único não tem essa propriedade.
    # Termos em separação quase perfeita (|β| > 10, pouquíssimos eventos) não são identificados:
    # ficam fora da comparação e são listados. O teste exige < 1e-6 nos identificados.
    df = _df_com_padrao(n=6000, n_padrao=200)
    nos = {"idade": explain._nos(df["idade_anos"].to_numpy(dtype=float), explain.GL_IDADE),
           "idade_interacao": explain._nos(df["idade_anos"].to_numpy(dtype=float),
                                           explain.GL_IDADE_INTERACAO)}
    padrao = explain.padrao_todas_sim(df).to_numpy()
    incl, excl = explain._pares_de(df.loc[~padrao])
    a = explain._ajustar_sobre(df.loc[~padrao], nos, incl, excl)
    b = explain._ajustar_sobre(df, nos, incl, excl, dummy="saturado")
    beta_a = pd.Series(np.asarray(a.resultados.params, dtype=float), index=a.colunas)
    beta_b = pd.Series(np.asarray(b.resultados.params, dtype=float), index=b.colunas)
    identificados = beta_a[beta_a.abs() < 10].index
    assert np.max(np.abs(beta_a[identificados] - beta_b[identificados])) < 1e-6
    assert len(b.colunas) > len(a.colunas)


def test_dummy_desconhecido_e_recusado():
    df = _df_com_padrao(n=2000, n_padrao=50)
    nos = {"idade": explain._nos(df["idade_anos"].to_numpy(dtype=float), explain.GL_IDADE),
           "idade_interacao": explain._nos(df["idade_anos"].to_numpy(dtype=float),
                                           explain.GL_IDADE_INTERACAO)}
    with pytest.raises(ValueError):
        explain._ajustar_sobre(df, nos, [], [], dummy="outro")


def test_colunas_de_diagnostico_nao_repetem_as_da_populacao():
    # DT_NOTIFIC já vem da população: repeti-la no join falhou na 1ª execução real.
    from dengue_sinan import dataset

    assert not set(explain.COLUNAS_DIAGNOSTICO) & set(dataset.POPULATION_COLUMNS)


def test_perfil_com_as_sete_recebe_o_indicador_do_padrao():
    # No ajuste B, o desenho de um perfil tem o indicador = 1 só se ele tem as 7 comorbidades.
    # Sem isso, risco_perfil falhava para qualquer perfil novo (1ª execução real).
    df = _df_com_padrao(n=3000, n_padrao=100)
    nos = {"idade": explain._nos(df["idade_anos"].to_numpy(dtype=float), explain.GL_IDADE),
           "idade_interacao": explain._nos(df["idade_anos"].to_numpy(dtype=float),
                                           explain.GL_IDADE_INTERACAO)}
    incl, excl = explain._pares_de(df)
    b = explain._ajustar_sobre(df, nos, incl, excl, dummy="unico")
    coluna = explain.NOME_PADRAO_DUMMY
    x_sete = explain._vetor_perfil(b, 40, "F", 0, COMORBIDADES)
    x_nenhuma = explain._vetor_perfil(b, 40, "F", 0, ())
    assert x_sete[b.colunas.index(coluna)] == 1.0
    assert x_nenhuma[b.colunas.index(coluna)] == 0.0
    assert explain.risco_perfil(b, 40, "F", 0, COMORBIDADES)["risco"] > 0


# --- Cenário A salvo, relatórios e nota (T-3.5 / T-3.2) ----------------------------------------
# Os ajustes de sensibilidade são salvos sem nomes de coluna (`remove_data`). Estes testes
# gravam um conjunto completo sobre dados sintéticos e conferem que a leitura o reconstrói igual
# ao ajuste em memória, sem recarregar os dados reais.

@pytest.fixture(scope="module")
def cenarios(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("sens_salvo")
    cfg = _cfg(tmp)
    df = _df_com_padrao(n=6000, n_padrao=200)
    _escrever_pares(cfg, df)
    principal = explain.ajustar_e1(cfg, df)
    explain.salvar_e1(cfg, principal)
    padrao = explain.padrao_todas_sim(df).to_numpy()
    incl, excl = explain._pares_de(df.loc[~padrao])
    a = explain._ajustar_sobre(df.loc[~padrao], principal.nos, incl, excl)
    b = explain._ajustar_sobre(df, principal.nos, principal.pares_incluidos,
                               principal.pares_excluidos, dummy="unico")
    s = explain._ajustar_sobre(df, principal.nos, incl, excl, dummy="saturado")
    pasta = explain._pasta_e1(cfg) / "sens"
    pasta.mkdir(parents=True, exist_ok=True)
    a.resultados.save(pasta / "A.pickle", remove_data=True)
    b.resultados.save(pasta / "B.pickle", remove_data=True)
    s.resultados.save(pasta / "B_saturado.pickle", remove_data=True)
    descritiva = Path(cfg["caminhos"]["dados"]) / "descritiva"
    descritiva.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([("DIABETES + HEMATOLOG + RENAL", 3, 50, 1)],
                 columns=["combinacao", "n_comorbidades", "casos", "eventos"]).to_csv(
        descritiva / "combinacoes_3_ou_mais.csv", index=False)
    qualidade = explain._pasta_qualidade(cfg)
    qualidade.mkdir(parents=True, exist_ok=True)
    escalares = {"casos_padrao": int(padrao.sum()),
                 "eventos_padrao": int(df.loc[padrao, "y"].sum())}
    (qualidade / "padrao_resumo.json").write_text(json.dumps({"escalares": escalares}),
                                                  encoding="utf-8")
    return {"cfg": cfg, "principal": principal, "A": a, "B": b, "S": s, "incl": incl}


def test_ajustes_salvos_reconstroem_o_cenario_A_do_ajuste_em_memoria(cenarios):
    salvos = explain._ajustes_salvos(cenarios["cfg"])
    a, s = cenarios["A"], cenarios["S"]
    assert set(salvos["A"].pares_incluidos) == set(cenarios["incl"])
    assert salvos["A"].colunas == a.colunas
    assert salvos["A"].n_casos == a.n_casos
    assert np.allclose(np.asarray(salvos["A"].resultados.params, dtype=float),
                       np.asarray(a.resultados.params, dtype=float))
    assert len(salvos["B_saturado"].colunas) == len(s.colunas)
    assert len(salvos["B"].colunas) == len(cenarios["principal"].colunas) + 1


def test_pares_sensiveis_sao_os_que_saem_no_cenario_A(cenarios):
    principal = cenarios["principal"]
    esperado = [p for p in principal.pares_incluidos if p not in cenarios["incl"]]
    assert explain.contexto_padrao(cenarios["cfg"])["pares_sensiveis"] == esperado


def test_relatorio_de_sensibilidade_marca_A_como_oficial_e_nao_iguala_B(cenarios):
    cfg = cenarios["cfg"]
    salvos = explain._ajustes_salvos(cfg)
    saida = explain.escrever_sensibilidade(
        cfg, {k: salvos[k] for k in ("principal", "A", "B")}, salvos["B_saturado"])
    texto = saida["publico"].read_text(encoding="utf-8")
    assert "**Sensibilidade oficial: o cenário A**" in texto
    assert "**B não equivale a excluir os casos.**" in texto
    assert "Não confirmado com estes dados" in texto
    assert "A decisão de excluir ou não" not in texto
    assert "hipótese de que o padrão explica o OR protetor" in texto
    assert "A leitura é circunstancial; a causa do padrão não foi provada." in texto
    assert "0.061" not in texto and "0.483" not in texto  # decimal com vírgula (R7 e pt-BR)
    assert contagens_1_a_9_em_prosa(texto) == []
    assert explain.AVISO_P6 in texto


def test_nota_do_padrao_cita_os_pares_o_proporcao_e_a_troca_de_posicoes():
    ctx = {
        "casos_padrao": 2000, "casos": 2453208,
        "pares_sensiveis": [("HEMATOLOG", "HEPATOPAT"), ("HEMATOLOG", "RENAL")],
        "ranking_principal": ["HEMATOLOG", "RENAL", "AUTO_IMUNE", "HEPATOPAT", "DIABETES",
                              "HIPERTENSA", "ACIDO_PEPT"],
        "ranking_a": ["HEMATOLOG", "AUTO_IMUNE", "RENAL", "HEPATOPAT", "DIABETES", "HIPERTENSA",
                      "ACIDO_PEPT"],
    }
    (nota,) = explain.nota_padrao(ctx)
    assert "2.000 casos (0,08% da população" in nota
    assert "HEMATOLOG × HEPATOPAT e HEMATOLOG × RENAL só têm 10 ou mais eventos" in nota
    assert "posições 2 e 3: passa a ser AUTO_IMUNE e RENAL (no principal, RENAL e AUTO_IMUNE)" \
        in nota
    assert "sensibilidade_padrao_todas_sim.md" in nota


def test_nota_do_padrao_sem_pares_nem_troca_no_ranking():
    ctx = {"casos_padrao": 2000, "casos": 2453208, "pares_sensiveis": [],
           "ranking_principal": ["HEMATOLOG", "RENAL"], "ranking_a": ["HEMATOLOG", "RENAL"]}
    (nota,) = explain.nota_padrao(ctx)
    assert "Nenhum par do E1 depende do padrão." in nota
    assert "o ranking não muda" in nota


def test_nota_com_um_so_par_usa_o_singular():
    ctx = {"casos_padrao": 2000, "casos": 2453208, "pares_sensiveis": [("HEMATOLOG", "RENAL")],
           "ranking_principal": ["A", "B"], "ranking_a": ["A", "B"]}
    (nota,) = explain.nota_padrao(ctx)
    assert "O par HEMATOLOG × RENAL só tem 10 ou mais eventos" in nota
    assert "sai do E1" in nota


def test_tabelas_de_categoria_nao_tem_uma_unica_celula_suprimida():
    # Cada tabela de categoria soma os 2.000 casos do padrão (publicados no total). Uma célula
    # suprimida sozinha sairia por subtração; a regra exige 0 ou pelo menos 2 suprimidas.
    df = _df_com_padrao()
    resumo = explain.resumo_padrao(df)
    texto = "\n".join(explain._md_investigacao(resumo, minimo=10))
    for tabela in texto.split("\n\n"):
        linhas = [ln for ln in tabela.splitlines() if ln.startswith("|")]
        if len(linhas) < 3 or "Casos com o padrão" not in linhas[0]:
            continue
        suprimidas = sum(ln.split("|")[3].strip() == "—" for ln in linhas[2:])
        assert suprimidas != 1, tabela
