# Fluxograma de exclusão (FR-02)

Contagem de registros após cada filtro de população, por ano do arquivo.

| index | 2024 |
|---|---|
| 1. Total baixado | 6 564 924 |
| 2. CLASSI_FIN ∈ {10, 11, 12} | 6 014 359 |
| 3. Rótulo conhecido (12, ou 10/11 com EVOLUCAO ∈ {1, 2}) | 5 331 924 |
| 4. Idade válida (0–120 anos) | 5 331 745 |

## Motivos de exclusão

### Removidos no filtro 2 (CLASSI_FIN)

| CLASSI_FIN | 2024 |
|---|---|
| 8 | 542 641 |
| <branco> | 7 924 |

### Removidos no filtro 3 (rótulo), por EVOLUCAO

| EVOLUCAO | 2024 |
|---|---|
| 0 | 2 204 |
| 3 | 1 106 |
| 4 | 180 |
| 9 | 255 821 |
| <branco> | 423 124 |

### Removidos no filtro 3 (rótulo), por CLASSI_FIN

| CLASSI_FIN | 2024 |
|---|---|
| 10 | 668 445 |
| 11 | 13 990 |

### Removidos no filtro 4 (idade), por CLASSI_FIN

| CLASSI_FIN | 2024 |
|---|---|
| 10 | 178 |
| 11 | 1 |
