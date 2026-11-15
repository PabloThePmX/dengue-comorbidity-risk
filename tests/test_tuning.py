from test_cv import _development_data

from dengue_sinan.tuning import tune


def test_tune_resumes_existing_optuna_database(tmp_path):
    config = {
        "seed": 2026,
        "ordem_dobras": ["Sudeste", "Sul", "Centro-Oeste", "Nordeste", "Norte"],
        "validacao_interna_frac": 0.1,
        "caminhos": {"mlruns": str(tmp_path)},
        "optuna": {
            "max_tentativas": {"elastic_net": 2},
            "poda_tentativas_iniciais": 5,
            "poda_dobras_aquecimento": 2,
        },
        "orcamento_teto_min": {"elastic_net": 5},
        "orcamento_piso_min": 1,
    }
    data = _development_data(rows_per_region=30)

    first = tune(config, "elastic_net", data, n_trials=2, log_mlflow=False)
    second = tune(config, "elastic_net", data, n_trials=2, log_mlflow=False)

    assert first["n_trials"] == 2
    assert second["n_trials"] == 4
    assert second["n_completed"] >= first["n_completed"]
    assert second["database"].endswith("elastic_net.db")
