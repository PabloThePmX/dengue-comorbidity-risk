"""Laço de validação leave-one-region-out (LORO) com early stopping (T-4.2, R1, R3, R5, R6)."""

from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from dengue_sinan.baselines import B1_FEATURES, make_b1_pipeline
from dengue_sinan.dataset import build_feature_frame
from dengue_sinan.folds import DEFAULT_FOLD_ORDER, inner_split, loro_folds
from dengue_sinan.guard import assert_dev_only
from dengue_sinan.metrics import pr_auc
from dengue_sinan.mlp import TorchMLPClassifier
from dengue_sinan.preprocess import (
    M1_FEATURES,
    assert_allowed_features,
    get_catboost_cat_indices,
    make_preprocessor,
)
from dengue_sinan.tabfm import TabFMClassifier

ITERATIVE_FAMILIES = {"xgboost", "xgb", "catboost", "mlp"}


def correct_subsampled_prob(p: np.ndarray, neg_rate: float) -> np.ndarray:
    """Corrige probabilidades quando negativos são subamostrados no treino (T-4.4):
    `p' = p / (p + (1 - p) / taxa_amostragem)`.
    """
    rate = float(neg_rate)
    if rate >= 1.0 or rate <= 0.0:
        return np.asarray(p, dtype=np.float64)
    p_arr = np.clip(np.asarray(p, dtype=np.float64), 0.0, 1.0)
    denom = p_arr + (1.0 - p_arr) / rate
    return np.where(denom > 0.0, p_arr / denom, 0.0)


def _subsample_negatives(
    idx_train: np.ndarray,
    y_all: np.ndarray,
    neg_rate: float,
    seed: int,
) -> np.ndarray:
    """Subamostra apenas negativos dentro da dobra de treino (T-4.4)."""
    if neg_rate >= 1.0:
        return idx_train
    y_tr = y_all[idx_train]
    pos_mask = y_tr == 1
    idx_pos = idx_train[pos_mask]
    idx_neg = idx_train[~pos_mask]
    n_keep_neg = max(1, int(round(len(idx_neg) * float(neg_rate))))
    rng = np.random.default_rng(int(seed))
    chosen_neg = rng.choice(idx_neg, size=n_keep_neg, replace=False)
    combined = np.concatenate([idx_pos, chosen_neg])
    combined.sort()
    return combined


def _fit_fold_model(
    familia: str,
    params: dict[str, Any],
    X_fit: pd.DataFrame,
    y_fit: np.ndarray,
    X_es: pd.DataFrame | None,
    y_es: np.ndarray | None,
    seed: int,
) -> tuple[Pipeline, int]:
    """Ajusta o pipeline da família numa dobra e devolve `(pipeline_ajustado, melhor_ponto)`."""
    fam = familia.strip().lower()
    p = dict(params or {})

    if fam == "b1":
        pipe = make_b1_pipeline(seed=seed)
        pipe.fit(X_fit[B1_FEATURES], y_fit)
        n_iter = int(getattr(pipe.named_steps["clf"], "n_iter_", [1])[0])
        return pipe, n_iter

    if fam in {"elastic_net", "elasticnet"}:
        pre = make_preprocessor("elastic_net")
        clf = LogisticRegression(
            penalty="elasticnet",
            solver="saga",
            C=float(p.get("C", 1.0)),
            l1_ratio=float(p.get("l1_ratio", 0.5)),
            max_iter=int(p.get("max_iter", 500)),
            random_state=seed,
        )
        pipe = Pipeline([("pre", pre), ("clf", clf)])
        pipe.fit(X_fit[M1_FEATURES], y_fit)
        n_iter = int(getattr(clf, "n_iter_", [1])[0])
        return pipe, n_iter

    if fam in {"random_forest", "rf"}:
        pre = make_preprocessor("arvore")
        rf_kwargs: dict[str, Any] = {
            "n_estimators": int(p.get("n_estimators", 200)),
            "max_depth": p.get("max_depth", 10),
            "min_samples_leaf": int(p.get("min_samples_leaf", 20)),
            "max_features": p.get("max_features", "sqrt"),
            "max_samples": p.get("max_samples", None),
            "n_jobs": int(p.get("n_jobs", -1)),
            "random_state": seed,
            # Regra R3: nunca usar class_weight
        }
        clf = RandomForestClassifier(**rf_kwargs)
        pipe = Pipeline([("pre", pre), ("clf", clf)])
        pipe.fit(X_fit[M1_FEATURES], y_fit)
        return pipe, int(rf_kwargs["n_estimators"])

    if fam in {"xgboost", "xgb"}:
        from xgboost import XGBClassifier

        pre = make_preprocessor("arvore")
        X_tr_t = pre.fit_transform(X_fit[M1_FEATURES])
        early_rounds = int(p.get("early_stopping_rounds", 50)) if X_es is not None else None
        xgb_kwargs: dict[str, Any] = {
            "n_estimators": int(p.get("n_estimators", 500)),
            "learning_rate": float(p.get("learning_rate", 0.05)),
            "max_depth": int(p.get("max_depth", 6)),
            "min_child_weight": float(p.get("min_child_weight", 10.0)),
            "subsample": float(p.get("subsample", 0.8)),
            "colsample_bytree": float(p.get("colsample_bytree", 0.8)),
            "reg_lambda": float(p.get("reg_lambda", 1.0)),
            "tree_method": str(p.get("tree_method", "hist")),
            "device": str(p.get("device", "cpu")),
            "eval_metric": "aucpr",
            "early_stopping_rounds": early_rounds,
            "random_state": seed,
            "n_jobs": int(p.get("n_jobs", -1)),
            # Regra R3: sem scale_pos_weight
        }
        clf = XGBClassifier(**xgb_kwargs)
        if X_es is not None and y_es is not None:
            X_es_t = pre.transform(X_es[M1_FEATURES])
            clf.fit(X_tr_t, y_fit, eval_set=[(X_es_t, y_es)], verbose=False)
            best_pt = int(getattr(clf, "best_iteration", xgb_kwargs["n_estimators"] - 1)) + 1
        else:
            clf.fit(X_tr_t, y_fit, verbose=False)
            best_pt = int(xgb_kwargs["n_estimators"])
        pipe = Pipeline([("pre", pre), ("clf", clf)])
        return pipe, best_pt

    if fam == "catboost":
        from catboost import CatBoostClassifier

        # Em CatBoost usamos OrdinalEncoder nas categóricas e numéricas cruas
        pre = make_preprocessor("arvore")
        X_tr_t = pre.fit_transform(X_fit[M1_FEATURES])
        early_rounds = int(p.get("early_stopping_rounds", 50)) if X_es is not None else None
        cb_kwargs: dict[str, Any] = {
            "iterations": int(p.get("iterations", 500)),
            "learning_rate": float(p.get("learning_rate", 0.05)),
            "depth": int(p.get("depth", 6)),
            "l2_leaf_reg": float(p.get("l2_leaf_reg", 3.0)),
            "eval_metric": "PRAUC",
            "random_seed": seed,
            "verbose": False,
            "allow_writing_files": False,
            # Regra R3: sem auto_class_weights ou class_weights
        }
        if p.get("task_type"):
            cb_kwargs["task_type"] = str(p["task_type"])

        clf = CatBoostClassifier(**cb_kwargs)
        if X_es is not None and y_es is not None:
            X_es_t = pre.transform(X_es[M1_FEATURES])
            try:
                clf.fit(
                    X_tr_t,
                    y_fit,
                    eval_set=(X_es_t, y_es),
                    early_stopping_rounds=early_rounds,
                    verbose=False,
                )
            except Exception:
                # Fallback documentado na T-4.6 se GPU não aceitar PRAUC
                cb_kwargs.pop("task_type", None)
                clf = CatBoostClassifier(**cb_kwargs)
                clf.fit(
                    X_tr_t,
                    y_fit,
                    eval_set=(X_es_t, y_es),
                    early_stopping_rounds=early_rounds,
                    verbose=False,
                )
            best_iter = clf.get_best_iteration()
            best_pt = int(best_iter) + 1 if best_iter is not None and best_iter >= 0 else int(
                cb_kwargs["iterations"]
            )
        else:
            clf.fit(X_tr_t, y_fit, verbose=False)
            best_pt = int(cb_kwargs["iterations"])

        _ = get_catboost_cat_indices()
        pipe = Pipeline([("pre", pre), ("clf", clf)])
        return pipe, best_pt

    if fam == "mlp":
        pre = make_preprocessor("mlp")
        X_tr_t = pre.fit_transform(X_fit[M1_FEATURES])
        clf = TorchMLPClassifier(
            hidden_layers=tuple(p.get("hidden_layers", (64,))),
            dropout=float(p.get("dropout", 0.1)),
            weight_decay=float(p.get("weight_decay", 1e-4)),
            lr=float(p.get("lr", 1e-3)),
            batch_size=int(p.get("batch_size", 1024)),
            max_epochs=int(p.get("max_epochs", 200)),
            patience=int(p.get("patience", 10)),
            seed=seed,
            device=p.get("device"),
        )
        if X_es is not None and y_es is not None:
            X_es_t = pre.transform(X_es[M1_FEATURES])
            clf.fit(X_tr_t, y_fit, eval_set=(X_es_t, y_es))
        else:
            clf.fit(X_tr_t, y_fit)
        pipe = Pipeline([("pre", pre), ("clf", clf)])
        return pipe, int(clf.best_iteration_)

    if fam == "tabfm":
        pre = make_preprocessor("mlp")
        clf = TabFMClassifier(
            max_context_rows=int(p.get("max_context_rows", 10000)),
            batch_size=int(p.get("batch_size", 4096)),
            seed=seed,
            device=p.get("device"),
        )
        pipe = Pipeline([("pre", pre), ("clf", clf)])
        pipe.fit(X_fit[M1_FEATURES], y_fit)
        return pipe, int(getattr(clf, "context_size_", 1))

    raise ValueError(f"Família desconhecida em run_loro: '{familia}'")


def run_loro(
    cfg: dict[str, Any],
    familia: str,
    params: dict[str, Any] | None,
    df: pd.DataFrame,
    *,
    fold_df: pd.DataFrame | None = None,
    trial: Any | None = None,
) -> dict[str, Any]:
    """Executa a validação leave-one-region-out (5 dobras) com early stopping interno (T-4.2).

    Garante R1 (`assert_dev_only`), R4 (`assert_allowed_features`), R5 (`Pipeline` por dobra) e
    R6 (validação interna 10% separada de `idx_train` sem tocar a região de validação).
    """
    assert_dev_only(df)
    fam = familia.strip().lower()
    p = dict(params or {})
    seed = int(cfg.get("seed", 20261103))
    frac_val = float(cfg.get("validacao_interna_frac", 0.10))
    order = cfg.get("ordem_dobras", list(DEFAULT_FOLD_ORDER))

    feat = build_feature_frame(df) if "n_comorbidades" not in df.columns else df
    feature_cols = B1_FEATURES if fam == "b1" else M1_FEATURES
    assert_allowed_features(feature_cols)

    y_all = feat["y"].to_numpy(dtype=np.int8)
    oof_p = np.full(len(feat), np.nan, dtype=np.float64)

    folds = loro_folds(feat, ordem_dobras=order)
    pr_auc_por_dobra: dict[str, float] = {}
    melhores_pontos: dict[str, int] = {}
    modelos_por_dobra: dict[str, Pipeline] = {}
    neg_rate = float(p.get("neg_subsample_rate", 1.0)) if fam in {"random_forest", "rf"} else 1.0

    for fold_idx, (regiao, idx_train, idx_val) in enumerate(folds):
        if fam in ITERATIVE_FAMILIES:
            col_parada = f"parada_{regiao}"
            if fold_df is not None and col_parada in fold_df.columns:
                is_parada = fold_df[col_parada].to_numpy(dtype=bool)
                idx_parada = idx_train[is_parada[idx_train]]
                idx_subtrain = idx_train[~is_parada[idx_train]]
            else:
                idx_subtrain, idx_parada = inner_split(idx_train, y_all, frac=frac_val, seed=seed)
            X_fit = feat.iloc[idx_subtrain]
            y_fit = y_all[idx_subtrain]
            X_es = feat.iloc[idx_parada]
            y_es = y_all[idx_parada]
        else:
            idx_used = _subsample_negatives(idx_train, y_all, neg_rate, seed + fold_idx)
            X_fit = feat.iloc[idx_used]
            y_fit = y_all[idx_used]
            X_es = None
            y_es = None

        pipe, best_pt = _fit_fold_model(fam, p, X_fit, y_fit, X_es, y_es, seed)
        X_val = feat.iloc[idx_val][feature_cols]
        raw_probs = pipe.predict_proba(X_val)[:, 1].astype(np.float64)
        val_probs = correct_subsampled_prob(raw_probs, neg_rate)

        oof_p[idx_val] = val_probs
        fold_score = pr_auc(y_all[idx_val], val_probs)
        pr_auc_por_dobra[regiao] = fold_score
        melhores_pontos[regiao] = int(best_pt)
        modelos_por_dobra[regiao] = pipe

        if trial is not None:
            running_mean = float(np.mean(list(pr_auc_por_dobra.values())))
            trial.report(running_mean, step=fold_idx)
            if trial.should_prune():
                import optuna

                raise optuna.TrialPruned()

    assert not np.isnan(oof_p).any(), "Existem linhas sem predição OOF."
    pr_auc_media = float(np.mean(list(pr_auc_por_dobra.values())))
    pr_auc_oof_val = pr_auc(y_all, oof_p)

    return {
        "familia": fam,
        "oof_p": oof_p,
        "pr_auc_por_dobra": pr_auc_por_dobra,
        "pr_auc_media": pr_auc_media,
        "pr_auc_oof": pr_auc_oof_val,
        "melhores_pontos": melhores_pontos,
        "modelos_por_dobra": modelos_por_dobra,
        "neg_subsample_rate": neg_rate,
    }
