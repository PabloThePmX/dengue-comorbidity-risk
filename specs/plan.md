# Plano técnico — Risco de desfecho grave em dengue por perfil de comorbidades

**Data**: 2026-11-15 | **Status**: v0.18 (D-60)

> **Como** o projeto é construído. Requisitos em [spec.md](spec.md); princípios em
> [constitution.md](constitution.md); motivos das escolhas em [research.md](research.md).

---

## Resumo

Serve ao objetivo de [goal.md](goal.md). Pipeline em Python que baixa os microdados do
SINAN-Dengue (2022–2024), monta a população e o alvo
([spec › Formulação do problema](spec.md#formulação-do-problema)) e treina dois tipos de modelo: o
explicativo E1, uma logística sem penalização com interações entre comorbidades (US1), e o
preditivo M1, escolhido entre seis candidatos avaliados nas mesmas dobras leave-one-region-out de
2022–23 (US2). O teste de 2024 é usado uma vez. Os artefatos alimentam uma demo Streamlit com duas
abas (US3) e um relatório TRIPOD+AI.

## Contexto técnico

| Item | Valor |
|---|---|
| **Linguagem/versão** | Python 3.13 (`requires-python >=3.13,<3.14`; o `pyreaddbc` não tem wheel para 3.14), ambiente com `uv` (D-16) |
| **Dependências principais** | Já instaladas: `pandas`, `pyarrow`, `pyreaddbc`, `dbfread`. Propostas na T-2.0, sujeitas a aprovação: `scikit-learn`, `statsmodels`, `xgboost`, `catboost`, `optuna`, `mlflow`, `shap`, `torch`, `pyyaml`, `matplotlib`; `streamlit` no Marco 6; pacote do TabFM a definir (T-4.7) |
| **Armazenamento** | Parquet por ano + `manifest.json` com hashes, no Google Drive; MLflow (`mlruns/`) e estudos do Optuna (SQLite) no Drive; `reports/` versionado só com agregados |
| **Testes** | `pytest` (testes unitários por módulo) e `ruff` |
| **Plataforma** | Google Colab, gratuito e Pro (D-44), para dados, treino e avaliação; Streamlit Community Cloud para a demo (D-17); Windows local para desenvolvimento |
| **Tipo de projeto** | Projeto único: pacote de pipeline + app, layout `src` ([Arquitetura do código](#arquitetura-do-código)) |
| **Metas de desempenho** | Demo < 1 s por consulta (NFR-06); sessão única dos 6 modelos ≈ 4 h ([Ambiente](#ambiente-de-execução-e-orçamento), D-53) |
| **Restrições** | ~12,7 GiB de RAM no Colab gratuito; GPU não garantida; 2024 não lido antes da T-5.1 (R1); nenhum microdado no git ou no app (NFR-03) |
| **Escala** | 7,78 mi de casos (2,45 mi no desenvolvimento, 5,33 mi no teste); 3.985 eventos no desenvolvimento; ~25 features ([data-model › Dicionário de features](data-model.md#dicionário-de-features)) |

## Constitution Check

O plano precisa cumprir a [constituição](constitution.md) antes de implementar e de novo depois do
Marco 4. Situação em 2026-11-15 (só o desenho; nada foi implementado além do Marco 1).

| Princípio | Como o plano cumpre | Situação |
|---|---|---|
| P1 Spec antes do código | Toda tarefa de `tasks/` cita os IDs do spec; decisões no [Registro de decisões](research.md#registro-de-decisões) | Cumpre |
| P2 Teste congelado | `guard.assert_dev_only` (T-2.2) e lacre da T-5.1 (R1, R2) | Cumpre no desenho; verificar na T-2.2 e na T-5.1 |
| P3 Sem vazamento | Lista fechada de features (R4); `Pipeline` dentro da dobra (R5); validação interna para early stopping (R6) | Cumpre no desenho |
| P4 Baselines e comparação justa | B0–B2 antes dos modelos (T-2.8); mesmas dobras, semente e orçamento (D-53) | Cumpre no desenho |
| P5 Prevalência natural | Sem pesos de classe nem reamostragem (R3); exceção do RF documentada ([Features](#features-e-pré-processamento)) | Cumpre no desenho |
| P6 Associação ≠ causa | Ranking só pelo E1 (R10); legendas do SHAP ([spec › Interpretabilidade](spec.md#interpretabilidade-e-equidade)) | Cumpre no desenho |
| P7 Reprodutível | `uv.lock`, semente única, config YAML, hashes, MLflow ([Reprodutibilidade](#reprodutibilidade)) | Cumpre no desenho; NFR-02 sem método de verificação definido (T-7.3) |
| P8 Privacidade | Só agregados, células < 10 suprimidas; demo sem microdados (NFR-03) | Cumpre no desenho |
| P9 Código testável | Um módulo por responsabilidade com testes ([Módulos](#módulos)); 48 testes passando no código do Marco 1 | Cumpre |
| P10 Honestidade | [Registro de problemas](tasks/00-como-usar.md#registro-de-problemas); resultado negativo é válido (SC-04) | Cumpre |

## Arquitetura do código

### Estrutura de pastas

```
specs/             documentação (mapa em specs/goal.md)
src/
  dengue_sinan/    pacote Python: todo o pipeline (instalado por `uv sync`)
  app/             demo Streamlit (Marco 6, FR-11)
tests/             pytest, um arquivo por módulo (NFR-05)
config/            base.yaml (parâmetros) e esperado.yaml (valores conferidos, D-56)
notebooks/         só chamam funções de src/ (NFR-05)
profiling/         gerador do notebook de profiling e resultados do Marco 1
reports/           só agregados, versionado (NFR-03); verificacao/ com os JSON do Colab (D-56)
data/, mlruns/     fora do git (NFR-03); no Colab, no Google Drive
```

- **Layout `src`:** o código fica em `src/` e os testes fora dele. Assim os testes importam o pacote
  **instalado**, e não a pasta solta, o que pega erros de empacotamento cedo.
- `tests/`, `notebooks/`, `profiling/` e `config/` ficam na raiz (D-54).

### Módulos

Módulos de `src/dengue_sinan/`:

| Módulo | Responsabilidade | Requisitos | Status / tarefa |
|---|---|---|---|
| `download.py` | FTP do DataSUS → Parquet por ano + `manifest.json` com hash | FR-01 | Existe (Marco 1) |
| `features.py` | Decodificação da idade com fallback por `ANO_NASC`; região pelo IBGE | D-50 | Existe (Marco 1) |
| `profiling.py` | População, alvo, faixas e tabelas do profiling | FR-02 | Existe (Marco 1) |
| `config.py` | Carrega `config/base.yaml` | NFR-02 | T-2.0 |
| `verify.py` | Relatório de verificação do Colab (`reports/verificacao/*.json`) contra `config/esperado.yaml`; impressão com SHA-256 e conferência do ambiente para o MCP | P10, D-56, D-57, D-64 | T-2.0 |
| `dataset.py` | Carrega a população e monta o frame de features | FR-02 | T-2.1 |
| `checks.py` | Checks bloqueantes de qualidade | FR-03 | T-2.1 |
| `guard.py` | `assert_dev_only`: bloqueia 2024 antes da avaliação final | FR-09, R1 | T-2.2 |
| `folds.py` | Dobras leave-one-region-out, validação interna, `save_folds`/`load_folds` com hash | FR-17, FR-22, D-53 | T-2.3 |
| `metrics.py` | PR-AUC, Brier, calibração, F2, net benefit, bootstrap simples e pareado | FR-09, D-53 | T-2.4 |
| `tracking.py` | MLflow: config, hashes, commit, métricas | NFR-02 | T-2.5 |
| `descriptive.py` | Tabela 1, eventos por par e por combinação | FR-18, D-52 | T-2.6 |
| `baselines.py` | B0, B1, B2 | FR-04 | T-2.8 |
| `explain.py` | E1: OR, IC, Benjamini-Hochberg, RERI/AP, ranking, perfis | FR-05, FR-06, FR-19 | T-3.1, T-3.2, T-3.5 |
| `artifacts.py` | `save_bundle`/`load_bundle` com metadados | FR-12 | T-3.6 |
| `preprocess.py` | `ColumnTransformer` por família de modelo | R5 | T-4.1 |
| `cv.py` | `run_loro`: dobras, early stopping, predições fora da dobra | FR-17, FR-22 | T-4.2 |
| `tuning.py` | Optuna: cronometragem, poda, estudo retomável | NFR-01, D-43, D-53 | T-4.3 |
| `runner.py` | `run_all_models`: sessão única com retomada; grava `sessao-m1.json`; entrada `python -m` para rodar em segundo plano | D-53, D-57, D-64 | T-4.3b |
| `mlp.py` | MLP em PyTorch com interface do scikit-learn | D-51 | T-4.6b |
| `evaluate.py` | `evaluate_test_once` + lacre | FR-09, R2 | T-5.1 |

A demo fica em `src/app/streamlit_app.py` (T-6.1) e só importa `dengue_sinan` e os artefatos
serializados; não lê microdados (NFR-03).

### Fluxo de dados

```
download ─► Parquet (Drive) ─► dataset + checks ─► folds (hash) ─┬─► baselines (B0, B1, B2)
                                                                 ├─► explain (E1) ─► perfis, ranking
                                                                 └─► runner: tuning ─► cv (6 modelos)
                                                                        │
                                       calibração, limiar, seleção ◄────┘
                                                  │
                                       retreino final ─► artifacts ─► evaluate (2024, uma vez)
                                                                           │
                                                          relatório (FR-20) e demo (FR-11)
```

- **Regras de dependência:** módulos de base (`config`, `features`, `metrics`, `guard`) não
  importam módulos de modelagem. Toda função que treina, ajusta, calibra ou escolhe chama
  `assert_dev_only` (R1). Só `evaluate.py` lê 2024.

---

## Ambiente de execução e orçamento

Como cumprir a NFR-01. Pesquisa de planos, preços e fontes do Colab:
[research › Planos do Colab](research.md#planos-do-colab).

- **Colab gratuito** (o FAQ do Google diz que os limites não são publicados e variam): sessão de até ~12 h, desconexão após ~90 min sem interação, GPU (em geral T4) não garantida, ~12 GB de RAM. A RAM e a GPU obtidas são registradas em cada execução. No profiling (2026-11-03): 12,7 GiB de RAM; os 3 anos com 40 colunas ocupam 0,46 GiB, e a população final (7,8 mi linhas), 0,91 GiB.
- **Plano usado pelo Programador:** Google AI Pro para estudantes (assinatura paga), com **200 unidades de computação por mês** no Colab, aceleradores mais potentes e sessões mais longas (confirmado na página da oferta em 2026-11-03).
  - `[VERIFY]` Depois de assinar: conferir no Colab (*Ambiente de execução → Ver recursos*) se o saldo aparece como 200, quais GPUs ficam disponíveis e se as unidades não usadas acumulam.
- **Consumo e custo da sessão de modelos (≈ 4 h, D-53):** T4 ≈ 1,2 unidade/h, L4 ≈ 1,7/h, A100 40 GB ≈ 5,4/h (medição de março de 2026). A sessão custa ~5 unidades em T4, ~7 em L4 e ~22 em A100; 200 unidades/mês cobrem cerca de 9 sessões em A100 e mais de 25 em T4/L4. GPU ociosa continua consumindo unidades.
- **RAM alta (medida em 2026-11-15):** a VM com GPU T4 e "RAM alta" tem **50,99 GiB e 8 vCPUs** (a padrão, 12,67 GiB e 2 vCPUs). Com ela, Random Forest e as 5 dobras com todos os dados devem caber sem subamostra. A opção pode não ser aplicada na primeira vez que é salva, por isso a checagem inicial confere a RAM por código (`cfg.ambiente`, D-64).
- **Como usar `[ASSUMPTION]`:** o Pro é um **acelerador**, não muda os orçamentos de tempo da tabela abaixo (mantém a comparação justa entre modelos). Sessão única (D-53) numa VM com GPU (L4 de preferência, T4 serve) e High RAM: XGBoost (`device="cuda"`), CatBoost (`task_type="GPU"`), MLP e TabFM na GPU; elastic net e Random Forest na CPU da mesma VM. A100 só se o TabFM exigir. Desconectar o ambiente ao fim da sessão.
  - `[VERIFY]` Se o CatBoost em GPU aceita `PRAUC` como métrica de early stopping; se não aceitar, CatBoost volta para a CPU.
  - `[VERIFY]` **torch com CUDA 13 no Colab.** O `uv.lock` (2026-11-03) resolve o `torch` 2.15.0 para Linux com wheels de CUDA 13 (pacotes `nvidia-*-cu13`); no Windows local, a mesma versão vem só com CPU (`2.15.0+cpu`). Depois de instalar o projeto no Colab, conferir se o driver suporta CUDA 13 (`nvidia-smi`) e se `torch.cuda.is_available()` dá `True`. Se não der, as alternativas são: usar o torch que já vem no Colab, baixando o piso de versão no `pyproject.toml`, ou instalar o torch do índice da PyTorch para a versão de CUDA do Colab. A escolha fica com o Programador, e a versão usada vai para o MLflow.
- **Reprodutibilidade (D-44):** mesmo executado no Pro, o pipeline MUST continuar executável no Colab gratuito, ainda que mais devagar ou com subamostra na busca. Assim o professor ou outra pessoa consegue reproduzir sem assinatura.
- **Orçamento por modelo** `[ASSUMPTION]` (relógio de parede da busca com as 5 dobras; revisto em D-53). É um **teto**: o orçamento real sai da cronometragem abaixo.

  | Modelo | Teto | Máx. de tentativas | Observação |
  |---|---|---|---|
  | Logística elastic net | 20 min | 15 | CPU; só 2 hiperparâmetros. |
  | XGBoost | 30 min | 30 | GPU. |
  | CatBoost | 40 min | 25 | GPU; bons padrões, precisa de menos tentativas. |
  | MLP | 40 min | 25 | GPU. |
  | Random Forest | 40 min | 25 | CPU; `max_samples` na busca para caber; subamostra de negativos se faltar memória ([Features](#features-e-pré-processamento)). |
  | TabFM | 30 min | 1 | GPU; sem busca, só predição nas 5 dobras. `[VERIFY]` velocidade no model card. |

  Total dos tetos ≈ 3 h 20; com carga dos dados, calibração, comparação e retreino do vencedor, **≈ 4 h numa sessão única** (D-53), antes ≈ 8 h. Cabe no limite de ~12 h do Colab gratuito.
- **Cronometragem antes da busca (D-53):** para cada modelo, a 1ª tentativa usa os **hiperparâmetros padrão** da biblioteca nas 5 dobras e mede o tempo `t`. Orçamento = mín(teto, `t` × máx. de tentativas), com piso de 10 min. Se 3 tentativas (`3t`) não couberem no teto, a busca usa a subamostra estratificada (regra abaixo). A tentativa padrão também é a referência: a busca nunca entrega algo pior que o padrão.
- **Sessão única e retomada (D-53):** dados, dobras e validações internas são montados uma vez e salvos no Drive com hash; todos os modelos usam exatamente essas linhas. Cada modelo concluído grava um marcador no Drive; se a sessão cair, a reexecução pula os concluídos e o Optuna retoma o estudo do modelo em andamento. Ordem: elastic net → XGBoost → CatBoost → MLP → Random Forest → TabFM (os baratos primeiro; o de maior risco de memória e o que depende do model card por último).
- **Execução pelo MCP do Colab (D-64):** o agente dispara a sessão em segundo plano (`python -m dengue_sinan.runner`, log no Drive) e a acompanha com células curtas que leem o `sessao-m1.json`. Reiniciar a sessão do Colab mata o processo (testado em 2026-11-15); a retomada acima cobre isso. Toda gravação no Drive é atômica (`os.replace`) e tem novas tentativas, porque o Drive falhou uma vez ao criar arquivo no teste. `[VERIFY]` SQLite do Optuna no Drive (travamento de arquivo), na checagem inicial da T-4.3b.
- **Regras do orçamento:**
  - A busca para no que vier primeiro: o tempo do orçamento ou o máx. de tentativas do modelo (tabela acima) `[ASSUMPTION]`.
  - Poda: uma tentativa claramente pior que a mediana depois das 2 primeiras dobras é interrompida, para gastar o tempo nas promissoras. As dobras rodam em ordem fixa, da região com mais eventos para a com menos (Sudeste, Sul, Centro-Oeste, Nordeste, Norte), para a poda decidir com as dobras de menor variância `[ASSUMPTION]`.
  - A busca é **retomável**: o estado fica salvo no Drive (SQLite do Optuna), então uma desconexão não perde as tentativas já feitas. As melhores tentativas já ficam salvas pela FR-22.
  - Se nem uma tentativa completa (5 dobras) couber, a busca usa uma **subamostra estratificada pelo alvo** (mesma prevalência, sem corrigir desbalanceamento, D-38) de cada dobra `[ASSUMPTION]`. O retreino final e as predições fora da dobra do modelo escolhido usam todos os dados.
  - Cada execução registra no MLflow: tempo gasto, nº de tentativas concluídas e podadas, hardware (CPU/GPU, RAM). Modelos rápidos fazem mais tentativas no mesmo orçamento; o relatório mostra esse número junto do resultado.
- **Por que orçamento por modelo:** [research › Evidência para o orçamento de busca](research.md#evidência-para-o-orçamento-de-busca).

---

## Features e pré-processamento

- **Lista de features:** o [data-model › Dicionário de features](data-model.md#dicionário-de-features) (lista fechada, R4), derivada dos campos marcados "Entra" na [spec › Revisão de vazamento](spec.md#revisão-de-vazamento).
- **Idade:** decodificar `NU_IDADE_N` pela regra verificada ([data-model › Demografia e idade](data-model.md#demografia-e-idade): 1º dígito = unidade; converter tudo para anos fracionários), com teste unitário cobrindo 1xxx, 2xxx, 3xxx e 4xxx. Se o código for inválido ou fora de [0, 120], usar ano dos sintomas − `ANO_NASC` (D-50) e marcar a flag `idade_de_ano_nasc`. Usar idade contínua (splines na logística) e faixas para perfis e subgrupos.
  - `[ASSUMPTION]` Faixas: 0–4, 5–14, 15–39, 40–59, 60–79, 80+.
- **Comorbidades:** categóricas de 3 níveis (Sim / Não / Ausente) — D-07; "Ausente" = branco ou valor fora de 1/2. One-hot na logística; nativo/ordinal nos modelos de árvore.
- **Sintomas:** mesmo esquema de 3 níveis `[ASSUMPTION]` (consistência com D-07).
- **UF/região:** não é feature (D-21). Guardada no dataset só para dobras de validação e subgrupos.
- **Escalonamento:** só para logística/MLP (variáveis contínuas). Árvores não precisam.
- **Outliers:** idade inválida ou fora de [0, 120] → fallback por `ANO_NASC` (D-50); sem `ANO_NASC` utilizável, o caso é excluído e contado no fluxograma (D-49). Atraso de notificação > 60 dias truncado em 60: confirmado pelo profiling, com mediana de 3 dias, p99 de 61 / 38 / 52 dias e 1,0% / 0,5% / 0,8% dos casos acima de 60 dias.
- **Desbalanceamento (D-12, revisado em D-38):** **sem correção.** Os modelos treinam com a prevalência natural, sem pesos de classe, subamostragem ou SMOTE. O recall é controlado pelo limiar (F2, [spec › Plano de avaliação](spec.md#plano-de-avaliação)), e a calibração posterior (isotônica ou Platt) continua nas predições fora da dobra. Motivo: corrigir o desbalanceamento não melhora AUROC nem AUPRC e piora a calibração, às vezes de forma que a recalibração não conserta (van den Goorbergh et al., JAMIA 2022; Carriero et al., Stat Med 2024 — síntese em `research/consensus-boas-praticas.md`, cópia local fora do repositório: termos do Consensus). Exceção: a subamostra de negativos do Random Forest, só por memória, com correção de probabilidade e verificada pela calibração (R3, T-4.4).
- **Implementação:** um único `sklearn.Pipeline` / `ColumnTransformer` por modelo, salvo inteiro no artefato (FR-12). Nada de transformação ad hoc fora do pipeline.

## Modelagem

### Modelo explicativo (E1)

Objetivo principal (D-01).

- **E1 — logística com interações**, sem penalização (R9): os mesmos efeitos principais de B1 (idade em spline, sexo, gestação e as 7 comorbidades; sem `n_comorbidades`, D-62) + interações 2 a 2 entre as 7 comorbidades (21 termos) + interação comorbidade × idade (spline) para hipertensão e diabetes `[ASSUMPTION]`. A idade entra contínua também na interação; as faixas servem só para relatório e subgrupos (D-41), porque categorizar preditores contínuos piora o modelo ([Collins et al., Stat Med 2016](https://consensus.app/papers/details/2bfae82d18cf5de2b57622aed743abc3/)).
- **Interação aditiva (D-40):** para cada par de comorbidades, além do OR da interação (escala multiplicativa), reportar o **RERI** (excesso de risco relativo devido à interação) e o **AP** (proporção atribuível à interação), com IC 95% por método delta ou bootstrap.
  - Por quê: a escala aditiva responde à pergunta de saúde pública ("essa combinação acrescenta casos além da soma das duas condições?"), e uma interação pode ser significativa numa escala e não na outra. Síntese das referências (Knol & VanderWeele; Li & Chambless) em `research/consensus-boas-praticas.md` (cópia local, fora do repositório: termos do Consensus).
  - RERI e AP saem do mesmo modelo E1 (ajustado por idade e sexo), comparando "só A", "só B" e "A e B" contra "nenhuma das duas".
- Só se reportam interações com **≥ 10 eventos** (y = 1) na célula combinada `[ASSUMPTION]`.
- Correção para comparações múltiplas: Benjamini-Hochberg (FDR 5%) `[ASSUMPTION]`.
- Com milhões de linhas, quase tudo fica "estatisticamente significativo". O relatório interpreta **tamanho de efeito (OR) e IC**, não p-valor.

### Candidatos de M1

| Modelo | Status | Motivo |
|---|---|---|
| Logística elastic net | Obrigatório | Pedido do professor. Todas as features do M1, como os outros candidatos ([dicionário](data-model.md#dicionário-de-features)), mais as interações 2 a 2 entre comorbidades do E1 (D-63); a penalização L1 + L2 lida com muitas interações correlacionadas. **Só para predição:** coeficientes penalizados são viesados de propósito e não têm IC clássico, por isso E1 continua sem penalização. |
| XGBoost | Obrigatório | Estado da arte em dados tabulares; pedido do professor. Fecha Q-07. |
| Random Forest | Obrigatório | Comparação clássica (pré-projeto); pode exigir subamostra de negativos no Colab (com correção de probabilidade). |
| CatBoost | Obrigatório | Categóricas nativas; pedido do professor. |
| MLP | Obrigatório | Pedido do professor e do grupo. Raramente vence boosting em tabular; se não vencer, é resultado válido. Exige escalonamento ([Features](#features-e-pré-processamento)). Implementado em **PyTorch com GPU** (D-51). |
| TabFM (Google Research) | Obrigatório | Modelo de fundação tabular zero-shot; pedido do professor. Restrições abaixo. |

### Restrições do TabFM

Verificado em 2026-11-02 em fontes de lançamento: [blog do Google Research](https://research.google/blog/introducing-tabfm-a-zero-shot-foundation-model-for-tabular-data/), [Enterprise DNA](https://enterprisedna.co/resources/news/google-tabfm-zero-shot-tabular-data-enterprise-analytics-2026).

- Lançado em 30/06/2026. Não há treino: as linhas de treino entram como **contexto** na hora da predição (aprendizado em contexto), e a arquitetura alterna atenção entre linhas e colunas.
- Código sob Apache 2.0; pesos no Hugging Face com licença **não comercial**. `[VERIFY]` Confirmar no model card que uso acadêmico está coberto.
- `[VERIFY]` No model card: limite de linhas de contexto e de features (uma fonte secundária cita até 500 features e 10 classes) e velocidade de predição.
- Com milhões de linhas no desenvolvimento, o contexto será uma **subamostra estratificada** do treino de cada dobra, com tamanho definido pelo limite verificado. O relatório registra que o TabFM vê só essa subamostra.
- Precisa de GPU (Colab). Avaliado nas mesmas dobras leave-one-region-out e calibrado igual aos outros (FR-08, FR-17).
- Os resultados no TabArena são do próprio Google, ainda sem verificação independente; não citar como evidência de superioridade.

### Busca de hiperparâmetros

- **Optuna (D-43)**, versão pinada no `uv.lock` quando a modelagem começar. Sampler TPE com semente fixa; poda com `MedianPruner`, reportando a PR-AUC acumulada a cada dobra `[ASSUMPTION]`; estado em SQLite no Drive (busca retomável); `timeout` igual ao orçamento do modelo.
- Máximo de tentativas por modelo da tabela de [Ambiente e orçamento](#ambiente-de-execução-e-orçamento) (15 a 30), **dentro do orçamento de tempo do modelo** (NFR-01, D-42, D-53); a 1ª tentativa usa os padrões da biblioteca (`enqueue_trial`); cada tentativa é avaliada pela PR-AUC média das 5 dobras leave-one-region-out. Se o orçamento não comportar, usar subamostra estratificada na busca antes de reduzir dobras ou modelos.
- **Espaço de busca:** `[OPEN QUESTION]` Q-08 — definido na implementação (proposta na T-4.0) e registrado no config.

### Early stopping e melhores pesos

FR-22.

- Em cada dobra leave-one-region-out, a região deixada de fora serve **só** para as predições fora da dobra. Ela não pode decidir onde parar o treino: se decidisse, a métrica fora da dobra ficaria otimista.
- Por isso, o early stopping usa uma **validação interna**: 10% estratificado pelo alvo das linhas das 4 regiões de treino `[ASSUMPTION]` (R6).
- Métrica monitorada: PR-AUC (`aucpr` no XGBoost, `PRAUC` no CatBoost, cálculo próprio por época no MLP). Paciência: 50 rodadas no boosting e 10 épocas no MLP `[ASSUMPTION]`.
- Retreino final: nº de árvores / épocas = mediana dos melhores pontos das 5 dobras, sem early stopping, porque não sobra validação em 2022–23 (D-37).
- O melhor ponto e o modelo daquele ponto são salvos por dobra no MLflow. A melhor tentativa de cada busca (config + artefato) recebe o alias `melhor-validacao`; tentativas piores não a sobrescrevem.
- Elastic net e Random Forest: "melhor peso" = configuração da melhor tentativa. TabFM: não tem pesos treinados; guarda-se só a subamostra de contexto e a semente.

### Incerteza e comparação

- **Bootstrap:** 1.000 reamostras para métricas escalares `[ASSUMPTION]`; **2.000** nas bandas da curva de calibração, como em [Austin et al., Stat Med 2014](https://consensus.app/papers/details/90973d5732005604963231ca27adbb22/) (D-41). Se o bootstrap ficar caro demais com milhões de linhas, o IC da AUC pode usar o método por função de influência ([LeDell et al., 2015](https://consensus.app/papers/details/d349620d7e9e5108a57864ddbb717245/)).
- **SHAP global (FR-13):** subamostra estratificada de 50 mil linhas de 2022–23 `[ASSUMPTION]`.
- **Comparação pareada (D-53):** como todos os modelos preveem as mesmas linhas nas mesmas dobras, a comparação é **pareada**: para cada par de modelos, a diferença de PR-AUC por dobra (5 valores) e o IC 95% da diferença por bootstrap com os **mesmos sorteios** para os dois modelos (1.000 reamostras, estratificadas por dobra e alvo). Isso remove a variância que os modelos compartilham e detecta diferenças que ICs separados não mostram. É **só reportada**: não entra na regra de seleção (D-53).

### Regra de seleção

- Maior PR-AUC média nas dobras leave-one-region-out.
- Empate (diferença < 0,005 ou ICs sobrepostos; regra mantida em D-53) → menor Brier.
- Persistindo → o modelo mais simples, na ordem: elastic net < Random Forest < XGBoost/CatBoost < MLP < TabFM `[ASSUMPTION]`.
- Calibrador e limiar: [spec › Plano de avaliação](spec.md#plano-de-avaliação); a escolha entre isotônica e Platt é a de menor Brier fora da dobra `[ASSUMPTION]`.

## Reprodutibilidade

E rastreio de experimentos. O critério é a NFR-02.

- **Ambiente (D-16):** `uv` + `pyproject.toml` + `uv.lock` versionado. No Colab: instalação a partir do lock.
- **Seeds:** seed global única no config (R8), propagada para numpy, sklearn, XGBoost, CatBoost, MLP, sampler do Optuna, subamostra de contexto do TabFM, bootstrap e subamostras.
- **Dados:** snapshot Parquet por ano, com hash SHA-256 registrado em `data/manifest.json` e no MLflow. Data do download registrada (o DataSUS pode revisar os arquivos).
- **Configuração:** arquivos YAML (anos, filtros, features por momento, hiperparâmetros, limiar); nada hard-coded.
- **Tracking (D-15):** MLflow, com `mlruns/` persistido no Google Drive do grupo. Cada execução registra config, hash dos dados, commit do git, métricas e artefatos. Os melhores pesos de validação de cada modelo ficam no registro de modelos do MLflow com o alias `melhor-validacao` (FR-22).

## Registro de complexidade

O Spec Kit pede justificativa só para violações da constituição. Não há violação. Abaixo, as
complexidades aceitas de propósito, para que fiquem visíveis.

| Complexidade | Por que é necessária | Alternativa mais simples rejeitada porque |
|---|---|---|
| Seis candidatos em M1 | Pedido do professor (D-32) | Só logística + XGBoost não atenderia ao retorno do pré-projeto |
| Validação leave-one-region-out (5× treinos) | Mede robustez geográfica e gera predições fora da dobra para calibração e limiar (D-08, FR-17) | Split aleatório esconde o drift e superestima o desempenho ([research › Evidência para o desenho de validação](research.md#evidência-para-o-desenho-de-validação)) |
| Sessão única com retomada e dobras com hash | Mesmo hardware e mesmas linhas para todos; sobrevive a quedas do Colab (D-53) | Uma sessão por modelo misturaria hardware e repetiria a carga dos dados |
| Dois modelos na demo (E1 e M1) | Perfil e triagem respondem perguntas diferentes (D-20, D-27) | Só um modelo deixaria uma das perguntas sem resposta |
