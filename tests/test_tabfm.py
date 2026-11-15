"""Testes unitários do classificador TabFM em contexto e integração com LORO (T-4.7)."""

import numpy as np
import pandas as pd

from dengue_sinan.config import load_config
from dengue_sinan.cv import run_loro
from dengue_sinan.dataset import COMORBIDADES, SINAIS
from dengue_sinan.folds import DEFAULT_FOLD_ORDER
from dengue_sinan.tabfm import TabFMClassifier, stratified_context_indices


def _make_synthetic_df(n_per_region: int = 40) -> pd.DataFrame:
    rng = np.random.default_rng(20261103)
    rows: list[dict] = []
    for reg in DEFAULT_FOLD_ORDER:
        for i in range(n_per_region):
            y = 1 if i < 6 else 0
            row: dict = {
                "ANO": 2022 if i % 2 == 0 else 2023,
                "regiao": reg,
                "y": y,
                "idade_anos": float(rng.integers(5, 85)),
                "dias_ate_notificacao": float(rng.integers(0, 15)),
                "sexo": "F" if i % 2 == 0 else "M",
                "gestante": 0,
                "n_comorbidades": 1 if y == 1 else 0,
            }
            for c in COMORBIDADES:
                row[c] = "Sim" if (c == "DIABETES" and y == 1) else "Não"
            for s in SINAIS:
                row[s] = "Sim" if s == "FEBRE" else "Não"
            rows.append(row)
    return pd.DataFrame(rows)


def test_stratified_context_preserves_prevalence() -> None:
    y = np.array([1] * 20 + [0] * 180, dtype=np.int8)
    idx = stratified_context_indices(y, max_rows=50, seed=20261103)
    assert len(idx) == 50
    assert int(np.sum(y[idx] == 1)) == 5
    assert int(np.sum(y[idx] == 0)) == 45


def test_tabfm_classifier_and_run_loro() -> None:
    rng = np.random.default_rng(20261103)
    X_tr = rng.normal(size=(150, 6)).astype(np.float32)
    y_tr = (X_tr[:, 0] - 0.5 * X_tr[:, 1] > 0.8).astype(np.int8)
    y_tr[:5] = 1
    y_tr[5:10] = 0

    clf = TabFMClassifier(max_context_rows=80, batch_size=32, seed=20261103, device="cpu")
    clf.fit(X_tr, y_tr)
    assert clf.context_size_ == 80

    probs = clf.predict_proba(X_tr[:25])
    assert probs.shape == (25, 2)
    assert np.all((probs >= 0.0) & (probs <= 1.0))
    assert np.allclose(probs.sum(axis=1), 1.0)

    cfg = load_config()
    df = _make_synthetic_df(30)
    res = run_loro(cfg, "tabfm", {"max_context_rows": 60, "device": "cpu"}, df)
    assert len(res["oof_p"]) == len(df)
    assert not np.isnan(res["oof_p"]).any()
    assert len(res["pr_auc_por_dobra"]) == 5
