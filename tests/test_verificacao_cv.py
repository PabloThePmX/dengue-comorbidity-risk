"""Testes da lógica de verificação da T-4.2 (`verificacao_cv._checks`) com dados sintéticos."""

import numpy as np
from test_cv import ORDEM, cfg_teste, frame_sintetico

from dengue_sinan import cv, folds, verificacao_cv


def _df_com_papeis(cfg: dict):
    """Frame sintético com papel_<região> no formato da T-2.3 (ajuste/parada/validacao)."""
    df = frame_sintetico()
    y = df["y"].to_numpy()
    for regiao in ORDEM:
        papel = np.full(len(df), "validacao", dtype=object)
        treino = np.flatnonzero(df["regiao"].to_numpy() != regiao)
        pos_ajuste, pos_parada = folds.inner_split(treino, y, cfg["validacao_interna_frac"],
                                                   cfg["seed"])
        papel[pos_ajuste] = "ajuste"
        papel[pos_parada] = "parada"
        df[f"papel_{regiao}"] = papel
    return df


def _esperado_a_partir_do_resultado(resultado: dict, n: int) -> dict:
    """Esperado calculado do próprio resultado: o teste confere a montagem dos checks."""
    oof = resultado["oof"]
    return {
        "desenvolvimento": {"populacao_total": n, "eventos_total": int(oof["y"].sum())},
        "cv": {"b1": {
            "pr_auc_oof": resultado["oof_pr_auc"],
            "tolerancia_oof": 1e-12,
            "pr_auc_por_dobra": dict(resultado["pr_auc_por_dobra"]),
            "tolerancia_dobra": 1e-12,
        }},
    }


def test_checks_passam_quando_os_numeros_batem():
    cfg = cfg_teste()
    df = _df_com_papeis(cfg)
    resultado = cv.run_loro(cfg, "b1", {}, df)
    esperado = _esperado_a_partir_do_resultado(resultado, len(df))
    checks = verificacao_cv._checks(cfg, resultado, df, esperado["desenvolvimento"],
                                    esperado["cv"]["b1"], anos=[2022])
    assert all(c["passou"] for c in checks), [c["nome"] for c in checks if not c["passou"]]


def test_checks_reprovam_pr_auc_diferente():
    cfg = cfg_teste()
    df = _df_com_papeis(cfg)
    resultado = cv.run_loro(cfg, "b1", {}, df)
    esperado = _esperado_a_partir_do_resultado(resultado, len(df))
    esperado["cv"]["b1"]["pr_auc_oof"] += 0.01
    checks = verificacao_cv._checks(cfg, resultado, df, esperado["desenvolvimento"],
                                    esperado["cv"]["b1"], anos=[2022])
    reprovados = [c["nome"] for c in checks if not c["passou"]]
    assert reprovados == ["pr_auc_oof_b1"]


def test_checks_reprovam_validacao_interna_diferente_da_t23():
    cfg = cfg_teste()
    df = _df_com_papeis(cfg)
    # Troca um caso de "parada" por "ajuste" em uma dobra: a T-2.3 deixa de bater.
    alvo = df.index[(df["papel_A"] == "parada")][0]
    df.loc[alvo, "papel_A"] = "ajuste"
    resultado = cv.run_loro(cfg, "b1", {}, df)
    esperado = _esperado_a_partir_do_resultado(resultado, len(df))
    checks = verificacao_cv._checks(cfg, resultado, df, esperado["desenvolvimento"],
                                    esperado["cv"]["b1"], anos=[2022])
    por_nome = {c["nome"]: c for c in checks}
    assert por_nome["validacao_interna_igual_t23"]["passou"] is False
