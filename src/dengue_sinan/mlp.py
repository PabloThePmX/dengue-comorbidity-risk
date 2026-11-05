"""Classificador MLP em PyTorch com early stopping e interface sklearn."""

from copy import deepcopy

import numpy as np
import torch
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.metrics import average_precision_score
from sklearn.model_selection import train_test_split
from sklearn.utils.validation import check_is_fitted
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


class MLPClassifier(ClassifierMixin, BaseEstimator):
    """MLP binário sem pesos de classe, com early stopping pela PR-AUC."""

    def __init__(
        self,
        hidden_layers=(64,),
        dropout=0.0,
        weight_decay=1e-4,
        learning_rate=1e-3,
        batch_size=1024,
        epochs=200,
        patience=10,
        seed=20261103,
        device=None,
        early_stopping=True,
    ):
        self.hidden_layers = hidden_layers
        self.dropout = dropout
        self.weight_decay = weight_decay
        self.learning_rate = learning_rate
        self.batch_size = batch_size
        self.epochs = epochs
        self.patience = patience
        self.seed = seed
        self.device = device
        self.early_stopping = early_stopping

    def _network(self, input_size: int) -> nn.Sequential:
        layers = []
        width = input_size
        for hidden in self.hidden_layers:
            layers.extend([nn.Linear(width, hidden), nn.ReLU()])
            if self.dropout:
                layers.append(nn.Dropout(self.dropout))
            width = hidden
        layers.append(nn.Linear(width, 1))
        return nn.Sequential(*layers)

    def fit(self, x, y, validation_data=None):
        features = np.asarray(x, dtype=np.float32)
        labels = np.asarray(y, dtype=np.float32).reshape(-1)
        if features.ndim != 2 or len(features) != len(labels) or not len(labels):
            raise ValueError("X e y precisam ter dimensões compatíveis e não vazias")
        if not np.isfinite(features).all() or not np.isin(labels, (0, 1)).all():
            raise ValueError("X precisa ser finito e y binário")
        if len(np.unique(labels)) != 2:
            raise ValueError("treino do MLP precisa conter as duas classes")
        if self.epochs < 1 or self.patience < 1:
            raise ValueError("epochs e patience devem ser positivos")
        if not self.early_stopping and validation_data is not None:
            raise ValueError("validation_data não deve ser informado com early_stopping=False")
        if validation_data is None:
            if self.early_stopping:
                train_x, valid_x, train_y, valid_y = train_test_split(
                    features,
                    labels,
                    test_size=0.1,
                    random_state=self.seed,
                    stratify=labels,
                )
            else:
                train_x, train_y = features, labels
                valid_x = valid_y = None
        else:
            train_x, train_y = features, labels
            valid_x, valid_y = validation_data
            valid_x = np.asarray(valid_x, dtype=np.float32)
            valid_y = np.asarray(valid_y, dtype=np.float32).reshape(-1)
            if valid_x.ndim != 2 or valid_x.shape[1] != features.shape[1]:
                raise ValueError("validation_data tem número de features incompatível")
            if (
                len(valid_x) != len(valid_y)
                or len(np.unique(valid_y)) != 2
                or not np.isfinite(valid_x).all()
                or not np.isin(valid_y, (0, 1)).all()
            ):
                raise ValueError("validação deve ter linhas alinhadas e ambas as classes")

        torch.manual_seed(self.seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(self.seed)
        self.device_ = torch.device(
            self.device or ("cuda" if torch.cuda.is_available() else "cpu")
        )
        self.classes_ = np.array([0, 1], dtype=np.int8)
        self.n_features_in_ = features.shape[1]
        self.model_ = self._network(self.n_features_in_).to(self.device_)
        optimizer = torch.optim.Adam(
            self.model_.parameters(),
            lr=self.learning_rate,
            weight_decay=self.weight_decay,
        )
        loss_function = nn.BCEWithLogitsLoss()
        dataset = TensorDataset(
            torch.from_numpy(train_x), torch.from_numpy(train_y.reshape(-1, 1))
        )
        loader = DataLoader(
            dataset,
            batch_size=self.batch_size,
            shuffle=True,
            generator=torch.Generator().manual_seed(self.seed),
        )
        valid_tensor = torch.from_numpy(valid_x).to(self.device_) if valid_x is not None else None
        best_score = -np.inf
        best_state = None
        rounds_without_improvement = 0
        self.history_ = []

        for epoch in range(self.epochs):
            self.model_.train()
            for batch_x, batch_y in loader:
                batch_x, batch_y = batch_x.to(self.device_), batch_y.to(self.device_)
                optimizer.zero_grad(set_to_none=True)
                loss = loss_function(self.model_(batch_x), batch_y)
                loss.backward()
                optimizer.step()

            if valid_tensor is not None:
                self.model_.eval()
                with torch.no_grad():
                    valid_probabilities = torch.sigmoid(
                        self.model_(valid_tensor)
                    ).cpu().numpy().ravel()
                score = float(average_precision_score(valid_y, valid_probabilities))
                self.history_.append({"epoch": epoch + 1, "pr_auc": score})
            else:
                score = float("nan")
                self.history_.append({"epoch": epoch + 1, "pr_auc": score})
            if not self.early_stopping or score > best_score:
                if self.early_stopping:
                    best_score = score
                best_state = deepcopy(self.model_.state_dict())
                self.best_epoch_ = epoch + 1
                rounds_without_improvement = 0
            else:
                rounds_without_improvement += 1
                if rounds_without_improvement >= self.patience:
                    break

        if best_state is None:
            raise RuntimeError("early stopping do MLP não encontrou pesos válidos")
        self.model_.load_state_dict(best_state)
        self.best_score_ = best_score if self.early_stopping else None
        return self

    def predict_proba(self, x):
        check_is_fitted(self, ["model_", "classes_"])
        features = np.asarray(x, dtype=np.float32)
        if features.ndim != 2 or features.shape[1] != self.n_features_in_:
            raise ValueError("X tem número de features incompatível com o MLP ajustado")
        self.model_.eval()
        with torch.no_grad():
            probabilities = torch.sigmoid(
                self.model_(torch.from_numpy(features).to(self.device_))
            ).cpu().numpy().ravel()
        return np.column_stack([1 - probabilities, probabilities])

    def predict(self, x):
        return (self.predict_proba(x)[:, 1] >= 0.5).astype(np.int8)
