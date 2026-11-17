"""Verificação da T-4.2 (Marco 4, no PC local, D-66): grava reports/verificacao/T-4.2.json.

Roda o laço `cv.run_loro` com o modelo "b1" nas dobras da T-2.3 (mesmo carregamento da T-2.8)
e confere com `config/esperado.yaml`:
- uma predição por caso de 2022–23 (o número de casos vem de `desenvolvimento`);
- PR-AUC do OOF e de cada dobra iguais às de `reports/baselines.md` (seção `cv`);
- a validação interna de `folds.inner_split` (usada pelo laço) reproduz a da T-2.3, caso a caso;
- nenhum ano fora de `anos_dev` e B1 sem melhor ponto (sem early stopping).
Só agregados (R7): nenhuma linha individual sai daqui.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from dengue_sinan import cv, folds, verify
from dengue_sinan.verificacao_baselines import carregar_features_com_dobras, hash_dobras_t23

ESPERADO_PADRAO = Path(__file__).resolve().parents[2] / "config" / "esperado.yaml"
MODELO = "b1"


def _checks(cfg: dict, resultado: dict, df: pd.DataFrame, dev: dict, cv_b1: dict,
            anos: list[int]) -> list[dict]:
    """Checks da T-4.2 a partir de um resultado de `cv.run_loro` (função pura, testável)."""
    oof = resultado["oof"]
    posicoes = resultado["posicoes"]
    checks = [
        verify.check("oof_uma_predicao_por_caso", dev["populacao_total"], len(oof)),
        verify.check("posicoes_sem_repeticao", True,
                     not pd.Series(posicoes).duplicated().any()),
        verify.check("oof_eventos_totais", dev["eventos_total"], int(oof["y"].sum())),
        verify.check("oof_so_anos_de_desenvolvimento", True,
                     set(np.unique(oof["ANO"]).tolist()) == set(anos)),
        verify.check("pr_auc_oof_b1", cv_b1["pr_auc_oof"], resultado["oof_pr_auc"],
                     tolerancia=cv_b1["tolerancia_oof"]),
    ]
    for regiao, esperado in cv_b1["pr_auc_por_dobra"].items():
        checks.append(verify.check(f"pr_auc_{regiao}_b1", esperado,
                                   resultado["pr_auc_por_dobra"][regiao],
                                   tolerancia=cv_b1["tolerancia_dobra"]))
    checks.append(verify.check("b1_sem_melhor_ponto", True,
                               all(v is None for v in resultado["melhores_pontos"].values())))

    # R6 e T-2.3: a validação interna do laço é a mesma gravada no arquivo de dobras.
    reproduz = True
    for regiao in cfg["ordem_dobras"]:
        papel = df[f"papel_{regiao}"].to_numpy()
        _, pos_parada = folds.inner_split(
            np.flatnonzero(df["regiao"].astype(str).to_numpy() != regiao),
            df["y"].to_numpy(), cfg["validacao_interna_frac"], cfg["seed"])
        reproduz &= np.array_equal(np.flatnonzero(papel == "parada"), pos_parada)
    checks.append(verify.check("validacao_interna_igual_t23", True, bool(reproduz)))
    return checks


def executar(cfg: dict, esperado_path: Path = ESPERADO_PADRAO) -> Path:
    """Carrega o desenvolvimento com as dobras da T-2.3, roda o B1 pelo laço e grava T-4.2."""
    esperado = yaml.safe_load(Path(esperado_path).read_text(encoding="utf-8"))
    dev = esperado["desenvolvimento"]
    cv_b1 = esperado["cv"][MODELO]
    anos = list(cfg["anos_dev"])

    df = carregar_features_com_dobras(cfg, hash_dobras_t23(cfg))
    resultado = cv.run_loro(cfg, MODELO, {}, df)
    checks = _checks(cfg, resultado, df, dev, cv_b1, anos)
    del df, resultado
    return verify.write_report("T-4.2", checks, Path(cfg["caminhos"]["relatorios"])
                               / "verificacao", cfg)
