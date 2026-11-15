"""Classificador Tabular Foundation Model (TabFM) em contexto para triagem (T-4.7, R3, R5, R8).

Implementa `TabFMClassifier` compatível com `sklearn.pipeline.Pipeline`:
- Subamostragem **estratificada pelo alvo** do treino de cada dobra para formar o contexto
  (`max_context_rows`, padrão 10.000 linhas), preservando a prevalência natural sem pesos (R3).
- Se `tabpfn` (`TabPFNClassifier`) estiver instalado no ambiente (ex.: GPU no Colab), utiliza-o em
  lotes (`batch_size`) sobre o contexto estratificado; caso contrário, executa atenção em contexto
  multi-escala em PyTorch (`cuda` se disponível, `cpu` caso contrário) combinada com projeção linear
  regularizada no contexto.
"""

from typing import Any

import numpy as np
import torch
from scipy.special import expit
from sklearn.base import BaseEstimator, ClassifierMixin


def stratified_context_indices(
    y: np.ndarray,
    max_rows: int,
    seed: int,
) -> np.ndarray:
    """Seleciona até `max_rows` índices estratificados por `y` preservando a prevalência (R3)."""
    n_total = len(y)
    if max_rows <= 0 or n_total <= max_rows:
        return np.arange(n_total, dtype=np.int64)

    rng = np.random.default_rng(int(seed))
    y_arr = np.asarray(y, dtype=np.int8).ravel()
    pos_idx = np.flatnonzero(y_arr == 1)
    neg_idx = np.flatnonzero(y_arr == 0)

    if len(pos_idx) == 0 or len(neg_idx) == 0:
        chosen = rng.choice(n_total, size=max_rows, replace=False)
        chosen.sort()
        return chosen.astype(np.int64)

    frac = float(max_rows) / float(n_total)
    n_pos = max(1, min(len(pos_idx), int(round(len(pos_idx) * frac))))
    n_neg = max(1, min(len(neg_idx), max_rows - n_pos))

    chosen_pos = rng.choice(pos_idx, size=n_pos, replace=False)
    chosen_neg = rng.choice(neg_idx, size=n_neg, replace=False)
    combined = np.concatenate([chosen_pos, chosen_neg])
    combined.sort()
    return combined.astype(np.int64)


class TabFMClassifier(BaseEstimator, ClassifierMixin):
    """Classificador tabular zero-shot / in-context learning (T-4.7, R3, R8)."""

    def __init__(
        self,
        max_context_rows: int = 10000,
        batch_size: int = 4096,
        temperatures: tuple[float, ...] = (0.15, 0.35, 0.75),
        ridge_alpha: float = 10.0,
        seed: int = 20261103,
        device: str | None = None,
        use_external_tabpfn: bool = True,
    ) -> None:
        self.max_context_rows = max_context_rows
        self.batch_size = batch_size
        self.temperatures = temperatures
        self.ridge_alpha = ridge_alpha
        self.seed = seed
        self.device = device
        self.use_external_tabpfn = use_external_tabpfn

    def _resolve_device(self) -> torch.device:
        if self.device:
            return torch.device(self.device)
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def fit(self, X: Any, y: Any) -> "TabFMClassifier":
        """Armazena a subamostra estratificada de contexto e prepara os tensores de inferência."""
        torch.manual_seed(int(self.seed))
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(int(self.seed))

        X_arr = np.asarray(X, dtype=np.float32)
        y_arr = np.asarray(y, dtype=np.float32).ravel()
        self.classes_ = np.array([0, 1], dtype=np.int8)

        ctx_idx = stratified_context_indices(y_arr, int(self.max_context_rows), int(self.seed))
        X_ctx = X_arr[ctx_idx]
        y_ctx = y_arr[ctx_idx]

        self.context_size_ = int(len(ctx_idx))
        self.base_rate_ = float(np.clip(np.mean(y_ctx), 1e-6, 1.0 - 1e-6))
        self.device_ = str(self._resolve_device())
        self.best_iteration_ = 1
        self._external_model: Any = None

        if self.use_external_tabpfn:
            try:
                from tabpfn import TabPFNClassifier  # type: ignore[import-not-found]

                ext_clf = TabPFNClassifier(device=self.device_, random_state=int(self.seed))
                ext_clf.fit(X_ctx, y_ctx.astype(np.int8))
                self._external_model = ext_clf
                self.backend_ = "tabpfn"
                return self
            except Exception:
                self._external_model = None

        self.backend_ = "torch_icl"
        # Padronização leve do contexto (ajustada apenas nos dados de contexto da dobra — R5)
        self._ctx_mean = np.mean(X_ctx, axis=0, keepdims=True).astype(np.float32)
        self._ctx_std = np.where(
            np.std(X_ctx, axis=0, keepdims=True) > 1e-6,
            np.std(X_ctx, axis=0, keepdims=True),
            1.0,
        ).astype(np.float32)
        X_norm = (X_ctx - self._ctx_mean) / self._ctx_std

        # Projeção linear fechada (ridge) no contexto sem peso de classe (R3)
        n_ctx, n_feat = X_norm.shape
        reg = float(self.ridge_alpha) * np.eye(n_feat, dtype=np.float32)
        y_centered = y_ctx - self.base_rate_
        gram = (X_norm.T @ X_norm) / max(1.0, float(n_ctx)) + reg
        self._ridge_w = np.linalg.solve(gram, (X_norm.T @ y_centered) / max(1.0, float(n_ctx)))

        # Normaliza vetores de contexto para atenção cosseno multi-temperatura em PyTorch
        norms = np.linalg.norm(X_norm, axis=1, keepdims=True)
        self._ctx_keys = (X_norm / np.maximum(norms, 1e-6)).astype(np.float32)
        self._ctx_values = y_ctx.astype(np.float32)
        return self

    def predict_proba(self, X: Any) -> np.ndarray:
        """Prediz probabilidades `(n, 2)` em lotes a partir do contexto estratificado."""
        X_arr = np.asarray(X, dtype=np.float32)
        n_samples = len(X_arr)
        bsize = max(256, int(self.batch_size))

        if getattr(self, "_external_model", None) is not None:
            probs_list: list[np.ndarray] = []
            for start in range(0, n_samples, bsize):
                batch = X_arr[start : start + bsize]
                p_batch = self._external_model.predict_proba(batch)[:, 1]
                probs_list.append(np.asarray(p_batch, dtype=np.float64))
            p1 = np.clip(np.concatenate(probs_list), 0.0, 1.0)
            return np.column_stack([1.0 - p1, p1])

        dev = self._resolve_device()
        X_norm = (X_arr - self._ctx_mean) / self._ctx_std
        q_norms = np.linalg.norm(X_norm, axis=1, keepdims=True)
        X_unit = (X_norm / np.maximum(q_norms, 1e-6)).astype(np.float32)

        prior_logit = float(np.log(self.base_rate_ / (1.0 - self.base_rate_)))
        temps = tuple(float(t) for t in self.temperatures)

        out_p1 = np.empty(n_samples, dtype=np.float64)
        with torch.no_grad():
            keys_t = torch.from_numpy(self._ctx_keys).to(dev)
            vals_t = torch.from_numpy(self._ctx_values).to(dev)
            ridge_w_t = torch.from_numpy(self._ridge_w).to(dev)

            for start in range(0, n_samples, bsize):
                end = min(n_samples, start + bsize)
                q_unit = torch.from_numpy(X_unit[start:end]).to(dev)
                q_norm = torch.from_numpy(X_norm[start:end]).to(dev)

                # Similaridade cosseno (batch, n_ctx)
                sim = q_unit @ keys_t.T

                # Atenção multi-escala sobre os rótulos do contexto
                attn_probs = torch.zeros(end - start, dtype=torch.float32, device=dev)
                for temp in temps:
                    weights = torch.softmax(sim / max(temp, 1e-3), dim=1)
                    attn_probs = attn_probs + (weights @ vals_t)
                attn_probs = attn_probs / float(len(temps))

                # Combina atenção não-paramétrica com projeção linear do contexto em log-odds
                attn_clamped = torch.clamp(attn_probs, 1e-6, 1.0 - 1e-6)
                attn_logit = torch.log(attn_clamped / (1.0 - attn_clamped))
                ridge_delta = q_norm @ ridge_w_t
                var_scale = max(self.base_rate_ * (1.0 - self.base_rate_), 1e-3)
                combined_logit = 0.5 * attn_logit + 0.5 * (prior_logit + ridge_delta / var_scale)
                out_p1[start:end] = expit(combined_logit.cpu().numpy().astype(np.float64))

        p1_final = np.clip(out_p1, 0.0, 1.0)
        return np.column_stack([1.0 - p1_final, p1_final])

    def predict(self, X: Any) -> np.ndarray:
        """Predição binária padrão (limiar 0.5; limiar F2 oficial em `FittedM1Model`)."""
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(np.int8)
