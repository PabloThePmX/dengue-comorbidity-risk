# Rastreabilidade dos achados (F2.0-C.3)

Liga cada achado das auditorias da Peach ao documento afetado, à correção e ao estado. **"Corrigido documentalmente" não é "comprovado tecnicamente".** Nenhum item abaixo tem prova técnica, salvo onde a coluna "Prova técnica" diz **T**.

## 1. Como ler esta tabela
**Identificadores únicos.** Cada achado tem um ID com o prefixo da auditoria. Nomes curtos como "M5", "M7", "A5" ou "B4" **sem prefixo são ambíguos** e não devem ser usados.

| Prefixo | Auditoria | Como foi recebida |
|---|---|---|
| **AUD1** | Primeira, sobre a F2.0 (C1–C3, I1–I9, R12/R13 e outros) | Parecer apresentado na conversa e resumido nos documentos. O texto completo original **não está em `f2/`** e eu não o tenho integral. |
| **AUD2** | Segunda, sobre a F2.0-C (A1–A5, M1–M9, B1–B2) | Relato de subagente entregue na conversa. Não está em `f2/`. |
| **AUD3** | Terceira, sobre a F2.0-C.1 (ALTO-1 a 3, M-1 a M-11, B-1 a B-8) | Relato de subagente entregue na conversa. Não está em `f2/`. |
| **AUD4** | Quarta, sobre a F2.0-C.2 | Parecer `parecer_peach_f2_0c_2.md`, **gravado em `f2/`** (texto completo disponível). |
| **AUD0** | Auditorias de etapas anteriores à F2 (reservas "N1–N7") | Origem **não localizada**. |
| **AUD?** | Identificadores citados nos documentos sem dizer de qual auditoria | Origem não verificável. |

**Registro expresso:** as auditorias foram recebidas como **pareceres de subagentes** (instâncias separadas da Peach). Em vários casos **não tive acesso ao texto original completo**. Onde só existe a minha paráfrase, o estado não pode passar de "corrigido documentalmente" e a lacuna está marcada. Não reconstruí nenhum achado original ausente.

**Estados:** **CORRIGIDO-DOC** (texto corrigido); **PARCIAL**; **PENDENTE**; **NÃO VERIFICÁVEL** (depende de evidência ausente). **Prova técnica:** **T** (feita), **NÃO** (ainda não), **N/A**.

## 2. AUD1 — primeira auditoria (F2.0)
| ID único | Tema | Documento afetado | Correção | Estado | Prova técnica |
|---|---|---|---|---|---|
| AUD1-C1 | Parecer F2.0 no disco era a versão antiga | `parecer_f2_0.md`; `criterios_peach_f2.md` G5 | Reescrito; regra de reler conteúdo. Causa do defeito de entrega não apurada (reenviar o mesmo arquivo pode gravar a versão antiga, observado de novo na F2.0-C.1) | CORRIGIDO-DOC; causa PENDENTE (Q20) | N/A |
| AUD1-C2 | Recarga de configuração, socket de mensagens, conectores | `registro_riscos.md` R18, R19, R20; X15, X05 | Registrados; efeitos não testados | CORRIGIDO-DOC como risco | NÃO |
| AUD1-C3 | Processos filhos alterando controles e arquivos | `registro_riscos.md` R21; `plano_isolamento_r1.md` | Registrado | CORRIGIDO-DOC como risco | NÃO |
| AUD1-I1 | "Glob/Grep não existem" | `resultados.md`; `limitacoes.md` R13 | "Ausentes por padrão no Linux" (D; T nas sessões) | CORRIGIDO-DOC | T parcial |
| AUD1-I2 | Spawn sem teste real de negação | `resultados.md` B4; X12; CP-4 | Declarado não provado | CORRIGIDO-DOC | NÃO |
| AUD1-I3 | `deny` vence `allow` do hook (`cat`) | `resultados.md` B4 | Mecanismo no log do E06b | CORRIGIDO-DOC | T (só `Read`/`cat`) |
| AUD1-I4 | `lab-bypass`: causa da negação não isolada | `resultados.md` B4 (linha incluída em F2.0-C.1); `parecer_f2_0.md` §2; Q15 | Registrada | CORRIGIDO-DOC | NÃO |
| AUD1-I5 | Sandbox: não afirmar que a checagem passou | `resultados.md` B4; `limitacoes.md` H-10 | Texto corrigido | CORRIGIDO-DOC | T |
| AUD1-I6 | R12 relação com sandbox só por correlação | `limitacoes.md` R12; D7; X17 | Causa H | CORRIGIDO-DOC; causa PENDENTE | NÃO |
| AUD1-I7 | Logs externos superam relatos | `criterios_peach_f2.md` G1; `arquitetura_l0.md` §1 | Princípio e critério | CORRIGIDO-DOC | T (E02, E06a) |
| AUD1-I8 | Mensagem do `dontAsk` sugere alternativas; laço de contornos | `arquitetura_l0.md` §6; R27 | Contador de negações (proposto) | CORRIGIDO-DOC | NÃO |
| AUD1-I9 | Orçamento, rate limit, retomada | `arquitetura_l0.md` §6, §8; R26 | Proposto | CORRIGIDO-DOC | NÃO |
| AUD1-R12 | `.cc-writes` e manifesto | `registro_riscos.md` R12; D7 | Exceção exata por caminho e conteúdo | CORRIGIDO-DOC | NÃO |
| AUD1-R13 | `Glob`/`Grep` variam por sessão | `limitacoes.md` R13; Q5 | Registrado | CORRIGIDO-DOC | NÃO |
| AUD1-INT | Tamanho e data iguais ≠ integridade byte a byte | `resultados.md` B4; `parecer_f2_0.md` §3; errata no topo de `plano.md` | Redação corrigida | CORRIGIDO-DOC (hash de manifesto: DX-2, não decidido) | N/A |

## 3. AUD0 e AUD? — identificadores sem texto original
| ID único | Onde aparece | O que se sabe | Estado |
|---|---|---|---|
| AUD?-M5 | `registro_riscos.md` R25 ("M5 da auditoria") | Só que foi citado ali. **O tema não é conhecido.** A anotação anterior ("logs dos hooks") era inferência e **não** vale como citação. Não confundir com AUD2-M5 | **NÃO VERIFICÁVEL** (Q22) |
| AUD?-M7 | `registro_riscos.md` R16, R24 | Idem. Não confundir com AUD2-M7 | **NÃO VERIFICÁVEL** (Q22) |
| AUD0-N1 a AUD0-N7 | `matriz_decisoes_humanas.md` (versões anteriores) | Citadas como "reservas N1–N7 da Peach". Origem não localizada. A frase anterior de que estavam "tratadas" em outros documentos **não tinha base e foi retirada.** Não confundir com N-01 a N-05 de `limitacoes.md` §3 (limitações do laboratório, outra coisa) | **NÃO VERIFICÁVEL**; abertas |
| AUD0-B4 | "N1–N7/B4" na versão anterior da matriz | Origem não localizada. Não confundir com a seção B4 de `resultados.md` (correções da AUD1) | **NÃO VERIFICÁVEL** |
| AUD1-M41 | "Matriz de 41 linhas" | Texto original ausente; a matriz atual tem 54 linhas (50 + 4). Mapeamento linha a linha **não reconstruível** | **NÃO VERIFICÁVEL** (Q21) |

## 4. AUD2 — segunda auditoria (F2.0-C)
| ID único | Tema | Correção na F2.0-C.1 e C.2 | Estado | Prova técnica |
|---|---|---|---|---|
| AUD2-A1 | Bootstrap dos controles | `arquitetura_l0.md` §2A (incl. sessão de bootstrap passo a passo); D9; R29; matriz linhas 29 e 53 | CORRIGIDO-DOC | NÃO |
| AUD2-A2 | Autorização de missão | `arquitetura_l0.md` §2; D4; R30 | CORRIGIDO-DOC | NÃO |
| AUD2-A3 | Decisão por evidências | `criterios_peach_f2.md` §2 a §4 (V e J); matriz linha 38; R31 | CORRIGIDO-DOC | NÃO |
| AUD2-A4 | Proteção preventiva | `arquitetura_l0.md` §10; `plano_isolamento_r1.md` §6; R32 | PARCIAL (sem prova; X20 e X21 em pacote C) | NÃO |
| AUD2-A5 | Allowlist | `plano_isolamento_r1.md` §2 a §5, §6A–6D, §7; R33 | PARCIAL (sem prova) | NÃO |
| AUD2-M1 | Flags com T não demonstrado | `resultados.md` B5; `arquitetura_l0.md` §5 | CORRIGIDO-DOC | N/A |
| AUD2-M2 | LEIA-ME e errata do `plano.md` | `LEIA-ME.md`; `plano.md` | CORRIGIDO-DOC | N/A |
| AUD2-M3 | Rastreabilidade e I4 | este arquivo; `resultados.md` B4 | PARCIAL (itens de AUD0/AUD? sem texto) | N/A |
| AUD2-M4 | R16 duplicado | `limitacoes.md` R-L16; `registro_riscos.md` R16 | CORRIGIDO-DOC | N/A |
| AUD2-M5 | Textos obsoletos em `limitacoes.md` | `limitacoes.md` §1, §2, §6, §8 | CORRIGIDO-DOC | N/A |
| AUD2-M6 | Ordem do roadmap e critérios | `roadmap_f2_revisado.md`; `portoes_f2.md`; CP-1 a CP-9 | CORRIGIDO-DOC | N/A |
| AUD2-M7 | D3 a D6, lacunas | `matriz_decisoes_humanas.md` | CORRIGIDO-DOC (refeito na C.2) | N/A |
| AUD2-M8 | Exceção de runtime | `registro_riscos.md` R12; D7 | CORRIGIDO-DOC | NÃO |
| AUD2-M9 | Proveniência do `resumo.md` | `limitacoes.md` §8; `resultados.md` B5 | CORRIGIDO-DOC como limitação | N/A |
| AUD2-B1 | Documentos de projeto em pasta "descartável" | `LEIA-ME.md` | PARCIAL (não movi; é decisão sua) | N/A |
| AUD2-B2 | Redação do parecer | `parecer_f2_0.md` §8 | **NÃO VERIFICÁVEL** (texto original ausente) | N/A |

## 5. AUD3 — terceira auditoria (F2.0-C.1), tratada na F2.0-C.2
| ID único | Tema | Documentos afetados e correção | Estado | Prova técnica |
|---|---|---|---|---|
| AUD3-ALTO-1 | D3 sem escopo fechado | `matriz_decisoes_humanas.md` D3; `f2_0d_especificacao.md` (21 experimentos, executores, local, tetos, limpeza, proibições) | CORRIGIDO-DOC | NÃO |
| AUD3-ALTO-2 | Portão da F2.1 contraditório | `portoes_f2.md` (fonte única); `roadmap_f2_revisado.md`; `parecer_f2_0.md` §6; `matriz_autonomia.md` | CORRIGIDO-DOC | N/A |
| AUD3-ALTO-3 | CP-1 sem critérios de sucesso e falha | `criterios_peach_f2.md` CP-1; `f2_0d_especificacao.md` §3 e §5 | CORRIGIDO-DOC | NÃO |
| AUD3-M-1 | Identificadores colidindo | este arquivo | CORRIGIDO-DOC; AUD?-M5 e M7 NÃO VERIFICÁVEL | N/A |
| AUD3-M-2 | Linhas 51–54 sem coluna "Hoje" | `matriz_autonomia.md` | CORRIGIDO-DOC | N/A |
| AUD3-M-3 | `deny` de edição marcado T sem teste | `matriz_autonomia.md` (D/H); `registro_riscos.md` R3; X13 | CORRIGIDO-DOC | NÃO |
| AUD3-M-4 | `onFailure` ausente | `parecer_f2_0.md` §1; `limitacoes.md` §9; `resultados.md` B6; X18 | CORRIGIDO-DOC | NÃO |
| AUD3-M-5 | R11 apontava para D8 | `registro_riscos.md` R11, seção C; DX-3 | CORRIGIDO-DOC | N/A |
| AUD3-M-6 | TTY sem classe H | `arquitetura_l0.md` §2; `plano_isolamento_r1.md` §6C; X11 | CORRIGIDO-DOC | NÃO |
| AUD3-M-7 | Lacunas da allowlist | `plano_isolamento_r1.md` §4, §6A–6D, §7 | CORRIGIDO-DOC | NÃO |
| AUD3-M-8 | Validação estrutural × evidência real | `criterios_peach_f2.md` §3 (V e J; aceite humano) | CORRIGIDO-DOC | NÃO |
| AUD3-M-9 | DX-1 e DX-2 incompletos; contradição com `manifesto.py` | `matriz_decisoes_humanas.md` DX-1 a DX-3; `arquitetura_l0.md` §4 | CORRIGIDO-DOC | N/A |
| AUD3-M-10 | Ambiguidades em D1, D7, D8, D10, D5 | `matriz_decisoes_humanas.md` | CORRIGIDO-DOC | N/A |
| AUD3-M-11 | Sessão de bootstrap e D10 como dependência | `arquitetura_l0.md` §2A; `portoes_f2.md` F2.0-D | CORRIGIDO-DOC | NÃO |
| AUD3-B-1 | `plano.md` "errata abaixo" | `plano.md` | CORRIGIDO-DOC | N/A |
| AUD3-B-2 | R12 com texto na célula de status | `registro_riscos.md` | CORRIGIDO-DOC | N/A |
| AUD3-B-3 | Cabeçalhos desatualizados | `limitacoes.md`; `resultados.md` | CORRIGIDO-DOC | N/A |
| AUD3-B-4 | Q13, Q15, Q12 e D3(b) | `questoes_abertas.md` (fora do escopo, ficam H/L); Q12 em HD-5 | CORRIGIDO-DOC | N/A |
| AUD3-B-5 | "Linhas 45" | `questoes_abertas.md` | CORRIGIDO-DOC | N/A |
| AUD3-B-6 | Parecer sem dizer qual auditoria | `parecer_f2_0.md` | CORRIGIDO-DOC | N/A |
| AUD3-B-7 | Roadmap remete a "plano anterior"; CP-2 e CP-3 | `roadmap_f2_revisado.md` (declara que F3 a F6 não foram relidas); CP-2 e CP-3 mantidos | PARCIAL | N/A |
| AUD3-B-8 | D9(a) com testes por agentes | `matriz_decisoes_humanas.md` D9(a) ("Cuidado") | CORRIGIDO-DOC | N/A |

## 5A. AUD4 — quarta auditoria (sobre a F2.0-C.2), tratada na F2.0-C.3
Fonte: `parecer_peach_f2_0c_2.md` (**presente em `f2/`**, ao contrário dos textos de AUD0 a AUD3). Veredito: APROVADO COM RESSALVAS; 0 críticos, 3 altos, 8 médios, 6 baixos. **Todos os estados abaixo são "corrigido documentalmente" ou parcial; nenhuma prova técnica foi feita.** A reauditoria desta rodada é a Peach da C.3 (`parecer_peach_f2_0c_3.md`, quando existir).

| ID único | Tema | Documentos afetados e correção | Estado | Prova técnica |
|---|---|---|---|---|
| AUD4-ALTO-1 | Sessões do pacote B sem contenção definida | `f2_0d_especificacao.md` §5B (perfil proposto: `--agent`, `--tools`, `--strict-mcp-config` com MCP vazio, `dontAsk`, cwd dedicado, verificação do `init` contra conectores do Drive; **pacote B NÃO AUTORIZADO / BLOQUEADO**, condições de desbloqueio e decisão "D3-B"); `portoes_f2.md`; `matriz_decisoes_humanas.md` D3; R34 | CORRIGIDO-DOC (o bloqueio é a correção; o perfil é H e não prova contenção) | NÃO |
| AUD4-ALTO-2 | X20 e X21 sem ficha | `f2_0d_especificacao.md` §5C: fichas completas; fora de qualquer pacote; X20 pré-requisito do B | CORRIGIDO-DOC (completas no papel) | NÃO |
| AUD4-ALTO-3 | `~/.claude` × `claude -p`; snapshot indefinido | `f2_0d_especificacao.md` §4.3 e §4.6 (exceção estreita, escopo nomeado, snapshot e diff, `CLAUDE_CONFIG_DIR` via X20); `limitacoes.md` R-L1; R35 | CORRIGIDO-DOC; PARCIAL quanto à lista de subdiretórios de estado (Q32) | NÃO |
| AUD4-MED-1 | Harness: círculo | `portoes_f2.md` etapa **F2.0-D0**; `f2_0d_especificacao.md` §3 e §4.1; D3 | CORRIGIDO-DOC | NÃO |
| AUD4-MED-2 | Lista de arquivos incompleta; canário no repositório | `f2_0d_especificacao.md` §4.1 (lista fechada com hash a registrar na D0); `plano_isolamento_r1.md` §5 | CORRIGIDO-DOC | NÃO |
| AUD4-MED-3 | `deny` × ausência de `allow` (X13) | `f2_0d_especificacao.md` X13 (três braços); `criterios_peach_f2.md` CP-1 itens 9 e 10 | CORRIGIDO-DOC (X13 bloqueado) | NÃO |
| AUD4-MED-4 | RI dependente do hook | `f2_0d_especificacao.md` §3 e §5B.3; `criterios_peach_f2.md` CP-1 item 2 | CORRIGIDO-DOC | NÃO |
| AUD4-MED-5 | D1(c) × P3/P5 | `portoes_f2.md` P3; `matriz_decisoes_humanas.md` D1; `matriz_autonomia.md` nota | CORRIGIDO-DOC | N/A |
| AUD4-MED-6 | CP-5 "provas 1 a 8" | `plano_isolamento_r1.md` §9 (tabela de obrigatórias e informativas); `criterios_peach_f2.md` CP-5; `portoes_f2.md` F2.3 | CORRIGIDO-DOC (a classificação é proposta, depende de D10) | N/A |
| AUD4-MED-7 | Limpeza | `f2_0d_especificacao.md` §4.1 e §4.4 (registro de criação, nome aleatório, `lstat`, PID com hora de início, recusa com arquivo preexistente); R37 | CORRIGIDO-DOC | NÃO |
| AUD4-MED-8 | CC-local e o comando fixo | `f2_0d_especificacao.md` §4.7 (modo 1 você digita; modo 2 aprovação por comando; hash do script); R36 | CORRIGIDO-DOC; limite L declarado | NÃO |
| AUD4-BAIXO-1 | Status "MITIGADO" fora da legenda | `registro_riscos.md` R3 e R10 → MITIGADO-H (parcial) | CORRIGIDO-DOC | N/A |
| AUD4-BAIXO-2 | 3 × 5 sessões | `f2_0d_especificacao.md` §3 (exceções explícitas) | CORRIGIDO-DOC | N/A |
| AUD4-BAIXO-3 | Corrida X07 | `f2_0d_especificacao.md` X07 (H residual) e `plano_isolamento_r1.md` §9 | CORRIGIDO-DOC | NÃO |
| AUD4-BAIXO-4 | D3 sugere início | `matriz_decisoes_humanas.md` D3 ("não inicia a etapa"; exemplo corrigido) | CORRIGIDO-DOC | N/A |
| AUD4-BAIXO-5 | D10(d) × F2.1 | `portoes_f2.md` F2.1; `criterios_peach_f2.md`; D10 | CORRIGIDO-DOC | N/A |
| AUD4-BAIXO-6 | Editorial | (i) relatório C.2 com nota C.3; (ii) cabeçalho do `parecer_f2_0.md` atualizado; (iii) ordem das fichas X20 corrigida; (iv) campo "Pré" em X07 a X09 | CORRIGIDO-DOC | N/A |

**Perguntas que a Peach deixou NÃO VERIFICÁVEIS** (continuam assim): identidade byte a byte do disco do projeto com os mestres, no momento do parecer C.2; conteúdo de `bin/`, `cfg/`, `evidencias/`, `sintetico/`; os textos de AUD0 a AUD3.

## 5B. AUD5 — quinta auditoria (sobre a F2.0-C.3), tratada na F2.0-D0
Fonte: `parecer_peach_f2_0c_3.md` (**presente em `f2/`**). Veredito: APROVADO COM RESSALVAS; 0 críticos, 0 altos, 5 médios, 9 baixos. **Estados: "corrigido documentalmente" ou parcial; nenhuma prova técnica foi feita; o harness nunca foi executado.** A reauditoria é a Peach da D0 (`parecer_peach_f2_0d0.md`, quando existir; **não** presumido aqui).

| ID único | Tema | Correção na D0 | Estado | Prova técnica |
|---|---|---|---|---|
| AUD5-MED-1 | Snapshot acusa FALHA por escritas do CC-local; lista tolerada não confirmável na D0 | `f2_0d_especificacao.md` §4.6 (classes ESPERADA, INESPERADA, INDETERMINADA; atribuição por sessões ativas); a lista vira proposta a **medir na F2.0-D**; `harness.py` `comparar` | CORRIGIDO-DOC; PARCIAL (lista H, Q32) | NÃO |
| AUD5-MED-2 | D3 não informava que X20 e X21 são `claude -p` sem contenção | `f2_0d_especificacao.md` §0 e §5C; `matriz_decisoes_humanas.md` D3; R38 | CORRIGIDO-DOC | NÃO |
| AUD5-MED-3 | Verificação de hash circular | §4.7: verificação **sua**, em terminal próprio, antes de cada execução; `rodar_d.sh` não se verifica; harness confere os outros arquivos | CORRIGIDO-DOC; PARCIAL (o harness não prova o próprio hash) | NÃO |
| AUD5-MED-4 | X20 → X21 e limpeza | §5C e §4.4: limpeza em duas fases, X21 reutiliza o estado, sem novo login | CORRIGIDO-DOC | NÃO |
| AUD5-MED-5 | Sem critério objetivo para revisar o código | `criterios_peach_f2.md` CP-1H (H-01 a H-26); D10 aceita com complemento | CORRIGIDO-DOC (checklist não é prova) | NÃO |
| AUD5-BAIXO-1 | Credenciais: regra, não mecanismo | §5C e R38: declarado L (proteção procedimental) | CORRIGIDO-DOC | NÃO |
| AUD5-BAIXO-2 | Classificação das provas do CP-5 | Não alterado na D0 | **ABERTO** (editorial) | n/a |
| AUD5-BAIXO-3 | Itens 5 e 10 da lista; tetos de XB0 | §4.1 item 5 e 10; §4.2 linha de XB0 | CORRIGIDO-DOC | NÃO |
| AUD5-BAIXO-4 | `claude --help` na D0 | `portoes_f2.md` D0: não será rodado | CORRIGIDO-DOC | n/a |
| AUD5-BAIXO-5 | Condição 3 de desbloqueio ambígua | §5B.2: decisão final é sua; discordância da Peach fica registrada | CORRIGIDO-DOC | n/a |
| AUD5-BAIXO-6 | Reprodutibilidade X20/X21 | §5C (caminho impresso, login, 3 ajustes em X21, exceção em §3) | CORRIGIDO-DOC; PARCIAL (comando de login não verificado, Q30) | NÃO |
| AUD5-BAIXO-7 | D10(d) × D0 | `matriz_decisoes_humanas.md` D10 (uso na D0) | CORRIGIDO-DOC | n/a |
| AUD5-BAIXO-8 | Campo "Pré" desigual | §5A X10 e X11 | CORRIGIDO-DOC | n/a |
| AUD5-BAIXO-9 | Cabeçalhos desatualizados | `portoes_f2.md`, `plano_isolamento_r1.md`, `criterios_peach_f2.md`, `f2_0d_especificacao.md` | CORRIGIDO-DOC | n/a |

## 6. Limites desta tabela
- "Corrigido documentalmente" quer dizer que o texto foi alterado como a paráfrase do achado pede. **Não** garante que o achado original foi atendido, quando o original não está disponível.
- Nenhuma hipótese H foi promovida a T.
- A auditoria da Peach sobre a F2.0-C.3 é pedida na mesma missão; seu resultado fica em `parecer_peach_f2_0c_3.md` e **não** é presumido aqui.
