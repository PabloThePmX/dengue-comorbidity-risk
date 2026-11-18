# Portões normativos F2 (F2.0-C.2; atualizado na C.3 e na F2.0-D0) — fonte única

Este arquivo é a **fonte normativa** dos pré-requisitos, das atividades permitidas, dos critérios de conclusão, das evidências, das condições de reprovação e de pausa e das autorizações humanas de cada etapa, de F2.0-D a F2.7. `roadmap_f2_revisado.md`, `parecer_f2_0.md`, `matriz_autonomia.md`, `criterios_peach_f2.md` e `matriz_decisoes_humanas.md` **remetem a ele**. Em caso de conflito com qualquer outro documento, vale este.

Todas as etapas estão **bloqueadas** até autorização humana expressa e escrita para cada uma. **Exceção registrada (D0, 2026-11-18, 17:11):** por mensagem sua, a **preparação da F2.0-D0** foi autorizada (D3 = pacote A; D10 aceita com complemento). Nenhuma outra etapa e **nenhuma execução (X01 a X21)** está autorizada.

**Nota D0 (2026-11-18):** D10 aceita com complemento (CP-1H, revisão obrigatória do código do harness antes de qualquer experimento) e D3 = pacote A, **só para preparar a D0**; o pacote B segue **NÃO AUTORIZADO / BLOQUEADO**; X20 e X21 estão **fora da D3**; R1 segue **ABERTO**. O harness foi escrito e **não foi executado**. A aprovação documental da D0 não é prova técnica de isolamento e **não autoriza executar nada**.

**Nota C.3 (2026-11-18):** acrescentada a etapa preparatória **F2.0-D0** (redação do harness, sem execução), que desfaz o círculo apontado em AUD4-MED-1; o **pacote B** da F2.0-D passa a **NÃO AUTORIZADO / BLOQUEADO**; **D1(c)** deixa de ser selecionável antes do CP-5; a numeração das provas do CP-5 foi alinhada às 13 do plano de isolamento. Histórico: o texto anterior (C.2) está descrito em `rastreabilidade.md` (AUD4).

## 1. Regras gerais
- **P1.** Nenhuma etapa inicia a seguinte. Concluir uma etapa, ter documentos prontos ou ter aprovação da Peach não autoriza a próxima. Só um texto seu, por etapa, autoriza o início.
- **P2.** Nenhuma etapa declara sucesso porque seus documentos foram escritos. Sucesso exige a evidência da coluna "Evidências" e a aprovação do critério CP correspondente (`criterios_peach_f2.md`).
- **P3. Execução dependente de isolamento (EDI):** qualquer execução **autônoma** de código ou comando escrito por agente, ou de Bash fora de um perfil sem interpretadores, inclusive `pytest`; qualquer sessão cuja segurança dependa de confinamento ainda não comprovado. **R1 bloqueia toda EDI até o CP-5 ser aprovado (na F2.3).** R1 **não** bloqueia a *entrada* em nenhuma etapa; ele bloqueia o que depende de isolamento. **Não existe exceção por aceite de risco antes do CP-5:** a alternativa D1(c) (aceitar R1 e liberar Bash e `pytest`) **não é selecionável antes do CP-5 aprovado** (C.3); depois dele, D1(c) só vale como aceite do **risco residual**, nunca como substituto da prova. Isso elimina a contradição D1(c) × P3/P5 (AUD4-MED-5).
- **P4. Execução supervisionada pelo humano (ESH):** a única forma de executar código de agente antes do CP-5. Condições: (a) código revisado pela Peach em sessão independente e lido por você; (b) hash do código registrado; (c) comando fixo, iniciado por você numa sessão do Claude Code no seu computador (CC-local); (d) só dados sintéticos; (e) um comando por vez, sem laço autônomo; (f) registro pelo harness (`f2_0d_especificacao.md` §3). ESH não é autonomia e não fecha R1.
- **P5.** R1 só passa a "mitigado" no CP-5 aprovado pela Peach e só vira "aceito" por decisão sua (D1). Enquanto isso, **R1 permanece aberto**.
- **P6. Executores** (definição única): **NUV** = esta sessão na nuvem: só lê e grava documentos e scripts em `agentes/laboratorio/f2/` pelas ferramentas de arquivo; **não tem shell** no seu computador. **CC-local** = sessão do Claude Code no seu computador, iniciada por você, que roda apenas comandos fixos de harness e devolve os logs. **HUM** = você: iniciar a sessão, fazer login se pedido, escolher locais, aprovar o início, ler diffs, aceitar riscos. **PEACH** = auditora em sessão separada, só leitura.
- **P7. Reprovação de etapa × hipótese refutada.** Uma hipótese de segurança refutada (por exemplo, o `bwrap` não nega uma leitura) é um **achado válido**, não reprovação da etapa. A etapa é reprovada por falha de processo (violação de proibição, evidência ausente, harness defeituoso) ou por não cumprir o critério de conclusão.
- **P8. Pausa comum a todas as etapas:** sinal de acesso a algo fora da lista autorizada; alteração inesperada detectada pelo snapshot definido em `f2_0d_especificacao.md` §4.6 (arquivo preexistente do escopo nomeado de `~/.claude` alterado, ou arquivo novo fora da área e dos subdiretórios de estado); `rate_limit_event` com `utilization` ≥ 0,95 ou erro 429; custo acumulado ≥ 80% do teto; o CC-local pedir ação proibida; erro do harness; qualquer dúvida sobre a identidade da sessão. Na pausa: nada é executado, estado salvo, pendência registrada, retomada só por você.
- **P9.** Toda ampliação de escopo (um experimento a mais, um arquivo a mais, um teto maior) exige **nova** decisão sua. Autorização implícita não existe.

## 2. Resumo dos portões
| Etapa | Entrada exige | Conclui com | Autonomia | R1 |
|---|---|---|---|---|
| F2.0-D0 | Autorização de início (texto seu); D3 (escopo escolhido); D10 com CP-1 aceito; lista fechada de arquivos de `f2_0d_especificacao.md` §4.1 | Harness e documentos revisados pela Peach e por você, hashes registrados. **Sem execução** | Nenhuma | Não fecha |
| F2.0-D | Autorização de início (texto separado); **D0 concluída**; D3 inalterada desde a D0; D10 (CP-1); local-base indicado | CP-1 | Nenhuma: só ESH com harness | Investigado, não fechado |
| F2.1 | Autorização de início; F2.0-D concluída e CP-1 aprovado **ou** aceite seu, por escrito, de cada experimento não concluído; D1, D8, D9; D10 com CP-2 e CP-3 aceitos (se D10(d), decidir antes da F2.1) | CP-2, CP-3 | Nenhuma EDI | **Não bloqueia a entrada** |
| F2.2 | Autorização de início; F2.1 concluída e aceita; D9 para os arquivos do hook | CP-4 | Nenhuma EDI | Não bloqueia a entrada |
| F2.3 | Autorização de início; F2.2 concluída e aceita; alternativa de isolamento escolhida (D1; D2 se aplicável) com base na F2.0-D | CP-5 | EDI só dentro do confinamento em prova, com canários | **Fecha aqui, se provado** |
| F2.4 | Autorização de início; CP-5 aprovado; D7, DX-1, DX-2, DX-3 | CP-6 | Sem missão | Fechado ou aceito |
| F2.5 | Autorização de início; CP-6 aprovado; D4, D5, D6 | CP-7 | Sem missão real | idem |
| F2.6 | Autorização de início; CP-7 aprovado; primeira missão confirmada por você em TTY (D4) | CP-8 | Missão pequena, nível ≤ 2 | idem |
| F2.7 | Autorização de início; CP-8 aprovado | CP-9 | Missões do ensaio | idem |

## 3. Portões por etapa
Para cada etapa: (1) pré-requisitos para iniciar; (2) atividades permitidas; (3) critérios para concluir; (4) evidências exigidas; (5) condições de reprovação; (6) condições de pausa (além de P8); (7) autorizações humanas.

### F2.0-D0 — redação e revisão do harness (preparatória; **sem execução**) — nova na C.3
Existe para que o harness possa ser exigido como pré-requisito da F2.0-D sem que a F2.0-D precise escrevê-lo (AUD4-MED-1).
1. **Pré-requisitos:** autorização de início **por escrito**, específica da D0; **D3** com o escopo escolhido (define o que o harness precisa suportar; o pacote B não pode ser escolhido, `f2_0d_especificacao.md` §0); **D10** com CP-1 aceito (a revisão usa CP-1); a lista fechada de arquivos de `f2_0d_especificacao.md` §4.1 aceita por você.
0. **Estado (2026-11-18, 17:11):** o início da **preparação** da D0 foi autorizado pela sua mensagem de D10/D3; os itens do §4.1 (1 a 7) foram tomados como "locais expressamente autorizados" (**interpretação a confirmar por você**). D3 itens 2 a 6 seguem pendentes (local-base, tetos, criar e remover, modo do CC-local, reafirmação de §4.3 e §4.6): são exigidos na F2.0-D, **não** para escrever o harness.
2. **Permitido:** a NUV (Mario) **grava apenas** os arquivos de `f2d/` listados em §4.1 (itens 1 a 7 e, se o B vier a ser considerado, 8 e 9) e atualiza documentos em `agentes/laboratorio/f2/`. Peach revisa em sessão independente. Conferir os valores exatos das flags que o perfil B cita (Q30) é tarefa **de leitura de documentação**; **`claude --help` não foi rodado e não será na D0** (a autorização de 17:11 não o cobre); **nada mais é executado**, só leitura de arquivos. **Proibido:** executar o harness, qualquer experimento, `claude -p`, hook, teste; criar canário; escrever fora da lista.
3. **Concluir:** todos os arquivos da lista existem; **revisão CP-1H** (`criterios_peach_f2.md`: Mario → Luigi, só verificações estáticas e de integridade → Peach, independente → você) com aprovação, sem crítico nem importante aberto; **sua leitura** do código e dos documentos; hashes registrados em `hashes_aprovados.sha256` (gerado pelo Luigi) e **o hash desse arquivo anotado por você fora do repositório** (é o que **você** confere, em terminal próprio, antes de cada execução; `rodar_d.sh` não se verifica: `f2_0d_especificacao.md` §4.7). **Aprovação documental não é prova técnica nem autoriza experimento.**
4. **Evidências:** lista com hash de cada arquivo; resultado da Peach; sua confirmação por escrito de que leu.
5. **Reprova:** arquivo fora da lista; execução de qualquer item; hash não registrado; revisão feita por quem escreveu.
6. **Pausa:** P8; código maior do que você consegue revisar (reduzir o escopo de D3; o harness da D0 tem cerca de 1.100 linhas: **risco declarado**, H-24 do CP-1H).
7. **Autorizações humanas:** início da D0; lista de arquivos; sua aprovação do harness. **Concluir a D0 não autoriza a F2.0-D (P1).**

### F2.0-D — experimentos de isolamento e hipóteses abertas
1. **Pré-requisitos:** autorização expressa de início, em texto separado do de D3 e do da D0; **F2.0-D0 concluída** (harness, matriz e `hashes_aprovados.sha256` com hash anotado por você); **D3** inalterada desde a D0 (se mudou, voltar à D0); **D10** com CP-1 aceito antes de ver resultados (critérios ficam fixos); local-base dos canários indicado por você; tetos de sessões, custo, turnos e duração confirmados; modo do CC-local escolhido (`f2_0d_especificacao.md` §4.7).
2. **Permitido:** só os experimentos que você marcou em D3; o harness aprovado; CC-local (ou você, no modo 1) roda apenas `rodar_d.sh <ID>` depois de conferir `hashes_aprovados.sha256`; NUV grava `resultados_d.md` e atualiza documentos; criar e limpar canários no local-base. **Pacote B (X12 a X19): NÃO AUTORIZADO / BLOQUEADO**; só se desbloqueia pelas condições de `f2_0d_especificacao.md` §5B.2 e por uma decisão sua nova ("D3-B"). X20 e X21 só individualmente. **Proibido:** o que está em §4.3 da especificação.
3. **Concluir:** cada experimento autorizado tem resultado SUCESSO, FALHA ou INCONCLUSIVO conforme sua ficha; relatório com T/D/H/L atualizados; limpeza confirmada; snapshots sem alteração fora da área e do estado tolerado (§4.6 da especificação); CP-1 aprovado pela Peach.
4. **Evidências:** `tentativa.log` do harness (início e fim por tentativa); logs de listener e de canário; snapshots antes e depois (§4.6); stream-json lido pelo harness e logs de hook das sessões (se houver sessões); `limpeza.log`; `registro_criados.json`.
5. **Reprova a etapa:** violação de proibição; canário protegido **real** tocado; evidência só em relato de agente; harness sem registro de início e fim; ampliação sem decisão sua; execução de experimento não marcado; alteração de arquivo preexistente do escopo nomeado de `~/.claude`.
6. **Pausa:** P8; falha de montagem inesperada; canário alterado sem tentativa registrada; hash de `hashes_aprovados.sha256` divergente do que você anotou; CC-local pede comando fora do fixo (§4.7).
7. **Autorizações humanas:** início; D3; D10; local-base; aprovação do harness (na D0); login e iniciar sessões (HUM); aceite de qualquer experimento pulado; "D3-B" para qualquer sessão do pacote B.

### F2.1 — gerador de regras e manifesto de controle
1. **Pré-requisitos:** autorização de início; F2.0-D concluída e CP-1 aprovado, **ou** para cada experimento não concluído (incluindo todo o pacote B bloqueado), aceite do risco correspondente por você, por escrito; **D1** decidida (**(a) ou (b)**; (c) não é selecionável antes do CP-5); **D8**; **D9** (autorização de bootstrap por arquivo); **D10 com CP-2 e CP-3 aceitos** (se você escolheu D10(d), decidir CP-2 e CP-3 antes de entrar). **R1 aberto não bloqueia a entrada.**
2. **Permitido:** em **sessão de bootstrap** (`arquitetura_l0.md` §2A), o Mario escreve o gerador de regras `deny`, `tools` por agente, `--settings` por papel e o manifesto de controle, **somente nos arquivos da lista**; a Peach revisa o diff em sessão independente; testes **só por ESH**. **Não permitido:** ativar controles, rodar o L0, missão autônoma, Bash ou `pytest` autônomos, EDI.
3. **Concluir:** CP-2 e CP-3 satisfeitos; revisão da Peach (estruturada) sem crítico nem importante aberto; sua revisão do diff; nenhuma ativação.
4. **Evidências:** logs do harness dos testes ESH; hashes dos arquivos escritos; snapshot antes e depois da sessão de bootstrap (nenhuma escrita fora da lista); manifesto de controle e sua verificação por um byte alterado.
5. **Reprova:** escrita fora da lista; teste de equivalência com `protegidos.json` falha; controle que aprova a si mesmo; teste não registrado.
6. **Pausa:** P8; diff maior do que você consegue revisar (decidir reduzir o lote).
7. **Autorizações:** início; D9 por arquivo; sua revisão e sua ativação (a ativação não faz parte da F2.1).

### F2.2 — hook central
1. **Pré-requisitos:** autorização de início; F2.1 concluída e aceita por você; D9 para os arquivos do hook.
2. **Permitido:** bootstrap do hook; testes por ESH (allow, deny JSON, deny exit 2, script ausente, exit 1, timeout, identidade ausente, `Agent` fora da lista); hash dos controles a cada chamada. Não ativar em sessões de trabalho.
3. **Concluir:** CP-4 aprovado. A negação real de `Agent` precisa constar em log real: do X12 **se** o pacote B vier a ser desbloqueado e executado, **ou** (caminho previsto enquanto o B estiver bloqueado) de teste desta etapa por ESH. Também aqui vale D10 com CP-4 aceito.
4. **Evidências:** logs do hook e do stream-json; testes ESH; revisão da Peach.
5. **Reprova:** falha de qualquer variante de bloqueio; hook que registra conteúdo protegido.
6. **Pausa:** P8.
7. **Autorizações:** início; D9; sua revisão e ativação.

### F2.3 — perfis de Bash e invólucro de isolamento (prova do isolamento)
1. **Pré-requisitos:** autorização de início; F2.2 concluída e aceita; **alternativa de isolamento escolhida por você** (D1; D2 se for usuário Unix separado) com base nos resultados da F2.0-D; D9 para `isolar.py` e perfis.
2. **Permitido:** implementar `isolar.py` e perfis de Bash; provas com canários sintéticos (`plano_isolamento_r1.md` §7); EDI **somente** dentro do confinamento em prova e com ESH até o CP-5. Não é permitido tocar dados protegidos reais.
3. **Concluir:** CP-5 aprovado, com as **provas obrigatórias** do plano de isolamento (`plano_isolamento_r1.md` §9, 13 provas numeradas em §7: as obrigatórias **fecham** R1; as **informativas** não), cada uma com controle positivo e registro independente. **Só aqui R1 pode passar a "mitigado"**, e só a sua decisão (D1) o torna "aceito".
4. **Evidências:** logs do harness; canários; resultado estruturado da Peach.
5. **Reprova:** qualquer canário protegido lido ou escrito de dentro do confinamento; controle positivo ausente; prova não registrada.
6. **Pausa:** P8; confinamento só funcionar com permissões que exijam `sudo` (decisão sua).
7. **Autorizações:** início; D9; escolha da alternativa; aceitação do risco residual.

### F2.4 — `verificar_ambiente` e tratamento de runtime
1. **Pré-requisitos:** autorização de início; **CP-5 aprovado**; **D7**; **DX-1**; **DX-2**; **DX-3**; D9 para os arquivos novos.
2. **Permitido:** bootstrap do verificador; testes de falha fechada (versão, login, configuração extra, `disableAllHooks`, ferramentas extras, isolamento quebrado, exceções de runtime exatas).
3. **Concluir:** CP-6 aprovado.
4. **Evidências:** logs de cada falha induzida; revisão da Peach.
5. **Reprova:** qualquer falha induzida tratada como "ok".
6. **Pausa:** P8.
7. **Autorizações:** início; D7; DX-1; DX-2; DX-3; D9.

### F2.5 — núcleo do L0
1. **Pré-requisitos:** autorização de início; **CP-6 aprovado**; **D4**, **D5** (números decididos ou provisórios aceitos), **D6**; D9 para `l0.py`.
2. **Permitido:** bootstrap do núcleo; testes com sessões simuladas e Haiku; **nenhuma missão real**.
3. **Concluir:** CP-7 aprovado.
4. **Evidências:** logs de retomada, contadores, PEND, resultados da Peach inválidos tratados como INCONCLUSIVO, heartbeat.
5. **Reprova:** L0 que aceita resultado da Peach só por JSON válido; L0 que inicia etapa nova ou se autoriza.
6. **Pausa:** P8.
7. **Autorizações:** início; D4; D5; D6; D9.

### F2.6 — orquestração por papéis e relatório final
1. **Pré-requisitos:** autorização de início; **CP-7 aprovado**; primeira missão **pequena**, sem dados protegidos, revisada e **confirmada por você em TTY** (D4).
2. **Permitido:** missão de nível ≤ 2 dentro dos limites; EDI **somente** dentro do confinamento aprovado no CP-5.
3. **Concluir:** CP-8 aprovado; relatório final que **não** inicia a próxima subetapa.
4. **Evidências:** eventos externos do L0; gates rodados pelo L0; resultado estruturado e verificação mecânica.
5. **Reprova:** qualquer ação de nível 3 executada; missão que amplia o próprio escopo.
6. **Pausa:** P8; limites da missão atingidos.
7. **Autorizações:** início; confirmação da missão.

### F2.7 — ensaio adversarial, auditoria e congelamento
1. **Pré-requisitos:** autorização de início; **CP-8 aprovado**.
2. **Permitido:** tentativas de burlar os controles em canários; auditoria final; manifesto v003 em arquivo novo; congelamento.
3. **Concluir:** CP-9 aprovado e riscos residuais aceitos por você por escrito.
4. **Evidências:** logs do ensaio; auditoria da Peach; manifesto v003.
5. **Reprova:** qualquer tentativa bem-sucedida que não gere PEND; crítico ou importante aberto.
6. **Pausa:** P8.
7. **Autorizações:** início; aceite dos riscos residuais; congelamento.

## 4. Contradições corrigidas por este arquivo
1. Antes: "R1 aberto bloqueia a F2.1" (relatório F2.0-C.1 §6) e "R1 só fecha na F2.3". Agora: R1 bloqueia **EDI**, não a entrada em etapas; a prova é a F2.3.
2. Antes: o parecer exigia D1 a D10 inteiras antes da F2.1; a matriz dizia D4 a D7 só nas F2.4 e F2.5. Agora cada etapa lista só as decisões de que precisa.
3. Antes: a evidência necessária de R21 era o teste de R1 sem dizer em qual etapa. Agora: CP-1 investiga; CP-5 prova.
4. Antes: testes das F2.1 e F2.2 não diziam como seriam executados sem isolamento. Agora: **ESH** (P4).
5. Antes: D10 era dependência vaga. Agora: D10 é pré-requisito da **entrada** na F2.0-D0 (critérios fixos antes dos resultados) e cada etapa exige o seu CP aceito (D10(d)).
6. (C.3) Antes: o harness era pré-requisito da F2.0-D, mas só podia ser escrito nela (círculo). Agora: etapa **F2.0-D0**, sem execução.
7. (C.3) Antes: D1(c) liberava EDI por aceite, contra P3/P5. Agora: (c) não é selecionável antes do CP-5.
8. (C.3) Antes: o pacote B aparecia como autorizável por D3(b). Agora: **bloqueado**, com condições de desbloqueio e decisão própria (D3-B).
9. (C.3) Antes: "provas 1 a 8" no CP-5. Agora: obrigatórias e informativas entre as 13.
