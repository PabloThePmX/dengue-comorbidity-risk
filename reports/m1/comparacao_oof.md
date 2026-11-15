# Comparação OOF dos modelos de triagem (T-4.9)

- **Modelo vencedor (M1):** `elastic_net` (Empate técnico entre ['mlp', 'xgboost', 'catboost', 'elastic_net', 'random_forest'] (diferença < 0,005 ou ICs sobrepostos); desempate por estabilidade na pior dobra, calibração e menor complexidade (§1.4).)

| modelo | pr_auc_media | pr_auc_oof | roc_auc | brier | calibrador | limiar_f2 | recall | precisao | f2 | tentativas_ok_podadas |
|---|---|---|---|---|---|---|---|---|---|---|
| B0 (prevalência) | 0.0018 | 0.0015 | 0.4629 | 0.0016 | - | - | - | - | - | 0/0 |
| B2 (protocolo MS) | - | - | - | - | regra | - | 0.6843 | 0.0042 | 0.0206 | 0/0 |
| b1 | 0.0126 | 0.0128 | 0.7241 | 0.0016 | isotonic | 0.0251 | 0.1338 | 0.0351 | 0.0856 | 1/0 |
| elastic_net | 0.0266 | 0.0260 | 0.8316 | 0.0016 | isotonic | 0.0230 | 0.2043 | 0.0400 | 0.1121 | 2/0 |
| xgboost | 0.0283 | 0.0289 | 0.8501 | 0.0016 | isotonic | 0.0259 | 0.1920 | 0.0478 | 0.1197 | 21/7 |
| catboost | 0.0271 | 0.0273 | 0.8451 | 0.0016 | isotonic | 0.0230 | 0.2321 | 0.0382 | 0.1151 | 21/4 |
| mlp | 0.0284 | 0.0280 | 0.8494 | 0.0016 | isotonic | 0.0263 | 0.1957 | 0.0458 | 0.1183 | 2/0 |
| random_forest | 0.0262 | 0.0259 | 0.8440 | 0.0016 | isotonic | 0.0239 | 0.2198 | 0.0393 | 0.1146 | 5/0 |
| tabfm | 0.0121 | 0.0091 | 0.7710 | 0.0016 | isotonic | 0.0135 | 0.2110 | 0.0171 | 0.0646 | 1/0 |
