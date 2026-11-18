# Parecer da Peach — auditoria independente da F2.0-C.2

Auditora: Peach (sessão independente, somente leitura, exclusivamente documental).
Objeto: `agentes/laboratorio/f2/` (19 arquivos `.md`), cópia lida em `/mnt/user-data/uploads/Dengue_trabalho/agentes/laboratorio/f2/`.
Classes usadas nos documentos: T testado, D documentação, H hipótese, L limitação. Neste parecer: "verificado" = conferido por mim no texto ou por script de leitura; "NÃO VERIFICÁVEL" = não há evidência suficiente nos arquivos.

## 1. Veredito

**APROVADO COM RESSALVAS.**

A F2.0-C.2 tratou, no papel, os nove itens pedidos e os três achados ALTO da C.1 de forma consistente; R1 segue ABERTO e nenhuma capacidade de isolamento foi declarada comprovada; nenhuma decisão aparece como autorizada. Não há achado CRÍTICO. Há **3 achados ALTO** que não invalidam a consolidação documental, mas **devem ser corrigidos antes de o usuário autorizar a F2.0-D** (ver §6 e §9): a especificação do Pacote B não define contenção das sessões `claude -p`; X20 e X21 não têm ficha, embora D3 afirme que todos os 21 têm; e a proibição de alterar `~/.claude` é incompatível com o próprio uso de `claude -p`.

## 2. Escopo efetivamente auditado e arquivos lidos

Todos lidos integralmente com a ferramenta Read (19 de 19, nenhum ausente): `relatorio_f2_0c_2.md`, `portoes_f2.md`, `f2_0d_especificacao.md`, `matriz_decisoes_humanas.md`, `matriz_autonomia.md`, `criterios_peach_f2.md`, `rastreabilidade.md`, `registro_riscos.md`, `plano_isolamento_r1.md`, `arquitetura_l0.md`, `parecer_f2_0.md`, `limitacoes.md`, `resultados.md`, `questoes_abertas.md`, `roadmap_f2_revisado.md`, `LEIA-ME.md`, `plano.md`, `consolidacao_f2_0c.md`, `relatorio_f2_0c_1.md`.

Checagens por script (só leitura, `python3 -I`, `grep`): matriz de autonomia com linhas 1 a 54 sem salto e 7 colunas em todas as linhas (coluna "Hoje (comprovado)" presente em todas); R1 a R33 completos; Q1 a Q29 completos; X01 a X21 e HD-1 a HD-16 presentes; nenhuma referência a R, Q, D, CP, X ou HD acima do máximo existente; "D1–D8" e "A1–A9" só em frases explicativas (`criterios_peach_f2.md` l.5, `consolidacao_f2_0c.md` l.5, `relatorio_f2_0c_1.md`); soma dos limites por experimento do Pacote B (3+3+2+2+5+2+5+2) = 24, confere.

Não verifiquei: a alegação do relatório (§10) de que os 18 arquivos no disco do projeto são idênticos byte a byte (`cmp`) aos mestres, o conteúdo de `bin/`, `cfg/`, `evidencias/`, `sintetico/`, manifestos, `DECISOES.md` (fora da pasta recebida e proibido tocar). Os textos originais de AUD0 a AUD3 não estão na pasta; não os reconstruí.

## 3. Avaliação dos achados da C.1 e dos nove itens da C.2

| Item pedido | Resultado | Evidência |
|---|---|---|
| ALTO-1 D3 fechada | ATENDIDO COM RESSALVA | D3 (`matriz_decisoes_humanas.md` l.40-57) lista 5 itens obrigatórios, pacotes (a)-(e), "Fora do escopo" e exemplo de resposta válida; `f2_0d_especificacao.md` §1-§8. Ressalva: X20/X21 sem ficha (AUD4-ALTO-2); lista de arquivos criáveis incompleta (AUD4-MED-2). |
| ALTO-2 portões | ATENDIDO | `portoes_f2.md` tem 7 campos por etapa de F2.0-D a F2.7, regras P1-P9; roadmap, parecer §6, LEIA-ME e matriz remetem a ele. Contradições residuais pontuais: D1(c) × P3 (AUD4-MED-5) e CP-5 "provas 1 a 8" (AUD4-MED-6). |
| ALTO-3 CP-1 | ATENDIDO COM RESSALVA | `criterios_peach_f2.md` CP-1 (8 mínimos) e `f2_0d_especificacao.md` §3 (cinco categorias, regra IN, contingências, limite de tentativas). "Não tentado" nunca é "negado": verificado em §3 (l.45-53), CP-1 item 4 e nas fichas X12, X13, X15, X17-X19. Ressalva: independência do registro nas sessões B (AUD4-MED-4). |
| M-1 IDs únicos | ATENDIDO | `rastreabilidade.md` §1-§5: prefixos AUD0-AUD3; AUD?-M5/M7 e AUD0-N1..N7/B4/M41/AUD2-B2 marcados NÃO VERIFICÁVEL sem reconstrução. |
| M-2 coluna "Hoje" 51-54 | ATENDIDO | `matriz_autonomia.md` l.106-109; script confirma 54 linhas. |
| M-3 `deny` de edição | ATENDIDO | Linhas 19, 24, 26, 28, 30, 32, 53 marcadas D/H "não testado"; seção 0 e R3 (`registro_riscos.md` l.13) só reconhecem T para `Read`/`cat`. Ressalva menor: R3 usa status "MITIGADO", que não está na legenda (AUD4-BAIXO-1). |
| M-4 `onFailure` | ATENDIDO | `parecer_f2_0.md` §1 item 3, `limitacoes.md` §9, `resultados.md` B6: só `block`/`continue` testados; sem campo = D; X18. |
| M-5 R11/DX-3 | ATENDIDO | R11 -> DX-3 (`registro_riscos.md` l.21; matriz DX-3). |
| M-6 TTY como H | ATENDIDO | `arquitetura_l0.md` §2 item 3 e `plano_isolamento_r1.md` §6C marcam H; X11 em pty do harness, "nunca no seu terminal". |
| M-7 plano de sandbox | ATENDIDO COM RESSALVA | `plano_isolamento_r1.md` §4 (/proc, /dev, /sys, .git, rede), §6A (rede do `claude`), §6B (aninhado), §6C (TTY), §6D (Landlock), §7 (13 provas). Ressalva: CP-5 cita só provas 1-8 (AUD4-MED-6). |
| M-8 estrutural × evidência | ATENDIDO | `criterios_peach_f2.md` §3: critérios V (L0 recalcula) e J (não destravam sozinhos), aceite humano por arquivo. É proposta (L0 inexistente). |
| M-9 DX-1/DX-2 | ATENDIDO | Alternativas e recomendação; DX-2 distinguido de `manifesto.py verificar` (matriz l.122; `arquitetura_l0.md` §4 item 4). |
| M-10 ambiguidades | ATENDIDO | D1 define "perfil de Bash sem interpretadores"; D7, D8(b), D10(b) "só tem efeito depois da lista de ajustes". |
| M-11 bootstrap/D10 | ATENDIDO | `arquitetura_l0.md` §2A passo a passo; D10 pré-requisito da F2.0-D (`portoes_f2.md` l.34 e §4 item 5). |
| Relatório com 9 itens + rastreabilidade | ATENDIDO | `relatorio_f2_0c_2.md` §1-§9 (+§10); `rastreabilidade.md`. O relatório admite explicitamente que a conferência é dele e que a Peach ainda não auditou. Resumo "tudo é corrigido documentalmente" (§3) é frouxo: `rastreabilidade.md` mostra PARCIAL (AUD2-A4, A5, M3, B1, AUD3-B-7) e NÃO VERIFICÁVEL (AUD4-BAIXO-6). |

Itens 8 e 9 da lista de escopo deste parecer:
- **R1 aberto?** Sim. `registro_riscos.md` R1 "ABERTO"; `portoes_f2.md` P5; `plano_isolamento_r1.md` §9. Nenhuma capacidade foi indevidamente declarada comprovada: `bwrap` aparece como "T só no teste mínimo" (plano §3 F), sandbox do CLI como T de falha, `deny` só `Read`/`cat`; tudo mais H/D. Verificado.
- **Nenhuma decisão autorizada implicitamente.** `matriz_decisoes_humanas.md` l.3 ("nenhuma decisão... está autorizada"; "não decidir equivale a não autorizar"); D10(d) autoriza só o uso de CP-1 pela Peach e "nada mais"; DX-2(b) só se escolhida. Exemplo de resposta de D3 exige 5 itens. Ver, porém, ambiguidade textual em AUD4-BAIXO-4.

## 4. Avaliação da especificação X01-X21

Legenda das colunas: Proc = procedimento reproduzível; Exec = executor; Amb = ambiente/canário; CPos = controle positivo; RI = registro independente; S/F/I = critérios de sucesso/falha/inconclusivo; Cont = contingência; Tent = limite de tentativas. "OK" = presente na ficha ou herdado de §3 de forma explícita.

| ID | Proc | Exec | Amb | CPos | RI | S/F/I | Cont | Tent | Observação |
|---|---|---|---|---|---|---|---|---|---|
| X01 | OK | CC-local | OK | fraco (versão do kernel) | padrão | OK (F n/a) | OK | OK | Pura leitura; adequado. |
| X02 | OK | CC-local | canários em local de D3 | OK | padrão | OK | OK | OK | Local do canário "protegido sintético" não é dito (ver AUD4-MED-2). |
| X03 | OK | CC-local | OK | OK | padrão + hash | OK | OK | OK | Cria `.git` sintético? Plano §4 diz testar `.git` em X03; a ficha X03 não menciona. |
| X04 | OK | CC-local | OK | OK | padrão + hash | OK | OK | OK | |
| X05 | OK | CC-local | listener do harness | OK | listener | OK | OK | OK | Boa prova independente (accept registrado). |
| X06 | OK | CC-local | processo vizinho | OK | padrão | OK | OK | OK | Limpeza do processo vizinho não descrita (AUD4-MED-7). |
| X07 | OK | CC-local | OK | OK | padrão | OK | OK | OK | Corrida "simples" não é determinística: ausência de vazamento em uma tentativa não prova negação (AUD4-BAIXO-3). Falta "Pré". |
| X08 | OK | CC-local | OK | OK | padrão | OK | OK | OK | Cria arquivos de teste não listados em §4.1. Falta "Pré". |
| X09 | OK | CC-local | OK | OK | padrão | OK | OK | OK | Falta "Pré". Esperado corretamente tratado como H. |
| X10 | OK | CC-local | OK | OK | padrão | OK | OK | OK | Exige `f2d/landlock_launcher.py` fora da lista de §4.1 (AUD4-MED-2). |
| X11 | OK | CC-local | pty próprio | OK | confirmador registra bytes | OK | OK | OK | Bem delimitado; não usa o terminal real. |
| X12 | parcial | CC-local | sessão B | OK | hook + stream-json | OK | OK | 3 | Modo de permissão e contenção não definidos (AUD4-ALTO-1, AUD4-MED-3). |
| X13 | parcial | CC-local | sessão B | OK | stream-json `tool_result` | OK (por operação) | OK | 3 | Confusão possível: negação por falta de `allow`/modo `-p` não é negação por `deny` (AUD4-MED-3). |
| X14 | OK | CC-local | sessão B | OK (harness fora do `claude`) | hook + tool_result | OK | OK | 2 | |
| X15 | OK | CC-local | cria `settings.local.json` em `f2/.claude/` | OK | hash + hora + hook | OK | OK | 2 | Arquivo preexistente não tratado (AUD4-MED-7). |
| X16 | OK | CC-local | sessão B | OK | `init`/`result` | OK | OK | 1/flag + 1 | Contradiz "máx. 3 sessões por experimento" de §3 (AUD4-BAIXO-2). |
| X17 | parcial | CC-local | diretório novo em `f2d/` | OK | listagem pelo harness | OK | OK | 2 | `.cc-writes` é relativo ao cwd da sessão; limpeza dessa pasta não está em `limpar.sh`. |
| X18 | OK | CC-local | sessão B | OK (`block`) | hook + tool_result | OK | OK | 1/variante + 1 | Mesmo contra-exemplo de contagem de X16. |
| X19 | OK | CC-local | sessão B | OK | hook registra original e reescrito | OK | OK | 2 | |
| X20 | AUSENTE | HUM + CC-local | AUSENTE | AUSENTE | "como §3" | AUSENTE | AUSENTE | AUSENTE | Ficha de duas linhas (`f2_0d_especificacao.md` l.151). |
| X21 | AUSENTE | idem | AUSENTE | AUSENTE | idem | AUSENTE | AUSENTE | AUSENTE | l.152; "pode exigir escrita em `~/.claude` real (proibido)". |

Conclusão: X01-X19 têm ficha utilizável (com os ajustes dos achados); X20 e X21 **não** satisfazem o que `matriz_decisoes_humanas.md` l.42 e o relatório §5 afirmam ("cada um com procedimento determinístico... critérios").

**Tetos (item 4):** claros e rotulados como **propostas, não decididas** (`f2_0d_especificacao.md` §4.2 título e l.90; relatório §5; D3 item 3). A base aritmética de 24 sessões confere. Observações: o custo da própria sessão CC-local (que executa `rodar_d.sh`) não entra no teto de US$ 1,00; e o teto de pausa por rate limit (≥ 0,95) está a 0,01 do uso já observado (≈ 0,94), o que o documento reconhece (l.90). Não é achado de segurança.

**Local do canário e limpeza (item 5):** proposta `/tmp/dengue_f2d/` (alternativa `~/dengue_f2d/`), modo 0700, marcador `.f2d_marker`, nunca `~/.claude`, `/etc`, `/run/user`; `limpar.sh` remove "apenas o que o harness criou", só se marcador e caminho conferem. Isso evita `rm` amplo no desenho, mas há lacunas (AUD4-MED-7): "temporários" indefinido; nome fixo previsível em `/tmp` compartilhado; remoção segura contra symlinks não especificada (X07 cria symlinks e hardlinks dentro da área); processos auxiliares (X05, X06) e arquivos criados pela própria sessão `claude` (`.cc-writes`, transcritos) fora da lista.

## 5. Avaliação dos portões e das decisões

**Portões F2.0-D a F2.7:** em geral coerentes. Tabela §2 e fichas §3 batem quanto a entradas e critérios (F2.1 exige D1, D8, D9, D10; F2.3 exige D1/D2; F2.4 D7, DX-1..3; F2.5 D4-D6; F2.6 D4), e `matriz_decisoes_humanas.md` coluna "Necessária para" corresponde. Roadmap e parecer §6 só resumem e remetem. Inconsistências: AUD4-MED-1 (circularidade do harness), AUD4-MED-5 (D1(c) × P3), AUD4-MED-6 (CP-5 provas 1-8), AUD4-BAIXO-5 (D10(d) versus exigência de D10 na F2.1).

**INICIAR × CONCLUIR:** distinção clara e repetida. P1 ("Nenhuma etapa inicia a seguinte... Só um texto seu, por etapa, autoriza o início"); `criterios_peach_f2.md` §2 (três aprovações; só a humana avança); `portoes_f2.md` campo 7 de cada etapa lista "início" separadamente; matriz l.55 ("autorização de início separada e expressa"). Ressalva textual: D3 emprega "autorizo" no exemplo de resposta válida, o que pode ser lido como autorização de início (AUD4-BAIXO-4).

**EDI × ESH:** P3/P4 definem bem; matriz linhas 7-9, 15, 17, 54 coerentes ("Nível 3 enquanto R1 estiver aberto"). Contraponto em D1(c) (AUD4-MED-5) e na natureza do CC-local (AUD4-MED-8).

**D1-D10, DX-1..3:** todas com pergunta, contexto, alternativas, consequência, recomendação, riscos e dependências; nenhuma marcada autorizada; recomendações estão separadas de escolha. D10(d) e D3(d) são coerentes com os portões.

**Fatos × relatos × propostas × H × decisões (item 11):** bem distinguidos. `resultados.md` B4 e `parecer_f2_0.md` §1-§2 separam T de D/H; `rastreabilidade.md` declara que as auditorias foram "relatos de subagentes" e marca lacunas; tetos e local do canário marcados como proposta; `limitacoes.md` marca seções 1-2 como histórico. Nenhuma atribuição de prova técnica inexistente foi encontrada.

## 6. Achados

Nenhum CRÍTICO. Contagem: ALTO 3, MÉDIO 8, BAIXO 6.

### ALTO

**AUD4-ALTO-1 — Sessões do Pacote B sem contenção definida.**
- Evidência: `f2_0d_especificacao.md` l.132: "Em todos: `--model haiku`, `--max-turns 8`, `--max-budget-usd 0,10`, `--output-format stream-json --verbose`, `--debug-file`." Não há `--agent`, `--tools`, `--strict-mcp-config`, `--setting-sources`, `--no-session-persistence`, modo de permissão, nem reaproveitamento do `hook_guarda.py` que confinava as sessões da F2.0. Os próprios documentos registram que sessões sem `--agent` têm Google Drive (`share_file`, `trash_file`), `WebSearch`, `RemoteTrigger`, `CronCreate` (`resultados.md` B3 E01/E11a; R20) e que o `cwd` fica dentro do repositório com dados protegidos (`registro_riscos.md` R21). `--strict-mcp-config` e `--tools` aparecem só como objeto de teste (X16), não como parte do padrão de segurança.
- Impacto: ao autorizar o Pacote B, o usuário autorizaria sessões de modelo com ferramentas externas e Bash sem confinamento, em pasta do repositório; a segurança dependeria só de prompt fixo e do hook em teste. É o inverso do princípio do próprio projeto (falha fechada, R20). Possível violação de §4.3 por ação do modelo (reprovaria a etapa por processo).
- Correção: especificar um perfil mínimo comum às sessões B (lista fechada de ferramentas, sem conectores, `--setting-sources`, modo de permissão, `deny` sobre dados protegidos reais, cwd dedicado em `f2d/`, guarda de laboratório) e dizer quais flags são exceção por experimento; ou restringir D3(b) até isso estar escrito. Registrar que X16 testa as flags, mas não pode ser pré-condição de si mesmo.

**AUD4-ALTO-2 — X20 e X21 sem ficha, contra a alegação de que os 21 têm todos os elementos.**
- Evidência: `f2_0d_especificacao.md` l.151-152 (X20: "Critérios e RI: como §3"; sem procedimento, ambiente, CPos, esperado, tentativas, contingência próprios; X21 idem). `matriz_decisoes_humanas.md` l.42 e `relatorio_f2_0c_2.md` §5-§6 e `rastreabilidade.md` AUD3-ALTO-3 ("CORRIGIDO-DOC") afirmam que todos os 21 têm critérios. D3(c) autorizaria ambos.
- Impacto: AUD3-ALTO-3 não está plenamente fechado para 2 dos 21. O usuário poderia autorizar login novo e credenciais em diretório temporário (X20) e "confinar o `claude`" (X21, que o texto diz poder exigir escrita em `~/.claude` real, proibida) sem procedimento reprodutível nem critérios de sucesso/falha.
- Correção: ou completar as fichas (procedimento, local das credenciais, limpeza segura de credenciais, CPos, S/F/I, tentativas, parada se exigir `~/.claude`), ou retirar X20/X21 de D3 e da contagem "21 experimentos" e declarar HD-15/HD-16 como não especificadas.

**AUD4-ALTO-3 — Proibição de alterar `~/.claude` incompatível com `claude -p`.**
- Evidência: §4.3 (l.93) proíbe "Alterar `~/.claude` real"; X15 repete "Nunca se altera `~/.claude`"; o cabeçalho do Pacote B diz "sem tocar `~/.claude`" (l.131). Mas `limitacoes.md` R-L1 (l.35) registra: "`claude -p` grava estado em `~/.claude` (histórico, telemetria local), mesmo com `--no-session-persistence`. É uma escrita global inevitável." CP-1 item 7 e `portoes_f2.md` F2.0-D item 3 exigem "snapshots sem alteração fora da área". `CLAUDE_CONFIG_DIR` (X20) está no Pacote C, excluído por padrão. Não se define o que é o "snapshot" da F2.0-D (R24 diz que o snapshot atual ignora esses locais).
- Impacto: executar qualquer sessão do Pacote B viola, por construção, uma proibição cuja violação "reprova a etapa" (`portoes_f2.md` F2.0-D item 5), ou obriga o auditor a ignorar a regra em silêncio. Decisão humana D3 seria tomada sobre texto contraditório.
- Correção: reconhecer a exceção explícita ("escrita de estado do próprio CLI em `~/.claude`, inevitável, não considerada violação; proibido: alterar `settings.json`, `agents/`, credenciais, hooks"), definir o snapshot (o que é comparado, onde) e levar D3(b) a mencionar isso como risco aceito; ou exigir X20 antes do Pacote B.

### MÉDIO

**AUD4-MED-1 — Circularidade: o harness é pré-requisito da F2.0-D, mas escrevê-lo só é permitido dentro dela.**
- Evidência: `portoes_f2.md` F2.0-D item 1 ("harness e especificação revisados pela Peach... e lidos por você, com hash registrado") e item 2 ("NUV grava scripts e documentos em `f2/` e `f2d/`" como atividade permitida da etapa). `f2d/` não existe. Nenhuma etapa ou decisão autoriza escrever o harness antes. Q29 só lista "quem revisa".
- Impacto: pré-requisito não satisfazível dentro das regras (P1, P9). Risco de escrita informal fora do portão.
- Correção: declarar uma subetapa de redação do harness (autorizada em D3 ou em decisão própria, sem execução) e quem a revisa; o hash do que for revisado deve ficar registrado antes do início.

**AUD4-MED-2 — Lista de arquivos criáveis (§4.1) incompleta e canário "no repositório".**
- Evidência: §4.1 enumera `harness.py`, `matriz_d.json`, `rodar_d.sh`, `limpar.sh`, `evidencias_d/`, `resultados_d.md`, `settings.local.json` e diz "Nada mais pode ser criado". Mas X10 exige `f2d/landlock_launcher.py`; D3(b) cita "seu hook de laboratório"; X12/X13/X18/X19 precisam de hooks e settings de teste; X08 precisa de arquivos de teste. `plano_isolamento_r1.md` §5 (l.67) prevê canário em `sintetico/nunca/canario_nunca.txt` (dentro do repositório, fora de `f2/`), contra §4.1 ("Fora do repositório (canários)"; "Nada fora de `agentes/laboratorio/f2/`").
- Impacto: ou experimentos válidos ficam inexecutáveis, ou serão executados criando arquivos "não autorizados" (P9). O auditor não tem lista para conferir.
- Correção: lista fechada de todos os artefatos (nomes, caminhos, hash esperado) e alinhamento do plano de isolamento com §4.1.

**AUD4-MED-3 — Modo de permissão das sessões B não definido (confusão entre `deny` e ausência de `allow`).**
- Evidência: fichas X12-X19 não indicam `permissionMode`/`allow`. Em `claude -p` sem `allow` e sem modo, ferramentas que pedem permissão são negadas por falta de permissão. Em X13, a "negação" de `Write`/`Edit`/Bash poderia vir disso e não da regra `deny` testada; o CPos ("operação sobre canário permitido funciona") também não funcionaria sem `allow`. `resultados.md` E06 mostra que o laboratório anterior usou `dontAsk` + `allow` explícitos.
- Impacto: resultados SUCESSO de X13 (e de X12/X19) podem ser falsos positivos; o CPos pode falhar sistematicamente e gerar INCONCLUSIVO.
- Correção: definir settings de cada experimento B (modo, `allow` para o CPos, `deny` testado) e o que prova que a negação foi da regra (mensagem/`permission_denials` no stream-json).

**AUD4-MED-4 — "Registro independente" das sessões B não é independente do processo testado, e sem hook não há tentativa.**
- Evidência: `f2_0d_especificacao.md` §3 exige RI "fora do alcance do processo testado"; para B (l.38, l.132) o registro é "o hook e o stream-json". O log do hook é escrito por processo do mesmo usuário, em `evidencias_d/` alcançável pela própria sessão sem confinamento; R25 diz que a regra `deny` age antes do hook e o hook nem registra. Apenas o stream-json capturado pelo harness (stdout) é externo.
- Impacto: CP-1 item 2 pode ser declarado cumprido sem sê-lo para B; risco de log adulterado ou ausente tratado como prova.
- Correção: declarar o stream-json capturado pelo harness como RI primário; o hook como corroborante; local de gravação fora do cwd das sessões.

**AUD4-MED-5 — D1(c) contradiz P3/P5.**
- Evidência: `portoes_f2.md` P3 ("R1 bloqueia toda EDI até o CP-5 ser aprovado") e P5; D1(c) (`matriz_decisoes_humanas.md` l.31) "Autoriza: execução de código de agente sem confinamento comprovado"; matriz de autonomia obs. 2 ("nível 1 com risco aceito pelo usuário (D1)").
- Impacto: dois regimes opostos para o mesmo caso; o usuário pode escolher (c) pensando que isso libera o que P3 diz estar bloqueado.
- Correção: uma frase em P3 ("exceto por aceite D1(c) escrito, que altera apenas X, não fecha R1") ou remover (c) como opção antes do CP-5.

**AUD4-MED-6 — CP-5 cita "provas 1 a 8", mas o plano tem 13 provas.**
- Evidência: `portoes_f2.md` l.63 e `plano_isolamento_r1.md` §9 ("provas 1 a 8"); §7 lista 13, entre elas 9 (Landlock), 10 (claude inteiro), 11 (`bwrap` aninhado/filho do claude), 12 (/proc, /dev, /sys, .git, rede), 13 (TTY). `criterios_peach_f2.md` CP-5 menciona "bwrap iniciado como filho do claude" (prova 11) e `/proc` não aparece.
- Impacto: ambiguidade sobre o que fecha R1; os itens que M-7 pediu (/proc, /dev, /sys, .git, aninhado, TTY) podem ficar fora do critério de fechamento.
- Correção: alinhar a numeração e dizer quais provas fecham R1 e quais só informam.

**AUD4-MED-7 — Limpeza: lacunas operacionais.**
- Evidência: `f2_0d_especificacao.md` §4.4 ("temporários" sem definição); §4.1 (`/tmp/dengue_f2d/` fixo e previsível); X07 cria symlinks e hardlinks; X05/X06 sobem listener e processo vizinho; X15/X19 usam `f2/.claude/settings.local.json` sem tratar arquivo preexistente (`LEIA-ME.md` l.44 e `plano.md` prevêem cópia opcional de `lab-sombra.md` para `.claude/agents/`); `.cc-writes` e transcritos criados pela sessão não estão na lista de limpeza.
- Impacto: não há risco de `rm` amplo no desenho (remoção condicionada a marcador e caminho), mas faltam: caminho único não previsível ou exigência de `mkdir` falho se existir; remoção que não segue symlinks; encerramento de processos e listeners; backup/restauração de arquivo preexistente.
- Correção: especificar cada item no `limpar.sh` ou declarar que não faz parte (e quem o faz).

**AUD4-MED-8 — CC-local: quem garante que só roda o comando fixo.**
- Evidência: `portoes_f2.md` P4(c) "comando fixo, iniciado por você numa sessão CC-local"; `f2_0d_especificacao.md` §1 "só roda o comando fixo... Não improvisa comandos". Mas o CC-local é uma sessão do Claude Code (modelo) no computador do usuário, sem os controles da F2 (ainda inexistentes), executando código escrito por agente. A única barreira é a pausa de P8 ("CC-local pedir ação proibida") e a leitura humana.
- Impacto: ESH depende de o usuário aprovar cada chamada Bash e de o modelo não improvisar; isso não está escrito como obrigação do HUM, nem o modo de permissão do CC-local.
- Correção: dizer que o CC-local roda em modo que exige aprovação humana de cada comando, ou que o usuário digita `rodar_d.sh <ID>` no terminal e o CC-local só lê logs; incluir a prova de identidade do comando (hash do script) citada na pausa de F2.0-D item 6.

### BAIXO

**AUD4-BAIXO-1 — Status "MITIGADO" fora da legenda.** `registro_riscos.md` l.3 define ABERTO, MITIGADO-H, RESOLVIDO-T, ACEITO-PENDENTE; R3 e R10 usam "MITIGADO". R3 depende de prova só para `Read`/`cat` (a evidência necessária diz H para `Write`/`Edit`). Corrigir para MITIGADO-H/RESOLVIDO-T parcial.

**AUD4-BAIXO-2 — Limite de sessões por experimento inconsistente.** §3 l.57: "no máximo 3 sessões por experimento"; X16 e X18 têm 5 (a soma de 24 depende disso). Ajustar §3.

**AUD4-BAIXO-3 — Corrida em X07 não é determinística.** Sucesso por ausência de vazamento numa corrida "simples" não prova negação. Declarar o resultado como "sem evidência de vazamento nesta tentativa" (H residual) e limitar a hipótese HD-4.

**AUD4-BAIXO-4 — Texto de D3 pode sugerir autorização de início.** Exemplo "D3: autorizo X01 a X09..." (matriz l.57) e as alternativas "Autoriza: os 11 experimentos" convivem com "autorização de início separada". Já há duas afirmações de separação; recomenda-se uma linha em D3 dizendo que D3 não inicia a etapa e que mudança do harness após o hash exige nova decisão.

**AUD4-BAIXO-5 — D10(d) × F2.1.** `portoes_f2.md` F2.1 exige "D10" sem dizer que, com D10(d), é preciso decidir CP-2/CP-3 antes. Explicitar.

**AUD4-BAIXO-6 — Editorial e de completude.** (i) `relatorio_f2_0c_2.md` §3 "tudo é corrigido documentalmente" vs PARCIAL/NÃO VERIFICÁVEL em `rastreabilidade.md`; (ii) cabeçalho de `parecer_f2_0.md` não cita C.2 (só §9); (iii) X20 aparece entre as fichas do Pacote A e fora de ordem (l.129); (iv) X07-X09 sem campo "Pré". Não exige nova auditoria.

## 7. Limitações desta auditoria

- Exclusivamente documental: nada foi executado; nenhuma afirmação T foi reproduzida. Aceito T/D/H/L como declarados nos documentos e só os conferi por coerência interna.
- Não li `bin/`, `cfg/`, `evidencias/`, `sintetico/`, manifestos ou `DECISOES.md`; não verifiquei se o disco do projeto está igual à cópia lida.
- Textos originais de AUD0-AUD3 ausentes; não avaliei se as correções atendem ao que as auditorias disseram, só ao que `rastreabilidade.md` relata.
- Não pude verificar comportamento do Claude Code citado (por exemplo, modo `-p` sem `allow`, gravação de estado em `~/.claude`) além do que os documentos registram (R-L1, E06); AUD4-MED-3 é inferência de projeto experimental, não observação.
- A contagem de linhas e IDs foi feita por script simples sobre tabelas Markdown; saltos fora do padrão `| N |` poderiam escapar.

## 8. Pendências que exigem decisão humana

1. D10 (ao menos CP-1) antes de D3; D3 com os cinco itens; harness: quem o escreve, quem revisa, hash.
2. Local dos canários (proposta `/tmp/dengue_f2d/` ou `~/dengue_f2d/`) e tetos (propostas, não decididos).
3. Aceitar (ou não) a escrita inevitável do `claude -p` em `~/.claude` e definir o snapshot (AUD4-ALTO-3).
4. Incluir ou excluir X20/X21 e definir X20 antes do Pacote B (AUD4-ALTO-2/3).
5. D1 (e se (c) existe antes do CP-5), D8, D9, D7, DX-1..3, D2, D4-D6 conforme a etapa.
6. Autorização de início de cada etapa, por escrito, separada de D3.
7. Pendências preexistentes, fora desta auditoria: DP-001, Etapa 3.2 (sem aprovação científica), Etapa 3.3, Q20-Q22 (origens de auditorias).

## 9. A documentação está suficientemente madura para o usuário considerar autorizar a F2.0-D?

**Parcialmente, e isso NÃO é autorização.** Para considerar D10 e a escolha do Pacote A (X01-X11), a documentação está madura: ficha utilizável, controle positivo e registro independente definidos, nada fora de `f2/` e do local de canários, tetos propostos. Para considerar o **Pacote B** (X12-X19), **não está madura** até que sejam resolvidos AUD4-ALTO-1 (contenção), AUD4-ALTO-3 (`~/.claude`) e AUD4-MED-3 (modo de permissão). Para X20/X21, **não está madura** (AUD4-ALTO-2). Antes de qualquer pacote, os pontos AUD4-MED-1 (como e por quem o harness é escrito e revisado) e AUD4-MED-2 (lista de arquivos) precisam de resposta. Recomendação técnica: uma correção documental curta sobre esses pontos (sem nova sequência de auditorias, a verificar na própria revisão do harness) e, só então, a decisão D10/D3. Nenhuma etapa deve ser iniciada por este parecer.
