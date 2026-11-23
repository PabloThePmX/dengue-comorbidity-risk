# Avaliação final no teste: avaliação única em 2024 (R2)

Avaliação única em 2024 (R2). Este arquivo é o resultado do teste: não há nova avaliação com o mesmo lacre. Só agregados (R7); células de 1 a 9 aparecem como <10.

## Dados

- Casos: 5331745; eventos: 11338 (prevalência 0,213%).

Alertas de qualidade FR-03 disparados (valor < 10 aparece como <10):

- 2024: DT_SIN_PRI > DT_NOTIFIC: 0
- 2024: gestante com sexo M: 15
- 2024: ignorado > 50% em DIABETES, por UF e ano: 0
- 2024: ignorado > 50% em HEMATOLOG, por UF e ano: 0
- 2024: ignorado > 50% em HEPATOPAT, por UF e ano: 0
- 2024: ignorado > 50% em RENAL, por UF e ano: 0
- 2024: ignorado > 50% em HIPERTENSA, por UF e ano: 0
- 2024: ignorado > 50% em ACIDO_PEPT, por UF e ano: 0
- 2024: ignorado > 50% em AUTO_IMUNE, por UF e ano: 0

## Métricas de probabilidade (IC 95% por bootstrap)

| Modelo | PR-AUC | ROC-AUC | Brier | Calibration slope | Intercepto | Obs/esp |
|---|---|---|---|---|---|---|
| M1 | 0,034627 (0,032455; 0,037152) | 0,8338 (0,8295; 0,8376) | 0,002086 (0,002083; 0,002088) | 0,945 (0,933; 0,955) | 0,270 (0,267; 0,273) | 1,301 (1,297; 1,305) |
| B0 | 0,002127 (0,002127; 0,002127) | 0,5000 (0,5000; 0,5000) | 0,002122 (0,002122; 0,002122) | não definido (previsão constante) | 0,270 (0,270; 0,270) | 1,309 (1,309; 1,309) |
| B1 | 0,016561 (0,015569; 0,017734) | 0,7156 (0,7096; 0,7211) | 0,002108 (0,002107; 0,002109) | 0,998 (0,980; 1,014) | 0,173 (0,172; 0,175) | 1,188 (1,186; 1,189) |
| E1 | 0,021973 (0,020490; 0,023624) | 0,7322 (0,7261; 0,7378) | 0,002101 (0,002099; 0,002103) | 0,960 (0,946; 0,974) | 0,174 (0,172; 0,176) | 1,187 (1,184; 1,189) |

## Métricas no limiar (IC 95%)

| Modelo | Limiar | Acurácia | Precisão | Recall | F1 | F2 | Alertas | Eventos capturados |
|---|---|---|---|---|---|---|---|---|
| M1 | 0,002155 | 0,8583 (0,8580; 0,8586) | 0,00975 (0,00963; 0,00989) | 0,6528 (0,6444; 0,6618) | 0,01922 (0,01897; 0,01948) | 0,04601 (0,04543; 0,04664) | 759006 | 7402 |
| B0 | 0,001529 | 0,0021 (0,0021; 0,0021) | 0,00213 (0,00213; 0,00213) | 1,0000 (1,0000; 1,0000) | 0,00424 (0,00424; 0,00424) | 0,01054 (0,01054; 0,01054) | 5331745 | 11338 |
| B1 | 0,001140 | 0,6449 (0,6445; 0,6454) | 0,00402 (0,00397; 0,00407) | 0,6730 (0,6644; 0,6816) | 0,00800 (0,00789; 0,00810) | 0,01964 (0,01939; 0,01990) | 1896960 | 7630 |
| B2 | 0,500000 | 0,7355 (0,7351; 0,7358) | 0,00529 (0,00522; 0,00536) | 0,6601 (0,6510; 0,6687) | 0,01050 (0,01035; 0,01064) | 0,02564 (0,02528; 0,02598) | 1414081 | 7484 |

## Diferença de PR-AUC (pareada, mesmos sorteios)

| Comparação | Diferença (IC 95%) |
|---|---|
| M1 − B0 | 0,032500 (0,030328; 0,035026) |
| M1 − B1 | 0,018066 (0,016330; 0,020070) |

Calibration slope de B0 não é definido: a previsão é a mesma para todos os casos. E1 é inferência (associação): não tem limiar, só métricas de probabilidade.


## Curva de decisão (net benefit, D-39)

Limiares de risco de 0,1% a 5,0% (50 pontos), com banda de IC 95% por bootstrap (1000 reamostras estratificadas por alvo, os mesmos sorteios para M1, B1 e a regra B2). M1 usa a probabilidade calibrada; B1, a predição bruta como risco. A regra B2 é uma decisão binária: tem as mesmas contagens de VP e FP em todo limiar. “Tratar todos” não tem banda porque a prevalência é fixa na reamostra estratificada.

Net benefit em alguns limiares (a curva inteira está em `metricas.json` e no CSV):

| Limiar | NB M1 | NB B1 | NB B2 | NB tratar todos |
|---|---|---|---|---|
| 0,10% | 0,001397 (0,001381; 0,001412) | 0,001080 (0,001063; 0,001097) | 0,001140 (0,001120; 0,001158) | 0,001128 |
| 1,30% | 0,000409 (0,000391; 0,000427) | 0,000218 (0,000202; 0,000233) | -0,002071 (-0,002091; -0,002052) | -0,011017 |
| 2,60% | 0,000219 (0,000204; 0,000233) | 0,000062 (0,000053; 0,000071) | -0,005639 (-0,005660; -0,005619) | -0,024511 |
| 3,80% | 0,000137 (0,000123; 0,000150) | 0,000018 (0,000014; 0,000023) | -0,009017 (-0,009041; -0,008994) | -0,037291 |
| 5,00% | 0,000092 (0,000080; 0,000104) | 0,000005 (0,000003; 0,000007) | -0,012481 (-0,012509; -0,012455) | -0,050393 |

Limiares de operação do M1 marcados na curva:

| Ponto | Limiar | NB (IC 95%) | Fonte do limiar |
|---|---|---|---|
| M1_principal | 0,002155 | 0,001084 (0,001066; 0,001103) | limiar congelado com o modelo (D-92) |
| M1_f2 | 0,021514 | 0,000265 (0,000248; 0,000280) | limiar_f2 do selecao.json (T-4.9) |

O limiar principal é o congelado com o modelo (recall ≥ B2, D-92). O limiar F2 é o ponto secundário (D-33) e vem do `selecao.json` da T-4.9; não é parte do modelo congelado.


## Calibração por caixas, com bandas (D-39)

Caixas por quantis do risco previsto (10 pedidas: com ~11 mil eventos em 5,3 milhões de casos, cada caixa tem, em média, bem mais que os 100 eventos que o spec pede, e as de menor risco ainda ficam perto disso; com mais caixas as de baixo risco teriam banda larga demais). Banda de IC 95% da taxa observada por bootstrap (2000 reamostras, estratificadas por alvo, mesmos sorteios para M1 e E1). Caixas com menos de 100 eventos têm aviso; com 1 a 9 eventos a taxa é suprimida (R7).

### M1

Globais (da avaliação de métricas): slope 0,945 (0,933; 0,955); intercepto 0,270 (0,267; 0,273); observado/esperado 1,301 (1,297; 1,305).

| Caixa | Casos | Eventos | Risco previsto médio | Taxa observada (IC 95%) | Aviso |
|---|---|---|---|---|---|
| C01 | 533136 | 150 | 0,000155 | 0,000281 (0,000240; 0,000324) |  |
| C02 | 533201 | 168 | 0,000212 | 0,000315 (0,000268; 0,000364) |  |
| C03 | 533179 | 210 | 0,000285 | 0,000394 (0,000343; 0,000447) |  |
| C04 | 532403 | 301 | 0,000383 | 0,000565 (0,000505; 0,000628) |  |
| C05 | 533950 | 389 | 0,000501 | 0,000729 (0,000661; 0,000803) |  |
| C06 | 532935 | 471 | 0,000642 | 0,000884 (0,000801; 0,000962) |  |
| C07 | 533406 | 609 | 0,000850 | 0,001142 (0,001056; 0,001230) |  |
| C08 | 533183 | 885 | 0,001241 | 0,001660 (0,001557; 0,001767) |  |
| C09 | 533177 | 1530 | 0,002099 | 0,002870 (0,002739; 0,003003) |  |
| C10 | 533175 | 6625 | 0,009976 | 0,012426 (0,012230; 0,012615) |  |

### E1

Globais (da avaliação de métricas): slope 0,960 (0,946; 0,974); intercepto 0,174 (0,172; 0,176); observado/esperado 1,187 (1,184; 1,189).

| Caixa | Casos | Eventos | Risco previsto médio | Taxa observada (IC 95%) | Aviso |
|---|---|---|---|---|---|
| C01 | 486739 | 565 | 0,000593 | 0,001161 (0,001068; 0,001256) |  |
| C02 | 574097 | 701 | 0,000650 | 0,001221 (0,001127; 0,001303) |  |
| C03 | 532536 | 558 | 0,000708 | 0,001048 (0,000960; 0,001132) |  |
| C04 | 532178 | 447 | 0,000751 | 0,000840 (0,000763; 0,000918) |  |
| C05 | 539404 | 461 | 0,000804 | 0,000855 (0,000779; 0,000927) |  |
| C06 | 532509 | 479 | 0,000868 | 0,000900 (0,000819; 0,000977) |  |
| C07 | 532554 | 554 | 0,000997 | 0,001040 (0,000954; 0,001126) |  |
| C08 | 530713 | 733 | 0,001334 | 0,001381 (0,001285; 0,001483) |  |
| C09 | 537167 | 1252 | 0,002186 | 0,002331 (0,002213; 0,002451) |  |
| C10 | 533848 | 5588 | 0,009003 | 0,010467 (0,010272; 0,010666) |  |


## Subgrupos (D-13, D-48)

> **Associação não é causa; diferenças de notificação não são diferenças de risco.**

Métricas do M1 no limiar principal (0,002155), com IC 95% por bootstrap DENTRO de cada subgrupo (1000 reamostras, estratificadas por alvo, semente do config); recall e precisão da regra B2 no mesmo subgrupo como referência. Subgrupo com menos de 10 eventos sai sem métricas e célula de 1 a 9 aparece como <10 (R7). Aviso de IC largo: os subgrupos que o spec nomeia e todos com menos de 100 eventos.

**Política de reamostras sem convergência (decisão provisória).** Reamostra sem convergência do ajuste do slope: é descartada só para o slope e o intercepto; as demais métricas usam todas as reamostras. As descartadas são contadas e reportadas. Se mais de 5% das reamostras do subgrupo forem descartadas, o IC do slope e do intercepto sai como indisponível. Se o ajuste da amostra do subgrupo não convergir, o ponto estimado também sai como indisponível. (Decisão provisória, a confirmar.)

### Faixa etária

| Subgrupo | Casos | Eventos | Prevalência | PR-AUC M1 (IC) | Recall M1 (IC) | Precisão M1 (IC) | Recall B2 (IC) | Precisão B2 (IC) | Aviso |
|---|---|---|---|---|---|---|---|---|---|
| 0–4 | 163839 | 259 | 0,158% | 0,0119 (0,0074; 0,0246) | 0,618 (0,560; 0,676) | 0,0052 (0,0047; 0,0056) | 0,749 (0,695; 0,799) | 0,0025 (0,0023; 0,0027) |  |
| 5–14 | 641272 | 536 | 0,084% | 0,0082 (0,0050; 0,0148) | 0,405 (0,366; 0,450) | 0,0039 (0,0035; 0,0043) | 0,231 (0,196; 0,267) | 0,0020 (0,0017; 0,0023) |  |
| 15–39 | 2274560 | 2647 | 0,116% | 0,0086 (0,0076; 0,0101) | 0,361 (0,342; 0,379) | 0,0068 (0,0064; 0,0071) | 0,301 (0,283; 0,318) | 0,0026 (0,0025; 0,0028) |  |
| 40–59 | 1457762 | 2380 | 0,163% | 0,0135 (0,0120; 0,0159) | 0,505 (0,485; 0,524) | 0,0072 (0,0070; 0,0075) | 0,488 (0,468; 0,508) | 0,0032 (0,0030; 0,0033) |  |
| 60–79 | 699861 | 3313 | 0,473% | 0,0358 (0,0326; 0,0399) | 0,809 (0,796; 0,822) | 0,0097 (0,0095; 0,0098) | 0,907 (0,897; 0,917) | 0,0059 (0,0058; 0,0060) |  |
| 80+ | 94451 | 2203 | 2,332% | 0,0904 (0,0831; 0,0992) | 0,993 (0,989; 0,996) | 0,0246 (0,0245; 0,0247) | 1,000 (1,000; 1,000) | 0,0233 (0,0233; 0,0233) |  |

Calibração do M1 no subgrupo:

| Subgrupo | Slope (IC) | Intercepto (IC) | Observado/esperado (IC) | Reamostras descartadas |
|---|---|---|---|---|
| 0–4 | 0,862 (0,779; 0,943) | -0,074 (-0,086; -0,062) | 0,929 (0,919; 0,941) | 0 |
| 5–14 | 0,895 (0,829; 0,962) | -0,041 (-0,046; -0,035) | 0,960 (0,955; 0,965) | 0 |
| 15–39 | 0,958 (0,927; 0,985) | 0,444 (0,441; 0,447) | 1,555 (1,551; 1,560) | 0 |
| 40–59 | 1,017 (0,985; 1,048) | 0,322 (0,319; 0,325) | 1,377 (1,372; 1,381) | 0 |
| 60–79 | 0,934 (0,911; 0,957) | 0,233 (0,228; 0,237) | 1,255 (1,248; 1,261) | 0 |
| 80+ | 0,839 (0,802; 0,875) | 0,213 (0,203; 0,222) | 1,220 (1,208; 1,230) | 0 |

### Sexo

| Subgrupo | Casos | Eventos | Prevalência | PR-AUC M1 (IC) | Recall M1 (IC) | Precisão M1 (IC) | Recall B2 (IC) | Precisão B2 (IC) | Aviso |
|---|---|---|---|---|---|---|---|---|---|
| F | 2909965 | 6046 | 0,208% | 0,0285 (0,0259; 0,0316) | 0,618 (0,605; 0,629) | 0,0091 (0,0089; 0,0092) | 0,638 (0,626; 0,650) | 0,0045 (0,0044; 0,0046) |  |
| M | 2415584 | 5285 | 0,219% | 0,0419 (0,0384; 0,0463) | 0,693 (0,681; 0,704) | 0,0106 (0,0104; 0,0108) | 0,685 (0,672; 0,697) | 0,0064 (0,0063; 0,0066) |  |
| I | 6188 | <10 | — | sem métricas | — | — | — | — | IC largo: poucos eventos; sem conclusões (subgrupo com poucos eventos apontado no spec; menos de 100 eventos) |
| em branco | <10 | 0 | 0,000% | sem métricas | — | — | — | — | IC largo: poucos eventos; sem conclusões (subgrupo com poucos eventos apontado no spec; menos de 100 eventos) |

Calibração do M1 no subgrupo:

| Subgrupo | Slope (IC) | Intercepto (IC) | Observado/esperado (IC) | Reamostras descartadas |
|---|---|---|---|---|
| F | 0,918 (0,904; 0,933) | 0,281 (0,277; 0,285) | 1,317 (1,311; 1,322) | 0 |
| M | 0,971 (0,957; 0,986) | 0,258 (0,254; 0,264) | 1,285 (1,279; 1,292) | 0 |

### Gestante

| Subgrupo | Casos | Eventos | Prevalência | PR-AUC M1 (IC) | Recall M1 (IC) | Precisão M1 (IC) | Recall B2 (IC) | Precisão B2 (IC) | Aviso |
|---|---|---|---|---|---|---|---|---|---|
| gestante | 40046 | 102 | 0,255% | 0,0083 (0,0060; 0,0122) | 0,353 (0,274; 0,441) | 0,0090 (0,0068; 0,0113) | 1,000 (1,000; 1,000) | 0,0025 (0,0025; 0,0025) | IC largo: poucos eventos; sem conclusões (subgrupo com poucos eventos apontado no spec) |
| não gestante | 5291699 | 11236 | 0,212% | 0,0349 (0,0329; 0,0374) | 0,656 (0,646; 0,665) | 0,0098 (0,0096; 0,0099) | 0,657 (0,649; 0,666) | 0,0054 (0,0053; 0,0054) |  |

Calibração do M1 no subgrupo:

| Subgrupo | Slope (IC) | Intercepto (IC) | Observado/esperado (IC) | Reamostras descartadas |
|---|---|---|---|---|
| gestante | 0,693 (0,565; 0,810) | 0,872 (0,847; 0,897) | 2,362 (2,303; 2,426) | 0 |
| não gestante | 0,947 (0,937; 0,958) | 0,266 (0,263; 0,269) | 1,296 (1,292; 1,300) | 0 |

### Região de residência

| Subgrupo | Casos | Eventos | Prevalência | PR-AUC M1 (IC) | Recall M1 (IC) | Precisão M1 (IC) | Recall B2 (IC) | Precisão B2 (IC) | Aviso |
|---|---|---|---|---|---|---|---|---|---|
| Sudeste | 3501741 | 6510 | 0,186% | 0,0353 (0,0321; 0,0390) | 0,676 (0,664; 0,687) | 0,0087 (0,0085; 0,0088) | 0,677 (0,666; 0,688) | 0,0048 (0,0048; 0,0049) |  |
| Sul | 1065151 | 2094 | 0,197% | 0,0348 (0,0306; 0,0412) | 0,648 (0,627; 0,667) | 0,0096 (0,0093; 0,0099) | 0,728 (0,708; 0,745) | 0,0047 (0,0046; 0,0048) |  |
| Centro-Oeste | 491446 | 1682 | 0,342% | 0,0485 (0,0423; 0,0575) | 0,644 (0,621; 0,666) | 0,0152 (0,0146; 0,0157) | 0,634 (0,612; 0,656) | 0,0094 (0,0090; 0,0097) |  |
| Nordeste | 227290 | 942 | 0,414% | 0,0265 (0,0221; 0,0327) | 0,531 (0,499; 0,562) | 0,0151 (0,0142; 0,0159) | 0,459 (0,427; 0,490) | 0,0083 (0,0077; 0,0088) |  |
| Norte | 46117 | 110 | 0,239% | 0,0220 (0,0133; 0,0497) | 0,582 (0,491; 0,682) | 0,0101 (0,0086; 0,0119) | 0,509 (0,418; 0,609) | 0,0047 (0,0039; 0,0057) | IC largo: poucos eventos; sem conclusões (subgrupo com poucos eventos apontado no spec) |

Calibração do M1 no subgrupo:

| Subgrupo | Slope (IC) | Intercepto (IC) | Observado/esperado (IC) | Reamostras descartadas |
|---|---|---|---|---|
| Sudeste | 0,967 (0,953; 0,980) | 0,101 (0,097; 0,104) | 1,103 (1,099; 1,107) | 0 |
| Sul | 0,967 (0,944; 0,993) | 0,271 (0,264; 0,278) | 1,303 (1,295; 1,312) | 0 |
| Centro-Oeste | 0,952 (0,923; 0,981) | 0,765 (0,756; 0,775) | 2,101 (2,079; 2,121) | 0 |
| Nordeste | 0,777 (0,737; 0,817) | 1,046 (1,034; 1,058) | 2,763 (2,727; 2,802) | 0 |
| Norte | 0,950 (0,827; 1,067) | 0,550 (0,526; 0,574) | 1,719 (1,679; 1,763) | 0 |

### Raça/cor

| Subgrupo | Casos | Eventos | Prevalência | PR-AUC M1 (IC) | Recall M1 (IC) | Precisão M1 (IC) | Recall B2 (IC) | Precisão B2 (IC) | Aviso |
|---|---|---|---|---|---|---|---|---|---|
| Branca | 2366073 | 5285 | 0,223% | 0,0426 (0,0388; 0,0471) | 0,706 (0,693; 0,718) | 0,0103 (0,0101; 0,0105) | 0,734 (0,722; 0,745) | 0,0055 (0,0054; 0,0056) |  |
| Preta | 262938 | 530 | 0,202% | 0,0366 (0,0274; 0,0521) | 0,638 (0,600; 0,681) | 0,0101 (0,0094; 0,0107) | 0,625 (0,585; 0,668) | 0,0046 (0,0044; 0,0050) |  |
| Amarela | 57208 | 108 | 0,189% | 0,0509 (0,0308; 0,0969) | 0,750 (0,676; 0,824) | 0,0097 (0,0087; 0,0107) | 0,685 (0,583; 0,769) | 0,0048 (0,0041; 0,0054) |  |
| Parda | 1837881 | 3859 | 0,210% | 0,0285 (0,0259; 0,0317) | 0,604 (0,589; 0,619) | 0,0100 (0,0097; 0,0102) | 0,602 (0,586; 0,618) | 0,0053 (0,0052; 0,0054) |  |
| Indígena | 11983 | 30 | 0,250% | 0,0306 (0,0113; 0,0933) | 0,467 (0,300; 0,634) | 0,0094 (0,0060; 0,0131) | 0,600 (0,433; 0,767) | 0,0064 (0,0046; 0,0083) | IC largo: poucos eventos; sem conclusões (menos de 100 eventos) |
| Ignorado/em branco | 795662 | 1526 | 0,192% | 0,0272 (0,0224; 0,0349) | 0,594 (0,569; 0,619) | 0,0075 (0,0072; 0,0078) | 0,563 (0,537; 0,589) | 0,0048 (0,0046; 0,0051) |  |

Calibração do M1 no subgrupo:

| Subgrupo | Slope (IC) | Intercepto (IC) | Observado/esperado (IC) | Reamostras descartadas |
|---|---|---|---|---|
| Branca | 0,980 (0,964; 0,997) | 0,240 (0,235; 0,244) | 1,263 (1,257; 1,268) | 0 |
| Preta | 0,969 (0,921; 1,017) | 0,337 (0,323; 0,350) | 1,391 (1,371; 1,409) | 0 |
| Amarela | 1,003 (0,907; 1,101) | 0,034 (0,001; 0,063) | 1,033 (1,001; 1,063) | 0 |
| Parda | 0,951 (0,933; 0,970) | 0,407 (0,402; 0,412) | 1,490 (1,482; 1,497) | 0 |
| Indígena | 0,835 (0,593; 1,079) | 0,620 (0,557; 0,682) | 1,830 (1,713; 1,953) | 0 |
| Ignorado/em branco | 0,842 (0,812; 0,873) | 0,062 (0,054; 0,070) | 1,062 (1,054; 1,071) | 0 |


## Análise `erros`

O resultado está em `erros.md`.

## Análise `criterios`

O resultado está em `criterios.md`.

---
Gerado pelo pipeline de avaliação (T-5.1). Só agregados; sem linhas individuais (R7).
