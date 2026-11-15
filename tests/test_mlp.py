"""Testes unitários do classificador MLP em PyTorch (T-4.6b)."""

import numpy as np

from dengue_sinan.mlp import TorchMLPClassifier


def test_torch_mlp_classifier_early_stopping_and_probabilities() -> None:
    rng = np.random.default_rng(20261103)
    X_tr = rng.normal(size=(200, 8)).astype(np.float32)
    logits_tr = 1.2 * X_tr[:, 0] - 0.8 * X_tr[:, 1] - 1.5
    y_tr = rng.binomial(1, 1.0 / (1.0 + np.exp(-logits_tr))).astype(np.int8)

    X_va = rng.normal(size=(60, 8)).astype(np.float32)
    logits_va = 1.2 * X_va[:, 0] - 0.8 * X_va[:, 1] - 1.5
    y_va = rng.binomial(1, 1.0 / (1.0 + np.exp(-logits_va))).astype(np.int8)
    y_va[:3] = 1
    y_va[3:6] = 0

    clf = TorchMLPClassifier(
        hidden_layers=(16,),
        dropout=0.1,
        lr=1e-2,
        batch_size=64,
        max_epochs=40,
        patience=3,
        seed=20261103,
        device="cpu",
    )
    clf.fit(X_tr, y_tr, eval_set=(X_va, y_va))

    assert 1 <= clf.best_iteration_ <= 40
    assert len(clf.history_) < 40  # parou antes de 40 pelo early stopping
    probs = clf.predict_proba(X_va)
    assert probs.shape == (60, 2)
    assert np.all((probs >= 0.0) & (probs <= 1.0))
    assert np.allclose(probs.sum(axis=1), 1.0)
