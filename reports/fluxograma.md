# Fluxograma de exclusão (FR-02)

Contagem de linhas após cada filtro, por ano do arquivo. Células com menos de 10 casos são suprimidas (R7).

Nota: células com menos de 10 casos aparecem como "<10" (R7). A supressão é simples: como os totais de cada filtro são publicados, a célula suprimida pode ser deduzida por subtração (total do filtro menos as demais células). É uma limitação conhecida e aceita para agregados de dados abertos. Nenhuma contagem de 1 a 9 é publicada.

| etapa | 2022 | 2023 |
|---|---|---|
| 1. Total baixado | 1 405 095 | 1 645 956 |
| 2. CLASSI_FIN ∈ {10, 11, 12} | 1 254 238 | 1 426 773 |
| 3. Rótulo conhecido (12, ou 10/11 com EVOLUCAO ∈ {1, 2}) | 1 148 338 | 1 304 949 |
| 4. Idade válida (0–120 anos) | 1 148 299 | 1 304 909 |

**Removidos no filtro 2 (CLASSI_FIN)**

| CLASSI_FIN | 2022 | 2023 |
|---|---|---|
| 0 | 330 | 8 112 |
| 8 | 149 045 | 207 687 |
| <branco> | 1 482 | 3 384 |

**Removidos no filtro 3 (rótulo), por EVOLUCAO**

| EVOLUCAO | 2022 | 2023 |
|---|---|---|
| 0 | 179 | 2 791 |
| 3 | 333 | 295 |
| 4 | 41 | 45 |
| 9 | 54 198 | 53 796 |
| <branco> | 51 149 | 64 897 |

**Removidos no filtro 3 (rótulo), por CLASSI_FIN**

| CLASSI_FIN | 2022 | 2023 |
|---|---|---|
| 10 | 104 087 | 119 098 |
| 11 | 1 813 | 2 726 |

**Removidos no filtro 4 (idade), por CLASSI_FIN**

| CLASSI_FIN | 2022 | 2023 |
|---|---|---|
| 10 | 38 | 39 |
| 11 | <10 | <10 |
