# Matriz de autonomia (F2.0-C.3)

Base: auditoria independente da Peach (matriz de 41 linhas), ajustada ao novo requisito de **autonomia por missão**. Uma **missão** é um escopo delimitado que o usuário autoriza uma vez (ver `arquitetura_l0.md`). Dentro dela, o sistema não pede autorização por comando, teste, correção ou delegação.

Classes de garantia: **T** testado, **D** documentação, **H** hipótese (a testar), **L** limitação conhecida. O controle técnico é o que **impõe** a linha; sem ele, a linha é só instrução (H).

## 0. Duas leituras diferentes da mesma matriz
1. **Nível desejado (alvo da arquitetura futura):** colunas "Nível", "Controle técnico" e "Classe". É o que o L0 e os controles devem permitir **depois** de implementados e auditados.
2. **Nível comprovado no ambiente atual:** coluna "Hoje (comprovado)". Hoje só existem a política F1 (`protegidos.json`, manifestos) e mecanismos provados no laboratório. **Nenhum controle da F2 está implementado.**

**Enquanto R1 permanecer aberto:** Bash e `pytest` não são operacionalmente liberados (linhas 7, 8, 9, 15, 17, 54); a proposta de isolamento não é proteção comprovada; agentes não alteram controles (linhas 29, 53); o L0 não autoriza a si próprio (linha 51); uma missão não autoriza etapa futura (linhas 48, 52).

**Classes T das linhas de `deny`:** só o `deny` de `Read` foi testado (E06). `Write`, `Edit` e Bash (exceto o `cat` negado por `deny` de `Read`) estão como D/H até o X13 da F2.0-D. Os portões de cada etapa estão em `portoes_f2.md`, que é a fonte normativa em caso de conflito.

**Objetivo:** reduzir a intervenção humana **sem** enfraquecer as fronteiras de segurança. A autonomia só avança quando a prova do controle correspondente (CP-n) for aprovada.

**Sobre 41 → 50 → 54 linhas.** A auditoria anterior da Peach trouxe uma matriz de 41 linhas; o texto original dela **não está nos documentos de `f2/`**, então um mapeamento linha a linha não pôde ser feito e fica pendente (`questoes_abertas.md` Q21). A matriz da F2.0-C (50 linhas) foi reorganizada por área e expandida com desdobramentos (por exemplo, ciclos, ciclo de vida da missão, Bash por perfil). A F2.0-C.1 acrescentou as linhas 51 a 54 (autoautorização do L0, autorização de etapa futura, bootstrap, código sem confinamento). Nenhuma linha foi apagada.

## Níveis
- **Nível 1, operacional.** Executa automático o que a missão autoriza: edição de código, testes, correções, auditorias.
- **Nível 2, técnico delimitado.** Decisão técnica **reversível** dentro do escopo, documentada: decisões registradas, propostas (DP), commits locais em branch de trabalho, repetição de ciclos até o limite.
- **Nível 3, aprovação humana.** Decisões científicas, mudança de escopo, dados protegidos, privilégios administrativos, instalação de dependências, operações irreversíveis, publicação, início de novas etapas.
- **N3★, nunca concedível por missão.** Parte do nível 3 que nenhuma missão pode delegar (por exemplo, `sudo`, alterar os próprios controles, dados protegidos). Só o usuário, fora da missão. Os controles só são escritos pelo **bootstrap** (D9), com autorização específica e revisão independente.

Quando uma ação ultrapassa a missão, o sistema **não tenta contornar**: o L0 grava uma pendência objetiva (`PEND-nnn`, formato em `arquitetura_l0.md`) e segue com tarefas independentes.

## 1. Código e testes

| # | Ação | Nível | Controle técnico | Classe | Se ultrapassar | Hoje (comprovado) |
|---|---|---|---|---|---|---|
| 1 | Editar arquivo de código listado na ficha | 1 | Hook: Write/Edit só em caminhos da ficha; `deny` estático nos demais | indício de `allow` em `saida/` (há arquivos em `saida/`; não reconferi o log); negação de `Write`/`Edit` fora da ficha **não testada** (D/H) | PEND | **Efetivo hoje:** sem controle F2; vale só por instrução. Na prática, sua autorização por ação  |
| 2 | Criar arquivo novo em pasta que a ficha autoriza (`src`, `tests`, `docs`) | 1 | Hook + política (`criar`) | H | PEND | **Efetivo hoje:** sem controle F2; vale só por instrução. Na prática, sua autorização por ação |
| 3 | Editar arquivo fora da ficha | 3 | Hook nega; `dontAsk` | `dontAsk` nega escrita fora do permitido em subagente (T); hook nega `Write`/`Edit`: **não testado** (D/H) | PEND | **Efetivo hoje:** sem controle F2; vale só por instrução. Na prática, sua autorização por ação  |
| 4 | Refatoração local dentro da ficha | 2 | Hook (ficha); registro de decisão | H | PEND se mudar API pública | **Efetivo hoje:** sem controle F2; vale só por instrução. Na prática, sua autorização por ação |
| 5 | Escolher nome de função, variável, estrutura interna | 2 | Nenhum bloqueio; registro no relatório se afetar interface | — | — | **Efetivo hoje:** sem controle F2; vale só por instrução. Na prática, sua autorização por ação |
| 6 | Criar teste novo | 1 | Hook (ficha); Peach revisa o diff **antes** de qualquer execução (R1) | H | PEND | **Efetivo hoje:** sem controle F2; vale só por instrução. Na prática, sua autorização por ação |
| 7 | Rodar `pytest` nos testes da ficha | 1 | Perfil de Bash do papel; execução no isolamento; o L0 roda o gate de forma independente | T (hook), H (isolamento) | PEND | **Nível 3 enquanto R1 estiver aberto** (só ESH) |
| 8 | Rodar `ruff` | 1 | Perfil de Bash; isolamento | T (hook) | — | **Nível 3 enquanto R1 estiver aberto** (só ESH) |
| 9 | Rodar `manifesto.py verificar` (mecanismo autorizado da F1; **não** depende de DX-2) | 1 | Perfil de Bash do L0 ou ESH | T (hook) | — | **Nível 3 enquanto R1 estiver aberto** (só ESH) |
| 10 | Corrigir falha de teste dentro do escopo (ciclos 1 a 3) | 1 | Contador do L0 | H | — | **Efetivo hoje:** sem controle F2; vale só por instrução. Na prática, sua autorização por ação |
| 11 | Repetir ciclo até o limite da missão | 2 | Contador do L0 em arquivo de estado | H | PEND no limite | **Efetivo hoje:** sem controle F2; vale só por instrução. Na prática, sua autorização por ação |
| 12 | Passar do limite de ciclos | 3 | L0 recusa o ciclo seguinte | H | PEND | **Efetivo hoje:** sem controle F2; vale só por instrução. Na prática, sua autorização por ação |
| 13 | Apagar arquivo criado na própria tarefa | 2 | Hook: só caminhos criados na tarefa (lista do L0) | H | PEND | **Efetivo hoje:** sem controle F2; vale só por instrução. Na prática, sua autorização por ação |
| 14 | Apagar, mover ou renomear arquivo preexistente | 3 | Hook e `deny`; nenhum agente apaga | D/H (nenhum `deny` de apagar/mover foi testado) | PEND | **Efetivo hoje:** sem controle F2; vale só por instrução. Na prática, sua autorização por ação  |

## 2. Execução de comandos

| # | Ação | Nível | Controle técnico | Classe | Se ultrapassar | Hoje (comprovado) |
|---|---|---|---|---|---|---|
| 15 | Bash em perfil do papel (padrões, sem metacaracteres) | 1 | Hook valida o comando original; isolamento em todo Bash | T (hook), H (padrões, isolamento) | negado + contador | **Nível 3 enquanto R1 estiver aberto** (só ESH) |
| 16 | Bash fora do perfil | 3 | Hook nega; conta como negação | T | PEND após N negações | **Efetivo hoje:** sem controle F2; vale só por instrução. Na prática, sua autorização por ação |
| 17 | Busca de arquivos e conteúdo (`find`, `grep`) | 1 | Perfil de Bash; `Glob` e `Grep` ausentes por padrão (D, T) | D/T | — | **Nível 3 enquanto R1 estiver aberto** (só ESH) |
| 18 | Instalar pacote, alterar dependência, `uv sync`, `pip` | 3 | Hook nega; `deny` em `pyproject.toml` e `uv.lock`; sem rede no isolamento | D/H | PEND | **Efetivo hoje:** sem controle F2; vale só por instrução. Na prática, sua autorização por ação  |
| 19 | Alterar `.python-version` | N3★ | `deny` | D/H (`deny` de edição **não testado**; só `Read` foi) | PEND | N3★: proibido por instrução e política F1; sem enforcement F2 implementado  |
| 20 | Acesso à rede (web, git remoto) | 3 | Isolamento sem rede; `tools` sem `WebSearch`; hook nega | H | PEND | **Efetivo hoje:** sem controle F2; vale só por instrução. Na prática, sua autorização por ação |
| 21 | `sudo` ou qualquer privilégio administrativo | N3★ | Fora de qualquer perfil | H | PEND | N3★: proibido por instrução e política F1; sem enforcement F2 implementado  |
| 22 | Instalar ou configurar sandbox, AppArmor, pacotes do sistema | N3★ | Ação do usuário | L | PEND | N3★: proibido por instrução e política F1; sem enforcement F2 implementado |

## 3. Dados e ciência

| # | Ação | Nível | Controle técnico | Classe | Se ultrapassar | Hoje (comprovado) |
|---|---|---|---|---|---|---|
| 23 | Ler dados de 2024, microdados, SOMENTE_HASH, NUNCA_ACESSAR | N3★ | `deny` de `Read` (T para `cat`) e do isolamento; hook; manifesto | T/H, L (`python -c` sem isolamento) | PEND | N3★: proibido por instrução e política F1; sem enforcement F2 implementado |
| 24 | Mover arquivos de 2024 | N3★ | Hook e `deny`; operação separada com lista exata | D/H | PEND | N3★: proibido por instrução e política F1; sem enforcement F2 implementado  |
| 25 | Treinar modelo, rodar experimento científico ou análise de dados | 3 | Hook nega; ficha não autoriza | H | PEND | **Efetivo hoje:** sem controle F2; vale só por instrução. Na prática, sua autorização por ação |
| 26 | Mudar métrica, critério científico ou desenho do estudo | 3 | `DECISOES.md` é SOMENTE_HUMANO; processo DP | D/H (`deny` de edição **não testado**) | PEND | **Efetivo hoje:** sem controle F2; vale só por instrução. Na prática, sua autorização por ação  |
| 27 | Alterar resultados ou artefatos preservados | N3★ | Política PRESERVADO | T (política F1) | PEND | N3★: proibido por instrução e política F1; sem enforcement F2 implementado |

## 4. Controles, política e identidade

| # | Ação | Nível | Controle técnico | Classe | Se ultrapassar | Hoje (comprovado) |
|---|---|---|---|---|---|---|
| 28 | Alterar `protegidos.json`, `politica_lib.py`, scripts de manifesto | N3★ | `deny`; hash conferido pelo L0 e pelo hook | D/H (`deny` de edição **não testado**) | PEND | N3★: proibido por instrução e política F1; sem enforcement F2 implementado  |
| 29 | Alterar hook, `.claude/settings*.json`, `agentes.json` (definições), L0, isolar.py, gerador de configuração | N3★ (**nunca por missão**; só pelo bootstrap autorizado em D9, ver `arquitetura_l0.md` §2A) | `deny`; hash conferido a cada chamada (R18); isolamento | H | PEND | N3★: proibido por instrução e política F1; sem enforcement F2 implementado |
| 30 | Alterar regras permanentes ou `DECISOES.md` | 3 | `deny` | D/H (`deny` de edição **não testado**) | DP | **Efetivo hoje:** sem controle F2; vale só por instrução. Na prática, sua autorização por ação  |
| 31 | Gerar nova versão de manifesto | 2, se prevista no plano da missão; senão 3 | Perfil de Bash com `manifesto.py gerar` sem `--incluir-2024`; modo `x` (não sobrescreve) | T (F1), H (perfil) | PEND | **Efetivo hoje:** sem controle F2; vale só por instrução. Na prática, sua autorização por ação |
| 32 | Alterar manifestos existentes (v001, v002) | N3★ | `deny`; modo `x` | D/H (`deny` de edição **não testado**; modo `x` é T na F1) | PEND | N3★: proibido por instrução e política F1; sem enforcement F2 implementado  |
| 33 | Iniciar sessão sem `--agent`, com ferramentas extras, conectores ou `WebSearch` | N3★ | L0 recusa; `init` conferido | T (E11a mostra o risco), H (recusa do L0) | PEND | N3★: proibido por instrução e política F1; sem enforcement F2 implementado |

## 5. Coordenação da equipe

| # | Ação | Nível | Controle técnico | Classe | Se ultrapassar | Hoje (comprovado) |
|---|---|---|---|---|---|---|
| 34 | Delegar Mario, Luigi e Peach (sessão por papel iniciada pelo L0) | 1 | Fila da missão; lista fechada de papéis | H | PEND | **Efetivo hoje:** sem controle F2; vale só por instrução. Na prática, sua autorização por ação |
| 35 | Spawn de subagente dentro da sessão (se o modo B for escolhido) | 1 para os três papéis; 3 para os demais | `PreToolUse` de `Agent` com lista fechada; **nunca testado com negação** | T (payload), H (negação) | negado | Não comprovado: sem negação real de `Agent` |
| 36 | Subagentes embutidos (`Explore`, `general-purpose`, `Plan`, `web-fetch`) | N3★ | Lista fechada | H | negado | N3★: proibido por instrução e política F1; sem enforcement F2 implementado |
| 37 | Pedir auditoria independente da Peach | 1 | Etapa da máquina de estados do L0 | H | — | **Efetivo hoje:** sem controle F2; vale só por instrução. Na prática, sua autorização por ação |
| 38 | Auditoria da Peach como **condição** (não autorização): resultado estruturado válido, zero críticos, zero importantes sem tratamento | 2 | L0 valida o arquivo estruturado (`criterios_peach_f2.md` §3 e §4); texto livre é só informativo | H | PEND se houver crítico ou importante, ou se o resultado estiver ausente, inválido ou contraditório (INCONCLUSIVO) | **Efetivo hoje:** sem controle F2; vale só por instrução. Na prática, sua autorização por ação |
| 39 | Aceitar risco residual | 3 | DP + decisão humana | D | PEND | **Efetivo hoje:** sem controle F2; vale só por instrução. Na prática, sua autorização por ação |
| 40 | Registrar decisão técnica reversível | 2 | Arquivo em `agentes/decisoes/propostas/` (criar) | H | — | **Efetivo hoje:** sem controle F2; vale só por instrução. Na prática, sua autorização por ação |
| 41 | Escrever relatório, evidência, histórico (só criar ou anexar) | 1 | Política F1 (criar/anexar) | T (F1) | — | **Efetivo hoje:** sem controle F2; vale só por instrução. Na prática, sua autorização por ação |

## 6. Ciclo de vida da missão

| # | Ação | Nível | Controle técnico | Classe | Se ultrapassar | Hoje (comprovado) |
|---|---|---|---|---|---|---|
| 42 | Controlar orçamento, turnos e tentativas | 1 | `--max-turns`, `--max-budget-usd` (D); contadores do L0 | D/H | PEND no teto | **Efetivo hoje:** sem controle F2; vale só por instrução. Na prática, sua autorização por ação |
| 43 | Pausar e retomar por rate limit | 1 | L0 lê `rate_limit_event` e o erro (T: eventos existem) | T (evento), H (retomada) | — | **Efetivo hoje:** sem controle F2; vale só por instrução. Na prática, sua autorização por ação |
| 44 | Recuperar passo interrompido | 1 | Estado em arquivo, passos idempotentes | H | — | **Efetivo hoje:** sem controle F2; vale só por instrução. Na prática, sua autorização por ação |
| 45 | Commit local em branch de trabalho | 2 | Perfil de Bash (`git commit`) em branch não principal; **o repositório atual não tem `.git`**: exige inicialização, que é nível 3 | H | PEND | Nível 3: sem `.git` no repositório |
| 46 | Push, publicação, merge | 3 | Hook nega; sem rede e sem credencial no isolamento | H | PEND | Nível 3: sem `.git` no repositório |
| 47 | Preparar plano da subetapa seguinte | 1 | Escrita na área do Yoshi | H | — | **Efetivo hoje:** sem controle F2; vale só por instrução. Na prática, sua autorização por ação |
| 48 | **Iniciar** a subetapa seguinte (nenhuma missão, auditoria ou aprovação do L0 a inicia; só você) | 3 | L0 só aceita missão nova assinada pelo usuário | H | PEND | **Efetivo hoje:** sem controle F2; vale só por instrução. Na prática, sua autorização por ação |
| 49 | Ampliar escopo, limites ou lista de arquivos da missão | 3 | Missão imutável (hash) | H | PEND | **Efetivo hoje:** sem controle F2; vale só por instrução. Na prática, sua autorização por ação |
| 50 | Relatório final consolidado | 1 | Etapa final do L0 | H | — | **Efetivo hoje:** sem controle F2; vale só por instrução. Na prática, sua autorização por ação |
| 51 | O L0 autorizar a si próprio, ou ampliar a missão | N3★ | Missão imutável (hash) e confirmação humana em TTY (D4) | H | PEND | Nenhum L0 existe; vale só por instrução |
| 52 | Missão autorizar etapa futura | N3★ | `nao_iniciar_proxima: true`; L0 só aceita missão nova confirmada por você | H | PEND | Nenhum L0 existe; vale só por instrução |
| 53 | Agente escrever os controles do L0 numa missão comum | N3★ | `deny` e bootstrap só por D9 | H | PEND | N3★: proibido por instrução; `deny` de `Write`/`Edit` **não testado** (H) |
| 54 | Agente executar código que ele escreveu sem confinamento comprovado | 3 | Perfil de Bash do papel; isolamento (CP-5) | H | PEND | **Nível 3 enquanto R1 estiver aberto** (só ESH, `portoes_f2.md` P4) |

## Observações
1. A matriz só vale quando os controles existirem. Hoje (F1) só há política e manifesto; o enforcement é da F2.
2. A linha 7 depende de R1 resolvido. Sem isolamento, `pytest` é nível 3 (só ESH, `portoes_f2.md` P4). *(Nota C.3: a leitura anterior "ou nível 1 com risco aceito (D1)" foi retirada: D1(c) não é selecionável antes do CP-5.)*
3. Interrupções que a matriz remove: autorização por execução de laboratório, por correção dentro da ficha, por delegação, por teste, por ciclo até o limite, por pausa e retomada. Interrupções que ficam: dados protegidos, dependências, escopo, ciências, privilégios, publicação, nova etapa.
