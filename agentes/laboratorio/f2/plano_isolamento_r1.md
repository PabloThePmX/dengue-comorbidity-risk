# Plano de isolamento para R1 (F2.0-C.2; sem alteração de conteúdo na D0)

**R1:** um subprocesso do Bash (`python -c`, script, `pytest`) roda com os direitos do usuário e pode ler ou escrever fora do que o hook e as regras `deny` enxergam. O `deny` de `Read` só foi provado contra `cat` (T). R1 **continua aberto**. Nada abaixo foi testado no ambiente; tudo o que é desenho está marcado H.

Classes: **T** testado, **D** documentação, **H** hipótese, **L** limitação. Restrições da investigação: sem `sudo`, sem instalação, sem mudança de sistema.

## 1. Fatos medidos
- Sandbox do Claude Code falha em todo Bash (`apply-seccomp … nested userns is capability-restricted`) (T, E07).
- `kernel.apparmor_restrict_unprivileged_userns=1`; `bwrap 0.11.1` e `socat` instalados; `bwrap --ro-bind / / --dev /dev --unshare-all true` retornou OK (T, E08). Esse teste não executou Python, `pytest`, escrita nem partiu de um filho do `claude`. A causa de o `bwrap` direto passar e o sandbox do CLI falhar não foi isolada (H, Q12).

## 2. Cinco tipos de proteção (não se confundem)
| Tipo | O que protege | Mecanismo candidato | Estado |
|---|---|---|---|
| Isolamento de **arquivos** | O que o processo lê e grava | Allowlist de montagens (bwrap) ou Landlock | H |
| Isolamento de **processos** | Ver, sinalizar, ptrace outros processos | `--unshare-pid`, `--unshare-ipc`, `--die-with-parent`; sem seccomp e sem cgroups (L) | H |
| Isolamento de **rede** | `connect()` a TCP e a sockets | `--unshare-net`; sockets de caminho dependem de não montar o caminho (bwrap) ou do ABI (Landlock) | H |
| **Proteção dos controles** contra alteração | Hook, L0, configurações, política | Montagem somente leitura **e** confinamento do processo `claude` inteiro; `deny`; hash | H |
| Proteção contra **hardlink e symlink** | Atalhos que alcançam protegidos | Não montar o alvo; `fs.protected_hardlinks`/`protected_symlinks` do kernel (valor não verificado); escrita só em diretório próprio | H |

Isolar só o Bash **não** protege os controles quando o próprio `claude` (ferramentas `Write`/`Edit`) roda sem confinamento. Hash detecta, não impede (ver §6).

## 3. Alternativas
| # | Alternativa | Sem sudo/instalação? | Cobre | Evidência | Limites |
|---|---|---|---|---|---|
| A | Usuário Unix separado | **Não** (exige root) | Arquivos e processos, forte | D | Inviável nas restrições atuais; opção do usuário (D2). Login do CLI precisa ser refeito (H). |
| B | Diretório de trabalho isolado | Sim | Acidentes, não ataque | D | Complemento. |
| C | `HOME` temporário | Sim | Parcial (quem usa `$HOME`) | D | Complemento. |
| D | Ambiente mínimo (`env -i`, `--clearenv`) | Sim | Variáveis e segredos herdados | D | Complemento. |
| E | Landlock por launcher próprio (ctypes) | Sim, sem root (D) | Arquivos; rede em ABI ≥4; sockets de caminho em ABI ≥9 | D (kernel); ABI local **não verificado** (H) | Não esconde nomes, não restringe `stat`/`chmod`, fds abertos escapam. |
| F | `bwrap` direto com **allowlist** | Sim (instalado) | Arquivos, processos, rede, controles (se o `claude` for confinado) | **T só no teste mínimo** | Falta provar com Python, `pytest`, escrita e como filho do `claude`; pode depender do mesmo AppArmor que quebrou o sandbox do CLI (H). |
| G | Sandbox nativo do Claude Code | Sim | Em tese tudo | **T: inutilizável aqui** | Falha por userns aninhado. |
| H | Contêineres | Desconhecido | — | Nenhuma | Não verifiquei se existem; provável mesma restrição (H). |

**Recomendação:** F com allowlist (§4), mais B, C e D; reserva E. Nada é afirmado como funcionando no ambiente. G fora; H sem avaliação.

## 4. Estratégia de allowlist de montagens (desenho para testar)
Princípio: **só existe dentro do confinamento o que está na lista**. Tudo mais não é montado (inexistente para o processo). Mapa com a decisão de projeto para cada item:

| Item | Decisão proposta | Modo | Observação / prova necessária |
|---|---|---|---|
| Diretório de trabalho da tarefa | Montar | leitura e escrita **só** nos caminhos da ficha; resto do repositório somente leitura | Provar que `saida/` e arquivos da ficha gravam e o resto não. |
| Repositório: pastas protegidas (NUNCA_ACESSAR, SOMENTE_HASH, 2024, `data/`) | **Não montar** | — | Canário protegido sintético deve ser inexistente ao `python -c`. Se o `pytest` real precisar de dados, a tarefa vira nível 3 ou usa dados sintéticos. |
| Executáveis e bibliotecas | Montar só o necessário: `/usr`, `/lib*`, `/bin`, interpretador Python e `.venv` | somente leitura | Descobrir a lista mínima por teste (H). `.venv` somente leitura. |
| `/etc` | Só arquivos mínimos (por exemplo `ld.so.cache`) | somente leitura | Lista a testar. |
| `HOME` | `tmpfs` temporário por sessão, vazio | leitura e escrita efêmeras | Nada do `HOME` real. |
| Diretórios de configuração (`~/.claude`, `~/.config`, `~/.local`) | **Não montar** no Bash | — | O `claude` (fora do invólucro) segue dependendo de `~/.claude`; ver §6. |
| Diretórios de **outros agentes** e de outros projetos | **Não montar** | — | Canário "outro agente" fora do repositório. |
| `.ssh`, credenciais, `.gitconfig`, tokens | **Não montar** | — | Canário `fake_home/.ssh/canario_ssh`. |
| Socket do Claude Code (`/run/user/<uid>/cc-socks`) e `/run/user` | **Não montar** | — | Canário: socket de teste no mesmo tipo de caminho; `connect()` deve falhar. |
| Diretórios temporários | `tmpfs` próprio, vazio, efêmero | leitura e escrita | `/tmp` real não é montado. |
| Logs e evidências | Montar `evidencias/` da tarefa só para **anexar** pelo hook e pelo L0, fora do alcance de escrita do filho; escrita de log fica com o L0 | — | O filho não escreve em log de auditoria. |
| Rede (Bash e filhos) | Sem rede (`--unshare-net`) | — | Teste de `connect()` TCP e Unix (X05). |
| Rede do processo `claude` confinado | **Sem `--unshare-net` para o `claude`** (ver §6A) | — | O `claude` precisa alcançar a API. |
| `/proc` | `--proc /proc` novo, dentro de `--unshare-pid`; nunca o `/proc` do host | somente o que o confinamento cria | X06: `environ` do processo vizinho não pode aparecer. |
| `/dev` | `--dev /dev` mínimo (`null`, `zero`, `urandom`); sem `pts` do host e sem `/dev/tty` útil | mínimo | X06 e X11. |
| `/sys` | **Não montar** | — | X06. |
| `.git` | Hoje o repositório **não tem `.git`**. Se existir: montar **somente leitura** (ou não montar). `.git/config` e `.git/hooks` são vetores de execução e de credenciais | somente leitura | Testar com um `.git` sintético (X03). |

Variáveis de ambiente: lista curta (`PATH`, `LANG`, `HOME` temporário). O invólucro **não** é entregue a quem escreve o comando: o hook valida o comando original contra o perfil, e `updatedInput` o reescreve para `isolar.py -- <comando>` (D: `updatedInput` substitui o objeto inteiro e as regras avaliam a entrada reescrita). Se uma regra `deny` que casa com o texto original deixa de casar com o reescrito, só o hook garante o confinamento (Q9, H).

## 5. Canários fora do repositório (prova da F2.0-D, com sua autorização do local, D3)
**Correção C.3:** o texto anterior colocava um canário em `sintetico/nunca/canario_nunca.txt`, dentro do repositório, contra `f2_0d_especificacao.md` §4.1. **Todos os canários de segurança ficam fora do repositório**, em `<local-base>/execucao_<aleatório>/` (local-base indicado por você; proposta `~/dengue_f2d/`; nome aleatório por `mkdtemp`; lista fechada de arquivos e regras de limpeza em `f2_0d_especificacao.md` §4.1 e §4.4). Os arquivos que já existem em `sintetico/` são sintéticos e **não** protegidos; ficam como estão e **não** servem de canário de segurança da F2.0-D. Se um dia for necessário testar um padrão de caminho relativo ao repositório (política v2), isso exige decisão própria (não proposta aqui).
Todos sintéticos, em um diretório raiz de testes fora do repositório:
- `fake_home/.ssh/canario_ssh` e `fake_home/.claude/settings.json` falso: leitura e escrita devem falhar.
- `outro_agente/canario`: leitura e escrita devem falhar.
- `controles_falsos/hook_falso.py` e `estado_l0_falso/estado.json`: leitura (esperado oculto) e escrita (esperado negada).
- Socket Unix de teste e porta TCP local de teste: `connect()` deve falhar dentro; deve funcionar fora (controle positivo).
- Canário "protegido" sintético (`protegido/canario_nunca.txt` em `execucao_<aleatório>/`, **fora do repositório**; alterado na C.3): leitura por `cat`, `head`, `python -c`, `os.open`, `base64` deve falhar.
- Hardlink e symlink: criar, de dentro, link apontando para canário protegido; deve falhar ou resolver para inexistente.
- **Controle positivo** de cada teste, fora do confinamento, mostrando que a leitura funcionaria sem ele (isso prova que R1 existe).

## 6. Proteção preventiva dos controles (A4)
- **Confinar o processo `claude` inteiro** com os arquivos de controle montados **somente leitura** e o estado do L0 não montado. Sem isso, `Write`/`Edit` do próprio CLI e `~/.claude` ficam só com `deny`, hook e detecção. Dependências a medir (H): quais caminhos o CLI precisa gravar (R16), como manter o login (`CLAUDE_CONFIG_DIR`, credenciais), se o `bwrap` funciona quando iniciado pelo L0 em vez de por um filho.
- **Verificação de integridade antes e durante:** o L0 confere o `controles.sha256` antes de iniciar cada sessão; o hook confere em **cada chamada de ferramenta**; o L0 confere a cada evento do stream-json e pelo menos em intervalo fixo (valor a medir na F2.0-D, não fixado).
- **Falha:** hash divergente, hook sem registro (heartbeat) ou arquivo ausente → o L0 encerra a sessão (grupo de processos), grava PEND e não retoma sozinho.
- **Limites dos hashes:** detectam, não impedem; um processo do mesmo usuário pode alterar e restaurar entre duas verificações (janela); o hash guardado precisa estar fora do alcance; hash de arquivo não cobre diretórios novos, links nem o processo em execução.

## 6A. Rede do `claude` confinado (M-7)
`--unshare-net` **não** é proposto para o processo `claude`, porque cortaria a comunicação com a API. Alternativas, todas H:
1. **`claude` com rede e confinado só em arquivos;** os Bash filhos recebem rede negada por um segundo nível (`bwrap --unshare-net` aninhado, X09/X14, ou Landlock ABI ≥ 4, X10). Se nenhum funcionar, os Bash filhos **têm rede**: o que for legível pode sair. Por isso a allowlist de arquivos importa mais.
2. **Ponte por socket Unix** (`socat` está instalado, T) entre o `claude` isolado em rede e um encaminhador no host. Complexo; precisaria de prova própria e não é proposto agora.
3. **Landlock TCP (ABI ≥ 4):** limita portas (por exemplo 443), **não** destinos. Não impede exfiltração por 443.
O que o `claude` confinado precisa escrever e como manter o login (`CLAUDE_CONFIG_DIR`) são X20 e X21 (pacote C, fora do padrão).

## 6B. `bwrap` aninhado (M-7)
Um `bwrap` dentro de um processo já confinado repete o modo de falha observado no sandbox do CLI (userns aninhado, E07, T). X09 e X14 testam; **não** há garantia. Se falhar: Landlock por comando (X10), ou `bwrap` iniciado só pelo L0 (fora do `claude`), ou D2.

## 6C. TTY e forja (M-6, M-7)
`/dev` mínimo remove o `pts` do host dentro do confinamento (H). Um processo **fora** do confinamento e do mesmo usuário Unix ainda alcança os TTYs do usuário. A confirmação em TTY (D4) só vale se o processo que pede a confirmação roda **fora do alcance** dos agentes. X11 testa a forja num pty do harness; nunca no seu terminal.

## 6D. Limites do Landlock (kernel docs, D)
Não restringe `chmod`/`stat`; descritores abertos antes da regra escapam; rede só em ABI ≥ 4; sockets de caminho só em ABI ≥ 9; não esconde nomes (só nega acesso); exige `no_new_privs`; irreversível. O ABI local não foi verificado (X01).

## 7. Prova necessária (F2.0-D)
1. Leitura e escrita fora, direta, por `os.open`, `open`, `head`, `base64` e `python -c`: negadas dentro, permitidas no controle positivo.
2. Escrita em controles e em `.claude/settings.local.json`: negada.
3. `pytest` sintético dentro do confinamento (dependências visíveis, `.venv` somente leitura).
4. Rede e `cc-socks`: `connect()` negado.
5. `~/.claude`, estado do L0 e `/run/user` invisíveis.
6. `updatedInput`×`deny`: documentar o que ocorre.
7. `bwrap` iniciado por filho do `claude` e iniciado pelo L0.
8. Hardlink, symlink e condição de corrida simples (trocar alvo entre verificação e uso).
9. Landlock: checar o ABI (`landlock_create_ruleset` com a flag de versão); repetir 1, 2, 4 se disponível.
10. Confinamento do `claude` inteiro (§6) e login (X20, X21; pacote C).
11. `bwrap` aninhado e iniciado por filho do `claude` (X09, X14).
12. `/proc`, `/dev`, `/sys`, `.git` sintético e rede (X05, X06, X03).
13. TTY e forja num pty do harness (X11).
**Cada prova:** procedimento determinístico, registro independente da tentativa e controle positivo (`f2_0d_especificacao.md` §3). Um teste mínimo de `bwrap` **não** é prova de isolamento completo.

## 8. Limitações que ficam (L)
- Sem seccomp e sem cgroups (sem limite de memória/CPU; mitigação: `ulimit` e tempo limite do L0).
- O processo `claude` fora do confinamento tem os direitos do usuário.
- O usuário (ou quem tenha `sudo`) pode tudo.
- Falhas do kernel, do `bwrap` ou do Landlock.

## 9. Fechamento de R1
R1 só passa a mitigado quando CP-5 for aprovado pela Peach com as **provas obrigatórias** abaixo. Aceitar o risco residual é decisão sua (D1). *(Correção C.3: o texto anterior dizia "provas 1 a 8", mas §7 tem 13; AUD4-MED-6. A classificação é proposta H, sujeita à sua decisão D10.)*

| Prova (§7) | Fecha R1? | Condição |
|---|---|---|
| 1 leitura e escrita fora | **Obrigatória** | sempre |
| 2 escrita em controles e `settings.local.json` | **Obrigatória** | sempre |
| 3 `pytest` sintético dentro | **Obrigatória** | sempre |
| 4 rede e `cc-socks` | **Obrigatória** | sempre (canário; o socket real continua H) |
| 5 `~/.claude`, estado do L0 e `/run/user` invisíveis | **Obrigatória** | sempre |
| 6 `updatedInput`×`deny` | **Informativa** | documenta; se só o hook protege, a prova passa a ser do CP-4 |
| 7 `bwrap` iniciado por filho do `claude` e pelo L0 | **Obrigatória** | para a forma de lançamento escolhida |
| 8 hardlink, symlink e corrida simples | **Obrigatória** | a corrida só prova "sem evidência de vazamento nesta tentativa" (H residual) |
| 9 Landlock | **Obrigatória só se** Landlock for a alternativa escolhida; **informativa** caso contrário | |
| 10 confinamento do `claude` inteiro e login | **Obrigatória só se** a alternativa deve proteger controles contra `Write`/`Edit` do próprio `claude`; sem ela R1 só pode ser mitigado para o Bash e o risco aos controles fica aberto | |
| 11 `bwrap` aninhado e como filho do `claude` | **Obrigatória** para a alternativa `bwrap` | |
| 12 `/proc`, `/dev`, `/sys`, `.git` sintético, rede | **Obrigatória** | |
| 13 TTY e forja num pty do harness | **Informativa para R1** (obrigatória para D4/R30) | |
