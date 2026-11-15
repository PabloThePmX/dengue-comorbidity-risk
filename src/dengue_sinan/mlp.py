"""Classificador MLP compatível com scikit-learn e early stopping interno."""

from copy import deepcopy

import numpy as np
import torch
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.metrics import average_precision_score
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


class MLPClassifier(ClassifierMixin, BaseEstimator):
    def __init__(
        self,
        hidden_layer_sizes=(128,),
        dropout=0.1,
        weight_decay=1e-4,
        learning_rate=1e-3,
        batch_size=1024,
        max_epochs=200,
        patience=10,
        seed=20261103,
        device="auto",
    ):
        self.hidden_layer_sizes = hidden_layer_sizes
        self.dropout = dropout
        self.weight_decay = weight_decay
        self.learning_rate = learning_rate
        self.batch_size = batch_size
        self.max_epochs = max_epochs
        self.patience = patience
        self.seed = seed
        self.device = device

    def _make_network(self, input_features: int) -> nn.Sequential:
        layers = []
        width = input_features
        for hidden_width in self.hidden_layer_sizes:
            layers.extend((nn.Linear(width, hidden_width), nn.ReLU()))
            if self.dropout:
                layers.append(nn.Dropout(self.dropout))
            width = hidden_width
        layers.append(nn.Linear(width, 1))
        return nn.Sequential(*layers)

    def fit(self, X, y, *, eval_set=None):
        features = np.asarray(X, dtype=np.float32)
        labels = np.asarray(y, dtype=np.float32).reshape(-1)
        if features.ndim != 2 or len(features) != len(labels):
            raise ValueError("X e y devem ter o mesmo número de linhas e X deve ser 2D.")
        if not len(labels) or not np.isin(labels, [0, 1]).all():
            raise ValueError("y deve conter apenas as duas classes 0 e 1.")
        if eval_set is not None:
            validation_x = np.asarray(eval_set[0], dtype=np.float32)
            validation_y = np.asarray(eval_set[1], dtype=np.int8).reshape(-1)
            if validation_x.ndim != 2 or validation_x.shape[1] != features.shape[1]:
                raise ValueError("eval_set deve ter o mesmo número de features de X.")
            if len(validation_x) != len(validation_y) or len(np.unique(validation_y)) != 2:
                raise ValueError("eval_set deve conter X/y alinhados e ambas as classes.")
        if self.batch_size < 1 or self.max_epochs < 1 or self.patience < 1:
            raise ValueError("batch_size, max_epochs e patience devem ser positivos.")

        torch.manual_seed(self.seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(self.seed)
        device = (
            torch.device("cuda" if torch.cuda.is_available() else "cpu")
            if self.device == "auto"
            else torch.device(self.device)
        )
        self.device_ = str(device)
        self.classes_ = np.array([0, 1], dtype=np.int8)
        self.n_features_in_ = features.shape[1]
        self.model_ = self._make_network(self.n_features_in_).to(device)
        optimizer = torch.optim.Adam(
            self.model_.parameters(),
            lr=self.learning_rate,
            weight_decay=self.weight_decay,
        )
        loss_function = nn.BCEWithLogitsLoss()
        train_loader = DataLoader(
            TensorDataset(torch.from_numpy(features), torch.from_numpy(labels)),
            batch_size=self.batch_size,
            shuffle=True,
            generator=torch.Generator().manual_seed(self.seed),
        )
        validation_tensor = (
            torch.from_numpy(validation_x).to(device) if eval_set is not None else None
        )

        best_score = -np.inf
        best_state = None
        rounds_without_improvement = 0
        for epoch in range(self.max_epochs):
            self.model_.train()
            for batch_x, batch_y in train_loader:
                batch_x = batch_x.to(device)
                batch_y = batch_y.to(device)
                optimizer.zero_grad(set_to_none=True)
                loss = loss_function(self.model_(batch_x).reshape(-1), batch_y)
                loss.backward()
                optimizer.step()

            if validation_tensor is None:
                continue
            self.model_.eval()
            with torch.no_grad():
                logits = self.model_(validation_tensor).reshape(-1)
                probabilities = torch.sigmoid(logits).cpu().numpy()
            score = float(average_precision_score(validation_y, probabilities))
            if score > best_score:
                best_score = score
                self.best_epoch_ = epoch + 1
                best_state = deepcopy(self.model_.state_dict())
                rounds_without_improvement = 0
            else:
                rounds_without_improvement += 1
            if rounds_without_improvement >= self.patience:
                break

        if validation_tensor is None:
            self.best_epoch_ = self.max_epochs
            best_state = deepcopy(self.model_.state_dict())
        if best_state is None:
            raise RuntimeError("MLP não produziu estado de validação utilizável.")
        self.model_.load_state_dict(best_state)
        self.best_validation_pr_auc_ = best_score if validation_tensor is not None else None
        self.n_epochs_ = epoch + 1
        return self

    def predict_proba(self, X) -> np.ndarray:
        if not hasattr(self, "model_"):
            raise RuntimeError("MLP precisa ser ajustado antes de prever.")
        features = np.asarray(X, dtype=np.float32)
        if features.ndim != 2 or features.shape[1] != self.n_features_in_:
            raise ValueError("X tem número de features incompatível com o ajuste.")
        self.model_.eval()
        with torch.no_grad():
            logits = self.model_(torch.from_numpy(features).to(self.device_)).reshape(-1)
            positive = torch.sigmoid(logits).cpu().numpy()
        return np.column_stack((1 - positive, positive))
