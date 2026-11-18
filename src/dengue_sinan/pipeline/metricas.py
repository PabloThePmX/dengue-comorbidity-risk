"""Métricas de discriminação e erro a partir de contagens por conglomerado e nível de escore.

Em vez de recalcular curvas sobre milhões de linhas em cada réplica do bootstrap, as predições
são tabuladas: para cada modelo, N[c, u] e E[c, u] contam linhas e eventos do conglomerado `c`
com o u-ésimo valor distinto de probabilidade. Reamostrar conglomerados vira multiplicar essas
contagens por pesos inteiros, e as métricas saem das contagens somadas:

* PR-AUC = average precision (mesma definição de `sklearn.metrics.average_precision_score`,
  com empates tratados como um único limiar);
* ROC-AUC com empates contados como 1/2 (mesma de `roc_auc_score`);
* Brier = média de (p − y)².

Os testes comparam estas funções com o scikit-learn.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import sparse

from dengue_sinan.folds import ORDEM_REGIOES

METRICAS = ("prevalencia", "pr_auc", "razao_pr_auc_prevalencia", "roc_auc", "brier", "bss")


def metricas_de_contagens(n, e, p_u) -> dict[str, np.ndarray]:
    """Métricas para contagens `n` (linhas) e `e` (eventos) por nível `p_u` (crescente).

    Aceita vetor (U,) ou matriz (B, U), uma réplica por linha. Devolve NaN quando faltar uma das
    classes (a métrica não existe nessa réplica).
    """
    n = np.atleast_2d(np.asarray(n, dtype="float64"))
    e = np.atleast_2d(np.asarray(e, dtype="float64"))
    p_u = np.asarray(p_u, dtype="float64")
    total, pos = n.sum(1), e.sum(1)
    neg = n - e
    neg_tot = neg.sum(1)
    ok = (pos > 0) & (neg_tot > 0)
    with np.errstate(divide="ignore", invalid="ignore"):
        prev = np.where(total > 0, pos / total, np.nan)
        abaixo = np.cumsum(neg, axis=1) - neg
        roc = (e * (abaixo + 0.5 * neg)).sum(1) / (pos * neg_tot)
        e_d, n_d = e[:, ::-1], n[:, ::-1]
        cum_e, cum_n = np.cumsum(e_d, axis=1), np.cumsum(n_d, axis=1)
        precisao = np.where(cum_n > 0, cum_e / cum_n, 0.0)
        pr = (e_d * precisao).sum(1) / pos
        brier = (e * (1 - p_u) ** 2 + neg * p_u**2).sum(1) / total
    return {
        "prevalencia": prev,
        "pr_auc": np.where(ok, pr, np.nan),
        "roc_auc": np.where(ok, roc, np.nan),
        "brier": np.where(total > 0, brier, np.nan),
        "razao_pr_auc_prevalencia": np.where(ok, pr / prev, np.nan),
        "n": total,
        "eventos": pos,
    }


@dataclass
class TabelaNiveis:
    """Contagens por conglomerado × nível de escore, para todos os modelos."""

    regioes: list[str]
    conglomerados: np.ndarray  # rótulo de cada conglomerado (só em memória)
    indice_regiao: dict[str, np.ndarray]  # posições dos conglomerados de cada região
    niveis: dict[str, np.ndarray] = field(default_factory=dict)
    N: dict[str, sparse.csr_matrix] = field(default_factory=dict)
    E: dict[str, sparse.csr_matrix] = field(default_factory=dict)
    linhas_por_regiao: dict[str, int] = field(default_factory=dict)
    eventos_por_regiao: dict[str, int] = field(default_factory=dict)


def montar_tabela(oof: pd.DataFrame, modelos: list[str]) -> TabelaNiveis:
    """Tabula a OOF. Cada conglomerado deve pertencer a uma única região."""
    cod, rotulos = pd.factorize(oof["conglomerado"].astype("string"))
    regioes_de = oof.groupby(cod)["regiao"].nunique()
    if (regioes_de > 1).any():
        raise ValueError("um conglomerado aparece em mais de uma região")
    reg_por_cluster = oof.groupby(cod)["regiao"].first().to_numpy()
    regioes = [r for r in ORDEM_REGIOES if r in set(oof["regiao"])]
    t = TabelaNiveis(
        regioes=regioes,
        conglomerados=np.asarray(rotulos),
        indice_regiao={r: np.flatnonzero(reg_por_cluster == r) for r in regioes},
    )
    y = oof["y"].to_numpy()
    for r in regioes:
        m = (oof["regiao"] == r).to_numpy()
        t.linhas_por_regiao[r], t.eventos_por_regiao[r] = int(m.sum()), int(y[m].sum())
    forma = (len(rotulos), 0)
    for modelo in modelos:
        u, inv = np.unique(oof[f"p_{modelo}"].to_numpy(dtype="float64"), return_inverse=True)
        forma = (len(rotulos), len(u))
        um = np.ones(len(inv))
        t.niveis[modelo] = u
        t.N[modelo] = sparse.coo_matrix((um, (cod, inv)), shape=forma).tocsr()
        t.E[modelo] = sparse.coo_matrix((y.astype(float), (cod, inv)), shape=forma).tocsr()
    return t


def contagens_ponderadas(t: TabelaNiveis, modelo: str, regiao: str, pesos=None):
    """(n, e) por nível para uma região. `pesos` (B, C) = multiplicidade de cada conglomerado."""
    idx = t.indice_regiao[regiao]
    N, E = t.N[modelo][idx], t.E[modelo][idx]
    if pesos is None:
        return np.asarray(N.sum(0)), np.asarray(E.sum(0))
    w = pesos[:, idx]
    return np.asarray((N.T @ w.T).T), np.asarray((E.T @ w.T).T)


def metricas_todas(t: TabelaNiveis, modelos: list[str], pesos=None) -> dict:
    """{(modelo, escopo): {métrica: vetor}} para escopo = região, 'global' ou 'media_das_dobras'.

    Sem `pesos`, é a estimativa pontual (uma réplica). Com `pesos` (B, C), uma réplica por linha.
    O BSS compara com o B0 da mesma réplica e do mesmo escopo.
    """
    por_regiao = {}
    for modelo in modelos:
        for r in t.regioes:
            n, e = contagens_ponderadas(t, modelo, r, pesos)
            por_regiao[(modelo, r)] = (n, e)
    saida = {}
    for modelo in modelos:
        for r in t.regioes:
            n, e = por_regiao[(modelo, r)]
            saida[(modelo, r)] = metricas_de_contagens(n, e, t.niveis[modelo])
        # global: níveis são os mesmos entre regiões (tabulação conjunta), basta somar
        n_g = sum(por_regiao[(modelo, r)][0] for r in t.regioes)
        e_g = sum(por_regiao[(modelo, r)][1] for r in t.regioes)
        saida[(modelo, "global")] = metricas_de_contagens(n_g, e_g, t.niveis[modelo])
    if "b0" in modelos:
        for chave, m in saida.items():
            b0 = saida[("b0", chave[1])]["brier"]
            m["bss"] = 1.0 - m["brier"] / b0
    else:
        for m in saida.values():
            m["bss"] = np.full_like(m["brier"], np.nan)
    for modelo in modelos:  # média das métricas das dobras (cada dobra = uma região)
        dobras = [saida[(modelo, r)] for r in t.regioes]
        saida[(modelo, "media_das_dobras")] = {
            k: np.mean([d[k] for d in dobras], axis=0) for k in METRICAS
        } | {"n": sum(d["n"] for d in dobras), "eventos": sum(d["eventos"] for d in dobras)}
    return saida
