# Interação aditiva: RERI e AP (T-3.2)

> **Modelo explicativo: associação, não causa (P6).** Os coeficientes são associações ajustadas por idade e sexo, não efeitos causais. Descrevem o modelo, não o mundo.

**Padrão suspeito "todas as 7 comorbidades = Sim".** 2.000 casos (0,08% da população de 2022–23) têm as 7 comorbidades = Sim, com risco parecido com o geral. Esse padrão influencia parte dos resultados. A sensibilidade oficial, sem esses casos, está em [sensibilidade_padrao_todas_sim.md](sensibilidade_padrao_todas_sim.md). Os pares HEMATOLOG × HEPATOPAT e HEMATOLOG × RENAL só têm 10 ou mais eventos por causa do padrão; sem ele, saem do E1. Sem o padrão, o ranking muda nas posições 2 e 3: passa a ser AUTO_IMUNE e RENAL (no principal, RENAL e AUTO_IMUNE).

Referência: idade 40, sexo F, não gestante, demais comorbidades em Não. OR_A, OR_B e OR_AB são contra "nenhuma das duas".

- RERI = OR_AB − OR_A − OR_B + 1 (excesso de risco relativo devido à interação). RERI > 0: supra-aditivo; RERI < 0: sub-aditivo; RERI = 0: aditivo.
- AP = RERI / OR_AB (proporção do risco com as duas comorbidades atribuível à interação).
- IC 95% oficial: método delta, com a covariância dos coeficientes (D-40). Os IC do delta são simétricos em torno do ponto estimado.
- Sensibilidade: 10.000 sorteios da normal multivariada dos coeficientes (semente 20261103); os quantis 2,5% e 97,5% dão IC por simulação. Não é bootstrap dos dados. A simulação não substitui o delta: mostra a assimetria do RERI, que é função exponencial dos coeficientes. Onde os dois IC discordam sobre incluir o zero, a conclusão aditiva do par é incerta (coluna "Sensível ao método").

| Par | OR_A | OR_B | OR_AB | RERI [IC 95%, delta] | AP [IC 95%, delta] | Leitura (IC do delta) | Sensível ao método |
|---|---|---|---|---|---|---|---|
| DIABETES × HEMATOLOG | 2,98 | 9,32 | 13,44 | 2,13 [-4,51; 8,77] | 0,16 [-0,26; 0,58] | compatível com aditividade (IC inclui zero) | — |
| DIABETES × HEPATOPAT | 2,98 | 4,89 | 8,85 | 1,98 [-2,11; 6,06] | 0,22 [-0,13; 0,58] | compatível com aditividade (IC inclui zero) | — |
| DIABETES × RENAL | 2,98 | 6,80 | 19,00 | 10,22 [3,18; 17,26] | 0,54 [0,38; 0,69] | supra-aditivo | — |
| DIABETES × HIPERTENSA | 2,98 | 2,67 | 5,48 | 0,83 [-0,23; 1,88] | 0,15 [-0,01; 0,31] | compatível com aditividade (IC inclui zero) | — |
| DIABETES × AUTO_IMUNE | 2,98 | 5,02 | 5,15 | -1,86 [-5,02; 1,30] | -0,36 [-1,20; 0,48] | compatível com aditividade (IC inclui zero) | — |
| HEMATOLOG × HEPATOPAT | 9,32 | 4,89 | 8,21 | -5,00 [-10,64; 0,63] | -0,61 [-1,69; 0,47] | compatível com aditividade (IC inclui zero) | — |
| HEMATOLOG × RENAL | 9,32 | 6,80 | 7,90 | -7,23 [-13,01; -1,45] | -0,92 [-2,28; 0,45] | sub-aditivo | RERI |
| HEMATOLOG × HIPERTENSA | 9,32 | 2,67 | 9,74 | -1,26 [-5,44; 2,93] | -0,13 [-0,60; 0,35] | compatível com aditividade (IC inclui zero) | — |
| HEMATOLOG × AUTO_IMUNE | 9,32 | 5,02 | 31,09 | 17,74 [-1,07; 36,55] | 0,57 [0,31; 0,83] | compatível com aditividade (IC inclui zero) | RERI |
| HEPATOPAT × RENAL | 4,89 | 6,80 | 13,36 | 2,67 [-5,60; 10,95] | 0,20 [-0,29; 0,69] | compatível com aditividade (IC inclui zero) | — |
| HEPATOPAT × HIPERTENSA | 4,89 | 2,67 | 10,58 | 4,02 [0,06; 7,98] | 0,38 [0,14; 0,62] | supra-aditivo | — |
| RENAL × HIPERTENSA | 6,80 | 2,67 | 15,12 | 6,64 [2,29; 10,99] | 0,44 [0,26; 0,62] | supra-aditivo | — |
| RENAL × AUTO_IMUNE | 6,80 | 5,02 | 37,02 | 26,20 [3,63; 48,77] | 0,71 [0,54; 0,88] | supra-aditivo | — |
| HIPERTENSA × ACIDO_PEPT | 2,67 | 0,70 | 1,64 | -0,74 [-1,72; 0,24] | -0,45 [-1,27; 0,37] | compatível com aditividade (IC inclui zero) | — |
| HIPERTENSA × AUTO_IMUNE | 2,67 | 5,02 | 4,51 | -2,19 [-4,37; -0,01] | -0,49 [-1,15; 0,18] | sub-aditivo | RERI |

## Conferência: delta × simulação

Maior diferença entre os extremos dos dois IC, nos 15 pares: RERI 9,12; AP 0,61 (na escala de cada medida).

Pares sensíveis ao método (o IC delta e o IC por simulação discordam sobre incluir o zero): HEMATOLOG × RENAL (RERI), HEMATOLOG × AUTO_IMUNE (RERI), HIPERTENSA × AUTO_IMUNE (RERI). Nesses pares, a conclusão aditiva é incerta.

| Par | RERI: delta | RERI: simulação | AP: delta | AP: simulação |
|---|---|---|---|---|
| DIABETES × HEMATOLOG | [-4,51; 8,77] | [-3,39; 10,82] | [-0,26; 0,58] | [-0,40; 0,49] |
| DIABETES × HEPATOPAT | [-2,11; 6,06] | [-1,30; 7,51] | [-0,13; 0,58] | [-0,24; 0,51] |
| DIABETES × RENAL | [3,18; 17,26] | [4,49; 18,93] | [0,38; 0,69] | [0,35; 0,67] |
| DIABETES × HIPERTENSA | [-0,23; 1,88] | [-0,13; 2,01] | [-0,01; 0,31] | [-0,03; 0,29] |
| DIABETES × AUTO_IMUNE | [-5,02; 1,30] | [-4,42; 2,48] | [-1,20; 0,48] | [-1,57; 0,26] |
| HEMATOLOG × HEPATOPAT | [-10,64; 0,63] | [-9,57; 2,81] | [-1,69; 0,47] | [-2,17; 0,17] |
| HEMATOLOG × RENAL | [-13,01; -1,45] | [-11,93; 0,74] | [-2,28; 0,45] | [-2,88; 0,05] |
| HEMATOLOG × HIPERTENSA | [-5,44; 2,93] | [-5,07; 3,61] | [-0,60; 0,35] | [-0,73; 0,25] |
| HEMATOLOG × AUTO_IMUNE | [-1,07; 36,55] | [3,68; 42,83] | [0,31; 0,83] | [0,21; 0,76] |
| HEPATOPAT × RENAL | [-5,60; 10,95] | [-3,44; 14,66] | [-0,29; 0,69] | [-0,48; 0,57] |
| HEPATOPAT × HIPERTENSA | [0,06; 7,98] | [0,56; 8,67] | [0,14; 0,62] | [0,08; 0,58] |
| RENAL × HIPERTENSA | [2,29; 10,99] | [2,66; 11,60] | [0,26; 0,62] | [0,22; 0,59] |
| RENAL × AUTO_IMUNE | [3,63; 48,77] | [9,53; 57,89] | [0,54; 0,88] | [0,47; 0,84] |
| HIPERTENSA × ACIDO_PEPT | [-1,72; 0,24] | [-1,64; 0,45] | [-1,27; 0,37] | [-1,57; 0,16] |
| HIPERTENSA × AUTO_IMUNE | [-4,37; -0,01] | [-4,22; 0,26] | [-1,15; 0,18] | [-1,32; 0,04] |

6 pares com eventos insuficientes não entram nesta tabela (R7).

