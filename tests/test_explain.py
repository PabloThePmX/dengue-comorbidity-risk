"""Testes unitários do modelo E1, RERI/AP, ranking e tabela de perfis (T-3.1 a T-3.5)."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dengue_sinan.dataset import COMORBIDADES
from dengue_sinan.explain import (
    build_profile_specs,
    compute_reri_ap_from_params,
    rank_comorbidities,
    run_e1_pipeline,
)


def test_reri_and_ap_match_hand_calculation() -> None:
    # Coeficientes escolhidos para OR_A = 2.0, OR_B = 3.0, OR_AB = 2 * 3 * 1.5 = 9.0
    # RERI = 9.0 - 2.0 - 3.0 + 1.0 = 5.0
    # AP = 5.0 / 9.0 = 0.5555555...
    beta_a = float(np.log(2.0))
    beta_b = float(np.log(3.0))
    beta_ab = float(np.log(1.5))
    cov = np.diag([0.01, 0.01, 0.01])

    res = compute_reri_ap_from_params(beta_a, beta_b, beta_ab, cov)
    assert res["OR_A"] == pytest.approx(2.0)
    assert res["OR_B"] == pytest.approx(3.0)
    assert res["OR_AB"] == pytest.approx(9.0)
    assert res["RERI"] == pytest.approx(5.0)
    assert res["AP"] == pytest.approx(5.0 / 9.0)
    assert res["RERI_IC95_inf"] < res["RERI"] < res["RERI_IC95_sup"]
    assert res["AP_IC95_inf"] < res["AP"] < res["AP_IC95_sup"]


def test_rank_comorbidities_detects_ci_overlap() -> None:
    main_or = pd.DataFrame(
        [
            {"comorbidade": "RENAL", "OR": 4.0, "IC95_inf": 3.5, "IC95_sup": 4.6},
            {"comorbidade": "DIABETES", "OR": 2.5, "IC95_inf": 2.0, "IC95_sup": 3.0},
            {"comorbidade": "HIPERTENSA", "OR": 2.2, "IC95_inf": 1.9, "IC95_sup": 2.6},
        ]
    )
    ranked = rank_comorbidities(main_or)
    assert ranked["comorbidade"].tolist() == ["RENAL", "DIABETES", "HIPERTENSA"]
    # RENAL [3.5, 4.6] não se sobrepõe com DIABETES [2.0, 3.0] nem HIPERTENSA [1.9, 2.6]
    assert ranked.loc[0, "status_ordem"] == "ordem definida"
    # DIABETES e HIPERTENSA se sobrepõem
    assert "sem ordem definida com: HIPERTENSA" in ranked.loc[1, "status_ordem"]
    assert "sem ordem definida com: DIABETES" in ranked.loc[2, "status_ordem"]


def test_build_profile_specs_creates_four_groups_from_e1_pairs() -> None:
    included_pairs = [("DIABETES", "HIPERTENSA")]
    trios = ["DIABETES + RENAL + HIPERTENSA"]
    specs = build_profile_specs(included_pairs, trios)

    # 1 referência + 7 isoladas + 21 pares + 1 trio = 30 perfis
    assert len(specs) == 30
    pair_Map = {s["perfil"]: s["status"] for s in specs if s["grupo"] == "3. Par"}
    assert pair_Map["DIABETES + HIPERTENSA"] == "estimado"
    assert pair_Map["DIABETES + RENAL"] == "dados insuficientes"

    trio_specs = [s for s in specs if s["grupo"] == "4. 3 ou mais"]
    assert len(trio_specs) == 1
    assert "soma dos efeitos individuais e dos pares" in trio_specs[0]["nota"]


def test_run_e1_pipeline_end_to_end_synthetic(tmp_path: Path) -> None:
    rng = np.random.default_rng(20261103)
    n = 300
    data: dict[str, object] = {
        "ANO": np.full(n, 2022),
        "idade_anos": rng.uniform(10, 85, size=n),
        "sexo": pd.Categorical(rng.choice(["F", "M"], size=n), categories=["F", "M", "I"]),
        "gestante": np.zeros(n, dtype="int8"),
        "y": np.zeros(n, dtype="int8"),
    }
    for c in COMORBIDADES:
        data[c] = pd.Categorical(
            rng.choice(["Não", "Sim"], size=n, p=[0.75, 0.25]),
            categories=["Não", "Sim", "Ausente"],
        )
    df = pd.DataFrame(data)
    # Garante >= 10 eventos no par DIABETES + HIPERTENSA e >= 10 casos num trio
    for col in ("DIABETES", "HIPERTENSA", "RENAL"):
        s = df[col].astype("object")
        s.iloc[:20] = "Sim"
        df[col] = pd.Categorical(s, categories=["Não", "Sim", "Ausente"])
    df.loc[:15, "y"] = 1
    df.loc[20:60, "y"] = rng.binomial(1, 0.3, size=41).astype("int8")
    df["n_comorbidades"] = (
        df[COMORBIDADES].apply(lambda r: sum(v == "Sim" for v in r), axis=1).astype("int8")
    )

    cfg = {
        "seed": 20261103,
        "supressao_min_celula": 10,
        "caminhos": {
            "relatorios": str(tmp_path / "reports"),
            "modelos": str(tmp_path / "models"),
        },
    }
    out = run_e1_pipeline(cfg, df)
    assert out["coef_path"].is_file()
    assert out["or_path"].is_file()
    assert out["reri_path"].is_file()
    assert out["ranking_path"].is_file()
    assert out["perfis_path"].is_file()
    assert out["bundle_path"].is_file()
