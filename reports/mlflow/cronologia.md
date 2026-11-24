# Cronologia dos experimentos (MLflow)

Exportado de `retorno-mlruns/` (cópia do `mlruns/` do Drive). Experimento `dengue-comorbidity-risk`; 45 execuções em 7 sessões (cada sessão começa em uma execução `sessao-m1`). Horários em UTC, como gravados pelo MLflow. Só agregados (R7): não há microdados nem parâmetros de configuração; esses estão em `config/` e nos hashes de dados dos registros.

Leitura das colunas: `pr_auc_busca` é a melhor PR-AUC da busca de hiperparâmetros; `oof_pr_auc` e `pr_auc_media` são do modelo final, fora da dobra (OOF) e média por dobra; `tempo_busca_s` e `tempo_treino_s` em segundos; `limiar`, `limiar_f2` e `recall_no_limiar` vêm da execução `selecao`. A diferença entre início e fim registrada pelo MLflow é zero em várias execuções, então esta tabela não a usa: os tempos vêm das métricas `tempo_busca_s` e `tempo_treino_s`. A execução `tune-elastic_net` de 2026-11-17 13:00 está como FAILED; a repetição das 13:27 terminou (FINISHED). Os pares de execuções `selecao` de 2026-11-18 23:54 e 2026-11-19 01:38 trazem os mesmos números.

| sessao | inicio_utc | run | status | pr_auc_busca | tentativas_concluidas | tentativas_podadas | tempo_busca_s | oof_pr_auc | pr_auc_media | tempo_treino_s | limiar | limiar_f2 | recall_no_limiar | brier_calibrado |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-11-17 13:00 | sessao-m1 | FINISHED |  |  |  |  |  |  |  |  |  |  |  |
| 1 | 2026-11-17 13:00 | tune-elastic_net | FAILED |  |  |  |  |  |  |  |  |  |  |  |
| 2 | 2026-11-17 13:27 | sessao-m1 | FINISHED |  |  |  |  |  |  |  |  |  |  |  |
| 2 | 2026-11-17 13:27 | tune-elastic_net | FINISHED | 0.0180 | 3 | 0 | 1253 |  |  |  |  |  |  |  |
| 2 | 2026-11-17 14:59 | final-elastic_net | FINISHED |  |  |  |  | 0.0195 | 0.0207 | 4242 |  |  |  |  |
| 2 | 2026-11-17 14:59 | tune-xgboost | FINISHED | 0.0284 | 14 | 16 | 1652 |  |  |  |  |  |  |  |
| 2 | 2026-11-17 15:28 | final-xgboost | FINISHED |  |  |  |  | 0.0287 | 0.0284 | 81 |  |  |  |  |
| 2 | 2026-11-17 15:28 | tune-catboost | FINISHED | 0.0265 | 5 | 2 | 2450 |  |  |  |  |  |  |  |
| 2 | 2026-11-17 16:19 | final-catboost | FINISHED |  |  |  |  | 0.0260 | 0.0266 | 565 |  |  |  |  |
| 2 | 2026-11-17 16:19 | tune-mlp | FINISHED | 0.0277 | 6 | 2 | 3272 |  |  |  |  |  |  |  |
| 2 | 2026-11-17 17:29 | final-mlp | FINISHED |  |  |  |  | 0.0276 | 0.0277 | 916 |  |  |  |  |
| 2 | 2026-11-17 17:29 | tune-random_forest | FINISHED | 0.0254 | 6 | 0 | 3306 |  |  |  |  |  |  |  |
| 2 | 2026-11-17 18:31 | final-random_forest | FINISHED |  |  |  |  | 0.0245 | 0.0254 | 416 |  |  |  |  |
| 3 | 2026-11-17 19:17 | sessao-m1 | FINISHED |  |  |  |  |  |  |  |  |  |  |  |
| 3 | 2026-11-17 19:17 | tune-elastic_net | FINISHED | 0.0289 | 3 | 1 | 1411 |  |  |  |  |  |  |  |
| 3 | 2026-11-17 20:18 | final-elastic_net | FINISHED |  |  |  |  | 0.0260 | 0.0266 | 1110 |  |  |  |  |
| 3 | 2026-11-17 20:18 | tune-xgboost | FINISHED | 0.0284 | 14 | 16 | 1652 |  |  |  |  |  |  |  |
| 3 | 2026-11-17 20:19 | final-xgboost | FINISHED |  |  |  |  | 0.0287 | 0.0284 | 82 |  |  |  |  |
| 3 | 2026-11-17 20:19 | tune-catboost | FINISHED | 0.0265 | 5 | 2 | 2450 |  |  |  |  |  |  |  |
| 3 | 2026-11-17 20:28 | final-catboost | FINISHED |  |  |  |  | 0.0258 | 0.0252 | 500 |  |  |  |  |
| 3 | 2026-11-17 20:28 | tune-mlp | FINISHED | 0.0277 | 6 | 2 | 3272 |  |  |  |  |  |  |  |
| 3 | 2026-11-17 20:43 | final-mlp | FINISHED |  |  |  |  | 0.0276 | 0.0277 | 941 |  |  |  |  |
| 3 | 2026-11-17 20:44 | tune-random_forest | FINISHED | 0.0254 | 6 | 0 | 3306 |  |  |  |  |  |  |  |
| 3 | 2026-11-17 20:51 | final-random_forest | FINISHED |  |  |  |  | 0.0245 | 0.0254 | 424 |  |  |  |  |
| 4 | 2026-11-17 21:57 | sessao-m1 | FINISHED |  |  |  |  |  |  |  |  |  |  |  |
| 4 | 2026-11-17 21:57 | tune-mlp | FINISHED | 0.0270 | 5 | 3 | 2442 |  |  |  |  |  |  |  |
| 4 | 2026-11-17 22:43 | final-mlp | FINISHED |  |  |  |  | 0.0249 | 0.0270 | 280 |  |  |  |  |
| 4 | 2026-11-17 22:43 | tune-random_forest | FINISHED | 0.0254 | 5 | 1 | 2429 |  |  |  |  |  |  |  |
| 4 | 2026-11-17 23:31 | final-random_forest | FINISHED |  |  |  |  | 0.0245 | 0.0254 | 412 |  |  |  |  |
| 5 | 2026-11-18 04:20 | sessao-m1 | FINISHED |  |  |  |  |  |  |  |  |  |  |  |
| 5 | 2026-11-18 04:20 | tune-elastic_net | FINISHED | 0.0289 | 3 | 1 | 1411 |  |  |  |  |  |  |  |
| 5 | 2026-11-18 04:38 | final-elastic_net | FINISHED |  |  |  |  | 0.0260 | 0.0266 | 1070 |  |  |  |  |
| 5 | 2026-11-18 04:38 | tune-xgboost | FINISHED | 0.0284 | 14 | 16 | 1652 |  |  |  |  |  |  |  |
| 5 | 2026-11-18 04:39 | final-xgboost | FINISHED |  |  |  |  | 0.0287 | 0.0284 | 78 |  |  |  |  |
| 5 | 2026-11-18 04:39 | tune-catboost | FINISHED | 0.0265 | 5 | 2 | 2450 |  |  |  |  |  |  |  |
| 5 | 2026-11-18 04:47 | final-catboost | FINISHED |  |  |  |  | 0.0258 | 0.0252 | 482 |  |  |  |  |
| 5 | 2026-11-18 04:47 | tune-mlp | FINISHED | 0.0270 | 5 | 3 | 2442 |  |  |  |  |  |  |  |
| 5 | 2026-11-18 04:52 | final-mlp | FINISHED |  |  |  |  | 0.0249 | 0.0270 | 278 |  |  |  |  |
| 5 | 2026-11-18 04:52 | tune-random_forest | FINISHED | 0.0254 | 5 | 1 | 2429 |  |  |  |  |  |  |  |
| 5 | 2026-11-18 04:59 | final-random_forest | FINISHED |  |  |  |  | 0.0245 | 0.0254 | 412 |  |  |  |  |
| 5 | 2026-11-18 05:08 | selecao | FINISHED |  |  |  |  |  |  |  | 0.021514 |  |  | 0.001599 |
| 6 | 2026-11-18 23:45 | sessao-m1 | FINISHED |  |  |  |  |  |  |  |  |  |  |  |
| 6 | 2026-11-18 23:54 | selecao | FINISHED |  |  |  |  |  |  |  | 0.002155 | 0.021514 | 0.6846 | 0.001599 |
| 7 | 2026-11-19 01:30 | sessao-m1 | FINISHED |  |  |  |  |  |  |  |  |  |  |  |
| 7 | 2026-11-19 01:38 | selecao | FINISHED |  |  |  |  |  |  |  | 0.002155 | 0.021514 | 0.6846 | 0.001599 |
