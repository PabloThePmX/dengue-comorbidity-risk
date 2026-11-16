"""Verificação da T-2.8 (Marco 2, no PC local, D-66): grava reports/verificacao/T-2.8.json.

Roda B0, B1 e B2 nas dobras da T-2.3 (hash conferido com o do relatório T-2.3), registra os três
runs no MLflow, escreve reports/baselines.md e confere, relendo os runs pela API do MLflow:
- PR-AUC OOF de B0 ≈ prevalência do desenvolvimento (config/esperado.yaml);
- PR-AUC OOF de B1 > B0;
- métricas de B2 finitas;
- os valores lidos dos runs são os calculados (sem depender da UI);
- exatamente 3 runs de baseline no experimento e todos FINISHED.
"""

import json
import math
from pathlib import Path

import mlflow
import pandas as pd
import yaml
from mlflow.tracking import MlflowClient

from dengue_sinan import baselines, dataset, folds, tracking, verify
from dengue_sinan.profiling import COMORBIDADES

ESPERADO_PADRAO = Path(__file__).resolve().parents[2] / "config" / "esperado.yaml"
TOLERANCIA_PREVALENCIA = 0.0002  # "≈ 0,0016" do spec: ±0,02 pp absolutos
TOLERANCIA_LEITURA = 1e-12       # o MLflow guarda o float tal como foi gravado
METRICA_PRIMARIA = {"B0": "pr_auc", "B1": "pr_auc", "B2": "f2"}
COLUNAS_USADAS = ["ANO", "LINHA", "regiao", "y", "idade_anos", "sexo", "gestante",
                  "LACO", "PETEQUIA_N", *COMORBIDADES]


def hash_dobras_t23(cfg: dict) -> str:
    """Hash do conteúdo das dobras, como ficou gravado no relatório T-2.3 (D-72)."""
    caminho = Path(cfg["caminhos"]["relatorios"]) / "verificacao" / "T-2.3.json"
    relatorio = json.loads(caminho.read_text(encoding="utf-8"))
    for check in relatorio["checks"]:
        if check["nome"] == "hash_conteudo_dobras":
            return check["obtido"]
    raise ValueError(f"{caminho} sem o check hash_conteudo_dobras")


def carregar_features_com_dobras(cfg: dict, hash_esperado: str) -> pd.DataFrame:
    """Features do desenvolvimento com `papel_<região>` da T-2.3 (ANO e LINHA como chave)."""
    pop, _flow, _reasons = dataset.load_population_with_flow(cfg, list(cfg["anos_dev"]))
    feat = dataset.build_feature_frame(pop)[COLUNAS_USADAS]
    del pop
    caminho = Path(cfg["caminhos"]["dados"]) / "folds" / "dobras_dev.parquet"
    dobras = folds.load_folds(caminho, hash_esperado)  # recusa se o hash não bater (D-72)
    papeis = [f"papel_{r}" for r in cfg["ordem_dobras"]]
    df = feat.merge(dobras[["ANO", "LINHA", "dobra", *papeis]], on=["ANO", "LINHA"],
                    how="inner", validate="one_to_one")
    if len(df) != len(feat) or len(df) != len(dobras):
        raise ValueError("casos das dobras não batem com a população de desenvolvimento")
    if not (df["regiao"].astype(str) == df["dobra"].astype(str)).all():
        raise ValueError("região da população e dobra da T-2.3 divergem")
    return df.drop(columns="dobra")


def _runs_por_baseline(cfg: dict) -> tuple[int, dict[str, object]]:
    """Lê de volta os runs do experimento pela API. Devolve (total de runs, {nome: run})."""
    tracking._permitir_backend_de_pasta()  # mesma opção do start_run (MLflow 3.x, pasta)
    mlflow.set_tracking_uri(str(tracking._caminho(cfg, "mlruns")))
    client = MlflowClient()
    experimento = client.get_experiment_by_name(tracking.NOME_EXPERIMENTO)
    if experimento is None:
        return 0, {}
    runs = client.search_runs([experimento.experiment_id], max_results=100)
    por_nome: dict[str, object] = {}
    for run in runs:
        nome = run.data.tags.get("baseline")
        if nome in baselines.NOMES:
            por_nome[nome] = run
    return len(runs), por_nome


def _checks(cfg: dict, resultados: dict, ids: dict[str, str], caminho_md: Path) -> list[dict]:
    esperado = yaml.safe_load(ESPERADO_PADRAO.read_text(encoding="utf-8"))["desenvolvimento"]
    prevalencia = esperado["eventos_total"] / esperado["populacao_total"]
    pr_b0 = resultados["B0"]["oof"]["pr_auc"]
    pr_b1 = resultados["B1"]["oof"]["pr_auc"]
    metricas_b2 = resultados["B2"]["oof"]
    eventos = [int(v) for v in resultados["B0"]["oof_df"].groupby("regiao")["y"].sum()]

    checks = [
        verify.check("pr_auc_oof_B0_aprox_prevalencia", prevalencia, pr_b0,
                     tolerancia=TOLERANCIA_PREVALENCIA),
        verify.check("pr_auc_oof_B1_maior_que_B0", True, pr_b1 > pr_b0),
        verify.check("metricas_b2_finitas", True,
                     all(math.isfinite(v) for v in metricas_b2.values())),
        verify.check("eventos_publicados_r7", True,
                     all(e >= cfg["supressao_min_celula"] for e in eventos)),
        verify.check("relatorio_baselines_gerado", True, caminho_md.exists()),
    ]

    total, por_nome = _runs_por_baseline(cfg)
    checks.append(verify.check("mlflow_runs_de_baseline", 3, total))
    for nome in baselines.NOMES:
        run = por_nome.get(nome)
        checks.append(verify.check(f"mlflow_{nome}_existe", True, run is not None))
        if run is None:
            continue
        metrica = METRICA_PRIMARIA[nome]
        esperado_run = resultados[nome]["oof"][metrica]
        lido = run.data.metrics.get(f"OOF/{metrica}", float("nan"))
        checks.append(verify.check(f"mlflow_{nome}_oof_{metrica}_relido", esperado_run, lido,
                                   tolerancia=TOLERANCIA_LEITURA))
        checks.append(verify.check(f"mlflow_{nome}_finalizado", True,
                                   run.info.status == "FINISHED"))
        checks.append(verify.check(f"mlflow_{nome}_run_id_gravado", True,
                                   run.info.run_id == ids[nome]))
    return checks


def executar(cfg: dict) -> Path:
    """Roda os três baselines, registra no MLflow, escreve o relatório e grava o T-2.8."""
    hash_dobras = hash_dobras_t23(cfg)
    df = carregar_features_com_dobras(cfg, hash_dobras)
    resultados = baselines.avaliar_dobras(cfg, df)
    del df
    ids = baselines.registrar_mlflow(cfg, resultados)
    caminho_md = baselines.escrever_relatorio(
        cfg, resultados, Path(cfg["caminhos"]["relatorios"]) / "baselines.md", hash_dobras)
    checks = _checks(cfg, resultados, ids, caminho_md)
    return verify.write_report("T-2.8", checks, Path(cfg["caminhos"]["relatorios"])
                               / "verificacao", cfg)
