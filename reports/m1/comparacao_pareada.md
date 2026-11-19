# Comparação pareada da PR-AUC (T-4.9, D-53)

Diferença de PR-AUC (A − B) por dobra e média das dobras, com IC 95% por bootstrap pareado: 1000 reamostras, semente 20261103, estratificadas por dobra e alvo. Os mesmos sorteios valem para todos os pares.

**Não entra na seleção.** A regra do plan usa a PR-AUC média e os ICs de cada modelo (comparacao_oof.md). Esta tabela só informa o que a diferença entre dois modelos mostra.

| Par (A − B) | Sudeste | Sul | Centro-Oeste | Nordeste | Norte | Diferença média | IC 95% | IC exclui 0 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| elastic_net − xgboost | -0,00381 | -0,00413 | 0,00035 | -0,00192 | 0,00079 | -0,00175 | [-0,00426; 0,00068] | não |
| elastic_net − catboost | -0,00089 | -0,00283 | 0,00340 | 0,00373 | 0,00356 | 0,00139 | [-0,00104; 0,00397] | não |
| elastic_net − mlp | -0,00095 | -0,00292 | 0,00157 | -0,00044 | 0,00083 | -0,00038 | [-0,00218; 0,00152] | não |
| elastic_net − random_forest | 0,00178 | -0,00736 | 0,00451 | 0,00482 | 0,00260 | 0,00127 | [-0,00108; 0,00399] | não |
| elastic_net − B1 | 0,01381 | 0,01035 | 0,01632 | 0,01321 | 0,01535 | 0,01381 | [0,01105; 0,01756] | sim |
| xgboost − catboost | 0,00292 | 0,00130 | 0,00306 | 0,00565 | 0,00278 | 0,00314 | [0,00124; 0,00556] | sim |
| xgboost − mlp | 0,00286 | 0,00122 | 0,00122 | 0,00148 | 0,00004 | 0,00136 | [-0,00014; 0,00331] | não |
| xgboost − random_forest | 0,00559 | -0,00323 | 0,00416 | 0,00674 | 0,00181 | 0,00302 | [0,00124; 0,00549] | sim |
| xgboost − B1 | 0,01762 | 0,01449 | 0,01597 | 0,01513 | 0,01456 | 0,01556 | [0,01293; 0,01984] | sim |
| catboost − mlp | -0,00005 | -0,00008 | -0,00184 | -0,00417 | -0,00274 | -0,00178 | [-0,00372; 0,00021] | não |
| catboost − random_forest | 0,00268 | -0,00453 | 0,00111 | 0,00109 | -0,00096 | -0,00012 | [-0,00164; 0,00145] | não |
| catboost − B1 | 0,01471 | 0,01319 | 0,01292 | 0,00948 | 0,01179 | 0,01242 | [0,01022; 0,01571] | sim |
| mlp − random_forest | 0,00273 | -0,00445 | 0,00295 | 0,00526 | 0,00177 | 0,00165 | [-0,00028; 0,00380] | não |
| mlp − B1 | 0,01476 | 0,01327 | 0,01476 | 0,01365 | 0,01452 | 0,01419 | [0,01164; 0,01795] | sim |
| random_forest − B1 | 0,01203 | 0,01772 | 0,01181 | 0,00839 | 0,01275 | 0,01254 | [0,01027; 0,01573] | sim |

Pares com B1 (logística sem penalização) incluídos. Só agregados (R7).
