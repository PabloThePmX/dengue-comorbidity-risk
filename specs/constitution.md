# Constituição do projeto

> Princípios que valem para todo o projeto: todos os arquivos de `specs/` e o código em `src/`.
> O objetivo que esses princípios protegem está em [goal.md](goal.md).
> Em caso de conflito, esta constituição vale sobre os outros arquivos. Os IDs (FR, NFR, D, §3.x)
> são os do spec. Versão e datas no rodapé (convenção do Spec Kit, D-55).
> Idioma: pt-BR (entregável acadêmico).

---

## 1. Princípios fundamentais

### P1 — Spec antes do código; quem decide é o Programador
- Nada é implementado sem estar no spec ou no plano.
- Escolhas de alvo, população, split, métrica, limiar, modelo, features e escopo são do
  Programador. Agentes e colaboradores apresentam opções com prós e contras e esperam a decisão.
- Toda decisão significativa entra no Registro de decisões (§3.16) com contexto, opções e
  consequências.

### P2 — O teste é congelado e usado uma vez
- Os dados de 2024 só são lidos na avaliação final, uma única vez (FR-09).
- Nada é escolhido pelo teste: nem peso, nem limiar, nem modelo (D-36). Resultado pior no teste é
  resultado, não motivo para ajustar.

### P3 — Sem vazamento
- Só entra como feature o que existe no momento da predição (§3.6) e não é proxy do rótulo (§3.8).
- Todo ajuste (encoder, scaler, calibrador, parada antecipada) usa só dados de treino da dobra.

### P4 — Baselines primeiro, comparação justa
- Todo modelo é julgado contra B0, B1 e B2 (§3.10).
- Os candidatos usam as mesmas linhas, as mesmas dobras e a mesma semente (D-53), com orçamento de
  busca comparável (D-42).

### P5 — Prevalência natural e probabilidades calibradas
- O produto é um risco. Os modelos treinam com a prevalência real; o recall se controla pelo
  limiar, e não por correção de desbalanceamento (D-38).

### P6 — Associação não é causa
- OR, SHAP e importâncias descrevem o modelo, não o mundo. O relatório não faz afirmação causal.
- O ranking de comorbidades vem só do modelo explicativo E1 (FR-19).

### P7 — Reprodutível a partir de um checkout limpo
- Ambiente travado (`uv.lock`), semente única, configuração em arquivo, dados com hash e
  experimentos no MLflow (§3.14, NFR-02).

### P8 — Privacidade e ética
- Nenhum microdado vai para o git, para o app ou para relatórios. Só agregados, com células de
  menos de 10 casos suprimidas (NFR-03).
- Dados públicos e desidentificados, tratados como tal (NFR-04).

### P9 — Código testável e verificado
- Código em módulos de `src/dengue_sinan/`, com teste em `tests/`. Notebooks só chamam funções
  (NFR-05).
- Toda mudança de comportamento vem com teste. Uma tarefa só está pronta depois de rodar os testes
  e o lint e conferir o critério de pronto.

### P10 — Honestidade nos resultados
- Números vêm da execução, nunca de memória ou estimativa. Afirmações sobre os dados passam por
  `[VERIFY]` até serem conferidas.
- Erros e números estranhos são registrados antes de corrigidos (tasks/00-como-usar.md, §10). Resultado negativo
  (por exemplo, M1 não supera B1) é resultado válido.

---

## 2. Regras que nunca podem ser quebradas

Aplicações diretas dos princípios. O [tasks/00-como-usar.md](tasks/00-como-usar.md) traz um resumo de uma linha de cada.

| # | Regra | Princípio | Origem |
|---|---|---|---|
| R1 | **Os dados de 2024 (teste) não são lidos antes da T-5.1.** Nenhuma função de treino, tuning, calibração, limiar, seleção ou gráfico usa 2024. | P2 | §3.8, FR-09 |
| R2 | O teste é avaliado **uma única vez**. A T-5.1 grava um "lacre"; uma segunda execução deve falhar. | P2 | FR-09, D-36 |
| R3 | **Sem correção de desbalanceamento**: nada de `class_weight`, `scale_pos_weight`, `is_unbalance`, `auto_class_weights`, `pos_weight`, SMOTE ou undersampling. Única exceção: subamostra de negativos do Random Forest por falta de memória, com correção de probabilidade (T-4.4). | P5 | D-38 |
| R4 | Features permitidas são **só** as da lista fechada do data-model (§D). Nada de UF, região, município, unidade, ano, semana, raça/cor, escolaridade, `ALRM_*`, `GRAV_*`, exames, `HOSPITALIZ`, `CRITERIO` etc. | P3 | §3.8, D-21, D-48 |
| R5 | Todo pré-processamento é ajustado **dentro** da dobra de treino, via `sklearn.Pipeline`. Nunca ajuste scaler, encoder ou calibrador no conjunto todo. | P3 | §3.8, §3.9 |
| R6 | Early stopping usa a **validação interna** (10% das regiões de treino), nunca a região deixada de fora. | P3 | FR-22, §3.11 |
| R7 | Nenhum microdado (linha a linha) vai para o git, para o app ou para relatórios. Só agregados; células com < 10 casos são suprimidas. | P8 | NFR-03, §3.12 |
| R8 | Semente única do config em tudo que for aleatório. | P7 | §3.14, NFR-02 |
| R9 | O E1 é logística **sem penalização** (para ter IC). Penalização só no candidato "elastic net" do M1. | P6 | §3.11 |
| R10 | Ranking de comorbidades vem **só** dos OR do E1, nunca de SHAP ou importância de árvore. | P6 | FR-19, D-41 |

---

## 3. Decisões reservadas ao Programador

Quem implementa **para e pergunta** antes de:

- adicionar qualquer dependência ao `pyproject.toml`;
- mudar qualquer item marcado `[OPEN QUESTION]`, `[ASSUMPTION]` ou `[DECISION NEEDED]` no spec ou
  no plano;
- definir o espaço de busca de hiperparâmetros (Q-08);
- decidir o que fazer se o TabFM não couber (licença, limites);
- escolher o modelo da demo se o melhor M1 não couber nela (Q-14);
- mudar alvo, população, split, métrica, limiar, faixas etárias ou lista de features;
- publicar qualquer coisa (app, repositório, relatório);
- aplicar uma correção de erro que mude uma decisão do spec (tasks/00-como-usar.md, regra 4b).

---

## 4. Governança

- **Hierarquia:** constitution > spec > plan, research, data-model, contracts > tasks. Se dois
  arquivos discordarem, vale o de cima, e a divergência é avisada ao Programador.
- **Constitution Check:** o [plan.md](plan.md) tem uma tabela que confere cada princípio. Ela é
  refeita antes de implementar e de novo depois do Marco 4; um princípio que não se cumpre vai para
  o Registro de complexidade do plano, com justificativa.
- **Emendas:** só o Programador altera esta constituição. Cada emenda tem uma entrada no Registro de
  decisões ([research.md](research.md), §3.16) e aumenta a versão no rodapé (mudança de princípio:
  versão maior; texto ou regra nova: versão menor).
- **IDs estáveis:** P, R, FR, NFR, D e §3.x nunca são renumerados. Item removido fica ~~riscado~~.

**Versão**: 1.1 | **Ratificada**: 2026-11-04 | **Última emenda**: 2026-11-04 (D-55)
