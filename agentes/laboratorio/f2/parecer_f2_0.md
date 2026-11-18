# F2.0 — Parecer técnico (versão corrigida em F2.0-C, atualizada em F2.0-C.1, C.2 e C.3)

**Conclusão: F2.0 concluída com ressalvas; a primeira auditoria independente (sobre a F2.0) deu APROVADA COM RESSALVAS.** Os experimentos reais rodaram em 18/11/2026 (Claude Code 2.1.327, Ubuntu 26.04.1, modelo Haiku, uma conta). A arquitetura F2 é viável para ferramentas de arquivo, hooks e subagentes. O sandbox do Claude Code (L4) não funciona neste computador. Esta F2.0 não aprova a F2: faltam as condições da seção 6. Nada de F2.1 foi iniciado.

Legenda: **T** testado no ambiente real; **D** documentação; **H** hipótese; **L** limitação.

Este parecer substitui a versão anterior. A cópia que estava no disco era antiga (5385 bytes, "Situação: PARCIAL"), embora o commit tivesse respondido "written" (achado C1). Causa não apurada.

## 1. O que ficou provado (T)
1. **Identidade.** O agente principal chega aos hooks com `agent_type` e **sem** `agent_id`. Subagentes chegam com os dois. Sem `--agent`, o `agent_type` some. `--agent` desconhecido impede a sessão de iniciar. Subagentes embutidos aparecem com o próprio nome (`general-purpose`, `Explore`).
2. **Bloqueio por hook.** `deny` em JSON e exit 2 bloqueiam sem devolver o conteúdo. O motivo do hook, e o caminho do script, aparecem para o modelo.
3. **`onFailure`.** Com `"block"`: executável ausente, exit 1 e timeout (2 s atingido) bloqueiam. Com `"continue"` passam (T). **Sem o campo:** só `python3 script_ausente.py` foi testado e bloqueou, porque o Python sai com 2; para executável ausente, exit 1 e timeout, o comportamento **sem o campo não foi testado** (a documentação diz que o padrão é `continue`, D; o X18 da F2.0-D testa). Todas as variantes foram testadas só com `Read` e agente principal.
4. **`deny` e `dontAsk`.** O `deny` de `Read` vale no agente principal e em subagentes, e **vence o `allow` de um hook** (log do E06b; a documentação confirma). Ele agiu também sobre `cat` via Bash (subcomando com caminho). `dontAsk` nega escrita fora do permitido em subagentes.
5. **`tools` na definição do agente** reduz o agente principal a `Read, Write, Edit, Bash, Task`. Sem `--agent`, a sessão tem conectores, `RemoteTrigger`, `CronCreate` e `WebSearch`.
6. **Observação do payload.** `PreToolUse` de `Agent` traz `subagent_type` e roda antes do `SubagentStart`.
7. **Integridade (só metadados).** Nenhuma alteração de caminho, tamanho ou data fora do laboratório. Nenhum canário protegido foi devolvido por ferramenta.

## 2. O que NÃO foi provado ou ficou limitado
| Ponto | Situação |
|---|---|
| Negação de spawn | **Nenhum teste real negou um `Agent`.** O guarda aprovou `lab-*`, `Explore` e `general-purpose`. O controle de spawn por `PreToolUse` é plausível (H forte), não confirmado (I2). |
| `Glob` e `Grep` | **Indisponíveis nas sessões testadas.** A documentação diz que no Linux ficam fora do conjunto padrão e que a busca passa pelo Bash (`bfs` e `ugrep` embutidos). Voltam com `--tools`, `--allowedTools`, remoção do Bash ou definição de agente que as liste sem Bash. Não é "inexistente no CLI" (I1, R13). |
| Cobertura do `deny` | Provada só para `cat`. Não provada para `python -c`, `head`, `base64`, redirecionamentos, variáveis, globs (R15). |
| `lab-bypass` | O log diz que o `permissionMode` do subagente não foi autorizado e o pai ficou em `dontAsk`, com várias causas possíveis. Efeito do `disableBypassPermissionsMode` não isolado (I4). |
| Sandbox | Todo Bash falhou com `apply-seccomp … nested userns is capability-restricted`; nenhum comando executou. O log do E07a não tem linha sobre sandbox, então **não afirmo que a checagem inicial passou** (I5). Causa (H): restrição de user namespaces aninhados do Ubuntu 26.04; o `bwrap` mínimo do E08 passa. |
| R12 | `.claude/.cc-writes/` foi criada (vazia na listagem). A correlação no tempo é com o primeiro Bash sob sandbox. Relação **não comprovada** (I6). |
| Sombreamento | `--agents` redefine o nome embutido `Explore` (T). Arquivo × CLI, `~/.claude/agents` e plugins: não testados. |
| Recarga, socket, hooks conflitantes, `disableAllHooks` | Não testados. Existem no log (observadores de arquivos de configuração, socket `uds-messaging`). Efeitos: H. |
| Relatos dos agentes | Erraram (E02, E06a). **Os logs externos são a fonte de evidência** (I7). |

## 3. Integridade dos manifestos v001 e v002 (texto corrigido)
Só se verificaram tamanho (v001 37165 B, v002 43487 B) e data, por listagem de diretório, antes e depois da F2.0. Isso demonstra **apenas a ausência de mudança nesses metadados**. Não demonstra integridade byte a byte. Os manifestos não foram abertos nem recalculados. O snapshot excluiu `.venv`, `data`, `.git` e `__pycache__`. Qualquer verificação mais forte exige o mecanismo autorizado (`manifesto.py verificar`) ou nova autorização.

## 4. Riscos e mitigações principais
Registro completo em `registro_riscos.md`. Os cinco que mais pesam:
1. **R1/R21.** Código executado como processo filho (Mario → Luigi/Peach) ignora os controles de ferramenta e pode tocar `~/.claude`, `.claude/settings.local.json`, `.git` e `data/`. Mitigação proposta: isolamento por `bwrap` direto ou Landlock, ambos sem `sudo` (H, a testar). Ver `plano_isolamento_r1.md`.
2. **R18/R19.** Recarga de configuração e socket de mensagens podem mudar a política ou forjar "usuário" (H). Mitigação: L0 que confere hashes, confina a sessão e usa autorização fora do chat.
3. **R20.** Sem `--agent`, a sessão tem conectores e ferramentas extras. Mitigação: L0 sempre com `--agent` e `--tools` fechadas, e confere o `init`.
4. **R25/I7.** O hook não registra negações por regra. Mitigação: L0 registra o stream-json.
5. **R12.** Pasta criada pelo runtime pode acusar `NOVO_EM_AREA_SOMENTE_HUMANO`. Mitigação: lista de exceções de runtime aprovada pelo usuário.

## 5. Arquitetura F2 revisada
Resumo. Detalhes: `arquitetura_l0.md`, `matriz_autonomia.md`, `plano_isolamento_r1.md`.
- **L0 passa a ser um orquestrador externo**, fora do raciocínio dos agentes. Ele valida o ambiente, lê uma missão autorizada pelo usuário, inicia **uma sessão `claude -p` por papel**, sempre com `--agent`, controla orçamento, turnos, ciclos, negações e rate limit, registra a partir dos logs do sistema, retoma após interrupção e abre pendências.
- **Camadas L1 a L3** (`dontAsk`, `deny` estático, hook com `onFailure: "block"`) permanecem.
- **L4 deixa de ser o sandbox do Claude Code** e passa a ser um isolamento próprio (`bwrap` direto ou Landlock), a validar.
- **L5** usa os logs do L0 e hashes dos arquivos de controle.
- **A autorização humana é uma missão fora do chat**, não uma mensagem na sessão.

## 6. Condições para iniciar etapas
As condições de cada etapa estão em **`portoes_f2.md`** (fonte normativa; tabela de portões de F2.0-D a F2.7). Em resumo: nenhuma etapa inicia a seguinte; a F2.1 **não** é bloqueada por R1 aberto (R1 bloqueia execução dependente de isolamento, não a entrada); a F2.0-D exige D3 com escopo fechado e D10; a prova do isolamento é a F2.3 (CP-5). A versão anterior desta seção exigia D1 a D10 inteiras antes da F2.1 e foi substituída.

## 7. Encerramento (versão F2.0-C)
A F2.0 está consolidada. Não inicio F2.1 nem implemento controles. Aguardo a avaliação do usuário.


## 8. Atualização F2.0-C.1
**Segunda auditoria da Peach (sobre a F2.0-C): APROVADO COM RESSALVAS**, sem críticos e com cinco altos (A1 a A5). A aprovação vale só para a consolidação documental; não aprova F2, L0, isolamento R1 nem a F2.1. O relato da auditoria vem de um subagente e foi apresentado a você.

**O que mudou nos documentos (sem executar nada):**
- **A1:** bootstrap dos controles definido no papel (`arquitetura_l0.md` §2A), decisão D9.
- **A2:** autorização de missão com resumo legível e confirmação em TTY (`arquitetura_l0.md` §2), decisão D4 revisada. HMAC não é proteção suficiente contra o mesmo usuário Unix.
- **A3:** resultado estruturado da Peach e três aprovações distintas (`criterios_peach_f2.md` §2 a §4). Linha 38 da matriz alinhada.
- **A4:** proteção preventiva dos controles (confinar o `claude` inteiro, somente leitura, hash em toda chamada, falha encerra) entrou no escopo da F2.0-D.
- **A5:** plano de `bwrap` reescrito como allowlist, com canários fora do repositório (`plano_isolamento_r1.md`).
- **M1 a M9** tratados; ver `rastreabilidade.md`.

**O que continua não provado:** tudo o que é desenho de L0, isolamento, bootstrap e missão é **H**. R1 continua **aberto**. Nenhum ponto da auditoria é dado como resolvido por prova técnica; "tratado no papel" não é "mitigado".

**Decisões que dependem de você:** D1 a D10 em `matriz_decisoes_humanas.md`, nenhuma autorizada. F2.0-D e F2.1 continuam **bloqueadas**.


## 9. Atualização F2.0-C.2
A terceira auditoria da Peach (sobre a F2.0-C.1) deu **APROVADO COM RESSALVAS**, com três achados altos. A F2.0-C.2 os tratou no papel: **D3** com escopo fechado (`matriz_decisoes_humanas.md`, `f2_0d_especificacao.md`), **portões únicos** (`portoes_f2.md`) e **CP-1** com critérios de sucesso, falha e inconclusão (`criterios_peach_f2.md`). Nada foi executado. R1 continua aberto. F2.0-D e F2.1 continuam bloqueadas.


## 10. Atualização F2.0-C.3
A quarta auditoria da Peach (sobre a F2.0-C.2, `parecer_peach_f2_0c_2.md`) deu **APROVADO COM RESSALVAS**, com 0 críticos, 3 altos, 8 médios e 6 baixos. A F2.0-C.3 os tratou **no papel**: pacote B **NÃO AUTORIZADO / BLOQUEADO** com perfil de contenção proposto (H) e condições de desbloqueio; fichas X20 e X21 completas; regra estreita para `~/.claude` e snapshot definido; etapa preparatória F2.0-D0; lista fechada de arquivos; canários fora do repositório; limpeza; modo do CC-local. **Nada foi executado nem provado.** R1 continua aberto; F2.0-D e F2.1 continuam bloqueadas. Ver `portoes_f2.md`, `f2_0d_especificacao.md` e `relatorio_f2_0c_3.md`.
