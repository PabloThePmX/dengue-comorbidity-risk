# Modelo explicativo E1: coeficientes (T-3.1)

> **Modelo explicativo: associação, não causa (P6).** Os coeficientes são associações ajustadas por idade e sexo, não efeitos causais. Descrevem o modelo, não o mundo.

Ajuste em 2022–23 (dados de desenvolvimento, sem dobras). Logística sem penalização (R9). Coeficientes na escala do logit; erro-padrão e IC 95% pelo método de Wald.

- Casos: 2 453 208 · eventos: 3 985 · padrões agrupados: 9 316 · parâmetros: 44
- Convergiu: sim · log-verossimilhança: -26755,25
- Tempo de ajuste: 1,2 s
- Equivalência agrupado x linha a linha: em 200 000 linhas aleatórias (semente 20261103) e no ponto ajustado, a maior diferença relativa de log-verossimilhança, escore e informação é 5,1e-15; passou (tolerância 1e-08)

## Coeficientes

Termos com menos de 10 eventos no nível aparecem como suprimidos (R7), inclusive "Ausente" (nível próprio de cada comorbidade). O intercepto e a base da idade (spline) não têm interpretação direta; a curva da idade sai na tabela de perfis. "DIABETES: Sim" e "HIPERTENSA: Sim" são o log-OR aos 40 anos (IDADE_REFERENCIA), com as demais comorbidades em Não, sexo F e não gestante. O OR varia com a idade (há interação com a idade): a leitura por faixa etária é da T-3.2.

Escolhas registradas: base natural própria para a idade (nós nos quantis das linhas; `patsy.cr` teria constante colineal com o intercepto). Supressão de 8 coeficientes com menos de 10 eventos no nível (Sexo: I e os "Ausente" das 7 comorbidades) confirmada pelo Programador.

| Termo | Coeficiente (logit) | Erro-padrão | IC 95% inferior | IC 95% superior |
|---|---|---|---|---|
| Intercepto | -6,1721 | 0,0862 | -6,3410 | -6,0032 |
| Idade (spline) 1 | -0,0952 | 0,0107 | -0,1161 | -0,0742 |
| Idade (spline) 2 | 0,0097 | 0,0019 | 0,0060 | 0,0134 |
| Idade (spline) 3 | -0,0239 | 0,0075 | -0,0386 | -0,0092 |
| Idade (spline) 4 | 0,0152 | 0,0091 | -0,0026 | 0,0330 |
| Idade (spline) 5 | 0,0019 | 0,0046 | -0,0072 | 0,0109 |
| Sexo: M (ref. F) | 0,2168 | 0,0322 | 0,1536 | 0,2800 |
| Sexo: I (ref. F) | suprimido (R7) | suprimido (R7) | suprimido (R7) | suprimido (R7) |
| Gestante: Sim | 0,7019 | 0,1679 | 0,3729 | 1,0310 |
| DIABETES: Ausente | suprimido (R7) | suprimido (R7) | suprimido (R7) | suprimido (R7) |
| DIABETES: Sim | 1,0928 | 0,1319 | 0,8342 | 1,3514 |
| HEMATOLOG: Ausente | suprimido (R7) | suprimido (R7) | suprimido (R7) | suprimido (R7) |
| HEMATOLOG: Sim | 2,2326 | 0,1267 | 1,9844 | 2,4809 |
| HEPATOPAT: Ausente | suprimido (R7) | suprimido (R7) | suprimido (R7) | suprimido (R7) |
| HEPATOPAT: Sim | 1,5873 | 0,1592 | 1,2752 | 1,8994 |
| RENAL: Ausente | suprimido (R7) | suprimido (R7) | suprimido (R7) | suprimido (R7) |
| RENAL: Sim | 1,9168 | 0,1500 | 1,6228 | 2,2107 |
| HIPERTENSA: Ausente | suprimido (R7) | suprimido (R7) | suprimido (R7) | suprimido (R7) |
| HIPERTENSA: Sim | 0,9836 | 0,0914 | 0,8045 | 1,1628 |
| ACIDO_PEPT: Ausente | suprimido (R7) | suprimido (R7) | suprimido (R7) | suprimido (R7) |
| ACIDO_PEPT: Sim | -0,3514 | 0,2609 | -0,8628 | 0,1599 |
| AUTO_IMUNE: Ausente | suprimido (R7) | suprimido (R7) | suprimido (R7) | suprimido (R7) |
| AUTO_IMUNE: Sim | 1,6141 | 0,1453 | 1,3293 | 1,8990 |
| DIABETES x HEMATOLOG | -0,7274 | 0,2549 | -1,2269 | -0,2279 |
| DIABETES x HEPATOPAT | -0,4999 | 0,2349 | -0,9602 | -0,0396 |
| DIABETES x RENAL | -0,0653 | 0,1621 | -0,3829 | 0,2523 |
| DIABETES x HIPERTENSA | -0,3747 | 0,1102 | -0,5906 | -0,1588 |
| DIABETES x AUTO_IMUNE | -1,0685 | 0,3117 | -1,6794 | -0,4576 |
| HEMATOLOG x HEPATOPAT | -1,7142 | 0,3582 | -2,4163 | -1,0121 |
| HEMATOLOG x RENAL | -2,0829 | 0,3736 | -2,8152 | -1,3507 |
| HEMATOLOG x HIPERTENSA | -0,9397 | 0,2154 | -1,3619 | -0,5175 |
| HEMATOLOG x AUTO_IMUNE | -0,4099 | 0,3308 | -1,0583 | 0,2384 |
| HEPATOPAT x RENAL | -0,9118 | 0,3172 | -1,5334 | -0,2901 |
| HEPATOPAT x HIPERTENSA | -0,2120 | 0,2162 | -0,6358 | 0,2119 |
| RENAL x HIPERTENSA | -0,1846 | 0,1738 | -0,5252 | 0,1559 |
| RENAL x AUTO_IMUNE | 0,0806 | 0,3107 | -0,5284 | 0,6895 |
| HIPERTENSA x ACIDO_PEPT | -0,1386 | 0,3792 | -0,8818 | 0,6047 |
| HIPERTENSA x AUTO_IMUNE | -1,0918 | 0,2384 | -1,5591 | -0,6245 |
| HIPERTENSA x Idade (spline) 1 | 0,0857 | 0,0411 | 0,0051 | 0,1664 |
| HIPERTENSA x Idade (spline) 2 | -0,0034 | 0,0018 | -0,0069 | 0,0002 |
| HIPERTENSA x Idade (spline) 3 | 0,0062 | 0,0035 | -0,0006 | 0,0131 |
| DIABETES x Idade (spline) 1 | 0,0550 | 0,0434 | -0,0300 | 0,1401 |
| DIABETES x Idade (spline) 2 | -0,0020 | 0,0020 | -0,0059 | 0,0019 |
| DIABETES x Idade (spline) 3 | 0,0032 | 0,0039 | -0,0044 | 0,0109 |

## Interações 2 a 2 entre comorbidades

Entram no E1 os pares com pelo menos 10 eventos. Os demais aparecem como "eventos insuficientes", sem contagem.

| Par | Situação |
|---|---|
| DIABETES + HEMATOLOG | incluído no E1 |
| DIABETES + HEPATOPAT | incluído no E1 |
| DIABETES + RENAL | incluído no E1 |
| DIABETES + HIPERTENSA | incluído no E1 |
| DIABETES + AUTO_IMUNE | incluído no E1 |
| HEMATOLOG + HEPATOPAT | incluído no E1 |
| HEMATOLOG + RENAL | incluído no E1 |
| HEMATOLOG + HIPERTENSA | incluído no E1 |
| HEMATOLOG + AUTO_IMUNE | incluído no E1 |
| HEPATOPAT + RENAL | incluído no E1 |
| HEPATOPAT + HIPERTENSA | incluído no E1 |
| RENAL + HIPERTENSA | incluído no E1 |
| RENAL + AUTO_IMUNE | incluído no E1 |
| HIPERTENSA + ACIDO_PEPT | incluído no E1 |
| HIPERTENSA + AUTO_IMUNE | incluído no E1 |
| DIABETES + ACIDO_PEPT | eventos insuficientes |
| HEMATOLOG + ACIDO_PEPT | eventos insuficientes |
| HEPATOPAT + ACIDO_PEPT | eventos insuficientes |
| HEPATOPAT + AUTO_IMUNE | eventos insuficientes |
| RENAL + ACIDO_PEPT | eventos insuficientes |
| ACIDO_PEPT + AUTO_IMUNE | eventos insuficientes |
