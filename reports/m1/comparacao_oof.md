# Comparação dos candidatos e baselines no OOF (T-4.9)

Predições fora da dobra (leave-one-region-out) de 2022–23, com as dobras da T-2.3 e a semente 20261103 do config. Ano de teste não lido (R1). Só agregados (R7): contagem abaixo de 10 aparece como <10.

## 1. PR-AUC por dobra (métrica primária, sobre a predição bruta)

| Modelo | Sudeste | Sul | Centro-Oeste | Nordeste | Norte | Média | IC 95% da média |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| elastic_net | 0,02726 | 0,02799 | 0,03186 | 0,02045 | 0,02561 | 0,02663 | [0,02399; 0,03143] |
| xgboost | 0,03107 | 0,03212 | 0,03151 | 0,02237 | 0,02482 | 0,02838 | [0,02574; 0,03380] |
| catboost | 0,02816 | 0,03082 | 0,02846 | 0,01672 | 0,02204 | 0,02524 | [0,02302; 0,02949] |
| mlp | 0,02821 | 0,03090 | 0,03029 | 0,02089 | 0,02478 | 0,02701 | [0,02464; 0,03188] |
| random_forest | 0,02548 | 0,03535 | 0,02735 | 0,01563 | 0,02300 | 0,02536 | [0,02306; 0,02995] |
| B0 | 0,00149 | 0,00139 | 0,00180 | 0,00255 | 0,00166 | 0,00178 | — |
| B1 | 0,01345 | 0,01763 | 0,01554 | 0,00724 | 0,01026 | 0,01282 | [0,01156; 0,01553] |
| B2 | — | — | — | — | — | — | — |

IC 95% da média: bootstrap pareado com a semente do config (mesmos sorteios para todos os modelos). B2 é regra e não tem PR-AUC.

## 2. Calibração e discriminação (OOF)

Calibrador: escolhido pelo menor Brier fora da dobra. Brier, slope e intercepto dos candidatos são os das predições calibradas com o calibrador reajustado no OOF inteiro (slope e intercepto do calibrado são do próprio OOF, não fora da dobra).

| Modelo | Calibrador | Brier bruto | Brier calibrado (fora da dobra) | Slope | Intercepto | ROC-AUC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| elastic_net | isotonica | 0,001605 | 0,001602 | 1,000 | -0,000 | 0,8301 |
| xgboost | platt | 0,001599 | 0,001599 | 1,011 | 0,005 | 0,8481 |
| catboost | isotonica | 0,001602 | 0,001601 | 1,000 | -0,000 | 0,8418 |
| mlp | platt | 0,001602 | 0,001602 | 1,024 | 0,016 | 0,8390 |
| random_forest | isotonica | 0,001603 | 0,001602 | 1,000 | -0,000 | 0,8389 |
| B0 | — | 0,001622 | — | -3,564 | -0,035 | 0,4629 |
| B1 | — | 0,001613 | — | 1,048 | -0,053 | 0,7109 |
| B2 | — | — | — | — | — | — |

## 3. Métricas no limiar

Limiar principal (D-92): precisão máxima com recall ≥ recall da B2 nas predições do OOF; empate: maior limiar (D-92). Recall de referência (B2 no OOF): 0,6843. Candidatos: predições calibradas do OOF. B0 e B1: o mesmo critério, nas predições brutas. B2: a regra do protocolo, sem limiar.

| Modelo | Limiar | Recall | Precisão | F2 |
| --- | ---: | ---: | ---: | ---: |
| elastic_net | 0,002043 | 0,6946 | 0,0064 | 0,0307 |
| xgboost | 0,002155 | 0,6846 | 0,0075 | 0,0359 |
| catboost | 0,002155 | 0,6989 | 0,0066 | 0,0319 |
| mlp | 0,002122 | 0,6843 | 0,0069 | 0,0333 |
| random_forest | 0,002001 | 0,7235 | 0,0059 | 0,0284 |
| B0 | 0,001529 | 1,0000 | 0,0016 | 0,0081 |
| B1 | 0,001140 | 0,6843 | 0,0029 | 0,0142 |
| B2 | regra | 0,6843 | 0,0042 | 0,0206 |

### 3.1 Ponto F2 (secundário, D-33)

Máximo de F2 nas mesmas predições. Reportado para comparação; não entra no modelo congelado.

| Modelo | Limiar F2 | Recall | Precisão | F2 |
| --- | ---: | ---: | ---: | ---: |
| elastic_net | 0,024537 | 0,1880 | 0,0422 | 0,1112 |
| xgboost | 0,021514 | 0,2068 | 0,0433 | 0,1178 |
| catboost | 0,025905 | 0,2018 | 0,0415 | 0,1139 |
| mlp | 0,018786 | 0,2078 | 0,0386 | 0,1107 |
| random_forest | 0,027273 | 0,1752 | 0,0464 | 0,1126 |
| B0 | 0,001529 | 1,0000 | 0,0016 | 0,0081 |
| B1 | 0,014346 | 0,1483 | 0,0266 | 0,0774 |
| B2 | regra | 0,6843 | 0,0042 | 0,0206 |

## 4. Busca de hiperparâmetros (cronometragem, orçamento e tentativas)

| Modelo | Cronometragem (min) | Orçamento (min) | Subamostra | Tentativas concluídas | Podadas | Falhas |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| elastic_net | 18,46 | 20,00 | sim | 3 | 1 | 0 |
| xgboost | 1,14 | 30,00 | não | 14 | 16 | 0 |
| catboost | 8,59 | 40,00 | não | 5 | 2 | 0 |
| mlp | 7,01 | 40,00 | não | 5 | 3 | 0 |
| random_forest | 3,11 | 40,00 | não | 5 | 1 | 0 |

## 5. Eventos por dobra (contexto, R7)

Sudeste: 1 736; Sul: 810; Centro-Oeste: 736; Nordeste: 582; Norte: 121

## 6. Seleção

**Vencedor: xgboost.** maior PR-AUC média: xgboost (0,02838); empatados pela regra (diferença < 0,005 ou ICs sobrepostos): xgboost, mlp, elastic_net, random_forest, catboost; desempate por menor Brier calibrado fora da dobra.

- Calibrador do vencedor: platt (menor Brier fora da dobra).
- Limiar (precisão máxima com recall ≥ 0,6843 da B2, predições calibradas do OOF; empate: maior limiar): 0,002155.
- Ponto F2 (secundário, não entra no modelo): 0,021514.
- A comparação pareada (`comparacao_pareada.md`) é só reportada (D-53).
