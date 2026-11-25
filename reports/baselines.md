# Baselines B0, B1 e B2 (FR-04)

Desenvolvimento 2022–23, com as dobras leave-one-region-out da T-2.3 (hash do conteúdo `09e29252e4ed3b44…`, semente 20261103). O ano de teste não foi lido (R1). Cada dobra mede a região deixada de fora; o OOF agrupado junta as cinco predições, uma por caso.

## B0 — prevalência do treino

| Dobra (validação) | Eventos | PR-AUC | ROC-AUC | Brier | Slope | Intercept |
|---|---:|---:|---:|---:|---:|---:|
| Sudeste | 1 736 | 0,00149 | 0,5000 | 0,00149 | — | -0,154 |
| Sul | 810 | 0,00139 | 0,5000 | 0,00139 | — | -0,197 |
| Centro-Oeste | 736 | 0,00180 | 0,5000 | 0,00180 | — | 0,125 |
| Nordeste | 582 | 0,00255 | 0,5000 | 0,00255 | — | 0,513 |
| Norte | 121 | 0,00166 | 0,5000 | 0,00166 | — | 0,025 |
| **OOF agrupado** | 3 985 | 0,00151 | 0,4629 | 0,00162 | -3,564 | -0,035 |

## B1 — logística sem penalização

Spline da idade (5 nós), sexo, gestante e as 7 comorbidades. Sem `n_comorbidades` (D-62) e sem pesos de classe (R3).

| Dobra (validação) | Eventos | PR-AUC | ROC-AUC | Brier | Slope | Intercept |
|---|---:|---:|---:|---:|---:|---:|
| Sudeste | 1 736 | 0,01345 | 0,7547 | 0,00148 | 1,182 | -0,203 |
| Sul | 810 | 0,01763 | 0,7779 | 0,00138 | 1,236 | -0,324 |
| Centro-Oeste | 736 | 0,01554 | 0,7031 | 0,00179 | 1,027 | 0,239 |
| Nordeste | 582 | 0,00724 | 0,6393 | 0,00254 | 0,644 | 0,724 |
| Norte | 121 | 0,01026 | 0,6916 | 0,00166 | 1,123 | 0,264 |
| **OOF agrupado** | 3 985 | 0,01284 | 0,7109 | 0,00161 | 1,048 | -0,053 |

## B2 — regra do protocolo

**B2 é uma regra, não um modelo:** não treina e é binária, então a PR-AUC dela é um ponto único (recall e precisão); por isso a tabela traz só recall, precisão e F2 no limiar da própria regra.

| Dobra (validação) | Eventos | Recall | Precisão | F2 |
|---|---:|---:|---:|---:|
| Sudeste | 1 736 | 0,7160 | 0,0040 | 0,0198 |
| Sul | 810 | 0,7457 | 0,0035 | 0,0169 |
| Centro-Oeste | 736 | 0,6454 | 0,0053 | 0,0258 |
| Nordeste | 582 | 0,5550 | 0,0055 | 0,0266 |
| Norte | 121 | 0,6777 | 0,0051 | 0,0248 |
| **OOF agrupado** | 3 985 | 0,6843 | 0,0042 | 0,0206 |

## Notas

- Slope de B0 é indefinido (predição constante em cada dobra): aparece como —.
- Eventos abaixo de 10 são publicados como <10 (R7).
- Os números são agregados. Nenhuma linha individual sai deste relatório (R7).
