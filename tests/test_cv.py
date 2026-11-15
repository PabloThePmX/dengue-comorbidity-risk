import numpy as np
import pandas as pd

from dengue_sinan.cv import run_loro
from dengue_sinan.profiling import COMORBIDADES, SINAIS, add_derived


def _development_data(rows_per_region=60):
    rng = np.random.default_rng(128)
    regions = [
        ("Norte", "15"),
        ("Nordeste", "29"),
        ("Centro-Oeste", "52"),
        ("Sudeste", "35"),
        ("Sul", "41"),
    ]
    frames = []
    for region, uf in regions:
        size = rows_per_region
        outcome = np.tile([0, 1], size // 2)
        rng.shuffle(outcome)
        data = {name: rng.choice(["1", "2", "9"], size) for name in COMORBIDADES + SINAIS}
        data.update(
            {
                "ANO": [2022] * size,
                "CLASSI_FIN": np.where(outcome, "12", "10"),
                "EVOLUCAO": ["1"] * size,
                "NU_IDADE_N": [f"4{age:03d}" for age in rng.integers(1, 100, size)],
                "ANO_NASC": ["1980"] * size,
                "DT_SIN_PRI": ["20220101"] * size,
                "DT_NOTIFIC": ["20220102"] * size,
                "CS_SEXO": rng.choice(["M", "F", "I"], size),
                "CS_GESTANT": rng.choice(["1", "5"], size),
                "CS_RACA": ["1"] * size,
                "ID_MN_RESI": [f"{uf}0001"] * size,
                "SG_UF": [uf] * size,
            }
        )
        frame = add_derived(pd.DataFrame(data))
        assert frame["regiao"].eq(region).all()
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def test_run_loro_returns_one_out_of_fold_prediction_per_row():
    df = _development_data()
    cfg = {
        "seed": 2026,
        "ordem_dobras": ["Sudeste", "Sul", "Centro-Oeste", "Nordeste", "Norte"],
        "validacao_interna_frac": 0.1,
    }

    result = run_loro(
        cfg,
        "elastic_net",
        {"C": 0.1, "l1_ratio": 0.5},
        df,
    )

    assert len(result["oof"]) == len(df)
    assert result["oof"]["probabilidade"].between(0, 1).all()
    assert result["fold_metrics"]["regiao"].tolist() == cfg["ordem_dobras"]
    assert result["mean_pr_auc"] > 0


def test_run_loro_rejects_frozen_test_year():
    df = _development_data()
    df.loc[0, "ANO"] = 2024
    cfg = {"seed": 2026, "validacao_interna_frac": 0.1}

    try:
        run_loro(cfg, "elastic_net", {"C": 0.1, "l1_ratio": 0.5}, df)
    except RuntimeError as error:
        assert "2024 é teste congelado" in str(error)
    else:
        raise AssertionError("A validação não pode aceitar linhas de 2024.")