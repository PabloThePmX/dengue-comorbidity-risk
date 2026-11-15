"""Persistência e predição com o bundle final M1."""

from pathlib import Path
from typing import Any

import joblib
import mlflow
import pandas as pd
from pandas.api.types import (
    is_bool_dtype,
    is_float_dtype,
    is_integer_dtype,
)

from dengue_sinan.calibration import apply_calibrator


class M1PyFuncModel(mlflow.pyfunc.PythonModel):
    def __init__(self, bundle: dict):
        self.bundle = bundle

    def predict(
        self,
        context: mlflow.pyfunc.PythonModelContext,
        model_input: pd.DataFrame,
        params: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        return predict_bundle(self.bundle, model_input)


def mlflow_signature(features: pd.DataFrame):
    """Cria assinatura tipada sem incluir exemplos com dados de pacientes."""
    from mlflow.models import ModelSignature
    from mlflow.types import ColSpec, DataType, Schema

    inputs = []
    for name, dtype in features.dtypes.items():
        if is_bool_dtype(dtype):
            data_type = DataType.boolean
        elif is_integer_dtype(dtype):
            data_type = DataType.long
        elif is_float_dtype(dtype):
            data_type = DataType.double
        else:
            data_type = DataType.string
        inputs.append(ColSpec(data_type, name))
    outputs = Schema(
        [
            ColSpec(DataType.double, "risco"),
            ColSpec(DataType.boolean, "alto_risco"),
            ColSpec(DataType.string, "modelo_versao"),
        ]
    )
    return ModelSignature(inputs=Schema(inputs), outputs=outputs)


def save_bundle(bundle: dict, path: str | Path) -> Path:
    """Valida e serializa o pipeline, calibrador, limiar e metadados do modelo."""
    required = {"pipeline", "calibrador", "limiar", "metadados", "melhores_pontos"}
    missing = required - set(bundle)
    if missing:
        raise ValueError(f"Bundle M1 incompleto: faltam {sorted(missing)}.")
    if not 0 <= float(bundle["limiar"]) <= 1:
        raise ValueError("O limiar do bundle deve estar entre 0 e 1.")
    if not hasattr(bundle["pipeline"], "predict_proba"):
        raise TypeError("O pipeline do bundle precisa implementar predict_proba.")
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    joblib.dump(bundle, temporary)
    temporary.replace(output)
    return output


def load_bundle(path: str | Path) -> dict:
    """Carrega um bundle salvo e valida seu contrato mínimo."""
    bundle = joblib.load(path)
    if not isinstance(bundle, dict):
        raise TypeError("O artefato M1 não contém um bundle.")
    required = {"pipeline", "calibrador", "limiar", "metadados", "melhores_pontos"}
    missing = required - set(bundle)
    if missing:
        raise ValueError(f"Bundle M1 inválido: faltam {sorted(missing)}.")
    if not hasattr(bundle["pipeline"], "predict_proba"):
        raise TypeError("O pipeline salvo não implementa predict_proba.")
    return bundle


def predict_bundle(bundle: dict, features: pd.DataFrame) -> pd.DataFrame:
    """Retorna probabilidades calibradas e a classificação no limiar congelado."""
    if not isinstance(features, pd.DataFrame) or features.empty:
        raise ValueError("features deve ser um DataFrame não vazio.")
    raw_probability = bundle["pipeline"].predict_proba(features)[:, 1]
    risk = apply_calibrator(bundle["calibrador"], raw_probability)
    threshold = float(bundle["limiar"])
    model_version = str(bundle["metadados"]["modelo_versao"])
    return pd.DataFrame(
        {
            "risco": risk,
            "alto_risco": risk >= threshold,
            "modelo_versao": model_version,
        },
        index=features.index,
    )