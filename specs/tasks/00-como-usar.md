# Tarefas — como usar, regras e registros (Marcos 2 a 7)

**Entrada**: [goal.md](../goal.md) (objetivo), [plan.md](../plan.md) (obrigatório), [spec.md](../spec.md) (histórias US1–US3),
[data-model.md](../data-model.md), [contracts/interfaces.md](../contracts/interfaces.md),
[research.md](../research.md) e [quickstart.md](../quickstart.md).

> Fontes da verdade, em ordem: [constitution.md](../constitution.md) (princípios e regras), depois
> spec, depois plan/research/data-model/contracts. Este arquivo só **traduz** esses documentos em
> tarefas. Se discordarem, vale o de cima — pare e avise o Programador.
> **Seções §3.x** valem como IDs em todos os arquivos de `specs/` (mapa no topo do spec.md). Onde
> este arquivo diz "spec", leia "o arquivo de `specs/` que tem a seção citada".
> Marco 1 (dados e profiling) está **concluído**: ver [profiling/RESULTADOS.md](../../profiling/RESULTADOS.md).

**Formato (convenções do Spec Kit, D-55):** `### [ ] T-x.y [P] [USn] — título`
- `[P]`: pode rodar em paralelo com outras `[P]` da mesma fase (arquivos diferentes, sem dependência).
- `[USn]`: história do spec que a tarefa entrega (US1 perfil, US2 triagem, US3 demo).
- Os IDs `T-x.y` são estáveis e não seguem o `T001` do template, para não quebrar referências.
- Estado: `[ ]` a fazer; `[~]` feita, mas aguardando o relatório do Colab em `reports/verificacao/`
  (`T-x.y.json`, ou `sessao-m1.json` na Fase 4; §0, item 2b); `[x]` pronta.

**Arquivos e ordem (D-58).** As tarefas ficam em um arquivo por fase, nesta pasta. A **fase atual**
é o primeiro arquivo, em ordem numérica, que ainda tem tarefa `[ ]` ou `[~]`. Leia sempre este
arquivo e o da fase atual; os outros, só se a tarefa citar.

| Arquivo | Fase | Marco | Tarefas | Começa quando |
|---|---|---|---|---|
| [01-setup-fundacao.md](01-setup-fundacao.md) | 1 Setup e 2 Fundação | 2 | T-2.0 a T-2.8 | Já pode (Marco 1 concluído) |
| [02-us1-perfil.md](02-us1-perfil.md) | 3 — US1 (P1, MVP) | 3 | T-3.1 a T-3.6 | 01 todo `[x]` |
| [03-us2-triagem.md](03-us2-triagem.md) | 4 — US2 (P2) | 4 | T-4.0 a T-4.10 | 01 todo `[x]`; ordem recomendada: depois do 02 |
| [04-teste-final.md](04-teste-final.md) | 5 — teste, uma vez | 5 | T-5.1 a T-5.4 | 02 e 03 todos `[x]` |
| [05-us3-demo.md](05-us3-demo.md) | 6 — US3 (P3) | 6 | T-6.1 a T-6.4 | 04 todo `[x]` (esqueleto pode começar antes, §7b) |
| [06-relatorio.md](06-relatorio.md) | 7 — polimento | 7 | T-7.1 a T-7.3 | Escrito ao longo; fecha depois de 04 e 05 |

---

## 0. Como usar este arquivo (leia antes de qualquer tarefa)

1. Faça as tarefas **na ordem**. Cada tarefa tem um ID (`T-2.3`), os IDs do spec que ela cumpre,
   os arquivos a criar/alterar, os passos e um **critério de pronto**.
2. Uma tarefa só está pronta quando **todos** os itens do critério de pronto foram verificados
   rodando comandos, não "parece que funciona".
2b. **Critério que só se verifica no Colab** (dados reais, GPU, queda de sessão). O ambiente local
   não tem os dados: eles ficam no Drive (NFR-03). **Ninguém digita resultado à mão** (D-56):
   - escreva a verificação **como código**: uma função em `src/` que calcula cada item do "Pronto
     quando" e chama `verify.write_report` (T-2.0), comparando com os valores de
     `config/esperado.yaml`. Nunca escreva números esperados direto no notebook;
   - acrescente a célula que chama essa função no notebook da tarefa;
   - faça e verifique localmente tudo o que der: código, testes com dados sintéticos (inclusive da
     própria verificação), ruff;
   - **não marque `[x]`**: troque `[ ]` por `[~]` (pendente no Colab), escreva em §9 "pendente no
     Colab: rodar <notebook>, célula <nome>; gera `reports/verificacao/T-x.y.json`" e **pare**.
     Avise que o código da tarefa precisa estar commitado e no GitHub antes de rodar, porque o
     Colab clona o repositório e o JSON registra esse commit;
   - na sessão seguinte, se houver tarefa `[~]`, **leia** `reports/verificacao/T-x.y.json`:
     - arquivo ausente → peça ao Programador só para rodar o notebook e colocar o arquivo na pasta
       (não peça números);
     - `"commit"` do JSON diferente do commit que contém o código da tarefa → peça para rodar de novo;
     - `"passou": true` → marque `[x]` e copie para o §9 o resumo dos `checks`;
     - `"passou": false` → registre em §10 os checks que falharam (regra 4b) e não marque `[x]`.
   - Nunca passe para a fase seguinte com uma tarefa `[~]` aberta.
   - **Exceção da Fase 4 (D-57):** T-4.3b a T-4.10 compartilham um único relatório,
     `reports/verificacao/sessao-m1.json`. Marque cada uma `[~]` e siga para a próxima **da mesma
     fase**; pare só depois da T-4.10, pedindo a sessão do Colab. Ao ler o relatório, marque `[x]`
     cada tarefa cujo bloco tem `"passou": true`.
3. Ao terminar cada tarefa: marque `[x]`, rode `uv run pytest -q` e `uv run ruff check .`, e
   escreva uma linha em **§9 Registro de execução** no fim deste arquivo (00-como-usar.md). Todo código novo vai em
   `src/dengue_sinan/` com teste em `tests/`; notebooks só chamam funções (NFR-05).
3b. **Ambiente local (Windows):** o projeto usa o Python **3.13** do `.venv`, criado pelo `uv`; o
   `python` do sistema (3.14) não serve. Se `uv` não estiver no PATH, use `python -m uv` ou o caminho
   completo `%APPDATA%\Python\Python314\Scripts\uv.exe`. Se `uv run pytest` falhar com
   "trampoline failed to canonicalize script path", rode `uv run python -m pytest -q` (mesmo efeito)
   e registre na §10. Nunca instale pacotes com `pip` direto: só `uv add`, depois do "ok" (T-2.0).
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
5. Não edite `constitution.md`, `spec.md` nem `plan.md` para "fazer caber" o seu código. Se
   algum precisar mudar, pergunte.
6. Código novo vai em `src/` (pacote em `src/dengue_sinan/`, demo em `src/app/`); testes em
   `tests/`; configuração em `config/`; notebooks em `notebooks/` (plan §A).

### 0.1 Regras que nunca podem ser quebradas (resumo)

Texto completo, com o princípio de cada uma: [constitution.md §2](../constitution.md#2-regras-que-nunca-podem-ser-quebradas).

| # | Regra em uma linha |
|---|---|
| R1 | 2024 (teste) não é lido antes da T-5.1. |
| R2 | O teste roda uma vez só; a T-5.1 grava um lacre e uma 2ª execução falha. |
| R3 | Sem correção de desbalanceamento (`class_weight`, `scale_pos_weight`, `is_unbalance`, `auto_class_weights`, `pos_weight`, SMOTE, undersampling). Exceção: RF por memória (T-4.4). |
| R4 | Só as features da lista fechada da §1.3. |
| R5 | Pré-processamento ajustado só dentro da dobra de treino, via `sklearn.Pipeline`. |
| R6 | Early stopping só na validação interna, nunca na região deixada de fora. |
| R7 | Nenhum microdado no git, app ou relatório; células com < 10 casos suprimidas. |
| R8 | Semente única do config em tudo que for aleatório. |
| R9 | E1 sem penalização. |
| R10 | Ranking de comorbidades só pelos OR do E1. |

### 0.2 Decisões que você NÃO pode tomar (🛑 pergunte)

Lista completa: [constitution.md §3](../constitution.md#3-decisões-reservadas-ao-programador). Em
especial: dependências novas (T-2.0), espaço de busca (T-4.0), TabFM (T-4.7), modelo da demo
(Q-14, T-4.10) e qualquer mudança de alvo, população, split, métrica, limiar, faixas ou features.

---

## 1. Referência rápida do spec (para não precisar reinterpretar)

Cópia resumida para consulta. Se divergir do spec ou do [data-model.md](../data-model.md), eles valem.

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

## 7b. Dependências e ordem de execução

- **Fase 1 (Setup)** não depende de nada. **Fase 2 (Fundação)** depende da Fase 1 e bloqueia todas
  as histórias.
- **Fase 3 (US1)** e **Fase 4 (US2)** dependem só da Fase 2. Podem andar em paralelo, mas a ordem
  recomendada é por prioridade: US1 (MVP) antes de US2.
- **Fase 5 (teste)** depende de US1 **e** US2 congelados (T-3.6 e T-4.10 commitados). Roda uma vez
  só (R2). Qualquer modelo extra (FR-14) entra antes dela.
- **Fase 6 (US3)** depende dos artefatos de US1 e US2. O esqueleto do app pode começar na Fase 2
  com modelos fictícios; a versão final usa os artefatos congelados.
- **Fase 7 (relatório)** pode ser escrita ao longo do projeto; fecha depois das Fases 5 e 6.
- **Checkpoints:** o critério de saída de cada marco (spec §3.18) é o checkpoint da fase.
- **Paralelismo dentro das fases:** tarefas `[P]` (ex.: T-2.2, T-2.4 e T-2.5; T-4.1). Tarefas que
  mexem no mesmo arquivo (ex.: T-3.1 a T-3.5 em `explain.py`) são sempre sequenciais.

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
| 2026-11-14 | T-2.0 | Dependências instaladas; `config.py` e `verify.py` implementados (58 testes passando) | `config/base.yaml`, `config/esperado.yaml`, `src/dengue_sinan/config.py`, `src/dengue_sinan/verify.py` |
| 2026-11-14 | T-2.2 | Guarda `assert_dev_only` e `assert_dev_years` implementada e testada | `src/dengue_sinan/guard.py`, `tests/test_guard.py` |
| 2026-11-15 | T-2.1 | Verificado no Colab (`passou: true`): 2.453.208 casos dev (2022: 1.148.299; 2023: 1.304.909) e 3.985 eventos (2022: 1.869; 2023: 2.116); fluxograma idêntico ao profiling | `reports/verificacao/T-2.1.json`, `reports/fluxograma.md` |
| 2026-11-15 | T-2.3 | Verificado no Colab (`passou: true`): 5 dobras LORO (SE 1.736, S 810, CO 736, NE 582, N 121 eventos); `sha256_dobras = c5289b35579f3eef5013f068738deebbee22aa48ce1c2489f805a845780253cc` | `reports/verificacao/T-2.3.json` |
| 2026-11-14 | T-2.4 | Métricas (`pr_auc`, `roc_auc`, `brier`, `calibration_slope_intercept`, `threshold_metrics`, `best_f2_threshold`, `net_benefit`, `bootstrap_ci`, `paired_bootstrap_diff`) implementadas e testadas | `src/dengue_sinan/metrics.py`, `tests/test_metrics.py` |
| 2026-11-14 | T-2.5 | Rastreamento MLflow (`start_run`, `log_fold_metrics`, `log_oof_predictions`) implementado e testado | `src/dengue_sinan/tracking.py`, `tests/test_tracking.py` |
| 2026-11-15 | T-2.6 / T-2.7 | Verificados no Colab (`passou: true`): 21 pares avaliados, **15 pares com ≥ 10 eventos** e **75 combinações de 3+ com ≥ 10 casos**; nenhuma célula < 10 casos exposta | `reports/verificacao/T-2.6.json`, `reports/verificacao/T-2.7.json`, `reports/descritiva/` |
| 2026-11-15 | T-2.8 | Verificado no Colab (`passou: true`): B0 PR-AUC OOF = 0,0015; B1 PR-AUC OOF = 0,0128 (média dobras 0,0126, ROC-AUC 0,7241); B2 recall = 0,6843, precisão = 0,0042, F2 = 0,0206 | `reports/verificacao/T-2.8.json`, `reports/baselines.md` |
| 2026-11-15 | T-3.1 a T-3.5 | Verificado no Colab (`passou: true`): E1 convergiu em 31,08 s com 15 pares (≥ 10 eventos); topo do ranking: `HEMATOLOG` (OR 9,25 [7,22–11,86]) e `RENAL` (OR 6,76 [5,04–9,07]); precisão do bundle < 1e-9 | `reports/verificacao/T-3.1_a_T-3.6.json`, `reports/e1/` |
| 2026-11-14 | T-3.6 | Serialização `save_bundle` e `load_bundle` implementada e testada (precisão < 1e-9) | `src/dengue_sinan/artifacts.py`, `tests/test_artifacts.py` |
| 2026-11-14 | T-4.0 | Espaço de busca (Q-08) aprovado pelo Programador e registrado em `config/base.yaml` | `config/base.yaml` |
| 2026-11-14 | T-4.1 a T-4.3 | `preprocess.py`, `cv.py`, `mlp.py`, `tabfm.py` e `tuning.py` implementados e testados localmente | `src/dengue_sinan/preprocess.py`, `src/dengue_sinan/cv.py`, `src/dengue_sinan/mlp.py`, `src/dengue_sinan/tabfm.py`, `src/dengue_sinan/tuning.py` |
| 2026-11-15 | T-4.3b a T-4.10 | Sessão única M1 verificada no Colab (`passou: true`, GPU L4, 53 GiB RAM): PR-AUC média — `mlp` 0,0284, `xgboost` 0,0283, `catboost` 0,0271, `elastic_net` 0,0266, `random_forest` 0,0262, `tabfm` 0,0121; vencedor **`elastic_net`** por desempate técnico (§1.4); `sha256_m1 = 2f65a1ccf183d5f79bbac5eab6062906033f502c044562bd5c3be9bcc6371ce2` | `reports/verificacao/sessao-m1.json`, `reports/m1/`, `reports/shap/` |
| 2026-11-15 | T-5.1 a T-5.4 | Avaliação única no teste 2024 concluída e lacrada (`passou: true`; 5.331.745 casos, 11.338 eventos): M1 PR-AUC = 0,0295 [0,0277–0,0316], ROC-AUC = 0,8132, Brier = 0,0021, slope = 0,9378; diff(M1−B0) = +0,0263 [0,0239–0,0317] (SC-01 passou); diff(M1−B1) = +0,0119 [0,0095–0,0158] (SC-02 passou); SC-03 falhou (recall M1 0,2056 vs B2 0,6601, precisão M1 0,0468 vs B2 0,0053); SC-04 passou (slope 0,9378 ∈ [0,8, 1,2]) | `reports/teste/LACRE.json`, `reports/teste/metricas.md`, `reports/teste/subgrupos.md`, `reports/teste/erros.md`, `reports/verificacao/T-5.1_a_T-5.4.json` |
| 2026-11-15 | T-6.1 a T-6.4 | App Streamlit com abas Perfil (E1) e Triagem (M1) alimentado pelos bundles congelados (`models/e1_final.joblib`, `models/m1_final.joblib`) e testado (< 1 s para 20 perfis; R7 conferida) | `src/app/streamlit_app.py`, `tests/test_streamlit_app.py`, `models/` |
| 2026-11-15 | T-7.1 a T-7.3 | Relatório TRIPOD+AI completo consolidado com as métricas verificadas de E1, M1 e teste 2024 + apêndices e checklist final (`requirements.md` e NFR-02 conferidos) | `reports/relatorio_tripod_ai.md`, `specs/checklists/requirements.md` |

---

## 10. Registro de problemas

Todo erro inesperado entra aqui **antes** de qualquer correção (regra 4b). Uma linha por problema;
se houver várias tentativas, uma linha por tentativa.

| Data | Tarefa | O que aconteceu (mensagem de erro ou número estranho) | O que foi tentado | Resultado | Precisou perguntar? |
|---|---|---|---|---|---|
| 2026-11-14 | T-2.0 | `uv add` falhou com `No interpreter found for Python 3.13.18` (`.python-version` exigia patch 3.13.18, mas o ambiente local tem 3.13.12) | Alterar `.python-version` para `3.13` (compatível com `requires-python >=3.13,<3.14`) | `uv add` instalou todos os pacotes e os 58 testes passaram | Não (correção técnica local) |
| 2026-11-14 | T-2.5 | MLflow 3.18 recusou `FileStore` (`file:///.../mlruns`) por padrão com `MlflowException: The filesystem tracking backend is in maintenance mode` | Definir `os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")` em `src/dengue_sinan/tracking.py` para manter o armazenamento em `mlruns/` previsto na T-2.5 | Testes de `tracking.py`, `baselines.py`, `tuning.py` e `runner.py` passaram | Não (compatibilidade com MLflow 3.x) |
| 2026-11-15 | T-4.9 | Na sessão do Colab, após concluir os 6 modelos às 07:37, `select_best_model` ficou >5h40 em `paired_bootstrap_diff` / `bootstrap_ci` porque `average_precision_score` reordenava 2,45M linhas 48.000 vezes (~6,8 s/iteração, estimado ~42 h) | Pré-calcular os limiares distintos dos casos positivos (`K <= n_pos`) e vetorizar as 1.000 reamostras estratificadas em `metrics.py` e `runner.py` (mesma definição matemática de Average Precision não-interpolada, reduzindo de ~42 h para ~6 s) | 21 pares + 6 ICs com `n_boot=1000` em 2,45M linhas executam em < 10 s; todos os testes passam | Sim (autorizado pelo Programador) |
| 2026-11-15 | T-6.4 | `joblib.load` dos bundles gerados no Colab (SciPy 1.14) falhou no ambiente local (SciPy 1.15+) com `ValueError: too many values to unpack (expected 2)` em `BSpline.__setstate__` | Adicionar shim `_ensure_scipy_bspline_compat()` em `src/dengue_sinan/artifacts.py` para aceitar estado `dict` do SciPy 1.14 sem alterar os bytes/SHA-256 dos `.joblib` | `e1_final.joblib` e `m1_final.joblib` carregam sem erro e executam 20 perfis em 0,958 s (`47,91 ms/perfil`) | Não (compatibilidade de unpickle entre versões do SciPy) |
