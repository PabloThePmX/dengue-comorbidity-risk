import numpy as np

from dengue_sinan.mlp import MLPClassifier


def test_mlp_trains_with_early_stopping_and_returns_probabilities():
    rng = np.random.default_rng(42)
    x = rng.normal(size=(120, 4)).astype(np.float32)
    y = (x[:, 0] + x[:, 1] > 0).astype(np.int8)
    model = MLPClassifier(
        hidden_layers=(8,),
        batch_size=32,
        epochs=8,
        patience=2,
        seed=7,
        device="cpu",
    )
    model.fit(x[:80], y[:80], validation_data=(x[80:], y[80:]))
    probabilities = model.predict_proba(x[80:])
    assert probabilities.shape == (40, 2)
    assert np.isfinite(probabilities).all()
    assert ((probabilities >= 0) & (probabilities <= 1)).all()
    assert 1 <= model.best_epoch_ <= 8
    assert model.device_.type == "cpu"


def test_mlp_can_fit_fixed_epochs_without_validation_split():
    rng = np.random.default_rng(7)
    x = rng.normal(size=(80, 3)).astype(np.float32)
    y = (x[:, 0] > 0).astype(np.int8)
    model = MLPClassifier(
        hidden_layers=(4,),
        batch_size=20,
        epochs=3,
        patience=2,
        seed=7,
        device="cpu",
        early_stopping=False,
    )
    model.fit(x, y)
    assert model.best_epoch_ == 3
    assert len(model.history_) == 3
    assert model.best_score_ is None
    assert model.predict_proba(x).shape == (80, 2)
