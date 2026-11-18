# Arquitetura L0 revisada (F2.0-C.2)

Documento de **planejamento**. Nada aqui foi implementado, e nenhum arquivo de controle foi criado. Toda garantia marcada H precisa de teste (ver `roadmap_f2_revisado.md`, F2.0-D).

Classes: **T** testado, **D** documentação, **H** hipótese, **L** limitação.

## 1. Princípios
1. **O L0 é um programa externo, determinístico, fora do raciocínio dos agentes.** Não é um agente. Decide por regras e contadores.
2. **Autonomia por missão.** O usuário autoriza uma missão uma vez. Dentro dela, ninguém pede autorização por comando.
3. **Os logs do sistema são a evidência.** Relatos de agentes erraram (E02, E06a). O L0 baseia decisões no stream-json, nos logs dos hooks, nos códigos de saída dos gates e nos hashes.
4. **Falha fechada.** Qualquer dúvida de ambiente, identidade ou hash encerra a sessão e abre pendência.
5. **Um papel por sessão.** Cada `claude -p` roda com um `--agent` (Yoshi, Mario, Luigi ou Peach). A identidade fica na raiz da sessão (`agent_type` sem `agent_id`, T) e a Peach é independente de verdade.

## 2. Autorização de missão (revisada em F2.0-C.1, aguarda D4)
Um **hash impresso não prova que você leu o escopo.** O procedimento proposto exige revisão e confirmação:
1. **Arquivo de missão** (`missao-NNN.json`) em diretório **fora do repositório e fora de qualquer caminho gravável por agente** (D6). Com o mesmo usuário Unix, isso só é verdadeiro se os agentes rodarem confinados (CP-5); sem isso, o arquivo é alterável e o procedimento não é protegido (L).
2. **Resumo legível**, gerado pelo L0 a partir do arquivo, no terminal: objetivo; subetapa; tarefas e papéis; **arquivos e caminhos graváveis**; **ações permitidas** e **ações proibidas**; limites (ciclos, orçamento, turnos, duração, negações); nível máximo (2); `nao_iniciar_proxima: true`; **consequências e riscos conhecidos** (R1 aberto ou não, R18 a R21, o que o confinamento prova ou não prova).
3. **Confirmação humana explícita em terminal interativo (TTY):** o L0 exige digitar o identificador da missão e uma frase de confirmação. Sem TTY (script, pipe, agente), recusa. **H (não testado):** a hipótese de que um agente ou processo filho **não consegue forjar** essa confirmação (injetar bytes no TTY, abrir `/dev/tty`, `TIOCSTI`) não foi testada. O experimento X11 testa isso num pty criado pelo harness, **nunca** no seu terminal. Até lá, a confirmação em TTY é um controle H.
4. **Verificação antes da execução:** o L0 confere o hash do arquivo de missão contra o hash mostrado e confirmado; confere que o arquivo não mudou desde a confirmação; e recusa missão com `nivel_maximo` acima de 2.
5. **Registro:** hora, hash e resumo confirmados vão para o estado do L0 (fora do alcance dos agentes).
6. A **assinatura HMAC** é camada opcional (D4(b)). Ela detecta alteração por processo que **não** lê a chave. Contra processo do mesmo usuário Unix sem confinamento, **não é proteção suficiente** (L), porque esse processo lê a chave.
7. Mensagens dentro de uma sessão (inclusive pelo socket de mensagens, R19) nunca autorizam nível 3.
8. O Yoshi pode **preparar** o rascunho de uma missão futura; ele não a confirma nem a inicia.

### Conteúdo mínimo da missão
`id`; `subetapa`; `objetivo`; `tarefas` (id, papel, ficha, critérios de aceite objetivos, dependências); `limites` (ciclos por tarefa, turnos por sessão, custo por sessão e total, tempo total, negações por tarefa, tentativas por passo); `perfis_bash` por papel; `ferramentas` por papel; `nivel_maximo` (2); `nao_iniciar_proxima: true`. **Os valores numéricos não estão decididos** (D5); ciclos 3 e negações 5 são tetos provisórios propostos.

## 2A. Bootstrap dos controles (A1, aguarda D9)
**Problema:** `l0.py`, o hook, `isolar.py` e o gerador de configuração são N3★, mas alguém precisa escrevê-los. Uma missão comum **não** concede isso ao Mario. Os controles também não podem aprovar a própria implementação.

Procedimento proposto, **não implementado** e **não autorizado**:
1. **Quem pode implementar:** só o que você indicar em D9: (a) você mesmo, ou (b) o Mario em **sessão de bootstrap** separada de qualquer missão, para os arquivos listados.
2. **Autorização específica:** por subetapa e por arquivo, escrita por você, com a lista exata de arquivos e o objetivo. Fora da lista, `deny`. Não vale para a missão seguinte.
3. **Revisão independente:** a Peach audita o diff em sessão sem contexto do Mario, com resultado estruturado (`criterios_peach_f2.md` §3). **E** você revisa o diff antes da primeira ativação. A auditoria da Peach não substitui a sua revisão.
4. **Validação antes de confiar:** testes de CP-4 a CP-7 correspondentes, com canários e falhas induzidas, rodados fora do controle recém-escrito.
5. **Versão conhecida e recuperável:** antes de cada ativação, cópia somente leitura da versão anterior e novo manifesto de controle (sem tocar em v001/v002). Reversão = restaurar a cópia e o manifesto.
6. **Nenhum controle aprova a si mesmo:** a primeira ativação é feita por você, com comandos fora do controle novo. Um hook novo não autoriza as próprias gravações; o L0 novo não executa a própria missão de bootstrap.
7. **Fora do bootstrap:** alterar controle continua N3★; a tentativa vira PEND.

### Sessão de bootstrap, passo a passo (proposta, não implementada, aguarda D9)
1. **Ficha de bootstrap** escrita ou aprovada por você: arquivos exatos, objetivo, testes esperados. A NUV só rascunha.
2. **Configuração da sessão** escrita por você, em local fora do alcance do agente: `--agent mario`, `--tools Read,Write,Edit` (**sem Bash**), `dontAsk`, `permissions.allow` de `Write`/`Edit` **só** para os caminhos da ficha e `deny` para o resto. O `deny` de `agentes/l0/` **não é levantado**: a sessão de bootstrap tem uma `allow` explícita só para a lista; sessões comuns continuam sem ela. **H:** a eficácia de `allow` por caminho para `Write`/`Edit` não foi testada (X13). Por isso o registro independente do passo 3 e 5 é obrigatório.
3. **Snapshot antes** (lista e hash de arquivos do repositório), por script fixo, iniciado por você (ESH).
4. **Você inicia** a sessão no seu computador (CC-local).
5. **Snapshot depois** e comparação automática: qualquer arquivo fora da lista = violação; a sessão é descartada e vira PEND.
6. **Revisão:** a Peach audita o diff em sessão independente (resultado estruturado; CP-1 a CP-9 aceitos em D10); você lê o diff.
7. **Testes** só por ESH (`portoes_f2.md` P4).
8. **Ativação** por você, com comandos fora do controle novo.
Cada subetapa repete o procedimento; nada é herdado.

## 3. Componentes
| Componente | Função | Onde fica | Quem escreve |
|---|---|---|---|
| `l0.py` (biblioteca padrão do Python) | Validar, executar, retomar, relatar | `agentes/l0/` (SOMENTE_HUMANO) | usuário (D9: escrito por você, ou pelo Mario só em sessão de bootstrap autorizada, ver §2A) |
| `isolar.py` ou invólucro de `bwrap` | Confinar todo Bash e o `pytest` | `agentes/l0/` | idem |
| Gerador de configuração por papel | Produzir `--settings` e `--agents` a partir de arquivos SOMENTE_HUMANO | `agentes/l0/` | idem |
| Hook central | Identidade, política, lista de `Agent`, hash dos controles, `onFailure: "block"` | `agentes/hooks/` | idem |
| **Estado do L0** | Estado da missão, contadores, eventos, chave de assinatura opcional | **fora do repositório**, por exemplo `~/.local/state/dengue-l0/` (H) | só o L0 |
| Pendências | `PEND-nnn.md` para o usuário | `agentes/pendencias/` | só o L0 |

## 4. Validação antes de iniciar (itens 1 a 3 do requisito)
O L0 recusa começar se qualquer item falhar:
1. **Versão** do `claude` igual à fixada (hoje 2.1.327) e `python3` presente.
2. **Login válido.** A sessão de teste de laboratório já mostrou "Not logged in" como falha; o L0 trata isso como pausa, não como erro de missão.
3. **Hashes dos controles:** `l0.py`, hook, `isolar.py`, `agentes.json`, `protegidos.json`, `politica_lib.py`, missão, fichas, lista de exceções de runtime. Comparados com `controles.sha256` (guardado no estado do L0).
4. **Manifesto:** `manifesto.py verificar` (mecanismo autorizado da F1, rodado pelo L0 ou por ESH) sem divergência. Isso **não** depende de DX-2 (hash dos arquivos de manifesto) e **não** abre nem recalcula v001 e v002.
5. **Configurações:** `~/.claude/settings.json` ausente ou com hash conhecido; `~/.claude/agents/` ausente ou vazio; `.claude/settings.local.json` ausente; `/etc/claude-code/managed-settings.json` no estado esperado; nenhuma chave `disableAllHooks`. `--setting-sources` fixo.
6. **Isolamento:** autoteste do `bwrap` ou Landlock com arquivos sintéticos (leitura permitida, leitura negada, escrita negada, rede negada). Falhou, não inicia.
7. **Ferramentas:** na primeira sessão de cada papel, o `init` precisa trazer exatamente a lista esperada (`Read, Write, Edit, Bash` e, no modo B, `Task`); `Glob`, `Grep`, MCP ou `WebSearch` fora da lista abortam (R13, R20, T para o `init`).
8. **Orçamento e janela:** uso de rate limit abaixo do limiar antes de começar uma sessão (proposto 0,90, H).

## 5. Execução (itens 4 a 7 do requisito)
### Modo A (recomendado): L0 conduz a máquina de estados, uma sessão por papel
```
 PLANEJAR (Yoshi) ─► IMPLEMENTAR (Mario) ─► REVISAR DIFF (Peach, só leitura)
        ▲                                              │
        │                                              ▼
   DECIDIR (L0 + critérios) ◄── AUDITAR (Peach) ◄── TESTAR (Luigi, isolado)
        │                                   gate autoritativo: o L0 roda pytest,
        ├── critérios atendidos → próxima tarefa        ruff e manifesto verificar
        ├── não atendidos e ciclo < limite → novo ciclo (Mario)
        └── limite, negações, orçamento ou nível 3 → PEND
 ao fim das tarefas: RELATÓRIO FINAL (Yoshi) e PREPARAR PRÓXIMA SUBETAPA (Yoshi, sem iniciar)
```
- Cada passo é um `claude -p --agent <papel> --settings <gerado> --agents <arquivo> --tools <lista> --setting-sources project --output-format stream-json --verbose --include-hook-events --max-turns N --max-budget-usd X --no-session-persistence`, com ambiente mínimo. Classificação das flags (M1): usadas no laboratório e funcionando (T): `-p`, `--output-format stream-json`, `--verbose`, `--max-turns`, `--model`, `--setting-sources`, `--settings`, `--agents`, `--agent`, `--no-session-persistence`, `--debug-file`. **Só documentação (D), nunca rodadas:** `--tools`, `--max-budget-usd`, `--strict-mcp-config`, `--include-hook-events` (a F2.0-D as testa; até lá são H). Eventos `hook_started`/`hook_response` já aparecem no stream-json sem `--include-hook-events` (T, E01).
- O Yoshi **propõe** a próxima ação em arquivo estruturado (`decisao.json`); o L0 **valida** contra a missão e executa. O Yoshi não lança processos.
- **Resultado da Peach estruturado (A3).** A Peach grava `auditoria-<missao>-<ciclo>.json` (`criterios_peach_f2.md` §3). O L0 valida esquema, missão, ciclo, `base_hash` e referências de evidência; texto livre é informativo. Ausente, inválido ou incoerente = INCONCLUSIVO e bloqueio da tarefa.
- **Três aprovações distintas:** aprovação da auditoria, aprovação dos critérios técnicos (gates do L0) e autorização humana para avançar. Só a terceira inicia etapa nova (`criterios_peach_f2.md` §2).
- **Gate autoritativo.** O L0 roda `pytest`, `ruff` e `manifesto verificar` ele mesmo, dentro do isolamento, e guarda código de saída e saída. O relato do Luigi é diagnóstico, não evidência (I7).
- **Peach independente:** sessão própria, sem contexto do Mario, com `--agent peach`.

### Modo B (alternativa): Yoshi delega por subagentes numa sessão só
Menos processos, mas: contagem de turnos e custo fica agregada; falhas por rate limit interrompem o passo no meio (aconteceu com a Peach, T); o spawn depende do `PreToolUse` de `Agent`, **sem teste real de negação**; e o relato do subagente volta pelo Yoshi. Serve como evolução, não como base.

## 6. Orçamento, ciclos e negações (item 7)
- Por sessão: `--max-turns` e `--max-budget-usd` (D). O custo é estimativa do cliente e pode ser ultrapassado (D); o L0 deixa margem.
- Por missão: soma de `total_cost_usd` e `num_turns` do `result` de cada sessão (T: `total_cost_usd` e `num_turns` aparecem no `result` das sessões do laboratório, ex. E01 e E06b), tempo de relógio, número de ciclos por tarefa e de tentativas por passo.
- **Negações:** o L0 conta `permission_denials` e eventos `permission_denied` (T: aparecem no stream-json do E06b), `tool_result` de erro com texto de bloqueio e negações do hook. Ao atingir o limite por tarefa (proposto 5), encerra a tarefa e abre pendência. Evita o laço de contornos que o texto do `dontAsk` estimula (I8, T).
- Estourou qualquer teto: sessão encerrada, estado salvo, PEND.

## 7. Registro de eventos (item 8)
O L0 grava `eventos.jsonl` no estado, a partir de: stream-json (`init`, `tool_use`, `tool_result`, `result`, `rate_limit_event`), log do hook (fora do alcance dos agentes), códigos de saída dos gates, `git status` quando houver `.git`, hashes antes e depois. Cada decisão do L0 aponta para os eventos que a sustentam. O texto dos agentes é guardado como "relato" e não é critério.

## 8. Rate limit e retomada (itens 9 e 10)
- Eventos reais já observados: `rate_limit_event` com `utilization` ~0,94 e `overageStatus: rejected`; erro 429 com hora de renovação (T).
- Ao ver o evento ou o erro, o L0 interrompe a sessão, grava o passo, espera até a renovação mais uma margem e **repete o passo**. Isso depende de passos idempotentes (H).
- Interrupção por queda da sessão, compactação ou desligamento: `l0.py retomar` lê `estado_missao.json` (escrita atômica por arquivo temporário e renomeação), confere os hashes e reexecuta o passo incompleto com a ficha e o diff atuais. **Não depende de `--resume`:** a documentação diz que `--continue` ignora sessões criadas por `claude -p` (D). O estado vem do arquivo, e um `SessionStart` pode injetar o resumo (D).

## 9. Limites da missão e pendências (item 11)
O L0 impede que a missão ultrapasse a autorização de três formas: (1) a missão é imutável (hash); (2) o hook e os perfis de Bash só aceitam o que a ficha e o perfil listam; (3) nenhuma ação de nível 3 é executada. Quando surge uma, o L0 grava:

```
PEND-nnn  tarefa: ...  nível: 3  ação pedida: ...  motivo: (nível 3 | limite | negações | orçamento)
evidência: eventos e arquivos  opções: A) ... B) ...  padrão seguro enquanto espera: nenhuma ação
```
Tarefas independentes continuam. A missão termina com a lista das pendências.

## 10. Proteção do L0 e da autorização contra processos filhos (revisada em F2.0-C.1)
**Ameaça.** Todos os processos rodam com o mesmo usuário Unix. Permissões comuns (`chmod`) **não bastam**: o mesmo usuário as altera, e o Claude Code observa configurações que esse usuário grava (R18). Hash **detecta**, não **impede**. A proteção real é **prevenção por confinamento**, e ela ainda é H.

**Camadas (todas H até a F2.0-D, que as inclui no escopo):**
1. **Confinar o processo `claude` inteiro** (não só o Bash), por `bwrap` com allowlist (`plano_isolamento_r1.md` §4) ou Landlock. Controles montados **somente leitura**; estado do L0, chave, `~/.claude` do usuário e `/run/user/<uid>` **não montados**. Dependências a medir: caminhos que o CLI grava (R16), manutenção do login (`CLAUDE_CONFIG_DIR`), `bwrap` iniciado pelo L0.
2. **Bash de cada agente** também dentro do invólucro (defesa em profundidade; o hook valida o comando original e reescreve via `updatedInput`).
3. **Regras `deny` e hook** para `Read`/`Edit` nos caminhos do L0 e do estado (T no mecanismo de `deny`).
4. **Verificação de integridade antes e durante a execução, com frequência definida:**
   - antes de iniciar cada sessão: o L0 confere o `controles.sha256`;
   - **em toda chamada de ferramenta:** o hook confere o hash dos controles;
   - a cada evento do stream-json e em intervalo fixo (valor a medir na F2.0-D, não fixado aqui);
   - heartbeat: a primeira chamada de ferramenta de cada sessão precisa gerar registro do hook; sem ele, o L0 encerra (R23).
5. **Comportamento diante de falha:** hash divergente, hook sem registro, arquivo ausente ou erro do verificador → o L0 encerra o grupo de processos da sessão, grava PEND e não retoma sozinho. Falha de verificação nunca vale como "ok".
6. **Alterações por processos filhos:** o filho do Bash roda no confinamento (sem controles graváveis); o filho do `claude` confinado herda as restrições. Hardlink e symlink: não montar o alvo; testes de CP-5.
7. **Limites dos hashes:** detectam, não impedem; há janela entre verificações (alterar e restaurar passa despercebido); o hash armazenado precisa estar fora do alcance; hash de arquivo não cobre links, diretórios novos nem o processo em memória.
8. **Autorização fora da sessão:** §2 (TTY). HMAC é opcional e insuficiente contra o mesmo usuário sem confinamento.

**Limites que permanecem (L):** o `claude` sem confinamento tem os direitos do usuário; o usuário (ou quem tenha `sudo`) pode tudo; falhas do kernel, do `bwrap` ou do Landlock; sem cgroups (mitigação parcial: `ulimit` e tempo limite).

## 11. Encerramento e relatório (item 12)
O L0 **não inicia a subetapa seguinte nem autoriza a si próprio**: encerrar a missão não é autorização para a próxima (`matriz_autonomia.md` linhas 48, 51 e 52).

Ao final, o L0 gera `relatorio_final.md` a partir dos eventos: tarefas concluídas e não concluídas, ciclos, custos, negações, pendências, hashes antes e depois, riscos residuais, e o **plano da próxima subetapa preparado, mas não iniciado**. Depois imprime o resumo ao usuário.

## 12. Riscos do próprio L0
- Um L0 com defeito é o ponto único de falha: precisa de testes adversariais e auditoria da Peach, e entra na lista de arquivos SOMENTE_HUMANO.
- A autonomia só vale enquanto o limite de orçamento e de uso da conta valer; o L0 depende de eventos do CLI que podem mudar com a versão (a versão fica fixada e conferida).
- Quem inicia o L0 (o usuário) continua sendo o único que pode ampliar autoridade.
