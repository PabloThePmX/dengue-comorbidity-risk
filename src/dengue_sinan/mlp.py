"""Classificador MLP em PyTorch compatível com scikit-learn (T-4.6b, R3, R5, R6, R8)."""

import copy
from typing import Any

import numpy as np
import torch
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.metrics import average_precision_score
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


class _MLPNet(nn.Module):
    def __init__(self, in_features: int, hidden_layers: tuple[int, ...], dropout: float) -> None:
        super().__init__()
        layers: list[nn.Module] = []
        prev = in_features
        for h in hidden_layers:
            layers.append(nn.Linear(prev, int(h)))
            layers.append(nn.ReLU())
            if dropout > 0.0:
                layers.append(nn.Dropout(p=float(dropout)))
            prev = int(h)
        layers.append(nn.Linear(prev, 1))
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)


class TorchMLPClassifier(BaseEstimator, ClassifierMixin):
    """Envolve uma rede MLP PyTorch com interface `fit` / `predict_proba` (R3: sem `pos_weight`)."""

    def __init__(
        self,
        hidden_layers: tuple[int, ...] | list[int] = (64,),
        dropout: float = 0.1,
        weight_decay: float = 1e-4,
        lr: float = 1e-3,
        batch_size: int = 1024,
        max_epochs: int = 200,
        patience: int = 10,
        seed: int = 20261103,
        device: str | None = None,
    ) -> None:
        self.hidden_layers = tuple(hidden_layers)
        self.dropout = dropout
        self.weight_decay = weight_decay
        self.lr = lr
        self.batch_size = batch_size
        self.max_epochs = max_epochs
        self.patience = patience
        self.seed = seed
        self.device = device

    def _resolve_device(self) -> torch.device:
        if self.device is not None:
            return torch.device(self.device)
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def _set_seeds(self) -> None:
        torch.manual_seed(int(self.seed))
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(int(self.seed))

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        *,
        eval_set: tuple[np.ndarray, np.ndarray] | None = None,
    ) -> "TorchMLPClassifier":
        """Treina a rede MLP com `BCEWithLogitsLoss()` sem `pos_weight` (R3).

        Se `eval_set=(X_val, y_val)` for fornecido, monitora a PR-AUC na validação interna ao fim de
        cada época, guarda o `state_dict` da melhor época (`best_iteration_`) e aplica early
        stopping com paciência `self.patience` (T-4.2, R6).
        """
        self._set_seeds()
        dev = self._resolve_device()
        self.device_ = str(dev)
        self.classes_ = np.array([0, 1], dtype=np.int8)

        X_arr = np.asarray(X, dtype=np.float32)
        y_arr = np.asarray(y, dtype=np.float32).ravel()
        in_features = X_arr.shape[1]

        model = _MLPNet(in_features, tuple(self.hidden_layers), float(self.dropout)).to(dev)
        # Regra R3: BCEWithLogitsLoss sem pos_weight
        criterion = nn.BCEWithLogitsLoss()
        optimizer = torch.optim.Adam(
            model.parameters(),
            lr=float(self.lr),
            weight_decay=float(self.weight_decay),
        )

        dataset = TensorDataset(torch.from_numpy(X_arr), torch.from_numpy(y_arr))
        gen = torch.Generator()
        gen.manual_seed(int(self.seed))
        loader = DataLoader(
            dataset,
            batch_size=min(int(self.batch_size), max(1, len(dataset))),
            shuffle=True,
            generator=gen,
        )

        best_score = -np.inf
        best_epoch = 1
        best_state = copy.deepcopy(model.state_dict())
        epochs_no_improve = 0
        self.history_: list[dict[str, float]] = []

        X_val_t: torch.Tensor | None = None
        y_val_arr: np.ndarray | None = None
        if eval_set is not None:
            X_val_arr = np.asarray(eval_set[0], dtype=np.float32)
            y_val_arr = np.asarray(eval_set[1], dtype=np.int8).ravel()
            X_val_t = torch.from_numpy(X_val_arr).to(dev)

        for epoch in range(1, int(self.max_epochs) + 1):
            model.train()
            epoch_loss = 0.0
            n_seen = 0
            for bx, by in loader:
                bx_d = bx.to(dev)
                by_d = by.to(dev)
                optimizer.zero_grad()
                logits = model(bx_d)
                loss = criterion(logits, by_d)
                loss.backward()
                optimizer.step()
                epoch_loss += float(loss.item()) * len(by)
                n_seen += len(by)

            mean_loss = epoch_loss / max(1, n_seen)

            if X_val_t is not None and y_val_arr is not None:
                model.eval()
                with torch.no_grad():
                    val_logits = model(X_val_t)
                    val_probs = torch.sigmoid(val_logits).cpu().numpy()
                if len(np.unique(y_val_arr)) > 1:
                    val_prauc = float(average_precision_score(y_val_arr, val_probs))
                else:
                    val_prauc = float(-mean_loss)
                self.history_.append(
                    {"epoch": float(epoch), "loss": mean_loss, "val_pr_auc": val_prauc}
                )
                if val_prauc > best_score + 1e-7:
                    best_score = val_prauc
                    best_epoch = epoch
                    best_state = copy.deepcopy(model.state_dict())
                    epochs_no_improve = 0
                else:
                    epochs_no_improve += 1
                    if self.patience and epochs_no_improve >= int(self.patience):
                        break
            else:
                self.history_.append({"epoch": float(epoch), "loss": mean_loss})
                best_epoch = epoch
                best_state = copy.deepcopy(model.state_dict())

        model.load_state_dict(best_state)
        model.eval()
        self.model_ = model.cpu()
        self.best_iteration_ = int(best_epoch)
        self.best_score_ = float(best_score) if best_score > -np.inf else 0.0
        self.n_features_in_ = in_features
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Retorna matriz `(n, 2)` com `[1 - p, p]` em `[0, 1]`."""
        X_arr = np.asarray(X, dtype=np.float32)
        self.model_.eval()
        with torch.no_grad():
            logits = self.model_(torch.from_numpy(X_arr))
            probs = torch.sigmoid(logits).numpy().astype(np.float64)
        probs = np.clip(probs, 0.0, 1.0)
        return np.column_stack([1.0 - probs, probs])

    def predict(self, X: np.ndarray) -> np.ndarray:
        probs = self.predict_proba(X)[:, 1]
        return (probs >= 0.5).astype(np.int8)

    def get_params(self, deep: bool = True) -> dict[str, Any]:  # noqa: ARG002
        return {
            "hidden_layers": self.hidden_layers,
            "dropout": self.dropout,
            "weight_decay": self.weight_decay,
            "lr": self.lr,
            "batch_size": self.batch_size,
            "max_epochs": self.max_epochs,
            "patience": self.patience,
            "seed": self.seed,
            "device": self.device,
        }
