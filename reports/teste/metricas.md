# Avaliação Final Única no Conjunto de Teste (2024) (T-5.1, T-5.4)

- **Diferença PR-AUC (M1 − B1):** `0.0119` (IC 95%: `[0.0095, 0.0158]`)
- **Diferença PR-AUC (M1 − B0):** `0.0263` (IC 95%: `[0.0239, 0.0317]`)

## Métricas principais

| modelo | pr_auc | pr_auc_ic95_inf | pr_auc_ic95_sup | roc_auc | brier | slope | intercept | limiar | recall | precisao | f2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| M1 (Triagem) | 0.0295 | 0.0277 | 0.0316 | 0.8132 | 0.0021 | 0.9378 | 0.2506 | 0.0230 | 0.2056 | 0.0468 | 0.1225 |
| E1 (Perfil explicativo) | 0.0221 | 0.0207 | 0.0238 | 0.7282 | 0.0021 | 0.9576 | 0.1702 | - | - | - | - |
| B1 (Baseline perfil) | 0.0191 | 0.0179 | 0.0204 | 0.7186 | 0.0021 | 0.9590 | 0.1717 | 0.0191 | 0.1522 | 0.0380 | 0.0950 |
| B0 (Prevalência) | 0.0021 | 0.0021 | 0.0021 | 0.5000 | 0.0021 | 0.0000 | 0.0000 | - | - | - | - |
| B2 (Protocolo MS) | - | - | - | - | - | - | - | regra | 0.6601 | 0.0053 | 0.0256 |

## Critérios de sucesso (SC-01 a SC-04 — T-5.4)

| criterio | valor_obtido | status |
|---|---|---|
| SC-01 (M1 supera B0 em PR-AUC; IC da diferença > 0) | diff=0.0263 [0.0239, 0.0317] | passou |
| SC-02 (Comparação M1 vs B1 em PR-AUC; desejável > 0) | diff=0.0119 [0.0095, 0.0158] | passou |
| SC-03 (Recall M1 >= Recall B2 com maior precisão no limiar) | recall M1=0.2056 vs B2=0.6601; prec M1=0.0468 vs B2=0.0053 | falhou |
| SC-04 (Calibration slope de M1 no teste entre 0,8 e 1,2) | slope=0.9378 | passou |
