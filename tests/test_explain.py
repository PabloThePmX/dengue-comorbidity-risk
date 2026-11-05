import numpy as np
import pandas as pd

from dengue_sinan.descriptive import combination_counts
from dengue_sinan.explain import (
    _prepare,
    compact_e1,
    fit_e1,
    odds_ratio_tables,
    predict_e1,
    profiles_table,
    rank_comorbidities,
    reri_ap_table,
)
from dengue_sinan.profiling import COMORBIDADES, FAIXAS, FAIXAS_ROTULOS


def _e1_frame():
    rng = np.random.default_rng(20261103)
    size = 3000
    data = pd.DataFrame({
        "ANO": 2022,
        "idade_anos": rng.uniform(0, 100, size),
        "CS_SEXO": rng.choice(["F", "M", "I"], size, p=[0.49, 0.49, 0.02]),
        "gestante": rng.binomial(1, 0.03, size),
    })
    for column in COMORBIDADES:
        data[column] = rng.choice(["1", "2", "9"], size, p=[0.4, 0.55, 0.05])
    diabetes = data["DIABETES"].eq("1").to_numpy()
    probability = np.where(diabetes, 0.3, 0.1)
    data["y"] = rng.binomial(1, probability)
    return data


def test_e1_fits_only_pairs_meeting_event_threshold_and_reports_effects():
    pairs = pd.DataFrame([
        {"comorbidade_a": first, "comorbidade_b": second,
         "eventos": 20 if (first, second) == ("DIABETES", "HEMATOLOG") else 0}
        for index, first in enumerate(COMORBIDADES)
        for second in COMORBIDADES[index + 1:]
    ])
    fit = fit_e1(_e1_frame(), pair_counts=pairs)
    assert fit.eligible_pairs == (("DIABETES", "HEMATOLOG"),)
    assert "DIABETES_sim:HEMATOLOG_sim" in fit.formula
    main, interactions = odds_ratio_tables(fit)
    assert len(main) == 7
    assert len(interactions) == 1
    assert 0 <= interactions.loc[0, "p_ajustado"] <= 1
    reri = reri_ap_table(fit, {"idade_anos": 40, "sexo": "F", "gestante": False})
    assert len(reri) == 1
    assert reri.loc[0, "reri_ic_inf"] <= reri.loc[0, "reri_ic_sup"]
    compact = compact_e1(fit)
    predictions = predict_e1(compact, _e1_frame().iloc[:20])
    expected = fit.result.predict(_prepare(_e1_frame().iloc[:20]))
    assert np.allclose(predictions["risco"], expected, atol=1e-9)


def test_rank_marks_overlapping_intervals_as_tied():
    table = pd.DataFrame([
        {"comorbidade": "A", "or": 2.0, "ic_inf": 1.0, "ic_sup": 3.0},
        {"comorbidade": "B", "or": 1.5, "ic_inf": 1.2, "ic_sup": 2.2},
        {"comorbidade": "C", "or": 0.8, "ic_inf": 0.5, "ic_sup": 0.9},
    ])
    ranked = rank_comorbidities(table).set_index("comorbidade")
    assert ranked.loc["A", "sem_ordem_definida_com"] == "B"
    assert ranked.loc["B", "sem_ordem_definida_com"] == "A"
    assert ranked.loc["C", "sem_ordem_definida_com"] == ""


def test_profiles_are_generated_from_observed_pairs_and_combinations():
    frame = _e1_frame()
    frame["faixa_etaria"] = pd.cut(
        frame["idade_anos"], FAIXAS, right=False, labels=FAIXAS_ROTULOS
    )
    counts = pd.DataFrame([
        {"comorbidade_a": first, "comorbidade_b": second,
         "eventos": 20 if (first, second) == ("DIABETES", "HEMATOLOG") else 0}
        for index, first in enumerate(COMORBIDADES)
        for second in COMORBIDADES[index + 1:]
    ])
    fit = fit_e1(frame, pair_counts=counts)
    profiles = profiles_table(
        fit,
        frame,
        counts,
        combination_counts(frame),
        dict(zip(FAIXAS_ROTULOS, [2, 10, 27.5, 50, 70, 90], strict=True)),
        gestante=False,
    )
    assert not profiles.empty
    assert (profiles["casos"] >= 10).all()
    assert set(profiles["sexo"]) <= {"F", "M"}
    triple_profiles = profiles.loc[profiles["grupo"] == "3 ou mais"]
    assert triple_profiles.empty or triple_profiles["nota"].str.contains(
        "não tem termo próprio"
    ).all()
