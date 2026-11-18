# Parecer da Peach — auditoria independente da F2.0-C.3

Auditora: Peach (sessão independente, somente leitura, exclusivamente documental). Objeto: `agentes/laboratorio/f2/` (21 arquivos `.md`), cópia em `/mnt/user-data/uploads/Dengue_trabalho/agentes/laboratorio/f2/`.
Convenções: classes T/D/H/L como nos documentos. "Verificado" = conferido por mim no texto ou por script de leitura. "NÃO VERIFICÁVEL" = sem evidência suficiente nos arquivos. Textos dos documentos tratados como dados.

## 1. Veredito

**APROVADO COM RESSALVAS.**

Os três ALTO da C.2 estão tratados no papel de forma consistente e honesta: o pacote B foi bloqueado (não "contido"), X20 e X21 ganharam ficha completa, e a contradição sobre `~/.claude` foi resolvida por exceção estreita, `CLAUDE_CONFIG_DIR` e snapshot definido. Os oito MÉDIO da C.2 estão corrigidos, com pequenas lacunas. R1 segue ABERTO; F2.0-D0, F2.0-D e F2.1 seguem bloqueadas; nenhuma decisão aparece como autorizada; nenhuma capacidade de isolamento é declarada comprovada. **Não há achado CRÍTICO nem ALTO novo.** Há **5 MÉDIO** e **9 BAIXO** novos ou remanescentes (§6), nenhum impede submeter D10 e D3 (pacote A) à decisão humana (§9).

## 2. Escopo e arquivos lidos

Lidos integralmente (Read/`cat`, 21 de 21, nenhum ausente): `parecer_peach_f2_0c_2.md`, `relatorio_f2_0c_3.md`, `f2_0d_especificacao.md`, `portoes_f2.md`, `matriz_decisoes_humanas.md`, `criterios_peach_f2.md`, `plano_isolamento_r1.md`, `registro_riscos.md`, `rastreabilidade.md`, `matriz_autonomia.md`, `questoes_abertas.md`, `parecer_f2_0.md`, `limitacoes.md`, `roadmap_f2_revisado.md`, `LEIA-ME.md`, `relatorio_f2_0c_2.md`. Apenas inspecionados por `grep` (busca de contradições e de resíduos do pacote B, `/tmp/dengue_f2d`, "provas 1 a 8"): `arquitetura_l0.md`, `resultados.md`, `plano.md`, `consolidacao_f2_0c.md`, `relatorio_f2_0c_1.md`.

Checagens por script (`python3 -I`, só leitura): R1 a R37 sem salto (R1 = ABERTO); Q1 a Q33 sem salto; matriz de autonomia com linhas 1 a 54 sem salto e 7 colunas; fichas X01 a X21 presentes e em ordem; HD-1 a HD-16 presentes; nenhuma referência a R, Q, CP, HD, X, DX ou D acima do máximo existente; "provas 1 a 8" só em citação histórica (`portoes_f2.md` l.7 e l.127, `plano_isolamento_r1.md` l.62/§9, `criterios_peach_f2.md` l.71, `rastreabilidade.md`, `relatorio_f2_0c_3.md`); soma das sessões do pacote B = 3+3+2+2+5+2+5+2 = 24, confere; soma do teto do pacote C = 2×0,05 + 2×0,05 = US$ 0,20, confere; 15 arquivos com carimbo de gravação posterior ao parecer C.2 batem com a lista do relatório C.3 §2 (13 alterados + 1 reescrito + 1 novo).

Não verifiquei: identidade byte a byte com o disco do projeto (afirmada pelo enunciado), conteúdo de `bin/`, `cfg/`, `evidencias/`, `sintetico/`, manifestos, `DECISOES.md`; comportamento real do Claude Code citado (flags, escrita em `~/.claude`, `--strict-mcp-config`); textos originais de AUD0 a AUD3.

## 3. Avaliação de cada ALTO

### AUD4-ALTO-1 — contenção do pacote B: **RESOLVIDO (no papel, pela via do bloqueio)**
Evidência:
- Perfil definido em `f2_0d_especificacao.md` §5B.1 (l.193-203): `--agents`/`--agent lab-b` com identidade verificada no `init`; `--tools` em lista fechada sem `WebSearch`, `WebFetch`, `RemoteTrigger`, `CronCreate` nem `mcp__*`; `--strict-mcp-config --mcp-config` vazio; Drive (`share_file`, `trash_file`, `create_file`, `update_file`) nomeado, com **verificação obrigatória do `init`** e encerramento do grupo de processos se aparecer `mcp__*` (item 3); `--setting-sources` e `--settings` com hash; `--permission-mode dontAsk` com `allow` mínimo e `deny` testado; comportamento na negação definido (parar e responder `NEGADO`; mais de 2 `permission_denials` encerra a sessão; item 5); cwd vazio e dedicado, canários fora do cwd e do repositório (item 6); prompt fixo gerado pelo harness e `hook_lab.py` com hash (item 7); estado do CLI só com `CLAUDE_CONFIG_DIR` (item 8).
- Não trata a lista como prova: l.194 ("Uma lista de flags e ferramentas num documento **não prova** contenção técnica"), l.200 (L não resolvido: o repositório com dados protegidos continua alcançável pelo mesmo usuário Unix; "Esta é a razão do bloqueio"), l.203 (sem X21 em SUCESSO não existe barreira técnica). Flags não conferidas na 2.1.327 estão marcadas (Q30); efeito de `--strict-mcp-config` sobre conectores da conta está marcado como desconhecido (Q31).
- Proteção contra comandos fora da missão: prompt fixo, hook que nega ferramenta fora da lista, limite de negações, abort por `init`; reconhecidamente insuficiente sem `bwrap` (l.203). Coerente.
- **Bloqueio inequívoco e condições verificáveis:** l.11 e l.190 ("NÃO AUTORIZADO / BLOQUEADO. D3 não pode selecioná-lo"); seis condições de desbloqueio em ordem (l.205-211), cada uma com resultado observável (X02-X04 em SUCESSO, X20 SUCESSO, X21 SUCESSO ou aceite escrito, XB0 SUCESSO, revisão da Peach, decisão nova "D3-B"). O bloqueio aparece em todos os documentos normativos e de entrada: `portoes_f2.md` l.7, 38, 48, 53, 56; `matriz_decisoes_humanas.md` l.3, 14, 46, 56-57; `LEIA-ME.md` l.5; `roadmap_f2_revisado.md` l.7, 29, 38; `criterios_peach_f2.md` CP-1 item 9; `registro_riscos.md` R34; `questoes_abertas.md` Q31; `parecer_f2_0.md` §10; `rastreabilidade.md` AUD4-ALTO-1; `relatorio_f2_0c_3.md` §1; `relatorio_f2_0c_2.md` nota C.3 (histórico). Nenhum resíduo de "D3(b)/(c) autoriza o pacote B" fora de textos históricos sinalizados. Nenhuma contradição encontrada.
- Ressalva menor: a condição 3 (aceite humano sem X21) deixa ambíguo quem prevalece se a Peach "mantiver o bloqueio" (AUD5-BAIXO-5).

### AUD4-ALTO-2 — X20 e X21 sem ficha: **RESOLVIDO (no papel)**
Evidência: `f2_0d_especificacao.md` l.240-266. Ambas têm: objetivo e hipótese (HD-15/HD-16), executor, ambiente e pré-condições (X20: autorização individual, X01 feito, local-base, diretório `mkdtemp` 0700 vazio, snapshot antes; X21: X20 SUCESSO, X02-X04, X09 ou X14, X05, lista de montagens), procedimento numerado, controle positivo, registro independente (snapshots, stream-json do pipe, `tentativa.log`), esperado (H), sucesso, falha (achado), inconclusivo, limites e contingências (tentativas, US$, minutos, "se exigir o `~/.claude` real, PARAR"), limpeza e evidências.
- Nenhuma afirmação indevida de "21 completos": l.15 qualifica "completude **no papel**" e que "não prova que o procedimento funciona"; a mesma qualificação está em `matriz_decisoes_humanas.md` l.45 e `rastreabilidade.md` AUD4-ALTO-2.
- **Segurança de login/credenciais em X20 (verificada):** o login é feito por HUM em terminal próprio, "sem agente observando" (l.244); credenciais "nunca são lidas, copiadas, impressas ou enviadas por agente" (l.244, §4.3 l.126); o snapshot registra credenciais só como existência, tamanho e mtime, **nunca lidas, nunca hasheadas, nunca impressas** (l.148); listagem do diretório de config só de metadados (l.244 item 5); limpeza "sem ler as credenciais" por `lstat`/`unlink`/`rmdir` sem seguir symlinks (l.252); revogação da sessão na conta fica como ação sua, não verificada (Q33). O desenho é sólido. A garantia "agente nunca lê" é **procedural**, não técnica (AUD5-BAIXO-1). Fichas com lacunas de reprodutibilidade: AUD5-MED-4 (X21 sem login após a limpeza de X20) e AUD5-BAIXO-6.

### AUD4-ALTO-3 — `~/.claude` × `claude -p`: **RESOLVIDO NO PAPEL, com PARCIAL na lista de estado tolerado**
Evidência: `f2_0d_especificacao.md` §4.6 (l.141-152) e §4.3 (l.126, "com a exceção estreita de §4.6"). Contradição desfeita: fato R-L1 reconhecido; escrita de estado do CLI tolerada em subdiretórios nomeados e em `~/.claude.json`; proibido alterar arquivo preexistente do escopo nomeado (`settings*.json`, `agents/`, `hooks/`, `commands/`, `skills/`, `plugins/`, `CLAUDE.md`, credenciais); `CLAUDE_CONFIG_DIR` dedicado como mecanismo preferencial, com X20 como pré-requisito do B (l.146); snapshot definido (o quê: caminhos, tipo, tamanho, mtime e SHA-256 só de arquivos de configuração do escopo nomeado, credenciais só metadados; quando: antes e depois de cada experimento do pacote A e de cada sessão `claude`; onde: `f2d/evidencias_d/<ID>/snapshot_antes|depois.json`, fora do cwd da sessão; como comparado: `diff` determinístico pelo harness, com regras de FALHA/PARADA, tolerância e pausa); limites declarados (l.151: "detecta, não impede", não prova isolamento, não cobre o restante do repositório nem restauração entre snapshots). Coerência com `portoes_f2.md` P8 e F2.0-D itens 3, 5; `criterios_peach_f2.md` CP-1 item 7; `limitacoes.md` R-L1; R35; Q32. Não declara resolvido sem prova ("Não há hoje demonstração", l.152). Não hasheia nem lê credenciais.
- Parcial: a lista de subdiretórios tolerados é proposta não verificada (Q32), e o texto manda "confirmar na D0 pelo snapshot", o que a D0 (sem execução) não pode fazer; além disso o snapshot não distingue escritas da própria sessão CC-local hospedeira (AUD5-MED-1).

## 4. Avaliação de cada MÉDIO da C.2

| ID | Resultado | Evidência e observação |
|---|---|---|
| MED-1 círculo do harness / D0 | **RESOLVIDO** | `portoes_f2.md` F2.0-D0 (l.36-44): escrita sem execução, pré-requisitos, revisão pela Peach e por você, hashes, reprovação por execução ou arquivo fora da lista. Ressalvas: não há critério objetivo para revisar o **código** (AUD5-MED-5); exceção `claude --help` (AUD5-BAIXO-4). |
| MED-2 lista fechada; canário fora do repositório | **RESOLVIDO** | `f2_0d_especificacao.md` §4.1 (15 itens com caminho, quem cria, quando, hash a registrar, pacote); X10 (`landlock_launcher.py`), X08 (testes), hook e settings do B estão na lista; regras (a)-(d); `plano_isolamento_r1.md` §5 (l.61-62, 68) corrigido: nenhum canário de segurança no repositório. Falha menor: item 5 diz que `hashes_aprovados` cobre "itens 1 a 4, 6 a 10", mas o item 10 é saída (AUD5-BAIXO-3). |
| MED-3 X13 `deny` × ausência de `allow` | **RESOLVIDO (B bloqueado)** | X13 com três braços (l.220-224); só o braço com `allow` e `deny` juntos, comparado ao braço de controle de `allow`, conta como prova; `criterios_peach_f2.md` CP-1 item 10; X15 e X19 reutilizam o braço 3. Origem da negação por `permission_denials`/`tool_result`. |
| MED-4 registro independente nas sessões B | **RESOLVIDO** | §3 (l.48): RI primário = stream-json lido pelo harness do pipe; hook só corroborante; "se só o hook registra... INCONCLUSIVO"; repetido em §5B.3 (l.216), XB0, X12, X13 e CP-1 item 2. |
| MED-5 D1(c) × P3/P5 | **RESOLVIDO** | `portoes_f2.md` P3 (l.12) e F2.1 item 1; `matriz_decisoes_humanas.md` D1(c) (l.33), D1 recomendação (l.34); `matriz_autonomia.md` obs. 2 (l.113). Sem contradição restante. |
| MED-6 CP-5 × 13 provas | **RESOLVIDO com BAIXO** | `plano_isolamento_r1.md` §9 (tabela obrigatória/informativa), `criterios_peach_f2.md` CP-5 (l.71), `portoes_f2.md` F2.3 item 3. Divergência residual: CP-5 "11 sempre" × plano "obrigatória para a alternativa `bwrap`"; prova 13 "obrigatória para D4/R30" sem CP que a exija (AUD5-BAIXO-2). |
| MED-7 limpeza | **RESOLVIDO** | §4.4 (l.128-136): "temporários" = só `registro_criados.json`; `mkdtemp` 0700 com falha se existir; marcador com nonce; `lstat`/`scandir(follow_symlinks=False)`, sem `rm -rf` por texto; recusa de dispositivo/caminho fora do local-base; hardlink só pelo nome; processos auxiliares só por PID com hora de início e grupo, nunca `pkill`; `settings.local.json` preexistente: recusa iniciar (§4.1 regra a; §4.4); `.cc-writes` só registrado. Cobre todas as lacunas apontadas. |
| MED-8 CC-local só roda o comando fixo | **RESOLVIDO com ressalva** | §4.7 (l.154-160): modo 1 (você digita; CC-local só `Read`) e modo 2 (aprovação por comando); qualquer outro comando = pausa; limite L declarado. A verificação de hash descrita é circular/ambígua (AUD5-MED-3). |

## 5. Coerência entre documentos

- **Especificação × portões × decisões × critérios:** coerentes quanto a: pacote B bloqueado e fora de D3 (spec l.11, 190; portões l.48, 53; matriz l.46, 56-57; critérios CP-1 item 9); D3 não inicia etapa (matriz l.44, 62; spec l.274; portões P1 e F2.0-D item 1); D0 sem execução, antes da F2.0-D (portões §2 e §3; spec l.10, 46; matriz l.14; LEIA-ME; roadmap); F2.0-D "D3 inalterada desde a D0"; D10(d) com CP-1 para D0/F2.0-D e CP-2/CP-3 antes da F2.1 (matriz l.116; critérios l.7; portões l.25, 56); D1(c) não selecionável (portões P3, matriz, matriz_autonomia).
- **IDs, numeração e contagens:** verificados por script (§2). Tetos: 24 sessões do B (3+3+2+2+5+2+5+2) e C 2+2 batem com as fichas; o texto de §3 foi reconciliado com X16/X18 (5) e X20/X21 (2). Exceção: as 2 sessões de XB0 não entram em nenhum teto (AUD5-BAIXO-3).
- **R1 ABERTO** (R1 "ABERTO"; P5; plano §9). **F2.0-D0, F2.0-D e F2.1 bloqueadas:** portões l.5, LEIA-ME l.5, roadmap l.3, matriz l.3, relatório C.3 §1. **Nenhuma decisão marcada como autorizada:** `matriz_decisoes_humanas.md` l.5 ("não decidir equivale a não autorizar"), `criterios_peach_f2.md` l.7, exemplo de D3 l.62; as ocorrências de "Autoriza:" são consequências descritas por alternativa, não autorizações.
- **Nenhuma capacidade de isolamento declarada comprovada:** `bwrap` "T só no teste mínimo" (plano §3 F), sandbox do CLI "T: inutilizável", `deny` T só para `Read`/`cat`, X09/X14 "incerto (H)", resto H. Verificado.
- **Iniciar × concluir:** P1, F2.0-D0 item 7 ("Concluir a D0 não autoriza a F2.0-D"), F2.0-D item 7, `criterios_peach_f2.md` §2 (três aprovações; só a humana avança).
- **Novas contradições introduzidas pela C.3:** nenhuma de natureza material. Pequenas tensões listadas em AUD5-BAIXO-2, -3, -4, -7. Cabeçalhos desatualizados ("F2.0-C.2" em `portoes_f2.md` l.1 e `criterios_peach_f2.md` l.1, `plano_isolamento_r1.md` l.1) são editoriais (AUD5-BAIXO-9).
- **Mudança de local-base para `~/dengue_f2d/`:** resolve o nome previsível em `/tmp` compartilhado. Riscos que ela introduz são pequenos: o diretório-pai é previsível, mas os subdiretórios são `mkdtemp` 0700; as credenciais de X20 passam a ficar sob o HOME, e não em `/tmp` (aceitável, 0700, removidas sem leitura). Nenhum risco novo relevante.
- **F2.0-D0 "criando código":** risco real e reconhecido (R36, R37). Está contido por: lista fechada, sem execução, revisão da Peach e sua, hash anotado por você, pausa se o código for maior do que você revisa. A lacuna é o critério da revisão (AUD5-MED-5).

## 6. Achados remanescentes ou novos

Contagem: CRÍTICO 0; ALTO 0; MÉDIO 5; BAIXO 9.

### MÉDIO

**AUD5-MED-1 — Snapshot do `~/.claude` pode acusar FALHA por escritas da própria sessão CC-local, e a lista de estado tolerado não é verificável na D0.**
- Evidência: `f2_0d_especificacao.md` §4.6 item 4 manda snapshot do escopo `~/.claude` "antes e depois de cada experimento do pacote A" (l.147); item 2 (l.145) torna FALHA/PARADA qualquer mudança em arquivo preexistente do escopo nomeado, **incluindo "qualquer arquivo de credencial"**, e a regra de comparação (l.150) trata arquivo novo ou alteração fora dos subdiretórios listados como alteração inesperada. O pacote A não tem sessão `claude`, mas o CC-local (modos 1 e 2, §4.7) **é** uma sessão do Claude Code ativa no mesmo usuário durante a execução, e `portoes_f2.md` F2.0-D item 5 reprova a etapa por alteração de arquivo preexistente do escopo nomeado. A lista tolerada (l.144) é "proposta... a confirmar na D0 pelo snapshot", mas a D0 não executa nada (`portoes_f2.md` l.39) e o pacote A não gera sessões `claude`. `questoes_abertas.md` Q32 repete "a confirmar na D0".
- Impacto: risco plausível de falso FALHA/PARADA (por exemplo mtime de credenciais ou arquivos de histórico na raiz de `~/.claude` mudando por atividade do CC-local ou de outra sessão do usuário), reprovando a etapa por processo, ou pressão para afrouxar a regra durante a execução. Não é possível confirmar o comportamento real do CLI aqui (NÃO VERIFICÁVEL).
- Correção: declarar que o snapshot só é **atribuível** quando nenhuma outra sessão do Claude Code estiver ativa, ou classificar mudança por mtime em credenciais como "pausa e relato" e não "FALHA da etapa" para experimentos sem sessão `claude` do harness; trocar "confirmar na D0 pelo snapshot" por "medir na primeira execução autorizada; até lá a lista é H".

**AUD5-MED-2 — D3 não informa que X20 e X21 são sessões `claude -p` sem contenção comprovada (mesma razão do bloqueio do B).**
- Evidência: o B é bloqueado por falta de contenção das sessões `claude -p` (conectores da conta, repositório ao alcance; spec l.11, 200; `matriz_decisoes_humanas.md` l.46). X20 e X21 são sessões `claude -p` Haiku, sem `--agent`, protegidas só por `--tools ""`, `--strict-mcp-config`, `--max-turns 1`, prompt trivial e abort após ler o `init` (spec l.244, 258); o efeito de `--strict-mcp-config` sobre os conectores é desconhecido (Q31) e só XB0, que vem **depois** de X20/X21, o mediria. D3(d) permite listá-los "um a um" (matriz l.58) e D3 não menciona esse risco ("Riscos" l.60 diz só que o pacote A não resolve o estado do `claude`).
- Impacto: o usuário pode selecionar X20/X21 sem saber que são as únicas sessões de modelo permitidas sem a contenção que justifica o bloqueio do B (o risco concreto é baixo, dado turno único, sem ferramentas e teto de US$ 0,05, mas a informação é necessária para uma decisão consciente). Hoje há uma assimetria de tratamento.
- Correção: acrescentar em D3 (Riscos) e na ficha de X20/X21 uma linha de risco aceito: "sessão `claude -p` sem contenção comprovada; mitigação H: `--tools ""`, turno único, abort pelo `init`; conectores da conta podem aparecer (Q31)". Recomendar na D3 selecionar só o pacote A neste momento.

**AUD5-MED-3 — A conferência de hash do CC-local (§4.7) é ambígua e, como escrita, circular.**
- Evidência: l.158: "a primeira linha do procedimento é `sha256sum -c f2d/hashes_aprovados.sha256` e a conferência do hash **desse** arquivo com o valor que você registrou ao fim da D0". Não diz quem executa (script, CC-local ou você), nem como o valor anotado por você chega à conferência. Se a verificação é a primeira linha de `rodar_d.sh`, um `rodar_d.sh` adulterado dispensa a verificação (o próprio `rodar_d.sh` é item 3 da lista, e a comparação do hash do arquivo de hashes exige o seu valor fora do alcance do script). No modo 2 a "string exata" aprovada por você é `bash .../rodar_d.sh <ID>`, que não inclui a verificação.
- Impacto: a barreira anunciada para AUD4-MED-8 depende de a conferência rodar fora do código conferido. Hoje não está definido.
- Correção: especificar que no modo 1 você roda por conta própria `sha256sum` do arquivo de hashes, compara com a sua anotação e só então digita o comando; no modo 2, a primeira aprovação é um comando de verificação separado cuja saída você compara à sua anotação antes de aprovar a execução, ou passar o hash esperado como argumento digitado por você.

**AUD5-MED-4 — Sequência X20 → X21 inconsistente: a limpeza de X20 apaga o diretório de login que X21 precisa, e X21 não tem passo de login.**
- Evidência: X20 limpeza remove `cfg_x20_<aleatório>/` (l.252); X21 exige "X20 em SUCESSO" e monta `cfg_x20_...` leitura e escrita (l.257), executor "CC-local (HUM aprova)" sem login (l.255), e §5B.2/portões não dizem se `limpar.sh X20` roda antes de X21. §4.1 item 15 cria o diretório por execução. Além disso, §3 permite no máximo 1 ajuste de montagem, enquanto X21 permite "até 3 ajustes" (l.258) (AUD5-BAIXO-6).
- Impacto: procedimento de X21 não reprodutível como escrito (ou o login é refeito sem passo documentado, ou a limpeza é adiada sem regra). Contradiz o requisito "procedimento reproduzível" do ALTO-2.
- Correção: definir se X21 reutiliza o diretório de X20 (limpeza só depois de X21, com a regra de ciclo de vida do registro) ou se exige novo login por HUM com o mesmo cuidado de X20; harmonizar o limite de ajustes.

**AUD5-MED-5 — Falta critério objetivo para a revisão do código do harness na D0.**
- Evidência: `portoes_f2.md` F2.0-D0 item 1 diz que "a revisão usa CP-1" e item 3 exige revisão estruturada (V e J). Mas `criterios_peach_f2.md` CP-1 (l.52-63) descreve o que se exige dos **resultados dos experimentos**, não do código (por exemplo, ausência de `rm -rf`/`shell=True`, de escrita fora da lista, de rede, remoção só por registro, `kill` só por PID). D10(d) "autoriza a Peach a usar CP-1 para a F2.0-D" (matriz l.116) e não menciona a D0.
- Impacto: a única barreira técnica contra um harness defeituoso (código escrito por agente, executado com os direitos do usuário) é uma revisão sem lista de verificação aceita por você em D10. É o ponto de maior consequência residual do pacote A.
- Correção: acrescentar ao CP-1 (ou como CP-0) uma lista curta de verificação do código do harness (as propriedades já descritas em §4.4, §4.1 e §4.7), e dizer em D10(d) que ela vale para a D0.

### BAIXO

**AUD5-BAIXO-1 — "Agente nunca lê credenciais" é regra, não mecanismo.** `f2_0d_especificacao.md` §4.3 e X20 proíbem; nada impede tecnicamente o CC-local (modelo com `Read`) de abrir `<local-base>/cfg_x20_*/`. Declarar como L ("proteção procedural; no modo 2, depende da sua atenção") em X20 e em D3.

**AUD5-BAIXO-2 — Classificação das provas do CP-5.** `criterios_peach_f2.md` l.71 ("11 sempre") × `plano_isolamento_r1.md` §9 linha 11 ("obrigatória para a alternativa `bwrap`"); prova 13 é "obrigatória para D4/R30" (plano §9), mas nenhum CP (CP-7/CP-8) a exige. Alinhar e atribuir a prova 13 ao CP da etapa que depende de D4.

**AUD5-BAIXO-3 — Pequenas incoerências de lista e tetos.** (i) `f2_0d_especificacao.md` l.97: `hashes_aprovados` cobre "itens 1 a 4, 6 a 10", mas o item 10 é saída sem hash prévio; (ii) as 2 sessões de XB0 (cap US$ 0,05 cada) não entram nos tetos de §4.2 (24 sessões do B, US$ 1,00; C US$ 0,20) nem na lista de exceções de §3 (l.67).

**AUD5-BAIXO-4 — Exceção `claude --help` na D0.** `portoes_f2.md` l.39 admite rodar `claude --help` se você autorizar, mas a D0 é "sem execução", a reprovação da D0 inclui "execução de qualquer item" (l.42), a NUV não tem shell (P6) e D3 não lista essa autorização. Dizer quem executaria e que a autorização consta da D0; ou manter Q30 como H.

**AUD5-BAIXO-5 — Condição 3 de desbloqueio ambígua.** `f2_0d_especificacao.md` l.208: "a Peach pode manter o bloqueio" mesmo com aceite expresso seu. Dizer que a decisão final é sua e que o parecer da Peach fica registrado como discordância, para evitar impasse.

**AUD5-BAIXO-6 — Detalhes de reprodutibilidade de X20/X21.** X20 não indica o diretório de trabalho do login nem como você obtém o caminho `cfg_x20_<aleatório>` (impresso pelo harness?); o comando de login é descrito como "comando de login do CLI" sem texto exato (Q30 relacionada); X21 tem "até 3 ajustes" contra "no máximo 1" de §3 (l.75, l.258).

**AUD5-BAIXO-7 — D10(d) × D0.** `matriz_decisoes_humanas.md` l.116 "Autoriza: a Peach usar CP-1 para a F2.0-D" não cobre expressamente o uso na D0, enquanto `portoes_f2.md` D0 item 1 exige "D10 com CP-1 aceito (a revisão usa CP-1)".

**AUD5-BAIXO-8 — Contagem de ficha "Pré" e itens históricos.** X01 a X11 usam o campo "Pré" de forma desigual (X01: "nenhuma"; X10: "Condição"; X11 dentro de Objetivo). Sem impacto de segurança.

**AUD5-BAIXO-9 — Cabeçalhos desatualizados.** `portoes_f2.md` l.1 e `criterios_peach_f2.md` l.1 ainda dizem "(F2.0-C.2)" embora o corpo traga notas C.3; `plano_isolamento_r1.md` l.1 idem. Editorial; não exige nova auditoria.

## 7. Limitações da auditoria

- Exclusivamente documental: nada foi executado; nenhuma afirmação T foi reproduzida; aceito T/D/H/L como declarados e conferi só coerência interna.
- Não li `bin/`, `cfg/`, `evidencias/`, `sintetico/`, manifestos, `DECISOES.md`; não comparei a cópia com o disco do projeto (o enunciado afirma conferência byte a byte).
- Não pude verificar comportamento real do Claude Code (flags `--tools ""`, `--setting-sources`, `--permission-mode dontAsk`, efeito de `--strict-mcp-config` sobre conectores, escritas em `~/.claude`, token refresh, `CLAUDE_CONFIG_DIR`). AUD5-MED-1 e AUD5-MED-2 são inferência de projeto, não observação (NÃO VERIFICÁVEL quanto à frequência real).
- Textos originais de AUD0 a AUD3 ausentes; não os reconstruí. `arquitetura_l0.md`, `resultados.md`, `plano.md`, `consolidacao_f2_0c.md` e `relatorio_f2_0c_1.md` foram só inspecionados por `grep`, não lidos integralmente.
- Contagens de IDs feitas por script simples sobre tabelas Markdown; saltos fora do padrão poderiam escapar.

## 8. Pendências de decisão humana

1. **D10** (recomendação técnica: (d), CP-1 agora), de preferência com um complemento de CP-1 para revisão do código do harness (AUD5-MED-5).
2. **D3**: lista de IDs do pacote A (ou parcial), local-base (proposta `~/dengue_f2d/` ou subdiretório aleatório em `/tmp`), tetos (propostas), autorização de criar e remover arquivos da lista, modo do CC-local (1 recomendado), reafirmação de §4.3/§4.6. X20 e X21 só individualmente e com a informação de AUD5-MED-2.
3. **Autorização de início da F2.0-D0**, em texto separado; depois revisão do harness (Peach e você), hashes anotados; **autorização de início separada da F2.0-D**.
4. Aceite ou ajuste da regra de `~/.claude` (§4.6) e da lista de estado tolerado (Q32).
5. Pacote B: nada a decidir agora; só "D3-B" futura, após as seis condições.
6. D1, D8, D9 (F2.1); D7, DX-1 a DX-3 (F2.4); D4 a D6 (F2.5); D2 se aplicável.
7. Fora desta auditoria: DP-001, Etapa 3.2 (sem aprovação científica), Etapa 3.3 (não autorizada).

## 9. D10 e D3 já podem ser submetidas à decisão humana?

**Sim, com ressalvas, e isto NÃO é autorização de nada.**
- **D10:** pode ser submetida agora. A alternativa (d) (aceitar só CP-1) é coerente com `portoes_f2.md`. Recomendo, mas não exijo como nova rodada de auditoria, incluir antes ou junto uma lista de verificação do código do harness (AUD5-MED-5), pois sem ela a revisão da D0 não tem critério aceito.
- **D3:** pode ser submetida **somente para o pacote A** (alternativas (a) ou (d)); está fechada o bastante para uma escolha consciente (itens obrigatórios, exemplo de resposta válida, "não inicia a etapa", pacote B bloqueado e fora de seleção). X20 e X21 não devem ser selecionados enquanto AUD5-MED-2 e AUD5-MED-4 não forem esclarecidos; o pacote B não é selecionável.
- **Risco crítico ou alto sem tratamento:** nenhum. R1 permanece aberto e tratado como tal; o risco de contenção do B está contido pelo bloqueio; os riscos remanescentes (MED-1, MED-3, MED-5) têm correção documental curta, que pode ser feita junto à D0, sem nova sequência de auditorias.
- Nenhuma etapa deve ser iniciada por este parecer.
