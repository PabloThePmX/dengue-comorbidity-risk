# Tarefas — como usar, ordem e registros

> Este arquivo só **traduz** os outros documentos em tarefas. Leia antes: o objetivo em
> [goal.md](../goal.md) e as regras R1–R10 e as decisões reservadas na
> [constituição](../constitution.md). Se algo aqui discordar dela, do spec ou do plan, vale o de
> cima: pare e avise o Programador.
> Marco 1 (dados e profiling) está **concluído**: ver [profiling/RESULTADOS.md](../../profiling/RESULTADOS.md).

---

## Arquivos e ordem

Cada arquivo é **um marco** ([spec › Marcos](../spec.md#marcos)): o Marco N fica em `0N-…md` e
suas tarefas são `T-N.x` (D-60). O critério de saída do marco no spec é o checkpoint do arquivo.

| Arquivo | Marco | Tarefas | Começa quando |
|---|---|---|---|
| [02-fundacao.md](02-fundacao.md) | 2 — Descrição, split e baselines | T-2.0 a T-2.8 | Já pode (Marco 1 concluído). Bloqueia todos os outros. |
| [03-us1-perfil.md](03-us1-perfil.md) | 3 — E1, perfil de risco (US1, MVP) | T-3.1 a T-3.6 | 02 todo `[x]` |
| [04-us2-triagem.md](04-us2-triagem.md) | 4 — M1, triagem (US2) | T-4.0 a T-4.10 | 02 todo `[x]`; ordem recomendada: depois do 03 |
| [05-teste-final.md](05-teste-final.md) | 5 — Avaliação final no teste, uma vez | T-5.1 a T-5.4 | 03 e 04 todos `[x]` e commitados, e o "ok" do Programador (D-71). Extras que são modelos (FR-14) entram antes. |
| [06-us3-demo.md](06-us3-demo.md) | 6 — Demo (US3) | T-6.1 e T-6.4 | 05 todo `[x]`. O esqueleto pode começar no Marco 2 com modelos fictícios. |
| [07-relatorio.md](07-relatorio.md) | 7 — Relatório | T-7.1 e T-7.3 | Escrito ao longo do projeto; fecha depois de 05 e 06. |

- O **marco atual** é o primeiro arquivo, em ordem numérica, que ainda tem tarefa `[ ]` ou `[~]`.
  Leia este arquivo e o do marco atual; os outros, só se a tarefa citar.
- Os Marcos 3 e 4 dependem só do 2 e podem andar em paralelo; a ordem recomendada é por
  prioridade (US1 antes de US2).
- Dentro de um arquivo, tarefas `[P]` podem rodar em paralelo (ex.: T-2.2, T-2.4, T-2.5; T-4.1).
  Tarefas que mexem no mesmo arquivo de código são sempre sequenciais.

## Equipe de agentes

Para executar as tarefas com agentes (D-65), diga "Kakashi, execute os passos" (ou `/kakashi`). O
fluxo completo está na skill [kakashi](../../.claude/skills/kakashi/SKILL.md).

| Agente | Papel | Quando |
|---|---|---|
| Kakashi (sessão principal) | Orquestra, pergunta ao Programador nos 🛑, marca `[x]` e escreve o Registro de execução | Sempre |
| [Naruto](../../.claude/agents/naruto.md) | Implementa a tarefa e roda a verificação no Colab | Cada tarefa |
| [Sakura](../../.claude/agents/sakura.md) | Valida os testes contra o "Pronto quando" | Cada tarefa |
| [Sasuke](../../.claude/agents/sasuke.md) | Audita critério de saída, R1–R10, decisões e escopo | Fim de cada marco |

As regras desta página valem igual com ou sem agentes.

## Formato das tarefas

`### [ ] T-N.x [P] [USn] — título`

- Estado: `[ ]` a fazer; `[~]` feita, aguardando o relatório do Colab pelo caminho manual
  ([Verificação no Colab](#verificação-no-colab)); `[x]` pronta.
- `[P]`: pode rodar em paralelo com outras `[P]` do mesmo arquivo.
- `[USn]`: história do spec que a tarefa entrega (US1 perfil, US2 triagem, US3 demo).
- Tarefa fundida em outra fica ~~riscada~~ com o destino; os IDs nunca são reaproveitados.

## Como executar uma tarefa

1. Pegue a **primeira** tarefa `[ ]` (ou `[~]`) do marco atual e leia só o que ela cita.
2. Siga os passos. Código novo em `src/dengue_sinan/` (demo em `src/app/`), teste em `tests/`,
   configuração em `config/`; notebooks só chamam funções (NFR-05).
3. Em **🛑 PARE E PERGUNTE**: não continue. Descreva as opções ao Programador e espere a resposta.
   Nunca escolha sozinho nada da lista de
   [decisões reservadas](../constitution.md#decisões-reservadas-ao-programador).
4. Não edite `constitution.md`, `spec.md` nem `plan.md` para "fazer caber" o código. Se algum
   precisar mudar, pergunte.
5. Rode `uv run pytest -q` e `uv run ruff check .` (ambiente local e problemas comuns:
   [quickstart › Local](../quickstart.md#local)).
6. Marque `[x]` só quando **todos** os itens do "Pronto quando" foram verificados rodando comandos.
   Se algum item só se verifica no Colab, siga a [Verificação no Colab](#verificação-no-colab).
7. Escreva uma linha no [Registro de execução](#registro-de-execução).

## Verificação no Colab

**Ninguém digita resultado à mão** (D-56). Onde a verificação roda depende do marco (D-66):

- **Marcos 2 e 3: no PC local**, com 2022 e 2023 em `data/` (fora do git). A função de verificação
  roda direto e grava o JSON em `reports/verificacao/`; os relatórios nascem em `reports/`. Valem
  só os passos 1, 3 e 7 abaixo; não há Colab nem `[~]`.
- **Marcos 4 e 5: no Colab**, pelo MCP (D-64); sem ele, pelo caminho manual. O Colab grava
  **agregados em texto** (tabelas, pontos de curva, médias de SHAP); traga cada arquivo como o JSON
  (passo 6, com SHA-256) e desenhe os gráficos localmente a partir deles.

**Preparar (sempre):**

1. Escreva a verificação **como código**: uma função em `src/` que calcula cada item do "Pronto
   quando" e chama `verify.write_report` (T-2.0), comparando com `config/esperado.yaml`. Nunca
   escreva números esperados no notebook.
2. Acrescente ao notebook da tarefa a célula que chama essa função.
3. Faça e verifique localmente tudo o que der: código, testes com dados sintéticos (inclusive da
   própria verificação), ruff.
4. No Colab, o código precisa estar commitado e no GitHub, porque o Colab clona o repositório. O
   orquestrador faz o commit e o push na `main` antes de cada execução, com mensagem de uma linha e
   sem co-autoria (D-66).

**Pelo MCP (padrão):** passos do lado do Programador em
[quickstart › Colab pelo MCP](../quickstart.md#colab-pelo-mcp).

5. Conecte com `open_colab_browser_connection` e rode, com `run_code_cell`, as células do notebook
   da tarefa (só chamadas de função). Antes, confira o ambiente com `verify.environment(cfg)`; se a GPU
   ou a RAM não forem as do config, peça ao Programador para trocar e salvar de novo.
6. Rode `verify.show_report(<caminho do arquivo>)`, que imprime o arquivo (JSON ou outro texto de
   agregados) e o SHA-256 dos bytes. Salve-o no mesmo caminho em `reports/`, calcule o SHA-256
   localmente e confira que é igual. Se não for, não use o arquivo: registre em
   [Erros inesperados](#erros-inesperados).
7. Leia o JSON:
   - `"commit"` diferente do commit que contém o código da tarefa → rode de novo depois do push;
   - `"passou": true` → marque `[x]` e copie o resumo dos `checks` para o Registro de execução;
   - `"passou": false` → registre os checks que falharam em [Erros inesperados](#erros-inesperados)
     e não marque `[x]`.
8. Células rodadas pelo MCP **só imprimem agregados** (R7): tudo o que aparece na saída passa pela
   conversa. Nunca mostre um `DataFrame` linha a linha.

**Manual (reserva, sem o MCP):** marque a tarefa `[~]`, anote no Registro de execução "pendente no
Colab: rodar <notebook>, célula <nome>; gera `reports/verificacao/T-N.x.json`" e **pare**. Na
sessão seguinte, se o arquivo estiver na pasta, siga o passo 7; se não estiver, peça ao Programador
só para rodar o notebook e colocar o arquivo lá (não peça números).

Nunca passe para o marco seguinte com uma tarefa `[~]` aberta.

**Sessão dos modelos (Marco 4, D-57):** T-4.3b a T-4.10 compartilham um único relatório,
`reports/verificacao/sessao-m1.json`, e a execução real é uma só, depois que todas estiverem
prontas localmente. Pelo MCP, dispare `run_all_models` **em segundo plano** (processo separado, com
log no Drive), acompanhe com células curtas que leem o relatório da sessão e avise o Programador a
cada bloco concluído. Se a sessão reiniciar, o job morre: confira o que ficou no Drive e dispare de
novo, porque a execução retoma de onde parou (D-53). No fim, faça os passos 6 e 7 com o
`sessao-m1.json` e marque `[x]` cada tarefa cujo bloco tem `"passou": true`. Sem o MCP, marque
cada uma `[~]` e pare depois da T-4.10, pedindo a sessão do Colab.

## Erros inesperados

Algo quebra, não converge, estoura memória ou dá número estranho:

1. Registre **sempre** no [Registro de problemas](#registro-de-problemas), antes de qualquer outra
   coisa.
2. Pode tentar **correções técnicas** que não mudam nenhuma decisão do spec, registrando cada
   tentativa e o resultado. Exemplos: aumentar iterações do otimizador, trocar o método numérico
   (`newton` → `lbfgs`), reduzir `batch_size`, liberar memória, reiniciar a sessão.
3. **🛑 PARE E PERGUNTE** se a correção exigir mudar algo decidido no spec. Exemplos: tirar uma
   variável ou interação, mudar a população, usar outro modelo, mexer em limiar, mexer no teste,
   corrigir desbalanceamento.

## Referência rápida

Só o que é de implementação e não está em outro lugar. Features: [data-model › Dicionário de
features](../data-model.md#dicionário-de-features). Números esperados:
[data-model › Tamanho e prevalência](../data-model.md#tamanho-e-prevalência) e
[Eventos por região e subgrupo](../data-model.md#eventos-por-região-e-subgrupo). Métricas e
limiar: [spec › Plano de avaliação](../spec.md#plano-de-avaliação). Seleção:
[plan › Regra de seleção](../plan.md#regra-de-seleção).

- Parquets por ano em `data/parquet/dengue_{ano}.parquet` (todas as colunas como **texto cru**),
  manifesto em `data/manifest.json`, gerados por `download.fetch_year` (FR-01, já pronto). No PC
  local, só 2022 e 2023 (D-66; 15,9 GiB de RAM); no Drive, os três anos
  (`MyDrive/dengue-comorbidity-risk/data/`).
- **Ano do split = ano do arquivo** (D-46). Desenvolvimento = 2022 e 2023; teste = 2024.
- Funções já implementadas no Marco 1 — **reutilize, não reescreva**:

| O quê | Regra | Função existente |
|---|---|---|
| População | `CLASSI_FIN` ∈ {10, 11, 12} **e** (`CLASSI_FIN` = 12 **ou** `EVOLUCAO` ∈ {1, 2}) **e** idade válida | `profiling.population_mask` |
| Alvo `y` | 1 se `CLASSI_FIN` = 12 **ou** `EVOLUCAO` = 2; senão 0 | `profiling.target` |
| Idade (anos) | `NU_IDADE_N` decodificado (1º dígito = unidade); se inválido ou fora de [0, 120], ano de `DT_SIN_PRI` − `ANO_NASC`; flag `idade_de_ano_nasc` | `features.age_years_with_fallback` |
| Região | 1º dígito do IBGE de `ID_MN_RESI` (senão `SG_UF`) → Norte, Nordeste, Sudeste, Sul, Centro-Oeste | `features.region_from_ibge` |
| Faixas etárias | 0–4, 5–14, 15–39, 40–59, 60–79, 80+ (só relatório, subgrupo e perfis) | `profiling.FAIXAS` |

## Extras

Só se o Programador pedir.

- FR-14 (M2 pós-alarme): **tem que ser feito antes do Marco 5**; população só `CLASSI_FIN` ∈ {11, 12}.
- FR-16 (sensibilidade 2017–2024).
- FR-10 (CLI `predict`, contrato em [contracts › Entrada de casos](../contracts/interfaces.md#entrada-de-casos)).
- Análise de sensibilidade de duplicatas com chave estrita (D-47).

---

## Registro de execução

Uma linha por tarefa concluída: data, tarefa, resultado principal (números), onde está o artefato.

| Data | Tarefa | Resultado | Artefato / run MLflow |
|---|---|---|---|
| 2026-11-03 | Marco 1 | Profiling concluído: 7.784.953 casos, 15.323 eventos (2022–24) | `profiling/RESULTADOS.md` |
| 2026-11-16 | T-2.0 | 67 testes passam (48 + 19 novos) e ruff limpo; `sha256_dbc` de 2022 e 2023 igual ao do profiling; 2024 não baixado; `uv sync --check` ok (165 pacotes; torch só CPU); `.python-version` passou a `3.13` (decisão do Programador) | `config/base.yaml`, `config/esperado.yaml`, `src/dengue_sinan/config.py`, `src/dengue_sinan/verify.py` |
| 2026-11-16 | T-2.1 | 85 testes passam e ruff limpo; `reports/verificacao/T-2.1.json` com `"passou": true` em 19 checks: 2.453.208 casos e 3.985 eventos (2022–23), 4 etapas do fluxograma por ano iguais ao profiling; sem 2024 e sem células < 10 (R7). O campo `commit` do JSON é `c1e60c2`, anterior ao código (sem commit ainda) | `src/dengue_sinan/dataset.py`, `checks.py`, `verificacao_populacao.py`; `reports/fluxograma.md`, `reports/verificacao/T-2.1.json` |
| 2026-11-16 | T-2.2 | 90 testes passam e ruff limpo; `assert_dev_only` lê `ano_teste` do config e recusa 2024. O `grep` do "Pronto quando" passa de forma vazia: ainda não existe função de treino, então a chamada do guard fica obrigatória nas tarefas que criarem funções de treino, tuning, calibração, limiar ou seleção (T-2.3 em diante) | `src/dengue_sinan/guard.py`, `tests/test_guard.py` |
| 2026-11-16 | T-2.3 | 107 testes passam e ruff limpo; `reports/verificacao/T-2.3.json` com `"passou": true`: eventos por dobra 736/582/121/1.736/810 (Centro-Oeste/Nordeste/Norte/Sudeste/Sul, total 3.985), 2.453.208 casos, hash do conteúdo das dobras `09e29252…a0ea` igual em duas execuções, `sha256_dbc` de 2022 e 2023 iguais ao manifesto. Nenhuma região nula. Programador aprovou a coluna `LINHA` em `load_population` e o formato largo das dobras (`papel_<região>`). O check do hash compara duas execuções; o valor fixo é conferido no Colab (T-4.3b). `commit` do JSON anterior ao código (sem commit ainda) | `src/dengue_sinan/folds.py`, `verificacao_folds.py`; `reports/verificacao/T-2.3.json`; `data/folds/dobras_dev.parquet` (fora do git) |
| 2026-11-16 | T-2.4 | 128 testes passam e ruff limpo. 1ª rodada da Sakura reprovou por lacuna de teste (nada distinguia o intercept com offset do ajuste livre); corrigida com testes novos, e a 2ª rodada comprovou por mutação real que eles falham com o código errado (intercept livre: 2 testes falham; índices independentes no pareado: 3 falham). Pendência de custo para a T-4.9: bootstrap pareado ≈ 3 s por reamostra em 2,45 M de linhas (≈ 50 min por par com 1.000 reamostras), a decidir com o Programador | `src/dengue_sinan/metrics.py`, `tests/test_metrics.py` |
| 2026-11-16 | T-2.5 | 141 testes passam e ruff limpo. Run de teste lido de volta pela API do MLflow (não pela UI) com config, seed, hashes do manifesto, `git_commit` e hardware; OOF só em `data/oof`, nunca em `mlruns/` nem `reports/` (R7). Programador decidiu manter o backend em pasta `mlruns/` com opt-out `MLFLOW_ALLOW_FILE_STORE` (MLflow 3.18 o marca como "maintenance mode"; `pyproject` trava `mlflow<4`); 1ª rodada da Sakura reprovou por falta de teste do opt-out, corrigida e confirmada por mutação | `src/dengue_sinan/tracking.py`, `tests/test_tracking.py`; `verify._commit` virou `verify.commit_atual` |
| 2026-11-16 | T-2.6 (inclui a antiga T-2.7) | 173 testes passam e ruff limpo; 2.453.208 casos e 3.985 eventos. **15 de 21 pares têm ≥ 10 eventos** (as únicas interações reportadas no E1) e **75 de 99 combinações exatas de 3+ têm ≥ 10 casos** (entram nos perfis); só 3 das 99 têm ≥ 10 eventos. R7 conferido de forma independente pela Sakura (nenhuma contagem 1–9, nada de 2024, nada linha a linha). Decisão do Programador: supressão complementar escondia o `Sim` das 7 comorbidades sem proteger de verdade (totais públicos permitem deduzi-lo por subtração), então a exibição publicada funde `Ausente` com `Não` ("Não ou ausente") e `Amarela` com `Indígena`; o E1 e os CSV internos mantêm os 3 níveis (D-07). **Pendente: regra do Sexo `I`** (7 eventos; `M` suprimido como complemento, M + I dedutível pelo total) | `src/dengue_sinan/descriptive.py`, `tests/test_descriptive.py`; `reports/descritiva/*.md` e 3 PNGs; contagens internas em `data/descritiva/` (fora do git) |
| 2026-11-16 | T-2.8 | 214 testes passam e ruff limpo; execução real de ~12 min sem aviso de convergência. OOF (2.453.208 casos, 3.985 eventos), recalculado de forma independente pela Sakura a partir das predições: **B0** PR-AUC 0,00151 (≈ prevalência 0,00162), Brier 0,00162; **B1** PR-AUC 0,01284, ROC 0,711, Brier 0,00161, slope 1,048, intercept −0,053; **B2** recall 0,684, precisão 0,0042, F2 0,0206. B1 supera B0 (~8× a prevalência; Nordeste a pior dobra: ROC 0,64, slope 0,64). O ROC < 0,5 do B0 agrupado é artefato (prevalências de treino diferem entre dobras; por dobra o ROC é 0,5). 3 runs FINISHED no MLflow (tag `baseline` = B0/B1/B2), lidos de volta pela API. B2 usa `LACO` e `PETEQUIA_N` (critério do grupo B do protocolo, `[ASSUMPTION]`); a Sakura não verificou se esses campos existem no momento da predição | `src/dengue_sinan/baselines.py`, `verificacao_baselines.py`; `reports/baselines.md`, `reports/verificacao/T-2.8.json`; OOF em `data/oof/` (fora do git) |
| 2026-11-16 | T-3.1 | 234 testes passam e ruff limpo. E1 convergiu (GLM binomial sem penalização, IRLS, 25 iterações): 2.453.208 casos, 3.985 eventos em 9.316 padrões de covariáveis, 44 parâmetros, log-verossimilhança −26.755,25; **tempo de ajuste 1,2 s** (pipeline com carga dos dados ≈ 395 s). 15 pares incluídos e 6 "eventos insuficientes" (lidos de `data/descritiva/pares_comorbidades.csv`). Decisões: base de spline natural própria no lugar do `patsy.cr` (colide com o intercepto: posto 5 de 6); ajuste agrupado por padrão de covariáveis, equivalência 5e-15; interações com idade **recentradas na idade 40**, então `DIABETES: Sim` e `HIPERTENSA: Sim` são o log-OR aos 40 anos (OR 2,98 [2,30; 3,86] e 2,67 [2,24; 3,20]; o ranking não depende da idade entre 33 e 60 anos); 8 coeficientes com < 10 eventos no nível (Sexo `I` e os `Ausente`) suprimidos (R7). Sakura conferiu os contrastes por idade, os 44 parâmetros e fez mutação | `src/dengue_sinan/explain.py`, `tests/test_explain.py`, `reports/e1/coeficientes.md`; ajuste sem dados em `data/e1/` (fora do git) |
| 2026-11-16 | T-3.2 (inclui as antigas T-3.3 e T-3.4) | 257 testes passam e ruff limpo. OR das 7 comorbidades (HEMATOLOG 9,32; RENAL 6,80; AUTO_IMUNE 5,02; HEPATOPAT 4,89; DIABETES 2,98 e HIPERTENSA 2,67 aos 40 anos; ACIDO_PEPT 0,70 [0,42; 1,17]); 15 pares com OR da interação e p ajustado por Benjamini-Hochberg; RERI e AP por par com IC delta (oficial, D-40) e simulação paramétrica (sensibilidade): 3 pares **sensíveis ao método** (HEMATOLOG × RENAL, HEMATOLOG × AUTO_IMUNE, HIPERTENSA × AUTO_IMUNE). Ranking só pelo E1 (R10): HEMATOLOG > RENAL > AUTO_IMUNE > HEPATOPAT > DIABETES > HIPERTENSA > ACIDO_PEPT, com 7 pares "sem ordem definida". Sakura recalculou de forma independente OR, BH, RERI/AP, delta e simulação e fez mutação | `src/dengue_sinan/explain.py`, `tests/test_explain_or.py`; `reports/e1/or_interacoes.md`, `reri_ap.md`, `ranking.md` |
| 2026-11-16 | T-3.5 (+ extra: investigação do padrão suspeito) | 299 testes passam e ruff limpo. Tabela de perfis com 940 linhas: G1 1 perfil, G2 7, G3 21 (15 no E1 e 6 "dados insuficientes"), G4 75 combinações (53 de 3 e 4 comorbidades com estimativa e 22 de 5+ sem número, D-78); 359 células publicadas (>= 10 casos observados). Sakura recalculou risco e IC de 8 perfis (delta) e a calibração: eventos esperados pelo E1 contra observados 2.150/2.197 (0 comorbidades), 887/1.050 (1), 565/603 (2), 124/135 (3+); nas combinações de 3 e 4, 118 contra 131. Padrão suspeito "todas as 7 = Sim" (2.000 casos, 0,08%): população mantida e sensibilidade A oficial (D-77); 1ª rodada da Sakura reprovou por uma contagem 1–9 em prosa em `reports/qualidade/padrao_todas_sim.md` (R7), corrigida e com varredura de prosa nos testes; 2ª rodada aprovada. `reports/verificacao/T-3.5.json` com `"passou": true` (11 checks) e `commit` = c644d43 (anterior às mudanças) | `src/dengue_sinan/explain.py`, `tests/test_perfis.py`, `tests/test_padrao_todas_sim.py`; `reports/e1/perfis_completo.md`, `perfis_resumo.md`, `sensibilidade_padrao_todas_sim.md`; `reports/qualidade/padrao_todas_sim.md` |
| 2026-11-16 | T-3.6 | 317 testes passam e ruff limpo. Artefato do E1 em `models/e1/` (pasta com `metadata.json` + `payload/e1.npz` e `e1.json`; sem pickle, sem dados, 22 KB; formato decidido: pasta com payload seguro, D-81). `load_bundle` carregado SEM `statsmodels` reproduz risco, IC e razão de risco de 10 perfis do Naruto e de outros 10 escolhidos pela Sakura com diferença 0,0 (tolerância 1e-9); carga + risco de um perfil ≈ 0,015 s (NFR-06 < 1 s). Metadata com versão do código, hashes dos dados (iguais ao manifesto), config, data de treino (aproximada pelo mtime do ajuste salvo, `[ASSUMPTION]`), métricas de validação (E1 é inferência: aviso explícito), features, versões das bibliotecas e SHA-256 do payload; byte adulterado, `schema_version` futuro e tipo desconhecido recusam a carga. Sem contagens 1–9 (R7/NFR-03). Mutação feita pela Sakura (verificação do hash desligada: 2 testes falham). `commit` do bundle e do JSON = c644d43, anterior ao código: regenerar após o commit | `src/dengue_sinan/artifacts.py`, `verificacao_artefatos.py`, `tests/test_artifacts.py`; `models/e1/`; `reports/verificacao/T-3.6.json`; `config/base.yaml` (`caminhos.modelos`) |
| 2026-11-16 | Marco 3 (auditoria do Sasuke) | Critério de saída cumprido (OR com IC e Benjamini-Hochberg; só 15 pares com >= 10 eventos; ranking com 7 pares "sem ordem definida"; perfis com células < 10 suprimidas; artefato `models/e1/`); 317 testes e ruff limpo; sem violação de R1–R10; 2024 intocado. Decisões do período registradas: D-73 a D-81 em `research.md`. **D-79 (2026-11-16): B2 mantém `LACO` e `PETEQUIA_N`** e a limitação (um "Não" pode ser "não foi feito") vai para o relatório; o Marco 4 mede a completude desses campos. Pendências da auditoria: commit do Marco 3 (aguarda o "ok" do Programador), regerar os JSON e o bundle depois do commit para o `commit` apontar para o código, seção do E1 em `config/esperado.yaml`, guard nos auxiliares públicos, notas no plan | — |
| 2026-11-16 | PAUSA (HD desconectado pelo Programador) | Estado: 317 testes passam e ruff limpo; nenhum processo vivo. Marco 3 cumprido, **sem commit** (autorizado: commit local, sem push). Para retomar, em ordem: (1) Naruto: seção `e1` já foi acrescentada ao `config/esperado.yaml`; falta fazer os checks de `reports/verificacao/T-3.5.json` e `T-3.6.json` compararem com ela (sem regerar os JSON ainda) e chamar `assert_dev_only` em `checar_equivalencia`, `contagens_por_padrao`, `padrao_todas_sim` e `resumo_padrao` (`explain.py`), com testes; (2) Sakura valida; (3) commit local do Marco 3 (uma linha, sem co-autoria); (4) regerar `reports/verificacao/T-3.5.json`, `T-3.6.json` e `models/e1/` para o campo `commit` apontar para o código, e segundo commit pequeno; (5) reauditar o Marco 3 (Sasuke, focado) e parar: o Marco 4 roda no Colab e pede ações do Programador (conectar, autorizar o Drive, escolher o ambiente) e um push antes de cada execução (D-66) | — |
| 2026-11-16 | Marco 2 (auditoria do Sasuke) | Critério de saída cumprido; 214 testes e ruff limpo; sem violação de R1–R10. Decisões do Programador na auditoria: (1) Sexo `I`: manter a supressão com nota no cabeçalho (M + I dedutível pelo total), e a mesma nota no fluxograma; (2) B2 mantém `LACO` e `PETEQUIA_N` e a limitação (um "Não" pode ser "não foi feito") vai para o relatório; **no Marco 4, medir a completude desses dois campos (proporção de `Ausente`) e anotar ao lado do B2**; (3) commit local sem push; (4) atualizar quickstart e plan (feito). `gestante` derivado = `CS_GESTANT` 1–4 confirmado em `profiling.GESTANTE_SIM`. Pendente de decisão para a T-4.9: custo do bootstrap pareado | — |

---

## Registro de problemas

Todo erro inesperado entra aqui **antes** de qualquer correção ([Erros inesperados](#erros-inesperados)).
Uma linha por problema; se houver várias tentativas, uma linha por tentativa.

| Data | Tarefa | O que aconteceu (mensagem de erro ou número estranho) | O que foi tentado | Resultado | Precisou perguntar? |
|---|---|---|---|---|---|
| 2026-11-15 | T-2.0 | `uv` não está no caminho do quickstart (`%APPDATA%\Python\Python313\Scripts\uv.exe` não existe); `python3.13.exe` em `.local\bin` é um trampolim quebrado | Achado `uv` 0.13.4 em `%APPDATA%\Python\Python314\Scripts\uv.exe` e usado dali | Funcionou | Não |
| 2026-11-15 | T-2.0 | `uv add` falhou ao gravar `pyproject.toml`: "os error 1224" (arquivo com seção mapeada pelo usuário); o `pyproject.toml` ficou parcialmente escrito e o `uv.lock` não | `git checkout -- pyproject.toml` (só a mudança desta execução) e novo `uv add` | Na 2ª tentativa gravou `pyproject.toml` e `uv.lock`; `uv lock --check` passa | Não |
| 2026-11-15 | T-2.0 | `uv add` e `uv sync` pararam na etapa de instalação, depois de "Prepared 21 packages" (o log só mostra "Using request connect timeout"; sem escrita em disco por mais de 40 min). Eu encerrei o processo duas vezes, o que deixou `scipy` incompleto em `.venv` (`scipy._lib` ausente; `import xgboost` falha) | `uv sync --reinstall-package scipy`; remoção do diretório parcial `.venv/Lib/site-packages/scipy`; `uv cache clean scipy`; `uv sync` (log em `scratchpad/uv_sync_t.log`) | Não resolvido: a cópia do `scipy` para `.venv` parou em 23:16 nos primeiros módulos e o `uv` ficou parado; encerrado por mim. `pytest` e `ruff` seguem funcionando (não importam scipy) | Sim (resolvido: causa-raiz na linha seguinte) |
| 2026-11-16 | T-2.0 | Causa-raiz dos travamentos de instalação: virtualização de `%APPDATA%` do app MSIX (a instalação gravava em caminho virtualizado) somada a chave de registro stale do CPython 3.13.18; pacotes devem ser instalados no terminal do Programador | Ambiente recriado pelo Programador no terminal dele (`.python-version` = `3.13`, Python 3.13.16); `uv sync` e `uv sync --check` passaram (165 pacotes) | Resolvido no terminal do Programador; verificação feita com `.venv\Scripts\python.exe` (sem `uv sync`) | Não |
| 2026-11-15 | T-2.0 | `nohup ... &` com o download de 2022/2023 terminou com exit 0 e sem nenhum arquivo gerado | Rodado em primeiro plano, com script em `scratchpad/fetch_dev.py` | Funcionou: 2022 e 2023 baixados e convertidos, hashes conferidos | Não |
| 2026-11-16 | T-2.5 | `mlflow.set_experiment` com `tracking_uri` em pasta (backend de arquivos) levanta `MlflowException`: "The filesystem tracking backend ... is in maintenance mode" (MLflow 3.18.0). 10 dos 11 testes de `tests/test_tracking.py` falharam por isso | Antes de corrigir: a opção `MLFLOW_ALLOW_FILE_STORE=true` (opt-out que o próprio erro indica) fica em `start_run`, com `setdefault` para não sobrescrever uma escolha explícita. Migrar para `sqlite:///` ficou como alternativa para o Programador (muda o layout de `mlruns/`) | Resolvido com o opt-out (função `_permitir_backend_de_pasta`, com 2 testes): `tests/test_tracking.py` 13/13, suíte completa 141 testes, ruff limpo. Pendência técnica: o backend de arquivos é o que o MLflow 3.x marca como manutenção; migrar para `sqlite:///` muda o layout de `mlruns/` | Sim (decidido em 2026-11-16: manter o backend de arquivos com o opt-out) |
| 2026-11-16 | T-3.1 | Ajuste do E1 convergiu (44 parâmetros), mas o teste de equivalência agrupado x linha a linha, em 200 mil linhas aleatórias, não rodou: a logística linha a linha (`sm.Logit`) não convergiu (aviso de convergência) e o GLM agrupado acusou matriz singular (diferença de ~3e15). Causa provável: termos raros ("Ausente", sexo I, pares) sem eventos na amostra (separação) | Checagem trocada por uma comparação da log-verossimilhança, do escore e da informação das duas formas no ponto ajustado, na mesma amostra (não exige convergir). A comparação com dois ajustes separados ficou nos testes sintéticos, onde converge (diferença < 1e-6) | Passou: diferença relativa máxima 5,1e-15 em 200 mil linhas; 18 testes do E1 passam | Não |
| 2026-11-16 | T-3.1 | `patsy.cr(idade_anos, df=5)` inclui a constante: posto 5 de 6 com intercepto (medido). Além disso, os nós e o centro dele são calculados sobre as linhas recebidas, e com dados agrupados o modelo mudaria | Base natural própria (`explain._base_spline`), nós nos quantis das linhas, gl colunas sem constante (como `ns(df=)` do R) | Posto completo nos testes e no ajuste real (44 colunas) | Não |
| 2026-11-16 | T-3.2 | `log_or_na_idade` (código da T-3.1) levantava `ValueError` para comorbidade sem termo de idade (ex.: RENAL, HEMATOLOG): procurava a coluna `RENAL x Idade (spline) 1`, que não existe. Os testes da T-3.1 só chamavam DIABETES | Vetor de contraste extraído (`_contraste_or`): o termo de idade só entra para DIABETES e HIPERTENSA (`COM_IDADE`); testes novos em `tests/test_explain_or.py` | Resolvido; 254 testes passam | Não |
| 2026-11-16 | T-3.2 | IC do método delta e IC por simulação (10.000 sorteios) discordam onde o IC é largo: maior diferença nos extremos do RERI = 9,12 (RENAL × AUTO_IMUNE: delta [3,63; 48,77], simulação [9,53; 57,89]). A leitura aditiva muda em 3 pares pela simulação (HEMATOLOG × RENAL, HEMATOLOG × AUTO_IMUNE, HIPERTENSA × AUTO_IMUNE). Causa provável: RERI é exponencial nos coeficientes; o delta é linear e simétrico | Conferido o código: com covariância pequena o delta e a simulação coincidem (teste, diferença < 0,01). Método não trocado (o spec fixa o delta). Os dois IC vão lado a lado em `reri_ap.md` e a divergência está listada | Não resolvido: falta decidir qual IC é o principal (delta do spec, simulação, ou outro) | Sim (decidido em 2026-11-16: delta oficial, simulação como sensibilidade; os 3 pares divergentes saem marcados "sensível ao método") |
| 2026-11-16 | T-3.5 (extra) | Padrão suspeito: 2.000 casos com as 7 comorbidades = Sim (0,08% da população), menos de 10 graves (risco igual ao geral). Dominam os casos de vários pares (60% dos casos com HEMATOLOG e RENAL) e fazem 4 a 5 perfis 3+ saírem com risco menor que o do saudável (todos com 5+ comorbidades) | Investigação em agregados (ano, UF, faixa, sexo, unidades, municípios, datas) e sensibilidade do E1: cenário A (sem o padrão) e B (indicador único), sem alterar a população | Mecanismo não provado: casos dispersos (1.298 unidades, 699 municípios, maior unidade 1,5%, sem lote de data); o que destoa é o pico exato em 7 comorbidades. Sem o padrão: OR de HEMATOLOG 9,3 → 6,9, RENAL 6,8 → 5,4, HEPATOPAT 4,9 → 3,9; ranking troca só a 2ª e a 3ª posições; 2 pares (HEMATOLOG × HEPATOPAT e × RENAL) caem abaixo de 10 eventos. Hipóteses do orquestrador que NÃO se confirmaram: o padrão explicar o ACIDO_PEPT "protetor" (fica mais protetor sem ele) e o indicador único equivaler à exclusão (não equivale: os casos continuam informando idade e DIABETES/HIPERTENSA) | Sim: Programador decidiu manter a população e o E1 principal, com a sensibilidade A como análise oficial, e publicar perfis com estimativa só até 4 comorbidades |
| 2026-11-16 | T-3.5 (extra) | Erros menores da investigação: `DT_NOTIFIC` colidiu no join com a população; a 1ª versão do relatório publicava meses de 2024; `risco_perfil` não aceitava o indicador do padrão no E1 do cenário B | Corrigidos e testados pelo Naruto | Resolvido (286 testes passam e ruff limpo antes do ajuste final) | Não |
