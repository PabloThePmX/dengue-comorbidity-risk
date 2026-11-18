"""Treinamento do modelo preditivo, a partir de dados de desenvolvimento (2022–2023).

Fluxo: validar configuração e dados (R1, R4) → predições fora da dobra (leave-one-region-out) →
calibrador ajustado nelas → modelo final em todo o desenvolvimento → avaliação de
desenvolvimento → artefato. Reusa `modelos.ModeloM1`, `cv_oof`, `Calibrador` e `ajustar_final`.
Não há busca de hiperparâmetros: os parâmetros vêm da configuração.
"""

import hashlib
import json
import platform
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path

import numpy as np
import pandas as pd

from dengue_sinan.guard import ANOS_DEV, anos_marcados, marcar_anos, verificar_dev
from dengue_sinan.modelos import Calibrador, ajustar_final, calibrar_cruzado, cv_oof
from dengue_sinan.pipeline import artefatos
from dengue_sinan.pipeline.avaliacao import LIMITACOES, montar_avaliacao
from dengue_sinan.pipeline.contrato import CAMPOS, checar_variaveis, contrato_de_entrada
from dengue_sinan.pipeline.preprocessamento import normalizar_x

ALGORITMOS = ("xgboost", "hgb")
CALIBRADORES = ("nenhum", "platt", "isotonica")
BIBLIOTECAS = ("numpy", "pandas", "pyarrow", "scikit-learn", "xgboost", "joblib")


@dataclass
class ConfigTreino:
    nome_modelo: str
    versao_modelo: str
    algoritmo: str
    params: dict
    calibrador: str
    seed: int
    variaveis: list[str]
    anos_desenvolvimento: list[int]
    n_jobs: int = -1
    paciencia: int = 50
    val_frac: float = 0.1
    max_iter: int = 1000
    extras: dict = field(default_factory=dict)  # origem dos params etc.; só registro

    @classmethod
    def de_arquivo(cls, caminho) -> "ConfigTreino":
        bruto = json.loads(Path(caminho).read_text("utf-8"))
        campos = set(cls.__dataclass_fields__) - {"extras"}
        extras = {k: v for k, v in bruto.items() if k not in campos}
        cfg = cls(**{k: v for k, v in bruto.items() if k in campos}, extras=extras)
        cfg.validar()
        return cfg

    def validar(self) -> None:
        if self.algoritmo not in ALGORITMOS:
            raise ValueError(f"algoritmo {self.algoritmo!r} não suportado; use {ALGORITMOS}")
        if self.calibrador not in CALIBRADORES:
            raise ValueError(f"calibrador {self.calibrador!r} inválido; use {CALIBRADORES}")
        if sorted(self.anos_desenvolvimento) != sorted(ANOS_DEV):
            raise PermissionError(
                f"R1: anos de desenvolvimento devem ser {list(ANOS_DEV)}, recebido "
                f"{self.anos_desenvolvimento}"
            )
        checar_variaveis(self.variaveis)

    def como_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "extras"} | {
            "extras": self.extras
        }


def _ambiente() -> dict:
    versoes = {}
    for pacote in BIBLIOTECAS:
        try:
            versoes[pacote] = metadata.version(pacote)
        except metadata.PackageNotFoundError:
            versoes[pacote] = None
    return {"python": platform.python_version(), "sistema": platform.platform(), **versoes}


def hash_dados(x: pd.DataFrame, y) -> str:
    """Hash do conteúdo E da ordem das linhas e colunas (a ordem altera o ajuste)."""
    h = hashlib.sha256()
    h.update(json.dumps(list(x.columns)).encode())
    h.update(pd.util.hash_pandas_object(x, index=False).to_numpy().tobytes())
    h.update(np.asarray(y, dtype="int8").tobytes())
    return h.hexdigest()


def _ajustar(x, y, regiao, meta, cfg: ConfigTreino) -> dict:
    """Parte que depende de dados e semente. Determinística para a mesma entrada e ambiente."""
    kw = {
        "paciencia": cfg.paciencia,
        "val_frac": cfg.val_frac,
        "max_iter": cfg.max_iter,
        "n_jobs": cfg.n_jobs,
    }
    cv = cv_oof(cfg.algoritmo, cfg.params, x, y, regiao, cfg.seed, meta=meta, **kw)
    oof = cv["oof"]
    ok = ~np.isnan(oof)
    calibrador = Calibrador(cfg.calibrador).ajustar(oof[ok], np.asarray(y)[ok])
    oof_calibrado = calibrar_cruzado(oof, y, regiao, cfg.calibrador, meta=meta)
    n_mediano = int(np.median(cv["melhor_iter"]))
    final = ajustar_final(cfg.algoritmo, cfg.params, x, y, cfg.seed, n_mediano, x_meta=meta, **kw)
    return {
        "cv": cv,
        "oof": oof,
        "oof_calibrado": oof_calibrado,
        "calibrador": calibrador,
        "final": final,
        "n_arvores_final": final.melhor_,
    }


@dataclass
class ResultadoTreino:
    objeto: dict  # o que vai para modelo.joblib
    metadados: dict
    contrato: dict
    avaliacao: dict


def treinar(x, y, regiao, meta, cfg: ConfigTreino, dados_info: dict | None = None):
    """Treina e devolve o `ResultadoTreino`. Falha se houver dado fora de 2022–2023 (R1)."""
    cfg.validar()
    verificar_dev(x, regiao, meta=meta, contexto="treino.treinar")
    x = normalizar_x(x, cfg.variaveis)
    marcar_anos(x, anos_marcados(x, regiao) or pd.unique(meta["ANO"]))
    y = np.asarray(y)
    r = _ajustar(x, y, regiao, meta, cfg)
    escopo = "desenvolvimento 2022–2023, validação cruzada leave-one-region-out"
    avaliacao = montar_avaliacao(
        y[~np.isnan(r["oof"])],
        r["oof"][~np.isnan(r["oof"])],
        r["oof_calibrado"][~np.isnan(r["oof"])],
        r["cv"]["pr_auc_dobra"],
        escopo,
    )
    meta_modelo = {
        "nome_modelo": cfg.nome_modelo,
        "versao_modelo": cfg.versao_modelo,
        "algoritmo": cfg.algoritmo,
        "params": cfg.params,
        "calibrador": cfg.calibrador,
        "variaveis_de_entrada": list(cfg.variaveis),
        "tipos_esperados": {v: CAMPOS[v].tipo for v in cfg.variaveis},
        "preprocessamento": [
            "validação contra o contrato (tipos estritos, intervalos, categorias)",
            "sexo ausente → I; gestante ausente → 0; idade ausente → erro",
            "sexo: categorias fixas [F, M, I] com código ordinal 0, 1, 2",
            "sem escala, imputação ou outro estado ajustado nos dados",
        ],
        "anos_desenvolvimento": list(cfg.anos_desenvolvimento),
        "data_treinamento_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "n_linhas": int(len(y)),
        "prevalencia_desenvolvimento": float(y.mean()),
        "dados": {"hash_conteudo_e_ordem": hash_dados(x, y), **(dados_info or {})},
        "ambiente": _ambiente(),
        "config": cfg.como_dict(),
        "validacao": {
            "melhor_iteracao_por_dobra": r["cv"]["melhor_iter"],
            "n_arvores_modelo_final": int(r["n_arvores_final"]),
        },
        "reprodutibilidade": {
            "semente": cfg.seed,
            "n_jobs": cfg.n_jobs,
            "condicoes": [
                "mesmos dados, na mesma ordem de linhas e de colunas (hash em dados)",
                "mesma configuração e semente",
                "mesmas versões de numpy, pandas, scikit-learn e xgboost (em ambiente)",
                "mesmo sistema operacional e build do xgboost: não testado",
            ],
            "fontes_de_variacao": [
                "ordem das linhas, ordem das colunas e semente mudam o ajuste (auditoria 1D)",
                "número de threads não alterou o resultado nos testes da auditoria 1D",
            ],
            "determinismo": "Repetição com os mesmos insumos reproduz as predições (verificado "
            "por `treinar --repetir-e-comparar` e por teste). Não há garantia entre plataformas.",
        },
        "limitacoes": LIMITACOES,
        "aviso": "Modelo exploratório. Não é a v1 histórica e não a substitui.",
    }
    objeto = {
        "motor": r["final"].motor_,
        "calibrador": r["calibrador"],
        "algoritmo": cfg.algoritmo,
        "variaveis": list(cfg.variaveis),
    }
    return ResultadoTreino(
        objeto, meta_modelo, contrato_de_entrada(list(cfg.variaveis)), avaliacao
    ), r


def treinar_e_salvar(x, y, regiao, meta, cfg: ConfigTreino, pasta_base, dados_info=None) -> Path:
    resultado, _ = treinar(x, y, regiao, meta, cfg, dados_info)
    return artefatos.salvar(
        pasta_base,
        cfg.nome_modelo,
        cfg.versao_modelo,
        resultado.objeto,
        resultado.metadados,
        resultado.contrato,
        resultado.avaliacao,
    )


def repetir_e_comparar(x, y, regiao, meta, cfg: ConfigTreino) -> dict:
    """Treina duas vezes com os mesmos insumos e compara. Não promete nada além do que mede."""
    x = normalizar_x(x, cfg.variaveis)
    marcar_anos(x, anos_marcados(x, regiao) or pd.unique(meta["ANO"]))
    a = _ajustar(x, y, regiao, meta, cfg)
    b = _ajustar(x, y, regiao, meta, cfg)
    return {
        "oof_identico": bool(np.array_equal(a["oof"], b["oof"], equal_nan=True)),
        "oof_calibrado_identico": bool(
            np.array_equal(a["oof_calibrado"], b["oof_calibrado"], equal_nan=True)
        ),
        "iteracoes_identicas": a["cv"]["melhor_iter"] == b["cv"]["melhor_iter"],
        "n_arvores_final": [int(a["n_arvores_final"]), int(b["n_arvores_final"])],
    }
