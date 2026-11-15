"""Explicações SHAP globais agregadas para o melhor modelo de árvore."""

from pathlib import Path

import numpy as np
import pandas as pd
import shap
from sklearn.model_selection import train_test_split

from dengue_sinan.dataset import build_feature_frame
from dengue_sinan.guard import assert_dev_only
from dengue_sinan.retrain import fit_final_pipeline

_TREE_MODELS = {"random_forest", "xgboost", "catboost"}


def _positive_class_values(values) -> np.ndarray:
    if isinstance(values, list):
        if len(values) != 2:
            raise ValueError("SHAP deve retornar valores para as duas classes.")
        values = values[1]
    array = np.asarray(values)
    if array.ndim == 3 and array.shape[-1] == 2:
        array = array[:, :, 1]
    if array.ndim != 2:
        raise ValueError(f"Formato SHAP não suportado: {array.shape}.")
    return array


def generate_global_shap(
    results: dict[str, dict],
    df: pd.DataFrame,
    cfg: dict,
    reports_dir: str | Path,
    *,
    sample_size: int = 50_000,
) -> dict:
    """Gera summary plot e interações para o modelo de árvore com maior PR-AUC."""
    assert_dev_only(df)
    candidates = [
        (name, result)
        for name, result in results.items()
        if name in _TREE_MODELS
    ]
    if not candidates:
        raise ValueError("SHAP global requer ao menos um modelo de árvore concluído.")
    model_name, result = max(
        candidates,
        key=lambda item: float(item[1]["mean_pr_auc"]),
    )
    pipeline, params, final_point = fit_final_pipeline(
        model_name, result["best_params"], result["best_points"], df, cfg
    )
    features = build_feature_frame(df)
    size = min(int(sample_size), len(features))
    if size < 2:
        raise ValueError("A amostra SHAP precisa conter ao menos duas linhas.")
    if size == len(features):
        sample_indices = np.arange(len(features))
    else:
        sample_indices, _ = train_test_split(
            np.arange(len(features)),
            train_size=size,
            stratify=df["y"].to_numpy(dtype=np.int8),
            random_state=int(cfg["seed"]),
        )
    sample = features.iloc[sample_indices]
    estimator = pipeline.named_steps["modelo"]
    if model_name == "catboost":
        categorical = [
            column for column in estimator.feature_names_
            if column in sample.columns
        ]
        sample = sample.astype({column: str for column in categorical})
    else:
        sample = pipeline.named_steps["preprocessamento"].transform(sample)

    explainer = shap.TreeExplainer(estimator)
    explanation = explainer(sample)
    values = _positive_class_values(explanation.values)
    names = (
        list(features.columns)
        if model_name == "catboost"
        else list(pipeline.named_steps["preprocessamento"].get_feature_names_out())
    )
    output = Path(reports_dir) / "shap"
    output.mkdir(parents=True, exist_ok=True)
    shap.summary_plot(
        values,
        sample,
        feature_names=names,
        plot_type="bar",
        show=False,
        max_display=20,
    )
    import matplotlib.pyplot as plt

    plt.gcf().suptitle("Explica o modelo, não causa; instável com features correlacionadas")
    plt.tight_layout()
    plt.savefig(output / "importancia_global.png", dpi=160, bbox_inches="tight")
    plt.close()

    interactions = explainer.shap_interaction_values(sample)
    if isinstance(interactions, list):
        if len(interactions) != 2:
            raise ValueError("SHAP deve retornar interações para as duas classes.")
        interactions = interactions[1]
    interactions = np.asarray(interactions)
    if interactions.ndim == 4 and interactions.shape[-1] == 2:
        interactions = interactions[:, :, :, 1]
    if interactions.ndim != 3:
        raise ValueError(f"Formato SHAP de interações não suportado: {interactions.shape}.")
    shap.summary_plot(
        interactions,
        sample,
        feature_names=names,
        show=False,
        max_display=20,
    )
    plt.gcf().suptitle("Interações: explica o modelo, não causa")
    plt.tight_layout()
    plt.savefig(output / "interacoes_global.png", dpi=160, bbox_inches="tight")
    plt.close()
    return {
        "modelo": model_name,
        "pipeline": pipeline,
        "params": params,
        "ponto_final": final_point,
        "linhas": size,
        "arquivos": [
            str(output / "importancia_global.png"),
            str(output / "interacoes_global.png"),
        ],
    }
