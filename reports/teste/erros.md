# Análise de Erros no Conjunto de Teste (2024) (T-5.3, R7)

> **Apenas agregados (R7); células `< 10` suprimidas (`<10`).**

## Perfil dos até 100 falsos negativos de maior risco previsto

| dimensao | categoria | casos |
|---|---|---|
| Faixa etária | 60–79 | 55 |
| Faixa etária | 80+ | 31 |
| Faixa etária | 40–59 | <10 |
| Faixa etária | 15–39 | <10 |
| Faixa etária | 5–14 | <10 |
| Região | Sudeste | 59 |
| Região | Centro-Oeste | 20 |
| Região | Sul | 19 |
| Região | Nordeste | <10 |
| Nº comorbidades | 1 | 48 |
| Nº comorbidades | 2 | 36 |
| Nº comorbidades | 0 | 13 |
| Nº comorbidades | 3 | <10 |
| Nº comorbidades | 4 | <10 |

## Calibração por comorbidade

| comorbidade | casos | eventos | obs_pct | pred_pct | erro_abs_pct |
|---|---|---|---|---|---|
| RENAL | 27 077 | 625 | 2.308 | 1.652 | 0.656 |
| HEMATOLOG | 28 894 | 355 | 1.229 | 0.891 | 0.337 |
| AUTO_IMUNE | 37 794 | 350 | 0.926 | 0.645 | 0.281 |
| DIABETES | 234 904 | 2 261 | 0.963 | 0.802 | 0.161 |
| HEPATOPAT | 28 314 | 258 | 0.911 | 0.769 | 0.143 |
| HIPERTENSA | 544 193 | 4 215 | 0.775 | 0.656 | 0.119 |
| ACIDO_PEPT | 28 442 | 90 | 0.316 | 0.276 | 0.040 |

## Recorte Espírito Santo (ES) vs demais UFs (§3.7)

| recorte | casos | eventos | pr_auc | brier |
|---|---|---|---|---|
| Espírito Santo (ES) | 117 062 | 122 | 0.0155 | 0.0010 |
| Demais UFs | 5 214 683 | 11 216 | 0.0297 | 0.0021 |
