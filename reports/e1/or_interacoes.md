# Modelo explicativo E1: OR e interações 2 a 2 (T-3.2)

> **Modelo explicativo: associação, não causa (P6).** Os coeficientes são associações ajustadas por idade e sexo, não efeitos causais. Descrevem o modelo, não o mundo.

**Padrão suspeito "todas as 7 comorbidades = Sim".** 2.000 casos (0,08% da população de 2022–23) têm as 7 comorbidades = Sim, com risco parecido com o geral. Esse padrão influencia parte dos resultados. A sensibilidade oficial, sem esses casos, está em [sensibilidade_padrao_todas_sim.md](sensibilidade_padrao_todas_sim.md). Os pares HEMATOLOG × HEPATOPAT e HEMATOLOG × RENAL só têm 10 ou mais eventos por causa do padrão; sem ele, saem do E1. Sem o padrão, o ranking muda nas posições 2 e 3: passa a ser AUTO_IMUNE e RENAL (no principal, RENAL e AUTO_IMUNE).

Ajuste do E1 em 2022–23 (dados de desenvolvimento, sem dobras). Logística sem penalização (R9). IC 95% pelo método de Wald, com a covariância do ajuste. P-valor de Wald; o p ajustado usa Benjamini-Hochberg (FDR 5%) sobre os pares incluídos (FR-05, D-40).

Leitura: o que orienta é o tamanho do efeito e o IC. O p ajustado só diz se o par passa na correção de múltiplas comparações.

## Efeitos principais: OR de cada comorbidade contra Não

Comorbidade isolada: as demais em Não, sexo F, não gestante. DIABETES e HIPERTENSA aos 40 anos (o OR delas varia com a idade; ver a tabela por faixa abaixo).

| Comorbidade | OR | IC 95% |
|---|---|---|
| DIABETES | 2,98 | [2,30; 3,86] |
| HEMATOLOG | 9,32 | [7,27; 11,95] |
| HEPATOPAT | 4,89 | [3,58; 6,68] |
| RENAL | 6,80 | [5,07; 9,12] |
| HIPERTENSA | 2,67 | [2,24; 3,20] |
| ACIDO_PEPT | 0,70 | [0,42; 1,17] |
| AUTO_IMUNE | 5,02 | [3,78; 6,68] |

## Interações 2 a 2 (pares com pelo menos 10 eventos)

OR da interação = exp(coeficiente do produto), na escala multiplicativa. OR de 1 quer dizer que o OR de uma comorbidade não muda na presença da outra. A escala aditiva está em [reri_ap.md](reri_ap.md).

| Par | OR da interação | IC 95% | p (Wald) | p ajustado (BH) |
|---|---|---|---|---|
| DIABETES × HEMATOLOG | 0,48 | [0,29; 0,80] | 0,004 | 0,008 |
| DIABETES × HEPATOPAT | 0,61 | [0,38; 0,96] | 0,033 | 0,056 |
| DIABETES × RENAL | 0,94 | [0,68; 1,29] | 0,687 | 0,766 |
| DIABETES × HIPERTENSA | 0,69 | [0,55; 0,85] | < 0,001 | 0,002 |
| DIABETES × AUTO_IMUNE | 0,34 | [0,19; 0,63] | < 0,001 | 0,002 |
| HEMATOLOG × HEPATOPAT | 0,18 | [0,09; 0,36] | < 0,001 | < 0,001 |
| HEMATOLOG × RENAL | 0,12 | [0,06; 0,26] | < 0,001 | < 0,001 |
| HEMATOLOG × HIPERTENSA | 0,39 | [0,26; 0,60] | < 0,001 | < 0,001 |
| HEMATOLOG × AUTO_IMUNE | 0,66 | [0,35; 1,27] | 0,215 | 0,323 |
| HEPATOPAT × RENAL | 0,40 | [0,22; 0,75] | 0,004 | 0,008 |
| HEPATOPAT × HIPERTENSA | 0,81 | [0,53; 1,24] | 0,327 | 0,409 |
| RENAL × HIPERTENSA | 0,83 | [0,59; 1,17] | 0,288 | 0,393 |
| RENAL × AUTO_IMUNE | 1,08 | [0,59; 1,99] | 0,795 | 0,795 |
| HIPERTENSA × ACIDO_PEPT | 0,87 | [0,41; 1,83] | 0,715 | 0,766 |
| HIPERTENSA × AUTO_IMUNE | 0,34 | [0,21; 0,54] | < 0,001 | < 0,001 |

6 pares têm eventos insuficientes (menos de 10) e não entram no E1 nem nesta tabela. Aparecem sem contagem em [coeficientes.md](coeficientes.md) (R7).

## OR de DIABETES e HIPERTENSA por faixa etária

Idade usada: o meio de cada faixa; na faixa aberta 80+, 80 (limite inferior). As demais comorbidades em Não, sexo F, não gestante. Quanto mais largo o IC, menos preciso o OR naquela idade.

| Faixa | Idade usada | DIABETES: OR | DIABETES: IC 95% | HIPERTENSA: OR | HIPERTENSA: IC 95% |
|---|---|---|---|---|---|
| 0–4 | 2,5 | 0,95 | [0,23; 3,93] | 0,50 | [0,12; 2,07] |
| 5–14 | 10,0 | 1,41 | [0,59; 3,38] | 0,92 | [0,38; 2,23] |
| 15–39 | 27,5 | 2,67 | [1,81; 3,95] | 2,38 | [1,77; 3,19] |
| 40–59 | 50,0 | 2,95 | [2,42; 3,60] | 2,68 | [2,37; 3,04] |
| 60–79 | 70,0 | 2,57 | [2,10; 3,16] | 2,80 | [2,49; 3,14] |
| 80+ | 80,0 | 2,30 | [1,85; 2,85] | 2,90 | [2,58; 3,26] |

Abaixo de 20 anos, a amplitude do IC de DIABETES vai de 2,79 a 3,70 e a de HIPERTENSA vai de 1,84 a 1,95 (escala do OR); nas faixas de 20 anos ou mais, vai de 1,00 a 2,15 e de 0,64 a 1,42. Nos dois efeitos, os IC abaixo de 20 anos são mais largos do que os de qualquer faixa de 20 anos ou mais.

O OR de DIABETES é máximo na faixa 40–59 (2,95) e cai em todas as faixas seguintes, até 2,30 em 80+.

O OR de HIPERTENSA não cai com a idade a partir da faixa 15–39: vai de 2,38 a 2,90 em 80+.

