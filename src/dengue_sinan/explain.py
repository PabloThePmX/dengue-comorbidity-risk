"""Modelo explicativo E1 e tabelas de efeitos de comorbidades."""

from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import patsy
import statsmodels.formula.api as smf
from scipy.special import expit
from scipy.stats import norm
from statsmodels.stats.multitest import multipletests

from dengue_sinan.descriptive import pair_event_counts
from dengue_sinan.guard import assert_dev_only
from dengue_sinan.profiling import COMORBIDADES, FAIXAS_ROTULOS, code


@dataclass(frozen=True)
class E1Fit:
    """Resultado ajustado e metadados agregados; não contém o DataFrame original."""

    result: Any
    formula: str
    eligible_pairs: tuple[tuple[str, str], ...]
    excluded_pairs: tuple[tuple[str, str], ...]
    pair_counts: pd.DataFrame
    spline_states: dict[str, dict[str, Any]]


@dataclass(frozen=True)
class E1Bundle:
    """Estado suficiente para predizer E1, sem observações nem matriz de treino."""

    formula: str
    columns: tuple[str, ...]
    coefficients: np.ndarray
    covariance: np.ndarray
    spline_states: dict[str, dict[str, Any]]


def _prepare(frame: pd.DataFrame) -> pd.DataFrame:
    prepared = pd.DataFrame(index=frame.index)
    if "y" in frame:
        prepared["y"] = frame["y"].astype("int8")
    prepared["idade_anos"] = pd.to_numeric(frame["idade_anos"], errors="coerce")
    sex_values = code(frame["CS_SEXO"])
    sex = sex_values.where(sex_values.isin({"F", "M"}), "I")
    prepared["sexo"] = pd.Categorical(sex, categories=["F", "M", "I"])
    if "gestante" in frame:
        pregnancy = frame["gestante"]
        if pd.api.types.is_bool_dtype(pregnancy):
            prepared["gestante"] = pregnancy.astype("int8")
        else:
            prepared["gestante"] = pregnancy.astype("string").isin(
                {"1", "True", "true"}
            ).astype("int8")
    else:
        prepared["gestante"] = code(frame["CS_GESTANT"]).isin(
            {"1", "2", "3", "4"}
        ).astype("int8")
    for column in COMORBIDADES:
        values = code(frame[column]).map({"1": "Sim", "2": "Não"}).fillna("Ausente")
        prepared[column] = pd.Categorical(values, categories=["Não", "Sim", "Ausente"])
        prepared[f"{column}_sim"] = values.eq("Sim").astype("int8")
    return prepared


def fit_e1(
    frame: pd.DataFrame,
    pair_counts: pd.DataFrame | None = None,
    min_events: int = 10,
    maxiter: int = 200,
    method: str = "lbfgs",
) -> E1Fit:
    """Ajusta a logística não penalizada E1 em desenvolvimento e falha se não convergir."""
    assert_dev_only(frame)
    if "y" not in frame:
        raise ValueError("frame precisa conter o alvo y")
    if pair_counts is None:
        pair_counts = pair_event_counts(frame)
    required = {"comorbidade_a", "comorbidade_b", "eventos"}
    if required - set(pair_counts.columns):
        raise ValueError(f"pair_counts precisa das colunas: {', '.join(sorted(required))}")

    eligible = tuple(
        (row.comorbidade_a, row.comorbidade_b)
        for row in pair_counts.itertuples(index=False)
        if row.eventos >= min_events
    )
    excluded = tuple(
        (row.comorbidade_a, row.comorbidade_b)
        for row in pair_counts.itertuples(index=False)
        if row.eventos < min_events
    )
    data = _prepare(frame)
    terms = [
        'cr(idade_anos, df=5, constraints="center")',
        'C(sexo, Treatment(reference="F"), levels=["F", "M", "I"])',
        "gestante",
        *[
            f'C({column}, Treatment(reference="Não"), levels=["Não", "Sim", "Ausente"])'
            for column in COMORBIDADES
        ],
        *[f"{first}_sim:{second}_sim" for first, second in eligible],
        'HIPERTENSA_sim:cr(idade_anos, df=3, constraints="center")',
        'DIABETES_sim:cr(idade_anos, df=3, constraints="center")',
    ]
    formula = "y ~ " + " + ".join(terms)
    result = smf.logit(formula, data=data).fit(
        method=method, maxiter=maxiter, disp=False, full_output=True
    )
    if not result.mle_retvals.get("converged", False):
        raise RuntimeError(
            f"E1 não convergiu com method={method!r}, maxiter={maxiter}; "
            "registre o problema antes de tentar outro método/mais iterações"
        )
    counts = pair_counts.copy()
    counts["incluida_no_E1"] = counts.apply(
        lambda row: (row["comorbidade_a"], row["comorbidade_b"]) in eligible, axis=1
    )
    spline_states = {}
    design_info = result.model.data.orig_exog.design_info
    for factor, info in design_info.factor_infos.items():
        name = "age_main" if "df=5" in str(factor) else "age_condition" if "df=3" in str(
            factor
        ) else None
        if name:
            transform = next(iter(info.state["transforms"].values()))
            spline_states[name] = {
                "knots": transform._all_knots.tolist(),
                "constraints": transform._constraints.tolist(),
            }
    return E1Fit(result, formula, eligible, excluded, counts, spline_states)


def _main_effect(result: Any, condition: str) -> str:
    prefix = (
        f'C({condition}, Treatment(reference="Não"), '
        'levels=["Não", "Sim", "Ausente"])[T.Sim]'
    )
    if prefix not in result.params.index:
        raise ValueError(f"coeficiente principal ausente no E1: {condition}")
    return prefix


def odds_ratio_tables(fit: E1Fit) -> tuple[pd.DataFrame, pd.DataFrame]:
    """ORs dos efeitos principais e interações; BH a 5% nos pares."""
    result = fit.result
    confidence = result.conf_int()
    main_rows = []
    for condition in COMORBIDADES:
        term = _main_effect(result, condition)
        estimate = float(result.params[term])
        lower, upper = confidence.loc[term]
        main_rows.append({
            "comorbidade": condition,
            "or": float(np.exp(estimate)),
            "ic_inf": float(np.exp(lower)),
            "ic_sup": float(np.exp(upper)),
        })

    pair_rows = []
    for first, second in fit.eligible_pairs:
        term = f"{first}_sim:{second}_sim"
        if term not in result.params.index:
            term = f"{second}_sim:{first}_sim"
        estimate = float(result.params[term])
        lower, upper = confidence.loc[term]
        pair_rows.append({
            "comorbidade_a": first,
            "comorbidade_b": second,
            "or_interacao": float(np.exp(estimate)),
            "ic_inf": float(np.exp(lower)),
            "ic_sup": float(np.exp(upper)),
            "p": float(result.pvalues[term]),
        })
    pairs = pd.DataFrame(pair_rows)
    if not pairs.empty:
        pairs["p_ajustado"] = multipletests(pairs["p"], method="fdr_bh")[1]
    else:
        pairs["p_ajustado"] = pd.Series(dtype=float)
    return pd.DataFrame(main_rows), pairs


def reri_ap_table(fit: E1Fit, reference_profile: dict[str, Any]) -> pd.DataFrame:
    """Calcula RERI/AP e IC delta no perfil de referência explicitamente informado."""
    required = {"idade_anos", "sexo", "gestante"}
    if required - reference_profile.keys():
        raise ValueError(f"reference_profile precisa de: {', '.join(sorted(required))}")
    reference_age = float(reference_profile["idade_anos"])
    reference_sex = reference_profile["sexo"]
    reference_pregnancy = reference_profile["gestante"]
    if not 0 <= reference_age <= 120 or reference_sex not in {"F", "M", "I"}:
        raise ValueError("perfil de referência precisa ter idade 0–120 e sexo F/M/I")
    if not isinstance(reference_pregnancy, (bool, np.bool_, int, np.integer)) or (
        reference_pregnancy not in (0, 1)
    ):
        raise ValueError("gestante do perfil de referência deve ser booleano ou 0/1")
    result = fit.result
    design_info = result.model.data.orig_exog.design_info
    beta = np.asarray(result.params)
    covariance = np.asarray(result.cov_params())

    def row_for(first: str | None = None, second: str | None = None) -> pd.DataFrame:
        values: dict[str, Any] = {
            "idade_anos": [reference_age],
            "sexo": pd.Categorical([reference_sex], categories=["F", "M", "I"]),
            "gestante": [int(bool(reference_pregnancy))],
        }
        for condition in COMORBIDADES:
            labels = []
            if condition == first or condition == second:
                labels.append("Sim")
            else:
                labels.append("Não")
            values[condition] = pd.Categorical(labels, categories=["Não", "Sim", "Ausente"])
            values[f"{condition}_sim"] = [int(labels[0] == "Sim")]
        return pd.DataFrame(values)

    rows = []
    for first, second in fit.eligible_pairs:
        design_rows = [
            np.asarray(patsy.build_design_matrices([design_info], row_for(*pair))[0])[0]
            for pair in ((None, None), (first, None), (None, second), (first, second))
        ]
        base, only_first, only_second, combined = design_rows
        contrast_first, contrast_second, contrast_both = (
            only_first - base, only_second - base, combined - base
        )
        or_first, or_second, or_both = np.exp([
            contrast_first @ beta, contrast_second @ beta, contrast_both @ beta,
        ])
        reri = float(or_both - or_first - or_second + 1)
        ap = float(reri / or_both)
        gradient_reri = (
            or_both * contrast_both - or_first * contrast_first - or_second * contrast_second
        )
        variance_reri = float(gradient_reri @ covariance @ gradient_reri)
        se_reri = np.sqrt(max(variance_reri, 0))
        gradient_ap = gradient_reri / or_both - reri * contrast_both
        variance_ap = float(gradient_ap @ covariance @ gradient_ap)
        se_ap = np.sqrt(max(variance_ap, 0))
        rows.append({
            "comorbidade_a": first,
            "comorbidade_b": second,
            "or_a": float(or_first),
            "or_b": float(or_second),
            "or_ab": float(or_both),
            "reri": reri,
            "reri_ic_inf": reri - 1.96 * se_reri,
            "reri_ic_sup": reri + 1.96 * se_reri,
            "ap": ap,
            "ap_ic_inf": ap - 1.96 * se_ap,
            "ap_ic_sup": ap + 1.96 * se_ap,
        })
    return pd.DataFrame(rows)


def rank_comorbidities(main_effects: pd.DataFrame) -> pd.DataFrame:
    """Ordena por OR e marca pares de IC sobrepostos como sem ordem definida."""
    required = {"comorbidade", "or", "ic_inf", "ic_sup"}
    if required - set(main_effects.columns):
        raise ValueError("main_effects precisa de comorbidade, or, ic_inf e ic_sup")
    ordered = main_effects.sort_values("or", ascending=False).reset_index(drop=True).copy()
    no_order = {condition: set() for condition in ordered["comorbidade"]}
    for row_a, row_b in combinations(ordered.itertuples(index=False), 2):
        if max(row_a.ic_inf, row_b.ic_inf) <= min(row_a.ic_sup, row_b.ic_sup):
            no_order[row_a.comorbidade].add(row_b.comorbidade)
            no_order[row_b.comorbidade].add(row_a.comorbidade)
    ordered["sem_ordem_definida_com"] = ordered["comorbidade"].map(
        lambda condition: ", ".join(sorted(no_order[condition]))
    )
    return ordered


def profiles_table(
    fit: E1Fit,
    frame: pd.DataFrame,
    pair_counts: pd.DataFrame,
    combinations_3plus: pd.DataFrame,
    age_references: dict[str, float],
    gestante: bool,
    minimum_cases: int = 10,
) -> pd.DataFrame:
    """Calcula perfis observados e riscos; idade de referência e gestação são explícitas."""
    assert_dev_only(frame)
    if set(age_references) != set(FAIXAS_ROTULOS):
        raise ValueError(f"age_references deve definir exatamente: {', '.join(FAIXAS_ROTULOS)}")
    if minimum_cases < 1:
        raise ValueError("minimum_cases deve ser positivo")
    if not isinstance(gestante, bool):
        raise ValueError("gestante deve ser booleano")
    for label, age in age_references.items():
        if not 0 <= age <= 120:
            raise ValueError(f"idade de referência inválida para {label}: {age}")

    present = {
        column: code(frame[column]).eq("1") | frame[column].astype("string").eq("Sim")
        for column in COMORBIDADES
    }

    def exact_profile(profile: tuple[str, ...]) -> pd.Series:
        return pd.concat(
            [present[column] if column in profile else ~present[column]
             for column in COMORBIDADES],
            axis=1,
        ).all(axis=1)

    eligible = set(fit.eligible_pairs)
    all_pairs = {
        (row.comorbidade_a, row.comorbidade_b)
        for row in pair_counts.itertuples(index=False)
    }
    profiles: list[tuple[str, tuple[str, ...], str]] = [
        ("Sem comorbidades", (), "referência")
    ]
    profiles.extend((column, (column,), "individual") for column in COMORBIDADES)
    profiles.extend(
        (f"{first} + {second}", (first, second),
         "par" if (first, second) in eligible else "dados insuficientes")
        for first, second in sorted(all_pairs)
    )
    profiles.extend(
        (row.comorbidades, tuple(row.comorbidades.split(", ")), "3 ou mais")
        for row in combinations_3plus.itertuples(index=False)
        if row.casos >= minimum_cases
    )
    bundle = compact_e1(fit)
    rows = []

    for age_band in FAIXAS_ROTULOS:
        for sex in ("F", "M"):
            reference = pd.DataFrame([{
                "idade_anos": age_references[age_band],
                "CS_SEXO": sex,
                "gestante": gestante,
                **{column: "2" for column in COMORBIDADES},
            }])
            reference_risk = float(predict_e1(bundle, reference).iloc[0]["risco"])
            band_mask = frame["faixa_etaria"].astype("string").eq(age_band)
            sex_mask = code(frame["CS_SEXO"]).eq(sex)
            for label, profile, status in profiles:
                observed = exact_profile(profile) & band_mask & sex_mask
                cases = int(observed.sum())
                if cases < minimum_cases:
                    continue
                base = {
                    "perfil": label,
                    "grupo": status,
                    "faixa_etaria": age_band,
                    "idade_referencia": age_references[age_band],
                    "sexo": sex,
                    "gestante": gestante,
                    "casos": cases,
                }
                if status == "dados insuficientes":
                    rows.append({**base, "risco": np.nan, "ic_inf": np.nan, "ic_sup": np.nan,
                                 "razao_referencia": np.nan, "nota": "eventos insuficientes"})
                    continue
                prediction = pd.DataFrame([{
                    "idade_anos": age_references[age_band],
                    "CS_SEXO": sex,
                    "gestante": gestante,
                    **{column: "1" if column in profile else "2" for column in COMORBIDADES},
                }])
                risk = predict_e1(bundle, prediction).iloc[0]
                note = (
                    "risco estimado pela soma dos efeitos individuais e dos pares; "
                    "o E1 não tem termo próprio para o trio"
                    if len(profile) >= 3 else ""
                )
                rows.append({
                    **base,
                    "risco": float(risk["risco"]),
                    "ic_inf": float(risk["ic_inf"]),
                    "ic_sup": float(risk["ic_sup"]),
                    "razao_referencia": float(risk["risco"] / reference_risk),
                    "nota": note,
                })
    return pd.DataFrame(rows)


def _markdown_table(frame: pd.DataFrame) -> str:
    headers = [str(column) for column in frame.columns]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(str(value) for value in row) + " |"
                 for row in frame.itertuples(index=False, name=None))
    return "\n".join(lines)


def compact_e1(fit: E1Fit) -> E1Bundle:
    """Remove o objeto statsmodels e os dados de ajuste, mantendo só parâmetros e desenho."""
    return E1Bundle(
        formula=fit.formula,
        columns=tuple(map(str, fit.result.params.index)),
        coefficients=np.asarray(fit.result.params, dtype=np.float64),
        covariance=np.asarray(fit.result.cov_params(), dtype=np.float64),
        spline_states=fit.spline_states,
    )


def _prediction_formula(bundle: E1Bundle) -> str:
    formula = bundle.formula.partition("~")[2]
    for name, degrees in (("age_main", 5), ("age_condition", 3)):
        state = bundle.spline_states[name]
        knots = state["knots"]
        explicit = (
            "cr(idade_anos, "
            f"knots={knots[1:-1]!r}, lower_bound={knots[0]!r}, "
            f"upper_bound={knots[-1]!r}, constraints={state['constraints']!r})"
        )
        original = f'cr(idade_anos, df={degrees}, constraints="center")'
        formula = formula.replace(original, explicit)
    return formula


def predict_e1(
    bundle: E1Bundle, frame: pd.DataFrame, confidence: float = 0.95,
) -> pd.DataFrame:
    """Risco e IC delta de E1 para perfis, usando apenas parâmetros e estado dos splines."""
    if not 0 < confidence < 1:
        raise ValueError("confidence deve estar entre 0 e 1")
    prepared = _prepare(frame)
    design = patsy.dmatrix(
        _prediction_formula(bundle), data=prepared, return_type="dataframe"
    )
    if design.shape[1] != len(bundle.columns):
        raise RuntimeError("colunas do desenho de predição diferem das do modelo ajustado")
    design.columns = bundle.columns
    matrix = np.asarray(design, dtype=np.float64)
    link = matrix @ bundle.coefficients
    variance = np.einsum("ij,jk,ik->i", matrix, bundle.covariance, matrix)
    standard_error = np.sqrt(np.maximum(variance, 0))
    z = float(norm.ppf((1 + confidence) / 2))
    return pd.DataFrame({
        "risco": expit(link),
        "ic_inf": expit(link - z * standard_error),
        "ic_sup": expit(link + z * standard_error),
    }, index=frame.index)


def write_e1_reports(
    fit: E1Fit,
    output_dir: str | Path,
    reference_profile: dict[str, Any],
    profiles: pd.DataFrame | None = None,
) -> None:
    """Escreve resumos agregados do E1 sem exportar a matriz nem as observações usadas."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    main, pairs = odds_ratio_tables(fit)
    reri = reri_ap_table(fit, reference_profile)
    ranking = rank_comorbidities(main)
    (output / "coeficientes.md").write_text(
        "# Modelo E1\n\n"
        f"Convergiu: {bool(fit.result.mle_retvals.get('converged', False))}.\n\n"
        f"```text\n{fit.result.summary()}\n```\n",
        encoding="utf-8",
    )
    (output / "or_interacoes.md").write_text(
        "# OR e interações\n\n"
        f"## Efeitos principais\n\n{_markdown_table(main)}\n\n"
        f"## Interações entre pares elegíveis\n\n{_markdown_table(pairs)}\n\n"
        f"Pares sem eventos suficientes: {fit.excluded_pairs}\n",
        encoding="utf-8",
    )
    (output / "reri_ap.md").write_text(
        "# Interação aditiva\n\n"
        f"{_markdown_table(reri)}\n",
        encoding="utf-8",
    )
    (output / "ranking.md").write_text(
        "# Ranking de comorbidades por OR ajustado\n\n"
        f"{_markdown_table(ranking)}\n",
        encoding="utf-8",
    )
    if profiles is not None:
        public_profiles = profiles.drop(columns=["casos"], errors="ignore")
        (output / "perfis_completo.md").write_text(
            "# Perfis do E1\n\n"
            "Riscos são estimados pelo modelo explicativo. Células com menos de 10 casos foram "
            "suprimidas antes da geração desta tabela.\n\n"
            f"{_markdown_table(public_profiles)}\n",
            encoding="utf-8",
        )
