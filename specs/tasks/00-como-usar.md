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
| [05-teste-final.md](05-teste-final.md) | 5 — Avaliação final no teste, uma vez | T-5.1 a T-5.4 | 03 e 04 todos `[x]` e commitados. Extras que são modelos (FR-14) entram antes. |
| [06-us3-demo.md](06-us3-demo.md) | 6 — Demo (US3) | T-6.1 e T-6.4 | 05 todo `[x]`. O esqueleto pode começar no Marco 2 com modelos fictícios. |
| [07-relatorio.md](07-relatorio.md) | 7 — Relatório | T-7.1 e T-7.3 | Escrito ao longo do projeto; fecha depois de 05 e 06. |

- O **marco atual** é o primeiro arquivo, em ordem numérica, que ainda tem tarefa `[ ]` ou `[~]`.
  Leia este arquivo e o do marco atual; os outros, só se a tarefa citar.
- Os Marcos 3 e 4 dependem só do 2 e podem andar em paralelo; a ordem recomendada é por
  prioridade (US1 antes de US2).
- Dentro de um arquivo, tarefas `[P]` podem rodar em paralelo (ex.: T-2.2, T-2.4, T-2.5; T-4.1).
  Tarefas que mexem no mesmo arquivo de código são sempre sequenciais.

## Formato das tarefas

`### [ ] T-N.x [P] [USn] — título`

- Estado: `[ ]` a fazer; `[~]` feita, aguardando o relatório do Colab
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

Para critérios que dependem de dados reais, GPU ou queda de sessão. Os dados ficam no Drive
(NFR-03), e **ninguém digita resultado à mão** (D-56).

1. Escreva a verificação **como código**: uma função em `src/` que calcula cada item do "Pronto
   quando" e chama `verify.write_report` (T-2.0), comparando com `config/esperado.yaml`. Nunca
   escreva números esperados no notebook.
2. Acrescente ao notebook da tarefa a célula que chama essa função.
3. Faça e verifique localmente tudo o que der: código, testes com dados sintéticos (inclusive da
   própria verificação), ruff.
4. Marque a tarefa `[~]`, anote no Registro de execução "pendente no Colab: rodar <notebook>,
   célula <nome>; gera `reports/verificacao/T-N.x.json`" e **pare**. Avise que o código precisa
   estar commitado e no GitHub antes de rodar ([quickstart › Google Colab](../quickstart.md#google-colab)).
5. Na sessão seguinte, leia o JSON:
   - arquivo ausente → peça ao Programador só para rodar o notebook e colocar o arquivo na pasta
     (não peça números);
   - `"commit"` diferente do commit que contém o código da tarefa → peça para rodar de novo;
   - `"passou": true` → marque `[x]` e copie o resumo dos `checks` para o Registro de execução;
   - `"passou": false` → registre os checks que falharam em [Erros inesperados](#erros-inesperados)
     e não marque `[x]`.
6. Nunca passe para o marco seguinte com uma tarefa `[~]` aberta.

**Exceção do Marco 4 (D-57):** T-4.3b a T-4.10 compartilham um único relatório,
`reports/verificacao/sessao-m1.json`. Marque cada uma `[~]` e siga para a próxima do mesmo marco;
pare só depois da T-4.10, pedindo a sessão do Colab. Ao ler o relatório, marque `[x]` cada tarefa
cujo bloco tem `"passou": true`.

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

- Parquets por ano no Drive: `MyDrive/dengue-comorbidity-risk/data/parquet/dengue_{ano}.parquet`
  (todas as colunas como **texto cru**), manifesto em `data/manifest.json`, gerados por
  `download.fetch_year` (FR-01, já pronto). O Colab gratuito tem ~12,7 GiB de RAM.
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

---

## Registro de problemas

Todo erro inesperado entra aqui **antes** de qualquer correção ([Erros inesperados](#erros-inesperados)).
Uma linha por problema; se houver várias tentativas, uma linha por tentativa.

| Data | Tarefa | O que aconteceu (mensagem de erro ou número estranho) | O que foi tentado | Resultado | Precisou perguntar? |
|---|---|---|---|---|---|
