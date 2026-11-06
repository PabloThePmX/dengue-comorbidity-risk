"""Métricas de discriminação, calibração e utilidade clínica (spec §3.12), com bootstrap.

Estimativas pontuais são EXATAS (linha a linha). Os ICs bootstrap usam uma tabela agregada de
pontuações (células com contagens de eventos e não eventos): o bootstrap de uma tabela de contagens
é uma multinomial, equivalente a reamostrar as linhas, e custa uma fração do tempo com milhões de
linhas (5,3 mi em 2024). As pontuações são quantizadas em escala log10 (3 casas) só para formar as
células; ver `quantizar`.
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score


# ----------------------------------------------------------------------------- pontuais
def pr_auc(y, p) -> float:
    return float(average_precision_score(y, p))


def roc_auc(y, p) -> float:
    return float(roc_auc_score(y, p))


def brier(y, p) -> float:
    return float(brier_score_loss(y, p))


def _logit(p):
    p = np.clip(np.asarray(p, dtype="float64"), 1e-9, 1 - 1e-9)
    return np.log(p / (1 - p))


def calibracao_resumo(y, p, casas: int = 4) -> dict:
    """Slope e intercepto de calibração (Van Calster et al.), O:E e IC 95% de Wald.

    - slope: coeficiente de logit(p) numa logística y ~ logit(p) (ideal = 1);
    - intercepto de calibração (CITL): intercepto com slope fixado em 1, via offset (ideal = 0);
    - O:E: eventos observados / esperados (ideal = 1).
    Ajustado sobre células agregadas (equivalente à linha a linha, com resolução fina).
    """
    y = np.asarray(y)
    p = np.clip(np.asarray(p, dtype="float64"), 1e-9, 1 - 1e-9)
    chave = np.round(np.log10(p), casas)
    tab = pd.DataFrame({"s": chave, "y": y}).groupby("s")["y"].agg(["sum", "count"]).reset_index()
    lg = _logit(10 ** tab["s"].to_numpy())
    desfecho = np.column_stack([tab["sum"], tab["count"] - tab["sum"]])
    out = {}
    m1 = sm.GLM(desfecho, sm.add_constant(lg), family=sm.families.Binomial()).fit()
    out["slope"] = float(m1.params[1])
    out["slope_ic95"] = tuple(float(v) for v in m1.conf_int()[1])
    m0 = sm.GLM(desfecho, np.ones((len(lg), 1)), family=sm.families.Binomial(), offset=lg).fit()
    out["intercepto_citl"] = float(m0.params[0])
    out["intercepto_ic95"] = tuple(float(v) for v in m0.conf_int()[0])
    out["O:E"] = float(y.sum() / p.sum())
    return out


def _wilson(k, n, z: float = 1.96):
    k, n = np.asarray(k, dtype=float), np.asarray(n, dtype=float)
    ph = k / n
    den = 1 + z**2 / n
    centro = (ph + z**2 / (2 * n)) / den
    meia = z * np.sqrt(ph * (1 - ph) / n + z**2 / (4 * n**2)) / den
    return centro - meia, centro + meia


def curva_calibracao(y, p, n_bins: int = 10) -> pd.DataFrame:
    """Risco previsto médio × taxa observada (IC de Wilson) em decis de risco previsto."""
    d = pd.DataFrame({"y": np.asarray(y), "p": np.asarray(p, dtype="float64")})
    d["bin"] = pd.qcut(d["p"].rank(method="first"), n_bins, labels=False)
    g = d.groupby("bin").agg(p_medio=("p", "mean"), eventos=("y", "sum"), n=("y", "size"))
    g["taxa_observada"] = g["eventos"] / g["n"]
    g["ic95_inf"], g["ic95_sup"] = _wilson(g["eventos"], g["n"])
    return g.reset_index(drop=True)


def metricas_limiar(y, flag) -> dict:
    """Matriz de confusão e métricas no limiar (flag = classificado como alto risco)."""
    y, flag = np.asarray(y).astype(bool), np.asarray(flag).astype(bool)
    return _de_contagens(
        int((y & flag).sum()),
        int((~y & flag).sum()),
        int((y & ~flag).sum()),
        int((~y & ~flag).sum()),
    )


def _de_contagens(tp, fp, fn, tn) -> dict:
    n = tp + fp + fn + tn
    div = lambda a, b: float(a / b) if b else float("nan")  # noqa: E731
    sens, vpp = div(tp, tp + fn), div(tp, tp + fp)
    f1 = div(2 * vpp * sens, vpp + sens) if tp else 0.0
    f2 = div(5 * vpp * sens, 4 * vpp + sens) if tp else 0.0
    return {
        "TP": tp,
        "FP": fp,
        "FN": fn,
        "TN": tn,
        "sensibilidade": sens,
        "especificidade": div(tn, tn + fp),
        "VPP": vpp,
        "VPN": div(tn, tn + fn),
        "acuracia": div(tp + tn, n),
        "F1": f1,
        "F2": f2,
        "pct_sinalizados": div(tp + fp, n),
    }


def _curva_ordenada(y, p):
    """TP/FP acumulados em cada limiar distinto (empates juntos), do maior para o menor risco."""
    y = np.asarray(y).astype(np.int64)
    p = np.asarray(p, dtype="float64")
    ordem = np.argsort(-p, kind="stable")
    ps, ys = p[ordem], y[ordem]
    fins = np.r_[np.flatnonzero(np.diff(ps) != 0), len(ps) - 1]
    tp = np.cumsum(ys)[fins]
    fp = (fins + 1) - tp
    return ps[fins], tp, fp


def melhor_limiar_f2(y, p) -> tuple[float, dict]:
    """Limiar que maximiza o F2 (D-33), escolhido SÓ nas predições fora da dobra."""
    lim, tp, fp = _curva_ordenada(y, p)
    pos = int(np.asarray(y).sum())
    sens, vpp = tp / pos, tp / (tp + fp)
    f2 = np.where(tp > 0, 5 * vpp * sens / (4 * vpp + sens), 0.0)
    i = int(np.argmax(f2))
    flag = np.asarray(p) >= lim[i]
    return float(lim[i]), metricas_limiar(y, flag)


def limiar_para_sensibilidade(y, p, alvo: float) -> float:
    """Maior limiar cuja sensibilidade é ≥ alvo (para comparar com a regra do MS)."""
    lim, tp, _ = _curva_ordenada(y, p)
    ok = np.flatnonzero(tp / max(int(np.asarray(y).sum()), 1) >= alvo)
    return float(lim[ok[0]]) if len(ok) else float(lim[-1])


def limiar_para_fracao(y, p, fracao: float) -> float:
    """Menor limiar que sinaliza no máximo `fracao` das linhas."""
    lim, tp, fp = _curva_ordenada(y, p)
    sinal = (tp + fp) / len(np.asarray(y))
    ok = np.flatnonzero(sinal <= fracao)
    return float(lim[ok[-1]]) if len(ok) else float(lim[0]) + 1e-12


def curva_decisao(y, p=None, flag=None, limiares=None) -> pd.DataFrame:
    """Benefício líquido (net benefit) por limiar de risco. Passe `p` (modelo) ou `flag` (regra)."""
    y = np.asarray(y).astype(np.int64)
    n = len(y)
    limiares = np.asarray(limiares if limiares is not None else np.linspace(0.001, 0.05, 50))
    peso = limiares / (1 - limiares)
    if p is not None:
        ordem = np.argsort(-np.asarray(p, dtype="float64"), kind="stable")
        ps, cum = np.asarray(p, dtype="float64")[ordem], np.cumsum(y[ordem])
        k = np.searchsorted(-ps, -limiares, side="right")  # nº de linhas com p ≥ limiar
        tp = np.where(k > 0, cum[np.maximum(k - 1, 0)], 0)
        fp = k - tp
    else:
        flag = np.asarray(flag).astype(bool)
        tp = np.full(len(limiares), int((y.astype(bool) & flag).sum()))
        fp = np.full(len(limiares), int((~y.astype(bool) & flag).sum()))
    return pd.DataFrame({"limiar": limiares, "net_benefit": tp / n - fp / n * peso})


def net_benefit_todos(prevalencia: float, limiares) -> np.ndarray:
    limiares = np.asarray(limiares)
    return prevalencia - (1 - prevalencia) * limiares / (1 - limiares)


# ----------------------------------------------------------------------------- bootstrap
def quantizar(p, casas: int = 3) -> np.ndarray:
    """Quantiza probabilidades em escala log10 (resolução ≈ 0,2%) para formar células."""
    return 10 ** np.round(np.log10(np.clip(np.asarray(p, dtype="float64"), 1e-9, 1.0)), casas)


def agregar(
    y, scores: dict | None = None, flags: dict | None = None, casas: int = 3
) -> pd.DataFrame:
    """Tabela de células: uma coluna por pontuação (quantizada) e por flag, com `pos` e `neg`."""
    d = {f"s_{k}": quantizar(v, casas) for k, v in (scores or {}).items()}
    d.update({f"f_{k}": np.asarray(v).astype(bool) for k, v in (flags or {}).items()})
    chaves = list(d)
    d["y"] = np.asarray(y).astype(np.int64)
    tab = pd.DataFrame(d).groupby(chaves, observed=True)["y"].agg(pos="sum", n="size").reset_index()
    tab["neg"] = tab["n"] - tab["pos"]
    return tab.drop(columns="n")


def reamostrar(tab: pd.DataFrame, B: int, seed: int, lote: int = 25):
    """Gera lotes (pos_b, neg_b) de reamostras bootstrap estratificadas pelo alvo."""
    rng = np.random.default_rng(seed)
    pos, neg = tab["pos"].to_numpy(), tab["neg"].to_numpy()
    p_pos, p_neg = pos / pos.sum(), neg / neg.sum()
    feitos = 0
    while feitos < B:
        m = min(lote, B - feitos)
        yield (
            rng.multinomial(int(pos.sum()), p_pos, size=m),
            rng.multinomial(int(neg.sum()), p_neg, size=m),
        )
        feitos += m


def _ordem_e_fins(score: np.ndarray):
    ordem = np.argsort(-score, kind="stable")
    s = score[ordem]
    fins = np.r_[np.flatnonzero(np.diff(s) != 0), len(s) - 1]
    return ordem, fins


def _pr_roc_lote(pos_b, neg_b, ordem, fins):
    tp = np.cumsum(pos_b[:, ordem], axis=1)[:, fins].astype("float64")
    fp = np.cumsum(neg_b[:, ordem], axis=1)[:, fins].astype("float64")
    P, N = pos_b.sum(axis=1, keepdims=True), neg_b.sum(axis=1, keepdims=True)
    rec = tp / P
    prec = np.where(tp + fp > 0, tp / np.maximum(tp + fp, 1), 0.0)
    rec0 = np.concatenate([np.zeros((len(rec), 1)), rec[:, :-1]], axis=1)
    ap = ((rec - rec0) * prec).sum(axis=1)
    tpr = np.concatenate([np.zeros((len(rec), 1)), rec], axis=1)
    fpr = np.concatenate([np.zeros((len(rec), 1)), fp / N], axis=1)
    auc = (np.diff(fpr, axis=1) * (tpr[:, 1:] + tpr[:, :-1]) / 2).sum(axis=1)
    return ap, auc


def bootstrap_metricas(tab: pd.DataFrame, B: int = 1000, seed: int = 0, lote: int = 25) -> dict:
    """Distribuições bootstrap de PR-AUC, ROC-AUC, Brier (por `s_*`) e métricas por `f_*`.

    Todas as métricas usam as MESMAS reamostras, o que permite diferenças pareadas entre modelos
    (D-53): basta subtrair as distribuições.
    """
    scores = [c for c in tab.columns if c.startswith("s_")]
    flags = [c for c in tab.columns if c.startswith("f_")]
    pre = {c: _ordem_e_fins(tab[c].to_numpy()) for c in scores}
    out: dict[str, list] = {
        f"{m}[{c[2:]}]": [] for c in scores for m in ("pr_auc", "roc_auc", "brier")
    }
    for c in flags:
        for m in ("sensibilidade", "especificidade", "VPP", "VPN", "pct_sinalizados"):
            out[f"{m}[{c[2:]}]"] = []
    for pos_b, neg_b in reamostrar(tab, B, seed, lote):
        n_tot = (pos_b + neg_b).sum(axis=1)
        for c in scores:
            ap, auc = _pr_roc_lote(pos_b, neg_b, *pre[c])
            p = tab[c].to_numpy()
            br = (pos_b * (1 - p) ** 2 + neg_b * p**2).sum(axis=1) / n_tot
            out[f"pr_auc[{c[2:]}]"].append(ap)
            out[f"roc_auc[{c[2:]}]"].append(auc)
            out[f"brier[{c[2:]}]"].append(br)
        for c in flags:
            f = tab[c].to_numpy()
            tp, fp = pos_b[:, f].sum(axis=1), neg_b[:, f].sum(axis=1)
            fn, tn = pos_b[:, ~f].sum(axis=1), neg_b[:, ~f].sum(axis=1)
            with np.errstate(invalid="ignore", divide="ignore"):
                out[f"sensibilidade[{c[2:]}]"].append(tp / (tp + fn))
                out[f"especificidade[{c[2:]}]"].append(tn / (tn + fp))
                out[f"VPP[{c[2:]}]"].append(tp / (tp + fp))
                out[f"VPN[{c[2:]}]"].append(tn / (tn + fn))
                out[f"pct_sinalizados[{c[2:]}]"].append((tp + fp) / n_tot)
    return {k: np.concatenate(v) for k, v in out.items()}


def ic95(amostras, nivel: float = 0.95) -> tuple[float, float]:
    a = np.asarray(amostras, dtype="float64")
    a = a[~np.isnan(a)]
    return float(np.quantile(a, (1 - nivel) / 2)), float(np.quantile(a, 1 - (1 - nivel) / 2))


def resumo_com_ic(pontual: float, amostras) -> dict:
    lo, hi = ic95(amostras)
    return {"estimativa": float(pontual), "ic95_inf": lo, "ic95_sup": hi}


def nri_bootstrap(tab: pd.DataFrame, col_novo: str, col_antigo: str, B: int = 1000, seed: int = 0):
    """NRI categórico (modelo novo × regra antiga) pontual e bootstrap, sobre a tabela de células.

    NRI = [P(sobe | evento) − P(desce | evento)] + [P(desce | não evento) − P(sobe | não evento)],
    onde \"sobe\" = classificado alto risco só pelo modelo novo e \"desce\" = só pela regra antiga.
    """
    novo, antigo = tab[col_novo].to_numpy().astype(bool), tab[col_antigo].to_numpy().astype(bool)
    sobe, desce = novo & ~antigo, ~novo & antigo

    def _nri(pos, neg):
        pos, neg = np.atleast_2d(pos), np.atleast_2d(neg)
        return (pos[:, sobe].sum(1) - pos[:, desce].sum(1)) / pos.sum(1) + (
            neg[:, desce].sum(1) - neg[:, sobe].sum(1)
        ) / neg.sum(1)

    pontual = float(_nri(tab["pos"].to_numpy(), tab["neg"].to_numpy())[0])
    amostras = np.concatenate([_nri(p, n) for p, n in reamostrar(tab, B, seed)])
    return pontual, amostras
