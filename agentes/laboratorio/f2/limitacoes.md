# F2.0 — Limitações, hipóteses não verificadas e riscos

> **Leitura:** as seções 1 a 5 são **históricas** (escritas antes da execução dos experimentos). O estado atual está nas seções 6, 7 e 8. Onde houver conflito, valem 6 a 8.

## 1. Limitação da primeira execução (HISTÓRICO, superado pela seção 6)
- **L-01. (HISTÓRICO, obsoleto.)** Na época da primeira entrega, nenhum experimento real tinha rodado, e os resultados E01–E11 estavam pendentes. Isso **deixou de ser verdade** em 18/11/2026: o usuário executou os experimentos. Ver seção 6. **Continua válido:** este ambiente de trabalho não tem shell no computador do usuário, e eu só vi o que os arquivos mostram.
- **L-02.** Os testes com payload sintético provam só os scripts do laboratório, não o Claude Code.

## 2. Hipóteses não verificadas (HISTÓRICO; o status atual está na seção 6)
| ID | Hipótese | Experimento |
|---|---|---|
| H-01 | `agent_type` aparece com `--agent` para o agente principal | E01 |
| H-02 | `agent_type` e `agent_id` corretos nos subagentes | E02 |
| H-03 | Agentes definidos por `--agents` funcionam com `--agent` | E01 |
| H-04 | JSON `deny` e exit 2 bloqueiam sem devolver conteúdo | E04 |
| H-05 | `onFailure: block` cobre ausência, exit 1 e timeout (v2.1.327 instalada) | E05 |
| H-06 | `python3 script_ausente.py` sai com 2 e bloqueia sem `onFailure` | E05_s04c |
| H-07 | `deny` e `dontAsk` valem dentro de subagentes | E06 |
| H-08 | `permissionMode` do subagente não afrouxa o pai | E06b |
| H-09 | Sandbox cobre Bash do agente principal e do subagente | E07 |
| H-10 | `bubblewrap`, `socat` e AppArmor estão utilizáveis sem instalar nada | E08 |
| H-11 | Definição por CLI e por arquivo: qual vence (arquivo só se o usuário copiar o modelo) | E10 |
| H-12 | Identidade ausente = `agent_type` ausente; desconhecida é tratada como esperado | E11 |
| H-13 | Hooks do mesmo grupo rodam em paralelo e `deny` vence `allow` | E04, E05 |
| H-14 | `--setting-sources project` com cwd no laboratório não carrega settings do repositório | E01 (ver `debug.log`) |

## 3. Não testável dentro da área autorizada
- **N-01.** Sombreamento por `~/.claude/agents/` (config global; proibido). Fica como risco R7 aberto.
- **N-02.** Settings gerenciadas (`/etc/claude-code`), exigem `sudo`. Proibido.
- **N-03.** Instalação de `bubblewrap`/`socat`/perfil AppArmor. Proibido. Se E08 mostrar ausência, o sandbox fica sem teste (E07 vai falhar com `failIfUnavailable`; isso também é resultado).
- **N-04.** Efeito de `.claude/settings.json` do projeto real. Proibido criar. Os testes usam `--settings`, que pode comportar-se diferente do arquivo de projeto (precedência e confiança de pasta).
- **N-05.** Hook sobre arquivos reais protegidos: proibido; só sintéticos.

## 4. Riscos do próprio laboratório
- **R-L1.** `claude -p` grava estado em `~/.claude` (histórico, telemetria local), mesmo com `--no-session-persistence`. É uma escrita global inevitável, fora do repositório e fora do alcance da política. **Nota C.3:** a especificação da F2.0-D (`f2_0d_especificacao.md` §4.6) trata esta escrita como **tolerada e estreita** (estado do CLI), proíbe alterar configuração, agentes, hooks e credenciais, define o snapshot que **detecta** (não impede) e exige `CLAUDE_CONFIG_DIR` dedicado (X20) para as sessões do pacote B; registrado como R35.
- **R-L2.** `bash_ok.txt` e o guarda dependem de o modelo emitir o comando exatamente como pedido. Se o modelo reescrever o comando, o guarda nega (falha segura, experimento inconclusivo). Repetir o experimento.
- **R-L3.** Modelos pequenos (`haiku` por padrão; `LAB_MODELO` muda) podem não seguir os prompts. Isso gera resultado "não executou a ação", que não é resultado de bloqueio. A análise precisa separar "negado" de "não tentado" (registro do hook mostra a tentativa).
- **R-L4.** `lab-bypass` declara `bypassPermissions`. Se o `deny` do pai não prevalecer, o subagente consegue ler `canario_nunca.txt` (sintético). O guarda ainda confina a pasta do laboratório. Risco aceito por ser sintético.
- **R-L5.** O diff de integridade compara só **metadados** (caminho, tamanho, data) e ignora `.venv`, `data`, `.git` e `__pycache__`. Alterações nesses locais não seriam vistas. Para v001 e v002 (que estão dentro do verificado), tamanho e data iguais demonstram **apenas a ausência de mudança nesses metadados**; não demonstram integridade byte a byte (corrigido em F2.0-C).
- **R-L6.** A ferramenta de escrita remota recusou gravar em `.claude/` ("Writing to .claude is not permitted via remote tools"). Não contornei. Consequência: o conflito arquivo × CLI do E10a depende de o usuário copiar `cfg/lab-sombra.md.modelo` para `.claude/agents/lab-sombra.md` dentro do laboratório. Se copiar, remover depois da F2.0.

## 5. Riscos da arquitetura F2 já confirmados pela documentação (D)
- `SubagentStart` não bloqueia: o controle de subagentes fica no `PreToolUse` da ferramenta `Agent`.
- `SubagentStop` não tem `onFailure`: não depender dele para segurança.
- `disableAllHooks` por `--settings`: o controle não vale contra quem lança a sessão.
- Hooks de níveis diferentes somam: um hook de usuário extra roda junto.

## 6. Atualização após a execução nº 2 (18/11/2026)

Status das hipóteses da seção 2:

| ID | Status | Evidência |
|---|---|---|
| H-01 | **Confirmada (T)** | E01 |
| H-02 | **Confirmada (T)** | E02 |
| H-03 | **Confirmada (T)** | E01 |
| H-04 | **Confirmada (T)** | E04 |
| H-05 | **Confirmada (T)** em 2.1.327, **no escopo testado:** hook de `PreToolUse` carregado por `--settings`, com Haiku, para ausência do script, saída 1 e timeout de 2 s. Não testada fora desse escopo (outros eventos, hooks de `~/.claude`, `SubagentStop`, outras versões) | E05 |
| H-06 | **Confirmada (T)** | E05_s04c |
| H-07 | **Confirmada (T), no escopo testado:** `deny` de `Read` sobre o diretório sintético e `dontAsk`, no agente principal e em subagentes. **Não cobre** `Bash` com `python -c`, `head`, `base64` ou subprocessos (R1, R15) | E06 |
| H-08 | **Parcial:** `lab-bypass` não afrouxou, mas o teste usou `disableBypassPermissionsMode: disable`; efeito isolado não separado | E06b |
| H-09 | **Refutada neste computador:** o sandbox não executa Bash (`apply-seccomp`); nenhum comando executou | E07 |
| H-10 | **Parcial:** `bwrap` e `socat` existem e o teste mínimo do `bwrap` passa, mas o sandbox do Claude Code falha. O log do E07a não tem linha sobre a checagem inicial (não afirmar que ela passou) | E07, E08 |
| H-11 | **Parcial:** CLI sobrepõe o embutido; arquivo × CLI não testado | E10 |
| H-12 | **Confirmada (T)** | E11 |
| H-13 | **Parcial:** a documentação diz que, entre hooks, `deny` > `defer` > `ask` > `allow`, e que `allow` de hook não anula `deny` de regra (confirmado no log do E06b). Paralelismo dos hooks de um grupo e combinação de `updatedInput`: H | E06b |
| H-14 | **Confirmada (T)** | execução nº 1 |

Riscos novos:
- **R12.** O runtime criou `.claude/.cc-writes/` na pasta do projeto (vazia na listagem). A correlação no tempo é com o primeiro Bash sob sandbox (E07a); **a relação não está comprovada (H)**. Se pasta vazia ou `.cc-writes` aciona `NOVO_EM_AREA_SOMENTE_HUMANO` no `manifesto.py verificar`: não sabido.
- **R13.** `Glob` e `Grep` estão **ausentes por padrão no Linux** (documentação; T nas sessões testadas) e voltam por `--tools`, `--allowedTools`, remoção do Bash ou definição de agente que as liste sem Bash. A disponibilidade varia por sessão e por configuração. O L0 deve fixar `--tools` e conferir o `init` a cada sessão.
- **R14.** O motivo do hook aparece para o modelo. Mensagens de bloqueio não podem citar caminhos sensíveis.
- **R15.** O Bash negado pelo `deny` de `Read` (`cat`) tem mecanismo não isolado. Outros caminhos de leitura (`python -c`, `head`, `less`, `base64`) não foram testados fora do sandbox.
- **R-L16** (antes "R16"; **não é o R16 de `registro_riscos.md`**, que trata de escrita fora do repositório). O sandbox falhou fechado (nada executou), mas falha fechada só protege o que passa por ele. Sem sandbox, processos rodados por `pytest`/scripts ficam sem barreira de SO (R1 segue aberto).
- **R17.** Os experimentos usaram Haiku. Modelos maiores podem tentar outras rotas. Os resultados de bloqueio são do Claude Code, não do modelo, mas os de "o modelo tentou X" não generalizam.


## 7. Atualização F2.0-C (consolidação)

- Registro completo de riscos, com mitigação e evidência necessária: `registro_riscos.md` (R1 a R33; ver `registro_riscos.md`). Os riscos novos desta etapa são R18 (recarga de configurações), R19 (socket de mensagens), R20 (conectores e ferramentas inesperadas), R21 (processos filhos gravando controles e arquivos fora do repositório), R22 (hooks conflitantes), R24 (arquivos fora do snapshot), R25 (logs incompletos), R26 (rate limit), R27 (tentativas repetidas após bloqueio) e R28 (sombreamento de agentes).
- **Logs incompletos (R25), com evidência:** a regra `deny` de `Read` age antes do hook (E06: nenhum `PreToolUse` de `Read` em `nunca`). O log dos hooks, sozinho, não registra essas negações. O L0 precisa registrar também o stream-json (`tool_result` com erro, `permission_denials`).
- **Relatos de agentes (I7):** não são evidência. Conferido no E02 e no E06a.
- **Defeito de entrega (C1):** o parecer reescrito não chegou ao disco no commit anterior, apesar de "written". Regra nova: reler do disco e conferir tamanho após cada gravação.
- Hipóteses ainda abertas que bloqueiam o desenho final: negação real de `Agent`; recarga ao vivo; uso do socket por processos filhos; cobertura do `deny` sobre `python -c`, `head`, `base64`; isolamento com `bwrap` ou Landlock executando `pytest`; reaparecimento de `.cc-writes` sem sandbox. Ver `questoes_abertas.md` e o experimento proposto F2.0-D em `roadmap_f2_revisado.md`.


## 8. Atualização F2.0-C.1 (correção documental)
- **M4, identificador R16:** o item da seção 6 passou a **R-L16**. Histórico preservado. R12 a R15 e R17 coincidem com o registro; R16 do registro é outro risco.
- **M5, textos obsoletos:** L-01 e as seções 1 e 2 estão marcadas como histórico. H-05 e H-07 ganharam o escopo em que foram testadas.
- **M9, proveniência do `resumo.md`:** o `evidencias/resumo.md` atual foi gerado por uma **cópia corrigida do `analisar.py` fora do repositório**, não pelo `analisar.py` da pasta (que foi corrigido depois). O script usado não está versionado, e a pasta não tem `.git`. A análise de `resultados.md` B3 foi feita **sobre os arquivos brutos** (`*.jsonl`, `*.out.jsonl`), então o `resumo.md` é só conveniência. Não reproduzi o resumo com o `analisar.py` corrigido (sem shell no computador).
- **M1, flags:** `--tools`, `--max-budget-usd`, `--strict-mcp-config` e `--include-hook-events` **não** foram usadas no laboratório (confirmado em `bin/rodar.sh`); estão como D/H. `total_cost_usd`, `num_turns` e eventos `permission_denied` estão no stream-json dos experimentos (T).
- **Nada aqui foi executado de novo.** Todas as correções são documentais.

## 9. Atualização F2.0-C.2
- **M-4, `onFailure`:** testado com `block` e com `continue` (E05). **Sem o campo**, só `python3 script_ausente.py` foi testado (bloqueou, porque o Python sai com 2). Executável ausente, exit 1 e timeout sem o campo: **não testado**; a documentação diz que o padrão é `continue` (D). X18 da F2.0-D investiga. H-05 vale só para o escopo da seção 6.
- **M-3, `deny`:** só o `deny` de `Read` foi testado (E06). `Write`, `Edit` e Bash (exceto o `cat` negado por `deny` de `Read`) são D/H. X13 investiga.
