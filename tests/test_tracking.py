import json
import os

import mlflow
import pandas as pd
import pytest
from mlflow.tracking import MlflowClient

from dengue_sinan import tracking, verify
from dengue_sinan.config import load_config

SHA_DBC_2022 = "aa" * 32
SHA_PARQUET_2022 = "bb" * 32


@pytest.fixture
def cfg(tmp_path):
    """Config real, com dados e mlruns em pastas temporárias (nada vai para o projeto)."""
    base = load_config()
    dados = tmp_path / "data"
    dados.mkdir()
    (dados / "manifest.json").write_text(json.dumps({
        "2022": {"sha256_dbc": SHA_DBC_2022, "sha256_parquet": SHA_PARQUET_2022},
        "2023": {"sha256_dbc": "cc" * 32, "sha256_parquet": "dd" * 32},
    }), encoding="utf-8")
    return {**base, "caminhos": {**base["caminhos"], "dados": str(dados),
                                 "mlruns": str(tmp_path / "mlruns")}}


def _oof(anos=(2022, 2023)):
    return pd.DataFrame({
        "ANO": list(anos),
        "regiao": ["Sudeste"] * len(anos),
        "y": [0] * len(anos),
        "p": [0.001] * len(anos),
    })


def _ler_run(run_id):
    return MlflowClient().get_run(run_id)


def test_run_registra_config_seed_hashes_commit_e_hardware(cfg):
    with tracking.start_run(cfg, "teste-t25", {"tarefa": "T-2.5"}) as run:
        run_id = run.info.run_id

    lido = _ler_run(run_id)
    params, tags = lido.data.params, lido.data.tags
    assert lido.info.run_name == "teste-t25"
    assert tags["tarefa"] == "T-2.5"
    # config inteiro, achatado: seed, valores aninhados e listas
    assert params["seed"] == str(cfg["seed"])
    assert params["ambiente.gpu"] == cfg["ambiente"]["gpu"]
    assert params["optuna.max_tentativas.xgboost"] == "30"
    # hashes do manifest, por ano de desenvolvimento
    assert params["dados.2022.sha256_dbc"] == SHA_DBC_2022
    assert params["dados.2022.sha256_parquet"] == SHA_PARQUET_2022
    assert params["dados.2023.sha256_dbc"] == "cc" * 32
    # commit: o mesmo que o verify grava (ou "desconhecido" sem git)
    assert tags["git_commit"] == verify.commit_atual()
    # hardware: reaproveitado de verify.environment
    assert {"hardware.cpu", "hardware.vcpus", "hardware.ram_gib", "hardware.gpu"} <= params.keys()
    # config completo como artefato JSON
    artefatos = [a.path for a in MlflowClient().list_artifacts(run_id)]
    assert "config.json" in artefatos


def test_sem_manifest_registra_ausente_sem_quebrar(cfg, tmp_path):
    (tmp_path / "data" / "manifest.json").unlink()
    with tracking.start_run(cfg, "sem-manifest") as run:
        pass
    params = _ler_run(run.info.run_id).data.params
    assert params["dados.manifest"] == "ausente"


def test_commit_desconhecido_sem_git_nao_quebra_o_run(cfg, monkeypatch):
    def sem_git(*args, **kwargs):
        raise OSError("git não encontrado")

    monkeypatch.setattr(verify.subprocess, "run", sem_git)
    with tracking.start_run(cfg, "sem-git") as run:
        pass
    assert _ler_run(run.info.run_id).data.tags["git_commit"] == "desconhecido"


def test_opt_out_do_backend_de_pasta_e_ligado_quando_ausente(monkeypatch):
    # setenv antes do delenv: o monkeypatch passa a restaurar o estado original no teardown,
    # mesmo quando a variável não existia, e o "true" não vaza para os outros testes.
    monkeypatch.setenv("MLFLOW_ALLOW_FILE_STORE", "x")
    monkeypatch.delenv("MLFLOW_ALLOW_FILE_STORE")
    tracking._permitir_backend_de_pasta()
    assert os.environ["MLFLOW_ALLOW_FILE_STORE"] == "true"


def test_opt_out_respeita_escolha_explicita_do_usuario(monkeypatch):
    monkeypatch.setenv("MLFLOW_ALLOW_FILE_STORE", "false")
    tracking._permitir_backend_de_pasta()
    assert os.environ["MLFLOW_ALLOW_FILE_STORE"] == "false"


def test_log_fold_metrics_grava_com_regiao_na_chave(cfg):
    with tracking.start_run(cfg, "dobras") as run:
        tracking.log_fold_metrics("Sudeste", {"pr_auc": 0.0021, "brier": 0.0016})
        tracking.log_fold_metrics("Norte", {"pr_auc": 0.0009})

    metricas = _ler_run(run.info.run_id).data.metrics
    assert metricas == {"Sudeste/pr_auc": 0.0021, "Sudeste/brier": 0.0016, "Norte/pr_auc": 0.0009}


def test_log_oof_grava_parquet_no_diretorio_pedido(cfg, tmp_path):
    pasta = tmp_path / "data" / "oof"
    df = _oof()
    with tracking.start_run(cfg, "oof") as run:
        destino = tracking.log_oof_predictions(cfg, "B1", df, pasta_saida=pasta)

    assert destino == pasta / "oof_B1.parquet"
    pd.testing.assert_frame_equal(pd.read_parquet(destino), df)
    params = _ler_run(run.info.run_id).data.params
    assert params["oof.B1.arquivo"] == "oof_B1.parquet"
    assert params["oof.B1.linhas"] == "2"
    assert len(params["oof.B1.sha256"]) == 64


def test_log_oof_padrao_fica_em_dados_oof(cfg, tmp_path):
    with tracking.start_run(cfg, "oof-padrao"):
        destino = tracking.log_oof_predictions(cfg, "B0", _oof())
    assert destino == tmp_path / "data" / "oof" / "oof_B0.parquet"
    assert destino.exists()


def test_recusa_destino_dentro_de_reports(cfg):
    destino = verify.REPO / "reports" / "oof_B1.parquet"
    with tracking.start_run(cfg, "recusa-reports"):
        with pytest.raises(ValueError, match="reports/"):
            tracking.log_oof_predictions(cfg, "B1", _oof(), pasta_saida=destino.parent)
    assert not destino.exists()


def test_recusa_destino_fora_da_pasta_de_dados(cfg, tmp_path):
    fora = tmp_path / "fora"
    with tracking.start_run(cfg, "recusa-fora"):
        with pytest.raises(ValueError, match="fora de caminhos.dados"):
            tracking.log_oof_predictions(cfg, "B1", _oof(), pasta_saida=fora)
    assert not (fora / "oof_B1.parquet").exists()


def test_recusa_df_com_linha_de_2024(cfg, tmp_path):
    with tracking.start_run(cfg, "recusa-2024"):
        with pytest.raises(RuntimeError, match="2024 é teste congelado"):
            tracking.log_oof_predictions(cfg, "B1", _oof((2022, 2024)),
                                         pasta_saida=tmp_path / "data" / "oof")


def test_recusa_df_sem_colunas_oof(cfg, tmp_path):
    with tracking.start_run(cfg, "sem-colunas"):
        with pytest.raises(ValueError, match="sem as colunas"):
            tracking.log_oof_predictions(cfg, "B1", pd.DataFrame({"ANO": [2022]}),
                                         pasta_saida=tmp_path / "data" / "oof")


def test_funcoes_de_log_exigem_run_ativo(cfg, tmp_path):
    with pytest.raises(RuntimeError, match="start_run"):
        tracking.log_fold_metrics("Sul", {"pr_auc": 0.1})
    with pytest.raises(RuntimeError, match="start_run"):
        tracking.log_oof_predictions(cfg, "B1", _oof(), pasta_saida=tmp_path / "data")
    assert mlflow.active_run() is None
