import numpy as np
from test_cv import _development_data

from dengue_sinan.dataset import build_feature_frame
from dengue_sinan.retrain import fit_final_pipeline


def test_final_elastic_net_pipeline_fits_all_development_rows():
    data = _development_data(rows_per_region=20)

    pipeline, params, final_point = fit_final_pipeline(
        "elastic_net",
        {"C": 1.0, "l1_ratio": 0.5},
        {},
        data,
        {"seed": 17},
    )

    probability = pipeline.predict_proba(build_feature_frame(data))[:, 1]
    assert final_point is None
    assert params == {"C": 1.0, "l1_ratio": 0.5}
    assert len(probability) == len(data)
    assert np.isfinite(probability).all()


def test_final_mlp_uses_median_best_epoch_without_early_stopping():
    data = _development_data(rows_per_region=20)
    regions = ("Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul")
    points = dict(zip(regions, (1, 2, 3, 4, 5), strict=True))

    pipeline, params, final_point = fit_final_pipeline(
        "mlp",
        {
            "hidden_layer_sizes": (8,),
            "dropout": 0.0,
            "weight_decay": 1e-4,
            "learning_rate": 1e-3,
            "batch_size": 16,
            "max_epochs": 10,
            "patience": 3,
        },
        points,
        data,
        {"seed": 17},
    )

    features = build_feature_frame(data)
    probability = pipeline.predict_proba(features)[:, 1]
    assert final_point == 3
    assert params["max_epochs"] == 3
    assert pipeline.named_steps["modelo"].best_epoch_ == 3
    assert len(probability) == len(data)
    assert np.isfinite(probability).all()
