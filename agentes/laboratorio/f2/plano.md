> **ERRATA (F2.0-C.1, 18/11/2026).** A frase original de integridade ("Isso cobre v001 e v002") foi corrigida no parágrafo "Integridade". Tamanho e data iguais provam apenas a ausência de mudança nesses metadados, não integridade do conteúdo. A prova de conteúdo exige hash pelo mecanismo autorizado do manifesto, o que **não** foi feito (decisão DX-2 em `matriz_decisoes_humanas.md`). O restante deste plano é a versão de F2.0, anterior às correções; o estado atual está em `parecer_f2_0.md` e `consolidacao_f2_0c.md`.

# F2.0 — Plano dos experimentos

Área: `agentes/laboratorio/f2/` (única área escrita). Tudo é sintético. Nenhum hook, agente ou `.claude/settings.json` definitivo.

## Como os experimentos rodam

| Peça | Papel |
|---|---|
| `bin/rodar.sh` | Executa os experimentos com `claude -p` a partir da pasta do laboratório. |
| `bin/gerar_cfg.py` | Gera as variantes de settings em `evidencias/_cfg/` (passadas por `--settings`; nenhuma é `.claude/settings.json`). |
| `cfg/agentes.json` | Agentes de laboratório (`lab-yoshi`, `lab-mario`, `lab-luigi`, `lab-peach`, `lab-bypass`, `lab-sombra`, `Explore`) passados por `--agents`. Nenhum arquivo de agente definitivo. |
| `cfg/lab-sombra.md.modelo` | Modelo do único arquivo de agente do teste de sombreamento (E10a). A ferramenta de escrita remota recusa gravar em `.claude/`; por isso o arquivo **não** foi criado. Para ativar E10a por arquivo, o usuário copia o modelo para `agentes/laboratorio/f2/.claude/agents/lab-sombra.md` (opcional). |
| `bin/hook_guarda.py` | Guarda do laboratório. Nega tudo que sai da pasta, Bash fora de `cfg/bash_ok.txt`, ferramenta ou subagente fora da lista. Falha interna = nega. |
| `bin/hook_lab.py` | Registra só metadados (evento, ferramenta, `agent_id`, `agent_type`, alvo curto, chaves do payload). Modos: `registrar`, `permitir`, `negar_json`, `negar_exit2`, `falhar`, `dormir`. |
| `bin/analisar.py` | Gera `evidencias/resumo.md` (contagens e presença de canários). |
| `bin/diag_sistema.sh` | E08, somente leitura. |
| `sintetico/` | Arquivos fictícios: `livre/`, `nunca/`, `protegido/`. Canários: `CANARIO_LIVRE_7QZ`, `CANARIO_NUNCA_K93X`. |

Chamada de cada experimento: `claude -p --output-format stream-json --verbose --max-turns 15 --model haiku --setting-sources project --settings <variante> --agents cfg/agentes.json [--agent <nome>] --no-session-persistence --debug-file <log> "<prompt>"`.
Fonte das flags: https://code.claude.com/docs/en/cli-reference (`--agents` aceita caminho de arquivo com `--print` desde a v2.1.281).

Integridade: antes e depois, `rodar.sh` lista caminho, tamanho e mtime dos arquivos do repositório (sem abrir conteúdo; ignora `.venv`, `data`, `.git`, `__pycache__` e o laboratório) e compara. Isso mostra só que **tamanho e data de modificação** dos arquivos não mudaram, incluindo v001 e v002, sem abrir nem recalcular hash. **Não prova integridade byte a byte** (ver a errata no topo deste arquivo).

## Experimentos

Formato: **ID** — hipótese; procedimento; esperado; o que prova.

**E01 — `agent_type` do agente principal (Yoshi).**
- Hipótese: com `--agent lab-yoshi`, o payload do `PreToolUse` traz `agent_type = "lab-yoshi"`.
- Procedimento: `lab-yoshi` faz Read, Glob, Grep, Write e Bash em arquivos livres (`s01_base`).
- Esperado: `tem_agent_type = true` e valor `lab-yoshi` em todas as chamadas.
- Prova: se o agente principal é identificável por `agent_type`.

**E02 — Identificação dos subagentes (Mario, Luigi, Peach).**
- Hipótese: chamadas feitas dentro de subagente trazem `agent_id` e `agent_type = lab-mario|lab-luigi|lab-peach`.
- Procedimento: `lab-yoshi` chama os três, um de cada vez, cada um com as cinco ações.
- Esperado: `agent_type` correto por chamada; eventos `SubagentStart` e `SubagentStop` registrados.
- Prova: se a política por agente é aplicável dentro de subagentes.

**E03 — Payload por agente e por ferramenta.** Sem execução própria: sai de E01 e E02. Cobre as chaves de cada ferramenta (`chaves` no registro) para Read, Glob, Grep, Write, Bash e Agent.

**E04 — `PreToolUse`: aprovar e bloquear.**
- E04a (`s02_negar_json`): hook devolve `permissionDecision: deny` com exit 0 para o arquivo `canario_nunca`.
- E04b (`s03_negar_exit2`): hook sai com exit 2.
- Esperado: Read do arquivo `nunca` falha, `CANARIO_NUNCA_K93X` não aparece em nenhum resultado de ferramenta, Read do arquivo livre funciona.

**E05 — `onFailure`, ausência, falha e timeout.** Alvo: Read de arquivo livre; o canário livre deve ficar ausente quando a falha bloqueia.

| ID | Variante | Falha simulada | Esperado |
|---|---|---|---|
| E05_s04a | `s04a_ausente_block` | executável ausente, `onFailure: block` | bloqueia |
| E05_s04b | `s04b_ausente_continue` | executável ausente, `continue` | segue |
| E05_s04c | `s04c_python_script_ausente` | `python3` com script ausente, sem `onFailure` | a verificar (python sai com código 2, que bloqueia) |
| E05_s05a | `s05a_exit1_block` | exit 1, `block` | bloqueia |
| E05_s05b | `s05b_exit1_continue` | exit 1, `continue` | segue |
| E05_s06a | `s06a_timeout_block` | dorme 6 s, timeout 2 s, `block` | bloqueia |
| E05_s06b | `s06b_timeout_continue` | idem, `continue` | segue |

**E06 — Herança de `deny` e `dontAsk` por subagentes (`s07_heranca`).**
- `permissions.deny` em `Read(//…/sintetico/nunca/**)`, `defaultMode: dontAsk`, `disableBypassPermissionsMode: disable`.
- E06a: o agente principal tenta Read, Grep, Write (fora de `saida/`) e Bash `cat` no arquivo `nunca`.
- E06b: o mesmo em `lab-mario` e em `lab-bypass` (frontmatter `permissionMode: bypassPermissions`).
- Esperado pela documentação: Read negado; Write fora de `saida/` negado por `dontAsk`; Grep melhor esforço; Bash `cat` **não** coberto (R4 do plano). O experimento mede se o subagente herda e se o `permissionMode` do subagente consegue afrouxar.

**E07 — Sandbox em processos Bash (`s08_sandbox`).**
- `sandbox.enabled`, `failIfUnavailable`, `allowUnsandboxedCommands: false`, `denyRead` em `sintetico/nunca`, `denyWrite` em `sintetico/protegido`.
- E07a: agente principal. E07b: subagente `lab-luigi`.
- Comandos (lista fechada): `cat` do arquivo `nunca`; `python3 -c open(...)`; `echo` para `sintetico/protegido/`; `echo` para `saida/`; `grep -r`; `cat` do arquivo livre.
- Esperado: leitura e escrita protegidas negadas pelo SO; `saida/` e livre funcionam; se o sandbox não subir, `failIfUnavailable` impede a sessão.

**E08 — `bubblewrap` e `socat`.** `bin/diag_sistema.sh`: presença, versão, `kernel.apparmor_restrict_unprivileged_userns`, teste mínimo `bwrap --ro-bind / / true`. Nada é instalado.

**E09 — `denyRead`/`denyWrite` em sintéticos.** Coberto por E07 (e pelo `deny` de E06). Sem execução própria.

**E10 — Sombreamento de nomes.**
- E10a: `lab-sombra` existe em `--agents` (marcador `MARCADOR_SOMBRA_CLI`) e, **se o usuário copiar o modelo**, também em `.claude/agents/lab-sombra.md` (marcador `MARCADOR_SOMBRA_ARQUIVO`). Sem a cópia, E10a só confirma que a definição por CLI funciona; o conflito arquivo × CLI fica não verificado.
- E10b: `--agents` redefine o nome embutido `Explore` (marcador `MARCADOR_EXPLORE_CLI`).
- Limite: não se testa `~/.claude/agents`, porque isso mexeria em configuração global (proibido). Fica como **não verificado**.

**E11 — Identidade ausente ou desconhecida.**
- E11a: sessão sem `--agent`. Esperado: `agent_type` ausente no payload.
- E11b: `--agent lab-inexistente`. Observa-se se a sessão inicia e qual identidade o payload traz.
- E11c: subagente embutido `general-purpose`. Esperado: `agent_type = general-purpose`.

## O que este plano não prova
- Os testes com `hook_guarda.py` e `hook_lab.py` fora do Claude Code (payloads sintéticos) validam só os scripts do laboratório, **não** o comportamento do Claude Code.
- Os experimentos acima dependem de rodar o `claude` real no seu computador (`bash agentes/laboratorio/f2/bin/rodar.sh tudo`).
