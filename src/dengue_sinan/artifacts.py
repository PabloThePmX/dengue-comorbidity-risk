"""Serialização e carregamento de artefatos de modelos com metadados obrigatórios (T-3.6, FR-12)."""

import datetime as dt
import platform
import subprocess
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any

import joblib

REQUIRED_METADATA_KEYS = (
    "versao_codigo",
    "hashes_dados",
    "config",
    "data_treino",
    "metricas_validacao",
    "lista_features",
    "versoes_bibliotecas",
)

_DEFAULT_LIBRARIES = (
    "pandas",
    "numpy",
    "scikit-learn",
    "statsmodels",
    "pyarrow",
    "joblib",
)


class ModelBundle(dict):
    """Pacote serializado que funciona como dicionário e delega atributos ao modelo."""

    def __getattr__(self, name: str) -> Any:
        if name in self:
            return self[name]
        model = self.get("model")
        if model is not None and hasattr(model, name):
            return getattr(model, name)
        raise AttributeError(f"'ModelBundle' e o modelo interno não possuem o atributo '{name}'.")


def _git_commit() -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return res.stdout.strip()
    except Exception:
        return "desconhecido"


def collect_library_versions(libraries: tuple[str, ...] = _DEFAULT_LIBRARIES) -> dict[str, str]:
    """Coleta versões do Python e das bibliotecas principais."""
    versions: dict[str, str] = {"python": platform.python_version()}
    for pkg in libraries:
        try:
            versions[pkg] = importlib_metadata.version(pkg)
        except importlib_metadata.PackageNotFoundError:
            continue
    return versions


def save_bundle(
    obj: Any,
    caminho: str | Path,
    metadados: dict[str, Any] | None = None,
    *,
    cfg: dict[str, Any] | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> Path:
    """Salva o objeto do modelo e os metadados obrigatórios da FR-12 em disco."""
    raw_meta = dict(metadados or {})
    if extra_metadata:
        raw_meta.update(extra_metadata)
    if cfg is not None and "config" not in raw_meta:
        raw_meta["config"] = cfg
    full_meta: dict[str, Any] = {
        "versao_codigo": raw_meta.get("versao_codigo") or _git_commit(),
        "hashes_dados": raw_meta.get("hashes_dados", {}),
        "config": raw_meta.get("config", {}),
        "data_treino": raw_meta.get("data_treino")
        or dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "metricas_validacao": raw_meta.get("metricas_validacao", {}),
        "lista_features": list(raw_meta.get("lista_features", [])),
        "versoes_bibliotecas": raw_meta.get("versoes_bibliotecas") or collect_library_versions(),
    }
    for extra_k, extra_v in raw_meta.items():
        if extra_k not in full_meta:
            full_meta[extra_k] = extra_v

    missing = [k for k in REQUIRED_METADATA_KEYS if k not in full_meta]
    if missing:
        raise ValueError(f"Metadados obrigatórios ausentes no artefato: {missing}")

    out_path = Path(caminho)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"model": obj, "metadados": full_meta, "metadata": full_meta}
    joblib.dump(payload, out_path, compress=3)
    return out_path


def _ensure_scipy_bspline_compat() -> None:
    """Garante compatibilidade de unpickle para `BSpline` entre SciPy 1.14 e 1.15+."""
    try:
        from scipy.interpolate import BSpline

        orig_setstate = getattr(BSpline, "__setstate__", None)
        if orig_setstate is not None and not getattr(
            orig_setstate, "_dengue_compat_patched", False
        ):

            def _compat_setstate(self: Any, state: Any) -> None:
                if isinstance(state, dict) and "t" in state and "c" in state and "k" in state:
                    BSpline.__init__(
                        self,
                        state["t"],
                        state["c"],
                        state["k"],
                        extrapolate=state.get("extrapolate", True),
                        axis=state.get("axis", 0),
                    )
                else:
                    orig_setstate(self, state)

            _compat_setstate._dengue_compat_patched = True  # type: ignore[attr-defined]
            BSpline.__setstate__ = _compat_setstate  # type: ignore[method-assign]
    except Exception:
        pass


def load_bundle(caminho: str | Path) -> ModelBundle:
    """Carrega o pacote salvo por `save_bundle` e valida a presença dos metadados da FR-12."""
    in_path = Path(caminho)
    if not in_path.is_file():
        raise FileNotFoundError(f"Artefato não encontrado: {in_path}")

    _ensure_scipy_bspline_compat()
    loaded = joblib.load(in_path)
    if not isinstance(loaded, dict) or "model" not in loaded or "metadados" not in loaded:
        raise ValueError(f"Formato de artefato inválido em {in_path}.")

    meta = loaded["metadados"]
    loaded.setdefault("metadata", meta)
    missing = [k for k in REQUIRED_METADATA_KEYS if k not in meta]
    if missing:
        raise ValueError(f"Artefato em {in_path} não contém metadados obrigatórios: {missing}")

    return ModelBundle(loaded)
