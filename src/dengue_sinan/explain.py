"""Modelo explicativo E1: regressão logística com interações, RERI/AP, ranking e perfis (Fase 3)."""

import itertools
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.special import expit
from sklearn.preprocessing import SplineTransformer
from statsmodels.stats.multitest import multipletests

from dengue_sinan import profiling
from dengue_sinan.artifacts import save_bundle
from dengue_sinan.dataset import COMORBIDADES, build_feature_frame
from dengue_sinan.descriptive import combination_counts, pair_event_counts
from dengue_sinan.guard import assert_dev_only
from dengue_sinan.verify import check, write_report

_Z_95 = 1.959963984540054
AGE_MIDPOINTS: dict[str, float] = {
    "0–4": 2.0,
    "5–14": 9.5,
    "15–39": 27.0,
    "40–59": 49.5,
    "60–79": 69.5,
    "80+": 85.0,
}
TRIO_NOTE = (
    "risco estimado pela soma dos efeitos individuais e dos pares; "
    "o E1 não tem termo próprio para o trio"
)


@dataclass
class E1Artifact:
    """Modelo E1 enxuto (parâmetros, covariância e transformadores de spline, sem dados — T-3.6)."""

    feature_names: list[str]
    params: pd.Series
    cov_params: pd.DataFrame
    spline_main: SplineTransformer
    spline_inter: SplineTransformer
    included_pairs: list[tuple[str, str]]
    excluded_pairs: list[tuple[str, str]]
    include_ausente_cols: list[str]
    include_sexo_i: bool
    converged: bool
    fit_seconds: float
    n_obs: int
    n_events: int

    def design_matrix(self, df: pd.DataFrame) -> pd.DataFrame:
        """Constrói a matriz de desenho `X` para novas observações ou perfis sintéticos."""
        n = len(df)
        idade = pd.to_numeric(df["idade_anos"], errors="coerce").fillna(40.0).to_numpy(
            dtype=np.float64
        ).reshape(-1, 1)

        sp_main = self.spline_main.transform(idade)
        sp_inter = self.spline_inter.transform(idade)

        cols: dict[str, np.ndarray] = {"Intercept": np.ones(n, dtype=np.float64)}
        for i in range(sp_main.shape[1]):
            cols[f"idade_sp5_{i}"] = sp_main[:, i]

        sexo_s = (
            df["sexo"].astype("string")
            if "sexo" in df.columns
            else pd.Series("F", index=df.index)
        )
        cols["sexo_M"] = (sexo_s == "M").to_numpy(dtype=np.float64)
        if self.include_sexo_i:
            cols["sexo_I"] = (sexo_s == "I").to_numpy(dtype=np.float64)

        if "gestante" in df.columns:
            gest = (
                pd.to_numeric(df["gestante"], errors="coerce")
                .fillna(0)
                .to_numpy(dtype=np.float64)
            )
        else:
            gest = np.zeros(n, dtype=np.float64)
        cols["gestante"] = (gest > 0).astype(np.float64)

        sim_map: dict[str, np.ndarray] = {}
        for c in COMORBIDADES:
            if c in df.columns:
                s_col = df[c].astype("string")
                sim_arr = s_col.isin({"Sim", "1", "True", "true"}).to_numpy(dtype=np.float64)
                aus_arr = s_col.isin({"Ausente"}).to_numpy(dtype=np.float64)
            else:
                sim_arr = np.zeros(n, dtype=np.float64)
                aus_arr = np.zeros(n, dtype=np.float64)
            sim_map[c] = sim_arr
            cols[f"{c}_Sim"] = sim_arr
            if c in self.include_ausente_cols:
                cols[f"{c}_Ausente"] = aus_arr

        for c1, c2 in self.included_pairs:
            cols[f"{c1}_Sim:{c2}_Sim"] = sim_map[c1] * sim_map[c2]

        for c_age in ("HIPERTENSA", "DIABETES"):
            for j in range(sp_inter.shape[1]):
                cols[f"{c_age}_Sim:idade_sp3_{j}"] = sim_map[c_age] * sp_inter[:, j]

        design_df = pd.DataFrame(cols, index=df.index)
        return design_df.reindex(columns=self.feature_names, fill_value=0.0)

    def predict_profile_risk(
        self,
        idade_anos: float,
        sexo: str = "F",
        gestante: int | bool = 0,
        comorbidades_ativas: list[str] | set[str] = (),
    ) -> dict[str, float]:
        """Calcula o risco previsto e o IC 95% (método delta na escala logit) para um perfil."""
        active_set = set(comorbidades_ativas)
        row: dict[str, Any] = {
            "idade_anos": float(idade_anos),
            "sexo": str(sexo),
            "gestante": int(bool(gestante)),
        }
        for c in COMORBIDADES:
            row[c] = "Sim" if c in active_set else "Não"

        X = self.design_matrix(pd.DataFrame([row]))
        x_vec = X.iloc[0].to_numpy(dtype=np.float64)
        beta = self.params.reindex(self.feature_names).to_numpy(dtype=np.float64)
        cov = (
            self.cov_params.reindex(index=self.feature_names, columns=self.feature_names)
            .to_numpy(dtype=np.float64)
        )

        logit_hat = float(x_vec @ beta)
        var_logit = float(max(0.0, x_vec @ cov @ x_vec))
        se_logit = float(np.sqrt(var_logit))

        risco = float(expit(logit_hat))
        ic_inf = float(expit(logit_hat - _Z_95 * se_logit))
        ic_sup = float(expit(logit_hat + _Z_95 * se_logit))
        return {
            "risco": risco,
            "ic95_inf": ic_inf,
            "ic95_sup": ic_sup,
            "logit": logit_hat,
            "se_logit": se_logit,
        }


def fit_e1(
    df: pd.DataFrame,
    min_pair_events: int = 10,
    min_ausente_events: int = 5,
) -> E1Artifact:
    """Ajusta o modelo explicativo E1 via `statsmodels.GLM` Binomial sem penalização (T-3.1, R9)."""
    assert_dev_only(df)
    feat = build_feature_frame(df) if "n_comorbidades" not in df.columns else df
    y = feat["y"].to_numpy(dtype=np.float64)

    pair_df = pair_event_counts(feat)
    included_pairs: list[tuple[str, str]] = []
    excluded_pairs: list[tuple[str, str]] = []
    for _, row in pair_df.iterrows():
        pair_tuple = (str(row["comorbidade_a"]), str(row["comorbidade_b"]))
        if int(row["eventos"]) >= int(min_pair_events):
            included_pairs.append(pair_tuple)
        else:
            excluded_pairs.append(pair_tuple)

    # Ordena na ordem canônica de itertools.combinations(COMORBIDADES, 2)
    canonical_order = list(itertools.combinations(COMORBIDADES, 2))
    inc_set = set(included_pairs)
    included_pairs = [p for p in canonical_order if p in inc_set]
    excluded_pairs = [p for p in canonical_order if p not in inc_set]

    idade = feat["idade_anos"].to_numpy(dtype=np.float64).reshape(-1, 1)
    # 5 gl (n_knots=4, degree=2 sem bias) no efeito principal e 3 gl nas interações com idade
    spline_main = SplineTransformer(n_knots=4, degree=2, include_bias=False)
    spline_inter = SplineTransformer(n_knots=3, degree=1, include_bias=False)
    spline_main.fit(idade)
    spline_inter.fit(idade)

    # Categoria "Ausente" nas comorbidades: ~0% na população; só inclui se tiver eventos suficientes
    include_ausente_cols: list[str] = []
    for c in COMORBIDADES:
        aus_mask = (feat[c].astype("string") == "Ausente").to_numpy(dtype=bool)
        if int(y[aus_mask].sum()) >= int(min_ausente_events):
            include_ausente_cols.append(c)

    sexo_i_mask = (feat["sexo"].astype("string") == "I").to_numpy(dtype=bool)
    include_sexo_i = int(y[sexo_i_mask].sum()) >= int(min_ausente_events)

    dummy_artifact = E1Artifact(
        feature_names=[],
        params=pd.Series(dtype=float),
        cov_params=pd.DataFrame(),
        spline_main=spline_main,
        spline_inter=spline_inter,
        included_pairs=included_pairs,
        excluded_pairs=excluded_pairs,
        include_ausente_cols=include_ausente_cols,
        include_sexo_i=include_sexo_i,
        converged=False,
        fit_seconds=0.0,
        n_obs=len(feat),
        n_events=int(y.sum()),
    )

    # Monta todas as colunas primeiro para descobrir feature_names não degeneradas
    sp_m = spline_main.transform(idade)
    sp_i = spline_inter.transform(idade)
    cols: dict[str, np.ndarray] = {"Intercept": np.ones(len(feat), dtype=np.float64)}
    for i in range(sp_m.shape[1]):
        cols[f"idade_sp5_{i}"] = sp_m[:, i]

    sexo_s = feat["sexo"].astype("string")
    cols["sexo_M"] = (sexo_s == "M").to_numpy(dtype=np.float64)
    if include_sexo_i:
        cols["sexo_I"] = (sexo_s == "I").to_numpy(dtype=np.float64)

    gest_arr = (feat["gestante"].to_numpy(dtype=np.float64) > 0).astype(np.float64)
    if gest_arr.sum() > 0:
        cols["gestante"] = gest_arr

    sim_map: dict[str, np.ndarray] = {}
    for c in COMORBIDADES:
        s_col = feat[c].astype("string")
        sim_arr = (s_col == "Sim").to_numpy(dtype=np.float64)
        sim_map[c] = sim_arr
        cols[f"{c}_Sim"] = sim_arr
        if c in include_ausente_cols:
            cols[f"{c}_Ausente"] = (s_col == "Ausente").to_numpy(dtype=np.float64)

    for c1, c2 in included_pairs:
        cols[f"{c1}_Sim:{c2}_Sim"] = sim_map[c1] * sim_map[c2]

    for c_age in ("HIPERTENSA", "DIABETES"):
        if sim_map[c_age].sum() >= min_pair_events:
            for j in range(sp_i.shape[1]):
                cols[f"{c_age}_Sim:idade_sp3_{j}"] = sim_map[c_age] * sp_i[:, j]

    X_df = pd.DataFrame(cols, index=feat.index)
    # Remove colunas constantes (exceto Intercept) para evitar matriz singular em amostras pequenas
    keep_cols = ["Intercept"] + [
        c for c in X_df.columns if c != "Intercept" and X_df[c].std() > 0
    ]
    X_df = X_df[keep_cols]

    t0 = time.perf_counter()
    glm = sm.GLM(y, X_df, family=sm.families.Binomial())
    try:
        res = glm.fit(maxiter=100, disp=False)
        converged = bool(getattr(res, "converged", True))
        if not converged:
            res = glm.fit(method="lbfgs", maxiter=300, disp=False)
            converged = bool(getattr(res, "converged", True))
    except Exception:
        res = glm.fit(method="lbfgs", maxiter=300, disp=False)
        converged = bool(getattr(res, "converged", True))
    elapsed = time.perf_counter() - t0

    dummy_artifact.feature_names = list(X_df.columns)
    dummy_artifact.params = pd.Series(res.params, index=X_df.columns, dtype=np.float64)
    dummy_artifact.cov_params = pd.DataFrame(
        res.cov_params(), index=X_df.columns, columns=X_df.columns, dtype=np.float64
    )
    dummy_artifact.converged = converged
    dummy_artifact.fit_seconds = float(elapsed)
    return dummy_artifact


def extract_or_and_interactions(model: E1Artifact) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Calcula OR + IC 95% dos efeitos principais e interações com Benjamini-Hochberg (T-3.2)."""
    main_rows: list[dict[str, Any]] = []
    for c in COMORBIDADES:
        term = f"{c}_Sim"
        if term in model.params.index:
            beta = float(model.params[term])
            se = float(np.sqrt(max(0.0, model.cov_params.loc[term, term])))
            or_val = float(np.exp(beta))
            ic_inf = float(np.exp(beta - _Z_95 * se))
            ic_sup = float(np.exp(beta + _Z_95 * se))
        else:
            beta, se, or_val, ic_inf, ic_sup = 0.0, 0.0, 1.0, 1.0, 1.0
        main_rows.append(
            {
                "comorbidade": c,
                "beta": beta,
                "se": se,
                "OR": or_val,
                "IC95_inf": ic_inf,
                "IC95_sup": ic_sup,
            }
        )
    main_df = pd.DataFrame(main_rows)

    from scipy.stats import norm

    inter_rows: list[dict[str, Any]] = []
    p_vals: list[float] = []
    inc_indices: list[int] = []

    all_pairs = list(itertools.combinations(COMORBIDADES, 2))
    inc_set = set(model.included_pairs)

    for idx, (c1, c2) in enumerate(all_pairs):
        term = f"{c1}_Sim:{c2}_Sim"
        if (c1, c2) in inc_set and term in model.params.index:
            beta = float(model.params[term])
            se = float(np.sqrt(max(0.0, model.cov_params.loc[term, term])))
            z_stat = beta / se if se > 0 else 0.0
            p_raw = float(2.0 * (1.0 - norm.cdf(abs(z_stat))))
            p_vals.append(p_raw)
            inc_indices.append(idx)
            inter_rows.append(
                {
                    "par": f"{c1} + {c2}",
                    "status": "incluído",
                    "OR_interacao": float(np.exp(beta)),
                    "IC95_inf": float(np.exp(beta - _Z_95 * se)),
                    "IC95_sup": float(np.exp(beta + _Z_95 * se)),
                    "p_valor": p_raw,
                    "p_ajustado_bh": np.nan,
                    "significativo_fdr_5pct": False,
                }
            )
        else:
            inter_rows.append(
                {
                    "par": f"{c1} + {c2}",
                    "status": "eventos insuficientes",
                    "OR_interacao": np.nan,
                    "IC95_inf": np.nan,
                    "IC95_sup": np.nan,
                    "p_valor": np.nan,
                    "p_ajustado_bh": np.nan,
                    "significativo_fdr_5pct": False,
                }
            )

    if p_vals:
        reject, p_adj, _, _ = multipletests(p_vals, alpha=0.05, method="fdr_bh")
        for i_list, row_idx in enumerate(inc_indices):
            inter_rows[row_idx]["p_ajustado_bh"] = float(p_adj[i_list])
            inter_rows[row_idx]["significativo_fdr_5pct"] = bool(reject[i_list])

    return main_df, pd.DataFrame(inter_rows)


def compute_reri_ap_from_params(
    beta_a: float,
    beta_b: float,
    beta_ab: float,
    cov_3x3: np.ndarray,
) -> dict[str, float]:
    """Calcula `OR_A`, `OR_B`, `OR_AB`, `RERI` e `AP` com IC 95% pelo método delta (T-3.3, D-40)."""
    or_a = float(np.exp(beta_a))
    or_b = float(np.exp(beta_b))
    or_ab = float(np.exp(beta_a + beta_b + beta_ab))

    reri = float(or_ab - or_a - or_b + 1.0)
    ap = float(reri / or_ab)

    # Gradiente de RERI em relação a (beta_a, beta_b, beta_ab)
    grad_reri = np.array([or_ab - or_a, or_ab - or_b, or_ab], dtype=np.float64)
    var_reri = float(max(0.0, grad_reri @ cov_3x3 @ grad_reri))
    se_reri = float(np.sqrt(var_reri))

    # Gradiente de AP = 1 - (OR_A + OR_B - 1) / OR_AB em relação a (beta_a, beta_b, beta_ab)
    grad_ap = np.array(
        [
            (or_b - 1.0) / or_ab,
            (or_a - 1.0) / or_ab,
            (or_a + or_b - 1.0) / or_ab,
        ],
        dtype=np.float64,
    )
    var_ap = float(max(0.0, grad_ap @ cov_3x3 @ grad_ap))
    se_ap = float(np.sqrt(var_ap))

    return {
        "OR_A": or_a,
        "OR_B": or_b,
        "OR_AB": or_ab,
        "RERI": reri,
        "RERI_IC95_inf": float(reri - _Z_95 * se_reri),
        "RERI_IC95_sup": float(reri + _Z_95 * se_reri),
        "AP": ap,
        "AP_IC95_inf": float(ap - _Z_95 * se_ap),
        "AP_IC95_sup": float(ap + _Z_95 * se_ap),
    }


def compute_reri_ap_table(model: E1Artifact) -> pd.DataFrame:
    """Gera a tabela de interação aditiva (RERI e AP com IC 95%) para os pares do E1 (T-3.3)."""
    rows: list[dict[str, Any]] = []
    for c1, c2 in model.included_pairs:
        t_a, t_b, t_ab = f"{c1}_Sim", f"{c2}_Sim", f"{c1}_Sim:{c2}_Sim"
        if not ({t_a, t_b, t_ab} <= set(model.params.index)):
            continue
        terms = [t_a, t_b, t_ab]
        b_a, b_b, b_ab = (float(model.params[t]) for t in terms)
        cov_sub = model.cov_params.loc[terms, terms].to_numpy(dtype=np.float64)
        metrics = compute_reri_ap_from_params(b_a, b_b, b_ab, cov_sub)
        rows.append({"par": f"{c1} + {c2}", **metrics})
    return pd.DataFrame(rows)


def rank_comorbidities(main_or_df: pd.DataFrame) -> pd.DataFrame:
    """Ordena as 7 comorbidades pelo OR principal e marca ICs sobrepostos (T-3.4, FR-19, R10)."""
    ranked = main_or_df.sort_values("OR", ascending=False).reset_index(drop=True).copy()
    ranked["posicao"] = np.arange(1, len(ranked) + 1)

    overlaps_col: list[str] = []
    for i, row_i in ranked.iterrows():
        lo_i, hi_i = float(row_i["IC95_inf"]), float(row_i["IC95_sup"])
        overlapping_names: list[str] = []
        for j, row_j in ranked.iterrows():
            if i == j:
                continue
            lo_j, hi_j = float(row_j["IC95_inf"]), float(row_j["IC95_sup"])
            if max(lo_i, lo_j) <= min(hi_i, hi_j):
                overlapping_names.append(str(row_j["comorbidade"]))
        if overlapping_names:
            overlaps_col.append(f"sem ordem definida com: {', '.join(overlapping_names)}")
        else:
            overlaps_col.append("ordem definida")

    ranked["status_ordem"] = overlaps_col
    return ranked[
        ["posicao", "comorbidade", "OR", "IC95_inf", "IC95_sup", "status_ordem"]
    ]


def build_profile_specs(
    included_pairs: list[tuple[str, str]],
    trios_3plus: list[str],
) -> list[dict[str, Any]]:
    """Gera automaticamente a lista dos 4 grupos de perfis da T-3.5 (D-52)."""
    all_pairs = list(itertools.combinations(COMORBIDADES, 2))
    inc_set = set(included_pairs)

    specs: list[dict[str, Any]] = [
        {
            "grupo": "1. Referência",
            "perfil": "Sem comorbidades",
            "comorbidades": [],
            "status": "estimado",
            "nota": "",
        }
    ]
    for c in COMORBIDADES:
        specs.append(
            {
                "grupo": "2. Isolada",
                "perfil": f"Só {c}",
                "comorbidades": [c],
                "status": "estimado",
                "nota": "",
            }
        )
    for c1, c2 in all_pairs:
        if (c1, c2) in inc_set:
            specs.append(
                {
                    "grupo": "3. Par",
                    "perfil": f"{c1} + {c2}",
                    "comorbidades": [c1, c2],
                    "status": "estimado",
                    "nota": "",
                }
            )
        else:
            specs.append(
                {
                    "grupo": "3. Par",
                    "perfil": f"{c1} + {c2}",
                    "comorbidades": [c1, c2],
                    "status": "dados insuficientes",
                    "nota": "dados insuficientes (< 10 eventos no desenvolvimento)",
                }
            )
    for combo_str in trios_3plus:
        diseases = [d.strip() for d in combo_str.split("+") if d.strip()]
        specs.append(
            {
                "grupo": "4. 3 ou mais",
                "perfil": " + ".join(diseases),
                "comorbidades": diseases,
                "status": "estimado",
                "nota": TRIO_NOTE,
            }
        )
    return specs


def generate_profiles_table(
    model: E1Artifact,
    df: pd.DataFrame | None = None,
    min_cell: int = 10,
) -> pd.DataFrame:
    """Gera a tabela completa de perfis por faixa etária e sexo (F/M) usando o E1 (T-3.5, FR-06)."""
    trios_list: list[str] = []
    if df is not None:
        combos_df = combination_counts(df)
        trios_list = combos_df.loc[combos_df["casos"] >= int(min_cell), "combinacao"].tolist()

    profile_specs = build_profile_specs(model.included_pairs, trios_list)
    rows: list[dict[str, Any]] = []

    for faixa_label, age_mid in AGE_MIDPOINTS.items():
        for sexo in ("F", "M"):
            ref_pred = model.predict_profile_risk(
                idade_anos=age_mid,
                sexo=sexo,
                gestante=0,
                comorbidades_ativas=[],
            )
            ref_risk = max(1e-12, ref_pred["risco"])

            for spec in profile_specs:
                if spec["status"] != "estimado":
                    rows.append(
                        {
                            "Grupo": spec["grupo"],
                            "Perfil": spec["perfil"],
                            "Faixa etária": faixa_label,
                            "Sexo": sexo,
                            "Risco estimado (%)": "dados insuficientes",
                            "IC 95% (%)": "dados insuficientes",
                            "Razão vs. saudável mesma faixa": "dados insuficientes",
                            "Nota": spec["nota"],
                        }
                    )
                    continue

                pred = model.predict_profile_risk(
                    idade_anos=age_mid,
                    sexo=sexo,
                    gestante=0,
                    comorbidades_ativas=spec["comorbidades"],
                )
                ratio = pred["risco"] / ref_risk
                rows.append(
                    {
                        "Grupo": spec["grupo"],
                        "Perfil": spec["perfil"],
                        "Faixa etária": faixa_label,
                        "Sexo": sexo,
                        "Risco estimado (%)": round(100.0 * pred["risco"], 4),
                        "IC 95% (%)": (
                            f"{100.0 * pred['ic95_inf']:.4f}–{100.0 * pred['ic95_sup']:.4f}"
                        ),
                        "Razão vs. saudável mesma faixa": round(ratio, 2),
                        "Nota": spec["nota"],
                    }
                )
    return pd.DataFrame(rows)


def run_e1_pipeline(cfg: dict[str, Any], df: pd.DataFrame) -> dict[str, Any]:
    """Executa T-3.1 a T-3.6 completas, grava `reports/e1/*.md` e serializa o artefato E1."""
    assert_dev_only(df)
    feat = build_feature_frame(df) if "n_comorbidades" not in df.columns else df
    min_cell = int(cfg.get("supressao_min_celula", 10))

    model = fit_e1(feat, min_pair_events=min_cell)
    main_or_df, inter_or_df = extract_or_and_interactions(model)
    reri_df = compute_reri_ap_table(model)
    ranking_df = rank_comorbidities(main_or_df)
    perfis_df = generate_profiles_table(model, feat, min_cell=min_cell)

    reports_e1 = Path(cfg.get("caminhos", {}).get("relatorios", "reports")) / "e1"
    reports_e1.mkdir(parents=True, exist_ok=True)

    # T-3.1: coeficientes.md
    coef_table = pd.DataFrame(
        {
            "termo": model.params.index,
            "coeficiente_logit": model.params.values,
            "erro_padrao": np.sqrt(np.maximum(0.0, np.diag(model.cov_params.values))),
        }
    )
    coef_path = reports_e1 / "coeficientes.md"
    coef_path.write_text(
        f"# E1 — Coeficientes da regressão logística sem penalização (T-3.1)\n\n"
        f"- Convergiu: `{model.converged}`\n"
        f"- Tempo de ajuste (s): `{model.fit_seconds:.2f}`\n"
        f"- Pares incluídos (≥ {min_cell} eventos): `{len(model.included_pairs)}`\n\n"
        f"{profiling.markdown_table(coef_table, decimals=4)}\n",
        encoding="utf-8",
    )

    # T-3.2: or_interacoes.md
    or_path = reports_e1 / "or_interacoes.md"
    or_path.write_text(
        "# E1 — Odds Ratios (efeitos principais e interações 2 a 2 com FDR 5%) (T-3.2)\n\n"
        "## Efeitos principais das 7 comorbidades\n\n"
        f"{profiling.markdown_table(main_or_df, decimals=4)}\n\n"
        "## Interações 2 a 2 (Benjamini-Hochberg FDR 5%)\n\n"
        f"{profiling.markdown_table(inter_or_df, decimals=4)}\n",
        encoding="utf-8",
    )

    # T-3.3: reri_ap.md
    reri_path = reports_e1 / "reri_ap.md"
    reri_path.write_text(
        "# E1 — Interação aditiva: RERI e AP com IC 95% (método delta) (T-3.3)\n\n"
        f"{profiling.markdown_table(reri_df, decimals=4)}\n",
        encoding="utf-8",
    )

    # T-3.4: ranking.md
    ranking_path = reports_e1 / "ranking.md"
    ranking_path.write_text(
        "# E1 — Ranking de comorbidades pelo OR ajustado (T-3.4, FR-19)\n\n"
        "> Duas comorbidades com IC 95% sobrepostos são marcadas como 'sem ordem definida'.\n\n"
        f"{profiling.markdown_table(ranking_df, decimals=4)}\n",
        encoding="utf-8",
    )

    # T-3.5: perfis_completo.md
    perfis_path = reports_e1 / "perfis_completo.md"
    perfis_path.write_text(
        "# E1 — Tabela completa de perfis de risco (T-3.5, FR-06)\n\n"
        f"{profiling.markdown_table(perfis_df, decimals=4)}\n",
        encoding="utf-8",
    )

    # T-3.6: Serializar o E1 (sem dados de treino)
    models_dir = Path(cfg.get("caminhos", {}).get("modelos", "models"))
    e1_bundle_path = save_bundle(
        model,
        models_dir / "e1_final.joblib",
        metadados={
            "config": cfg,
            "lista_features": model.feature_names,
            "metricas_validacao": {
                "converged": model.converged,
                "fit_seconds": model.fit_seconds,
                "n_included_pairs": len(model.included_pairs),
            },
        },
    )

    return {
        "model": model,
        "main_or_df": main_or_df,
        "inter_or_df": inter_or_df,
        "reri_df": reri_df,
        "ranking_df": ranking_df,
        "perfis_df": perfis_df,
        "coef_path": coef_path,
        "or_path": or_path,
        "reri_path": reri_path,
        "ranking_path": ranking_path,
        "perfis_path": perfis_path,
        "bundle_path": e1_bundle_path,
    }


def verify_phase3_e1(
    cfg: dict[str, Any],
    df: pd.DataFrame,
    *,
    out_dir: str | Path | None = None,
) -> Path:
    """Executa `run_e1_pipeline` e grava `reports/verificacao/T-3.1_a_T-3.6.json` (D-56)."""
    res = run_e1_pipeline(cfg, df)
    model: E1Artifact = res["model"]

    from dengue_sinan.artifacts import load_bundle

    reloaded = load_bundle(res["bundle_path"])
    r_orig = model.predict_profile_risk(65.0, "F", 0, ["HIPERTENSA", "DIABETES"])["risco"]
    r_load = reloaded["model"].predict_profile_risk(65.0, "F", 0, ["HIPERTENSA", "DIABETES"])[
        "risco"
    ]

    dest_dir = (
        Path(out_dir)
        if out_dir is not None
        else Path(cfg.get("caminhos", {}).get("relatorios", "reports")) / "verificacao"
    )
    checks = [
        check("e1_convergiu", True, bool(model.converged)),
        check("coeficientes_md_existe", True, res["coef_path"].is_file()),
        check("or_interacoes_md_existe", True, res["or_path"].is_file()),
        check("reri_ap_md_existe", True, res["reri_path"].is_file()),
        check("ranking_md_existe", True, res["ranking_path"].is_file()),
        check("perfis_completo_md_existe", True, res["perfis_path"].is_file()),
        check("bundle_reproduz_risco_precisao_1e9", True, bool(abs(r_orig - r_load) < 1e-9)),
    ]
    return write_report("T-3.1_a_T-3.6", checks, dest_dir, cfg)
