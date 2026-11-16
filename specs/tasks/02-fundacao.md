# Marco 2 — Descrição, split e baselines

> **Leia antes:** [00-como-usar.md](00-como-usar.md) (como executar, Verificação no Colab, Erros
> inesperados). Os registros de execução e de problemas ficam **lá**.

Objetivo: descrever a população e fixar o piso que todo modelo precisa superar. Spec: FR-04,
FR-17, FR-18, [Baselines](../spec.md#baselines). T-2.0 prepara o ambiente; T-2.1 a T-2.8 são a
fundação e bloqueiam todos os outros marcos.

Critério de saída ([spec › Marcos](../spec.md#marcos)): análise descritiva gerada; dobras
construídas; métricas fora da dobra de B0, B1 e B2 no MLflow; eventos por par de comorbidades
contados; **2024 intocado**.

### [x] T-2.0 — Dependências e configuração

- **Dependências aprovadas (D-67)**, sem precisar perguntar de novo:
  - runtime: `scikit-learn`, `statsmodels` (E1 com IC), `xgboost`, `catboost`, `optuna`, `mlflow`,
    `shap`, `pyyaml`, `matplotlib`, `streamlit`;
  - MLP: **`torch` (PyTorch)** (D-51). O código escolhe o dispositivo sozinho (`"cuda"` se houver,
    senão `"cpu"`), para continuar executável no Colab gratuito (D-44);
  - TabFM: só na T-4.7 (D-69).
- `uv add <pacotes>`; rode `uv run pytest -q` (os 48 testes atuais devem passar).
  Observado na execução (2026-11-16): com `mlflow` 3.18.0 o lock manteve o `pyarrow` 26.0.0, sem
  rebaixar para 25.x, e os testes passam. Se um `uv add` futuro rebaixar o pyarrow, não é erro
  e não precisa ir para o Registro de problemas.
- Crie `config/base.yaml` com, no mínimo:
  ```yaml
  seed: 20261103
  anos_dev: [2022, 2023]
  ano_teste: 2024
  caminhos:
    dados: "data"            # no Colab: /content/drive/MyDrive/dengue-comorbidity-risk/data
    mlruns: "mlruns"
    relatorios: "reports"
  dias_notificacao_max: 60
  faixas: [0, 5, 15, 40, 60, 80]
  validacao_interna_frac: 0.10
  bootstrap: {metricas: 1000, calibracao: 2000}
  supressao_min_celula: 10
  dca_limiares: {min: 0.001, max: 0.05, passos: 50}
  # D-53: sessão única; teto por modelo, orçamento real sai da cronometragem (T-4.3)
  ordem_modelos: [elastic_net, xgboost, catboost, mlp, random_forest, tabfm]
  ordem_dobras: [Sudeste, Sul, Centro-Oeste, Nordeste, Norte]
  orcamento_teto_min: {elastic_net: 20, xgboost: 30, catboost: 40, mlp: 40, random_forest: 40, tabfm: 30}
  orcamento_piso_min: 10
  optuna:
    max_tentativas: {elastic_net: 15, xgboost: 30, catboost: 25, mlp: 25, random_forest: 25, tabfm: 1}
    poda_tentativas_iniciais: 5   # MedianPruner(n_startup_trials)
    poda_dobras_aquecimento: 2    # MedianPruner(n_warmup_steps): só poda depois da 2ª dobra
  bootstrap_pareado: 1000
  # D-64: ambiente mínimo conferido antes da sessão dos modelos (Pro, T4 + RAM alta)
  ambiente: {gpu: "T4", ram_min_gib: 50}   # no Colab gratuito: {gpu: null, ram_min_gib: 12}
  ```
- Crie `src/dengue_sinan/config.py` com `load_config(path) -> dict` (ou dataclass) e um teste
  que carrega `config/base.yaml`.
- Crie `config/esperado.yaml` com os valores que as verificações do Colab conferem, copiados do
  [data-model › Tamanho e prevalência](../data-model.md#tamanho-e-prevalência) e dos
  [eventos por região](../data-model.md#eventos-por-região-e-subgrupo): população e eventos por
  ano de 2022–23, total do desenvolvimento, eventos por região do desenvolvimento e o fluxograma de
  exclusão. **Não** inclua números de 2024 aqui (R1); os de 2024 entram só na T-5.1.
- Crie `src/dengue_sinan/verify.py` (D-56) com:
  - `check(nome, esperado, obtido, tolerancia=0) -> dict` → `{"nome", "esperado", "obtido",
    "tolerancia", "passou"}`;
  - `write_report(tarefa, checks, out_dir, cfg) -> Path`: grava `out_dir/<tarefa>.json` no formato
    de [contracts › Relatório de verificação](../contracts/interfaces.md#relatório-de-verificação),
    com `"passou"` = todos os checks passaram; recusa valores que não sejam número, texto ou
    booleano (garante R7: só agregados);
  - `update_session_report(path, bloco, checks, cfg) -> Path` (D-57): cria ou reescreve o bloco
    `bloco` do relatório de sessão sem apagar os outros, e recalcula o `"passou"` geral (todos os
    blocos passaram e a sessão terminou);
  - `show_report(path) -> str` (D-64): imprime o conteúdo de um arquivo de texto (o JSON ou outro
    arquivo de agregados) e o SHA-256 dos bytes, e devolve o hash. É o que o agente lê pelo MCP do
    Colab para salvar a cópia local e conferir;
  - `environment(cfg) -> list[dict]` (D-64): checks de GPU (nome) e RAM total contra
    `cfg["ambiente"]`, mais o nº de vCPUs só como registro;
  - testes: um check que passa e um que falha; o JSON lido de volta tem o mesmo conteúdo; uma
    lista ou DataFrame como `obtido` levanta erro; atualizar um bloco preserva os demais;
    `show_report` devolve o mesmo SHA-256 que `hashlib` calcula sobre o arquivo; `environment`
    reprova RAM abaixo do mínimo (com valores simulados).
- **Dados no PC local (D-66):** baixe 2022 e 2023 com `download.fetch_year(ano, "data")`. Não baixe
  2024 no PC (R1). `data/` está no `.gitignore`.
- **Mesmo snapshot do Drive (D-72):** compare o `sha256_dbc` de cada ano no `data/manifest.json` com
  o do profiling (`profiling/RESULTADOS.md`, seção "0. Manifesto dos dados", que mostra os 16
  primeiros caracteres). Se não bater, o DataSUS revisou o arquivo desde o profiling: **🛑 PARE E
  PERGUNTE** antes de seguir, porque o PC e o Colab usariam dados diferentes.
- `reports/` (incluindo `reports/verificacao/`) **fica versionado**, só com agregados. Antes de
  cada commit, confira R7: nenhuma tabela com linhas individuais e nenhuma célula com < 10 casos.
- Como rodar no Colab: [quickstart › Google Colab](../quickstart.md#google-colab). Não crie outro
  guia; se algum passo mudar, atualize o quickstart.
- **Pronto quando:** dependências instaladas; 2022 e 2023 em `data/`, com o `sha256_dbc` igual ao do
  profiling; `load_config` e `verify` testados; testes e ruff passam.

### [x] T-2.1 — Carregar a população em memória (`dataset.py`)

- Arquivo: `src/dengue_sinan/dataset.py`.
- Função: `load_population(cfg, anos: list[int]) -> pd.DataFrame`.
  - Lê só as colunas necessárias (as do [dicionário de features](../data-model.md#dicionário-de-features)
    + `CLASSI_FIN`, `EVOLUCAO`, `NU_IDADE_N`, `ANO_NASC`, `DT_SIN_PRI`, `DT_NOTIFIC`, `CS_SEXO`,
    `CS_GESTANT`, `CS_RACA`, `ID_MN_RESI`, `SG_UF`) com `pyarrow.parquet.read_table(..., columns=...)`
    e `to_pandas(strings_to_categorical=True)`.
  - Adiciona `ANO`, aplica `population_mask`, depois `add_derived` (y, idade, faixa, região, gestante).
  - **Recebe a lista de anos explicitamente.** Sem default que inclua 2024 (R1).
- Função: `build_feature_frame(df) -> pd.DataFrame` que cria as colunas finais do dicionário de
  features (`sexo`, `n_comorbidades`, `dias_ate_notificacao` truncado, níveis Sim/Não/Ausente).
- **Checks de qualidade (FR-03)**, em `src/dengue_sinan/checks.py`, rodados **antes** do filtro
  de população ([data-model › Checks de qualidade](../data-model.md#checks-de-qualidade)); checks
  bloqueantes levantam `ValueError` com mensagem clara:
  - bloqueante: todas as colunas usadas existem em todos os anos;
  - bloqueante: `CLASSI_FIN` só tem valores em {0, 8, 10, 11, 12, branco} e `EVOLUCAO` só em
    {0, 1, 2, 3, 4, 9, branco} (domínio observado no profiling; valor novo = falha);
  - alerta (só registra, não falha): `DT_SIN_PRI` > `DT_NOTIFIC`; gestante com sexo M; "ignorado"
    > 50% em alguma comorbidade numa UF/ano;
  - idade inválida **não** é bloqueante: vira fallback/exclusão (D-49, D-50).
- **Fluxograma (FR-02):** `load_population` grava `reports/fluxograma.md` com
  `profiling.exclusion_flow` e `profiling.exclusion_reasons` (contagem após cada filtro, por ano).
- Testes (`tests/test_dataset.py`, `tests/test_checks.py`) com DataFrame sintético: níveis com 3
  categorias; `n_comorbidades`; truncamento de dias em 60 e negativos em 0; check bloqueante
  falha com `CLASSI_FIN` = "1"; alerta não interrompe; `load_population` falha se `anos` incluir
  2024 quando chamada pelas funções de treino (ver T-2.2).
- **Pronto quando:** testes passam e `reports/verificacao/T-2.1.json`, gerado no PC local
  ([Verificação no Colab](00-como-usar.md#verificação-no-colab), D-66), tem `"passou": true` para: total de
  **2.453.208** casos e **3.985** eventos com `anos=[2022, 2023]` e cada etapa do fluxograma igual
  à de `profiling/RESULTADOS.md`.

### [x] T-2.2 [P] — Guarda contra uso do teste (`guard.py`)

- Arquivo: `src/dengue_sinan/guard.py`.
- `assert_dev_only(df)`: levanta `RuntimeError("2024 é teste congelado (R1)")` se `df["ANO"]`
  contiver o ano de teste.
- Chame `assert_dev_only` no início de **toda** função de treino, tuning, calibração, limiar e
  seleção (T-2.4 em diante).
- Teste: passa com 2022–23; falha com qualquer linha de 2024.
- **Pronto quando:** teste passa e `grep -rn "assert_dev_only" src/` mostra a chamada em cada
  função de treino criada até aqui.

### [x] T-2.3 — Dobras leave-one-region-out e validação interna (`folds.py`)

- Arquivo: `src/dengue_sinan/folds.py`.
- `loro_folds(cfg, df) -> list[tuple[str, np.ndarray, np.ndarray]]` (`cfg` para ler `ordem_dobras`;
  `load_population` devolve também `LINHA`, o nº da linha no Parquet do ano, para o id): para cada região
  (Norte, Nordeste, Centro-Oeste, Sudeste, Sul), devolve `(regiao, idx_treino, idx_validacao)`.
  Linhas com `regiao` nula: **🛑 PARE E PERGUNTE** se existirem (o profiling não mostrou nenhuma).
- `inner_split(idx_treino, y, frac, seed) -> (idx_ajuste, idx_parada)`: 10% estratificado pelo alvo
  (`StratifiedShuffleSplit`), só dentro das 4 regiões de treino (R6).
- As dobras saem **sempre na ordem `cfg.ordem_dobras`** (Sudeste → Norte, da região com mais eventos
  para a com menos), para a poda do Optuna decidir com as dobras mais estáveis (D-53).
- `save_folds(cfg, df, caminho) -> str` grava em Parquet, por linha: id (ano do arquivo + nº da
  linha no arquivo), dobra de validação e a flag de validação interna de cada dobra. Devolve o
  **hash do conteúdo** (D-72), e não dos bytes do arquivo: SHA-256 de um CSV canônico (colunas em
  ordem fixa, linhas ordenadas por ano e linha, sem índice), para que o mesmo conteúdo dê o mesmo
  hash no PC e no Colab, com qualquer versão do pyarrow. `folds_hash(df_folds) -> str` calcula esse
  hash; `load_folds(caminho, hash_esperado)` levanta erro se o hash não bater. Todos os modelos usam
  essas mesmas dobras (D-53).
- Testes: 5 dobras; nenhuma interseção treino/validação; cada linha aparece em exatamente uma
  validação; a validação de cada dobra só tem uma região; `inner_split` preserva a prevalência
  (diferença < 0,01 pp em dados sintéticos grandes); `folds_hash` é igual para o mesmo conteúdo com
  as linhas embaralhadas e muda quando uma linha troca de dobra; duas execuções com a mesma semente
  dão o mesmo hash.
- **Pronto quando:** testes passam e `reports/verificacao/T-2.3.json`, gerado no PC local (D-66),
  tem `"passou": true` para os
  [eventos por região](../data-model.md#eventos-por-região-e-subgrupo) em cada dobra, e registra o
  hash do conteúdo das dobras e o `sha256_dbc` de 2022 e 2023 do `data/manifest.json`. São os
  valores que a sessão do Colab confere (T-4.3b).

### [x] T-2.4 [P] — Métricas (`metrics.py`)

- Arquivo: `src/dengue_sinan/metrics.py`. Funções puras, testadas com casos pequenos calculados à mão:
  - `pr_auc(y, p)`, `roc_auc(y, p)`, `brier(y, p)`;
  - `calibration_slope_intercept(y, p)`: logística de `y` em `logit(p)`; slope = coeficiente,
    intercept = intercepto com `logit(p)` como offset (calibration-in-the-large). Use `statsmodels`;
  - `threshold_metrics(y, p, limiar) -> dict` com acurácia, precisão, recall, F1, F2;
  - `best_f2_threshold(y, p) -> float` (varre os valores únicos de `p` ou uma grade fina);
  - `net_benefit(y, p, limiares) -> DataFrame` com colunas `limiar`, `modelo`, `tratar_todos`
    (`tratar_ninguem` = 0). Fórmula: NB = VP/n − FP/n × (pt / (1 − pt));
  - `bootstrap_ci(fn, y, p, n, seed) -> (estimativa, ic_inf, ic_sup)` com reamostragem estratificada;
  - `paired_bootstrap_diff(fn, y, p_a, p_b, dobra, n, seed) -> (diferenca, ic_inf, ic_sup)`: em cada
    reamostra, sorteia **os mesmos índices** para os dois modelos (estratificado por dobra e alvo),
    calcula `fn` por dobra, tira a média das 5 e guarda `média_a − média_b` (D-53).
- Testes: F2 de um exemplo conhecido; PR-AUC de preditor perfeito = 1; preditor constante tem
  PR-AUC = prevalência; slope = 1 e intercept = 0 para probabilidades perfeitamente calibradas
  (simuladas); net benefit de "tratar todos" bate com a fórmula; `paired_bootstrap_diff` com
  `p_a == p_b` dá diferença 0 e IC [0, 0].
- **Pronto quando:** testes passam.

### [x] T-2.5 [P] — Rastreamento (`tracking.py`)

- Arquivo: `src/dengue_sinan/tracking.py`.
- `start_run(cfg, nome, tags)`: abre run no MLflow (`tracking_uri` = pasta `mlruns` do config),
  registra `config` inteiro, `seed`, hashes do `manifest.json` (`sha256_dbc`, `sha256_parquet`
  por ano), commit do git (`git rev-parse HEAD`), hardware (CPU, RAM, GPU se houver).
- `log_fold_metrics(regiao, metricas)` e `log_oof_predictions(...)` — predições fora da dobra (OOF)
  salvas como artefato Parquet **no Drive, nunca no git** (R7).
- **Pronto quando:** um run de teste aparece em `mlflow ui` com config, hashes e commit.

### [x] T-2.6 — Análise descritiva e contagem de combinações (`descriptive.py`)

FR-18, D-52. Só 2022–23 (chame `assert_dev_only`). Inclui a antiga T-2.7 (D-60).

- **Tabela de características** por desfecho (`y = 0` vs `y = 1`): idade (mediana, IQR), sexo,
  gestação, raça/cor, cada comorbidade, nº de comorbidades.
- **Risco bruto** de `y = 1` com IC 95% (Wilson) por comorbidade, por nº de comorbidades (0, 1, 2,
  3+) e por faixa etária. Gráficos (matplotlib) desses riscos em `reports/descritiva/`. No topo da
  tabela: "riscos brutos, descritivos; não substituem o E1".
- **Pares:** `pair_event_counts(df) -> DataFrame` com, para cada um dos 21 pares, nº de casos e de
  eventos com **as duas** comorbidades = Sim. Publicado em `reports/descritiva/pares_comorbidades.md`;
  a contagem completa de eventos fica guardada para a T-3.1.
- **Combinações de 3+:** `combination_counts(df) -> DataFrame` com **cada combinação exata** de 3
  ou mais comorbidades = Sim que apareça nos dados (até 99 possíveis): nº de casos e de eventos.
  Define as linhas "3 ou mais" da tabela de perfis (T-3.5). Guardada em arquivo interno.
- Em tudo que é publicado, suprimir células com < 10 casos (R7).
- **Pronto quando:** `reports/descritiva/tabela1.md`, `riscos_brutos.md`, `pares_comorbidades.md`
  e os PNGs existem; nenhuma célula < 10 casos aparece; testes do IC de Wilson, da supressão e das
  contagens de pares e combinações passam; o Registro de execução anota quantos pares têm
  **≥ 10 eventos** (as únicas interações reportadas no E1) e quantas combinações de 3+ têm
  **≥ 10 casos** (entram nos perfis).

### ~~[ ] T-2.7 — Eventos por par de comorbidades~~

Fundida na T-2.6 (D-60).

### [x] T-2.8 — Baselines B0, B1, B2 (FR-04) (`baselines.py`)

- Arquivo: `src/dengue_sinan/baselines.py`.
- **B0:** prevê a prevalência do treino de cada dobra para todos.
- **B1:** logística **sem** penalização (`LogisticRegression(penalty=None)` ou `statsmodels`),
  features: spline de idade, sexo, gestante, 7 comorbidades (**sem** `n_comorbidades`, D-62).
  Dentro de `Pipeline` (R5). Sem pesos de classe (R3).
- **B2:** regra do protocolo (binária), "alto risco" se **qualquer**:
  idade < 2 anos **ou** > 65; `gestante` = 1; ≥ 1 comorbidade = Sim; `LACO` = Sim **ou**
  `PETEQUIA_N` = Sim. Implementar como função pura `rule_b2(df) -> np.ndarray[bool]` com teste.
- Para B0 e B1: rodar as 5 dobras leave-one-region-out, guardar predições OOF, calcular PR-AUC,
  Brier, ROC-AUC, slope/intercept por dobra e no OOF agrupado.
- Para B2: recall, precisão, F2 no OOF (é regra, sem PR-AUC).
- Registrar tudo no MLflow (T-2.5).
- **Pronto quando:** PR-AUC OOF de B0 ≈ prevalência (~0,0016); B1 com PR-AUC > B0; métricas de B2
  calculadas; tabela `reports/baselines.md` com os três; MLflow com 3 runs.
