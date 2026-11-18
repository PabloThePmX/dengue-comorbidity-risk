# Laboratório F2.0 — documentação de entrada

Experimentos controlados do Claude Code para a F2 (agentes `feat/soneca`). **Nada aqui é hook, agente ou configuração definitiva.** Os experimentos e evidências são sintéticos; os documentos de arquitetura e decisão desta pasta são **de projeto** e não devem ser apagados com o laboratório (limite de escopo: não foram movidos).

**Estado:** F2.0 executada; F2.0-C, C.1, C.2 e C.3 são correções documentais. **Estado F2.0-D0 (2026-11-18, 17:11):** **D10 aceita com complemento** (CP-1 + CP-1H, revisão do código do harness) e **D3 = pacote A (X01 a X11) só para preparar a D0**. O harness foi escrito e **nunca executado**; **X01 a X11 NÃO estão autorizados a rodar**. **F2.0-D e F2.1 estão bloqueadas** e dependem de autorização humana expressa e separada. **D1, D2, D4 a D9, DX-1, DX-2, DX-3 e os itens 2 a 6 de D3 seguem sem decisão.** R1 (isolamento) continua aberto. O **pacote B** (sessões `claude -p`, X12–X19) está **NÃO AUTORIZADO / BLOQUEADO**; X20 e X21 estão fora de qualquer pacote e **fora da D3**. Etapa 3.2 sem aprovação científica. Etapa 3.3 não autorizada.

**Fonte normativa dos portões:** `portoes_f2.md`. Se outro documento divergir dele, vale `portoes_f2.md`.

## Ordem de leitura sugerida
1. `relatorio_f2_0c_3.md`: resumo da correção documental mais recente e lista de arquivos (depois, `parecer_peach_f2_0c_3.md`, se já existir).
2. `portoes_f2.md`: tabela única de portões da F2.0-D à F2.7.
3. `matriz_decisoes_humanas.md`: D1 a D10 e DX-1 a DX-3 (o que você precisa decidir). Comece por D3 e D10.
4. `f2_0d_especificacao.md`: o que a D3 escolheria, experimento por experimento; perfil e bloqueio do pacote B.
5. `parecer_f2_0.md`: conclusão técnica da F2.0, com as atualizações.
6. `matriz_autonomia.md`, `arquitetura_l0.md`, `plano_isolamento_r1.md`: o desenho (tudo H, não implementado).
7. `registro_riscos.md`, `limitacoes.md`, `resultados.md`: riscos, limites e resultados reais.
8. `criterios_peach_f2.md`, `questoes_abertas.md`, `rastreabilidade.md`.

## Índice de arquivos
| Arquivo | Conteúdo |
|---|---|
| `portoes_f2.md` | **Normativo.** Portões de cada etapa, de F2.0-D0 a F2.7 (pré-requisitos, atividades, conclusão, evidência, falha, pausa, autorizações) |
| `f2_0d_especificacao.md` | Escopo fechado proposto para a F2.0-D: hipóteses HD, experimentos X01–X21, executores, lista fechada de arquivos, snapshot, limpeza, CC-local, pacote B bloqueado |
| `plano.md` | Plano dos experimentos F2.0 (com errata de integridade no topo) |
| `resultados.md` | Resultados E01 a E11, correções B4 a B6 |
| `limitacoes.md` | Hipóteses e limites (seções 1 e 2 são histórico; valem 6 a 9) |
| `parecer_f2_0.md` | Parecer técnico F2.0 |
| `registro_riscos.md` | Riscos R1 a R40 |
| `matriz_autonomia.md` | Autonomia: alvo × comprovado hoje (54 linhas) |
| `arquitetura_l0.md` | L0 externo, autorização, bootstrap |
| `plano_isolamento_r1.md` | Isolamento R1 por allowlist |
| `matriz_decisoes_humanas.md` | D1 a D10, DX-1 a DX-3 (D10 e D3 registradas em 17:11) |
| `roadmap_f2_revisado.md` | Resumo curto que aponta para `portoes_f2.md` |
| `criterios_peach_f2.md` | Critérios CP-1 a CP-9 e **CP-1H** (revisão do código do harness; **não** existe `criterios_aprovacao.md`) |
| `questoes_abertas.md` | Q1 a Q36 |
| `rastreabilidade.md` | Achados das auditorias da Peach, com IDs únicos |
| `consolidacao_f2_0c.md` | Consolidação F2.0-C (histórico; portões superados) |
| `relatorio_f2_0c_1.md` | Relatório da F2.0-C.1 (histórico; portões superados) |
| `relatorio_f2_0c_2.md` | Relatório da F2.0-C.2 (histórico; com nota C.3) |
| `relatorio_f2_0c_3.md` | Relatório da F2.0-C.3 |
| `parecer_peach_f2_0c_2.md`, `parecer_peach_f2_0c_3.md` | Pareceres da Peach (auditorias C.2 e C.3) |
| `relatorio_f2_0d0.md` | Relatório da F2.0-D0 (decisões registradas, harness preparado, lista de arquivos, verificações, limites) |
| `f2d/` | Harness da D0 (**não executado**): `harness.py`, `landlock_launcher.py`, `rodar_d.sh`, `limpar.sh`, `matriz_d.json`, `testes_x08/`, `hashes_aprovados.sha256` |
| `parecer_peach_f2_0c_2.md` | Parecer da Peach sobre a F2.0-C.2 (quarta auditoria, AUD4) |
| `parecer_peach_f2_0c_3.md` | Parecer da Peach sobre a F2.0-C.3 (só existe se a auditoria da C.3 foi concluída) |
| `bin/`, `cfg/`, `evidencias/`, `sintetico/`, `saida/` | Scripts, configuração de laboratório, evidências, canários, saídas |

## Rodar o laboratório (somente se autorizado)
`bash agentes/laboratorio/f2/bin/rodar.sh tudo` a partir da raiz do repositório.
Opcional (E10a): copiar `cfg/lab-sombra.md.modelo` para `.claude/agents/lab-sombra.md` aqui dentro; remover depois.
`evidencias/LEIA-ME.md` é outro arquivo (pasta de evidências), não esta entrada.
