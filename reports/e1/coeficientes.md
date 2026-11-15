# E1 — Coeficientes da regressão logística sem penalização (T-3.1)

- Convergiu: `True`
- Tempo de ajuste (s): `31.08`
- Pares incluídos (≥ 10 eventos): `15`

| termo | coeficiente_logit | erro_padrao |
|---|---|---|
| Intercept | -2.1700 | 1.0344 |
| idade_sp5_0 | -3.2597 | 1.0308 |
| idade_sp5_1 | -5.3874 | 1.0468 |
| idade_sp5_2 | -5.0925 | 1.0215 |
| idade_sp5_3 | -1.1936 | 1.0862 |
| sexo_M | 0.2105 | 0.0322 |
| sexo_I | 0.3821 | 0.4521 |
| gestante | 0.6874 | 0.1675 |
| DIABETES_Sim | 0.1968 | 0.2696 |
| HEMATOLOG_Sim | 2.2251 | 0.1265 |
| HEPATOPAT_Sim | 1.5924 | 0.1587 |
| RENAL_Sim | 1.9107 | 0.1498 |
| HIPERTENSA_Sim | 1.2397 | 0.2088 |
| ACIDO_PEPT_Sim | -0.3570 | 0.2603 |
| AUTO_IMUNE_Sim | 1.6231 | 0.1450 |
| DIABETES_Sim:HEMATOLOG_Sim | -0.7235 | 0.2546 |
| DIABETES_Sim:HEPATOPAT_Sim | -0.5018 | 0.2342 |
| DIABETES_Sim:RENAL_Sim | -0.0611 | 0.1618 |
| DIABETES_Sim:HIPERTENSA_Sim | -0.3549 | 0.1095 |
| DIABETES_Sim:AUTO_IMUNE_Sim | -1.0629 | 0.3101 |
| HEMATOLOG_Sim:HEPATOPAT_Sim | -1.7221 | 0.3576 |
| HEMATOLOG_Sim:RENAL_Sim | -2.0701 | 0.3724 |
| HEMATOLOG_Sim:HIPERTENSA_Sim | -0.9572 | 0.2148 |
| HEMATOLOG_Sim:AUTO_IMUNE_Sim | -0.4262 | 0.3308 |
| HEPATOPAT_Sim:RENAL_Sim | -0.9108 | 0.3170 |
| HEPATOPAT_Sim:HIPERTENSA_Sim | -0.2369 | 0.2153 |
| RENAL_Sim:HIPERTENSA_Sim | -0.2010 | 0.1733 |
| RENAL_Sim:AUTO_IMUNE_Sim | 0.0718 | 0.3107 |
| HIPERTENSA_Sim:ACIDO_PEPT_Sim | -0.1700 | 0.3787 |
| HIPERTENSA_Sim:AUTO_IMUNE_Sim | -1.0999 | 0.2374 |
| HIPERTENSA_Sim:idade_sp3_0 | -0.2789 | 0.2714 |
| HIPERTENSA_Sim:idade_sp3_1 | -0.3001 | 0.2562 |
| DIABETES_Sim:idade_sp3_0 | 0.5831 | 0.3459 |
| DIABETES_Sim:idade_sp3_1 | 0.8770 | 0.3043 |
