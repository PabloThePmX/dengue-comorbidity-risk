import numpy as np

from dengue_sinan.mlp import MLPClassifier


def test_mlp_supports_fixed_epoch_fit_without_early_stopping():
    rng = np.random.default_rng(42)
    features = rng.normal(size=(40, 4)).astype(np.float32)
    labels = np.tile([0, 1], 20)
    model = MLPClassifier(
        hidden_layer_sizes=(8,),
        batch_size=10,
        max_epochs=2,
        patience=1,
        seed=17,
        device="cpu",
    )

    model.fit(features, labels)
    probabilities = model.predict_proba(features)

    assert model.best_epoch_ == 2
    assert model.n_epochs_ == 2
    assert probabilities.shape == (len(features), 2)
    assert np.isfinite(probabilities).all()
    assert np.allclose(probabilities.sum(axis=1), 1)
