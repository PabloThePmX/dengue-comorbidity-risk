# Resultados do profiling — SINAN Dengue 2022–2024

> Gerado automaticamente por `profiling/01_profiling.ipynb` em 2026-11-03 04:21 UTC (Colab). Não edite à mão: rode o notebook de novo.
> "Dentro do esperado?" = `sim`/`não` quando a regra é objetiva; `revisar` quando depende de julgamento.

## Resumo

| # | Item | Seção do spec | Resultado (número ou achado) | Dentro do esperado? | Observação |
|---|---|---|---|---|---|
| 0 | Hash, data e versão de cada Parquet | §3.14 | 2022: 1,405,095 linhas, final; 2023: 1,645,956 linhas, final; 2024: 6,564,924 linhas, final | sim | Linhas lidas = cabeçalho do DBF. |
| 1 | Valores de CLASSI_FIN/EVOLUCAO/CRITERIO por ano | §3.6 | 2022: CLASSI_FIN ∈ {0, 10, 11, 12, 8}; 2023: CLASSI_FIN ∈ {0, 10, 11, 12, 8}; 2024: CLASSI_FIN ∈ {10, 11, 12, 8} | sim | 10/11/12 presentes e 1/2 ausentes; D-02 vale. |
| 2 | Fluxograma de exclusão | §3.6, FR-02 | 2022: 1,405,095 → 1,148,299; 2023: 1,645,956 → 1,304,909; 2024: 6,564,924 → 5,331,745 | revisar | Conferir motivos de saída no detalhe. |
| 3a | Prevalência de y por ano | §3.7 | 2022: 0.16% (1,869 eventos); 2023: 0.16% (2,116 eventos); 2024: 0.21% (11,338 eventos) | revisar |  |
| 3b | Eventos por região (2022–23) | §3.8 | mín. 121 eventos | sim | Todas as regiões com ≥ 100 eventos. |
| 3c | Eventos por subgrupo (2024) | §3.8, §3.12 | 2 subgrupo(s) com < 100 eventos | não | sexo=<branco>, sexo=I |
| 4a | Valores das comorbidades | §3.7 | DIABETES: 0.0% ausente na população final | revisar | Valores fora de 1/2: 9 |
| 4b | % ausente × y (vazamento) | §3.8 | razão y0/y1 entre 0.28 e 0.59 | sim | Nenhuma comorbidade com razão > 2. |
| 5 | Idade: decodificação e faixa | §3.7, §3.9 | 100.0% concordam com ANO_NASC (±1 ano); 340 fora de [0, 120]; 11,673 códigos inválidos; 11,571 recuperadas por ANO_NASC; 442 sem idade | sim | Idade inválida usa ano dos sintomas − ANO_NASC (D-50). |
| 6 | Demografia e inconsistências | §3.7 | gestante com sexo M: 19; raça ignorada/branco: 2022 20%, 2023 17%, 2024 16% | revisar | Ver Q-05 (raça/escolaridade). |
| 7a | Sinais clínicos: % ausente | §3.8 | entre 1.7% e 4.0% | revisar |  |
| 7b | ALRM_* preenchido por CLASSI_FIN | §3.6 | algum ALRM_* preenchido: 3.3% em CLASSI_FIN=10, 99.8% em 11 | sim | Preenchimento revela a classe: restrição de M2 a 11/12 necessária. |
| 8 | Atraso sintomas → notificação | §3.9 | 2022: mediana 3 d, p99 61 d, 14,377 > 60 d; 2023: mediana 3 d, p99 38 d, 8,474 > 60 d; 2024: mediana 3 d, p99 52 d, 52,045 > 60 d | revisar | Ver também ano da data × ano do arquivo. |
| 9 | Duplicatas | §3.6 | 2022: 17.28% em grupo duplicado; 2023: 21.06% em grupo duplicado; 2024: 42.40% em grupo duplicado | revisar | 25,079 linhas em grupos com desfecho conflitante → Q-04. Chave sem DT_NASC (mais fraca). |
| 10 | Cobertura do ES | §3.7 | 2022: ES 236 vs mediana vizinhos 132 /100 mil; 2023: ES 2855 vs mediana vizinhos 237 /100 mil; 2024: ES 3053 vs mediana vizinhos 1419 /100 mil | revisar | População: IBGE, Censo 2022 (SIDRA 4709). |
| 11 | RAM e tamanho do DataFrame | NFR-01 | RAM 12.7 GiB; DataFrame 0.46 GiB (Colab) | sim |  |

## 0. Manifesto dos dados

| index | 2022 | 2023 | 2024 |
|---|---|---|---|
| arquivo | DENGBR22.dbc | DENGBR23.dbc | DENGBR24.dbc |
| status no DataSUS | final | final | final |
| revisão no DataSUS (UTC) | 2026-03-19T18:03:00 | 2026-03-17T11:35:00 | 2026-02-27T14:06:00 |
| baixado em (UTC) | 2026-11-03T04:01:26 | 2026-11-03T04:01:32 | 2026-11-03T04:01:37 |
| linhas | 1 405 095 | 1 645 956 | 6 564 924 |
| linhas no cabeçalho DBF | 1 405 095 | 1 645 956 | 6 564 924 |
| colunas | 121 | 121 | 121 |
| SHA-256 .dbc | 1a5a3a1be0d63c8b… | c0e7f95ef832c097… | cd66ee77271a9718… |
| SHA-256 Parquet | 95e860f78a9d3b75… | 5cb9928289d5b0e1… | 8ffbbcd8ec5dd4a9… |

Hashes completos em `data/manifest.json`. Ambiente: python 3.13.16, pyreaddbc 2.0.4, dbfread 2.0.7, pyarrow 23.0.1, pandas 2.2.3.

Colunas em comum nos 3 anos: 121. Mesmo schema em todos os anos.

## 1. Códigos do alvo

**CLASSI_FIN**

| CLASSI_FIN | 2022 | 2023 | 2024 |
|---|---|---|---|
| 0 | 330 | 8 112 | 0 |
| 10 | 1 233 766 | 1 401 419 | 5 904 136 |
| 11 | 18 924 | 23 668 | 101 392 |
| 12 | 1 548 | 1 686 | 8 831 |
| 8 | 149 045 | 207 687 | 542 641 |
| <branco> | 1 482 | 3 384 | 7 924 |

**EVOLUCAO**

| EVOLUCAO | 2022 | 2023 | 2024 |
|---|---|---|---|
| 0 | 488 | 10 610 | 2 206 |
| 1 | 1 149 973 | 1 307 584 | 5 337 488 |
| 2 | 1 056 | 1 192 | 6 337 |
| 3 | 393 | 345 | 1 308 |
| 4 | 65 | 98 | 341 |
| 9 | 55 181 | 55 166 | 257 863 |
| <branco> | 197 939 | 270 961 | 959 381 |

**CRITERIO**

| CRITERIO | 2022 | 2023 | 2024 |
|---|---|---|---|
| 0 | 304 | 2 918 | 402 |
| 1 | 584 788 | 655 107 | 2 199 918 |
| 2 | 665 413 | 766 131 | 3 785 749 |
| 3 | 10 006 | 22 316 | 65 816 |
| <branco> | 144 584 | 199 484 | 513 039 |

**Contingência: algum `GRAV_*` preenchido, por `CLASSI_FIN`** (todos os anos)

| CLASSI_FIN | linhas | com algum GRAV_* preenchido | % |
|---|---|---|---|
| 0 | 8 442 | 8 442 | 100.0 |
| 10 | 8 539 321 | 271 253 | 3.2 |
| 11 | 143 984 | 6 874 | 4.8 |
| 12 | 12 065 | 12 008 | 99.5 |
| 8 | 899 373 | 82 | 0.0 |
| <branco> | 12 790 | 2 | 0.0 |

## 2. Fluxograma de exclusão

| index | 2022 | 2023 | 2024 |
|---|---|---|---|
| 1. Total baixado | 1 405 095 | 1 645 956 | 6 564 924 |
| 2. CLASSI_FIN ∈ {10, 11, 12} | 1 254 238 | 1 426 773 | 6 014 359 |
| 3. Rótulo conhecido (12, ou 10/11 com EVOLUCAO ∈ {1, 2}) | 1 148 338 | 1 304 949 | 5 331 924 |
| 4. Idade válida (0–120 anos) | 1 148 299 | 1 304 909 | 5 331 745 |

**Removidos no filtro 2 (CLASSI_FIN)**

| CLASSI_FIN | 2022 | 2023 | 2024 |
|---|---|---|---|
| 0 | 330 | 8 112 | 0 |
| 8 | 149 045 | 207 687 | 542 641 |
| <branco> | 1 482 | 3 384 | 7 924 |

**Removidos no filtro 3 (rótulo), por EVOLUCAO**

| EVOLUCAO | 2022 | 2023 | 2024 |
|---|---|---|---|
| 0 | 179 | 2 791 | 2 204 |
| 3 | 333 | 295 | 1 106 |
| 4 | 41 | 45 | 180 |
| 9 | 54 198 | 53 796 | 255 821 |
| <branco> | 51 149 | 64 897 | 423 124 |

**Removidos no filtro 3 (rótulo), por CLASSI_FIN**

| CLASSI_FIN | 2022 | 2023 | 2024 |
|---|---|---|---|
| 10 | 104 087 | 119 098 | 668 445 |
| 11 | 1 813 | 2 726 | 13 990 |

**Removidos no filtro 4 (idade), por CLASSI_FIN**

| CLASSI_FIN | 2022 | 2023 | 2024 |
|---|---|---|---|
| 10 | 38 | 39 | 178 |
| 11 | 1 | 1 | 1 |

## 3. Prevalência e eventos

**Prevalência por ano**

| ANO | casos | eventos (y=1) | prevalência (%) |
|---|---|---|---|
| 2 022 | 1 148 299 | 1 869 | 0.16 |
| 2 023 | 1 304 909 | 2 116 | 0.16 |
| 2 024 | 5 331 745 | 11 338 | 0.21 |

**Eventos por região — desenvolvimento 2022–23 (dobras leave-one-region-out)**

| regiao | casos | eventos (y=1) | prevalência (%) | < 100 eventos |
|---|---|---|---|---|
| Centro-Oeste | 408 714 | 736 | 0.18 |  |
| Nordeste | 228 052 | 582 | 0.26 |  |
| Norte | 72 715 | 121 | 0.17 |  |
| Sudeste | 1 162 452 | 1 736 | 0.15 |  |
| Sul | 581 275 | 810 | 0.14 |  |

**Teste 2024 — por faixa etária**

| faixa_etaria | casos | eventos (y=1) | prevalência (%) | < 100 eventos |
|---|---|---|---|---|
| 0–4 | 163 839 | 259 | 0.16 |  |
| 15–39 | 2 274 560 | 2 647 | 0.12 |  |
| 40–59 | 1 457 762 | 2 380 | 0.16 |  |
| 5–14 | 641 272 | 536 | 0.08 |  |
| 60–79 | 699 861 | 3 313 | 0.47 |  |
| 80+ | 94 451 | 2 203 | 2.33 |  |

**Teste 2024 — por sexo**

| sexo | casos | eventos (y=1) | prevalência (%) | < 100 eventos |
|---|---|---|---|---|
| <branco> | 8 | 0 | 0.00 | ⚠️ |
| F | 2 909 965 | 6 046 | 0.21 |  |
| I | 6 188 | 7 | 0.11 | ⚠️ |
| M | 2 415 584 | 5 285 | 0.22 |  |

**Teste 2024 — por gestante (1–4)**

| gestante | casos | eventos (y=1) | prevalência (%) | < 100 eventos |
|---|---|---|---|---|
| False | 5 291 699 | 11 236 | 0.21 |  |
| True | 40 046 | 102 | 0.25 |  |

**Teste 2024 — por região**

| regiao | casos | eventos (y=1) | prevalência (%) | < 100 eventos |
|---|---|---|---|---|
| Centro-Oeste | 491 446 | 1 682 | 0.34 |  |
| Nordeste | 227 290 | 942 | 0.41 |  |
| Norte | 46 117 | 110 | 0.24 |  |
| Sudeste | 3 501 741 | 6 510 | 0.19 |  |
| Sul | 1 065 151 | 2 094 | 0.20 |  |

## 4. Comorbidades

**Valores por ano (todas as notificações)**

| campo | valor | 2022 | 2023 | 2024 |
|---|---|---|---|---|
| DIABETES | 1 | 47 868 | 58 513 | 285 737 |
| DIABETES | 2 | 1 300 991 | 1 534 300 | 6 165 054 |
| DIABETES | <branco> | 56 222 | 52 954 | 114 119 |
| DIABETES | outros | 14 | 189 | 14 |
| HEMATOLOG | 1 | 7 294 | 8 362 | 35 695 |
| HEMATOLOG | 2 | 1 341 566 | 1 584 457 | 6 415 099 |
| HEMATOLOG | <branco> | 56 222 | 52 954 | 114 119 |
| HEMATOLOG | outros | 13 | 183 | 11 |
| HEPATOPAT | 1 | 7 606 | 8 787 | 34 744 |
| HEPATOPAT | 2 | 1 341 254 | 1 584 031 | 6 416 048 |
| HEPATOPAT | <branco> | 56 222 | 52 954 | 114 119 |
| HEPATOPAT | outros | 13 | 184 | 13 |
| RENAL | 1 | 6 218 | 7 504 | 33 245 |
| RENAL | 2 | 1 342 642 | 1 585 314 | 6 417 549 |
| RENAL | <branco> | 56 222 | 52 954 | 114 119 |
| RENAL | outros | 13 | 184 | 11 |
| HIPERTENSA | 1 | 116 221 | 137 156 | 660 409 |
| HIPERTENSA | 2 | 1 232 640 | 1 455 658 | 5 790 385 |
| HIPERTENSA | <branco> | 56 222 | 52 954 | 114 119 |
| HIPERTENSA | outros | 12 | 188 | 11 |
| ACIDO_PEPT | 1 | 7 598 | 8 572 | 35 170 |
| ACIDO_PEPT | 2 | 1 341 262 | 1 584 249 | 6 415 625 |
| ACIDO_PEPT | <branco> | 56 222 | 52 954 | 114 119 |
| ACIDO_PEPT | outros | 13 | 181 | 10 |
| AUTO_IMUNE | 1 | 7 579 | 10 459 | 45 556 |
| AUTO_IMUNE | 2 | 1 341 280 | 1 582 356 | 6 405 235 |
| AUTO_IMUNE | <branco> | 56 222 | 52 954 | 114 119 |
| AUTO_IMUNE | outros | 14 | 187 | 14 |

**Valores fora de 1/2 mais comuns**

| campo | valor | linhas |
|---|---|---|
| DIABETES | 9 | 217 |
| HEMATOLOG | 9 | 207 |
| HEPATOPAT | 9 | 210 |
| RENAL | 9 | 208 |
| HIPERTENSA | 9 | 211 |
| ACIDO_PEPT | 9 | 204 |
| AUTO_IMUNE | 9 | 215 |

**% Ausente × alvo (população final)**

| campo | % ausente y=0 | % ausente y=1 | razão y0/y1 | alerta (razão > 2) |
|---|---|---|---|---|
| DIABETES | 0.00 | 0.01 | 0.59 |  |
| HEMATOLOG | 0.00 | 0.01 | 0.57 |  |
| HEPATOPAT | 0.00 | 0.01 | 0.28 |  |
| RENAL | 0.00 | 0.01 | 0.57 |  |
| HIPERTENSA | 0.00 | 0.01 | 0.57 |  |
| ACIDO_PEPT | 0.00 | 0.01 | 0.56 |  |
| AUTO_IMUNE | 0.00 | 0.01 | 0.58 |  |

## 5. Idade

| ANO | linhas | NU_IDADE_N em branco | código inválido | fora de [0, 120] | recuperada por ANO_NASC | sem idade (excluída) | mín | p50 | p99 | máx |
|---|---|---|---|---|---|---|---|---|---|---|
| 2 022 | 1 405 095 | 0 | 11 507 | 44 | 11 428 | 123 | 0.00 | 33.00 | 82.00 | 120.00 |
| 2 023 | 1 645 956 | 0 | 55 | 56 | 48 | 63 | 0.00 | 33.00 | 82.00 | 120.00 |
| 2 024 | 6 564 924 | 0 | 111 | 240 | 95 | 256 | 0.00 | 34.00 | 83.00 | 120.00 |

**Unidade (1º dígito de NU_IDADE_N)**

| unidade (1º dígito) | 2022 | 2023 | 2024 |
|---|---|---|---|
| 0 | 106 | 4 | 3 |
| 1 | 1 704 | 69 | 178 |
| 2 | 8 242 | 5 468 | 20 049 |
| 3 | 10 610 | 9 070 | 31 386 |
| 4 | 1 381 611 | 1 631 332 | 6 513 273 |
| 5 | 1 308 | 5 | 11 |
| 6 | 856 | 4 | 12 |
| 7 | 339 | 1 | 7 |
| 8 | 193 | 3 | 4 |
| 9 | 126 | 0 | 1 |

**Idade decodificada × (ano de DT_SIN_PRI − ANO_NASC)** — tolerância de 1 ano, porque os microdados não trazem DT_NASC, só o ano de nascimento

| linhas com ANO_NASC e idade | concordam (|dif| ≤ 1 ano) | % concordância | dif. p99 (anos) |
|---|---|---|---|
| 9 561 394 | 9 561 390 | 100.00 | 1.00 |

## 6. Demografia

**CS_SEXO**

| CS_SEXO | 2022 | 2023 | 2024 |
|---|---|---|---|
| <branco> | 25 | 6 | 13 |
| F | 761 763 | 885 311 | 3 580 624 |
| I | 1 408 | 2 355 | 9 839 |
| M | 641 899 | 758 284 | 2 974 448 |

**CS_GESTANT**

| CS_GESTANT | 2022 | 2023 | 2024 |
|---|---|---|---|
| 1 | 2 987 | 3 292 | 12 740 |
| 2 | 3 612 | 4 133 | 14 509 |
| 3 | 2 932 | 3 355 | 12 196 |
| 4 | 1 982 | 2 349 | 10 505 |
| 5 | 493 245 | 585 197 | 2 345 909 |
| 6 | 781 649 | 901 522 | 3 593 122 |
| 9 | 118 297 | 145 860 | 574 736 |
| <branco> | 391 | 248 | 1 207 |

**CS_RACA**

| CS_RACA | 2022 | 2023 | 2024 |
|---|---|---|---|
| 1 | 568 501 | 693 173 | 2 763 406 |
| 2 | 39 851 | 72 528 | 335 247 |
| 3 | 12 326 | 25 613 | 72 387 |
| 4 | 503 083 | 579 683 | 2 316 568 |
| 5 | 3 457 | 3 117 | 15 427 |
| 9 | 277 845 | 271 835 | 1 061 872 |
| <branco> | 32 | 7 | 17 |

**Inconsistências**

| ANO | gestante (1–4) | gestante com sexo M | gestante com < 10 anos |
|---|---|---|---|
| 2 022 | 11 513 | 0 | 0 |
| 2 023 | 13 129 | 4 | 11 |
| 2 024 | 49 950 | 15 | 18 |

**% ignorado (9) + branco — Q-05**

| index | 2022 | 2023 | 2024 |
|---|---|---|---|
| CS_RACA | 19.8 | 16.5 | 16.2 |
| CS_ESCOL_N | 51.5 | 50.2 | 53.9 |

## 7. Sinais clínicos e de alarme

**% ausente (branco ou ≠ 1/2) por ano**

| index | 2022 | 2023 | 2024 |
|---|---|---|---|
| FEBRE | 4.0 | 3.2 | 1.7 |
| MIALGIA | 4.0 | 3.2 | 1.7 |
| CEFALEIA | 4.0 | 3.2 | 1.7 |
| EXANTEMA | 4.0 | 3.2 | 1.7 |
| VOMITO | 4.0 | 3.2 | 1.7 |
| NAUSEA | 4.0 | 3.2 | 1.7 |
| DOR_COSTAS | 4.0 | 3.2 | 1.7 |
| CONJUNTVIT | 4.0 | 3.2 | 1.7 |
| ARTRITE | 4.0 | 3.2 | 1.7 |
| ARTRALGIA | 4.0 | 3.2 | 1.7 |
| PETEQUIA_N | 4.0 | 3.2 | 1.7 |
| LEUCOPENIA | 4.0 | 3.2 | 1.7 |
| LACO | 4.0 | 3.2 | 1.7 |
| DOR_RETRO | 4.0 | 3.2 | 1.7 |

**Algum `ALRM_*` preenchido, por `CLASSI_FIN`** (todos os anos)

| CLASSI_FIN | linhas | com algum ALRM_* preenchido | % |
|---|---|---|---|
| 0 | 8 442 | 8 442 | 100.0 |
| 10 | 8 539 321 | 281 453 | 3.3 |
| 11 | 143 984 | 143 711 | 99.8 |
| 12 | 12 065 | 11 214 | 92.9 |
| 8 | 899 373 | 822 | 0.1 |
| <branco> | 12 790 | 9 | 0.1 |

## 8. Datas

**Atraso sintomas → notificação (dias)**

| ANO | com as duas datas | sintomas > notificação | mediana | p95 | p99 | máx | > 60 dias |
|---|---|---|---|---|---|---|---|
| 2 022 | 1 405 044 | 3 | 3.0 | 14.0 | 61.0 | 354.0 | 14 377 |
| 2 023 | 1 645 956 | 0 | 3.0 | 11.0 | 38.0 | 388.0 | 8 474 |
| 2 024 | 6 564 924 | 0 | 3.0 | 12.0 | 52.0 | 373.0 | 52 045 |

**Ano de DT_SIN_PRI × ano do arquivo**

| ano de DT_SIN_PRI | 2022 | 2023 | 2024 |
|---|---|---|---|
| 2021 | 45 | 0 | 0 |
| 2022 | 1 404 999 | 0 | 0 |
| 2023 | 0 | 1 645 956 | 5 238 |
| 2024 | 0 | 0 | 6 559 686 |
| <branco> | 51 | 0 | 0 |

**Ano de DT_NOTIFIC × ano do arquivo**

| ano de DT_NOTIFIC | 2022 | 2023 | 2024 |
|---|---|---|---|
| 2022 | 1 405 095 | 0 | 0 |
| 2023 | 0 | 1 645 276 | 284 |
| 2024 | 0 | 680 | 6 564 163 |
| 2025 | 0 | 0 | 477 |

## 9. Duplicatas

Chave: ANO_NASC + idade (os microdados não trazem DT_NASC) + CS_SEXO + ID_MN_RESI + DT_SIN_PRI, na população final. Sem a data completa de nascimento, a chave é mais fraca e tende a superestimar duplicatas.

| ANO | linhas | linhas em grupo duplicado | % em grupo duplicado | linhas excedentes (remoção manteria 1) | linhas em grupos com y conflitante |
|---|---|---|---|---|---|
| 2 022 | 1 148 299 | 198 393 | 17.28 | 110 734 | 569 |
| 2 023 | 1 304 909 | 274 876 | 21.06 | 160 919 | 699 |
| 2 024 | 5 331 745 | 2 260 675 | 42.40 | 1 594 148 | 23 811 |

**NDUPLIC_N (marcação de duplicidade do próprio SINAN), população final**

| NDUPLIC_N | 2022 | 2023 | 2024 |
|---|---|---|---|
| / | 0 | 26 | 0 |
| 0 | 0 | 0 | 116 455 |
| 1 | 1 304 | 1 918 | 12 491 |
| <branco> | 1 146 995 | 1 302 965 | 5 202 799 |

## 10. Cobertura do Espírito Santo

População: IBGE, Censo 2022 (SIDRA 4709).

**ES e vizinhos**

| index | 2022 | 2023 | 2024 | por 100 mil — 2022 | por 100 mil — 2023 | por 100 mil — 2024 |
|---|---|---|---|---|---|---|
| 29 (BA) | 18 669 | 26 553 | 152 451 | 132.0 | 187.8 | 1 078.0 |
| 31 (MG) | 66 820 | 306 145 | 1 296 803 | 325.3 | 1 490.5 | 6 313.6 |
| 32 (ES) | 9 062 | 109 436 | 117 062 | 236.4 | 2 854.6 | 3 053.5 |
| 33 (RJ) | 8 538 | 38 050 | 227 885 | 53.2 | 237.0 | 1 419.4 |

**TP_SISTEMA (sistema de origem) — ES e vizinhos, 2022–24**

| SG_UF | / | 0 | 2 | <branco> |
|---|---|---|---|---|
| ES | 25 | 116 208 | 206 | 119 121 |
| MG | 0 | 132 | 1 644 103 | 25 533 |
| RJ | 0 | 29 | 269 318 | 5 126 |
| BA | 0 | 29 | 195 519 | 2 125 |

**Todas as UFs**

| index | 2022 | 2023 | 2024 | por 100 mil — 2022 | por 100 mil — 2023 | por 100 mil — 2024 |
|---|---|---|---|---|---|---|
| 11 (RO) | 12 794 | 9 836 | 3 864 | 809.1 | 622.1 | 244.4 |
| 12 (AC) | 2 790 | 5 212 | 4 778 | 336.1 | 627.9 | 575.7 |
| 13 (AM) | 4 979 | 4 881 | 7 835 | 126.3 | 123.8 | 198.8 |
| 14 (RR) | 60 | 190 | 517 | 9.4 | 29.8 | 81.2 |
| 15 (PA) | 4 315 | 4 143 | 17 075 | 53.1 | 51.0 | 210.3 |
| 16 (AP) | 276 | 844 | 8 244 | 37.6 | 115.0 | 1 123.5 |
| 17 (TO) | 19 509 | 2 884 | 3 804 | 1 290.7 | 190.8 | 251.7 |
| 21 (MA) | 5 163 | 3 979 | 6 965 | 76.2 | 58.7 | 102.8 |
| 22 (PI) | 25 853 | 3 550 | 8 504 | 790.3 | 108.5 | 260.0 |
| 23 (CE) | 39 644 | 14 024 | 11 886 | 450.8 | 159.5 | 135.1 |
| 24 (RN) | 9 054 | 1 574 | 3 848 | 274.1 | 47.7 | 116.5 |
| 25 (PB) | 18 851 | 5 305 | 11 811 | 474.3 | 133.5 | 297.2 |
| 26 (PE) | 7 987 | 3 039 | 13 169 | 88.2 | 33.5 | 145.4 |
| 27 (AL) | 32 505 | 4 753 | 16 945 | 1 039.3 | 152.0 | 541.8 |
| 28 (SE) | 4 860 | 2 690 | 1 715 | 219.9 | 121.7 | 77.6 |
| 29 (BA) | 18 669 | 26 553 | 152 451 | 132.0 | 187.8 | 1 078.0 |
| 31 (MG) | 66 820 | 306 145 | 1 296 803 | 325.3 | 1 490.5 | 6 313.6 |
| 32 (ES) | 9 062 | 109 436 | 117 062 | 236.4 | 2 854.6 | 3 053.5 |
| 33 (RJ) | 8 538 | 38 050 | 227 885 | 53.2 | 237.0 | 1 419.4 |
| 35 (SP) | 310 273 | 314 125 | 1 859 991 | 698.6 | 707.3 | 4 188.1 |
| 41 (PR) | 139 813 | 162 958 | 595 759 | 1 221.7 | 1 423.9 | 5 205.7 |
| 42 (SC) | 82 047 | 108 093 | 304 102 | 1 078.1 | 1 420.3 | 3 995.9 |
| 43 (RS) | 61 258 | 27 106 | 165 284 | 562.9 | 249.1 | 1 518.7 |
| 50 (MS) | 21 290 | 40 703 | 15 484 | 772.2 | 1 476.3 | 561.6 |
| 51 (MT) | 30 633 | 25 802 | 36 710 | 837.3 | 705.2 | 1 003.4 |
| 52 (GO) | 183 662 | 67 414 | 310 359 | 2 602.7 | 955.3 | 4 398.2 |
| 53 (DF) | 27 594 | 11 620 | 128 895 | 979.4 | 412.4 | 4 575.0 |

## 11. Memória

| item | valor |
|---|---|
| RAM total da sessão (GiB) | 12.67 |
| RAM disponível agora (GiB) | 5.37 |
| DataFrame carregado (9,615,975 linhas × 40 colunas, GiB) | 0.46 |
| População final (7,784,953 linhas, GiB) | 0.92 |

Ambiente: Colab.
