# Tarefas — Fases 1 e 2 — Setup e Fundação (Marco 2)

> **Leia antes:** [00-como-usar.md](00-como-usar.md) — regras (§0, R1–R10), referência rápida (§1),
> dependências (§7b) e os registros §9 e §10, que ficam **lá**, não neste arquivo. Os §0, §1, §7b,
> §9 e §10 citados abaixo são daquele arquivo.

---

## 2. Fases 1 e 2 — Setup e Fundação (Marco 2: descrição, split e baselines)

T-2.0 é a **Fase 1 (Setup)**. T-2.1 a T-2.8 são a **Fase 2 (Fundação)**: bloqueiam todas as histórias.

Objetivo: descrever a população e fixar o piso. Spec: FR-04, FR-17, FR-18, §3.10.
Critério de saída do marco (spec §3.18): análise descritiva gerada; dobras construídas; métricas
OOF de B0, B1, B2 no MLflow; eventos por par de comorbidades contados; **2024 intocado**.

### [ ] T-2.0 — Dependências e configuração

- **🛑 PARE E PERGUNTE** antes de instalar. Proposta para o Programador aprovar:
  - runtime: `scikit-learn`, `statsmodels` (E1 com IC), `xgboost`, `catboost`, `optuna`, `mlflow`,
    `shap`, `pyyaml`, `matplotlib`, `streamlit`;
  - MLP: **`torch` (PyTorch), com GPU** — já decidido (D-51). Os 6 modelos rodam numa **sessão
    única** do Colab com GPU (D-53). O código escolhe o dispositivo sozinho (`"cuda"` se houver, senão `"cpu"`), para continuar
    executável no Colab gratuito (D-44);
  - TabFM: pacote/versão só depois de T-4.7.
- Depois do "ok": `uv add <pacotes>`; rode `uv run pytest -q` (os 48 testes atuais devem passar).
  Esperado: o `mlflow` exige `pyarrow<26`, então o `uv add` rebaixa o pyarrow para 25.x. Não é erro
  e não precisa ir para a §10.
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
  ```
- Crie `src/dengue_sinan/config.py` com `load_config(path) -> dict` (ou dataclass) e um teste
  que carrega `config/base.yaml`.
- Crie `config/esperado.yaml` com os valores que as verificações do Colab conferem, copiados de
  `profiling/RESULTADOS.md` (3ª execução): população e eventos por ano de 2022–23, total do
  desenvolvimento (2.453.208 casos, 3.985 eventos), eventos por região do desenvolvimento e o
  fluxograma de exclusão. **Não** inclua números de 2024 aqui (R1); os de 2024 entram só na T-5.1.
- Crie `src/dengue_sinan/verify.py` (D-56) com:
  - `check(nome, esperado, obtido, tolerancia=0) -> dict` → `{"nome", "esperado", "obtido",
    "tolerancia", "passou"}`;
  - `write_report(tarefa, checks, out_dir, cfg) -> Path`: grava `out_dir/<tarefa>.json` no formato
    de [contracts/interfaces.md](../contracts/interfaces.md) ("Relatório de verificação"), com
    `"passou"` = todos os checks passaram; recusa valores que não sejam número, texto ou booleano
    (garante R7: só agregados).
  - `update_session_report(path, bloco, checks, cfg) -> Path` (D-57): cria ou reescreve o bloco
    `bloco` do relatório de sessão sem apagar os outros, e recalcula o `"passou"` geral (todos os
    blocos passaram e a sessão terminou);
  - Testes: um check que passa e um que falha; o JSON lido de volta tem o mesmo conteúdo; uma
    lista ou DataFrame como `obtido` levanta erro; atualizar um bloco preserva os demais.
- `reports/verificacao/` fica versionado (só agregados).
- `reports/` **fica versionado** (só agregados). Antes de cada commit, confira R7: nenhuma tabela com
  linhas individuais e nenhuma célula com < 10 casos.
- **Como rodar no Colab:** o guia é o [quickstart.md](../quickstart.md) §2 (não crie outro arquivo; se
  mudar algum passo, atualize o quickstart). Resumo:
  1. montar o Drive; 2. `git clone` do repositório e `pip install -e .` (ou `uv sync`);
  2b. conferir a GPU: `nvidia-smi` e `python -c "import torch; print(torch.__version__,
     torch.cuda.is_available())"`. Se der `False` numa VM com GPU, **🛑 PARE E PERGUNTE**: o lock
     usa torch com CUDA 13, e o driver do Colab pode não suportar (spec `[VERIFY]`, NFR-01);
  3. apontar `caminhos.dados` e `caminhos.mlruns` do config para a pasta do Drive;
  4. chamar as funções de `src/` (notebooks não contêm lógica, só chamadas);
  5. ao terminar a sessão, desconectar o ambiente (NFR-01, para não gastar unidades com GPU ociosa).
- **Pronto quando:** dependências instaladas com aprovação; `load_config` testado; testes e ruff passam.

### [ ] T-2.1 — Carregar a população em memória (`dataset.py`)

- Arquivo: `src/dengue_sinan/dataset.py`.
- Função: `load_population(cfg, anos: list[int]) -> pd.DataFrame`.
  - Lê só as colunas necessárias (lista da §1.3 + `CLASSI_FIN`, `EVOLUCAO`, `NU_IDADE_N`,
    `ANO_NASC`, `DT_SIN_PRI`, `DT_NOTIFIC`, `CS_SEXO`, `CS_GESTANT`, `CS_RACA`, `ID_MN_RESI`, `SG_UF`)
    com `pyarrow.parquet.read_table(..., columns=...)` e `to_pandas(strings_to_categorical=True)`.
  - Adiciona `ANO`, aplica `population_mask`, depois `add_derived` (y, idade, faixa, região, gestante).
  - **Recebe a lista de anos explicitamente.** Sem default que inclua 2024 (R1).
- Função: `build_feature_frame(df) -> pd.DataFrame` que cria as colunas finais da §1.3
  (`sexo`, `n_comorbidades`, `dias_ate_notificacao` truncado, níveis Sim/Não/Ausente).
- **Checks de qualidade (FR-03)**, em `src/dengue_sinan/checks.py`, rodados **antes** do filtro
  de população; checks bloqueantes levantam `ValueError` com mensagem clara:
  - bloqueante: todas as colunas usadas existem em todos os anos;
  - bloqueante: `CLASSI_FIN` só tem valores em {0, 8, 10, 11, 12, branco} e `EVOLUCAO` só em
    {0, 1, 2, 3, 4, 9, branco} (domínio observado no profiling; valor novo = falha);
  - alerta (só registra, não falha): `DT_SIN_PRI` > `DT_NOTIFIC`; gestante com sexo M; "ignorado"
    > 50% em alguma comorbidade numa UF/ano.
  - Idade inválida **não** é bloqueante: vira fallback/exclusão (D-49, D-50).
- **Fluxograma (FR-02):** `load_population` grava `reports/fluxograma.md` com
  `profiling.exclusion_flow` e `profiling.exclusion_reasons` (contagem após cada filtro, por ano).
- Testes (`tests/test_dataset.py`, `tests/test_checks.py`) com DataFrame sintético: níveis 3
  categorias; `n_comorbidades`; truncamento de dias em 60 e negativos em 0; check bloqueante
  falha com `CLASSI_FIN` = "1"; alerta não interrompe; `load_population` falha se `anos` incluir
  2024 quando chamada pelas funções de treino (ver T-2.2).
- **Pronto quando:** testes passam e `reports/verificacao/T-2.1.json` (gerado no Colab, §0 item
  2b) tem `"passou": true` para: total de **2.453.208** casos e **3.985** eventos com
  `anos=[2022, 2023]` (§1.2) e cada etapa do fluxograma igual à de `profiling/RESULTADOS.md`.

### [ ] T-2.2 [P] — Guarda contra uso do teste (`guard.py`)

- Arquivo: `src/dengue_sinan/guard.py`.
- `assert_dev_only(df)`: levanta `RuntimeError("2024 é teste congelado (R1)")` se `df["ANO"]`
  contiver o ano de teste.
- Chame `assert_dev_only` no início de **toda** função de treino, tuning, calibração, limiar e
  seleção (T-2.4 em diante).
- Teste: passa com 2022–23; falha com qualquer linha de 2024.
- **Pronto quando:** teste passa e `grep -rn "assert_dev_only" src/` mostra a chamada em cada
  função de treino criada até aqui.

### [ ] T-2.3 — Dobras leave-one-region-out e validação interna (`folds.py`)

- Arquivo: `src/dengue_sinan/folds.py`.
- `loro_folds(df) -> list[tuple[str, np.ndarray, np.ndarray]]`: para cada região
  (Norte, Nordeste, Centro-Oeste, Sudeste, Sul), devolve `(regiao, idx_treino, idx_validacao)`.
  Linhas com `regiao` nula: **🛑 PARE E PERGUNTE** se existirem (o profiling não mostrou nenhuma).
- `inner_split(idx_treino, y, frac, seed) -> (idx_ajuste, idx_parada)`: 10% estratificado pelo alvo
  (`StratifiedShuffleSplit`), só dentro das 4 regiões de treino (R6).
- As dobras saem **sempre na ordem `cfg.ordem_dobras`** (Sudeste → Norte, da região com mais eventos
  para a com menos), para a poda do Optuna decidir com as dobras mais estáveis (D-53).
- `save_folds(cfg, df, caminho) -> str` grava em Parquet, por linha: id, dobra de validação e a flag
  de validação interna de cada dobra; devolve o **hash** (sha256) do arquivo. `load_folds(caminho,
  hash_esperado)` levanta erro se o hash não bater. Todos os modelos usam esse mesmo arquivo (D-53).
- Testes: 5 dobras; nenhuma interseção treino/validação; cada linha aparece em exatamente uma
  validação; a validação de cada dobra só tem uma região; `inner_split` preserva a prevalência
  (diferença < 0,01 pp em dados sintéticos grandes).
- **Pronto quando:** testes passam e `reports/verificacao/T-2.3.json` tem `"passou": true` para os
  eventos por dobra de §1.2 e para o hash do arquivo de dobras salvo.

### [ ] T-2.4 [P] — Métricas (`metrics.py`)

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

### [ ] T-2.5 [P] — Rastreamento (`tracking.py`)

- Arquivo: `src/dengue_sinan/tracking.py`.
- `start_run(cfg, nome, tags)`: abre run no MLflow (`tracking_uri` = pasta `mlruns` do config),
  registra `config` inteiro, `seed`, hashes do `manifest.json` (`sha256_dbc`, `sha256_parquet`
  por ano), commit do git (`git rev-parse HEAD`), hardware (CPU, RAM, GPU se houver).
- `log_fold_metrics(regiao, metricas)` e `log_oof_predictions(...)` — OOF salvo como artefato
  Parquet **no Drive, nunca no git** (R7).
- **Pronto quando:** um run de teste aparece em `mlflow ui` com config, hashes e commit.

### [ ] T-2.6 — Análise descritiva (FR-18) (`descriptive.py`)

- Arquivo: `src/dengue_sinan/descriptive.py`. Só 2022–23 (chame `assert_dev_only`).
- Tabela de características por desfecho (`y = 0` vs `y = 1`): idade (mediana, IQR), sexo,
  gestação, raça/cor, cada comorbidade, nº de comorbidades.
- Risco bruto de `y = 1` com IC 95% (Wilson) por comorbidade, por nº de comorbidades (0, 1, 2, 3+)
  e por faixa etária.
- Gráficos (matplotlib) desses riscos, salvos em `reports/descritiva/`.
- Suprimir células com < 10 casos (R7).
- Escrever no topo da tabela: "riscos brutos, descritivos; não substituem o E1".
- **Pronto quando:** `reports/descritiva/tabela1.md`, `riscos_brutos.md` e os PNGs existem; nenhuma
  célula < 10 casos aparece; teste unitário do IC de Wilson e da supressão passa.

### [ ] T-2.7 — Eventos por par de comorbidades

- Em `descriptive.py`: `pair_event_counts(df) -> DataFrame` com, para cada um dos 21 pares,
  nº de casos e de eventos com **as duas** comorbidades = Sim (2022–23).
- Salvar em `reports/descritiva/pares_comorbidades.md` (suprimir < 10 casos na publicação, mas
  guardar a contagem de eventos para T-3.1).
- Também `combination_counts(df) -> DataFrame` com **cada combinação exata** de 3 ou mais
  comorbidades = Sim que apareça nos dados (até 99 possíveis): nº de casos e de eventos (2022–23).
  Ela define as linhas "3 ou mais" da tabela de perfis (T-3.5). Guardar em arquivo interno; na
  publicação, suprimir < 10 casos.
- **Pronto quando:** tabelas geradas; anote no §9 quantos pares têm **≥ 10 eventos** (serão as
  únicas interações reportadas no E1) e quantas combinações de 3+ têm **≥ 10 casos** (entram nos perfis).

### [ ] T-2.8 — Baselines B0, B1, B2 (FR-04) (`baselines.py`)

- Arquivo: `src/dengue_sinan/baselines.py`.
- **B0:** prevê a prevalência do treino de cada dobra para todos.
- **B1:** logística **sem** penalização (`LogisticRegression(penalty=None)` ou `statsmodels`),
  features: spline de idade, sexo, gestante, 7 comorbidades, `n_comorbidades`. Dentro de
  `Pipeline` (R5). Sem pesos de classe (R3).
- **B2:** regra do protocolo (binária), "alto risco" se **qualquer**:
  idade < 2 anos **ou** > 65; `gestante` = 1; ≥ 1 comorbidade = Sim; `LACO` = Sim **ou**
  `PETEQUIA_N` = Sim. Implementar como função pura `rule_b2(df) -> np.ndarray[bool]` com teste.
- Para B0 e B1: rodar as 5 dobras LORO, guardar predições OOF, calcular PR-AUC, Brier, ROC-AUC,
  slope/intercept por dobra e no OOF agrupado.
- Para B2: recall, precisão, F2 no OOF (é regra, sem PR-AUC).
- Registrar tudo no MLflow (T-2.5).
- **Pronto quando:** PR-AUC OOF de B0 ≈ prevalência (~0,0016); B1 com PR-AUC > B0; métricas de B2
  calculadas; tabela `reports/baselines.md` com os três; MLflow com 3 runs.
