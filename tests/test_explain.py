import numpy as np
import pandas as pd
import patsy
import pytest

from dengue_sinan.explain import (
    _analysis_frame,
    _e1_formula,
    fit_e1,
    odds_ratio_tables,
    rank_comorbidities,
    reri_ap,
)
from dengue_sinan.profiling import COMORBIDADES, SINAIS, add_derived


def _development_data(rows=1400):
    data = {name: ["2"] * rows for name in COMORBIDADES + SINAIS}
    rng = np.random.default_rng(2026)
    for name in COMORBIDADES:
        data[name] = rng.choice(["1", "2", "9"], size=rows, p=[0.2, 0.75, 0.05])
    age = rng.integers(1, 100, size=rows)
    risk = (
        -1.7
        + 0.02 * (age - 50)
        + 0.75 * np.array([int(value == "1") for value in data["DIABETES"]])
        + 0.45 * np.array([int(value == "1") for value in data["RENAL"]])
    )
    probability = 1 / (1 + np.exp(-risk))
    outcome = rng.binomial(1, probability)
    sex = rng.choice(["M", "F", "I"], size=rows, p=[0.46, 0.48, 0.06])
    pregnant = rng.binomial(1, 0.08, size=rows)
    data.update(
        {
            "ANO": [2022] * rows,
            "CLASSI_FIN": ["12" if value else "10" for value in outcome],
            "EVOLUCAO": ["1"] * rows,
            "NU_IDADE_N": [f"4{int(value):03d}" for value in age],
            "ANO_NASC": ["1980"] * rows,
            "DT_SIN_PRI": ["20220101"] * rows,
            "DT_NOTIFIC": ["20220102"] * rows,
            "CS_SEXO": sex,
            "CS_GESTANT": ["1" if value else "5" for value in pregnant],
            "CS_RACA": ["1"] * rows,
            "ID_MN_RESI": ["355030"] * rows,
            "SG_UF": ["35"] * rows,
        }
    )
    return add_derived(pd.DataFrame(data))


@pytest.fixture(scope="module")
def fitted_e1():
    return fit_e1(_development_data(5000))


def test_e1_fits_without_penalty_and_reports_pairs(fitted_e1):
    model, included, omitted = fitted_e1
    assert model.converged
    assert len(included) + len(omitted) == 21
    assert (included["eventos"] >= 10).all()


def test_qr_splines_preserve_model_space_and_map_covariance(fitted_e1):
    model, included, _ = fitted_e1
    raw_analysis = _analysis_frame(_development_data(5000))
    _, raw_design = patsy.dmatrices(
        _e1_formula(included), data=raw_analysis, return_type="dataframe"
    )
    qr_design = model.model._e1_qr_design
    transformed_design = qr_design.transform(raw_analysis)

    raw_rank = np.linalg.matrix_rank(raw_design.to_numpy())
    qr_rank = np.linalg.matrix_rank(transformed_design.to_numpy())
    assert raw_rank == qr_rank == transformed_design.shape[1]

    rng = np.random.default_rng(42)
    for _, basis, exposure in qr_design.spline_blocks:
        raw_basis = patsy.build_design_matrices(
            [basis.design_info], raw_analysis, return_type="dataframe"
        )[0].to_numpy()
        gamma = rng.normal(size=basis.rotation.shape[1])
        mapped_beta = basis.rotation @ gamma
        qr_values = basis.transform(raw_analysis).to_numpy() @ gamma
        raw_values = raw_basis @ mapped_beta
        if exposure is not None:
            indicator = raw_analysis[exposure].to_numpy()
            qr_values *= indicator
            raw_values *= indicator
        np.testing.assert_allclose(qr_values, raw_values, atol=1e-10)

    mapped, mapped_covariance = qr_design.mapped_spline_coefficients(model)
    assert mapped_covariance.shape == (len(mapped), len(mapped))
    assert np.isfinite(mapped_covariance).all()
    np.testing.assert_allclose(mapped_covariance, mapped_covariance.T, atol=1e-10)
    assert np.isfinite(mapped["erro_padrao"]).all()


def test_e1_rejects_test_year():
    df = _development_data(100)
    df["ANO"] = 2024
    with pytest.raises(RuntimeError, match="2024 é teste congelado"):
        fit_e1(df)


def test_or_tables_contain_main_and_pair_effects(fitted_e1):
    model, included, _ = fitted_e1
    main, interactions = odds_ratio_tables(model, included)
    assert len(main) == 7
    assert len(interactions) == len(included)
    assert "p_ajustado" in interactions


def test_reri_requires_explicit_reference_profile(fitted_e1):
    model, included, _ = fitted_e1
    result = reri_ap(
        model,
        included.head(1),
        idade_referencia=50,
        sexo_referencia="M",
        gestante_referencia=False,
    )
    assert len(result) == 1
    assert np.isfinite(result.loc[0, "reri"])
    assert result.loc[0, "reri_ic_inferior"] <= result.loc[0, "reri_ic_superior"]


def test_ranking_marks_overlapping_intervals_as_incomparable():
    effects = pd.DataFrame(
        {
            "comorbidade": ["A", "B", "C"],
            "or": [2.0, 1.8, 1.2],
            "ic_inferior": [1.2, 1.1, 0.8],
            "ic_superior": [3.0, 2.8, 1.0],
        }
    )
    ranking = rank_comorbidities(effects)
    assert "B" in ranking.loc[0, "sem_ordem_definida_com"]
    assert "C" not in ranking.loc[0, "sem_ordem_definida_com"]