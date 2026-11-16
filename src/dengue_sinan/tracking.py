"""Rastreamento de experimentos no MLflow (T-2.5, D-15, P7, R7, R8).

Cada run registra a configuração inteira, a semente, os hashes dos dados (`data/manifest.json`),
o commit do git e o hardware. As predições fora da dobra (OOF) vão para um Parquet dentro da
pasta de dados (`caminhos.dados`), nunca para `reports/` (R7).

Decisão de diretório de saída: `log_oof_predictions` recebe `pasta_saida` explícito e, por padrão,
usa `<caminhos.dados>/oof`. A pasta de dados fica fora do git (`data/` no `.gitignore`); o arquivo
não vai para o MLflow, porque copiaria microdados para `mlruns/`. Só o caminho relativo, o nº de
linhas e o SHA-256 do arquivo são registrados como params do run.
"""

import hashlib
import json
import os
import platform
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import mlflow
import pandas as pd

from dengue_sinan import verify
from dengue_sinan.guard import assert_dev_only

NOME_EXPERIMENTO = "dengue-comorbidity-risk"
COLUNAS_OOF = ("ANO", "regiao", "y", "p")


def _caminho(cfg: dict, chave: str) -> Path:
    """Caminho de `cfg["caminhos"][chave]`; relativo é a partir da raiz do repositório."""
    caminho = Path(cfg["caminhos"][chave])
    return caminho if caminho.is_absolute() else (verify.REPO / caminho).resolve()


def _achatar(valor, prefixo: str = "") -> dict[str, str]:
    """Transforma o config aninhado em params `chave.subchave` (o MLflow aceita só texto plano)."""
    if isinstance(valor, dict):
        saida: dict[str, str] = {}
        for chave, sub in valor.items():
            saida.update(_achatar(sub, f"{prefixo}.{chave}" if prefixo else str(chave)))
        return saida
    return {prefixo: str(valor)}


def _hashes_dados(cfg: dict) -> dict[str, str]:
    """SHA-256 do .dbc e do Parquet de cada ano de desenvolvimento, lidos de manifest.json."""
    manifesto = _caminho(cfg, "dados") / "manifest.json"
    if not manifesto.exists():
        return {"dados.manifest": "ausente"}
    dados = json.loads(manifesto.read_text(encoding="utf-8"))
    params: dict[str, str] = {}
    for ano in cfg["anos_dev"]:
        entrada = dados.get(str(ano), {})
        params[f"dados.{ano}.sha256_dbc"] = entrada.get("sha256_dbc", "ausente")
        params[f"dados.{ano}.sha256_parquet"] = entrada.get("sha256_parquet", "ausente")
    return params


def _hardware(cfg: dict) -> dict[str, str]:
    """Reaproveita `verify.environment` (GPU, RAM, vCPUs); acrescenta só o nome da CPU."""
    obtidos = {c["nome"]: c["obtido"] for c in verify.environment(cfg)}
    return {
        "hardware.cpu": platform.processor() or "desconhecido",
        "hardware.vcpus": str(obtidos["vcpus"]),
        "hardware.ram_gib": str(obtidos["ram_gib"]),
        "hardware.gpu": str(obtidos["gpu"]),
    }


def _permitir_backend_de_pasta() -> None:
    """Liga o opt-out do backend de arquivos (`mlruns/`) do MLflow 3.x, que vem em "manutenção".

    Mantemos a pasta `mlruns/` do plano e optamos por ela explicitamente. `setdefault` não
    sobrescreve um valor que o usuário definiu (ex.: "false"), respeitando a escolha dele.
    """
    os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")


@contextmanager
def start_run(
    cfg: dict, nome: str, tags: dict[str, str] | None = None
) -> Iterator[mlflow.ActiveRun]:
    """Abre um run no MLflow e registra config, semente, hashes, commit e hardware.

    Use com `with`: o run fecha mesmo se o bloco levantar erro.
    """
    _permitir_backend_de_pasta()
    mlflow.set_tracking_uri(str(_caminho(cfg, "mlruns")))
    mlflow.set_experiment(NOME_EXPERIMENTO)
    tags_run = {**(tags or {}), "git_commit": verify.commit_atual()}
    with mlflow.start_run(run_name=nome, tags=tags_run) as run:
        mlflow.log_params({**_achatar(cfg), **_hashes_dados(cfg), **_hardware(cfg)})
        mlflow.log_dict(cfg, "config.json")
        yield run


def _exigir_run_ativo() -> None:
    if mlflow.active_run() is None:
        raise RuntimeError("chame dentro de start_run(...)")


def log_fold_metrics(regiao: str, metricas: dict[str, float]) -> None:
    """Grava as métricas da dobra `regiao` como `<regiao>/<métrica>` (ex.: `Sudeste/pr_auc`)."""
    _exigir_run_ativo()
    if not regiao:
        raise ValueError("regiao vazia")
    mlflow.log_metrics({f"{regiao}/{nome}": float(valor) for nome, valor in metricas.items()})


def _checar_destino(cfg: dict, destino: Path) -> None:
    """Recusa destino fora de `caminhos.dados` ou dentro de `caminhos.relatorios` (R7)."""
    destino = destino.resolve()
    if destino.is_relative_to(_caminho(cfg, "relatorios")):
        raise ValueError(f"{destino} está em reports/: microdados não vão para relatórios (R7)")
    if not destino.is_relative_to(_caminho(cfg, "dados")):
        raise ValueError(f"{destino} está fora de caminhos.dados ({_caminho(cfg, 'dados')}); "
                         "a saída das predições deve ficar na pasta de dados, fora do git (R7)")


def log_oof_predictions(
    cfg: dict,
    nome_modelo: str,
    df_oof: pd.DataFrame,
    pasta_saida: Path | None = None,
) -> Path:
    """Salva as predições OOF em `<pasta>/oof_<modelo>.parquet` e registra o arquivo no run.

    `df_oof` precisa das colunas `COLUNAS_OOF` e de `ANO` em desenvolvimento (guard, R1).
    `pasta_saida` padrão: `<caminhos.dados>/oof`. Recusa destino em `reports/` ou fora da pasta de
    dados, antes de gravar qualquer coisa.
    """
    _exigir_run_ativo()
    faltando = [c for c in COLUNAS_OOF if c not in df_oof.columns]
    if faltando:
        raise ValueError(f"df_oof sem as colunas {faltando}")
    assert_dev_only(df_oof)
    pasta = Path(pasta_saida) if pasta_saida is not None else _caminho(cfg, "dados") / "oof"
    destino = pasta / f"oof_{nome_modelo}.parquet"
    _checar_destino(cfg, destino)

    destino.parent.mkdir(parents=True, exist_ok=True)
    df_oof.to_parquet(destino, index=False)
    sha = hashlib.sha256(destino.read_bytes()).hexdigest()
    mlflow.log_params({
        f"oof.{nome_modelo}.arquivo": destino.name,
        f"oof.{nome_modelo}.linhas": str(len(df_oof)),
        f"oof.{nome_modelo}.sha256": sha,
    })
    return destino
