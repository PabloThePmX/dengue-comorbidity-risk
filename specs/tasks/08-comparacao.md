# Marco 8 — Comparação com modelos de outras branches, em 2025 (US4)

> **Leia antes:** [00-como-usar.md](00-como-usar.md) (como executar, Erros inesperados). Os
> registros de execução e de problemas ficam **lá**. Regras novas: [constituição](../constitution.md)
> R1 e R2 (versão 1.5) e a [D-97](../research.md#registro-de-decisões).

Spec: FR-23, SC-09, US4; D-97, D-98, D-99. Contrato dos arquivos:
[contracts › Comparação em 2025](../contracts/interfaces.md#comparação-em-2025). Critério de saída:
[spec › Marcos](../spec.md#marcos). Plano técnico: [plan › Comparação em 2025](../plan.md#comparação-em-2025).

**Por que existe.** O Programador quer saber se o M1 é melhor que os modelos gerados, para o mesmo
problema, nas outras branches do repositório. O teste de 2024 está lacrado (R2): reavaliá-lo
invalidaria o resultado do Marco 5. O ano de 2025 (dados finais do DataSUS, nunca lido por modelo
algum) vira o **ano de comparação**, lido uma única vez, com regras próprias.

**Pré-requisitos:** Marcos 5 e 7 prontos. A comparação **não muda** o M1, o limiar nem os critérios
SC-01 a SC-04 (nada é escolhido por 2025, R1).

**O que entra e o que não entra (conjunto fechado, no [manifesto](../../config/comparacao/manifesto.yaml)):**
`m1_main`, `e1_main`, `b0_main`, `b1_main` e `b2_regra` (projeto); `m1_soneca` (branch `feat/soneca`) e
`m1_lora` (branch `feat/lora`). Fora: `feat/ricardo` (só código de treino, sem artefato) e `mario`
(sem commits novos). O "melhor modelo" de cada branch é o modelo **congelado por ela**, escolhido pela
validação dela (decisão do Programador, 2026-11-24).

> **Nota de processo (D-98).** O trabalho das T-8.1 a T-8.5 foi feito antes deste plano, em
> conversa, sem arquivo de tarefas, sem FR/SC no spec e sem seção no plan. É um desvio do fluxo
> Spec Kit do projeto (planejar primeiro). O plano abaixo regulariza o que já existe, com a evidência
> de cada tarefa, e organiza o que falta. As tarefas já feitas foram auditadas (Sasuke) antes de
> serem marcadas `[x]`.

### [x] T-8.0 — Planejamento: spec, plan, contrato, checklist e D-98

- Acrescentar **US4**, **FR-23**, **SC-09** e o **Marco 8** ao [spec.md](../spec.md); a seção
  Comparação em 2025 ao [plan.md](../plan.md); o contrato ao [contracts/interfaces.md](../contracts/interfaces.md);
  a seção Comparação ao [checklist](../checklists/requirements.md); a linha deste arquivo ao
  [00-como-usar.md](00-como-usar.md); e a **D-98** ao Registro de decisões. IDs novos, sem renumerar.
- Cada escolha que não era do Programador entra como `[ASSUMPTION]` para a revisão dele.
- **Pronto quando:** os links e IDs conferem (grep) e o Sasuke não aponta contradição entre os arquivos.
- **Feita em 2026-11-24**, depois das T-8.1 a T-8.5 (ver nota de processo).

### [x] T-8.1 — Emenda do R1 e do R2 e D-97 (constituição 1.5)

- R1 e R2 passam a tratar o ano de comparação (2025): porta própria, manifesto commitado antes da
  leitura, nada escolhido por 2025, lacre próprio, conjunto fechado de modelos, modelo acrescentado
  depois é exploratório, previsões por caso fora do git (R7).
- **Pronto quando:** `constitution.md` na versão 1.5, D-97 no Registro, linha no Registro de execução.
- **Evidência:** commit `ae1eba5`. Texto revisto pelo orquestrador por delegação do Programador
  (acrescentou manifesto prévio, vedação de escolher por 2025, conjunto fechado e R7).

### [x] T-8.2 — Porta do ano de comparação (`guard.py`, `dataset.py`, `config.py`)

- `config/base.yaml` ganha `ano_comparacao: 2025`; `config.py` recusa que ele esteja em `anos_dev` ou
  seja o `ano_teste` (chave opcional). `guard.leitura_do_ano_de_comparacao()` (por thread,
  aninhável; dentro dela só 2025; vazio recusado; as duas portas juntas recusadas);
  `assert_dev_only` recusa 2025 fora da porta. `dataset.load_population(..., comparacao=True)`.
- **Pronto quando:** testes novos de guard, config e dataset passam, o caminho de 2024 não muda
  (testes antigos sem alteração) e a suíte inteira passa.
- **Evidência:** commit `748b5ed`; 19 testes novos; suíte inteira 1422 passed, 3 skipped, `ruff` limpo.
- **Atenção:** `guard.py`, `dataset.py` e `config.py` mudaram depois do lacre de 2024; a reprodução do
  NFR-02 vale para o commit `7fbe300`.

### [x] T-8.3 — Manifesto e validador (`config/comparacao/manifesto.yaml`, `comparacao_manifesto.py`)

- Conjunto fechado, com SHA-256 de cada artefato, commit e branch de origem, anos de treino, limiar
  próprio e regra, `modelo_por_branch`, orçamentos de alertas e saídas. O validador recusa ano
  diferente do config, modelo treinado em 2025, SHA-256 inválido, ids repetidos e modelo dentro e
  fora do conjunto.
- **Pronto quando:** testes do validador passam e os SHA-256 das branches batem com os blobs do git
  (`git show <ref>:<arquivo> | sha256sum`) e com os lacres delas.
- **Evidência:** commit `26116ce` (e ajustes em `17e5043` e `296d766`); 10 testes; SHA-256 conferidos
  (`lora` `2f65a1cc…`, `soneca` `6286d444…`); limiar exato da `lora` `0.023047375160051217`.

### [x] T-8.4 — Entrada comum e script isolado do `m1_soneca`

- `comparacao_entrada.exportar_entrada` (quadro de features comum, com `ANO` e `LINHA`; só anos de
  desenvolvimento sem a porta; só 2025 com a porta). `scripts/comparacao/prever_soneca.py`, que roda só
  com o python do worktree isolado (`..\_comparacao\soneca`, detached em `2cdf4b3`): confere o
  interpretador, o SHA-256 e o ano **antes** do `joblib.load`; recusa 2024 sempre e 2025 sem
  `DENGUE_PORTA_COMPARACAO=1`; adaptador de 26 variáveis; remapeamento de classes restaurado.
- **Pronto quando:** testes passam (incluindo integração com o worktree real e paridade independente
  do adaptador) e a fumaça roda em amostra de 2022, sem métrica.
- **Evidência:** commit `17e5043`; Sakura APROVADO (95 passed, 0 skip); conformidade: 26 variáveis no
  dicionário (R4), sem correção de desbalanceamento (R3), treino 2022–23.

### [x] T-8.5 — Script isolado do `m1_lora`

- Mesmo molde. Elastic net com calibrador isotônico dentro do objeto; a branch publica
  `predict_proba(feat)[:,1]`, e o script replica. Worktree `..\_comparacao\lora` (detached em
  `af96e97`), ambiente criado pelo Programador (o quickstart proíbe `uv sync` por agentes).
- **Pronto quando:** idem T-8.4.
- **Evidência:** commits `296d766` e `b808c54`; Sakura APROVADO (80 passed, 0 skip; paridade de 500
  linhas, diferença 0,0). **Atenção R7:** o pickle da branch guarda 20 linhas de microdados de 2022–23
  (`background_df`); a cópia só existe no worktree local, e as cópias temporárias foram apagadas.

### [x] T-8.6 — Previsões do próprio projeto dentro da porta (`m1_main`, `e1_main`, `b0_main`, `b1_main`, `b2_regra`)

- `scripts/comparacao/prever_projeto.py` (roda com o `.venv` da main): lê a entrada comum e grava
  `p` (ANO, LINHA) de M1, E1, B0 e B1 com os artefatos congelados; a B2 é a regra
  (`baselines.rule_b2`) sobre a mesma entrada. Mesma recusa de ano, mesma ordem de checagens
  (SHA-256 contra o manifesto **antes** de carregar), mesmo contrato de saída.
- **Feita em 2026-11-24.** `prever_projeto.py` e `tests/test_prever_projeto.py` (42 testes); o M1 roda pelo
  carregador tolerante da demo (`app.servico.carregar_bundle_m1`; o XGBoost do `.venv` não lê o booster
  gravado no Colab); E1 e B2 rodam; B0 e B1, copiados do Drive pelo Programador, rodam (SHA-256 `b6e4ad9c…` e
  `9271ca6f…` conferidos). Só o payload veio, sem `metadata.json`: o script usa os codecs de `baselines_final`
  depois do SHA-256 e a conformidade registra `metadata_json_presente: false`, sem inventar valores. E1:
  decisão **A** (D-99), população principal = casos que o E1 estima (0,16% dos casos e 0,23% dos eventos de
  2022–23 ficam de fora).
- ~~🛑 Copiar `models/b0_final` e `models/b1_final` do Drive~~ Cumprido pelo Programador; os arquivos estão em
  `models/` (ignorado pelo git).
- **Atenção:** `evaluate.predizer` só abre a porta do **teste**; não serve para 2025. O
  `prever_projeto.py` abre `guard.leitura_do_ano_de_comparacao()` e recusa 2024 sempre. Os limiares de B0 e
  B1 do manifesto agora são os exatos de `reports/teste/metricas.json` (`0.0015293309772438427` e
  `0.0011404326369948274`; antes arredondados).
- **Pronto quando:** testes (adaptador, recusa de ano, SHA divergente, paridade com
  `evaluate`/`retreino` sobre linhas de 2022) passam; fumaça em amostra de 2022, sem métrica; JSON de
  conformidade só com nomes e agregados.

### [x] T-8.7 — Avaliador comparativo (`src/dengue_sinan/comparar.py`) [P]

- População principal = linhas com `estimavel = true` no E1 (D-99); população completa como informação.
- Funções puras, sem ler dados reais: carregar as previsões (parquet) e alinhar com o `y` por
  (`ANO`, `LINHA`); recusar linha faltando, duplicada ou `p` fora de [0, 1]; métricas sem limiar
  (PR-AUC, ROC-AUC, Brier, calibration slope e intercepto, observado/esperado, net benefit);
  recall e precisão entre os 5%, 10% e 14% de maior risco `[ASSUMPTION]` (com empates tratados de
  forma estável); recall e precisão no limiar próprio de cada modelo (só informação); bootstrap
  pareado (1.000 reamostras `[ASSUMPTION]`, semente do config, mesmos sorteios para todos) e
  diferenças contra o M1 com IC 95%; regra de leitura: "melhor" só se o IC da diferença excluir 0,
  senão "sem diferença detectável" `[ASSUMPTION]`; tabela de conformidade R3 a R6 por modelo
  (reporta, não exclui); supressão R7 (células < 10).
- Reaproveita `metrics.py` (bootstrap pareado, net benefit, calibração). Código novo só no que falta
  (recall em orçamento de alertas, tabela comparativa).
- O alinhamento é um **join pela chave (`ANO`, `LINHA`)**, que recusa linha faltando, duplicada ou de
  ano diferente (risco de desalinhamento apontado pela auditoria).
- **Pronto quando:** testes com respostas conhecidas (dados sintéticos: modelo perfeito, aleatório,
  empate, empates de `p`, linha faltando, linha duplicada) passam; o módulo **não importa** nenhuma
  função de treino, ajuste ou seleção, nem abre portas, e não lê parquet de dados; `ruff` limpo.

### [x] T-8.8 — Gráficos comparativos (`src/dengue_sinan/comparar_graficos.py`) [P]

- Só a partir dos agregados (R7), como as figuras de `reports/teste/`: (1) PR-AUC com IC por modelo;
  (2) diferenças pareadas contra o M1 (forest plot); (3) recall e precisão contra o orçamento de
  alertas; (4) calibração lado a lado; (5) curva de decisão com todos; (6) tabela de conformidade
  visual. Rodapé com "ano de comparação 2025; avaliação única (R2); só agregados (R7); IC bootstrap".
  Eixos e cores consistentes entre as figuras; legível em preto e branco.
- **Pronto quando:** testes geram as figuras a partir de agregados sintéticos, conferem arquivos e
  rótulos, e recusam agregados com células < 10; as figuras são legíveis (conferência visual do agente).

### [ ] T-8.9 — Orquestrador do ensaio e da execução (`comparar.executar`, `python -m dengue_sinan.comparar`)

- Sequência: (1) **checagens pré-execução** (go/no-go), antes de abrir a porta: o manifesto passa em
  `git status --porcelain` limpo, tem commit que é ancestral do HEAD (molde: `evaluate._arvore_limpa`)
  e o **lacre ausente** (checado antes de ler qualquer dado); SHA-256 dos artefatos **locais** (M1, E1,
  B0, B1) e do `.dbc` de 2025 contra o manifesto; worktrees e ambientes presentes. O avaliador é o
  **único** que define `DENGUE_PORTA_COMPARACAO=1` (a variável é um contrato, não uma porta: teste que
  ela não está definida fora do avaliador); (2) abre a porta e exporta a entrada de 2025; (3) roda os scripts
  isolados com `DENGUE_PORTA_COMPARACAO=1` (subprocess, só o python de cada worktree) e o do projeto;
  (4) alinha, calcula e grava `metricas.json` e os `.md`; (5) grava o **lacre logo depois dos
  agregados e antes das figuras** (`reports/comparacao/LACRE.json`: commit, hash do manifesto, SHA-256
  dos artefatos, das previsões, dos agregados e dos dados, semente, reamostras); (6) gera as figuras só dos
  agregados (idempotente: pode repetir com `--so-graficos` sem reler 2025). Se qualquer script falhar
  **antes** das métricas, nada foi visto e não há lacre; se falhar depois, o lacre já existe e vale.
  Uma segunda execução **falha** (R2).
- **Modo ensaio (`--ensaio`):** a mesma cadeia com um **ano sintético** num diretório temporário (sem
  tocar 2025 nem 2024), para provar a cadeia inteira antes da execução real.
- Código novo em `src/dengue_sinan/comparar_executar.py` (o `comparar.py` não pode importar `guard`: há teste
  estático). A execução real exige o argumento `--confirmo-execucao-unica-em-2025`; `--so-checagens` roda só o
  go/no-go (para a T-8.10).
- **Pronto quando:** o ensaio ponta a ponta passa nos testes (inclusive "segunda execução falha",
  "manifesto alterado recusa", "manifesto sem commit recusa", "lacre depois dos agregados e antes das figuras", "script externo falha
  → nada de lacre", "SHA-256 de artefato divergente recusa", "variável de ambiente só no avaliador"); nada em
  `data/` entra no git; `ruff` limpo.

### [ ] T-8.10 — 🛑 Go/no-go e "ok" do Programador

- Listar ao Programador, antes de ler 2025: o manifesto (modelos, limiares, orçamentos), o que foi
  verificado e o que não foi, os `[ASSUMPTION]` (orçamentos 5/10/14%, 1.000 reamostras, regra de
  "melhor"), os limites conhecidos (3.436 eventos em 2025, IC mais largo; versões de pandas/numpy
  diferentes entre treino e execução da `soneca` e da `lora`; 20 linhas de microdados no pickle da
  `lora`). Suíte inteira verde, `ruff` limpo, árvore limpa, tudo commitado e enviado.
- **Pronto quando:** o Programador responde "ok" por escrito. Sem o "ok", nada abre a porta.

### [ ] T-8.11 — 🛑 Execução única em 2025 (R2, D-97)

- `python -m dengue_sinan.comparar` (execução real). Roda **uma vez**; o resultado é reportado como
  saiu (resultado pior ou empate é resultado). Agregados em `reports/comparacao/`; relatório de
  verificação `reports/verificacao/T-8.11.json` (D-64: commit, hashes, checks, `passou`).
- **Pronto quando:** o lacre existe, os agregados e as figuras existem, o JSON de verificação tem
  `"passou": true`, `git status` não lista nenhum parquet de previsões e a segunda execução falha.

### [ ] T-8.12 — Relatório e README

- Nova seção de resultados da comparação no relatório (e no Word), com as figuras e a tabela;
  limitações (3.436 eventos; versões diferentes; "melhor" por modelo congelado; R7 da `lora`; `ricardo`
  fora; B2 parcial); Apêndice A com D-97 e D-98; README com o resumo e as figuras principais;
  itens do TRIPOD+AI afetados; números só de `reports/comparacao/`.
- **Pronto quando:** nenhum número digitado de memória (conferência da Sakura contra `reports/`), SC-09
  registrado com o resultado real (inclusive "sem diferença detectável"), checklist da seção
  Comparação passando.

### [ ] T-8.13 — Fecho do marco

- Auditoria do Marco 8 (Sasuke): R1 a R10, R1/R2 1.5, manifesto contra o lacre, nenhuma leitura de
  2025 fora da porta (`git log` e testes), checklist, consistência de IDs. Limpeza: remover os
  worktrees (`git worktree remove`), os ambientes isolados e as cópias temporárias, com confirmação do
  Programador.
- **Pronto quando:** Sasuke CUMPRIDO, tudo commitado e o Registro de execução completo.

### Fora do escopo (decisão do Programador, quando quiser)

- **`m1_ricardo`:** a branch não tem artefato. Se for treinada (horas de GPU no Colab), entra só como
  **exploratória**, depois do lacre, e o relatório declara isso (D-97 c).
- **MLP e XGBoost da `lora`** (PR-AUC de validação um pouco maior que o elastic net congelado): sem
  artefato commitado; o Programador manteve o modelo congelado.
- **Reavaliar 2024** com os modelos das branches: não recomendado; invalidaria o R2.

### Ordem e dependências

```
T-8.0 → T-8.1 → T-8.2 → T-8.3 → T-8.4 ┐
                                T-8.5 ┤
                      T-8.6 (🛑 B0/B1) ┤→ T-8.9 (ensaio) → T-8.10 (🛑) → T-8.11 (🛑) → T-8.12 → T-8.13
                      T-8.7 [P] ──────┤
                      T-8.8 [P] ──────┘
```

T-8.7 e T-8.8 não leem dados e podem rodar em paralelo com T-8.6. A T-8.9 só começa quando as
quatro anteriores estão `[x]`.
