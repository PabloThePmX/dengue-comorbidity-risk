# Equipe de agentes — Dengue Comorbidity Risk

> Criado na Fase F1; política de proteção revisada (v2) em 2026-11-18 e corrigida no mesmo dia (permissões por agente, 2024 em qualquer pasta). Os agentes em si (`.claude/`), hooks e `settings.json` ainda **não existem**: entram nas fases F2 a F4.
> Decisões que fundamentam esta estrutura: [`decisoes/DECISOES.md`](decisoes/DECISOES.md).
> Idioma: pt-BR. Quem decide é o Programador (você).

## Papéis

| Agente | Papel | Modelo previsto (DA-004) |
|---|---|---|
| **Yoshi** | Coordena: prepara fichas, controla o roadmap, interpreta o parecer, pede decisão humana | Sonnet |
| **Mario** | Implementa só o que a ficha autoriza | Sonnet |
| **Luigi** | Executa testes e verificações; não corrige código | Sonnet |
| **Peach** | Audita de forma independente; devolve APROVADO, REPROVADO ou INCONCLUSIVO | Opus, se disponível |

Se um modelo não estiver disponível, **ninguém o substitui em silêncio**: o Yoshi para e informa a limitação. O modelo efetivamente usado vai em cada relatório.

## Ciclo

1. Você autoriza uma etapa em `estado/autorizacao.json` (só você grava).
2. Yoshi prepara a ficha em `tarefas/<etapa>/`.
3. Mario implementa → `relatorios/<etapa>/ciclo-NN/mario.md`.
4. Luigi executa → `luigi.md` e `evidencias/`.
5. Peach audita → `peach.md`, com exatamente um estado.
6. Yoshi interpreta. **APROVADO** = *tecnicamente aprovada*; aguarda sua autorização para a próxima etapa. **REPROVADO** = lista objetiva ao Mario (até o limite de ciclos). **INCONCLUSIVO** = lista de evidências ausentes; não avança.

Aprovação técnica **não** é validação clínica nem validação externa.

## Estados (`estado/estado.json`)

`SEM_ETAPA_AUTORIZADA`, `PREPARANDO`, `EM_IMPLEMENTACAO`, `EM_EXECUCAO`, `EM_AUDITORIA`, `EM_CORRECAO`, `TECNICAMENTE_APROVADA`, `AGUARDANDO_AUTORIZACAO`, `BLOQUEADA_INCONCLUSIVA`, `INTERROMPIDA_LIMITE`.

## Arquivos

| Caminho | Função | Quem grava |
|---|---|---|
| `estado/estado.json` | Estado central | Yoshi |
| `estado/limites.json` | Limite de ciclos de correção (padrão 3) | Você |
| `estado/autorizacao.json` | Etapa autorizada | **Só você** |
| `estado/protegidos.json` | Política de proteção v2 (eixos de leitura e de escrita) | **Só você** |
| `roadmap/ROADMAP.md` | Roadmap principal e mapa para as T-x.y | Yoshi (com sua confirmação); Mario só se a ficha listar |
| `decisoes/DECISOES.md` | Histórico de decisões, só acréscimo (`DA-nnn`) | **Só você**. O Yoshi propõe em `decisoes/propostas/DP-nnn.md` |
| `criterios/` | Regras permanentes e critérios de aceitação | **Só você** |
| `tarefas/_modelo.md` | Modelo da ficha de tarefa | **Só você** |
| `relatorios/` | Um relatório por agente e por ciclo (só criação; revisões em `<agente>-revN.md`) | Cada agente, só o seu |
| `evidencias/` | Logs e hashes. **Nunca** microdados (só criação) | Luigi e Peach, só em `…/<agente>/` |
| `historico/execucoes.jsonl` | Registro de execução, só acréscimo | Yoshi |
| `scripts/politica_lib.py` | Lê `protegidos.json` e decide leitura e escrita (usada pelo manifesto e, na F2, pelo hook) | Você |
| `scripts/manifesto.py` | Gera, confere e compara manifestos versionados. **Você** o executa | — |
| `estado/manifesto_hashes.json` | Manifesto **v001** (legado; não é alterado nem renomeado) | — |
| `estado/manifestos/manifesto-vNNN.json` | Manifestos v002 em diante, em cadeia (cada um guarda o hash do anterior) | Você, pelo script |
| `estado/manifestos/local-2024-vNNN.json` | Hashes de 2024, locais e fora do Git (D4) | Você, pelo script |

Arquivos lidos por hooks ficam em JSON (só biblioteca padrão, DA-015). O restante é Markdown.

## Política de proteção (esquema 2)

Cada caminho tem **dois eixos**. Avaliam-se todos os itens que casam e vale o mais restritivo em cada eixo; a ordem dos itens não importa. Uma concessão a um agente nunca anula uma classe mais restritiva. Sem item que case, a leitura é livre e a escrita só ocorre pela ficha (negação por padrão). Política ausente ou inválida: nega tudo.

| Eixo | Valores (do menos ao mais restritivo) |
|---|---|
| Leitura | `livre` < `so_hash` < `nunca` |
| Escrita | `ficha` < `anexar` < `criar` < `humano` |

| Classe (rótulo) | Leitura | Escrita | Exemplos |
|---|---|---|---|
| `NUNCA_ACESSAR` | nunca | humano | `data/**`, `*.parquet`, `*.dbc`, `*.dbf`, `artefatos/oof/**`, tudo de 2024 |
| `SOMENTE_HASH` | só hash | humano | 9 arquivos `teste_*`, 12 `oof_*.npz`, `LACRE_TESTE_2024.json`, `m1_congelado.joblib` |
| `SOMENTE_HUMANO` | livre | humano | `specs/`, `CLAUDE.md`, `.claude/`, `.gitignore`, `.python-version`, `autorizacao.json`, `protegidos.json`, `limites.json`, `scripts/`, `DECISOES.md`, `criterios/`, `tarefas/_modelo.md`, `tests/agentes/` |
| `PRESERVADO` | livre | humano | resto de `reports/modelo_risco_dengue/`, `reports/etapa1/`, `m1-perfil-2.0.0`, `notebooks/`, `profiling/` |
| `ESCRITA_CONTROLADA` | livre | controlada | `estado.json`, `roadmap/`, `tarefas/` (Yoshi, por concessão); `src/`, `tests/`, `docs/` (Mario, pela ficha); `config/`, `pyproject.toml`, `uv.lock`, `reports/etapa2/`, `reports/etapa3/` (Mario, só caminho exato na ficha; hash monitorado) |
| `REGISTRO_CRIAR` | livre | criar | `relatorios/`, `evidencias/`, `decisoes/propostas/` |
| `REGISTRO_ANEXAR` | livre | anexar | `historico/execucoes.jsonl` |

Nenhum agente exclui, move ou renomeia arquivo. Pedidos assim vão ao usuário.

**Escrita por agente e por ação (correção C2).** Os modos são distintos, sem hierarquia entre si (só `humano` bloqueia tudo). A ação permitida é a interseção das ações de **todos** os itens que casam, e exige concessão explícita ao agente:

- `escritores` (concessão direta ao agente) ou `via_ficha` (o agente pode usar a ficha da tarefa; hoje só o **Mario**).
- Luigi, Peach e Yoshi **não** ganham acesso por constar na ficha.
- O Mario não usa a ficha para `agentes/estado/**`, decisões, histórico, fichas, roadmap, scripts nem testes de agentes.
- Caminho sem nenhum item (por exemplo `README.md`): escrita negada.
- O hook da F2 deve chamar `pode_escrever_seguro` e `pode_ler_seguro`, que normalizam o caminho e negam em qualquer falha da política. `pode_escrever` e `pode_ler` rejeitam caminho não normalizado (`..`, `//`, barra inicial).

**2024 em qualquer pasta (correção C3).** Padrões por nome e extensão, sem diferenciar caixa: `*2024*.{csv,zip,gz,feather,pkl,parquet,dbc,dbf,xlsx,…}`, `*2024` sem extensão, pastas com `2024` no nome, `*dengbr*24*` e `.json` de resultados, métricas, avaliações e predições de 2024. **Não existe** regra genérica `*2024*` nem para `.json`, para não capturar o lacre. O lacre tem item próprio `SOMENTE_HASH` em qualquer pasta. Nas áreas do Mario (`src/`, `tests/`, `docs/`, `config/`, `reports/etapa2|3/`), nome com 2024 só o usuário grava. Limites: `.json` de 2024 fora dessas áreas com nome fora das palavras conhecidas não é pego, e `.py` com 2024 no nome fora das áreas do Mario não é bloqueado.

**`SOMENTE_HASH` significa:** o agente não lê o conteúdo e não calcula hash por conta própria. A integridade se confere só com `manifesto.py verificar`. Processos de `pytest` podem calcular hash internamente (DA-008, DA-009).

**2024:** `grupo: "2024"` é permanente e sem diferenciar maiúsculas de minúsculas. Os bloqueios continuam valendo depois de qualquer movimentação de arquivos (DA-010). O `LACRE_TESTE_2024.json` é um registro de hash e **não** é conjunto de dados; por isso é `SOMENTE_HASH`.

## Manifesto versionado

- `gerar` cria sempre uma versão nova (v002, v003…) e nunca sobrescreve. `gerar --incluir-2024` também grava `local-2024-vNNN.json`.
- `verificar [--versao N]` confere a cadeia e os hashes. Mostra `ALTERADO`, `AUSENTE`, `CLASSE_ALTERADA`, `NAO_VERIFICADO` e `NOVO`. Só `ALTERADO`, `AUSENTE` e cadeia quebrada reprovam.
- `comparar A B` lista caminhos adicionados, removidos e alterados (nunca conteúdo).
- `verificar` reprova também **arquivo novo em área `SOMENTE_HUMANO`** não registrado na versão de referência. A saída traz `NOVO_EM_AREA_SOMENTE_HUMANO: <caminho> (…não registrado em vNNN…)`. Inclui pastas que o script ignora no resto (`venv`, `.git`, `node_modules`, `__pycache__`) e links simbólicos novos dentro dessas áreas. Ignora só `.pyc` em `__pycache__` e caches de ferramentas (inertes). Não vale para áreas fora do manifesto (`DECISOES.md`, `manifestos/**`).
- Comparar contra a v001 mostra `protegidos.json` como `ALTERADO` (a política mudou de propósito, DA-016) e vários arquivos só-humanos como novos (a v001 não os conhecia). Use a v002 como referência depois da F1.5.

## Limitações até a F2

Hoje **nada aplica** a política: `politica_lib.py` só é usada pelo manifesto e pelos testes. Sem hook, nada impede um agente de ler `SOMENTE_HASH`/`NUNCA_ACESSAR` por `Grep`, `cat` ou script, nem de gravar fora da política. A lista fechada de comandos, os hooks e as regras de `settings.json` entram na F2. Scripts e processos de `pytest` também conseguem ler arquivos que as regras de ferramenta bloqueiam.

## Regras que valem sempre

Ver [`criterios/regras_permanentes.md`](criterios/regras_permanentes.md). Em resumo: 2024 protegido, M1 só com `idade_anos`, `sexo` e `gestante`, município só como agrupamento, artefatos históricos preservados, sem commit nem push automáticos, sem avançar etapa sem sua autorização.
