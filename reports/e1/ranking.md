# Ranking de comorbidades (T-3.2, FR-19)

> **Modelo explicativo: associação, não causa (P6).** Os coeficientes são associações ajustadas por idade e sexo, não efeitos causais. Descrevem o modelo, não o mundo.

**Padrão suspeito "todas as 7 comorbidades = Sim".** 2.000 casos (0,08% da população de 2022–23) têm as 7 comorbidades = Sim, com risco parecido com o geral. Esse padrão influencia parte dos resultados. A sensibilidade oficial, sem esses casos, está em [sensibilidade_padrao_todas_sim.md](sensibilidade_padrao_todas_sim.md). Os pares HEMATOLOG × HEPATOPAT e HEMATOLOG × RENAL só têm 10 ou mais eventos por causa do padrão; sem ele, saem do E1. Sem o padrão, o ranking muda nas posições 2 e 3: passa a ser AUTO_IMUNE e RENAL (no principal, RENAL e AUTO_IMUNE).

Fonte: só os OR do E1 (R10), efeito principal de cada comorbidade contra Não, ajustado por idade e sexo. DIABETES e HIPERTENSA aos 40 anos: o OR delas muda com a idade (ver [or_interacoes.md](or_interacoes.md)), então o ranking vale para 40 anos. É associação ajustada, não causa.

Regra: duas comorbidades cujos IC 95% se sobrepõem ficam marcadas "sem ordem definida" entre si. Intervalos que só tocam na borda contam como sobrepostos.

A sobreposição não é transitiva: A pode se sobrepor a B, e B a C, sem que A e C se sobreponham. Por isso o ranking marca pares e não forma grupos fechados.

| Posição | Comorbidade | OR | IC 95% | Sem ordem definida com |
|---|---|---|---|---|
| 1 | HEMATOLOG | 9,32 | [7,27; 11,95] | RENAL |
| 2 | RENAL | 6,80 | [5,07; 9,12] | HEMATOLOG, AUTO_IMUNE, HEPATOPAT |
| 3 | AUTO_IMUNE | 5,02 | [3,78; 6,68] | RENAL, HEPATOPAT, DIABETES |
| 4 | HEPATOPAT | 4,89 | [3,58; 6,68] | RENAL, AUTO_IMUNE, DIABETES |
| 5 | DIABETES | 2,98 | [2,30; 3,86] | AUTO_IMUNE, HEPATOPAT, HIPERTENSA |
| 6 | HIPERTENSA | 2,67 | [2,24; 3,20] | DIABETES |
| 7 | ACIDO_PEPT | 0,70 | [0,42; 1,17] | — |

## Pares sem ordem definida

- HEMATOLOG e RENAL
- RENAL e AUTO_IMUNE
- RENAL e HEPATOPAT
- AUTO_IMUNE e HEPATOPAT
- AUTO_IMUNE e DIABETES
- HEPATOPAT e DIABETES
- DIABETES e HIPERTENSA

