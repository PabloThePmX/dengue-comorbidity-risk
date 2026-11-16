# Sensibilidade do E1 ao padrão "todas as 7 comorbidades = Sim"

> **Modelo explicativo: associação, não causa (P6).** Os coeficientes são associações ajustadas por idade e sexo, não efeitos causais. Descrevem o modelo, não o mundo.

A leitura é circunstancial; a causa do padrão não foi provada.
**Sensibilidade oficial: o cenário A** (decisão do Programador). É a análise citada nos demais relatórios do E1. Três ajustes com a mesma fórmula, os mesmos nós de idade e o recentramento em 40 (D-41/T-3.1). Principal: todos os casos de 2022–23. **A**: sem os casos com as 7 comorbidades = Sim (2000 casos excluídos; pares recalculados nesse dado). **B**: o principal mais um indicador do padrão, sem excluir casos. Logística sem penalização (R9). IC 95% pelo delta, como no principal (D-40). P-valores ajustados por Benjamini-Hochberg sobre os pares incluídos.

## Verificação de equivalência

- A × B com **indicador por padrão de covariáveis** (saturado): em teoria, equivale a excluir o grupo para os demais coeficientes. **Não confirmado com estes dados**: maior diferença nos coeficientes identificados (|β| < 10) = 0,061, contra a tolerância de 1e-6. Com 2 termos em separação quase perfeita (|β| ≥ 10), o MLE dos indicadores por caso não converge de forma estável.
- Principal × B com **um único indicador**: maior diferença nos coeficientes comuns = 0,295 (no log-OR). **B não equivale a excluir os casos.** A equivalência só valeria com um indicador por padrão de covariáveis (bullet acima), e não se confirmou aqui. Por isso B é só leitura complementar; A é a referência.

## Efeitos principais (OR, IC 95%)

| Comorbidade | Principal | A (sem o padrão) | B (indicador único) |
|---|---|---|---|
| DIABETES | 2,98 [2,30; 3,86] | 3,09 [2,39; 4,00] | 3,00 [2,32; 3,89] |
| HEMATOLOG | 9,32 [7,27; 11,95] | 6,93 [5,36; 8,97] | 9,95 [7,78; 12,72] |
| HEPATOPAT | 4,89 [3,58; 6,68] | 3,87 [2,85; 5,26] | 5,16 [3,79; 7,02] |
| RENAL | 6,80 [5,07; 9,12] | 5,44 [4,03; 7,34] | 7,20 [5,38; 9,64] |
| HIPERTENSA | 2,67 [2,24; 3,20] | 2,68 [2,24; 3,21] | 2,68 [2,24; 3,21] |
| ACIDO_PEPT | 0,70 [0,42; 1,17] | 0,43 [0,26; 0,73] | 0,77 [0,46; 1,27] |
| AUTO_IMUNE | 5,02 [3,78; 6,68] | 5,64 [4,28; 7,43] | 5,28 [3,98; 6,99] |

DIABETES e HIPERTENSA aos 40 anos, como no principal.

Maior variação de OR de efeito principal entre o principal e A: |log| = 0,483. Mudanças (principal → A): DIABETES: 2,98 → 3,09; HEMATOLOG: 9,32 → 6,93; HEPATOPAT: 4,89 → 3,87; RENAL: 6,80 → 5,44; HIPERTENSA: 2,67 → 2,68; ACIDO_PEPT: 0,70 → 0,43; AUTO_IMUNE: 5,02 → 5,64.

## Interações 2 a 2 (OR da interação, IC 95%, p ajustado BH)

| Par | Principal | A | B |
|---|---|---|---|
| DIABETES × HEMATOLOG | 0,48 [0,29; 0,80]; p ajust. 0,008 | 0,32 [0,19; 0,56]; p ajust. < 0,001 | 0,43 [0,26; 0,73]; p ajust. 0,003 |
| DIABETES × HEPATOPAT | 0,61 [0,38; 0,96]; p ajust. 0,056 | 0,60 [0,37; 0,98]; p ajust. 0,066 | 0,58 [0,36; 0,93]; p ajust. 0,041 |
| DIABETES × RENAL | 0,94 [0,68; 1,29]; p ajust. 0,766 | 0,97 [0,70; 1,34]; p ajust. 0,897 | 0,90 [0,65; 1,24]; p ajust. 0,561 |
| DIABETES × HIPERTENSA | 0,69 [0,55; 0,85]; p ajust. 0,002 | 0,66 [0,53; 0,82]; p ajust. < 0,001 | 0,68 [0,55; 0,84]; p ajust. 0,001 |
| DIABETES × AUTO_IMUNE | 0,34 [0,19; 0,63]; p ajust. 0,002 | 0,31 [0,16; 0,59]; p ajust. < 0,001 | 0,29 [0,15; 0,56]; p ajust. < 0,001 |
| HEMATOLOG × HEPATOPAT | 0,18 [0,09; 0,36]; p ajust. < 0,001 | — | 0,13 [0,06; 0,30]; p ajust. < 0,001 |
| HEMATOLOG × RENAL | 0,12 [0,06; 0,26]; p ajust. < 0,001 | — | 0,10 [0,04; 0,21]; p ajust. < 0,001 |
| HEMATOLOG × HIPERTENSA | 0,39 [0,26; 0,60]; p ajust. < 0,001 | 0,33 [0,21; 0,52]; p ajust. < 0,001 | 0,37 [0,24; 0,57]; p ajust. < 0,001 |
| HEMATOLOG × AUTO_IMUNE | 0,66 [0,35; 1,27]; p ajust. 0,323 | 0,28 [0,13; 0,61]; p ajust. 0,002 | 0,56 [0,28; 1,11]; p ajust. 0,147 |
| HEPATOPAT × RENAL | 0,40 [0,22; 0,75]; p ajust. 0,008 | 0,23 [0,12; 0,46]; p ajust. < 0,001 | 0,33 [0,17; 0,65]; p ajust. 0,003 |
| HEPATOPAT × HIPERTENSA | 0,81 [0,53; 1,24]; p ajust. 0,409 | 0,91 [0,59; 1,40]; p ajust. 0,861 | 0,79 [0,52; 1,21]; p ajust. 0,354 |
| RENAL × HIPERTENSA | 0,83 [0,59; 1,17]; p ajust. 0,393 | 0,98 [0,69; 1,39]; p ajust. 0,897 | 0,80 [0,57; 1,13]; p ajust. 0,277 |
| RENAL × AUTO_IMUNE | 1,08 [0,59; 1,99]; p ajust. 0,795 | 0,77 [0,38; 1,55]; p ajust. 0,666 | 1,00 [0,53; 1,90]; p ajust. 0,991 |
| HIPERTENSA × ACIDO_PEPT | 0,87 [0,41; 1,83]; p ajust. 0,766 | 1,08 [0,49; 2,42]; p ajust. 0,897 | 0,67 [0,30; 1,48]; p ajust. 0,372 |
| HIPERTENSA × AUTO_IMUNE | 0,34 [0,21; 0,54]; p ajust. < 0,001 | 0,32 [0,20; 0,52]; p ajust. < 0,001 | 0,33 [0,20; 0,53]; p ajust. < 0,001 |

Pares que **entram** no E1 em A: nenhum. Pares que **saem** em A: HEMATOLOG × HEPATOPAT, HEMATOLOG × RENAL.
Em B: entram nenhum; saem nenhum.

## Ranking de comorbidades (só pelo E1, R10)

| Posição | Principal | A | B |
|---|---|---|---|
| 1 | HEMATOLOG | HEMATOLOG | HEMATOLOG |
| 2 | RENAL | AUTO_IMUNE | RENAL |
| 3 | AUTO_IMUNE | RENAL | AUTO_IMUNE |
| 4 | HEPATOPAT | HEPATOPAT | HEPATOPAT |
| 5 | DIABETES | DIABETES | DIABETES |
| 6 | HIPERTENSA | HIPERTENSA | HIPERTENSA |
| 7 | ACIDO_PEPT | ACIDO_PEPT | ACIDO_PEPT |

## Plausibilidade dos perfis de 3 ou mais (razão vs. saudável, 60–79, F)

| Ajuste | Perfis de 3+ | Razão < 1 | Abaixo do maior componente |
|---|---|---|---|
| principal | 75 | 5 | 45 |
| A | 75 | 3 | 31 |
| B | 75 | 11 | 49 |

Perfis com razão < 1 em A: DIABETES + HEMATOLOG + HIPERTENSA + AUTO_IMUNE, DIABETES + HEMATOLOG + HEPATOPAT + HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE, DIABETES + HEMATOLOG + HEPATOPAT + RENAL + HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE.

## Conclusão objetiva

- Efeitos principais: a maior variação de OR entre principal e A é um fator de 1,62.
- Ranking: principal HEMATOLOG > RENAL > AUTO_IMUNE …; A HEMATOLOG > AUTO_IMUNE > RENAL …. A ordem muda nas posições 2 e 3: AUTO_IMUNE (principal: RENAL) e RENAL (principal: AUTO_IMUNE).
- Interações: 15 pares no principal, 13 em A, 15 em B. As interações com IC 95% inteiro abaixo de 1 são 8 em A (contra 9 no principal). As interações negativas **persistem** sem o padrão: ele explica só parte delas.
- ACIDO_PEPT: Sem o padrão, ACIDO_PEPT fica **mais** protetor (0,43 contra 0,70 no principal). A hipótese de que o padrão explica o OR protetor de ACIDO_PEPT **não se confirmou**.
- Perfis de 3+ com razão < 1: principal 5, A 3, B 11 (de 75).

Sensibilidade oficial: cenário A, decidida pelo Programador. Os relatórios principais do E1 não excluem os casos do padrão; citam este cenário.

