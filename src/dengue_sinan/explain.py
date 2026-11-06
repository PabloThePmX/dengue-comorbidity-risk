"""Modelo explicativo E1: logística SEM penalização com interações, OR, RERI/AP, ranking, perfis.

Associação ajustada por idade e sexo, NÃO efeito causal (P6). Ajusta sobre dados agregados por
padrão de covariáveis (binomial agrupado), matematicamente idêntico ao ajuste linha a linha e
muito mais leve com milhões de linhas. A idade entra em spline (B-spline cúbico, nós fixados
nos quantis da população) também nas interações com hipertensão e diabetes (spec §3.11).
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
import patsy
import statsmodels.api as sm
from scipy import stats
from statsmodels.stats.multitest import multipletests

from dengue_sinan.dataset import PARES, completos_para_e1
from dengue_sinan.profiling import COMORBIDADES, FAIXAS, FAIXAS_ROTULOS

IDADE_MAX = 121
INTERACAO_IDADE = ("HIPERTENSA", "DIABETES")  # [ASSUMPTION] do spec §3.11
QUANTIS_NOS = (0.05, 0.25, 0.5, 0.75, 0.95)  # 5 nós [ASSUMPTION], posições definidas pela população
MIN_EVENTOS_CELULA = 10


@dataclass
class ModeloGLM:
    """Resultado do ajuste: parâmetros, covariância e o molde da matriz de desenho."""

    res: object
    design_info: object
    rhs: str
    nos: tuple
    pares: list

    @property
    def beta(self) -> pd.Series:
        return self.res.params

    @property
    def cov(self) -> pd.DataFrame:
        return self.res.cov_params()


def nos_da_idade(idade: pd.Series, quantis=QUANTIS_NOS) -> tuple:
    """Nós do spline nos quantis da idade da população (não do tipo de evento: sem vazamento)."""
    return tuple(float(round(v, 3)) for v in np.quantile(idade.dropna().to_numpy(), quantis))


def agregar_e1(pop: pd.DataFrame, x: pd.DataFrame, casas_idade: int = 2):
    """Casos completos agrupados por padrão de covariáveis: colunas k (eventos) e n (casos).

    Devolve também quantas linhas e eventos saíram pela análise de casos completos.
    """
    ok = completos_para_e1(pop, x)
    d = pd.DataFrame(
        {
            "idade": x["idade_anos"].round(casas_idade),
            "sexo_M": (x["sexo"] == "M").astype("int8"),
            "gestante": x["gestante"].astype("int8"),
            **{c: (x[c] == "Sim").astype("int8") for c in COMORBIDADES},
            "y": pop["y"].astype("int8"),
        }
    )
    exclusao = {
        "linhas_excluidas": int((~ok).sum()),
        "eventos_excluidos": int(pop.loc[~ok, "y"].sum()),
        "linhas_analisadas": int(ok.sum()),
        "eventos_analisados": int(pop.loc[ok, "y"].sum()),
    }
    chaves = [c for c in d.columns if c != "y"]
    agg = d[ok].groupby(chaves, observed=True)["y"].agg(k="sum", n="size").reset_index()
    return agg, exclusao


def pares_com_eventos(agg: pd.DataFrame, minimo: int = MIN_EVENTOS_CELULA) -> pd.DataFrame:
    """Eventos e casos na célula combinada (A = Sim e B = Sim) de cada par (decide o E1)."""
    linhas = []
    for a, b in PARES:
        s = agg[(agg[a] == 1) & (agg[b] == 1)]
        linhas.append({"A": a, "B": b, "casos": int(s["n"].sum()), "eventos": int(s["k"].sum())})
    t = pd.DataFrame(linhas)
    t["entra_no_E1"] = t["eventos"] >= minimo
    return t


def montar_rhs(nos: tuple, pares: list, interacao_idade=INTERACAO_IDADE) -> str:
    spline = (
        f"bs(idade, knots={list(nos)}, degree=3, include_intercept=False, "
        f"lower_bound=0, upper_bound={IDADE_MAX})"
    )
    termos = [spline, "sexo_M", "gestante", *COMORBIDADES]
    termos += [f"{a}:{b}" for a, b in pares]
    termos += [f"{c}:{spline}" for c in interacao_idade]
    return " + ".join(termos)


def ajustar_e1(
    agg: pd.DataFrame,
    nos: tuple,
    pares: list,
    interacao_idade=INTERACAO_IDADE,
    comorbidades: list | None = None,
) -> ModeloGLM:
    """Logística binomial agrupada sem penalização; `comorbidades` limita os efeitos."""
    if comorbidades is None:
        rhs = montar_rhs(nos, pares, interacao_idade)
    else:
        spline = (
            f"bs(idade, knots={list(nos)}, degree=3, include_intercept=False, "
            f"lower_bound=0, upper_bound={IDADE_MAX})"
        )
        rhs = " + ".join([spline, "sexo_M", "gestante", *comorbidades])
    X = patsy.dmatrix(rhs, agg, return_type="dataframe")
    desfecho = np.column_stack([agg["k"], agg["n"] - agg["k"]])
    res = sm.GLM(desfecho, X, family=sm.families.Binomial()).fit(maxiter=100)
    return ModeloGLM(res, X.design_info, rhs, nos, list(pares))


# ------------------------------------------------------------------------------ contrastes
def _linhas(m: ModeloGLM, df: pd.DataFrame) -> np.ndarray:
    return np.asarray(patsy.build_design_matrices([m.design_info], df)[0])


def _perfil_df(idade, presentes, sexo_M=0, gestante=0) -> pd.DataFrame:
    base = {"idade": np.atleast_1d(idade).astype(float), "sexo_M": sexo_M, "gestante": gestante}
    base.update({c: int(c in presentes) for c in COMORBIDADES})
    return pd.DataFrame(base)


def contraste_log_odds(m: ModeloGLM, presentes: set, idade: float, sexo_M=0, gestante=0):
    """log-odds do perfil (comorbidades em `presentes`) contra 'nenhuma', mesma idade e sexo."""
    L = (
        _linhas(m, _perfil_df(idade, presentes, sexo_M, gestante))
        - _linhas(m, _perfil_df(idade, set(), sexo_M, gestante))
    )[0]
    return L


def or_com_ic(m: ModeloGLM, presentes: set, idade: float, z: float = 1.96) -> dict:
    L = contraste_log_odds(m, presentes, idade)
    est = float(L @ m.beta.to_numpy())
    se = float(np.sqrt(L @ m.cov.to_numpy() @ L))
    return {
        "OR": float(np.exp(est)),
        "ic95_inf": float(np.exp(est - z * se)),
        "ic95_sup": float(np.exp(est + z * se)),
        "log_or": est,
        "se": se,
    }


def reri_ap(m: ModeloGLM, a: str, b: str, idade: float, z: float = 1.96) -> dict:
    """RERI e AP (interação aditiva) com IC 95% pelo método delta (D-40).

    Usa OR como aproximação do RR (desfecho raro, prevalência ≈ 0,2%).
    """
    Ls = np.vstack(
        [
            contraste_log_odds(m, {a}, idade),
            contraste_log_odds(m, {b}, idade),
            contraste_log_odds(m, {a, b}, idade),
        ]
    )
    lg = Ls @ m.beta.to_numpy()
    V = Ls @ m.cov.to_numpy() @ Ls.T
    la, lb, lab = lg
    reri = np.exp(lab) - np.exp(la) - np.exp(lb) + 1
    ap = reri / np.exp(lab)
    g_reri = np.array([-np.exp(la), -np.exp(lb), np.exp(lab)])
    g_ap = np.array(
        [-np.exp(la - lab), -np.exp(lb - lab), np.exp(la - lab) + np.exp(lb - lab) - np.exp(-lab)]
    )
    se_reri, se_ap = np.sqrt(g_reri @ V @ g_reri), np.sqrt(g_ap @ V @ g_ap)
    return {
        "RERI": float(reri),
        "RERI_ic95_inf": float(reri - z * se_reri),
        "RERI_ic95_sup": float(reri + z * se_reri),
        "AP": float(ap),
        "AP_ic95_inf": float(ap - z * se_ap),
        "AP_ic95_sup": float(ap + z * se_ap),
    }


# ------------------------------------------------------------------------------ tabelas
def _or_bruto(agg: pd.DataFrame, c: str, z: float = 1.96) -> dict:
    e, n = agg[agg[c] == 1], agg[agg[c] == 0]
    a, b = e["k"].sum(), (e["n"] - e["k"]).sum()
    cc, d = n["k"].sum(), (n["n"] - n["k"]).sum()
    if min(a, b, cc, d) == 0:
        return {"OR_bruto": np.nan, "bruto_ic95_inf": np.nan, "bruto_ic95_sup": np.nan}
    lor = np.log(a * d / (b * cc))
    se = np.sqrt(1 / a + 1 / b + 1 / cc + 1 / d)  # método de Woolf
    return {
        "OR_bruto": float(np.exp(lor)),
        "bruto_ic95_inf": float(np.exp(lor - z * se)),
        "bruto_ic95_sup": float(np.exp(lor + z * se)),
    }


def tabela_or_comorbidades(agg: pd.DataFrame, nos: tuple) -> pd.DataFrame:
    """OR bruto, ajustado por idade/sexo/gestação (uma por vez) e mutuamente ajustado."""
    mutuo = ajustar_e1(agg, nos, [], interacao_idade=(), comorbidades=COMORBIDADES)
    linhas = []
    for c in COMORBIDADES:
        so_c = ajustar_e1(agg, nos, [], interacao_idade=(), comorbidades=[c])
        exp = agg[agg[c] == 1]
        linha = {
            "comorbidade": c,
            "casos_expostos": int(exp["n"].sum()),
            "eventos_expostos": int(exp["k"].sum()),
            **_or_bruto(agg, c),
        }
        for rot, mod in (("aj_idade_sexo", so_c), ("aj_mutuo", mutuo)):
            beta, se = float(mod.beta[c]), float(np.sqrt(mod.cov.loc[c, c]))
            linha.update(
                {
                    f"OR_{rot}": float(np.exp(beta)),
                    f"{rot}_ic95_inf": float(np.exp(beta - 1.96 * se)),
                    f"{rot}_ic95_sup": float(np.exp(beta + 1.96 * se)),
                }
            )
        linhas.append(linha)
    return pd.DataFrame(linhas)


def tabela_interacoes(m: ModeloGLM, agg: pd.DataFrame, idade_ref: float) -> pd.DataFrame:
    """OR da interação multiplicativa, RERI e AP de cada par estimado, com Benjamini-Hochberg."""
    ev = pares_com_eventos(agg).set_index(["A", "B"])
    linhas = []
    for a, b in m.pares:
        nome = f"{a}:{b}"
        beta, se = float(m.beta[nome]), float(np.sqrt(m.cov.loc[nome, nome]))
        p = float(2 * stats.norm.sf(abs(beta / se)))
        linhas.append(
            {
                "A": a,
                "B": b,
                "eventos_celula": int(ev.loc[(a, b), "eventos"]),
                "OR_interacao": float(np.exp(beta)),
                "ic95_inf": float(np.exp(beta - 1.96 * se)),
                "ic95_sup": float(np.exp(beta + 1.96 * se)),
                "p_valor": p,
                **reri_ap(m, a, b, idade_ref),
            }
        )
    t = pd.DataFrame(linhas)
    if len(t):
        t["p_BH"] = multipletests(t["p_valor"], method="fdr_bh")[1]
    return t


def ranking_comorbidades(m: ModeloGLM, idade_ref: float) -> pd.DataFrame:
    """Ranking pelo OR do E1 (só dele, R10). IC sobrepostos → 'sem ordem definida' (FR-19)."""
    t = pd.DataFrame([{"comorbidade": c, **or_com_ic(m, {c}, idade_ref)} for c in COMORBIDADES])
    t = t.sort_values("OR", ascending=False).reset_index(drop=True)
    sobrepoe = []
    for i, r in t.iterrows():
        outros = [
            t.loc[j, "comorbidade"]
            for j in range(len(t))
            if j != i
            and r["ic95_inf"] <= t.loc[j, "ic95_sup"]
            and t.loc[j, "ic95_inf"] <= r["ic95_sup"]
        ]
        sobrepoe.append(", ".join(outros) if outros else "")
    t["sem_ordem_definida_com"] = sobrepoe
    t.insert(0, "posicao", np.arange(1, len(t) + 1))
    return t


def teste_razao_verossimilhanca(m_completo: ModeloGLM, m_reduzido: ModeloGLM) -> dict:
    lr = 2 * (m_completo.res.llf - m_reduzido.res.llf)
    gl = int(m_completo.res.df_model - m_reduzido.res.df_model)
    return {
        "LR": float(lr),
        "gl": gl,
        "p_valor": float(stats.chi2.sf(lr, gl)) if gl > 0 else np.nan,
    }


def prever_e1(m: ModeloGLM, df: pd.DataFrame) -> np.ndarray:
    """Probabilidade prevista para linhas com as colunas idade, sexo_M, gestante e comorbidades."""
    eta = _linhas(m, df) @ m.beta.to_numpy()
    return 1 / (1 + np.exp(-np.clip(eta, -700, 700)))


def _risco_padronizado(m: ModeloGLM, ref: pd.DataFrame, presentes: set):
    """Risco médio do perfil padronizado pela população de referência + gradiente."""
    d = ref.copy()
    for c in COMORBIDADES:
        d[c] = int(c in presentes)
    X = _linhas(m, d)
    p = 1 / (1 + np.exp(-(X @ m.beta.to_numpy())))
    w = ref["n"].to_numpy(dtype=float)
    media = float((w * p).sum() / w.sum())
    grad = ((w * p * (1 - p))[:, None] * X).sum(axis=0) / w.sum()
    return media, grad


def tabela_perfis(
    m: ModeloGLM, agg: pd.DataFrame, minimo: int = MIN_EVENTOS_CELULA
) -> pd.DataFrame:
    """Risco absoluto por perfil e faixa etária, com IC 95% (delta) e razão vs. 'sem comorbidades'.

    Perfis: nenhuma comorbidade; cada uma sozinha; cada par que entrou no E1; toda combinação
    exata de 3+ com ≥ `minimo` eventos (FR-06, D-52). Células com < `minimo` eventos NÃO saem.
    Combinações de 3+ vêm da soma dos efeitos do E1 (sem interações de 3ª ordem).
    """
    comb = agg[COMORBIDADES].astype(int)
    agg = agg.assign(
        _chave=comb.astype(str).agg("".join, axis=1),
        _faixa=pd.cut(agg["idade"], FAIXAS, right=False, labels=FAIXAS_ROTULOS),
    )
    perfis: dict[str, set] = {"Sem comorbidades": set()}
    perfis.update({c: {c} for c in COMORBIDADES})
    perfis.update({f"{a} + {b}": {a, b} for a, b in m.pares})
    por_chave = agg.groupby("_chave")["k"].sum()
    for chave, ev in por_chave.items():
        pres = {c for c, v in zip(COMORBIDADES, chave, strict=True) if v == "1"}
        if len(pres) >= 3 and ev >= minimo:
            perfis[" + ".join(sorted(pres))] = pres
    linhas = []
    for faixa in FAIXAS_ROTULOS:
        ref = agg[agg["_faixa"] == faixa][["idade", "sexo_M", "gestante", "n", *COMORBIDADES]]
        if ref.empty:
            continue
        base, g_base = _risco_padronizado(m, ref, set())
        for nome, pres in perfis.items():
            chave = "".join("1" if c in pres else "0" for c in COMORBIDADES)
            sub = agg[(agg["_faixa"] == faixa) & (agg["_chave"] == chave)]
            eventos, casos = int(sub["k"].sum()), int(sub["n"].sum())
            if eventos < minimo:
                continue  # supressão de célula pequena (NFR-03, SC-05)
            risco, g = _risco_padronizado(m, ref, pres)
            se_logit = float(np.sqrt(g @ m.cov.to_numpy() @ g) / (risco * (1 - risco)))
            lg = np.log(risco / (1 - risco))
            g_razao = g / risco - g_base / base
            se_razao = float(np.sqrt(g_razao @ m.cov.to_numpy() @ g_razao))
            razao = risco / base
            linhas.append(
                {
                    "perfil": nome,
                    "faixa_etaria": faixa,
                    "casos_observados": casos,
                    "eventos_observados": eventos,
                    "risco_estimado": risco,
                    "ic95_inf": float(1 / (1 + np.exp(-(lg - 1.96 * se_logit)))),
                    "ic95_sup": float(1 / (1 + np.exp(-(lg + 1.96 * se_logit)))),
                    "razao_vs_sem_comorbidade": razao,
                    "razao_ic95_inf": float(razao * np.exp(-1.96 * se_razao)),
                    "razao_ic95_sup": float(razao * np.exp(1.96 * se_razao)),
                }
            )
    return pd.DataFrame(linhas)
