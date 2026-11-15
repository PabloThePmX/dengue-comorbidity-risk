"""Testes de serialização de artefatos com metadados (T-3.6, FR-12)."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dengue_sinan.artifacts import REQUIRED_METADATA_KEYS, load_bundle, save_bundle
from dengue_sinan.dataset import COMORBIDADES
from dengue_sinan.explain import fit_e1


def test_save_and_load_bundle_reproduces_e1_risk_within_1e9(tmp_path: Path) -> None:
    rng = np.random.default_rng(20261103)
    n = 200
    data: dict[str, object] = {
        "ANO": np.full(n, 2022),
        "idade_anos": rng.uniform(15, 80, size=n),
        "sexo": pd.Categorical(rng.choice(["F", "M"], size=n), categories=["F", "M", "I"]),
        "gestante": np.zeros(n, dtype="int8"),
        "y": rng.binomial(1, 0.15, size=n).astype("int8"),
    }
    for c in COMORBIDADES:
        data[c] = pd.Categorical(
            rng.choice(["Não", "Sim"], size=n, p=[0.8, 0.2]),
            categories=["Não", "Sim", "Ausente"],
        )
    df = pd.DataFrame(data)
    df["n_comorbidades"] = (
        df[COMORBIDADES].apply(lambda r: sum(v == "Sim" for v in r), axis=1).astype("int8")
    )

    model = fit_e1(df, min_pair_events=10)
    bundle_path = save_bundle(
        model,
        tmp_path / "e1_test.joblib",
        metadados={
            "config": {"seed": 20261103},
            "lista_features": model.feature_names,
            "metricas_validacao": {"converged": model.converged},
        },
    )

    loaded = load_bundle(bundle_path)
    assert set(REQUIRED_METADATA_KEYS) <= set(loaded["metadados"].keys())

    r_orig = model.predict_profile_risk(65.0, "F", 0, ["DIABETES", "HIPERTENSA"])["risco"]
    r_loaded = loaded.predict_profile_risk(65.0, "F", 0, ["DIABETES", "HIPERTENSA"])["risco"]
    assert abs(r_orig - r_loaded) < 1e-9


def test_load_bundle_rejects_invalid_file(tmp_path: Path) -> None:
    import joblib

    bad = tmp_path / "bad.joblib"
    joblib.dump({"not_a_bundle": 123}, bad)
    with pytest.raises(ValueError, match="Formato de artefato inválido"):
        load_bundle(bad)
