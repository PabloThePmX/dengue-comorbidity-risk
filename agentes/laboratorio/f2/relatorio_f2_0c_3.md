# Relatório F2.0-C.3 — correção documental consolidada

**Natureza:** somente documental, dentro de `agentes/laboratorio/f2/`. Nada foi executado, testado ou implementado. **F2.0-D0, F2.0-D e F2.1 continuam bloqueadas.** Nenhuma decisão (D1–D10, DX-1 a DX-3, D3-B) foi autorizada. R1 continua **ABERTO**. Este relatório **não** traz o veredito da Peach; ele fica em `parecer_peach_f2_0c_3.md`.

Origem: `parecer_peach_f2_0c_2.md` (AUD4: 0 críticos, 3 altos, 8 médios, 6 baixos). Redator: Mario (documental). Verificação de integridade: Luigi. Auditoria: Peach (outra etapa).

## 1. Decisão de projeto mais importante desta rodada
**O pacote B (X12 a X19) passou a NÃO AUTORIZADO / BLOQUEADO.** Motivo: não existe hoje garantia técnica de que as sessões `claude -p` fiquem contidas (conectores da conta, repositório com dados protegidos ao alcance do mesmo usuário Unix, estado em `~/.claude`). O perfil de contenção que escrevi (`--agent`, `--tools`, `--strict-mcp-config`, `dontAsk`, cwd dedicado, verificação do `init`) é **proposta H e não prova contenção**. A única barreira técnica prevista é o `bwrap` em volta do `claude` (X21), que depende de X20 e de provas de `bwrap` ainda não feitas. O desbloqueio exige seis condições (`f2_0d_especificacao.md` §5B.2) e uma decisão sua nova, **"D3-B"**.

## 2. Arquivos
**Criado (1):** `relatorio_f2_0c_3.md`. *(O pedido permitia só este documento novo. Também foi copiado para `f2/` o `parecer_peach_f2_0c_2.md`, já existente no disco do projeto, para manter a pasta de trabalho idêntica a ele.)*
**Reescrito (1):** `f2_0d_especificacao.md`.
**Alterados (13):** `portoes_f2.md`, `matriz_decisoes_humanas.md`, `plano_isolamento_r1.md`, `criterios_peach_f2.md`, `registro_riscos.md` (R34 a R37; R3 e R10 com status da legenda), `questoes_abertas.md` (Q30 a Q33), `rastreabilidade.md` (seção AUD4), `matriz_autonomia.md` (nota sobre D1), `limitacoes.md` (nota em R-L1), `parecer_f2_0.md` (§10), `roadmap_f2_revisado.md`, `relatorio_f2_0c_2.md` (nota C.3), `LEIA-ME.md`.
**Não tocados:** `bin/`, `cfg/`, `evidencias/`, `sintetico/`, `saida/`, manifestos, `DECISOES.md`, qualquer coisa fora de `f2/`.
Histórico preservado: onde o texto da C.2 mudou, o novo texto traz a nota "C.3" ou "Correção C.3" dizendo o que havia antes.

## 3. Tratamento dos achados (resumo; detalhe em `rastreabilidade.md` §5A)
| Achado | Tratamento | Estado |
|---|---|---|
| AUD4-ALTO-1 contenção do B | Perfil proposto; B bloqueado; condições de desbloqueio; XB0; verificação do `init` contra `mcp__*`/Drive | CORRIGIDO-DOC (bloqueio). **Contenção técnica não demonstrada** |
| AUD4-ALTO-2 X20/X21 | Fichas completas; fora de pacote; X20 pré-requisito do B | CORRIGIDO-DOC |
| AUD4-ALTO-3 `~/.claude` e snapshot | Exceção estreita; escopo nomeado; snapshot e diff definidos; `CLAUDE_CONFIG_DIR` via X20 | CORRIGIDO-DOC; lista de subdiretórios de estado ainda por confirmar (Q32) |
| AUD4-MED-1 círculo do harness | Etapa **F2.0-D0**, sem execução | CORRIGIDO-DOC |
| AUD4-MED-2 lista de arquivos / canário no repo | Lista fechada (§4.1); canários fora do repositório | CORRIGIDO-DOC |
| AUD4-MED-3 `deny` × `allow` (X13) | Três braços; o braço com `allow` e `deny` juntos é a prova | CORRIGIDO-DOC |
| AUD4-MED-4 registro independente do B | stream-json lido pelo harness é o primário; hook corrobora | CORRIGIDO-DOC |
| AUD4-MED-5 D1(c) × P3/P5 | D1(c) não selecionável antes do CP-5 | CORRIGIDO-DOC |
| AUD4-MED-6 provas do CP-5 | 13 provas, obrigatórias e informativas | CORRIGIDO-DOC (classificação é proposta) |
| AUD4-MED-7 limpeza | Registro de criação; nome aleatório; `lstat`; PID com hora de início; recusa com arquivo preexistente | CORRIGIDO-DOC |
| AUD4-MED-8 CC-local | Modo 1 (você digita) ou modo 2 (aprovação por comando); hash conferido; comando fora do fixo = pausa | CORRIGIDO-DOC; limite L declarado |
| AUD4-BAIXO-1 a 6 | Corrigidos conforme `rastreabilidade.md` | CORRIGIDO-DOC |

## 4. O que permaneceu aberto (nada foi provado)
- **R1 aberto.** Toda a contenção é H: `bwrap` com allowlist, Landlock, usuário separado.
- **Pacote B bloqueado.** Desbloqueá-lo exige X20 e (X21 ou aceite seu de que não há contenção técnica), XB0, revisão da Peach e "D3-B". Nenhuma dessas condições foi cumprida.
- **Flags** do perfil B (`--setting-sources`, `--tools ""`, `--agents`, `dontAsk`): valores exatos **não conferidos** na 2.1.327 (Q30). Efeito de `--strict-mcp-config` sobre os conectores da conta: **desconhecido** (Q31).
- **Subdiretórios de estado** de `~/.claude` tolerados: proposta, não confirmada (Q32). Revogação do login criado em X20: não verificada (Q33).
- O snapshot **detecta, não impede**, e não cobre o restante do repositório (sem `.git`).
- Modo 2 do CC-local depende da sua atenção a cada aprovação.
- Texto original das auditorias AUD0 a AUD3 continua ausente; as lacunas continuam NÃO VERIFICÁVEIS.
- Dados (hashes, tetos, local-base) são **propostas**: tetos de B (24 sessões, US$ 1,00) só valem se o B for desbloqueado.

## 5. Decisões humanas ainda necessárias
Ordem sugerida: **D10** (ao menos CP-1) → **D3** (escopo do pacote A; local-base; modo do CC-local) → autorização de início da **F2.0-D0** → revisão do harness por Peach e por você → autorização de início **separada** da F2.0-D. D3 **não** inicia nada. D1, D8, D9 antes da F2.1; D7, DX-1 a DX-3 na F2.4; D4 a D6 na F2.5. Pacote B só por "D3-B", depois das condições. DP-001, Etapa 3.2 (sem aprovação científica) e Etapa 3.3 (não autorizada) seguem fora.
**D10 e D3 já podem ser submetidas à decisão humana?** Esta é a pergunta da Peach na C.3; este relatório não a responde.

## 6. Confirmação de conduta
Nada foi executado: nem X01–X21, nem sessões `claude -p`, nem hooks ou testes. Não implementei harness nem isolamento. Não alterei configurações do Claude Code, não instalei nada, não alterei permissões ou usuários, não usei `sudo`. Não acessei dados de 2024, nem protegidos, nem manifestos. Não escrevi fora de `agentes/laboratorio/f2/`. Não fiz commit nem push. Não iniciei F2.0-D0, F2.0-D nem F2.1.

## 7. Verificação (Mario, antes da entrega à verificação do Luigi)
Script de leitura sobre os arquivos de `f2/`: matriz de autonomia com linhas 1 a 54 sem salto; R1 a R37 sem salto e R1 **ABERTO**; Q1 a Q33 em ordem; nenhuma referência a R, D, Q, CP, X ou HD acima do máximo; X01 a X21 com uma ficha cada, em ordem; X20 e X21 com todos os campos; pacote B marcado BLOQUEADO em especificação, portões e matriz de decisões; F2.0-D0, F2.0-D e F2.1 bloqueadas; nenhuma decisão marcada como autorizada; "provas 1 a 8" só em citações do achado antigo. Esta verificação é minha; a conferência independente de gravação (cmp contra o disco do projeto) e a auditoria são das etapas seguintes.
