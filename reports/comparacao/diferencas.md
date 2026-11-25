# Diferenças de PR-AUC contra o M1

Ano de comparação 2025 · avaliação única (R2) · só agregados (R7; células com menos de 10 suprimidas) · IC 95% por bootstrap pareado: 1000 reamostras, semente 20261103.

Diferença = PR-AUC do modelo − PR-AUC do `m1_main`, com as mesmas reamostras (pareada). Positiva: o modelo supera o M1. Leitura "melhor" se o IC 95% fica acima de 0; "pior" se fica abaixo; "sem diferença detectável" se o IC inclui 0 (SC-09).

## População principal

| Modelo | Diferença | IC 95% | Leitura |
|---|---|---|---|
| m1_main | referência | — | — |
| e1_main | -0,0152 | (-0,0187; -0,0124) | pior |
| b1_main | -0,0194 | (-0,0233; -0,0161) | pior |
| b0_main | -0,0334 | (-0,0381; -0,0295) | pior |
| b2_regra | -0,0309 | (-0,0356; -0,0271) | pior |
| m1_soneca | -0,0029 | (-0,0047; -0,0016) | pior |
| m1_lora | -0,0061 | (-0,0086; -0,0042) | pior |

## População completa

| Modelo | Diferença | IC 95% | Leitura |
|---|---|---|---|
| m1_main | referência | — | — |
| e1_main | não estima | — | — |
| b1_main | -0,0202 | (-0,0239; -0,0169) | pior |
| b0_main | -0,0333 | (-0,0380; -0,0295) | pior |
| b2_regra | -0,0309 | (-0,0355; -0,0272) | pior |
| m1_soneca | -0,0029 | (-0,0047; -0,0016) | pior |
| m1_lora | -0,0061 | (-0,0084; -0,0040) | pior |
