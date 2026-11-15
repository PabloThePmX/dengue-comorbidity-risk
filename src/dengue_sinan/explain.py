"""Modelo explicativo E1 e medidas de associação das comorbidades."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import patsy
import statsmodels.api as sm
from scipy.linalg import qr
from scipy.stats import norm
from statsmodels.stats.multitest import multipletests

from dengue_sinan.dataset import COMORBIDITY_FEATURES, build_feature_frame
from dengue_sinan.descriptive import pair_event_counts
from dengue_sinan.guard import assert_dev_only
from dengue_sinan.profiling import COMORBIDADES
from dengue_sinan.reporting import markdown_table


@dataclass
class _CenteredQRSpline:
    design_info: patsy.DesignInfo
    center: np.ndarray
    rotation: np.ndarray
    source_names: list[str]
    feature_names: list[str]

    @classmethod
    def fit(
        cls,
        analysis: pd.DataFrame,
        center_mask: np.ndarray,
        degrees_of_freedom: int,
        prefix: str,
    ) -> "_CenteredQRSpline":
        raw = patsy.dmatrix(
            f"cr(idade_anos, df={degrees_of_freedom}) - 1",
            data=analysis,
            return_type="dataframe",
        )
        values = raw.to_numpy(dtype=float)
        mask = np.asarray(center_mask, dtype=bool)
        if mask.shape != (len(analysis),) or not mask.any():
            raise ValueError(f"Não há linhas para centralizar o spline {prefix}.")
        center = values[mask].mean(axis=0)
        if not np.isfinite(center).all() or np.linalg.norm(center) == 0:
            raise ValueError(f"Centro inválido para o spline {prefix}.")
        orthogonal, _ = qr(center[:, None], mode="full")
        rotation = orthogonal[:, 1:]
        transformed = (values - center) @ rotation
        if np.linalg.matrix_rank(transformed) != rotation.shape[1]:
            raise ValueError(f"A base QR do spline {prefix} não tem posto completo.")
        return cls(
            design_info=raw.design_info,
            center=center,
            rotation=rotation,
            source_names=list(raw.columns),
            feature_names=[f"{prefix}_qr_{index + 1}" for index in range(rotation.shape[1])],
        )

    def transform(self, analysis: pd.DataFrame) -> pd.DataFrame:
        raw = patsy.build_design_matrices(
            [self.design_info], analysis, return_type="dataframe"
        )[0]
        transformed = (raw.to_numpy(dtype=float) - self.center) @ self.rotation
        return pd.DataFrame(transformed, index=analysis.index, columns=self.feature_names)


@dataclass
class _E1QRDesign:
    age: _CenteredQRSpline
    hypertension: _CenteredQRSpline
    diabetes: _CenteredQRSpline
    pairs: pd.DataFrame

    @property
    def spline_blocks(self) -> list[tuple[str, _CenteredQRSpline, str | None]]:
        return [
            ("idade_anos", self.age, None),
            ("hipertensa", self.hypertension, "hipertensa_sim"),
            ("diabetes", self.diabetes, "diabetes_sim"),
        ]

    def transform(self, analysis: pd.DataFrame) -> pd.DataFrame:
        design = pd.DataFrame(index=analysis.index)
        design["Intercept"] = 1.0
        design[self.age.feature_names] = self.age.transform(analysis)
        for column in ("sexo_F", "sexo_I", "gestante"):
            design[column] = analysis[column].astype(float)
        for feature in COMORBIDITY_FEATURES:
            design[f"{feature}_sim"] = analysis[f"{feature}_sim"].astype(float)
            design[f"{feature}_ausente"] = analysis[f"{feature}_ausente"].astype(float)
        for first, second in _pair_feature_names(self.pairs):
            name = f"{first}_sim:{second}_sim"
            design[name] = (
                analysis[f"{first}_sim"] * analysis[f"{second}_sim"]
            ).astype(float)
        for basis, exposure in (
            (self.hypertension, "hipertensa_sim"),
            (self.diabetes, "diabetes_sim"),
        ):
            interactions = basis.transform(analysis).mul(analysis[exposure], axis=0)
            interactions.columns = [
                f"{exposure}:{column}" for column in basis.feature_names
            ]
            design[interactions.columns] = interactions
        return design

    def mapped_spline_coefficients(
        self, result
    ) -> tuple[pd.DataFrame, np.ndarray]:
        params = result.params
        covariance = np.asarray(result.cov_params(), dtype=float)
        mapped_rows = []
        mapping_rows = []
        fit_names = list(params.index)
        for block_name, basis, exposure in self.spline_blocks:
            fitted_names = (
                basis.feature_names
                if exposure is None
                else [f"{exposure}:{column}" for column in basis.feature_names]
            )
            for name in basis.source_names:
                mapped_rows.append(
                    {
                        "bloco": block_name,
                        "termo_original": name if exposure is None else f"{exposure}:{name}",
                    }
                )
            for index, _name in enumerate(basis.source_names):
                row = np.zeros(len(fit_names), dtype=float)
                for column, fitted_name in enumerate(fitted_names):
                    row[fit_names.index(fitted_name)] = basis.rotation[index, column]
                mapping_rows.append(row)
        mapping = np.vstack(mapping_rows)
        mapped_coefficients = mapping @ params.to_numpy(dtype=float)
        mapped_covariance = mapping @ covariance @ mapping.T
        standard_errors = np.sqrt(np.maximum(np.diag(mapped_covariance), 0))
        table = pd.DataFrame(mapped_rows)
        table["coeficiente"] = mapped_coefficients
        table["erro_padrao"] = standard_errors
        table["ic_inferior"] = table["coeficiente"] - 1.96 * table["erro_padrao"]
        table["ic_superior"] = table["coeficiente"] + 1.96 * table["erro_padrao"]
        return table, mapped_covariance


def _analysis_frame(df: pd.DataFrame) -> pd.DataFrame:
    features = build_feature_frame(df)
    analysis = pd.DataFrame(index=df.index)
    analysis["y"] = df["y"].astype(int)
    analysis["idade_anos"] = features["idade_anos"]
    analysis["sexo_F"] = features["sexo"].eq("F").astype(int)
    analysis["sexo_I"] = features["sexo"].eq("I").astype(int)
    analysis["gestante"] = features["gestante"].astype(int)
    for feature in COMORBIDITY_FEATURES:
        analysis[f"{feature}_sim"] = features[feature].eq("Sim").astype(int)
        analysis[f"{feature}_ausente"] = features[feature].eq("Ausente").astype(int)
    return analysis


def _pair_feature_names(pairs: pd.DataFrame) -> list[tuple[str, str]]:
    mapping = dict(zip(COMORBIDADES, COMORBIDITY_FEATURES, strict=True))
    return [
        (mapping[first], mapping[second])
        for first, second in pairs[["comorbidade_1", "comorbidade_2"]].itertuples(
            index=False, name=None
        )
    ]


def _e1_formula(pairs: pd.DataFrame) -> str:
    terms = ["cr(idade_anos, df=5)", "sexo_F", "sexo_I", "gestante"]
    for feature in COMORBIDITY_FEATURES:
        terms.extend((f"{feature}_sim", f"{feature}_ausente"))
    terms.extend(f"{first}_sim:{second}_sim" for first, second in _pair_feature_names(pairs))
    terms.extend(
        [
            "hipertensa_sim:cr(idade_anos, df=3)",
            "diabetes_sim:cr(idade_anos, df=3)",
        ]
    )
    return "y ~ " + " + ".join(terms)


def fit_e1(df: pd.DataFrame, reports_dir: str | Path | None = None):
    """Ajusta E1 sem penalização e inclui interações com pelo menos 10 eventos."""
    assert_dev_only(df)
    if "y" not in df:
        raise ValueError("DataFrame deve conter o desfecho y.")
    pairs = pair_event_counts(df)
    included = pairs[pairs["eventos"] >= 10].reset_index(drop=True)
    omitted = pairs[pairs["eventos"] < 10].reset_index(drop=True)
    analysis = _analysis_frame(df)
    hypertension = analysis["hipertensa_sim"].to_numpy(dtype=bool)
    diabetes = analysis["diabetes_sim"].to_numpy(dtype=bool)
    qr_design = _E1QRDesign(
        age=_CenteredQRSpline.fit(
            analysis, np.ones(len(analysis), dtype=bool), 5, "idade"
        ),
        hypertension=_CenteredQRSpline.fit(analysis, hypertension, 3, "idade_hipertensa"),
        diabetes=_CenteredQRSpline.fit(analysis, diabetes, 3, "idade_diabetes"),
        pairs=included,
    )
    design_matrix = qr_design.transform(analysis)
    result = sm.GLM(analysis["y"], design_matrix, family=sm.families.Binomial()).fit(
        maxiter=200
    )
    result.model._e1_qr_design = qr_design
    if not result.converged:
        raise RuntimeError(
            "E1 não convergiu após 200 iterações; registre o problema antes de tentar correções."
        )
    if not np.isfinite(result.cov_params().to_numpy()).all():
        raise RuntimeError("E1 convergiu sem covariância finita; não é possível calcular IC.")
    if reports_dir is not None:
        output = Path(reports_dir) / "e1"
        output.mkdir(parents=True, exist_ok=True)
        (output / "coeficientes.md").write_text(
            "# E1 — regressão logística sem penalização\n\n"
            + result.summary().as_text()
            + "\n\n## Coeficientes spline mapeados à base original\n\n"
            + markdown_table(qr_design.mapped_spline_coefficients(result)[0])
            + "\n",
            encoding="utf-8",
        )
        _write_table(omitted, output / "pares_eventos_insuficientes.md",
                     "Pares sem eventos suficientes")
    return result, included, omitted


def _write_table(table: pd.DataFrame, path: Path, title: str) -> None:
    path.write_text(
        f"# {title}\n\n{markdown_table(table)}\n",
        encoding="utf-8",
    )


def odds_ratio_tables(result, pairs: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Extrai OR/IC de efeitos principais e interações, com FDR nos pares."""
    intervals = result.conf_int()
    main_rows = []
    for source, feature in zip(COMORBIDADES, COMORBIDITY_FEATURES, strict=True):
        term = f"{feature}_sim"
        main_rows.append(
            {
                "comorbidade": source,
                "termo": term,
                "or": float(np.exp(result.params[term])),
                "ic_inferior": float(np.exp(intervals.loc[term, 0])),
                "ic_superior": float(np.exp(intervals.loc[term, 1])),
                "p": float(result.pvalues[term]),
            }
        )

    pair_rows = []
    for first, second in _pair_feature_names(pairs):
        term = f"{first}_sim:{second}_sim"
        pair_rows.append(
            {
                "comorbidade_1": COMORBIDADES[COMORBIDITY_FEATURES.index(first)],
                "comorbidade_2": COMORBIDADES[COMORBIDITY_FEATURES.index(second)],
                "termo": term,
                "or_interacao": float(np.exp(result.params[term])),
                "ic_inferior": float(np.exp(intervals.loc[term, 0])),
                "ic_superior": float(np.exp(intervals.loc[term, 1])),
                "p": float(result.pvalues[term]),
            }
        )
    pairs_table = pd.DataFrame(pair_rows)
    if not pairs_table.empty:
        pairs_table["p_ajustado"] = multipletests(pairs_table["p"], method="fdr_bh")[1]
    return pd.DataFrame(main_rows), pairs_table


def write_odds_ratio_report(
    result, pairs: pd.DataFrame, reports_dir: str | Path
) -> tuple[pd.DataFrame, pd.DataFrame]:
    output = Path(reports_dir) / "e1"
    output.mkdir(parents=True, exist_ok=True)
    main, interactions = odds_ratio_tables(result, pairs)
    _write_table(
        pd.concat(
            [
                main.assign(tipo="efeito principal").rename(columns={"comorbidade": "par"}),
                interactions.assign(tipo="interação").rename(
                    columns={
                        "comorbidade_1": "par",
                        "comorbidade_2": "par_2",
                        "or_interacao": "or",
                    }
                ),
            ],
            ignore_index=True,
        ),
        output / "or_interacoes.md",
        "OR e intervalos de confiança do E1",
    )
    return main, interactions


def _design_vector(
    result,
    idade: float,
    sexo: str,
    gestante: bool,
    comorbidades: set[str],
) -> np.ndarray:
    row = {
        "idade_anos": idade,
        "sexo_F": int(sexo == "F"),
        "sexo_I": int(sexo == "I"),
        "gestante": int(gestante),
    }
    for feature, source in zip(COMORBIDITY_FEATURES, COMORBIDADES, strict=True):
        row[f"{feature}_sim"] = int(source in comorbidades)
        row[f"{feature}_ausente"] = 0
    qr_design = getattr(result.model, "_e1_qr_design", None)
    if qr_design is None:
        raise ValueError("O modelo E1 não contém metadados da parametrização QR.")
    design = qr_design.transform(pd.DataFrame([row]))
    return design.loc[:, result.params.index].to_numpy(dtype=float)[0]


def reri_ap(
    result,
    pairs: pd.DataFrame,
    *,
    idade_referencia: float,
    sexo_referencia: str,
    gestante_referencia: bool,
) -> pd.DataFrame:
    """Calcula RERI/AP e IC delta; exige perfil de referência explícito."""
    if sexo_referencia not in {"F", "M"}:
        raise ValueError("sexo_referencia deve ser F ou M.")
    covariance = np.asarray(result.cov_params(), dtype=float)
    beta = np.asarray(result.params, dtype=float)
    rows = []
    for source_first, source_second in pairs[
        ["comorbidade_1", "comorbidade_2"]
    ].itertuples(index=False, name=None):
        x0 = _design_vector(result, idade_referencia, sexo_referencia, gestante_referencia, set())
        x_a = _design_vector(
            result, idade_referencia, sexo_referencia, gestante_referencia, {source_first}
        )
        x_b = _design_vector(
            result, idade_referencia, sexo_referencia, gestante_referencia, {source_second}
        )
        x_ab = _design_vector(
            result,
            idade_referencia,
            sexo_referencia,
            gestante_referencia,
            {source_first, source_second},
        )
        contrast_a, contrast_b, contrast_ab = x_a - x0, x_b - x0, x_ab - x0
        or_a, or_b, or_ab = (
            np.exp(float(contrast @ beta))
            for contrast in (contrast_a, contrast_b, contrast_ab)
        )
        reri = or_ab - or_a - or_b + 1
        gradient_reri = or_ab * contrast_ab - or_a * contrast_a - or_b * contrast_b
        variance_reri = float(gradient_reri @ covariance @ gradient_reri)
        se_reri = np.sqrt(max(variance_reri, 0))
        ap = reri / or_ab
        gradient_ap = (gradient_reri - reri * contrast_ab) / or_ab
        variance_ap = float(gradient_ap @ covariance @ gradient_ap)
        se_ap = np.sqrt(max(variance_ap, 0))
        z = norm.ppf(0.975)
        rows.append(
            {
                "comorbidade_1": source_first,
                "comorbidade_2": source_second,
                "or_a": or_a,
                "or_b": or_b,
                "or_ab": or_ab,
                "reri": reri,
                "reri_ic_inferior": reri - z * se_reri,
                "reri_ic_superior": reri + z * se_reri,
                "ap": ap,
                "ap_ic_inferior": ap - z * se_ap,
                "ap_ic_superior": ap + z * se_ap,
            }
        )
    return pd.DataFrame(rows)


def write_reri_report(table: pd.DataFrame, reports_dir: str | Path) -> Path:
    output = Path(reports_dir) / "e1"
    output.mkdir(parents=True, exist_ok=True)
    path = output / "reri_ap.md"
    _write_table(table, path, "Interação aditiva — RERI e AP")
    return path


def rank_comorbidities(main_effects: pd.DataFrame) -> pd.DataFrame:
    """Ordena ORs e assinala pares com intervalos de confiança sobrepostos."""
    ordered = main_effects.sort_values("or", ascending=False).reset_index(drop=True).copy()
    incomparable = []
    for row in ordered.itertuples(index=False):
        overlaps = ordered[
            (ordered["comorbidade"] != row.comorbidade)
            & (ordered["ic_inferior"] <= row.ic_superior)
            & (ordered["ic_superior"] >= row.ic_inferior)
        ]["comorbidade"]
        incomparable.append(", ".join(overlaps.astype(str)))
    ordered["sem_ordem_definida_com"] = incomparable
    return ordered


def write_ranking_report(main_effects: pd.DataFrame, reports_dir: str | Path) -> Path:
    output = Path(reports_dir) / "e1"
    output.mkdir(parents=True, exist_ok=True)
    path = output / "ranking.md"
    _write_table(rank_comorbidities(main_effects), path, "Ranking descritivo por OR do E1")
    return path