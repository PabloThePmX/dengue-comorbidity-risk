# Tarefas — Fase 4 — US2: triagem (Marco 4)

> **Leia antes:** [00-como-usar.md](00-como-usar.md) — regras (§0, R1–R10), referência rápida (§1),
> dependências (§7b) e os registros §9 e §10, que ficam **lá**, não neste arquivo. Os §0, §1, §7b,
> §9 e §10 citados abaixo são daquele arquivo.

---

## 4. Fase 4 — US2: triagem (Marco 4, P2)

Spec: FR-07, FR-08, FR-12, FR-13, FR-17, FR-22, NFR-01, §3.11, D-32, D-36, D-37, D-42, D-43.
Tudo em 2022–23 (R1). **Uma sessão única do Colab para os 6 modelos** (NFR-01, D-53): mesmos dados,
mesmas dobras (arquivo de T-2.3 com hash), mesma semente; comparação pareada no fim (T-4.9).
VM com GPU (L4 de preferência; T4 serve) e High RAM no Pro. No gratuito, o mesmo notebook roda,
mais devagar, retomando de onde parou.

**Como esta fase é verificada (D-57):** T-4.0 a T-4.10 são implementadas e testadas **localmente**
(dados sintéticos). Só depois que todas estiverem prontas o Programador roda **uma** sessão do
Colab (`notebooks/04_modelos.ipynb`), que executa tudo e grava **um** relatório:
`reports/verificacao/sessao-m1.json`, com um bloco por etapa (checagem inicial, cada modelo,
seleção, SHAP, retreino), cada um com seu `"passou"`. O arquivo é reescrito ao fim de cada etapa;
se a sessão cair, o que terminou fica registrado e a reexecução continua de onde parou.

### [ ] T-4.0 [US2] — Espaço de busca (Q-08) — 🛑 aprovação do Programador

Proposta (registrar no `config/base.yaml` depois do "ok"):

| Modelo | Hiperparâmetros e faixas propostas |
|---|---|
| Elastic net (`LogisticRegression(penalty="elasticnet", solver="saga")`) | `C` log [1e-3, 10]; `l1_ratio` [0, 1] |
| Random Forest | `n_estimators` [200, 800]; `max_depth` [4, 20] ou None; `min_samples_leaf` [10, 500] log; `max_features` {"sqrt", 0.3, 0.5}; `max_samples` [0.05, 0.3] (fração sorteada por árvore: acelera muito sem mudar a prevalência, D-53) |
| XGBoost (`tree_method="hist"`) | `learning_rate` log [0.01, 0.3]; `max_depth` [3, 10]; `min_child_weight` log [1, 100]; `subsample` [0.5, 1]; `colsample_bytree` [0.5, 1]; `reg_lambda` log [1e-3, 10]; `n_estimators` até 2000 com early stopping |
| CatBoost | `learning_rate` log [0.01, 0.3]; `depth` [4, 10]; `l2_leaf_reg` log [1, 30]; `iterations` até 3000 com early stopping |
| MLP (PyTorch, GPU) | camadas ocultas {[64], [128], [128, 64]}; `dropout` [0, 0.3]; `weight_decay` log [1e-6, 1e-2]; `lr` log [1e-4, 1e-2] (Adam); `batch_size` {1024, 4096}; épocas até 200 com early stopping. Perda: `BCEWithLogitsLoss` **sem `pos_weight`** (R3) |
| TabFM | sem busca |

Nenhum parâmetro de peso de classe (R3).

### [ ] T-4.1 [P] [US2] — Pré-processamento por família (`preprocess.py`)

- `make_preprocessor(familia) -> ColumnTransformer`:
  - `"linear"` (elastic net, MLP): spline + escala na idade; `StandardScaler` em `dias`;
    one-hot nas categóricas;
  - `"arvore"` (RF, XGBoost): `OrdinalEncoder` nas categóricas; numéricas cruas;
  - `"catboost"`: categóricas passadas como `cat_features` (sem encoder).
- Elastic net recebe também as interações 2 a 2 entre comorbidades (`PolynomialFeatures(interaction_only=True)`
  só nas colunas de comorbidade Sim).
- Teste: o `ColumnTransformer` ajustado só no treino transforma a validação sem erro e com o
  mesmo nº de colunas; nenhuma coluna da lista proibida (R4) entra.
- **Pronto quando:** testes passam.

### [ ] T-4.2 [US2] — Laço de validação com early stopping (`cv.py`)

- `run_loro(cfg, familia, params, df) -> dict` que, para cada dobra:
  1. separa treino (4 regiões) e validação (1 região);
  2. para modelos iterativos, separa a validação interna com `inner_split` (R6);
  3. ajusta o pipeline no treino (iterativos: early stopping na validação interna, monitorando
     PR-AUC — `eval_metric="aucpr"` no XGBoost, `eval_metric="PRAUC"` no CatBoost; no MLP, ao fim
     de cada época calcule a PR-AUC na validação interna e guarde o `state_dict` da melhor época;
     paciência 50 rodadas / 10 épocas);
  4. guarda o **melhor ponto** (nº de árvores / época) e o modelo daquele ponto (FR-22);
  5. prediz a região de validação (OOF).
- Devolve: OOF de todas as linhas, PR-AUC por dobra, PR-AUC média, melhores pontos por dobra.
- Chame `assert_dev_only` (R1).
- Teste com dados sintéticos pequenos: OOF tem uma predição por linha; nenhuma linha é prevista por
  um modelo que a viu no treino.
- **Pronto quando:** teste passa e `run_loro` roda com B1 reproduzindo as métricas de T-2.8.

### [ ] T-4.3 [US2] — Busca com Optuna (`tuning.py`) (D-43, NFR-01)

- `tune(cfg, modelo, df)`:
  - `optuna.create_study(direction="maximize", sampler=TPESampler(seed=cfg.seed),
    pruner=MedianPruner(), storage="sqlite:///<Drive>/optuna/<modelo>.db", study_name=<modelo>,
    load_if_exists=True)` — busca **retomável**;
  - pruner: `MedianPruner(n_startup_trials=cfg.optuna.poda_tentativas_iniciais,
    n_warmup_steps=cfg.optuna.poda_dobras_aquecimento)`;
  - **cronometragem (D-53):** se o estudo estiver vazio, `study.enqueue_trial(<padrões da biblioteca>)`
    e rode essa 1ª tentativa sozinha (`n_trials=1`), medindo o tempo `t` das 5 dobras;
  - orçamento = `max(piso, min(teto, t × max_tentativas))` (valores do config); se `3t > teto`, a
    busca vai para a subamostra (item abaixo); grave `t` e o orçamento no MLflow;
  - `study.optimize(objetivo, n_trials=max_tentativas[modelo], timeout=orçamento_em_segundos)`;
  - objetivo: `run_loro` reportando a PR-AUC acumulada após cada dobra (`trial.report`) e podando
    com `trial.should_prune()`;
  - se `3t > teto`: busca em **subamostra estratificada pelo alvo** de cada dobra (mesma
    prevalência, R3), no tamanho que faça `3t` caber, e anote isso no MLflow. As predições OOF finais
    do modelo (T-4.4 em diante) usam todos os dados.
- Registre no MLflow: tempo gasto, tentativas concluídas e podadas, hardware.
- A melhor tentativa vai para o registro de modelos com alias **`melhor-validacao`** (FR-22).
  Tentativas piores nunca sobrescrevem.
- Teste local com dados sintéticos e SQLite numa pasta temporária: rodar `tune` com `n_trials=2`,
  chamar de novo com o mesmo `study_name` e conferir que o nº de tentativas cresceu e que nenhuma
  tentativa anterior se perdeu (interrupção simulada).
- **Pronto quando:** testes passam. A busca real é verificada no `sessao-m1.json` (T-4.3b).

### [ ] T-4.3b [US2] — Execução em sessão única (`runner.py`) (D-53)

- `run_all_models(cfg)`:
  1. carrega a população 2022–23 uma vez (`load_population`) e as dobras com `load_folds` (hash);
  2. percorre `cfg.ordem_modelos`; para cada modelo, se existir `<Drive>/m1/<modelo>/CONCLUIDO.json`
     com o mesmo hash de dobras e de config, **pula**;
  3. senão: `tune` → `run_loro` com os melhores parâmetros → grava OOF (`oof.parquet`), métricas,
     melhores parâmetros e melhores pontos por dobra; por último grava `CONCLUIDO.json`;
  4. libera memória entre modelos (`del`, `gc.collect()`, `torch.cuda.empty_cache()`);
  5. no fim, chama a seleção (T-4.9), o SHAP global (T-4.8) e o retreino final (T-4.10), nessa ordem;
  6. **relatório da sessão (D-57):** antes do 1º modelo, grava o bloco `checagem_inicial` (Drive
     gravável, SQLite do Optuna abre no Drive, GPU detectada, hash das dobras igual ao de T-2.3); ao
     fim de cada etapa, chama `verify.update_session_report` com o bloco daquela etapa (checks em
     cada tarefa abaixo). Bloco de modelo pulado por `CONCLUIDO.json` é mantido como estava.
- Notebook `notebooks/04_modelos.ipynb`: só monta o Drive, carrega o config e chama `run_all_models`
  (sem lógica no notebook). No fim, copia o `sessao-m1.json` do Drive para download.
- Registre no MLflow o hardware (GPU, nº de vCPUs, RAM) uma vez por sessão.
- Teste com dados sintéticos e 2 modelos baratos: interromper depois do 1º e rodar de novo pula o 1º
  e termina o 2º; hash de dobras diferente faz o modelo rodar de novo.
- Teste local da queda simulada: `run_all_models` com uma opção de teste que levanta erro depois do
  1º modelo; na reexecução, o 1º é pulado (`CONCLUIDO.json`), o 2º termina e o relatório tem os dois
  blocos com `"passou": true`.
- **Pronto quando:** testes passam e o bloco `checagem_inicial` do `sessao-m1.json` tem
  `"passou": true`.

### [ ] T-4.4 a T-4.8 [US2] — Os 6 modelos (dentro de `run_all_models`)

Implemente e teste cada modelo separadamente (testes rápidos em CPU), mas a execução real é **uma
só**, pela T-4.3b, na ordem do config. Tetos de tempo e de tentativas: `config/base.yaml` (D-53).

- [ ] **T-4.4 Random Forest** (teto 40 min, CPU). Se faltar memória: subamostra de negativos **só no treino
  da dobra**, depois corrija a probabilidade: `p' = p / (p + (1 − p) / taxa_amostragem)` e confira
  a calibração no OOF. Anote a taxa no MLflow.
- [ ] **T-4.5 XGBoost** (teto 30 min, `device="cuda"` se houver GPU). Sem `scale_pos_weight` (R3).
- [ ] **T-4.6 CatBoost** (teto 40 min, `task_type="GPU"` se houver GPU). Sem `auto_class_weights`
  (R3). Se o CatBoost em GPU não aceitar `eval_metric="PRAUC"` no early stopping, use CPU e anote
  no §10 (spec `[VERIFY]`).
- [ ] **T-4.6b Elastic net** (teto 20 min, CPU) e **MLP** (teto 40 min, GPU).
  - MLP em `src/dengue_sinan/mlp.py`: classe compatível com sklearn (`fit`, `predict_proba`) que
    envolve a rede PyTorch, para entrar no mesmo `Pipeline` (R5) e no mesmo `run_loro`.
  - Fixe as sementes do PyTorch (`torch.manual_seed`, `torch.cuda.manual_seed_all`) com a semente do
    config (R8) e registre o dispositivo usado no MLflow.
  - Teste unitário rápido em CPU com dados sintéticos: treina, para no early stopping e devolve
    probabilidades entre 0 e 1.
- [ ] **T-4.7 TabFM** (teto 30 min, GPU).
  - **Antes de codar, 🛑 PARE E PERGUNTE** com estas informações do model card (spec `[VERIFY]`):
    licença dos pesos cobre uso acadêmico?; limite de linhas de contexto e de features; velocidade
    de predição; nome e versão do pacote.
  - Contexto = subamostra **estratificada** do treino de cada dobra, no tamanho do limite verificado.
  - Sem busca; calibração igual aos outros (T-4.9).
- [ ] **T-4.8 SHAP global (FR-13, SHOULD).** Para o melhor modelo de árvore: valores SHAP e SHAP
  interaction values numa subamostra estratificada de 50 mil linhas `[ASSUMPTION]` de 2022–23.
  Gráficos em `reports/shap/`. Legenda: "explica o modelo, não causa; instável com features
  correlacionadas". Não usar para ranking (R10).

**Pronto (para cada um) quando:** testes locais passam e o bloco do modelo no `sessao-m1.json` tem
`"passou": true` para: OOF com exatamente uma predição por linha de 2022–23 (2.453.208); PR-AUC
registrada nas 5 dobras; melhores pontos por dobra (modelos iterativos); alias `melhor-validacao`
no MLflow; tempo gasto ≤ teto do modelo; nº de tentativas concluídas e podadas. Para a T-4.8
(SHAP, SHOULD), o bloco `shap` confere que os gráficos de `reports/shap/` foram gerados.

### [ ] T-4.9 [US2] — Calibração, limiar e seleção (FR-08, FR-17, §3.11)

- Para cada modelo: ajustar **isotônica** e **Platt** nas predições OOF (2022–23); escolher a de
  menor Brier OOF. Guardar o calibrador.
- Limiar = `best_f2_threshold` nas predições OOF **calibradas**.
- Tabela comparativa `reports/m1/comparacao_oof.md`: por modelo, PR-AUC média (e por dobra),
  Brier, slope/intercept, ROC-AUC, métricas no limiar; com B0, B1 e B2 ao lado; e, por modelo, tempo
  da cronometragem, orçamento usado e tentativas concluídas/podadas.
- **Comparação pareada (D-53)** `reports/m1/comparacao_pareada.md`: para cada par de modelos
  (incluindo B1), diferença de PR-AUC por dobra (5 valores) e `paired_bootstrap_diff` com IC 95%.
  Use `bootstrap_pareado` e a semente do config; os mesmos sorteios para todos os pares.
- Aplicar a **regra de seleção** da §1.4, com empate por "diferença < 0,005 ou ICs sobrepostos"
  (mantida em D-53). A comparação pareada **não** entra na seleção: ela só é reportada. Registrar o vencedor e o motivo no §9 e no MLflow.
- **Pronto quando:** testes locais passam e o bloco `selecao` do `sessao-m1.json` tem `"passou": true`
  para: um único modelo escolhido, com calibrador e limiar gravados; `comparacao_oof.md` e
  `comparacao_pareada.md` gerados; nenhum arquivo de 2024 aberto na sessão (`guard`).

### [ ] T-4.10 [US2] — Retreino final e congelamento (FR-12, FR-22, D-37)

- Retreinar o modelo escolhido em **todo** 2022–23 com os melhores hiperparâmetros.
  Iterativos: nº de árvores/épocas = **mediana** dos melhores pontos das 5 dobras (sem early stopping).
- Aplicar o calibrador e o limiar da T-4.9 (não reajustar).
- Serializar com `save_bundle` (pipeline + calibrador + limiar + metadados FR-12 + os 5 melhores pontos).
- Medir se o modelo cabe na demo: tamanho do arquivo, tempo de predição de um caso e tempo do SHAP
  local. Os três vão para o bloco `retreino` do `sessao-m1.json`. Se o tempo passar de 1 s
  (NFR-06): **🛑 PARE E PERGUNTE** (Q-14).
- **Pronto quando:** o bloco `retreino` do `sessao-m1.json` tem `"passou": true` para: o artefato
  `models/m1_final.*` (no Drive) carrega e prediz; o hash do arquivo está no relatório (copie para o
  §9).
