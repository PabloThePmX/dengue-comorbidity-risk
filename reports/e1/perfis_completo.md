# Tabela de perfis de risco (T-3.5, FR-06)

> **Modelo explicativo: associação, não causa (P6).** Os coeficientes são associações ajustadas por idade e sexo, não efeitos causais. Descrevem o modelo, não o mundo.

Modelo: E1, logística sem penalização (R9), ajustada em 2022–23 com idade (spline), sexo, gestação e comorbidades. Os perfis vêm do E1 e das contagens de 2022–23 (D-52); nenhum perfil foi escrito à mão.

- **Risco estimado:** probabilidade prevista de dengue grave ou óbito para o perfil, em %, com 3 casas. IC 95%: método delta na escala do logit (η ± 1,96 · EP), transformado pela logística.
- **Razão vs. "saudável":** risco do perfil dividido pelo risco de "sem comorbidades" na mesma faixa e sexo, com 2 casas. IC 95%: método delta na escala do log da razão, com Var = dᵀΣd, em que d é a diferença entre as linhas do desenho dos dois perfis. A covariância entre os dois logits entra pela Σ.
- **Perfil:** só as comorbidades listadas estão "Sim"; as demais, "Não" (referência do modelo). Gestante: Não. Idade: meio da faixa (80+ usa 80). Sexo: F e M separados (`[ASSUMPTION]`); I não aparece.
- **Supressão (R7):** a célula observada é o nº de casos de 2022–23 com o mesmo padrão de comorbidades, na mesma faixa e sexo e gestante Não; as demais comorbidades não Sim, inclusive "Ausente", como na T-2.6. Com menos de 10 casos, risco, IC e razão saem como "—", sem contagem. A supressão usa a célula observada porque o risco é previsto pelo modelo, não contado. Por cautela, a razão também sai "—" se a célula do saudável estiver suprimida. Nenhuma contagem de 1 a 9 é publicada.
- **Pares sem termo:** os pares com "dados insuficientes" (menos de 10 eventos) não têm termo no E1. Um perfil que contém um desses pares não recebe efeito para ele.
- **Três ou quatro comorbidades:** têm estimativa. A nota da linha diz "trio" (3) ou "combinação" (4): risco estimado pela soma dos efeitos individuais e dos pares, porque o E1 não tem termo próprio para elas.
- **Cinco ou mais comorbidades:** não têm estimativa. São combinações com menos de 10 eventos no total; o E1 não tem termo para elas e a extrapolação é instável. Aparecem como "dados insuficientes", sem número de eventos (R7).
- **Aviso:** o perfil contém um dos pares que só têm 10 ou mais eventos por causa do padrão suspeito "todas as 7 comorbidades = Sim" (HEMATOLOG × HEPATOPAT e HEMATOLOG × RENAL). Sem o padrão, esses pares saem do E1; ver [sensibilidade](sensibilidade_padrao_todas_sim.md).
- **Combinações omitidas:** combinações de 3 ou mais comorbidades com menos de 10 casos em 2022–23, que não aparecem na tabela (R7): 24.
- **Demo:** a demo calcula qualquer combinação pelo E1 (`risco_perfil`), mesmo as que não estão nesta tabela.
- Leitura: associação ajustada, não causa. Não é ferramenta clínica nem substitui avaliação médica.

Referência: "sem comorbidades" tem razão 1,00 por definição.

## Grupo 1: Referência (1 perfis)

Células suprimidas (R7) neste grupo: 0 de 12.

| Perfil | Faixa etária | Sexo | Risco estimado | IC 95% | Razão vs. "saudável" (mesma faixa e sexo), IC 95% | Aviso |
|---|---|---|---|---|---|---|
| Sem comorbidades | 0–4 | F | 0,164% | [0,145%; 0,187%] | 1,00 [1,00; 1,00] | — |
| Sem comorbidades | 0–4 | M | 0,204% | [0,180%; 0,232%] | 1,00 [1,00; 1,00] | — |
| Sem comorbidades | 5–14 | F | 0,087% | [0,079%; 0,096%] | 1,00 [1,00; 1,00] | — |
| Sem comorbidades | 5–14 | M | 0,108% | [0,099%; 0,119%] | 1,00 [1,00; 1,00] | — |
| Sem comorbidades | 15–39 | F | 0,062% | [0,056%; 0,070%] | 1,00 [1,00; 1,00] | — |
| Sem comorbidades | 15–39 | M | 0,078% | [0,070%; 0,086%] | 1,00 [1,00; 1,00] | — |
| Sem comorbidades | 40–59 | F | 0,078% | [0,072%; 0,084%] | 1,00 [1,00; 1,00] | — |
| Sem comorbidades | 40–59 | M | 0,096% | [0,089%; 0,105%] | 1,00 [1,00; 1,00] | — |
| Sem comorbidades | 60–79 | F | 0,194% | [0,178%; 0,212%] | 1,00 [1,00; 1,00] | — |
| Sem comorbidades | 60–79 | M | 0,241% | [0,221%; 0,263%] | 1,00 [1,00; 1,00] | — |
| Sem comorbidades | 80+ | F | 0,435% | [0,397%; 0,477%] | 1,00 [1,00; 1,00] | — |
| Sem comorbidades | 80+ | M | 0,540% | [0,493%; 0,591%] | 1,00 [1,00; 1,00] | — |

## Grupo 2: Uma comorbidade (7 perfis)

Células suprimidas (R7) neste grupo: 0 de 84.

| Perfil | Faixa etária | Sexo | Risco estimado | IC 95% | Razão vs. "saudável" (mesma faixa e sexo), IC 95% | Aviso |
|---|---|---|---|---|---|---|
| DIABETES | 0–4 | F | 0,156% | [0,038%; 0,643%] | 0,95 [0,23; 3,93] | — |
| DIABETES | 0–4 | M | 0,194% | [0,047%; 0,797%] | 0,95 [0,23; 3,93] | — |
| DIABETES | 5–14 | F | 0,123% | [0,052%; 0,294%] | 1,41 [0,59; 3,38] | — |
| DIABETES | 5–14 | M | 0,153% | [0,064%; 0,365%] | 1,41 [0,59; 3,38] | — |
| DIABETES | 15–39 | F | 0,167% | [0,112%; 0,249%] | 2,67 [1,81; 3,95] | — |
| DIABETES | 15–39 | M | 0,207% | [0,139%; 0,309%] | 2,67 [1,81; 3,95] | — |
| DIABETES | 40–59 | F | 0,228% | [0,187%; 0,279%] | 2,95 [2,42; 3,60] | — |
| DIABETES | 40–59 | M | 0,284% | [0,232%; 0,347%] | 2,95 [2,42; 3,60] | — |
| DIABETES | 60–79 | F | 0,499% | [0,409%; 0,609%] | 2,57 [2,10; 3,16] | — |
| DIABETES | 60–79 | M | 0,619% | [0,507%; 0,755%] | 2,57 [2,10; 3,16] | — |
| DIABETES | 80+ | F | 0,994% | [0,805%; 1,228%] | 2,30 [1,85; 2,85] | — |
| DIABETES | 80+ | M | 1,232% | [0,998%; 1,520%] | 2,30 [1,85; 2,85] | — |
| HEMATOLOG | 0–4 | F | 1,512% | [1,153%; 1,982%] | 9,32 [7,27; 11,95] | — |
| HEMATOLOG | 0–4 | M | 1,872% | [1,430%; 2,447%] | 9,32 [7,27; 11,95] | — |
| HEMATOLOG | 5–14 | F | 0,808% | [0,623%; 1,046%] | 9,32 [7,27; 11,95] | — |
| HEMATOLOG | 5–14 | M | 1,001% | [0,774%; 1,295%] | 9,32 [7,27; 11,95] | — |
| HEMATOLOG | 15–39 | F | 0,579% | [0,445%; 0,754%] | 9,32 [7,27; 11,95] | — |
| HEMATOLOG | 15–39 | M | 0,718% | [0,552%; 0,934%] | 9,32 [7,27; 11,95] | — |
| HEMATOLOG | 40–59 | F | 0,718% | [0,558%; 0,925%] | 9,32 [7,27; 11,95] | — |
| HEMATOLOG | 40–59 | M | 0,891% | [0,691%; 1,147%] | 9,32 [7,27; 11,95] | — |
| HEMATOLOG | 60–79 | F | 1,783% | [1,385%; 2,293%] | 9,32 [7,27; 11,95] | — |
| HEMATOLOG | 60–79 | M | 2,205% | [1,714%; 2,833%] | 9,32 [7,27; 11,95] | — |
| HEMATOLOG | 80+ | F | 3,916% | [3,053%; 5,010%] | 9,32 [7,27; 11,95] | — |
| HEMATOLOG | 80+ | M | 4,818% | [3,764%; 6,149%] | 9,32 [7,27; 11,95] | — |
| HEPATOPAT | 0–4 | F | 0,799% | [0,573%; 1,113%] | 4,89 [3,58; 6,68] | — |
| HEPATOPAT | 0–4 | M | 0,991% | [0,712%; 1,377%] | 4,89 [3,58; 6,68] | — |
| HEPATOPAT | 5–14 | F | 0,425% | [0,308%; 0,587%] | 4,89 [3,58; 6,68] | — |
| HEPATOPAT | 5–14 | M | 0,528% | [0,383%; 0,727%] | 4,89 [3,58; 6,68] | — |
| HEPATOPAT | 15–39 | F | 0,305% | [0,220%; 0,422%] | 4,89 [3,58; 6,68] | — |
| HEPATOPAT | 15–39 | M | 0,378% | [0,273%; 0,523%] | 4,89 [3,58; 6,68] | — |
| HEPATOPAT | 40–59 | F | 0,378% | [0,275%; 0,519%] | 4,89 [3,58; 6,68] | — |
| HEPATOPAT | 40–59 | M | 0,469% | [0,342%; 0,644%] | 4,89 [3,58; 6,68] | — |
| HEPATOPAT | 60–79 | F | 0,943% | [0,687%; 1,293%] | 4,89 [3,58; 6,68] | — |
| HEPATOPAT | 60–79 | M | 1,169% | [0,853%; 1,601%] | 4,89 [3,58; 6,68] | — |
| HEPATOPAT | 80+ | F | 2,093% | [1,529%; 2,859%] | 4,89 [3,58; 6,68] | — |
| HEPATOPAT | 80+ | M | 2,586% | [1,892%; 3,526%] | 4,89 [3,58; 6,68] | — |
| RENAL | 0–4 | F | 1,107% | [0,807%; 1,517%] | 6,80 [5,07; 9,12] | — |
| RENAL | 0–4 | M | 1,372% | [1,003%; 1,874%] | 6,80 [5,07; 9,12] | — |
| RENAL | 5–14 | F | 0,590% | [0,435%; 0,801%] | 6,80 [5,07; 9,12] | — |
| RENAL | 5–14 | M | 0,732% | [0,540%; 0,991%] | 6,80 [5,07; 9,12] | — |
| RENAL | 15–39 | F | 0,423% | [0,310%; 0,576%] | 6,80 [5,07; 9,12] | — |
| RENAL | 15–39 | M | 0,525% | [0,386%; 0,714%] | 6,80 [5,07; 9,12] | — |
| RENAL | 40–59 | F | 0,525% | [0,389%; 0,708%] | 6,80 [5,07; 9,12] | — |
| RENAL | 40–59 | M | 0,651% | [0,483%; 0,877%] | 6,80 [5,07; 9,12] | — |
| RENAL | 60–79 | F | 1,307% | [0,970%; 1,757%] | 6,80 [5,07; 9,12] | — |
| RENAL | 60–79 | M | 1,618% | [1,203%; 2,172%] | 6,80 [5,07; 9,12] | — |
| RENAL | 80+ | F | 2,886% | [2,153%; 3,858%] | 6,80 [5,07; 9,12] | — |
| RENAL | 80+ | M | 3,560% | [2,662%; 4,745%] | 6,80 [5,07; 9,12] | — |
| HIPERTENSA | 0–4 | F | 0,082% | [0,020%; 0,339%] | 0,50 [0,12; 2,07] | — |
| HIPERTENSA | 0–4 | M | 0,102% | [0,025%; 0,421%] | 0,50 [0,12; 2,07] | — |
| HIPERTENSA | 5–14 | F | 0,081% | [0,033%; 0,194%] | 0,92 [0,38; 2,23] | — |
| HIPERTENSA | 5–14 | M | 0,100% | [0,042%; 0,241%] | 0,92 [0,38; 2,23] | — |
| HIPERTENSA | 15–39 | F | 0,148% | [0,109%; 0,201%] | 2,38 [1,77; 3,19] | — |
| HIPERTENSA | 15–39 | M | 0,184% | [0,136%; 0,250%] | 2,38 [1,77; 3,19] | — |
| HIPERTENSA | 40–59 | F | 0,208% | [0,185%; 0,233%] | 2,68 [2,37; 3,04] | — |
| HIPERTENSA | 40–59 | M | 0,258% | [0,229%; 0,290%] | 2,68 [2,37; 3,04] | — |
| HIPERTENSA | 60–79 | F | 0,542% | [0,494%; 0,595%] | 2,80 [2,49; 3,14] | — |
| HIPERTENSA | 60–79 | M | 0,672% | [0,611%; 0,739%] | 2,80 [2,49; 3,14] | — |
| HIPERTENSA | 80+ | F | 1,253% | [1,146%; 1,370%] | 2,90 [2,58; 3,26] | — |
| HIPERTENSA | 80+ | M | 1,551% | [1,416%; 1,700%] | 2,90 [2,58; 3,26] | — |
| ACIDO_PEPT | 0–4 | F | 0,116% | [0,068%; 0,196%] | 0,70 [0,42; 1,17] | — |
| ACIDO_PEPT | 0–4 | M | 0,144% | [0,085%; 0,243%] | 0,70 [0,42; 1,17] | — |
| ACIDO_PEPT | 5–14 | F | 0,061% | [0,037%; 0,103%] | 0,70 [0,42; 1,17] | — |
| ACIDO_PEPT | 5–14 | M | 0,076% | [0,045%; 0,128%] | 0,70 [0,42; 1,17] | — |
| ACIDO_PEPT | 15–39 | F | 0,044% | [0,026%; 0,074%] | 0,70 [0,42; 1,17] | — |
| ACIDO_PEPT | 15–39 | M | 0,055% | [0,032%; 0,092%] | 0,70 [0,42; 1,17] | — |
| ACIDO_PEPT | 40–59 | F | 0,055% | [0,033%; 0,091%] | 0,70 [0,42; 1,17] | — |
| ACIDO_PEPT | 40–59 | M | 0,068% | [0,040%; 0,114%] | 0,70 [0,42; 1,17] | — |
| ACIDO_PEPT | 60–79 | F | 0,137% | [0,081%; 0,230%] | 0,70 [0,42; 1,17] | — |
| ACIDO_PEPT | 60–79 | M | 0,170% | [0,101%; 0,285%] | 0,70 [0,42; 1,17] | — |
| ACIDO_PEPT | 80+ | F | 0,307% | [0,183%; 0,515%] | 0,70 [0,42; 1,17] | — |
| ACIDO_PEPT | 80+ | M | 0,381% | [0,227%; 0,638%] | 0,70 [0,42; 1,17] | — |
| AUTO_IMUNE | 0–4 | F | 0,821% | [0,603%; 1,115%] | 5,02 [3,78; 6,68] | — |
| AUTO_IMUNE | 0–4 | M | 1,017% | [0,748%; 1,382%] | 5,02 [3,78; 6,68] | — |
| AUTO_IMUNE | 5–14 | F | 0,437% | [0,325%; 0,587%] | 5,02 [3,78; 6,68] | — |
| AUTO_IMUNE | 5–14 | M | 0,542% | [0,403%; 0,728%] | 5,02 [3,78; 6,68] | — |
| AUTO_IMUNE | 15–39 | F | 0,313% | [0,232%; 0,422%] | 5,02 [3,78; 6,68] | — |
| AUTO_IMUNE | 15–39 | M | 0,388% | [0,288%; 0,524%] | 5,02 [3,78; 6,68] | — |
| AUTO_IMUNE | 40–59 | F | 0,388% | [0,291%; 0,517%] | 5,02 [3,78; 6,68] | — |
| AUTO_IMUNE | 40–59 | M | 0,482% | [0,361%; 0,643%] | 5,02 [3,78; 6,68] | — |
| AUTO_IMUNE | 60–79 | F | 0,969% | [0,726%; 1,292%] | 5,02 [3,78; 6,68] | — |
| AUTO_IMUNE | 60–79 | M | 1,200% | [0,899%; 1,602%] | 5,02 [3,78; 6,68] | — |
| AUTO_IMUNE | 80+ | F | 2,148% | [1,612%; 2,858%] | 5,02 [3,78; 6,68] | — |
| AUTO_IMUNE | 80+ | M | 2,655% | [1,992%; 3,531%] | 5,02 [3,78; 6,68] | — |

## Grupo 3: Pares de comorbidades (21 perfis; 6 com dados insuficientes)

Células suprimidas (R7) neste grupo: 60 de 180.

| Perfil | Faixa etária | Sexo | Risco estimado | IC 95% | Razão vs. "saudável" (mesma faixa e sexo), IC 95% | Aviso |
|---|---|---|---|---|---|---|
| DIABETES + HEMATOLOG | 0–4 | F | — | — | — | — |
| DIABETES + HEMATOLOG | 0–4 | M | — | — | — | — |
| DIABETES + HEMATOLOG | 5–14 | F | 0,553% | [0,213%; 1,428%] | 6,36 [2,44; 16,59] | — |
| DIABETES + HEMATOLOG | 5–14 | M | 0,686% | [0,264%; 1,767%] | 6,36 [2,44; 16,59] | — |
| DIABETES + HEMATOLOG | 15–39 | F | 0,747% | [0,416%; 1,336%] | 12,04 [6,72; 21,58] | — |
| DIABETES + HEMATOLOG | 15–39 | M | 0,926% | [0,516%; 1,655%] | 12,04 [6,72; 21,58] | — |
| DIABETES + HEMATOLOG | 40–59 | F | 1,021% | [0,619%; 1,679%] | 13,29 [8,02; 22,03] | — |
| DIABETES + HEMATOLOG | 40–59 | M | 1,265% | [0,767%; 2,078%] | 13,29 [8,02; 22,03] | — |
| DIABETES + HEMATOLOG | 60–79 | F | 2,208% | [1,340%; 3,619%] | 11,60 [6,95; 19,36] | — |
| DIABETES + HEMATOLOG | 60–79 | M | 2,728% | [1,658%; 4,457%] | 11,60 [6,95; 19,36] | — |
| DIABETES + HEMATOLOG | 80+ | F | 4,328% | [2,644%; 7,010%] | 10,35 [6,19; 17,30] | — |
| DIABETES + HEMATOLOG | 80+ | M | — | — | — | — |
| DIABETES + HEPATOPAT | 0–4 | F | — | — | — | — |
| DIABETES + HEPATOPAT | 0–4 | M | — | — | — | — |
| DIABETES + HEPATOPAT | 5–14 | F | 0,365% | [0,138%; 0,959%] | 4,19 [1,58; 11,09] | — |
| DIABETES + HEPATOPAT | 5–14 | M | 0,453% | [0,172%; 1,188%] | 4,19 [1,58; 11,09] | — |
| DIABETES + HEPATOPAT | 15–39 | F | 0,493% | [0,269%; 0,900%] | 7,93 [4,35; 14,46] | — |
| DIABETES + HEPATOPAT | 15–39 | M | 0,611% | [0,335%; 1,115%] | 7,93 [4,35; 14,46] | — |
| DIABETES + HEPATOPAT | 40–59 | F | 0,675% | [0,409%; 1,110%] | 8,75 [5,29; 14,49] | — |
| DIABETES + HEPATOPAT | 40–59 | M | 0,836% | [0,508%; 1,376%] | 8,75 [5,29; 14,49] | — |
| DIABETES + HEPATOPAT | 60–79 | F | 1,465% | [0,889%; 2,405%] | 7,64 [4,59; 12,71] | — |
| DIABETES + HEPATOPAT | 60–79 | M | 1,813% | [1,102%; 2,969%] | 7,64 [4,59; 12,71] | — |
| DIABETES + HEPATOPAT | 80+ | F | — | — | — | — |
| DIABETES + HEPATOPAT | 80+ | M | — | — | — | — |
| DIABETES + RENAL | 0–4 | F | — | — | — | — |
| DIABETES + RENAL | 0–4 | M | — | — | — | — |
| DIABETES + RENAL | 5–14 | F | — | — | — | — |
| DIABETES + RENAL | 5–14 | M | — | — | — | — |
| DIABETES + RENAL | 15–39 | F | 1,052% | [0,625%; 1,766%] | 17,02 [10,13; 28,61] | — |
| DIABETES + RENAL | 15–39 | M | 1,304% | [0,775%; 2,184%] | 17,02 [10,13; 28,61] | — |
| DIABETES + RENAL | 40–59 | F | 1,437% | [0,975%; 2,114%] | 18,79 [12,66; 27,88] | — |
| DIABETES + RENAL | 40–59 | M | 1,779% | [1,208%; 2,612%] | 18,79 [12,66; 27,88] | — |
| DIABETES + RENAL | 60–79 | F | 3,093% | [2,125%; 4,484%] | 16,40 [11,08; 24,26] | — |
| DIABETES + RENAL | 60–79 | M | 3,814% | [2,626%; 5,508%] | 16,40 [11,08; 24,26] | — |
| DIABETES + RENAL | 80+ | F | 6,012% | [4,158%; 8,618%] | 14,63 [9,87; 21,70] | — |
| DIABETES + RENAL | 80+ | M | 7,360% | [5,115%; 10,481%] | 14,63 [9,87; 21,70] | — |
| DIABETES + HIPERTENSA | 0–4 | F | 0,054% | [0,008%; 0,342%] | 0,33 [0,05; 2,09] | — |
| DIABETES + HIPERTENSA | 0–4 | M | 0,067% | [0,010%; 0,424%] | 0,33 [0,05; 2,09] | — |
| DIABETES + HIPERTENSA | 5–14 | F | 0,078% | [0,025%; 0,248%] | 0,90 [0,28; 2,85] | — |
| DIABETES + HIPERTENSA | 5–14 | M | 0,097% | [0,031%; 0,307%] | 0,90 [0,28; 2,85] | — |
| DIABETES + HIPERTENSA | 15–39 | F | 0,272% | [0,175%; 0,423%] | 4,37 [2,81; 6,78] | — |
| DIABETES + HIPERTENSA | 15–39 | M | 0,338% | [0,217%; 0,525%] | 4,37 [2,81; 6,78] | — |
| DIABETES + HIPERTENSA | 40–59 | F | 0,420% | [0,362%; 0,488%] | 5,44 [4,63; 6,39] | — |
| DIABETES + HIPERTENSA | 40–59 | M | 0,521% | [0,448%; 0,607%] | 5,44 [4,63; 6,39] | — |
| DIABETES + HIPERTENSA | 60–79 | F | 0,955% | [0,861%; 1,059%] | 4,95 [4,35; 5,64] | — |
| DIABETES + HIPERTENSA | 60–79 | M | 1,183% | [1,064%; 1,316%] | 4,95 [4,35; 5,64] | — |
| DIABETES + HIPERTENSA | 80+ | F | 1,965% | [1,763%; 2,189%] | 4,59 [3,99; 5,27] | — |
| DIABETES + HIPERTENSA | 80+ | M | 2,429% | [2,175%; 2,711%] | 4,59 [3,99; 5,27] | — |
| DIABETES + ACIDO_PEPT | — | — | dados insuficientes | — | — | — |
| DIABETES + AUTO_IMUNE | 0–4 | F | — | — | — | — |
| DIABETES + AUTO_IMUNE | 0–4 | M | — | — | — | — |
| DIABETES + AUTO_IMUNE | 5–14 | F | — | — | — | — |
| DIABETES + AUTO_IMUNE | 5–14 | M | — | — | — | — |
| DIABETES + AUTO_IMUNE | 15–39 | F | 0,287% | [0,138%; 0,597%] | 4,61 [2,22; 9,57] | — |
| DIABETES + AUTO_IMUNE | 15–39 | M | 0,357% | [0,171%; 0,740%] | 4,61 [2,22; 9,57] | — |
| DIABETES + AUTO_IMUNE | 40–59 | F | 0,393% | [0,204%; 0,757%] | 5,09 [2,63; 9,85] | — |
| DIABETES + AUTO_IMUNE | 40–59 | M | 0,488% | [0,253%; 0,939%] | 5,09 [2,63; 9,85] | — |
| DIABETES + AUTO_IMUNE | 60–79 | F | 0,857% | [0,444%; 1,649%] | 4,44 [2,28; 8,65] | — |
| DIABETES + AUTO_IMUNE | 60–79 | M | 1,063% | [0,551%; 2,040%] | 4,44 [2,28; 8,65] | — |
| DIABETES + AUTO_IMUNE | 80+ | F | — | — | — | — |
| DIABETES + AUTO_IMUNE | 80+ | M | — | — | — | — |
| HEMATOLOG + HEPATOPAT | 0–4 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) |
| HEMATOLOG + HEPATOPAT | 0–4 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) |
| HEMATOLOG + HEPATOPAT | 5–14 | F | 0,712% | [0,353%; 1,431%] | 8,21 [4,07; 16,56] | depende do padrão suspeito (ver sensibilidade) |
| HEMATOLOG + HEPATOPAT | 5–14 | M | 0,883% | [0,439%; 1,770%] | 8,21 [4,07; 16,56] | depende do padrão suspeito (ver sensibilidade) |
| HEMATOLOG + HEPATOPAT | 15–39 | F | 0,511% | [0,253%; 1,029%] | 8,21 [4,07; 16,56] | depende do padrão suspeito (ver sensibilidade) |
| HEMATOLOG + HEPATOPAT | 15–39 | M | 0,633% | [0,314%; 1,275%] | 8,21 [4,07; 16,56] | depende do padrão suspeito (ver sensibilidade) |
| HEMATOLOG + HEPATOPAT | 40–59 | F | 0,633% | [0,315%; 1,270%] | 8,21 [4,07; 16,56] | depende do padrão suspeito (ver sensibilidade) |
| HEMATOLOG + HEPATOPAT | 40–59 | M | 0,785% | [0,391%; 1,573%] | 8,21 [4,07; 16,56] | depende do padrão suspeito (ver sensibilidade) |
| HEMATOLOG + HEPATOPAT | 60–79 | F | 1,574% | [0,786%; 3,129%] | 8,21 [4,07; 16,56] | depende do padrão suspeito (ver sensibilidade) |
| HEMATOLOG + HEPATOPAT | 60–79 | M | 1,948% | [0,974%; 3,856%] | 8,21 [4,07; 16,56] | depende do padrão suspeito (ver sensibilidade) |
| HEMATOLOG + HEPATOPAT | 80+ | F | — | — | — | depende do padrão suspeito (ver sensibilidade) |
| HEMATOLOG + HEPATOPAT | 80+ | M | — | — | — | depende do padrão suspeito (ver sensibilidade) |
| HEMATOLOG + RENAL | 0–4 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) |
| HEMATOLOG + RENAL | 0–4 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) |
| HEMATOLOG + RENAL | 5–14 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) |
| HEMATOLOG + RENAL | 5–14 | M | 0,849% | [0,405%; 1,774%] | 7,90 [3,76; 16,59] | depende do padrão suspeito (ver sensibilidade) |
| HEMATOLOG + RENAL | 15–39 | F | 0,491% | [0,233%; 1,032%] | 7,90 [3,76; 16,59] | depende do padrão suspeito (ver sensibilidade) |
| HEMATOLOG + RENAL | 15–39 | M | 0,609% | [0,289%; 1,278%] | 7,90 [3,76; 16,59] | depende do padrão suspeito (ver sensibilidade) |
| HEMATOLOG + RENAL | 40–59 | F | 0,609% | [0,290%; 1,273%] | 7,90 [3,76; 16,59] | depende do padrão suspeito (ver sensibilidade) |
| HEMATOLOG + RENAL | 40–59 | M | 0,755% | [0,360%; 1,577%] | 7,90 [3,76; 16,59] | depende do padrão suspeito (ver sensibilidade) |
| HEMATOLOG + RENAL | 60–79 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) |
| HEMATOLOG + RENAL | 60–79 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) |
| HEMATOLOG + RENAL | 80+ | F | — | — | — | depende do padrão suspeito (ver sensibilidade) |
| HEMATOLOG + RENAL | 80+ | M | — | — | — | depende do padrão suspeito (ver sensibilidade) |
| HEMATOLOG + HIPERTENSA | 0–4 | F | — | — | — | — |
| HEMATOLOG + HIPERTENSA | 0–4 | M | — | — | — | — |
| HEMATOLOG + HIPERTENSA | 5–14 | F | 0,293% | [0,114%; 0,752%] | 3,37 [1,31; 8,67] | — |
| HEMATOLOG + HIPERTENSA | 5–14 | M | 0,364% | [0,141%; 0,933%] | 3,37 [1,31; 8,67] | — |
| HEMATOLOG + HIPERTENSA | 15–39 | F | 0,538% | [0,334%; 0,866%] | 8,66 [5,39; 13,92] | — |
| HEMATOLOG + HIPERTENSA | 15–39 | M | 0,668% | [0,414%; 1,075%] | 8,66 [5,39; 13,92] | — |
| HEMATOLOG + HIPERTENSA | 40–59 | F | 0,752% | [0,507%; 1,115%] | 9,77 [6,54; 14,59] | — |
| HEMATOLOG + HIPERTENSA | 40–59 | M | 0,933% | [0,629%; 1,382%] | 9,77 [6,54; 14,59] | — |
| HEMATOLOG + HIPERTENSA | 60–79 | F | 1,946% | [1,324%; 2,852%] | 10,19 [6,84; 15,19] | — |
| HEMATOLOG + HIPERTENSA | 60–79 | M | 2,406% | [1,639%; 3,520%] | 10,19 [6,84; 15,19] | — |
| HEMATOLOG + HIPERTENSA | 80+ | F | 4,418% | [3,036%; 6,388%] | 10,58 [7,10; 15,75] | — |
| HEMATOLOG + HIPERTENSA | 80+ | M | 5,430% | [3,741%; 7,819%] | 10,58 [7,10; 15,75] | — |
| HEMATOLOG + ACIDO_PEPT | — | — | dados insuficientes | — | — | — |
| HEMATOLOG + AUTO_IMUNE | 0–4 | F | — | — | — | — |
| HEMATOLOG + AUTO_IMUNE | 0–4 | M | — | — | — | — |
| HEMATOLOG + AUTO_IMUNE | 5–14 | F | — | — | — | — |
| HEMATOLOG + AUTO_IMUNE | 5–14 | M | — | — | — | — |
| HEMATOLOG + AUTO_IMUNE | 15–39 | F | 1,905% | [1,030%; 3,498%] | 31,09 [16,75; 57,68] | — |
| HEMATOLOG + AUTO_IMUNE | 15–39 | M | 2,356% | [1,275%; 4,311%] | 31,09 [16,75; 57,68] | — |
| HEMATOLOG + AUTO_IMUNE | 40–59 | F | 2,355% | [1,282%; 4,287%] | 31,09 [16,75; 57,68] | — |
| HEMATOLOG + AUTO_IMUNE | 40–59 | M | 2,909% | [1,587%; 5,274%] | 31,09 [16,75; 57,68] | — |
| HEMATOLOG + AUTO_IMUNE | 60–79 | F | 5,707% | [3,153%; 10,114%] | 31,09 [16,75; 57,68] | — |
| HEMATOLOG + AUTO_IMUNE | 60–79 | M | — | — | — | — |
| HEMATOLOG + AUTO_IMUNE | 80+ | F | — | — | — | — |
| HEMATOLOG + AUTO_IMUNE | 80+ | M | — | — | — | — |
| HEPATOPAT + RENAL | 0–4 | F | — | — | — | — |
| HEPATOPAT + RENAL | 0–4 | M | — | — | — | — |
| HEPATOPAT + RENAL | 5–14 | F | — | — | — | — |
| HEPATOPAT + RENAL | 5–14 | M | — | — | — | — |
| HEPATOPAT + RENAL | 15–39 | F | 0,828% | [0,419%; 1,627%] | 13,36 [6,78; 26,31] | — |
| HEPATOPAT + RENAL | 15–39 | M | 1,026% | [0,520%; 2,013%] | 13,36 [6,78; 26,31] | — |
| HEPATOPAT + RENAL | 40–59 | F | 1,026% | [0,523%; 2,005%] | 13,36 [6,78; 26,31] | — |
| HEPATOPAT + RENAL | 40–59 | M | 1,271% | [0,648%; 2,478%] | 13,36 [6,78; 26,31] | — |
| HEPATOPAT + RENAL | 60–79 | F | — | — | — | — |
| HEPATOPAT + RENAL | 60–79 | M | — | — | — | — |
| HEPATOPAT + RENAL | 80+ | F | — | — | — | — |
| HEPATOPAT + RENAL | 80+ | M | — | — | — | — |
| HEPATOPAT + HIPERTENSA | 0–4 | F | 0,324% | [0,076%; 1,371%] | 1,98 [0,46; 8,45] | — |
| HEPATOPAT + HIPERTENSA | 0–4 | M | — | — | — | — |
| HEPATOPAT + HIPERTENSA | 5–14 | F | 0,318% | [0,125%; 0,809%] | 3,66 [1,43; 9,32] | — |
| HEPATOPAT + HIPERTENSA | 5–14 | M | — | — | — | — |
| HEPATOPAT + HIPERTENSA | 15–39 | F | 0,584% | [0,370%; 0,922%] | 9,40 [5,97; 14,81] | — |
| HEPATOPAT + HIPERTENSA | 15–39 | M | 0,725% | [0,459%; 1,142%] | 9,40 [5,97; 14,81] | — |
| HEPATOPAT + HIPERTENSA | 40–59 | F | 0,817% | [0,567%; 1,174%] | 10,61 [7,32; 15,37] | — |
| HEPATOPAT + HIPERTENSA | 40–59 | M | 1,012% | [0,703%; 1,455%] | 10,61 [7,32; 15,37] | — |
| HEPATOPAT + HIPERTENSA | 60–79 | F | 2,110% | [1,480%; 3,000%] | 11,07 [7,66; 16,00] | — |
| HEPATOPAT + HIPERTENSA | 60–79 | M | 2,607% | [1,831%; 3,700%] | 11,07 [7,66; 16,00] | — |
| HEPATOPAT + HIPERTENSA | 80+ | F | 4,780% | [3,379%; 6,721%] | 11,48 [7,93; 16,63] | — |
| HEPATOPAT + HIPERTENSA | 80+ | M | 5,869% | [4,162%; 8,216%] | 11,48 [7,93; 16,63] | — |
| HEPATOPAT + ACIDO_PEPT | — | — | dados insuficientes | — | — | — |
| HEPATOPAT + AUTO_IMUNE | — | — | dados insuficientes | — | — | — |
| RENAL + HIPERTENSA | 0–4 | F | 0,463% | [0,111%; 1,913%] | 2,82 [0,67; 11,86] | — |
| RENAL + HIPERTENSA | 0–4 | M | — | — | — | — |
| RENAL + HIPERTENSA | 5–14 | F | 0,454% | [0,184%; 1,118%] | 5,22 [2,11; 12,92] | — |
| RENAL + HIPERTENSA | 5–14 | M | 0,563% | [0,228%; 1,384%] | 5,22 [2,11; 12,92] | — |
| RENAL + HIPERTENSA | 15–39 | F | 0,833% | [0,568%; 1,218%] | 13,44 [9,21; 19,61] | — |
| RENAL + HIPERTENSA | 15–39 | M | 1,032% | [0,705%; 1,508%] | 13,44 [9,21; 19,61] | — |
| RENAL + HIPERTENSA | 40–59 | F | 1,163% | [0,892%; 1,513%] | 15,16 [11,56; 19,89] | — |
| RENAL + HIPERTENSA | 40–59 | M | 1,440% | [1,107%; 1,872%] | 15,16 [11,56; 19,89] | — |
| RENAL + HIPERTENSA | 60–79 | F | 2,987% | [2,334%; 3,817%] | 15,82 [12,16; 20,57] | — |
| RENAL + HIPERTENSA | 60–79 | M | 3,684% | [2,885%; 4,694%] | 15,82 [12,16; 20,57] | — |
| RENAL + HIPERTENSA | 80+ | F | 6,692% | [5,297%; 8,421%] | 16,41 [12,64; 21,29] | — |
| RENAL + HIPERTENSA | 80+ | M | 8,179% | [6,499%; 10,246%] | 16,41 [12,64; 21,29] | — |
| RENAL + ACIDO_PEPT | — | — | dados insuficientes | — | — | — |
| RENAL + AUTO_IMUNE | 0–4 | F | — | — | — | — |
| RENAL + AUTO_IMUNE | 0–4 | M | — | — | — | — |
| RENAL + AUTO_IMUNE | 5–14 | F | — | — | — | — |
| RENAL + AUTO_IMUNE | 5–14 | M | — | — | — | — |
| RENAL + AUTO_IMUNE | 15–39 | F | 2,261% | [1,209%; 4,190%] | 37,02 [19,70; 69,57] | — |
| RENAL + AUTO_IMUNE | 15–39 | M | 2,793% | [1,497%; 5,152%] | 37,02 [19,70; 69,57] | — |
| RENAL + AUTO_IMUNE | 40–59 | F | 2,792% | [1,504%; 5,127%] | 37,02 [19,70; 69,57] | — |
| RENAL + AUTO_IMUNE | 40–59 | M | 3,445% | [1,861%; 6,293%] | 37,02 [19,70; 69,57] | — |
| RENAL + AUTO_IMUNE | 60–79 | F | — | — | — | — |
| RENAL + AUTO_IMUNE | 60–79 | M | — | — | — | — |
| RENAL + AUTO_IMUNE | 80+ | F | — | — | — | — |
| RENAL + AUTO_IMUNE | 80+ | M | — | — | — | — |
| HIPERTENSA + ACIDO_PEPT | 0–4 | F | 0,050% | [0,011%; 0,227%] | 0,31 [0,07; 1,38] | — |
| HIPERTENSA + ACIDO_PEPT | 0–4 | M | 0,063% | [0,014%; 0,282%] | 0,31 [0,07; 1,38] | — |
| HIPERTENSA + ACIDO_PEPT | 5–14 | F | 0,049% | [0,018%; 0,137%] | 0,57 [0,20; 1,57] | — |
| HIPERTENSA + ACIDO_PEPT | 5–14 | M | 0,061% | [0,022%; 0,170%] | 0,57 [0,20; 1,57] | — |
| HIPERTENSA + ACIDO_PEPT | 15–39 | F | 0,091% | [0,049%; 0,168%] | 1,46 [0,79; 2,69] | — |
| HIPERTENSA + ACIDO_PEPT | 15–39 | M | 0,113% | [0,061%; 0,209%] | 1,46 [0,79; 2,69] | — |
| HIPERTENSA + ACIDO_PEPT | 40–59 | F | 0,127% | [0,073%; 0,222%] | 1,64 [0,94; 2,88] | — |
| HIPERTENSA + ACIDO_PEPT | 40–59 | M | 0,158% | [0,090%; 0,276%] | 1,64 [0,94; 2,88] | — |
| HIPERTENSA + ACIDO_PEPT | 60–79 | F | 0,333% | [0,191%; 0,578%] | 1,71 [0,98; 3,00] | — |
| HIPERTENSA + ACIDO_PEPT | 60–79 | M | 0,413% | [0,237%; 0,717%] | 1,71 [0,98; 3,00] | — |
| HIPERTENSA + ACIDO_PEPT | 80+ | F | 0,771% | [0,444%; 1,335%] | 1,78 [1,02; 3,11] | — |
| HIPERTENSA + ACIDO_PEPT | 80+ | M | 0,956% | [0,551%; 1,654%] | 1,78 [1,02; 3,11] | — |
| HIPERTENSA + AUTO_IMUNE | 0–4 | F | — | — | — | — |
| HIPERTENSA + AUTO_IMUNE | 0–4 | M | — | — | — | — |
| HIPERTENSA + AUTO_IMUNE | 5–14 | F | — | — | — | — |
| HIPERTENSA + AUTO_IMUNE | 5–14 | M | — | — | — | — |
| HIPERTENSA + AUTO_IMUNE | 15–39 | F | 0,250% | [0,150%; 0,415%] | 4,01 [2,42; 6,64] | — |
| HIPERTENSA + AUTO_IMUNE | 15–39 | M | 0,310% | [0,186%; 0,515%] | 4,01 [2,42; 6,64] | — |
| HIPERTENSA + AUTO_IMUNE | 40–59 | F | 0,350% | [0,228%; 0,535%] | 4,52 [2,94; 6,96] | — |
| HIPERTENSA + AUTO_IMUNE | 40–59 | M | 0,434% | [0,283%; 0,665%] | 4,52 [2,94; 6,96] | — |
| HIPERTENSA + AUTO_IMUNE | 60–79 | F | 0,910% | [0,598%; 1,383%] | 4,72 [3,07; 7,25] | — |
| HIPERTENSA + AUTO_IMUNE | 60–79 | M | 1,128% | [0,741%; 1,715%] | 4,72 [3,07; 7,25] | — |
| HIPERTENSA + AUTO_IMUNE | 80+ | F | 2,094% | [1,382%; 3,161%] | 4,89 [3,18; 7,53] | — |
| HIPERTENSA + AUTO_IMUNE | 80+ | M | 2,588% | [1,709%; 3,902%] | 4,89 [3,18; 7,53] | — |
| ACIDO_PEPT + AUTO_IMUNE | — | — | dados insuficientes | — | — | — |

## Grupo 4: Três ou mais comorbidades (75 perfis; 22 com dados insuficientes)

Células suprimidas (R7) neste grupo: 493 de 636.

| Perfil | Faixa etária | Sexo | Risco estimado | IC 95% | Razão vs. "saudável" (mesma faixa e sexo), IC 95% | Aviso | Nota |
|---|---|---|---|---|---|---|---|
| DIABETES + HEMATOLOG + HEPATOPAT | 0–4 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + HEPATOPAT | 0–4 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + HEPATOPAT | 5–14 | F | 0,296% | [0,093%; 0,941%] | 3,40 [1,06; 10,87] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + HEPATOPAT | 5–14 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + HEPATOPAT | 15–39 | F | 0,400% | [0,164%; 0,977%] | 6,43 [2,63; 15,74] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + HEPATOPAT | 15–39 | M | 0,497% | [0,203%; 1,210%] | 6,43 [2,63; 15,74] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + HEPATOPAT | 40–59 | F | 0,548% | [0,235%; 1,274%] | 7,10 [3,03; 16,65] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + HEPATOPAT | 40–59 | M | 0,680% | [0,291%; 1,578%] | 7,10 [3,03; 16,65] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + HEPATOPAT | 60–79 | F | 1,192% | [0,510%; 2,762%] | 6,20 [2,63; 14,62] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + HEPATOPAT | 60–79 | M | 1,476% | [0,633%; 3,407%] | 6,20 [2,63; 14,62] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + HEPATOPAT | 80+ | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + HEPATOPAT | 80+ | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + RENAL | 0–4 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + RENAL | 0–4 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + RENAL | 5–14 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + RENAL | 5–14 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + RENAL | 15–39 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + RENAL | 15–39 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + RENAL | 40–59 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + RENAL | 40–59 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + RENAL | 60–79 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + RENAL | 60–79 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + RENAL | 80+ | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + RENAL | 80+ | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + RENAL | 0–4 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + RENAL | 0–4 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + RENAL | 5–14 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + RENAL | 5–14 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + RENAL | 15–39 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + RENAL | 15–39 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + RENAL | 40–59 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + RENAL | 40–59 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + RENAL | 60–79 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + RENAL | 60–79 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + RENAL | 80+ | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + RENAL | 80+ | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + RENAL | 0–4 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + RENAL | 0–4 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + RENAL | 5–14 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + RENAL | 5–14 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + RENAL | 15–39 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + RENAL | 15–39 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + RENAL | 40–59 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + RENAL | 40–59 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + RENAL | 60–79 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + RENAL | 60–79 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + RENAL | 80+ | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + RENAL | 80+ | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + HEPATOPAT + RENAL | 0–4 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HEPATOPAT + RENAL | 0–4 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HEPATOPAT + RENAL | 5–14 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HEPATOPAT + RENAL | 5–14 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HEPATOPAT + RENAL | 15–39 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HEPATOPAT + RENAL | 15–39 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HEPATOPAT + RENAL | 40–59 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HEPATOPAT + RENAL | 40–59 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HEPATOPAT + RENAL | 60–79 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HEPATOPAT + RENAL | 60–79 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HEPATOPAT + RENAL | 80+ | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HEPATOPAT + RENAL | 80+ | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HIPERTENSA | 0–4 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + HIPERTENSA | 0–4 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + HIPERTENSA | 5–14 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + HIPERTENSA | 5–14 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + HIPERTENSA | 15–39 | F | 0,478% | [0,251%; 0,910%] | 7,69 [4,03; 14,68] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + HIPERTENSA | 15–39 | M | 0,593% | [0,311%; 1,128%] | 7,69 [4,03; 14,68] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + HIPERTENSA | 40–59 | F | 0,737% | [0,442%; 1,229%] | 9,57 [5,70; 16,08] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + HIPERTENSA | 40–59 | M | 0,914% | [0,548%; 1,523%] | 9,57 [5,70; 16,08] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + HIPERTENSA | 60–79 | F | 1,669% | [1,012%; 2,740%] | 8,72 [5,22; 14,55] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + HIPERTENSA | 60–79 | M | 2,064% | [1,253%; 3,384%] | 8,72 [5,22; 14,55] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + HIPERTENSA | 80+ | F | 3,408% | [2,084%; 5,525%] | 8,07 [4,84; 13,47] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + HIPERTENSA | 80+ | M | 4,198% | [2,573%; 6,777%] | 8,07 [4,84; 13,47] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + HIPERTENSA | 0–4 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + HIPERTENSA | 0–4 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + HIPERTENSA | 5–14 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + HIPERTENSA | 5–14 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + HIPERTENSA | 15–39 | F | 0,651% | [0,364%; 1,161%] | 10,48 [5,85; 18,77] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + HIPERTENSA | 15–39 | M | 0,807% | [0,451%; 1,439%] | 10,48 [5,85; 18,77] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + HIPERTENSA | 40–59 | F | 1,003% | [0,658%; 1,526%] | 13,05 [8,50; 20,05] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + HIPERTENSA | 40–59 | M | 1,242% | [0,815%; 1,890%] | 13,05 [8,50; 20,05] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + HIPERTENSA | 60–79 | F | 2,261% | [1,502%; 3,391%] | 11,88 [7,78; 18,15] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + HIPERTENSA | 60–79 | M | 2,794% | [1,859%; 4,179%] | 11,88 [7,78; 18,15] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + HIPERTENSA | 80+ | F | 4,589% | [3,067%; 6,812%] | 11,00 [7,18; 16,86] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + HIPERTENSA | 80+ | M | 5,637% | [3,781%; 8,327%] | 11,00 [7,18; 16,86] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + HIPERTENSA | 0–4 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + HIPERTENSA | 0–4 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + HIPERTENSA | 5–14 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + HIPERTENSA | 5–14 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + HIPERTENSA | 15–39 | F | 0,384% | [0,166%; 0,888%] | 6,17 [2,67; 14,29] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + HIPERTENSA | 15–39 | M | 0,477% | [0,206%; 1,100%] | 6,17 [2,67; 14,29] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + HIPERTENSA | 40–59 | F | 0,537% | [0,242%; 1,190%] | 6,96 [3,12; 15,54] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + HIPERTENSA | 40–59 | M | 0,667% | [0,300%; 1,474%] | 6,96 [3,12; 15,54] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + HIPERTENSA | 60–79 | F | 1,395% | [0,632%; 3,049%] | 7,26 [3,26; 16,20] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + HIPERTENSA | 60–79 | M | 1,726% | [0,784%; 3,760%] | 7,26 [3,26; 16,20] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + HIPERTENSA | 80+ | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + HIPERTENSA | 80+ | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + HEPATOPAT + HIPERTENSA | 0–4 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HEPATOPAT + HIPERTENSA | 0–4 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HEPATOPAT + HIPERTENSA | 5–14 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HEPATOPAT + HIPERTENSA | 5–14 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HEPATOPAT + HIPERTENSA | 15–39 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HEPATOPAT + HIPERTENSA | 15–39 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HEPATOPAT + HIPERTENSA | 40–59 | F | 0,320% | [0,137%; 0,749%] | 4,14 [1,76; 9,73] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HEPATOPAT + HIPERTENSA | 40–59 | M | 0,397% | [0,170%; 0,928%] | 4,14 [1,76; 9,73] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HEPATOPAT + HIPERTENSA | 60–79 | F | 0,728% | [0,312%; 1,690%] | 3,77 [1,60; 8,85] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HEPATOPAT + HIPERTENSA | 60–79 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HEPATOPAT + HIPERTENSA | 80+ | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HEPATOPAT + HIPERTENSA | 80+ | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + RENAL + HIPERTENSA | 0–4 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + RENAL + HIPERTENSA | 0–4 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + RENAL + HIPERTENSA | 5–14 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + RENAL + HIPERTENSA | 5–14 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + RENAL + HIPERTENSA | 15–39 | F | 1,424% | [0,873%; 2,317%] | 23,13 [14,11; 37,91] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + RENAL + HIPERTENSA | 15–39 | M | 1,763% | [1,081%; 2,862%] | 23,13 [14,11; 37,91] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + RENAL + HIPERTENSA | 40–59 | F | 2,186% | [1,680%; 2,841%] | 28,80 [21,89; 37,90] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + RENAL + HIPERTENSA | 40–59 | M | 2,701% | [2,077%; 3,505%] | 28,80 [21,89; 37,90] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + RENAL + HIPERTENSA | 60–79 | F | 4,857% | [3,864%; 6,089%] | 26,22 [20,42; 33,67] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + RENAL + HIPERTENSA | 60–79 | M | 5,963% | [4,756%; 7,452%] | 26,22 [20,42; 33,67] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + RENAL + HIPERTENSA | 80+ | F | 9,594% | [7,728%; 11,853%] | 24,28 [18,91; 31,17] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + RENAL + HIPERTENSA | 80+ | M | 11,646% | [9,425%; 14,309%] | 24,28 [18,91; 31,17] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + RENAL + HIPERTENSA | 0–4 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + RENAL + HIPERTENSA | 0–4 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + RENAL + HIPERTENSA | 5–14 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + RENAL + HIPERTENSA | 5–14 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + RENAL + HIPERTENSA | 15–39 | F | 0,380% | [0,160%; 0,900%] | 6,10 [2,57; 14,49] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + RENAL + HIPERTENSA | 15–39 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + RENAL + HIPERTENSA | 40–59 | F | 0,531% | [0,233%; 1,208%] | 6,88 [3,00; 15,77] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + RENAL + HIPERTENSA | 40–59 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + RENAL + HIPERTENSA | 60–79 | F | 1,378% | [0,609%; 3,090%] | 7,18 [3,14; 16,43] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + RENAL + HIPERTENSA | 60–79 | M | 1,706% | [0,755%; 3,810%] | 7,18 [3,14; 16,43] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + RENAL + HIPERTENSA | 80+ | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + RENAL + HIPERTENSA | 80+ | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + RENAL + HIPERTENSA | 0–4 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + RENAL + HIPERTENSA | 0–4 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + RENAL + HIPERTENSA | 5–14 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + RENAL + HIPERTENSA | 5–14 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + RENAL + HIPERTENSA | 15–39 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + RENAL + HIPERTENSA | 15–39 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + RENAL + HIPERTENSA | 40–59 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + RENAL + HIPERTENSA | 40–59 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + RENAL + HIPERTENSA | 60–79 | F | 1,107% | [0,470%; 2,585%] | 5,75 [2,42; 13,66] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + RENAL + HIPERTENSA | 60–79 | M | 1,371% | [0,583%; 3,192%] | 5,75 [2,42; 13,66] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + RENAL + HIPERTENSA | 80+ | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + RENAL + HIPERTENSA | 80+ | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEPATOPAT + RENAL + HIPERTENSA | 0–4 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + RENAL + HIPERTENSA | 0–4 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + RENAL + HIPERTENSA | 5–14 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + RENAL + HIPERTENSA | 5–14 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + RENAL + HIPERTENSA | 15–39 | F | 1,317% | [0,637%; 2,703%] | 21,36 [10,30; 44,32] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + RENAL + HIPERTENSA | 15–39 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + RENAL + HIPERTENSA | 40–59 | F | 1,836% | [0,938%; 3,562%] | 24,10 [12,19; 47,66] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + RENAL + HIPERTENSA | 40–59 | M | 2,270% | [1,162%; 4,386%] | 24,10 [12,19; 47,66] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + RENAL + HIPERTENSA | 60–79 | F | 4,667% | [2,429%; 8,781%] | 25,14 [12,74; 49,63] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + RENAL + HIPERTENSA | 60–79 | M | 5,732% | [3,000%; 10,679%] | 25,14 [12,74; 49,63] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + RENAL + HIPERTENSA | 80+ | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + RENAL + HIPERTENSA | 80+ | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + RENAL + HIPERTENSA | 0–4 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + RENAL + HIPERTENSA | 0–4 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + RENAL + HIPERTENSA | 5–14 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + RENAL + HIPERTENSA | 5–14 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + RENAL + HIPERTENSA | 15–39 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + RENAL + HIPERTENSA | 15–39 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + RENAL + HIPERTENSA | 40–59 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + RENAL + HIPERTENSA | 40–59 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + RENAL + HIPERTENSA | 60–79 | F | 4,692% | [2,476%; 8,715%] | 25,29 [13,00; 49,20] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + RENAL + HIPERTENSA | 60–79 | M | 5,763% | [3,057%; 10,602%] | 25,29 [13,00; 49,20] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + RENAL + HIPERTENSA | 80+ | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + RENAL + HIPERTENSA | 80+ | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + RENAL + HIPERTENSA | 0–4 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + RENAL + HIPERTENSA | 0–4 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + RENAL + HIPERTENSA | 5–14 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + RENAL + HIPERTENSA | 5–14 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + RENAL + HIPERTENSA | 15–39 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + RENAL + HIPERTENSA | 15–39 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + RENAL + HIPERTENSA | 40–59 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + RENAL + HIPERTENSA | 40–59 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + RENAL + HIPERTENSA | 60–79 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + RENAL + HIPERTENSA | 60–79 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + RENAL + HIPERTENSA | 80+ | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + RENAL + HIPERTENSA | 80+ | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HEPATOPAT + RENAL + HIPERTENSA | — | — | dados insuficientes (5+ comorbidades: poucos eventos; extrapolação instável do E1) | — | — | depende do padrão suspeito (ver sensibilidade) | — |
| DIABETES + HEMATOLOG + ACIDO_PEPT | 0–4 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + ACIDO_PEPT | 0–4 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + ACIDO_PEPT | 5–14 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + ACIDO_PEPT | 5–14 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + ACIDO_PEPT | 15–39 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + ACIDO_PEPT | 15–39 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + ACIDO_PEPT | 40–59 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + ACIDO_PEPT | 40–59 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + ACIDO_PEPT | 60–79 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + ACIDO_PEPT | 60–79 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + ACIDO_PEPT | 80+ | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + ACIDO_PEPT | 80+ | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + ACIDO_PEPT | 0–4 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + ACIDO_PEPT | 0–4 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + ACIDO_PEPT | 5–14 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + ACIDO_PEPT | 5–14 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + ACIDO_PEPT | 15–39 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + ACIDO_PEPT | 15–39 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + ACIDO_PEPT | 40–59 | F | 0,476% | [0,240%; 0,941%] | 6,16 [3,10; 12,26] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + ACIDO_PEPT | 40–59 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + ACIDO_PEPT | 60–79 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + ACIDO_PEPT | 60–79 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + ACIDO_PEPT | 80+ | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + ACIDO_PEPT | 80+ | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + ACIDO_PEPT | 0–4 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + ACIDO_PEPT | 0–4 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + ACIDO_PEPT | 5–14 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + ACIDO_PEPT | 5–14 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + ACIDO_PEPT | 15–39 | F | 0,360% | [0,156%; 0,827%] | 5,78 [2,51; 13,29] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + ACIDO_PEPT | 15–39 | M | 0,447% | [0,194%; 1,025%] | 5,78 [2,51; 13,29] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + ACIDO_PEPT | 40–59 | F | 0,446% | [0,194%; 1,022%] | 5,78 [2,51; 13,29] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + ACIDO_PEPT | 40–59 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + ACIDO_PEPT | 60–79 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + ACIDO_PEPT | 60–79 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + ACIDO_PEPT | 80+ | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + ACIDO_PEPT | 80+ | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + HEPATOPAT + ACIDO_PEPT | 0–4 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HEPATOPAT + ACIDO_PEPT | 0–4 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HEPATOPAT + ACIDO_PEPT | 5–14 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HEPATOPAT + ACIDO_PEPT | 5–14 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HEPATOPAT + ACIDO_PEPT | 15–39 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HEPATOPAT + ACIDO_PEPT | 15–39 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HEPATOPAT + ACIDO_PEPT | 40–59 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HEPATOPAT + ACIDO_PEPT | 40–59 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HEPATOPAT + ACIDO_PEPT | 60–79 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HEPATOPAT + ACIDO_PEPT | 60–79 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HEPATOPAT + ACIDO_PEPT | 80+ | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HEPATOPAT + ACIDO_PEPT | 80+ | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + RENAL + ACIDO_PEPT | 0–4 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + RENAL + ACIDO_PEPT | 0–4 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + RENAL + ACIDO_PEPT | 5–14 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + RENAL + ACIDO_PEPT | 5–14 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + RENAL + ACIDO_PEPT | 15–39 | F | 0,743% | [0,369%; 1,489%] | 11,98 [5,96; 24,09] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + RENAL + ACIDO_PEPT | 15–39 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + RENAL + ACIDO_PEPT | 40–59 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + RENAL + ACIDO_PEPT | 40–59 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + RENAL + ACIDO_PEPT | 60–79 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + RENAL + ACIDO_PEPT | 60–79 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + RENAL + ACIDO_PEPT | 80+ | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + RENAL + ACIDO_PEPT | 80+ | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + RENAL + ACIDO_PEPT | 0–4 | F | 0,907% | [0,419%; 1,951%] | 5,56 [2,58; 11,99] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + RENAL + ACIDO_PEPT | 0–4 | M | 1,124% | [0,520%; 2,411%] | 5,56 [2,58; 11,99] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + RENAL + ACIDO_PEPT | 5–14 | F | 0,483% | [0,224%; 1,040%] | 5,56 [2,58; 11,99] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + RENAL + ACIDO_PEPT | 5–14 | M | 0,599% | [0,278%; 1,288%] | 5,56 [2,58; 11,99] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + RENAL + ACIDO_PEPT | 15–39 | F | 0,346% | [0,160%; 0,747%] | 5,56 [2,58; 11,99] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + RENAL + ACIDO_PEPT | 15–39 | M | 0,429% | [0,199%; 0,926%] | 5,56 [2,58; 11,99] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + RENAL + ACIDO_PEPT | 40–59 | F | 0,429% | [0,199%; 0,923%] | 5,56 [2,58; 11,99] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + RENAL + ACIDO_PEPT | 40–59 | M | 0,533% | [0,247%; 1,144%] | 5,56 [2,58; 11,99] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + RENAL + ACIDO_PEPT | 60–79 | F | 1,070% | [0,499%; 2,283%] | 5,56 [2,58; 11,99] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + RENAL + ACIDO_PEPT | 60–79 | M | 1,326% | [0,618%; 2,820%] | 5,56 [2,58; 11,99] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + RENAL + ACIDO_PEPT | 80+ | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + RENAL + ACIDO_PEPT | 80+ | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + RENAL + ACIDO_PEPT | 0–4 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + RENAL + ACIDO_PEPT | 0–4 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + RENAL + ACIDO_PEPT | 5–14 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + RENAL + ACIDO_PEPT | 5–14 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + RENAL + ACIDO_PEPT | 15–39 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + RENAL + ACIDO_PEPT | 15–39 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + RENAL + ACIDO_PEPT | 40–59 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + RENAL + ACIDO_PEPT | 40–59 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + RENAL + ACIDO_PEPT | 60–79 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + RENAL + ACIDO_PEPT | 60–79 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + RENAL + ACIDO_PEPT | 80+ | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + RENAL + ACIDO_PEPT | 80+ | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEPATOPAT + RENAL + ACIDO_PEPT | 0–4 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + RENAL + ACIDO_PEPT | 0–4 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + RENAL + ACIDO_PEPT | 5–14 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + RENAL + ACIDO_PEPT | 5–14 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + RENAL + ACIDO_PEPT | 15–39 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + RENAL + ACIDO_PEPT | 15–39 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + RENAL + ACIDO_PEPT | 40–59 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + RENAL + ACIDO_PEPT | 40–59 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + RENAL + ACIDO_PEPT | 60–79 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + RENAL + ACIDO_PEPT | 60–79 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + RENAL + ACIDO_PEPT | 80+ | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + RENAL + ACIDO_PEPT | 80+ | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + RENAL + ACIDO_PEPT | 0–4 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + RENAL + ACIDO_PEPT | 0–4 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + RENAL + ACIDO_PEPT | 5–14 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + RENAL + ACIDO_PEPT | 5–14 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + RENAL + ACIDO_PEPT | 15–39 | F | 0,884% | [0,357%; 2,170%] | 14,28 [5,76; 35,41] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + RENAL + ACIDO_PEPT | 15–39 | M | 1,096% | [0,444%; 2,681%] | 14,28 [5,76; 35,41] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + RENAL + ACIDO_PEPT | 40–59 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + RENAL + ACIDO_PEPT | 40–59 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + RENAL + ACIDO_PEPT | 60–79 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + RENAL + ACIDO_PEPT | 60–79 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + RENAL + ACIDO_PEPT | 80+ | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + RENAL + ACIDO_PEPT | 80+ | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + RENAL + ACIDO_PEPT | 0–4 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + RENAL + ACIDO_PEPT | 0–4 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + RENAL + ACIDO_PEPT | 5–14 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + RENAL + ACIDO_PEPT | 5–14 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + RENAL + ACIDO_PEPT | 15–39 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + RENAL + ACIDO_PEPT | 15–39 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + RENAL + ACIDO_PEPT | 40–59 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + RENAL + ACIDO_PEPT | 40–59 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + RENAL + ACIDO_PEPT | 60–79 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + RENAL + ACIDO_PEPT | 60–79 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + RENAL + ACIDO_PEPT | 80+ | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + RENAL + ACIDO_PEPT | 80+ | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HIPERTENSA + ACIDO_PEPT | 0–4 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HIPERTENSA + ACIDO_PEPT | 0–4 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HIPERTENSA + ACIDO_PEPT | 5–14 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HIPERTENSA + ACIDO_PEPT | 5–14 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HIPERTENSA + ACIDO_PEPT | 15–39 | F | 0,167% | [0,083%; 0,334%] | 2,68 [1,33; 5,36] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HIPERTENSA + ACIDO_PEPT | 15–39 | M | 0,207% | [0,103%; 0,415%] | 2,68 [1,33; 5,36] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HIPERTENSA + ACIDO_PEPT | 40–59 | F | 0,258% | [0,147%; 0,453%] | 3,33 [1,89; 5,89] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HIPERTENSA + ACIDO_PEPT | 40–59 | M | 0,320% | [0,182%; 0,563%] | 3,33 [1,89; 5,89] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HIPERTENSA + ACIDO_PEPT | 60–79 | F | 0,587% | [0,337%; 1,020%] | 3,03 [1,73; 5,33] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HIPERTENSA + ACIDO_PEPT | 60–79 | M | 0,728% | [0,418%; 1,265%] | 3,03 [1,73; 5,33] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HIPERTENSA + ACIDO_PEPT | 80+ | F | 1,213% | [0,698%; 2,100%] | 2,81 [1,60; 4,94] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HIPERTENSA + ACIDO_PEPT | 80+ | M | 1,502% | [0,865%; 2,597%] | 2,81 [1,60; 4,94] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HIPERTENSA + ACIDO_PEPT | 0–4 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HIPERTENSA + ACIDO_PEPT | 0–4 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HIPERTENSA + ACIDO_PEPT | 5–14 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HIPERTENSA + ACIDO_PEPT | 5–14 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HIPERTENSA + ACIDO_PEPT | 15–39 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HIPERTENSA + ACIDO_PEPT | 15–39 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HIPERTENSA + ACIDO_PEPT | 40–59 | F | 0,462% | [0,239%; 0,892%] | 5,99 [3,08; 11,63] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HIPERTENSA + ACIDO_PEPT | 40–59 | M | 0,574% | [0,297%; 1,106%] | 5,99 [3,08; 11,63] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HIPERTENSA + ACIDO_PEPT | 60–79 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HIPERTENSA + ACIDO_PEPT | 60–79 | M | 1,488% | [0,775%; 2,838%] | 6,25 [3,22; 12,13] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HIPERTENSA + ACIDO_PEPT | 80+ | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HIPERTENSA + ACIDO_PEPT | 80+ | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + HIPERTENSA + ACIDO_PEPT | 0–4 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HIPERTENSA + ACIDO_PEPT | 0–4 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HIPERTENSA + ACIDO_PEPT | 5–14 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HIPERTENSA + ACIDO_PEPT | 5–14 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HIPERTENSA + ACIDO_PEPT | 15–39 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HIPERTENSA + ACIDO_PEPT | 15–39 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HIPERTENSA + ACIDO_PEPT | 40–59 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HIPERTENSA + ACIDO_PEPT | 40–59 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HIPERTENSA + ACIDO_PEPT | 60–79 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HIPERTENSA + ACIDO_PEPT | 60–79 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HIPERTENSA + ACIDO_PEPT | 80+ | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HIPERTENSA + ACIDO_PEPT | 80+ | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEPATOPAT + HIPERTENSA + ACIDO_PEPT | 0–4 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + HIPERTENSA + ACIDO_PEPT | 0–4 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + HIPERTENSA + ACIDO_PEPT | 5–14 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + HIPERTENSA + ACIDO_PEPT | 5–14 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + HIPERTENSA + ACIDO_PEPT | 15–39 | F | 0,359% | [0,181%; 0,710%] | 5,76 [2,91; 11,40] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + HIPERTENSA + ACIDO_PEPT | 15–39 | M | 0,445% | [0,225%; 0,880%] | 5,76 [2,91; 11,40] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + HIPERTENSA + ACIDO_PEPT | 40–59 | F | 0,502% | [0,267%; 0,942%] | 6,50 [3,44; 12,29] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + HIPERTENSA + ACIDO_PEPT | 40–59 | M | 0,623% | [0,331%; 1,168%] | 6,50 [3,44; 12,29] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + HIPERTENSA + ACIDO_PEPT | 60–79 | F | 1,303% | [0,697%; 2,425%] | 6,78 [3,59; 12,83] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + HIPERTENSA + ACIDO_PEPT | 60–79 | M | 1,614% | [0,864%; 2,995%] | 6,78 [3,59; 12,83] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + HIPERTENSA + ACIDO_PEPT | 80+ | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + HIPERTENSA + ACIDO_PEPT | 80+ | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + HIPERTENSA + ACIDO_PEPT | 0–4 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + HIPERTENSA + ACIDO_PEPT | 0–4 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + HIPERTENSA + ACIDO_PEPT | 5–14 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + HIPERTENSA + ACIDO_PEPT | 5–14 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + HIPERTENSA + ACIDO_PEPT | 15–39 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + HIPERTENSA + ACIDO_PEPT | 15–39 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + HIPERTENSA + ACIDO_PEPT | 40–59 | F | 0,617% | [0,316%; 1,201%] | 8,00 [4,07; 15,70] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + HIPERTENSA + ACIDO_PEPT | 40–59 | M | 0,765% | [0,392%; 1,488%] | 8,00 [4,07; 15,70] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + HIPERTENSA + ACIDO_PEPT | 60–79 | F | 1,398% | [0,722%; 2,690%] | 7,28 [3,72; 14,27] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + HIPERTENSA + ACIDO_PEPT | 60–79 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + HIPERTENSA + ACIDO_PEPT | 80+ | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + HIPERTENSA + ACIDO_PEPT | 80+ | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + HIPERTENSA + ACIDO_PEPT | 0–4 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + HIPERTENSA + ACIDO_PEPT | 0–4 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + HIPERTENSA + ACIDO_PEPT | 5–14 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + HIPERTENSA + ACIDO_PEPT | 5–14 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + HIPERTENSA + ACIDO_PEPT | 15–39 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + HIPERTENSA + ACIDO_PEPT | 15–39 | M | 0,293% | [0,113%; 0,758%] | 3,78 [1,46; 9,82] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + HIPERTENSA + ACIDO_PEPT | 40–59 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + HIPERTENSA + ACIDO_PEPT | 40–59 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + HIPERTENSA + ACIDO_PEPT | 60–79 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + HIPERTENSA + ACIDO_PEPT | 60–79 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + HIPERTENSA + ACIDO_PEPT | 80+ | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + HIPERTENSA + ACIDO_PEPT | 80+ | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HEPATOPAT + HIPERTENSA + ACIDO_PEPT | — | — | dados insuficientes (5+ comorbidades: poucos eventos; extrapolação instável do E1) | — | — | depende do padrão suspeito (ver sensibilidade) | — |
| RENAL + HIPERTENSA + ACIDO_PEPT | 0–4 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| RENAL + HIPERTENSA + ACIDO_PEPT | 0–4 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| RENAL + HIPERTENSA + ACIDO_PEPT | 5–14 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| RENAL + HIPERTENSA + ACIDO_PEPT | 5–14 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| RENAL + HIPERTENSA + ACIDO_PEPT | 15–39 | F | 0,512% | [0,268%; 0,976%] | 8,23 [4,31; 15,72] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| RENAL + HIPERTENSA + ACIDO_PEPT | 15–39 | M | 0,635% | [0,332%; 1,210%] | 8,23 [4,31; 15,72] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| RENAL + HIPERTENSA + ACIDO_PEPT | 40–59 | F | 0,715% | [0,395%; 1,291%] | 9,29 [5,11; 16,89] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| RENAL + HIPERTENSA + ACIDO_PEPT | 40–59 | M | 0,887% | [0,491%; 1,599%] | 9,29 [5,11; 16,89] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| RENAL + HIPERTENSA + ACIDO_PEPT | 60–79 | F | 1,852% | [1,033%; 3,296%] | 9,69 [5,34; 17,59] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| RENAL + HIPERTENSA + ACIDO_PEPT | 60–79 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| RENAL + HIPERTENSA + ACIDO_PEPT | 80+ | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| RENAL + HIPERTENSA + ACIDO_PEPT | 80+ | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + RENAL + HIPERTENSA + ACIDO_PEPT | 0–4 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + RENAL + HIPERTENSA + ACIDO_PEPT | 0–4 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + RENAL + HIPERTENSA + ACIDO_PEPT | 5–14 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + RENAL + HIPERTENSA + ACIDO_PEPT | 5–14 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + RENAL + HIPERTENSA + ACIDO_PEPT | 15–39 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + RENAL + HIPERTENSA + ACIDO_PEPT | 15–39 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + RENAL + HIPERTENSA + ACIDO_PEPT | 40–59 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + RENAL + HIPERTENSA + ACIDO_PEPT | 40–59 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + RENAL + HIPERTENSA + ACIDO_PEPT | 60–79 | F | 3,033% | [1,709%; 5,327%] | 16,06 [8,88; 29,05] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + RENAL + HIPERTENSA + ACIDO_PEPT | 60–79 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + RENAL + HIPERTENSA + ACIDO_PEPT | 80+ | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + RENAL + HIPERTENSA + ACIDO_PEPT | 80+ | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + RENAL + HIPERTENSA + ACIDO_PEPT | 0–4 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + RENAL + HIPERTENSA + ACIDO_PEPT | 0–4 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + RENAL + HIPERTENSA + ACIDO_PEPT | 5–14 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + RENAL + HIPERTENSA + ACIDO_PEPT | 5–14 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + RENAL + HIPERTENSA + ACIDO_PEPT | 15–39 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + RENAL + HIPERTENSA + ACIDO_PEPT | 15–39 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + RENAL + HIPERTENSA + ACIDO_PEPT | 40–59 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + RENAL + HIPERTENSA + ACIDO_PEPT | 40–59 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + RENAL + HIPERTENSA + ACIDO_PEPT | 60–79 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + RENAL + HIPERTENSA + ACIDO_PEPT | 60–79 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + RENAL + HIPERTENSA + ACIDO_PEPT | 80+ | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + RENAL + HIPERTENSA + ACIDO_PEPT | 80+ | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + RENAL + HIPERTENSA + ACIDO_PEPT | — | — | dados insuficientes (5+ comorbidades: poucos eventos; extrapolação instável do E1) | — | — | depende do padrão suspeito (ver sensibilidade) | — |
| DIABETES + HEPATOPAT + RENAL + HIPERTENSA + ACIDO_PEPT | — | — | dados insuficientes (5+ comorbidades: poucos eventos; extrapolação instável do E1) | — | — | — | — |
| HEMATOLOG + HEPATOPAT + RENAL + HIPERTENSA + ACIDO_PEPT | — | — | dados insuficientes (5+ comorbidades: poucos eventos; extrapolação instável do E1) | — | — | depende do padrão suspeito (ver sensibilidade) | — |
| DIABETES + HEMATOLOG + HEPATOPAT + RENAL + HIPERTENSA + ACIDO_PEPT | — | — | dados insuficientes (5+ comorbidades: poucos eventos; extrapolação instável do E1) | — | — | depende do padrão suspeito (ver sensibilidade) | — |
| DIABETES + HEMATOLOG + AUTO_IMUNE | 0–4 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + AUTO_IMUNE | 0–4 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + AUTO_IMUNE | 5–14 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + AUTO_IMUNE | 5–14 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + AUTO_IMUNE | 15–39 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + AUTO_IMUNE | 15–39 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + AUTO_IMUNE | 40–59 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + AUTO_IMUNE | 40–59 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + AUTO_IMUNE | 60–79 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + AUTO_IMUNE | 60–79 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + AUTO_IMUNE | 80+ | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + AUTO_IMUNE | 80+ | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + AUTO_IMUNE | 0–4 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + AUTO_IMUNE | 0–4 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + AUTO_IMUNE | 5–14 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + AUTO_IMUNE | 5–14 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + AUTO_IMUNE | 15–39 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + AUTO_IMUNE | 15–39 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + AUTO_IMUNE | 40–59 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + AUTO_IMUNE | 40–59 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + AUTO_IMUNE | 60–79 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + AUTO_IMUNE | 60–79 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + AUTO_IMUNE | 80+ | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + AUTO_IMUNE | 80+ | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + AUTO_IMUNE | 0–4 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + AUTO_IMUNE | 0–4 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + AUTO_IMUNE | 5–14 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + AUTO_IMUNE | 5–14 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + AUTO_IMUNE | 15–39 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + AUTO_IMUNE | 15–39 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + AUTO_IMUNE | 40–59 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + AUTO_IMUNE | 40–59 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + AUTO_IMUNE | 60–79 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + AUTO_IMUNE | 60–79 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + AUTO_IMUNE | 80+ | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HEPATOPAT + AUTO_IMUNE | 80+ | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + RENAL + AUTO_IMUNE | 0–4 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + RENAL + AUTO_IMUNE | 0–4 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + RENAL + AUTO_IMUNE | 5–14 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + RENAL + AUTO_IMUNE | 5–14 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + RENAL + AUTO_IMUNE | 15–39 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + RENAL + AUTO_IMUNE | 15–39 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + RENAL + AUTO_IMUNE | 40–59 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + RENAL + AUTO_IMUNE | 40–59 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + RENAL + AUTO_IMUNE | 60–79 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + RENAL + AUTO_IMUNE | 60–79 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + RENAL + AUTO_IMUNE | 80+ | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + RENAL + AUTO_IMUNE | 80+ | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + RENAL + AUTO_IMUNE | 0–4 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + RENAL + AUTO_IMUNE | 0–4 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + RENAL + AUTO_IMUNE | 5–14 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + RENAL + AUTO_IMUNE | 5–14 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + RENAL + AUTO_IMUNE | 15–39 | F | 1,752% | [0,771%; 3,929%] | 28,54 [12,50; 65,15] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + RENAL + AUTO_IMUNE | 15–39 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + RENAL + AUTO_IMUNE | 40–59 | F | 2,166% | [0,960%; 4,817%] | 28,54 [12,50; 65,15] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + RENAL + AUTO_IMUNE | 40–59 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + RENAL + AUTO_IMUNE | 60–79 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + RENAL + AUTO_IMUNE | 60–79 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + RENAL + AUTO_IMUNE | 80+ | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + RENAL + AUTO_IMUNE | 80+ | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HIPERTENSA + AUTO_IMUNE | 0–4 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HIPERTENSA + AUTO_IMUNE | 0–4 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HIPERTENSA + AUTO_IMUNE | 5–14 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HIPERTENSA + AUTO_IMUNE | 5–14 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HIPERTENSA + AUTO_IMUNE | 15–39 | F | 0,158% | [0,079%; 0,316%] | 2,53 [1,26; 5,07] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HIPERTENSA + AUTO_IMUNE | 15–39 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HIPERTENSA + AUTO_IMUNE | 40–59 | F | 0,244% | [0,136%; 0,435%] | 3,15 [1,76; 5,65] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HIPERTENSA + AUTO_IMUNE | 40–59 | M | 0,303% | [0,169%; 0,540%] | 3,15 [1,76; 5,65] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HIPERTENSA + AUTO_IMUNE | 60–79 | F | 0,555% | [0,313%; 0,984%] | 2,87 [1,60; 5,13] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HIPERTENSA + AUTO_IMUNE | 60–79 | M | 0,689% | [0,388%; 1,220%] | 2,87 [1,60; 5,13] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HIPERTENSA + AUTO_IMUNE | 80+ | F | 1,147% | [0,649%; 2,020%] | 2,66 [1,48; 4,75] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HIPERTENSA + AUTO_IMUNE | 80+ | M | 1,421% | [0,804%; 2,499%] | 2,66 [1,48; 4,75] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HIPERTENSA + AUTO_IMUNE | 0–4 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HIPERTENSA + AUTO_IMUNE | 0–4 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HIPERTENSA + AUTO_IMUNE | 5–14 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HIPERTENSA + AUTO_IMUNE | 5–14 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HIPERTENSA + AUTO_IMUNE | 15–39 | F | 0,602% | [0,268%; 1,346%] | 9,69 [4,32; 21,76] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HIPERTENSA + AUTO_IMUNE | 15–39 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HIPERTENSA + AUTO_IMUNE | 40–59 | F | 0,841% | [0,391%; 1,799%] | 10,93 [5,06; 23,65] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HIPERTENSA + AUTO_IMUNE | 40–59 | M | 1,043% | [0,485%; 2,226%] | 10,93 [5,06; 23,65] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HIPERTENSA + AUTO_IMUNE | 60–79 | F | 2,173% | [1,021%; 4,566%] | 11,41 [5,28; 24,65] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HIPERTENSA + AUTO_IMUNE | 60–79 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HIPERTENSA + AUTO_IMUNE | 80+ | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + HIPERTENSA + AUTO_IMUNE | 80+ | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEMATOLOG + HIPERTENSA + AUTO_IMUNE | 0–4 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HIPERTENSA + AUTO_IMUNE | 0–4 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HIPERTENSA + AUTO_IMUNE | 5–14 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HIPERTENSA + AUTO_IMUNE | 5–14 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HIPERTENSA + AUTO_IMUNE | 15–39 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HIPERTENSA + AUTO_IMUNE | 15–39 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HIPERTENSA + AUTO_IMUNE | 40–59 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HIPERTENSA + AUTO_IMUNE | 40–59 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HIPERTENSA + AUTO_IMUNE | 60–79 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HIPERTENSA + AUTO_IMUNE | 60–79 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HIPERTENSA + AUTO_IMUNE | 80+ | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HIPERTENSA + AUTO_IMUNE | 80+ | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEPATOPAT + HIPERTENSA + AUTO_IMUNE | 0–4 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + HIPERTENSA + AUTO_IMUNE | 0–4 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + HIPERTENSA + AUTO_IMUNE | 5–14 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + HIPERTENSA + AUTO_IMUNE | 5–14 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + HIPERTENSA + AUTO_IMUNE | 15–39 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + HIPERTENSA + AUTO_IMUNE | 15–39 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + HIPERTENSA + AUTO_IMUNE | 40–59 | F | 1,369% | [0,815%; 2,290%] | 17,89 [10,55; 30,32] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + HIPERTENSA + AUTO_IMUNE | 40–59 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + HIPERTENSA + AUTO_IMUNE | 60–79 | F | 3,506% | [2,113%; 5,763%] | 18,66 [11,02; 31,62] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + HIPERTENSA + AUTO_IMUNE | 60–79 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + HIPERTENSA + AUTO_IMUNE | 80+ | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEPATOPAT + HIPERTENSA + AUTO_IMUNE | 80+ | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HEPATOPAT + HIPERTENSA + AUTO_IMUNE | 0–4 | F | 0,075% | [0,011%; 0,512%] | 0,45 [0,07; 3,14] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + HIPERTENSA + AUTO_IMUNE | 0–4 | M | 0,093% | [0,013%; 0,635%] | 0,45 [0,07; 3,14] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + HIPERTENSA + AUTO_IMUNE | 5–14 | F | 0,109% | [0,031%; 0,387%] | 1,25 [0,35; 4,46] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + HIPERTENSA + AUTO_IMUNE | 5–14 | M | 0,135% | [0,038%; 0,481%] | 1,25 [0,35; 4,46] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + HIPERTENSA + AUTO_IMUNE | 15–39 | F | 0,378% | [0,186%; 0,768%] | 6,07 [2,98; 12,36] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + HIPERTENSA + AUTO_IMUNE | 15–39 | M | 0,469% | [0,230%; 0,952%] | 6,07 [2,98; 12,36] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + HIPERTENSA + AUTO_IMUNE | 40–59 | F | 0,583% | [0,317%; 1,069%] | 7,56 [4,09; 13,97] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + HIPERTENSA + AUTO_IMUNE | 40–59 | M | 0,723% | [0,394%; 1,325%] | 7,56 [4,09; 13,97] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + HIPERTENSA + AUTO_IMUNE | 60–79 | F | 1,322% | [0,723%; 2,405%] | 6,88 [3,72; 12,72] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + HIPERTENSA + AUTO_IMUNE | 60–79 | M | 1,637% | [0,897%; 2,971%] | 6,88 [3,72; 12,72] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + HIPERTENSA + AUTO_IMUNE | 80+ | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + HIPERTENSA + AUTO_IMUNE | 80+ | M | 3,344% | [1,848%; 5,978%] | 6,37 [3,45; 11,78] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + HIPERTENSA + AUTO_IMUNE | 0–4 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + HIPERTENSA + AUTO_IMUNE | 0–4 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + HIPERTENSA + AUTO_IMUNE | 5–14 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + HIPERTENSA + AUTO_IMUNE | 5–14 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + HIPERTENSA + AUTO_IMUNE | 15–39 | F | 0,430% | [0,157%; 1,169%] | 6,91 [2,53; 18,88] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + HIPERTENSA + AUTO_IMUNE | 15–39 | M | 0,533% | [0,195%; 1,449%] | 6,91 [2,53; 18,88] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + HIPERTENSA + AUTO_IMUNE | 40–59 | F | 0,601% | [0,227%; 1,581%] | 7,79 [2,93; 20,72] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + HIPERTENSA + AUTO_IMUNE | 40–59 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + HIPERTENSA + AUTO_IMUNE | 60–79 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + HIPERTENSA + AUTO_IMUNE | 60–79 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + HIPERTENSA + AUTO_IMUNE | 80+ | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + HEPATOPAT + HIPERTENSA + AUTO_IMUNE | 80+ | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + HEPATOPAT + HIPERTENSA + AUTO_IMUNE | — | — | dados insuficientes (5+ comorbidades: poucos eventos; extrapolação instável do E1) | — | — | depende do padrão suspeito (ver sensibilidade) | — |
| RENAL + HIPERTENSA + AUTO_IMUNE | 0–4 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| RENAL + HIPERTENSA + AUTO_IMUNE | 0–4 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| RENAL + HIPERTENSA + AUTO_IMUNE | 5–14 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| RENAL + HIPERTENSA + AUTO_IMUNE | 5–14 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| RENAL + HIPERTENSA + AUTO_IMUNE | 15–39 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| RENAL + HIPERTENSA + AUTO_IMUNE | 15–39 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| RENAL + HIPERTENSA + AUTO_IMUNE | 40–59 | F | 2,104% | [1,091%; 4,020%] | 27,70 [14,20; 54,06] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| RENAL + HIPERTENSA + AUTO_IMUNE | 40–59 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| RENAL + HIPERTENSA + AUTO_IMUNE | 60–79 | F | 5,328% | [2,818%; 9,847%] | 28,90 [14,84; 56,29] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| RENAL + HIPERTENSA + AUTO_IMUNE | 60–79 | M | 6,533% | [3,476%; 11,948%] | 28,90 [14,84; 56,29] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| RENAL + HIPERTENSA + AUTO_IMUNE | 80+ | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| RENAL + HIPERTENSA + AUTO_IMUNE | 80+ | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + RENAL + HIPERTENSA + AUTO_IMUNE | 0–4 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + RENAL + HIPERTENSA + AUTO_IMUNE | 0–4 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + RENAL + HIPERTENSA + AUTO_IMUNE | 5–14 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + RENAL + HIPERTENSA + AUTO_IMUNE | 5–14 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + RENAL + HIPERTENSA + AUTO_IMUNE | 15–39 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + RENAL + HIPERTENSA + AUTO_IMUNE | 15–39 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + RENAL + HIPERTENSA + AUTO_IMUNE | 40–59 | F | 1,384% | [0,662%; 2,871%] | 18,08 [8,57; 38,14] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + RENAL + HIPERTENSA + AUTO_IMUNE | 40–59 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + RENAL + HIPERTENSA + AUTO_IMUNE | 60–79 | F | 3,105% | [1,507%; 6,290%] | 16,46 [7,84; 34,57] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + RENAL + HIPERTENSA + AUTO_IMUNE | 60–79 | M | 3,828% | [1,865%; 7,695%] | 16,46 [7,84; 34,57] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + RENAL + HIPERTENSA + AUTO_IMUNE | 80+ | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + RENAL + HIPERTENSA + AUTO_IMUNE | 80+ | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + RENAL + HIPERTENSA + AUTO_IMUNE | 0–4 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + RENAL + HIPERTENSA + AUTO_IMUNE | 0–4 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + RENAL + HIPERTENSA + AUTO_IMUNE | 5–14 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + RENAL + HIPERTENSA + AUTO_IMUNE | 5–14 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + RENAL + HIPERTENSA + AUTO_IMUNE | 15–39 | F | 0,460% | [0,171%; 1,228%] | 7,40 [2,76; 19,83] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + RENAL + HIPERTENSA + AUTO_IMUNE | 15–39 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + RENAL + HIPERTENSA + AUTO_IMUNE | 40–59 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + RENAL + HIPERTENSA + AUTO_IMUNE | 40–59 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + RENAL + HIPERTENSA + AUTO_IMUNE | 60–79 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + RENAL + HIPERTENSA + AUTO_IMUNE | 60–79 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + RENAL + HIPERTENSA + AUTO_IMUNE | 80+ | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + RENAL + HIPERTENSA + AUTO_IMUNE | 80+ | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + RENAL + HIPERTENSA + AUTO_IMUNE | — | — | dados insuficientes (5+ comorbidades: poucos eventos; extrapolação instável do E1) | — | — | depende do padrão suspeito (ver sensibilidade) | — |
| HEMATOLOG + HEPATOPAT + RENAL + HIPERTENSA + AUTO_IMUNE | — | — | dados insuficientes (5+ comorbidades: poucos eventos; extrapolação instável do E1) | — | — | depende do padrão suspeito (ver sensibilidade) | — |
| DIABETES + HEMATOLOG + HEPATOPAT + RENAL + HIPERTENSA + AUTO_IMUNE | — | — | dados insuficientes (5+ comorbidades: poucos eventos; extrapolação instável do E1) | — | — | depende do padrão suspeito (ver sensibilidade) | — |
| DIABETES + ACIDO_PEPT + AUTO_IMUNE | 0–4 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + ACIDO_PEPT + AUTO_IMUNE | 0–4 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + ACIDO_PEPT + AUTO_IMUNE | 5–14 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + ACIDO_PEPT + AUTO_IMUNE | 5–14 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + ACIDO_PEPT + AUTO_IMUNE | 15–39 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + ACIDO_PEPT + AUTO_IMUNE | 15–39 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + ACIDO_PEPT + AUTO_IMUNE | 40–59 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + ACIDO_PEPT + AUTO_IMUNE | 40–59 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + ACIDO_PEPT + AUTO_IMUNE | 60–79 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + ACIDO_PEPT + AUTO_IMUNE | 60–79 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + ACIDO_PEPT + AUTO_IMUNE | 80+ | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + ACIDO_PEPT + AUTO_IMUNE | 80+ | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HEMATOLOG + RENAL + ACIDO_PEPT + AUTO_IMUNE | 0–4 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + RENAL + ACIDO_PEPT + AUTO_IMUNE | 0–4 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + RENAL + ACIDO_PEPT + AUTO_IMUNE | 5–14 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + RENAL + ACIDO_PEPT + AUTO_IMUNE | 5–14 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + RENAL + ACIDO_PEPT + AUTO_IMUNE | 15–39 | F | 1,239% | [0,535%; 2,842%] | 20,08 [8,65; 46,62] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + RENAL + ACIDO_PEPT + AUTO_IMUNE | 15–39 | M | 1,534% | [0,664%; 3,507%] | 20,08 [8,65; 46,62] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + RENAL + ACIDO_PEPT + AUTO_IMUNE | 40–59 | F | 1,534% | [0,666%; 3,494%] | 20,08 [8,65; 46,62] | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + RENAL + ACIDO_PEPT + AUTO_IMUNE | 40–59 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + RENAL + ACIDO_PEPT + AUTO_IMUNE | 60–79 | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + RENAL + ACIDO_PEPT + AUTO_IMUNE | 60–79 | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + RENAL + ACIDO_PEPT + AUTO_IMUNE | 80+ | F | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + RENAL + ACIDO_PEPT + AUTO_IMUNE | 80+ | M | — | — | — | depende do padrão suspeito (ver sensibilidade) | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEMATOLOG + RENAL + ACIDO_PEPT + AUTO_IMUNE | — | — | dados insuficientes (5+ comorbidades: poucos eventos; extrapolação instável do E1) | — | — | depende do padrão suspeito (ver sensibilidade) | — |
| DIABETES + HEPATOPAT + RENAL + ACIDO_PEPT + AUTO_IMUNE | — | — | dados insuficientes (5+ comorbidades: poucos eventos; extrapolação instável do E1) | — | — | — | — |
| HEMATOLOG + HEPATOPAT + RENAL + ACIDO_PEPT + AUTO_IMUNE | — | — | dados insuficientes (5+ comorbidades: poucos eventos; extrapolação instável do E1) | — | — | depende do padrão suspeito (ver sensibilidade) | — |
| DIABETES + HEMATOLOG + HEPATOPAT + RENAL + ACIDO_PEPT + AUTO_IMUNE | — | — | dados insuficientes (5+ comorbidades: poucos eventos; extrapolação instável do E1) | — | — | depende do padrão suspeito (ver sensibilidade) | — |
| HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | 0–4 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | 0–4 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | 5–14 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | 5–14 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | 15–39 | F | 0,153% | [0,074%; 0,316%] | 2,46 [1,19; 5,06] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | 15–39 | M | 0,190% | [0,092%; 0,392%] | 2,46 [1,19; 5,06] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | 40–59 | F | 0,214% | [0,109%; 0,421%] | 2,77 [1,40; 5,46] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | 40–59 | M | 0,266% | [0,135%; 0,523%] | 2,77 [1,40; 5,46] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | 60–79 | F | 0,560% | [0,286%; 1,093%] | 2,89 [1,46; 5,70] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | 60–79 | M | 0,694% | [0,354%; 1,355%] | 2,89 [1,46; 5,70] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | 80+ | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | 80+ | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para o trio |
| DIABETES + HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | 0–4 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | 0–4 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | 5–14 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | 5–14 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | 15–39 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | 15–39 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | 40–59 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | 40–59 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | 60–79 | F | 0,341% | [0,156%; 0,742%] | 1,76 [0,80; 3,86] | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | 60–79 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | 80+ | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | 80+ | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| DIABETES + HEPATOPAT + HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | — | — | dados insuficientes (5+ comorbidades: poucos eventos; extrapolação instável do E1) | — | — | — | — |
| DIABETES + HEMATOLOG + HEPATOPAT + HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | — | — | dados insuficientes (5+ comorbidades: poucos eventos; extrapolação instável do E1) | — | — | depende do padrão suspeito (ver sensibilidade) | — |
| RENAL + HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | 0–4 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| RENAL + HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | 0–4 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| RENAL + HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | 5–14 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| RENAL + HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | 5–14 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| RENAL + HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | 15–39 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| RENAL + HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | 15–39 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| RENAL + HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | 40–59 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| RENAL + HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | 40–59 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| RENAL + HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | 60–79 | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| RENAL + HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | 60–79 | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| RENAL + HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | 80+ | F | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| RENAL + HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | 80+ | M | — | — | — | — | risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo próprio para a combinação |
| HEMATOLOG + RENAL + HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | — | — | dados insuficientes (5+ comorbidades: poucos eventos; extrapolação instável do E1) | — | — | depende do padrão suspeito (ver sensibilidade) | — |
| DIABETES + HEMATOLOG + RENAL + HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | — | — | dados insuficientes (5+ comorbidades: poucos eventos; extrapolação instável do E1) | — | — | depende do padrão suspeito (ver sensibilidade) | — |
| HEPATOPAT + RENAL + HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | — | — | dados insuficientes (5+ comorbidades: poucos eventos; extrapolação instável do E1) | — | — | — | — |
| DIABETES + HEPATOPAT + RENAL + HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | — | — | dados insuficientes (5+ comorbidades: poucos eventos; extrapolação instável do E1) | — | — | — | — |
| HEMATOLOG + HEPATOPAT + RENAL + HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | — | — | dados insuficientes (5+ comorbidades: poucos eventos; extrapolação instável do E1) | — | — | depende do padrão suspeito (ver sensibilidade) | — |
| DIABETES + HEMATOLOG + HEPATOPAT + RENAL + HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE | — | — | dados insuficientes (5+ comorbidades: poucos eventos; extrapolação instável do E1) | — | — | depende do padrão suspeito (ver sensibilidade) | — |

