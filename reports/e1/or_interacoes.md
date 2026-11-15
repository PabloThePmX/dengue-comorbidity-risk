# E1 — Odds Ratios (efeitos principais e interações 2 a 2 com FDR 5%) (T-3.2)

## Efeitos principais das 7 comorbidades

| comorbidade | beta | se | OR | IC95_inf | IC95_sup |
|---|---|---|---|---|---|
| DIABETES | 0.1968 | 0.2696 | 1.2175 | 0.7178 | 2.0651 |
| HEMATOLOG | 2.2251 | 0.1265 | 9.2542 | 7.2216 | 11.8587 |
| HEPATOPAT | 1.5924 | 0.1587 | 4.9157 | 3.6014 | 6.7095 |
| RENAL | 1.9107 | 0.1498 | 6.7580 | 5.0381 | 9.0650 |
| HIPERTENSA | 1.2397 | 0.2088 | 3.4545 | 2.2941 | 5.2018 |
| ACIDO_PEPT | -0.3570 | 0.2603 | 0.6998 | 0.4202 | 1.1655 |
| AUTO_IMUNE | 1.6231 | 0.1450 | 5.0686 | 3.8148 | 6.7346 |

## Interações 2 a 2 (Benjamini-Hochberg FDR 5%)

| par | status | OR_interacao | IC95_inf | IC95_sup | p_valor | p_ajustado_bh | significativo_fdr_5pct |
|---|---|---|---|---|---|---|---|
| DIABETES + HEMATOLOG | incluído | 0.4851 | 0.2945 | 0.7989 | 0.0045 | 0.0084 | 1 |
| DIABETES + HEPATOPAT | incluído | 0.6055 | 0.3826 | 0.9581 | 0.0321 | 0.0536 | 0 |
| DIABETES + RENAL | incluído | 0.9407 | 0.6851 | 1.2917 | 0.7055 | 0.7559 | 0 |
| DIABETES + HIPERTENSA | incluído | 0.7012 | 0.5658 | 0.8690 | 0.0012 | 0.0030 | 1 |
| DIABETES + ACIDO_PEPT | eventos insuficientes |  |  |  |  |  | 0 |
| DIABETES + AUTO_IMUNE | incluído | 0.3455 | 0.1881 | 0.6344 | 0.0006 | 0.0018 | 1 |
| HEMATOLOG + HEPATOPAT | incluído | 0.1787 | 0.0886 | 0.3602 | 0.0000 | 0.0000 | 1 |
| HEMATOLOG + RENAL | incluído | 0.1262 | 0.0608 | 0.2618 | 0.0000 | 0.0000 | 1 |
| HEMATOLOG + HIPERTENSA | incluído | 0.3840 | 0.2520 | 0.5850 | 0.0000 | 0.0000 | 1 |
| HEMATOLOG + ACIDO_PEPT | eventos insuficientes |  |  |  |  |  | 0 |
| HEMATOLOG + AUTO_IMUNE | incluído | 0.6530 | 0.3415 | 1.2488 | 0.1976 | 0.2964 | 0 |
| HEPATOPAT + RENAL | incluído | 0.4022 | 0.2161 | 0.7487 | 0.0041 | 0.0084 | 1 |
| HEPATOPAT + HIPERTENSA | incluído | 0.7891 | 0.5174 | 1.2035 | 0.2714 | 0.3392 | 0 |
| HEPATOPAT + ACIDO_PEPT | eventos insuficientes |  |  |  |  |  | 0 |
| HEPATOPAT + AUTO_IMUNE | eventos insuficientes |  |  |  |  |  | 0 |
| RENAL + HIPERTENSA | incluído | 0.8179 | 0.5824 | 1.1488 | 0.2462 | 0.3357 | 0 |
| RENAL + ACIDO_PEPT | eventos insuficientes |  |  |  |  |  | 0 |
| RENAL + AUTO_IMUNE | incluído | 1.0745 | 0.5844 | 1.9754 | 0.8172 | 0.8172 | 0 |
| HIPERTENSA + ACIDO_PEPT | incluído | 0.8436 | 0.4016 | 1.7720 | 0.6534 | 0.7539 | 0 |
| HIPERTENSA + AUTO_IMUNE | incluído | 0.3329 | 0.2090 | 0.5302 | 0.0000 | 0.0000 | 1 |
| ACIDO_PEPT + AUTO_IMUNE | eventos insuficientes |  |  |  |  |  | 0 |
