# TODO — implementação do modelo (Marcos 2 a 7)

> Fonte da verdade: [specs.md](specs.md) (v0.13). Este arquivo só **traduz** o spec em tarefas.
> Se este TODO e o spec discordarem, **o spec vale** — pare e avise o Programador.
> Marco 1 (dados e profiling) está **concluído**: ver [profiling/RESULTADOS.md](profiling/RESULTADOS.md).

---

## 0. Como usar este arquivo (leia antes de qualquer tarefa)

1. Faça as tarefas **na ordem**. Cada tarefa tem um ID (`T-2.3`), os IDs do spec que ela cumpre,
   os arquivos a criar/alterar, os passos e um **critério de pronto**.
2. Uma tarefa só está pronta quando **todos** os itens do critério de pronto foram verificados
   rodando comandos, não "parece que funciona".
3. Ao terminar cada tarefa: marque `[x]`, rode `uv run pytest -q` e `uv run ruff check .`, e
   escreva uma linha em **§9 Registro de execução** no fim deste arquivo. Todo código novo vai em
   `src/dengue_sinan/` com teste em `tests/`; notebooks só chamam funções (NFR-05).
4. Quando o texto disser **🛑 PARE E PERGUNTE**, não continue: descreva as opções ao programador e
   espere a resposta. Nunca escolha sozinho.
4b. **Erro inesperado** (algo quebra, não converge, estoura memória, dá número estranho): registre
   **sempre** em **§10 Registro de problemas** antes de qualquer outra coisa. Depois:
   - pode tentar **correções técnicas** que não mudam nenhuma decisão do spec, e registrar cada
     tentativa e o resultado. Exemplos permitidos: aumentar iterações do otimizador, trocar o método
     numérico (`newton` → `lbfgs`), reduzir `batch_size`, liberar memória, reiniciar a sessão;
   - **🛑 PARE E PERGUNTE** se a correção exigir mudar algo decidido no spec. Exemplos proibidos sem
     perguntar: tirar uma variável ou interação, mudar a população, usar outro modelo, mexer em
     limiar, mexer no teste, corrigir desbalanceamento.
5. Não edite `specs.md` para "fazer caber" o seu código. Se o spec precisar mudar, pergunte.

### 0.1 Regras que nunca podem ser quebradas

| # | Regra | Por quê (spec) |
|---|---|---|
| R1 | **Os dados de 2024 (teste) não são lidos antes da T-5.1.** Nenhuma função de treino, tuning, calibração, limiar, seleção ou gráfico usa 2024. | §3.8, FR-09 |
| R2 | O teste é avaliado **uma única vez**. A T-5.1 grava um "lacre"; uma segunda execução deve falhar. | FR-09, D-36 |
| R3 | **Sem correção de desbalanceamento**: nada de `class_weight`, `scale_pos_weight`, `is_unbalance`, SMOTE ou undersampling. Única exceção: subamostra de negativos do Random Forest por falta de memória, com correção de probabilidade (T-4.4). | D-38 |
| R4 | Features permitidas são **só** as da lista de §1.3 deste TODO. Nada de UF, região, município, unidade, ano, semana, raça/cor, escolaridade, `ALRM_*`, `GRAV_*`, exames, `HOSPITALIZ`, `CRITERIO` etc. | §3.8, D-21, D-48 |
| R5 | Todo pré-processamento é ajustado **dentro** da dobra de treino, via `sklearn.Pipeline`. Nunca ajuste scaler/encoder/calibrador no conjunto todo. | §3.8, §3.9 |
| R6 | Early stopping usa a **validação interna** (10% das regiões de treino), nunca a região deixada de fora. | FR-22, §3.11 |
| R7 | Nenhum microdado (linha a linha) vai para o git, para o app ou para relatórios. Só agregados; células com < 10 casos são suprimidas. | NFR-03, §3.12 |
| R8 | Semente única do config em tudo que for aleatório. | §3.14, NFR-02 |
| R9 | O E1 é logística **sem penalização** (para ter IC). Penalização só no candidato "elastic net" do M1. | §3.11 |
| R10 | Ranking de comorbidades vem **só** dos OR do E1, nunca de SHAP ou importância de árvore. | FR-19, D-41 |

### 0.2 Decisões que você NÃO pode tomar (🛑 pergunte)

- Adicionar qualquer dependência ao `pyproject.toml` (a lista proposta está em T-2.0; precisa de "ok" do Programador).
- Qualquer item marcado `[OPEN QUESTION]` ou `[ASSUMPTION]` no spec que você precise mudar.
- Espaço de busca de hiperparâmetros (Q-08): a T-4.0 traz uma **proposta**; o Programador aprova.
- O que fazer se o TabFM não couber (limites, licença): T-4.7.
- Qual modelo vai para a demo se o melhor M1 não couber (Q-14): T-4.10.
- Mudar alvo, população, split, métrica, limiar, faixas etárias ou lista de features.

---

## 1. Referência rápida do spec (para não precisar reinterpretar)

### 1.1 Dados

- Parquets por ano no Drive: `MyDrive/dengue-comorbidity-risk/data/parquet/dengue_{ano}.parquet`
  (todas as colunas como **texto cru**), manifesto em `data/manifest.json`. Gerados por
  `src/dengue_sinan/download.py` (`fetch_year`), que já cumpre o **FR-01**. Colab gratuito tem
  ~12,7 GiB de RAM.
- **Ano do split = ano do arquivo** (D-46). Desenvolvimento = 2022 e 2023; teste = 2024.

### 1.2 População, alvo e idade (já implementados — reutilize, não reescreva)

| O quê | Regra | Função existente |
|---|---|---|
| População | `CLASSI_FIN` ∈ {10, 11, 12} **e** (`CLASSI_FIN` = 12 **ou** `EVOLUCAO` ∈ {1, 2}) **e** idade válida | `profiling.population_mask` |
| Alvo `y` | 1 se `CLASSI_FIN` = 12 **ou** `EVOLUCAO` = 2; senão 0 | `profiling.target` |
| Idade (anos) | `NU_IDADE_N` decodificado (1º dígito = unidade); se inválido ou fora de [0, 120], ano de `DT_SIN_PRI` − `ANO_NASC`; flag `idade_de_ano_nasc` | `features.age_years_with_fallback` |
| Região | 1º dígito do IBGE de `ID_MN_RESI` (senão `SG_UF`) → Norte, Nordeste, Sudeste, Sul, Centro-Oeste | `features.region_from_ibge` |
| Faixas etárias | 0–4, 5–14, 15–39, 40–59, 60–79, 80+ (só relatório/subgrupo/perfis) | `profiling.FAIXAS` |

Números esperados (3ª execução do profiling) — use para conferir o seu carregamento:

| | 2022 | 2023 | 2024 |
|---|---|---|---|
| População final | 1.148.299 | 1.304.909 | 5.331.745 |
| Eventos (y = 1) | 1.869 | 2.116 | 11.338 |

Eventos por região no desenvolvimento (2022–23): Centro-Oeste 736, Nordeste 582, Norte 121,
Sudeste 1.736, Sul 810 (total 3.985).

### 1.3 Features de M1 (lista fechada — R4)

| Feature | Origem | Tipo | Transformação |
|---|---|---|---|
| `idade_anos` | `age_years_with_fallback` | contínua | logística/MLP: spline (`SplineTransformer`, 5 nós `[ASSUMPTION]`) + escala; árvores: crua |
| `sexo` | `CS_SEXO` | categórica: M, F, I/branco → "I" | one-hot (logística/MLP); nativa/ordinal (árvores) |
| `gestante` | `CS_GESTANT` ∈ {1,2,3,4} | binária | 0/1 |
| 7 comorbidades | `DIABETES`, `HEMATOLOG`, `HEPATOPAT`, `RENAL`, `HIPERTENSA`, `ACIDO_PEPT`, `AUTO_IMUNE` | 3 níveis: Sim (1) / Não (2) / Ausente (resto) | one-hot (logística/MLP); ordinal/nativa (árvores) |
| `n_comorbidades` | soma de comorbidades = Sim | inteira 0–7 | crua |
| 12 sintomas | `FEBRE`, `MIALGIA`, `CEFALEIA`, `EXANTEMA`, `VOMITO`, `NAUSEA`, `DOR_COSTAS`, `CONJUNTVIT`, `ARTRITE`, `ARTRALGIA`, `DOR_RETRO`, `PETEQUIA_N` | 3 níveis | igual às comorbidades |
| `LEUCOPENIA`, `LACO` | item 33 | 3 níveis | igual às comorbidades |
| `dias_ate_notificacao` | `DT_NOTIFIC` − `DT_SIN_PRI` (dias) | contínua | truncar em [0, 60] |

⚠️ Cuidado com nomes parecidos: entram `PETEQUIA_N` e `LACO` (item 33). Ficam **fora** `PETEQUIAS`
e `LACO_N`, que são da classificação antiga de febre hemorrágica e funcionam como proxy do rótulo.

Features do **E1 / B1** (só perfil): `idade_anos` (spline), `sexo`, `gestante`, 7 comorbidades,
`n_comorbidades` (B1). Sem sintomas.

Colunas que o dataset guarda **só para dobras e subgrupos** (nunca entram no `X`): `ANO`,
`regiao`, `faixa_etaria`, `CS_RACA` (raça/cor), `idade_de_ano_nasc`.

### 1.4 Validação e métricas

- Dobras: **leave-one-region-out** nas 5 regiões, só com 2022–23. Em cada dobra: treina em 4
  regiões, prediz a 5ª ("fora da dobra", OOF).
- Métrica primária: **PR-AUC** (`average_precision_score`). Secundárias: Brier, calibration slope
  e intercept, ROC-AUC. No limiar: acurácia, precisão, recall, F1, **F2**.
- Limiar: o que **maximiza F2** nas predições OOF **calibradas** (D-33).
- Seleção: maior PR-AUC média nas 5 dobras; empate (< 0,005 ou ICs sobrepostos) → menor Brier;
  persistindo → mais simples: elastic net < RF < XGBoost/CatBoost < MLP < TabFM.
- Calibração: isotônica ou Platt nas predições OOF (escolher a de menor Brier OOF `[ASSUMPTION]`).
- Curva de decisão (net benefit): limiares de 0,1% a 5%.
- Bootstrap: 1.000 reamostras para métricas; 2.000 para bandas da curva de calibração.

---

## 2. Marco 2 — Descrição, split e baselines

Objetivo: descrever a população e fixar o piso. Spec: FR-04, FR-17, FR-18, §3.10.
Critério de saída do marco (spec §3.18): análise descritiva gerada; dobras construídas; métricas
OOF de B0, B1, B2 no MLflow; eventos por par de comorbidades contados; **2024 intocado**.

### [ ] T-2.0 — Dependências e configuração

- **🛑 PARE E PERGUNTE** antes de instalar. Proposta para o Programador aprovar:
  - runtime: `scikit-learn`, `statsmodels` (E1 com IC), `xgboost`, `catboost`, `optuna`, `mlflow`,
    `shap`, `pyyaml`, `matplotlib`, `streamlit`;
  - MLP: **`torch` (PyTorch), com GPU** — já decidido (D-51). A sessão do MLP roda no Colab Pro
    com GPU. O código escolhe o dispositivo sozinho (`"cuda"` se houver, senão `"cpu"`), para continuar
    executável no Colab gratuito (D-44);
  - TabFM: pacote/versão só depois de T-4.7.
- Depois do "ok": `uv add <pacotes>`; rode `uv run pytest -q` (os 48 testes atuais devem passar).
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
  orcamento_min: {elastic_net: 60, random_forest: 90, xgboost: 90, catboost: 90, mlp: 90, tabfm: 60}
  optuna: {max_tentativas: 50}
  ```
- Crie `src/dengue_sinan/config.py` com `load_config(path) -> dict` (ou dataclass) e um teste
  que carrega `config/base.yaml`.
- `reports/` **fica versionado** (só agregados). Antes de cada commit, confira R7: nenhuma tabela com
  linhas individuais e nenhuma célula com < 10 casos.
- **Como rodar no Colab** (crie `notebooks/colab_setup.md` com estes passos e use em todas as sessões):
  1. montar o Drive; 2. `git clone` do repositório e `pip install -e .` (ou `uv sync`);
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
- **Pronto quando:** rodando no Colab com `anos=[2022, 2023]`, o total é **2.453.208** casos e
  **3.985** eventos (§1.2), e o fluxograma bate com o de `profiling/RESULTADOS.md`. Anote os
  números no §9.

### [ ] T-2.2 — Guarda contra uso do teste (`guard.py`)

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
- Testes: 5 dobras; nenhuma interseção treino/validação; cada linha aparece em exatamente uma
  validação; a validação de cada dobra só tem uma região; `inner_split` preserva a prevalência
  (diferença < 0,01 pp em dados sintéticos grandes).
- **Pronto quando:** testes passam e, no Colab, os eventos por dobra batem com §1.2.

### [ ] T-2.4 — Métricas (`metrics.py`)

- Arquivo: `src/dengue_sinan/metrics.py`. Funções puras, testadas com casos pequenos calculados à mão:
  - `pr_auc(y, p)`, `roc_auc(y, p)`, `brier(y, p)`;
  - `calibration_slope_intercept(y, p)`: logística de `y` em `logit(p)`; slope = coeficiente,
    intercept = intercepto com `logit(p)` como offset (calibration-in-the-large). Use `statsmodels`;
  - `threshold_metrics(y, p, limiar) -> dict` com acurácia, precisão, recall, F1, F2;
  - `best_f2_threshold(y, p) -> float` (varre os valores únicos de `p` ou uma grade fina);
  - `net_benefit(y, p, limiares) -> DataFrame` com colunas `limiar`, `modelo`, `tratar_todos`
    (`tratar_ninguem` = 0). Fórmula: NB = VP/n − FP/n × (pt / (1 − pt));
  - `bootstrap_ci(fn, y, p, n, seed) -> (estimativa, ic_inf, ic_sup)` com reamostragem estratificada.
- Testes: F2 de um exemplo conhecido; PR-AUC de preditor perfeito = 1; preditor constante tem
  PR-AUC = prevalência; slope = 1 e intercept = 0 para probabilidades perfeitamente calibradas
  (simuladas); net benefit de "tratar todos" bate com a fórmula.
- **Pronto quando:** testes passam.

### [ ] T-2.5 — Rastreamento (`tracking.py`)

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

---

## 3. Marco 3 — Modelo explicativo (E1)

Spec: FR-05, FR-06, FR-19, §3.11, §3.13, D-40, D-41. Ajustado em 2022–23 (todos os dados de
desenvolvimento, sem dobras — é inferência, não predição).

### [ ] T-3.1 — Ajustar o E1 (`explain.py`)

- Arquivo: `src/dengue_sinan/explain.py`. Use `statsmodels` (`smf.logit` ou `sm.GLM` binomial)
  para ter matriz de covariância (R9: sem penalização).
- Fórmula: `y ~ cr(idade_anos, df=5) + sexo + gestante + <7 comorbidades Sim/Não> +
  <interações 2 a 2 entre comorbidades> + HIPERTENSA:cr(idade_anos, df=3) +
  DIABETES:cr(idade_anos, df=3)`. Graus de liberdade dos splines `[ASSUMPTION]`.
- **Interações:** inclua só os pares com **≥ 10 eventos** (T-2.7). Os demais pares não entram
  no modelo e são listados como "eventos insuficientes".
- Comorbidade "Ausente": é ~0% na população. Trate como categoria de referência à parte ou
  🛑 PERGUNTE se a contagem for > 0 e o modelo não convergir.
- Se o ajuste não convergir: registre em §10 e tente só correções técnicas (regra 4b: mais iterações,
  outro método de otimização). Se ainda não convergir, **🛑 PARE E PERGUNTE**. Nunca remova termos
  por conta própria.
- **Pronto quando:** modelo converge; resumo salvo em `reports/e1/coeficientes.md`; tempo de ajuste anotado no §9.

### [ ] T-3.2 — OR, IC e correção múltipla

- Para cada comorbidade: OR do efeito principal com IC 95%.
- Para cada par incluído: OR da interação com IC 95% e p-valor; **Benjamini-Hochberg** (FDR 5%)
  nos pares. Reportar p ajustado.
- No relatório, interpretar **tamanho do efeito e IC**, não p-valor (spec §3.11).
- **Pronto quando:** `reports/e1/or_interacoes.md` existe com OR, IC, p e p ajustado.

### [ ] T-3.3 — Interação aditiva: RERI e AP (FR-05, D-40)

- Para cada par incluído (A, B): calcule, a partir do E1 (mesma idade/sexo de referência),
  `OR_A`, `OR_B`, `OR_AB` contra "nenhuma das duas";
  `RERI = OR_AB − OR_A − OR_B + 1`; `AP = RERI / OR_AB`.
- IC 95% pelo **método delta** usando a covariância dos coeficientes (ou bootstrap de 1.000).
- Teste unitário com coeficientes inventados: RERI e AP batem com a conta à mão.
- **Pronto quando:** `reports/e1/reri_ap.md` com RERI, AP e IC de cada par.

### [ ] T-3.4 — Ranking de comorbidades (FR-19)

- Ordenar as 7 comorbidades pelo OR do efeito principal.
- Duas comorbidades com IC sobrepostos ficam marcadas **"sem ordem definida"** entre si.
- Fonte: só E1 (R10).
- **Pronto quando:** `reports/e1/ranking.md` existe e teste unitário da lógica de sobreposição passa.

### [ ] T-3.5 — Tabela de perfis (FR-06)

- Perfis (D-52) — **todas as comorbidades**, gerados automaticamente (não escreva a lista à mão):
  1. sem comorbidades (referência);
  2. cada uma das **7 comorbidades sozinha**;
  3. cada **par** de comorbidades que entrou no E1 (os pares com ≥ 10 eventos, T-2.7); os pares
     que não entraram aparecem na tabela como "dados insuficientes";
  4. **3 ou mais:** **todas** as combinações de 3+ comorbidades que tenham ≥ 10 casos em 2022–23
     (sem limite fixo; a contagem vem da T-2.7), cada uma nomeada pelas doenças que contém. Cada
     linha leva a nota: "risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem
     termo próprio para o trio".
- Para cada perfil × faixa etária (idade no meio da faixa) × sexo (F e M separados `[ASSUMPTION]`):
  risco previsto pelo E1 com IC 95% (método delta na escala logit e depois transformar) e razão
  contra "sem comorbidades" na mesma faixa e sexo.
- Suprimir perfis cuja célula observada tenha < 10 casos (R7).
- A tabela completa vai para `reports/e1/perfis_completo.md`. O relatório mostra uma versão curta
  (faixa 60–79, os perfis mais frequentes) e aponta para a completa. A demo calcula **qualquer**
  combinação pelo E1, mesmo as que não estão na tabela.
- **Pronto quando:** `reports/e1/perfis_completo.md` no formato do spec §3.15, com os 4 grupos de
  perfis acima; teste unitário confirma que a lista de perfis é gerada a partir dos pares do E1.

### [ ] T-3.6 — Serializar o E1 (FR-12)

- Arquivo: `src/dengue_sinan/artifacts.py`. `save_bundle(obj, caminho, metadados)` e
  `load_bundle(caminho)`.
- Metadados obrigatórios: versão do código (commit), hashes dos dados, config, data de treino,
  métricas de validação, lista de features, versão das bibliotecas.
- O artefato do E1 guarda os coeficientes e a covariância (para IC na demo), **sem dados**.
- **Pronto quando:** `load_bundle` recupera o modelo e reproduz o risco de um perfil com diferença < 1e-9.

---

## 4. Marco 4 — Modelos preditivos (M1)

Spec: FR-07, FR-08, FR-12, FR-13, FR-17, FR-22, NFR-01, §3.11, D-32, D-36, D-37, D-42, D-43.
Tudo em 2022–23 (R1). **Uma sessão do Colab por modelo** (NFR-01).

### [ ] T-4.0 — Espaço de busca (Q-08) — 🛑 aprovação do Programador

Proposta (registrar no `config/base.yaml` depois do "ok"):

| Modelo | Hiperparâmetros e faixas propostas |
|---|---|
| Elastic net (`LogisticRegression(penalty="elasticnet", solver="saga")`) | `C` log [1e-3, 10]; `l1_ratio` [0, 1] |
| Random Forest | `n_estimators` [200, 800]; `max_depth` [4, 20] ou None; `min_samples_leaf` [10, 500] log; `max_features` {"sqrt", 0.3, 0.5} |
| XGBoost (`tree_method="hist"`) | `learning_rate` log [0.01, 0.3]; `max_depth` [3, 10]; `min_child_weight` log [1, 100]; `subsample` [0.5, 1]; `colsample_bytree` [0.5, 1]; `reg_lambda` log [1e-3, 10]; `n_estimators` até 2000 com early stopping |
| CatBoost | `learning_rate` log [0.01, 0.3]; `depth` [4, 10]; `l2_leaf_reg` log [1, 30]; `iterations` até 3000 com early stopping |
| MLP (PyTorch, GPU) | camadas ocultas {[64], [128], [128, 64]}; `dropout` [0, 0.3]; `weight_decay` log [1e-6, 1e-2]; `lr` log [1e-4, 1e-2] (Adam); `batch_size` {1024, 4096}; épocas até 200 com early stopping. Perda: `BCEWithLogitsLoss` **sem `pos_weight`** (R3) |
| TabFM | sem busca |

Nenhum parâmetro de peso de classe (R3).

### [ ] T-4.1 — Pré-processamento por família (`preprocess.py`)

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

### [ ] T-4.2 — Laço de validação com early stopping (`cv.py`)

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

### [ ] T-4.3 — Busca com Optuna (`tuning.py`) (D-43, NFR-01)

- `tune(cfg, modelo, df)`:
  - `optuna.create_study(direction="maximize", sampler=TPESampler(seed=cfg.seed),
    pruner=MedianPruner(), storage="sqlite:///<Drive>/optuna/<modelo>.db", study_name=<modelo>,
    load_if_exists=True)` — busca **retomável**;
  - `study.optimize(objetivo, n_trials=50, timeout=orcamento_min*60)`;
  - objetivo: `run_loro` reportando a PR-AUC acumulada após cada dobra (`trial.report`) e podando
    com `trial.should_prune()`;
  - se nem uma tentativa completa couber no orçamento: busca em **subamostra estratificada pelo
    alvo** de cada dobra (mesma prevalência, R3) e anote isso no MLflow.
- Registre no MLflow: tempo gasto, tentativas concluídas e podadas, hardware.
- A melhor tentativa vai para o registro de modelos com alias **`melhor-validacao`** (FR-22).
  Tentativas piores nunca sobrescrevem.
- **Pronto quando:** interromper e rodar de novo continua o mesmo estudo (teste manual no Colab,
  anotado no §9).

### [ ] T-4.4 a T-4.8 — Um modelo por sessão

Para cada modelo: rode `tune`, depois `run_loro` com os melhores parâmetros, salve OOF e métricas.

- [ ] **T-4.4 Random Forest** (90 min). Se faltar memória: subamostra de negativos **só no treino
  da dobra**, depois corrija a probabilidade: `p' = p / (p + (1 − p) / taxa_amostragem)` e confira
  a calibração no OOF. Anote a taxa no MLflow.
- [ ] **T-4.5 XGBoost** (90 min). Sem `scale_pos_weight` (R3).
- [ ] **T-4.6 CatBoost** (90 min). Sem `auto_class_weights` (R3).
- [ ] **T-4.6b Elastic net** (60 min) e **MLP** (90 min, GPU do Colab Pro).
  - MLP em `src/dengue_sinan/mlp.py`: classe compatível com sklearn (`fit`, `predict_proba`) que
    envolve a rede PyTorch, para entrar no mesmo `Pipeline` (R5) e no mesmo `run_loro`.
  - Fixe as sementes do PyTorch (`torch.manual_seed`, `torch.cuda.manual_seed_all`) com a semente do
    config (R8) e registre o dispositivo usado no MLflow.
  - Teste unitário rápido em CPU com dados sintéticos: treina, para no early stopping e devolve
    probabilidades entre 0 e 1.
- [ ] **T-4.7 TabFM** (60 min, GPU).
  - **Antes de codar, 🛑 PARE E PERGUNTE** com estas informações do model card (spec `[VERIFY]`):
    licença dos pesos cobre uso acadêmico?; limite de linhas de contexto e de features; velocidade
    de predição; nome e versão do pacote.
  - Contexto = subamostra **estratificada** do treino de cada dobra, no tamanho do limite verificado.
  - Sem busca; calibração igual aos outros (T-4.9).
- [ ] **T-4.8 SHAP global (FR-13, SHOULD).** Para o melhor modelo de árvore: valores SHAP e SHAP
  interaction values numa subamostra estratificada de 50 mil linhas `[ASSUMPTION]` de 2022–23.
  Gráficos em `reports/shap/`. Legenda: "explica o modelo, não causa; instável com features
  correlacionadas". Não usar para ranking (R10).

**Pronto (para cada um) quando:** OOF salvo; PR-AUC média e por dobra no MLflow; melhores pontos
por dobra registrados; alias `melhor-validacao` presente.

### [ ] T-4.9 — Calibração, limiar e seleção (FR-08, FR-17, §3.11)

- Para cada modelo: ajustar **isotônica** e **Platt** nas predições OOF (2022–23); escolher a de
  menor Brier OOF. Guardar o calibrador.
- Limiar = `best_f2_threshold` nas predições OOF **calibradas**.
- Tabela comparativa `reports/m1/comparacao_oof.md`: por modelo, PR-AUC média (e por dobra),
  Brier, slope/intercept, ROC-AUC, métricas no limiar; com B0, B1 e B2 ao lado.
- Aplicar a **regra de seleção** da §1.4. Registrar o vencedor e o motivo no §9 e no MLflow.
- **Pronto quando:** um único modelo M1 escolhido, com calibrador e limiar, **sem ter lido 2024**.

### [ ] T-4.10 — Retreino final e congelamento (FR-12, FR-22, D-37)

- Retreinar o modelo escolhido em **todo** 2022–23 com os melhores hiperparâmetros.
  Iterativos: nº de árvores/épocas = **mediana** dos melhores pontos das 5 dobras (sem early stopping).
- Aplicar o calibrador e o limiar da T-4.9 (não reajustar).
- Serializar com `save_bundle` (pipeline + calibrador + limiar + metadados FR-12 + os 5 melhores pontos).
- Verificar se o modelo cabe na demo (tamanho do arquivo, tempo de predição < 1 s, SHAP local
  viável). Se **não** couber: **🛑 PARE E PERGUNTE** (Q-14).
- **Pronto quando:** `models/m1_final.*` (no Drive) carrega e prediz; hash do arquivo anotado no §9.

---

## 5. Marco 5 — Avaliação final no teste (uma vez só)

Spec: FR-09, §3.12, D-36, D-39. **Pré-requisitos:** T-3.6 e T-4.10 prontos e commitados.

### [ ] T-5.1 — Avaliação única (`evaluate.py`)

- `evaluate_test_once(cfg)`:
  1. se `reports/teste/LACRE.json` existir → `raise RuntimeError("teste já avaliado (R2)")`;
  2. carregar 2024 com `load_population(cfg, [2024])` (único lugar autorizado);
  3. carregar os artefatos congelados de E1, M1, B1 (e regra B2);
  4. predizer; calcular todas as métricas da §1.4 com IC bootstrap (1.000; 2.000 nas bandas de
     calibração) e a **diferença de PR-AUC** M1 − B1 com IC;
  5. gravar `LACRE.json` com data, commit, hashes dos artefatos e dos dados.
- Teste: uma segunda chamada levanta erro.
- **Pronto quando:** `reports/teste/metricas.md` gerado e `LACRE.json` gravado.

### [ ] T-5.2 — Curva de decisão, calibração e subgrupos

- Curva de decisão (0,1%–5%) para M1, B1 e B2, com "tratar todos" e "ninguém"; marcar o limiar F2.
- Curva de calibração com bandas (2.000 bootstrap) para M1 e E1.
- Subgrupos: faixa etária; sexo; gestantes; região; **raça/cor** (com "ignorado"). PR-AUC, recall no
  limiar e calibração, com IC. Subgrupos com < 100 eventos (sexo "I") ou no limite (gestantes,
  Norte) recebem aviso de IC largo.
- **Pronto quando:** `reports/teste/` tem as figuras e tabelas.

### [ ] T-5.3 — Análise de erros

- Os 100 falsos negativos com **maior** risco previsto entre os não detectados `[ASSUMPTION]`:
  descrever por perfil (faixa, comorbidades, região, atraso) **em agregados** (R7).
- Células de comorbidade com pior calibração.
- Olhar o Espírito Santo à parte (sistema de origem diferente, spec §3.7).
- **Pronto quando:** `reports/teste/erros.md` sem nenhuma linha individual.

### [ ] T-5.4 — Critérios de aceitação (§3.12, `[ASSUMPTION]`)

Reportar cada um como passou/falhou, **sem mexer no modelo**:
- M1 supera B0 em PR-AUC (IC da diferença não inclui 0);
- comparação com B1 (superar é desejável, não obrigatório);
- recall de M1 ≥ recall de B2, com precisão maior, no limiar;
- calibration slope no teste entre 0,8 e 1,2.

Se o teste sair pior que a validação: **reportar como resultado (drift)**. É proibido voltar e
trocar modelo, peso, calibrador ou limiar (D-36).

---

## 6. Marco 6 — Demo Streamlit

Spec: FR-11, NFR-03, NFR-06, §3.15, D-27, D-35.

### [ ] T-6.1 — Estrutura do app

- `app/streamlit_app.py` com duas abas: **Perfil** (E1) e **Triagem** (M1).
- Carrega os artefatos (`load_bundle`), **nunca** microdados (R7). Não grava entradas (NFR-03).
- Aviso fixo nas duas abas: "Projeto acadêmico. Não é ferramenta clínica nem substitui avaliação
  médica." Na aba Triagem, em destaque.
- Uma frase em cada aba explicando a diferença: Perfil = "qual o risco de quem tem estas
  condições"; Triagem = "qual o risco deste paciente, com estes sintomas, agora".

### [ ] T-6.2 — Aba Perfil (E1)

- Entradas: idade, sexo, gestação, 7 comorbidades.
- Saídas: risco com IC 95% (método delta), comparação com "sem comorbidades" na mesma faixa, OR das
  comorbidades marcadas.

### [ ] T-6.3 — Aba Triagem (M1)

- Entradas: schema da CLI (§3.15 do spec): perfil + sintomas + dias até o atendimento.
- Saídas: risco calibrado; "alto risco" sim/não no limiar; **5 fatores** que mais aumentaram ou
  reduziram o risco (TreeSHAP para árvore; coeficiente × valor para elastic net; para MLP,
  `shap.GradientExplainer` com amostra de fundo; para TabFM, SHAP aproximado) com a frase "contribuição no modelo, não causa"; se o caso cairia no grupo B
  (B2) `[ASSUMPTION]`.

### [ ] T-6.4 — Verificação e publicação

- Teste: o app sobe (`streamlit run`) e as duas abas respondem em < 1 s (NFR-06) para 20 perfis.
- Conferir que nenhum arquivo de dados está no repositório (R7).
- Publicar no Streamlit Community Cloud **só depois do "ok" do Programador** (é publicação pública).

---

## 7. Marco 7 — Relatório (TRIPOD+AI)

Spec: FR-20, FR-21, D-22, D-28.

### [ ] T-7.1 — Rascunho do relatório

- Estrutura pelo checklist TRIPOD+AI. Seções mínimas: título/resumo; introdução (com trabalhos
  relacionados e diferencial, §3.2); métodos (fonte, população, alvo, preditores, split, modelos,
  métricas); resultados (fluxograma, descritiva, E1, M1, teste, subgrupos); discussão (limitações:
  duplicatas, ES/`TP_SISTEMA`, leucopenia "não feito", sem doenças respiratórias, idade por
  `ANO_NASC`, drift 2024); conclusão.
- Parágrafo obrigatório: por que o alvo difere do pré-projeto (D-22, spec §3.6).
- Ética (NFR-04): dados públicos e **desidentificados** (não "anonimizados"); dispensa pela CNS
  510/2016, art. 1º, parágrafo único, inciso II.
- Explicar F2 vs F0.5 (D-33) e por que não há correção de desbalanceamento (D-38).

### [ ] T-7.2 — Apêndices

- A: registro de decisões (copiar §3.16 do spec), destacando D-22 a D-25.
- B: fluxograma de exclusão e resultados do profiling.
- C: "passos seguidos" — cronologia exportada do MLflow (config, hash dos dados, métricas por run).
- D: revisão do profissional de saúde (FR-21), se houver. Sugestões que mudariam o modelo viram
  limitação, não retreino.

### [ ] T-7.3 — Checklist final

- Rodar o checklist §5 do `CLAUDE.md` e o TRIPOD+AI; listar o que falhou.
- Confirmar NFR-02: rodar de novo do zero e obter as métricas de teste com as mesmas 3 casas
  decimais — **sem reavaliar o teste**: a reprodução usa o mesmo pipeline e compara com
  `reports/teste/metricas.md` numa cópia isolada, e o resultado é anotado, não usado para mudar nada.
  🛑 Confirme com o Programador como fazer essa verificação sem violar R2.

---

## 8. Extras (só se o Programador pedir)

- FR-14 (M2 pós-alarme): **tem que ser feito antes do Marco 5**; população só `CLASSI_FIN` ∈ {11, 12}.
- FR-16 (sensibilidade 2017–2024).
- FR-10 (CLI `predict`).
- Análise de sensibilidade de duplicatas com chave estrita (D-47).

---

## 9. Registro de execução

Uma linha por tarefa concluída: data, tarefa, resultado principal (números), onde está o artefato.

| Data | Tarefa | Resultado | Artefato / run MLflow |
|---|---|---|---|
| 2026-11-03 | Marco 1 | Profiling concluído: 7.784.953 casos, 15.323 eventos (2022–24) | `profiling/RESULTADOS.md` |

---

## 10. Registro de problemas

Todo erro inesperado entra aqui **antes** de qualquer correção (regra 4b). Uma linha por problema;
se houver várias tentativas, uma linha por tentativa.

| Data | Tarefa | O que aconteceu (mensagem de erro ou número estranho) | O que foi tentado | Resultado | Precisou perguntar? |
|---|---|---|---|---|---|
