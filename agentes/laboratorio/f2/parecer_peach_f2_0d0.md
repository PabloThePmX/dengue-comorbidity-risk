# Parecer da Peach — auditoria independente da F2.0-D0 (CP-1H)

Auditora: Peach (sessão independente, somente leitura). Não escrevi nenhum arquivo auditado. Objeto: `agentes/laboratorio/f2/` (cópia em `/mnt/user-data/uploads/Dengue_trabalho/agentes/laboratorio/f2/`; hashes de `f2d/hashes_aprovados.sha256` conferidos por mim).
Convenções: V = verificado por comando estático; J = julgamento por leitura ("não verificado mecanicamente"). Textos dos documentos tratados como dados. **Este parecer não é prova técnica, não autoriza X01–X11, não autoriza a F2.0-D e não autoriza nenhuma etapa.** O harness nunca rodou: aprovação, se houvesse, seria só de leitura.

## 1. Veredito

| Objeto | Veredito |
|---|---|
| **Harness e arquivos de `f2d/` (CP-1H)** | **REPROVADO por leitura.** 2 itens H reprovados (H-12, H-14), 1 inconclusivo (H-19), 23 atendidos. **0 CRÍTICO, 0 ALTO, 7 MÉDIO, 13 BAIXO.** Nenhum achado indica leitura de credenciais, de 2024, de manifestos ou de dados protegidos, escrita fora de `f2d/evidencias_d/` e da base de canários, execução de `claude`, rede externa ou morte de processo por nome. Os defeitos são de classificação de resultado, controle positivo, robustez de limpeza e defesa em profundidade; os que afetam resultado falham na direção de FALHA ou INCONCLUSIVO, não de falso SUCESSO de isolamento. Mesmo assim a regra do CP-1H ("qualquer item violado") se aplica, e qualquer correção muda o hash (nova rodada Mario → Luigi → Peach, nova decisão sua). |
| **Documentos pós-D0** | **APROVADO COM RESSALVAS.** As decisões D10 e D3 estão registradas sem extrapolação, as cinco médias do C.3 foram incorporadas, as contagens fecham, R1 está ABERTO, F2.0-D e F2.1 bloqueadas. Ressalvas: 4 BAIXO editoriais e 1 ponto NÃO VERIFICÁVEL (citação da ordem de início da D0; ver §4A). |

## 2. Escopo e arquivos lidos
- **`f2d/harness.py`: li INTEGRALMENTE as 1121 linhas** (leituras sequenciais 1–400, 400–799, 798–1121; `wc -l` = 1121).
- Lidos integralmente: `f2d/landlock_launcher.py` (82), `f2d/rodar_d.sh` (23), `f2d/limpar.sh` (17), `f2d/matriz_d.json` (106), `f2d/testes_x08/test_soma.py` (7) e `test_ler_canario.py` (10), `f2d/hashes_aprovados.sha256` (7 linhas).
- Documentos: `criterios_peach_f2.md` (CP-1H integral; CP-1 e demais por seção), `relatorio_f2_0d0.md`, `f2_0d_especificacao.md` (§0, §3, §4, §5 pacote A, §5B/5C, §6, §9; fichas X12–X19 só quanto a escopo), `portoes_f2.md` (integral), `matriz_decisoes_humanas.md` (integral), `registro_riscos.md` (R18–R40 e nota; contagem R1–R40), `questoes_abertas.md` (Q17–Q36 e seção C; contagem Q1–Q36), `rastreabilidade.md` (§5B AUD5), `parecer_peach_f2_0c_3.md` (§6 e §8 integrais), `LEIA-ME.md`, `roadmap_f2_revisado.md` (integrais), `plano_isolamento_r1.md` §4 e §5.
- Comandos estáticos 1–8 reproduzidos (só leitura; nada do harness foi executado; `ast.parse` em memória; nenhum `__pycache__`; `ls -laR f2d` mostra só os 8 arquivos e `testes_x08/`).

**Saídas dos comandos (resumo):**
1. `sintaxe ok` (4 arquivos .py). 2. `bash -n` ok (2 .sh). 3. `sha256sum` dos 7 arquivos é **idêntico** a `hashes_aprovados.sha256` (diff vazio); `sha256sum hashes_aprovados.sha256` = `d736afa263b7da17d0b90d7d2413aca01dbf5127994c962e0ef4f068e214b315` (igual ao do relatório §4B; **o hash que vale é o que você anotar**). 4. Só 2 ocorrências, ambas comentário: `harness.py:982`, `landlock_launcher.py:9`. 5. Imports: `harness.py:14-33` (exatamente a lista do H-01) e `landlock_launcher.py:14-17`; imports internos dos scripts de sonda em `harness.py:527,547,565,580,598` e, dentro da string do X11, `fcntl` e `termios` (`harness.py:950`; `fcntl` é stdlib mas não está na lista do H-01). 6. `socket`: `24, 565, 573, 575, 762, 765, 770, 895, 896`. 7. X12–X21/XB0: só `harness.py:7, 339 (texto "D7/X17"), 1076`, `rodar_d.sh:17` e lista `recusados` de `matriz_d.json:14-26`. 8. 1121 / 82 / 23 / 17 / 10 / 7 linhas.

## 3. Tabela H-01 a H-26

| Item | Tipo | Resultado | Evidência (arquivo:linha) |
|---|---|---|---|
| H-01 | V | APROVADO | Comando 5; `harness.py:14-33`, `landlock_launcher.py:14-17`. Nota: `fcntl` na sonda X11 (`harness.py:950`) fora da lista nominal, mas stdlib (AUD6-BAIX-12). |
| H-02 | V+J | APROVADO | Comando 4 sem ocorrência real. Todo `Popen` com lista e `shell=False`: `harness.py:375`, `800`. `os.execv` só no launcher (`landlock_launcher.py:78`), finalidade declarada (H-21). |
| H-03 | V+J | APROVADO | Comandos 4 e 6; listeners só `127.0.0.1` porta 0 (`harness.py:762-763`, `896-897`) e Unix em `execucao_*/run_user_falso` (`765-767`); sondas conectam a `127.0.0.1`/socket do harness (`573-575`). `rede=True` de `args_bwrap` nunca é passado. |
| H-04 | V+J | APROVADO | `IDS_A` (`43`), recusa em `1075-1076`, conferência dupla em `matriz_d.json` (`1081-1082`); regex `^X(0[1-9]|1[01])$` em `rodar_d.sh:16`; nenhuma montagem de comando `claude` (grep "claude": só caminhos de snapshot, contagem de sessões e comentários). |
| H-05 | J | APROVADO (ressalvas BAIXO) | Constantes `44-46`; `Popen(start_new_session=True)` (`376`) e `matar_grupo(p.pid)` no estouro (`385-386`). Ressalva: 2º `communicate()` sem prazo; teto total só no início (AUD6-BAIX-2). |
| H-06 | J | APROVADO | `preparar_base` `179-213`: absoluto, sem `..`, HOME ou /tmp, fora do repo e de `~/.claude` (`185-191`), `mkdir 0700` + marcador `O_EXCL|O_NOFOLLOW` (`196-198`), reutilização só com dono, modo, marcador e registro (`205-212`). Ressalva BAIXO (AUD6-BAIX-7). |
| H-07 | J | APROVADO | Todas as escritas: `log` `93-96`, `reg_salvar` `112-117`, snapshots/resultado/tempo `1107-1111` e `limpeza.log` `1020` em `evidencias_d/`; base/`execucao_*` via `os.mkdir`/`mkdtemp`/`O_EXCL` `137,143,196,198,427`; sondas escrevem só em `cpos`/`tarefa`/`fora`/`.git_sintetico` do `execucao_*`. Nenhuma outra. |
| H-08 | J | APROVADO | `snap_repo` parte de `RAIZ_F2` (`289`), não segue symlink (`296`), pula `evidencias_d` e `sessao` (`294`), `NAO_HASHEAR`/`SENSIVEL` no nome (`52`, `300-301`). Nenhum caminho de 2024, `data/` ou manifesto no código (grep). |
| H-09 | J | APROVADO | `snap_claude`: teste de nome sensível em `266` precede qualquer `open` (hash só em `279`, classe `config`); `~/.claude.json` só `lstat` (`245`); credenciais só metadados. |
| H-10 | V+J | APROVADO (MÉDIO registrado) | Sem `rmtree`/`rm -rf`/glob/texto montado (comando 4); `lstat` e `(st_dev,st_ino)` (`1038-1045`), marcador de `dir_exec` conferido (`1024-1031`), `follow_symlinks=False` (`1005`). Ressalva: AUD6-MED-6. |
| H-11 | V+J | APROVADO | `encerrar_processos` `984-998`: PID + `starttime` (`989`) + `pgid` (`991`); `matar_grupo` só se `getpgid==pid` (`352`). Sem `pkill`/`killall`/busca por nome. `inicio_proc` índice 19 correto (campo 22 de `/proc/pid/stat`). |
| **H-12** | J | **REPROVADO** | `x09` (`873-878`): `dentro["rc"] != 0` devolve FALHA mesmo com timeout, `falha_do_harness` (rc `None`) ou confinamento externo que não iniciou; contradiz a regra IN (`f2_0d_especificacao.md:65`). AUD6-MED-1. O restante (`categoria` `395-403`, `veredito` `406-413`, `except Exception` `1099-1100`) está correto. |
| H-13 | J | APROVADO | `INICIO` antes do `Popen` (`372`), `FIM` depois (`390`) ou em falha (`378`), `O_APPEND`+`fsync` (`96-100`) em `evidencias_d/<ID>/tentativa.log`, nunca montado em `args_bwrap`/`args_landlock`. |
| **H-14** | J | **REPROVADO** | Tabela abaixo. X10 `rede_tcp` sem controle positivo (`895-911`); X06 com controle positivo que tende a falhar por truncamento (`579-596`, `388`, `808`). AUD6-MED-2 e AUD6-MED-3. |
| H-15 | V | APROVADO | `secrets.token_hex`: `197`, `428`, `438` (um por canário), `944`, `949`. |
| H-16 | V+J | APROVADO | `os.path.lexists(RAIZ_F2/".claude"/"settings.local.json")` (`1077-1078`), antes de `verificar_hashes` e de qualquer objeto. |
| H-17 | J | APROVADO | `verificar_hashes()` em `1079`, antes de `EVID.mkdir` (`1083`) e de qualquer objeto; exige os 7 (`53-54`, `167-169`); confere os outros e o próprio contra o registro (`170-176`); recusa nome fora de `f2d/` (`172`). Nota: `limpar` não a chama (AUD6-BAIX-1). |
| H-18 | J | APROVADO (MÉDIO registrado) | `comparar` `307-344` implementa as três classes e as regras de §4.6; credencial só metadados vira INDETERMINADA (`329-330`); novo/removido com sessão ativa vira INDETERMINADA (`332`). Ressalva: AUD6-MED-4. |
| H-19 | J | **INCONCLUSIVO** | Flags exigidas presentes (`475-478`, `490`); nada de repo, `~/.claude`, `/run/user`, `/sys`, `/tmp` real ou HOME fixos em `481-491`. Mas `prefixos_python` (`464-471`) monta, em leitura, diretórios derivados do ambiente sem guarda; X08 monta `REPO/.venv` (`859-860`). Não é decidível por leitura. AUD6-MED-5. |
| H-20 | V+J | APROVADO | `set -euo pipefail` (`rodar_d.sh:6`, `limpar.sh:5`); trava `SIM` (`8`/`7`); regex de ID (`16`); `limpar.sh` recusa argumentos (`11`); `exec python3 -I -B` (`23`/`17`); nenhum comando além do fixo; sem auto-verificação, sem circularidade. |
| H-21 | J | APROVADO | `landlock_launcher.py`: restringe só a si (`74-77`) e `os.execv` (`78`); falha fechada (`46`, `49`, `65`, `75`, `_syscall` `28-33`); não escreve arquivo, sem rede. Estruturas de ABI e `packed 12 bytes` coerentes com a documentação do kernel (H: comportamento não medido). |
| H-22 | J | APROVADO | `test_soma.py` só aritmética; `test_ler_canario.py:7-10` só leitura (`rb`) do caminho em `F2D_CANARIO_X08`, sem impressão, sem rede, sem escrita. |
| H-23 | V | APROVADO | Comando 4 sem ocorrência real; nenhum `setuid`/`umask`/`chmod`/`chown`/instalação (grep adicional). |
| H-24 | V | APROVADO | Registrado: 1121/82/23/17/10/7 (1260 linhas). Eu consegui ler tudo. **Se o tamanho é revisável por você é decisão sua** (P8). |
| H-25 | V | APROVADO | Comandos 1 e 2. `matriz_d.json` também é JSON válido (`json.load` em memória). |
| H-26 | V | APROVADO | `ls -laR f2d`: só os 7 arquivos listados, `hashes_aprovados.sha256` e `testes_x08/`. |

**Tabela experimento × controle positivo (H-14):**

| Exp. | CPos na ficha | CPos no código | Classificação |
|---|---|---|---|
| X01 | kernel responde | `vals["kernel"]` `688`, `698` | ok (SUCESSO sempre que o kernel é lido; AUD6-BAIX-8) |
| X02 | método fora lê; dentro lê o permitido | `641-649` | ok; `veredito` exige `cpos_dentro` (`411`) |
| X03 | escrita no permitido funciona | cópias em `cpos` (`657-661`) + `escrever_tarefa` (`668`) | ok |
| X04 | escrita fora e leitura do controle dentro | cópia (`718-721`) + `ler_controle` (`730`) | ok (CPos de escrita feito em cópia, para preservar o hash) |
| X05 | `connect` fora aceito e registrado | `793` (`aceitos_fora >= 2`) | ok |
| X06 | leitura do vizinho fora | `808` | **defeituoso** (truncamento; AUD6-MED-3) |
| X07 | links fora leem o nonce | `841` | ok |
| X08 | pytest fora passa os dois | `858`, `865` | ok |
| X09 | comando fora funciona | `873`, `876` | ok no CPos, **classificação errada** (AUD6-MED-1) |
| X10 | métodos sem launcher | leitura/escrita `890-893` ok; **rede `895-911` sem CPos** | **ausente na rede** (AUD6-MED-2) |
| X11 | humano chega ao confirmador | `947` | ok |

## 4. Verificações

### A. Decisões D10 e D3 (registro fiel, sem extrapolação)
- **D10 aceita com complemento:** `matriz_decisoes_humanas.md:5, 16, 34, 132`; `criterios_peach_f2.md:7`; relatório §1. Registra CP-1 + CP-1H, "aprovação documental não é comprovação técnica nem autoriza experimentos". A leitura "só CP-1 e CP-1H" é a mais estreita e vem declarada como ambiguidade (`matriz:16`, Q34), não como extrapolação. **Conforme.**
- **D3 pacote A só autoriza a preparação da D0; não executar X01–X11:** `matriz:17, 56`; `f2_0d_especificacao.md:5, 12`; `portoes_f2.md:5, 7`; `matriz_d.json:3-7`. **Conforme.**
- **Pacote B bloqueado; X20/X21 fora de qualquer pacote e da D3; R1 aberto; nada de isolamento presumido:** `matriz:17, 20, 60`; `f2_0d_especificacao.md:13-14, 5C`; `portoes_f2.md:7`; R1 "ABERTO" (`registro_riscos.md:11`); R38. **Conforme.**
- **Pendentes (D1, D2, D4–D9, DX, D3 itens 2–6; F2.0-D e execução não autorizadas):** `matriz:20, 27, 56`; `LEIA-ME.md:5`; `roadmap:32`; `portoes_f2.md:5`. **Conforme.**
- **Ponto NÃO VERIFICÁVEL por mim:** a linha "F2.0-D0 — Início autorizado na mesma mensagem" com a citação "Conduza a F2.0-D0 para produzir e revisar o harness…" (`matriz:18`). O enunciado que recebi resume só D10 e D3; **não posso confirmar a citação nem que a ordem de iniciar a D0 estava na mesma mensagem das 17:11**. Se o texto original diferir, a linha deve ser corrigida por você. Há também tensão interna leve: `matriz:58` e `f2_0d_especificacao.md:77` dizem que a autorização de início da D0 é "outro texto seu, separado", enquanto o registro a atribui à mesma mensagem; `portoes_f2.md:41` resolve dizendo que a preparação foi autorizada pela mensagem de D10/D3 (consistente com o efeito literal de D3). Ver AUD6-BAIX-13. A ficha F2.0-D0 em `portoes_f2.md:25` ("Autorização de início (texto seu)") é coerente com isso desde que a leitura seja a de `portoes_f2.md:41`.

### B. As cinco correções médias do parecer C.3
| Item | Resultado | Evidência |
|---|---|---|
| MED-1 snapshot esperada/inesperada/indeterminada, sem falso FALHA | **Incorporada** no papel (§4.6, `f2_0d_especificacao.md:153-157`; `rastreabilidade.md:125`) e no código (`harness.py:307-344`, contagem de sessões `216-230`, lista de estado como H `48`). Código com defeito de borda: AUD6-MED-4. |
| MED-2 X20/X21 fora de D3 explícito | **Incorporada**: `f2_0d_especificacao.md:5, 14, 5C`; `matriz:17, 60, 74`; R38; harness recusa (`1075-1076`; `rodar_d.sh:17`; `matriz_d.json:14-26`). |
| MED-3 hash do CC-local sem circularidade | **Incorporada**: `f2_0d_especificacao.md:161-169`; `rodar_d.sh:4-5` não se verifica; você roda `sha256sum` e `-c` antes; harness confere os outros (`156-176`). `limpar` fica sem essa conferência (AUD6-BAIX-1). |
| MED-4 sequência/limpeza X20→X21 sem apagar estado necessário | **Incorporada no papel** (§5C: duas fases, `retido_para_X21`, sem novo login). X20/X21 não existem no código; nada a testar. |
| MED-5 critérios objetivos de revisão do harness | **Incorporada**: CP-1H com H-01 a H-26 (`criterios_peach_f2.md:67-119`). A aplicação é este parecer. |

### C. Itens H-xx
Ver §3. Reprovados: H-12, H-14. Inconclusivo: H-19 (e, **por construção**, o comportamento em execução de `bwrap`, Landlock, pty, listeners e do `claude`, que só a F2.0-D mede).

### D. Busca ativa de defeitos (resumo por tema)
- **Fuga da raiz permitida, symlinks, `..`, TOCTOU:** `preparar_base` resolve o pai com `realpath` e recusa symlink no último componente (`183`, `205`); criação sempre `O_EXCL`/`mkdtemp`. Resíduos de TOCTOU só para o mesmo usuário (AUD6-BAIX-9, AUD6-MED-6).
- **Limpeza que apague algo não criado:** só registro, inode conferido, sem seguir symlink. Falta checar que o caminho registrado está dentro da base (AUD6-MED-6).
- **Credenciais, 2024, manifestos, protegidos:** nenhum acesso (H-08, H-09).
- **`~/.claude` real:** só leitura de metadados e hash de configuração do escopo nomeado; `HOME=/tmp` dentro do `bwrap`; nunca usado como `CLAUDE_CONFIG_DIR`.
- **Escrita fora da área:** nenhuma (H-07).
- **Processos não registrados mortos:** não (H-11).
- **Nonce em logs:** `tentativa.log` registra argv, que não contém nonces de canário; porém `resultado.json` do X07 pode conter conteúdo lido (AUD6-BAIX-4); `stderr[:300]` é logado.
- **Sessões `claude`:** nenhuma; recusa efetiva de X12–X21/XB0 em três camadas (`rodar_d.sh`, `main`, `matriz_d.json`).
- **Falha aberta:** só em X09 (AUD6-MED-1). Demais classificadores exigem `rc==0` e CPos para SUCESSO.
- **Registro independente dentro do alcance do testado:** não; `evidencias_d` nunca é montado nem liberado no Landlock.
- **X01–X11 × fichas:** coerentes, exceto os pontos do §3 (tabela de controle positivo).
- **`matriz_d.json` × harness:** coerente em IDs, pacote A e tetos; os campos `pre` e `tetos_propostos` não são lidos pelo harness (AUD6-BAIX-5).
- **`testes_x08` inofensivos:** sim (H-22).

### E. Coerência dos documentos pós-D0
- Contagens conferidas por script: **R1–R40** sem salto (R1 ABERTO, `registro_riscos.md:11`; R38–R40 ABERTO), **Q1–Q36** sem salto, matriz de autonomia **1–54**, fichas **X01–X21 e XB0** uma vez cada.
- Portões: F2.0-D0 sem execução, F2.0-D e F2.1 bloqueadas, "nenhuma execução (X01 a X21) autorizada" (`portoes_f2.md:5, 7`); `LEIA-ME.md:5` e `roadmap:3, 32` coerentes. Hash do relatório §4B idêntico ao meu.
- Desatualizações editoriais: AUD6-BAIX-11 a 13.

## 5. Achados

### CRÍTICO
Nenhum.

### ALTO
Nenhum.

### MÉDIO

**AUD6-MED-1 — X09 declara FALHA em timeout, falha do harness ou confinamento externo que não iniciou.**
- Evidência: `harness.py:873-878`. `fora["rc"] != 0` → INCONCLUSIVO; senão `"SUCESSO" if dentro["rc"] == 0 else "FALHA"`, sem olhar `dentro["timeout"]` nem `dentro["categoria"]` (rc `None`) e sem controle de que `args_bwrap(c)` sozinho inicia. Regra IN: `f2_0d_especificacao.md:65`.
- Impacto: um HD-5 "refutado" (achado válido) pode ser, na verdade, `bwrap` externo falho ou timeout. Resultado científico errado, não falso isolamento.
- Correção: rodar antes `args_bwrap(c) + [true]` como controle do confinamento externo; só devolver FALHA se esse controle for rc 0, `dentro` não tiver timeout nem `falha_do_harness`; caso contrário INCONCLUSIVO.

**AUD6-MED-2 — X10: `rede_tcp` sem controle positivo.**
- Evidência: `harness.py:895-911`. SUCESSO quando há `j` e nenhum accept, sem uma conexão equivalente fora do Landlock; a ficha X10 manda repetir X05 (com CPos) e usar "mesmos métodos sem launcher" (`f2_0d_especificacao.md:197`).
- Impacto: negativa de rede sem prova de que o `connect` funcionaria; viola H-14.
- Correção: executar `SCRIPT_REDE` sem launcher contra o mesmo listener e exigir `aceitos_fora >= 1` e `tcp_local == "ok"`; senão INCONCLUSIVO.

**AUD6-MED-3 — X06: o controle positivo tende a falhar por truncamento da saída.**
- Evidência: `SCRIPT_PROC` imprime `environ_vizinho` e a lista de todos os PIDs (`harness.py:579-596`); `executar` corta a saída em `MAX_SAIDA=4096` (`388`, `46`); `json_saida(fora)` fica `None` com saída truncada e `cpos_ok` cai (`806-808`).
- Impacto: em host com algumas centenas de processos X06 vira INCONCLUSIVO sistematicamente (falha fechada, mas o experimento deixa de medir).
- Correção: imprimir só `str(pid) in pids` e contagem (ou limitar a lista), e o nonce lido, em vez da listagem completa; ou aceitar `fora["leu"]` e o teste do PID por consulta dirigida.

**AUD6-MED-4 — `comparar` usa a classe da entrada "depois"; arquivo de configuração trocado por symlink ou maior que 1 MiB vira INDETERMINADA.**
- Evidência: `harness.py:317-331` (`ref = ed or ea`; `classe = ref.get("classe")`) e `275-279` (hash só se arquivo regular ≤ 1 MiB). Se `settings.json` preexistente (classe `config`) passa a `link`/`outro`, cai em `329-330` (INDETERMINADA), não em INESPERADA (`323-324`).
- Impacto: enfraquece H-18 ("mudança de configuração preexistente é INESPERADA") em cenário raro ou adversarial; o snapshot só detecta de qualquer forma.
- Correção: se `ea` ou `ed` tem classe `config`, tratar pelo ramo de config (mudança de tipo, ausência de hash ou de classe = INESPERADA).

**AUD6-MED-5 — Montagens derivadas do ambiente sem guarda (`prefixos_python`) e `.venv` do repositório em X08.**
- Evidência: `harness.py:464-471, 488-489, 859-860`. Qualquer diretório derivado de `dirname(dirname(python))`, do `realpath` ou de `sys.base_prefix`, fora de `/`, `/usr`, `/usr/*` e `/lib*`, é montado somente leitura; `achar("python3")` vem do PATH herdado. Python em `~/bin` ou `~/.local` poderia levar HOME inteiro; X08 monta `REPO/.venv`.
- Impacto: pode invalidar a allowlist de H-19 (canários sintéticos legíveis → FALHA espúria de X02/X03/X10) e, no limite, expor ao processo confinado só o que os comandos fixos conseguem ler (canários). Não é leitura de dado protegido pelo harness. H-19 não é decidível por leitura.
- Correção: abortar (INCONCLUSIVO-AMBIENTE) se um prefixo for ancestral de HOME, do repositório, de `~/.claude`, da base ou for `/etc`, `/run`, `/sys`, `/tmp`, `/home`, `/root`; registrar a lista de montagens final em `tentativa.log`; registrar que `REPO/.venv` é montado em X08 (a ficha o prevê).

**AUD6-MED-6 — Limpeza sem checagem de contenção na base e com bloqueio permanente após limpeza parcial.**
- Evidência: `harness.py:1036-1057`. Nenhum teste de que `o["caminho"]` está dentro de uma base registrada (a ficha §4.4 item (3) manda recusar "caminho real fora do local-base", `f2_0d_especificacao.md:134`); só `st_dev` dos filhos (`1006`). Além disso, `1024-1031`: se um `dir_exec` não foi removido (por exemplo sobrou `fora/novo.txt` após FALHA de X03/X10, ou o marcador já foi apagado numa limpeza parcial), a leitura do marcador falha e `limpar()` devolve 4 **antes de remover qualquer coisa**, para sempre. `remover_conteudo` (`1001-1012`) apaga também o que não está no registro dentro de `tarefa` e `cpos` (previsto no §4.4, mas contraria a frase "o que não está no registro não é removido").
- Impacto: registro adulterado ou corrompido apagaria qualquer caminho cujo inode coincida; uma única FALHA com sobra bloqueia toda limpeza automática futura (falha fechada, mas operacionalmente trava).
- Correção: exigir `realpath(caminho)` dentro de uma base registrada e dentro de um `execucao_*` com marcador conferido; tratar marcador ausente de `dir_exec` parcialmente limpo (marcador já limpo) como estado conhecido, não como divergência; documentar o apagamento recursivo de `tarefa`/`cpos`.

**AUD6-MED-7 — X08: o pytest roda fora do confinamento com descoberta de configuração a partir do repositório.**
- Evidência: `harness.py:854-856, 848-850`. `--rootdir` não impede a busca de `pytest.ini`/`pyproject.toml`/`tox.ini` nem de `conftest.py` nos ancestrais de `f2d/testes_x08` (até o repositório); `-o addopts=` só zera `addopts`. A execução usa `REPO/.venv/bin/python` (plugins instalados podem carregar sozinhos). Esses arquivos, se existirem, não estão no hash.
- Impacto: INCONCLUSIVO por leitura (depende do conteúdo do repositório, que não li): o CPos de X08 pode executar código de `conftest`/plugin do repositório, fora do confinamento. Fora do conjunto revisado e hasheado.
- Correção: `-c /dev/null --confcutdir=<raiz_t> --noconftest` (ou equivalente), `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` no ambiente, e copiar os dois testes para `cpos` para o CPos de fora.

### BAIXO
- **AUD6-BAIX-1** — `limpar` não executa `verificar_hashes` nem a trava de `settings.local.json` (`harness.py:1072-1073`); `limpar.sh` também não confere. Documentar que você confere os hashes antes também da limpeza.
- **AUD6-BAIX-2** — Teto: 2º `p.communicate()` sem prazo (`387`); `MAX_SAIDA` corta só depois de bufferizar toda a saída (`388`); `TETO_TOTAL_S` só no início (`1086`) e `gasto` só atualizado na conclusão normal (`1110-1111`), não em exceção; `tempo_total.json` gravado de forma não atômica.
- **AUD6-BAIX-3** — `preparar_base`, snapshots e `montar_cenario` ficam fora do `try` (`1090-1093`, `1103`): exceção ali vira traceback sem `resultado.json` (fecha, mas não vira INCONCLUSIVO registrado).
- **AUD6-BAIX-4** — O X07 grava no `resultado.json` o conteúdo lido (até 512 bytes) dos arquivos de teste (`harness.py:605-606, 624, 838`); em FALHA isso inclui o nonce do canário protegido. É sintético; ainda assim o nonce não deveria ir para o artefato.
- **AUD6-BAIX-5** — `matriz_d.json`: `pre` e `tetos_propostos` não são lidos nem comparados com as constantes (`harness.py:44-46`, `1080-1082`); ordem de pré-requisitos e o limite "1 execução + 1 repetição" (`f2_0d_especificacao.md:69`) não são mecanizados; dependem de você.
- **AUD6-BAIX-6** — `achar()` usa o PATH herdado (`harness.py:457-461`) enquanto os filhos recebem `PATH=/usr/bin:/bin` (`373`); sugerir ancorar em diretórios fixos.
- **AUD6-BAIX-7** — A base e o marcador nunca são removidos por `limpar` (`r["bases"]` não é percorrido); a base aceita qualquer diretório novo sob HOME fora de `~/.claude`/repositório (`185-191`). Documentar.
- **AUD6-BAIX-8** — X01 devolve SUCESSO sempre que o kernel é lido, mesmo com valores `nao_verificado` ou `bwrap` ausente (`harness.py:698`); o snapshot trata `plugins/` como `lista` sem listar conteúdo (`51`, `270-271`); mudança em `.claude/` por criação de `.cc-writes` seria INESPERADA no nível do diretório (`336-341`).
- **AUD6-BAIX-9** — Escritas em `evidencias_d` sem `O_NOFOLLOW`/`O_EXCL` (`96`, `113`, `1107-1111`); leitura do marcador e hash de arquivos seguem symlink (`208`, `279`, `1027`). Só o mesmo usuário poderia explorar; `evidencias_d` não é montada.
- **AUD6-BAIX-10** — X11: o confirmador lê o lado escravo e não registra "origem" dos bytes (`harness.py:926-936`); a escrita no dispositivo (item 1 da ficha) chega ao lado mestre, que ninguém lê, então só `TIOCSTI` é detectável.
- **AUD6-BAIX-11** — `questoes_abertas.md:52` ainda diz "Nenhuma foi decidida", o que contradiz D10 e D3 decididas em 17:11 (`matriz_decisoes_humanas.md:11-20`).
- **AUD6-BAIX-12** — `LEIA-ME.md:10, 41-45`: ordem de leitura ainda começa no relatório C.3; linhas duplicadas de `parecer_peach_f2_0c_2.md` e `_0c_3.md` (a 0c_3 aparece como "só existe se…"); lista de imports do H-01 não cita `fcntl` (script X11, `harness.py:950`).
- **AUD6-BAIX-13** — Registro da ordem de início da D0 (`matriz:18`): citação NÃO VERIFICÁVEL por mim; `matriz:58` e `f2_0d_especificacao.md:77` ainda dizem que o início da D0 é texto separado. Você confirma o texto original e, se necessário, ajusta.

## 6. Limitações
- Nada foi executado. **Harness escrito ≠ harness testado.** Comportamento de `bwrap`, Landlock (ABI, estruturas `ctypes`), pty/`TIOCSTI`, listeners, `pytest` e rede é H (Q36); só a F2.0-D mede.
- Não vi a mensagem original das 17:11; conferi D10/D3 contra o enunciado e contra os próprios documentos.
- Não li o repositório fora de `f2/` (conteúdo de `pytest.ini`/`conftest.py` dos ancestrais: AUD6-MED-7 inconclusivo); não li `bin/`, `cfg/`, `evidencias/`, `sintetico/`, manifestos nem 2024. Não comparei com o disco do projeto (afirmado byte a byte pelo enunciado).
- Meu hash do conjunto confere com `hashes_aprovados.sha256`; isso prova identidade de bytes com o que Luigi hasheou, não correção do código.
- Aplico os severos do C.3 (CRÍTICO/ALTO/MÉDIO/BAIXO); a regra do CP-1H trata item violado como reprovação, independentemente da gravidade.

## 7. Pendências de decisão humana
1. **Corrigir ou aceitar** AUD6-MED-1 a 7 (cada correção muda o hash e exige nova rodada Mario → Luigi → Peach e nova gravação do hash por você); em especial decidir o que fazer com H-19 e AUD6-MED-7 (inconclusivos por leitura).
2. **Ler o código e os documentos você mesmo** (CP-1H, passo 4) e confirmar por escrito; **anotar fora do repositório** o hash de `hashes_aprovados.sha256` da versão final (hoje `d736afa2…b315`, que mudará se houver correção).
3. Decidir se 1260 linhas são revisáveis por você (H-24, P8); caso contrário reduzir o escopo de D3.
4. Confirmar a leitura de D10 (só CP-1 e CP-1H; Q34) e a lista do §4.1 como "locais autorizados" (Q35); confirmar o texto original da ordem de iniciar a D0 (AUD6-BAIX-13).
5. D3 itens 2 a 6 (local-base, tetos, criar/remover, modo do CC-local, reafirmação de §4.3 e §4.6); D1, D2, D4–D9, DX-1 a DX-3; autorização de início separada da F2.0-D. Nada disso foi decidido por mim.

## 8. Os arquivos estão aptos para você decidir se autoriza a F2.0-D? (NÃO é autorização)
- **Harness: NÃO, ainda não.** Por leitura, o CP-1H está **reprovado** em H-12 e H-14 e **inconclusivo** em H-19, sem críticos nem altos. Recomendo corrigir AUD6-MED-1, 2, 3, 5 e 6 (e decidir MED-4 e MED-7) antes de qualquer decisão; refazer a revisão; só então você lê e anota o hash. Mesmo aprovado, o CP-1H seria revisão por leitura e **não** prova de comportamento.
- **Documentos: sim, com ressalvas editoriais** (AUD6-BAIX-11 a 13), que não impedem a decisão.
- **Isto não autoriza a F2.0-D, nem X01–X11, nem qualquer etapa.** R1 continua ABERTO; nenhuma prova de isolamento é presumida.
