# Consolidação F2.0-C

> **Atualização F2.0-C.2:** os portões vigentes estão em `portoes_f2.md`.

> **Atualização F2.0-C.1:** este documento descreve a F2.0-C. A correção seguinte está em `relatorio_f2_0c_1.md`. Pontos desatualizados abaixo: decisões agora são **D1 a D10** (não D1 a D8); a errata do `plano.md` da seção 4 **foi aplicada** no próprio `plano.md` e no `LEIA-ME.md` foi atualizado.

Índice, lista de arquivos alterados e criados, errata e relatório final. A F2.1 **não** foi iniciada e nenhum controle definitivo foi implementado.

## 1. Arquivos alterados (autorizados na seção 2)
| Arquivo | Mudança |
|---|---|
| `parecer_f2_0.md` | Substituído pela versão corrigida (a do disco estava desatualizada, C1) |
| `resultados.md` | Linhas B3 corrigidas (I1, I2, I3, I5, I6), nova seção B4 com as correções da auditoria, texto de integridade corrigido |
| `limitacoes.md` | R-L5, H-09, H-10, H-13, R12, R13 reescritos; nova seção 7 |

## 2. Arquivos criados (todos em `agentes/laboratorio/f2/`)
`registro_riscos.md`, `matriz_autonomia.md`, `arquitetura_l0.md`, `plano_isolamento_r1.md`, `matriz_decisoes_humanas.md`, `roadmap_f2_revisado.md`, `criterios_peach_f2.md`, `questoes_abertas.md`, `consolidacao_f2_0c.md`.

## 3. Entregáveis pedidos → arquivo
1 parecer corrigido → `parecer_f2_0.md`; 2 registro de riscos → `registro_riscos.md`; 3 matriz de autonomia → `matriz_autonomia.md`; 4 L0 → `arquitetura_l0.md`; 5 isolamento R1 → `plano_isolamento_r1.md`; 6 decisões humanas → `matriz_decisoes_humanas.md`; 7 roadmap → `roadmap_f2_revisado.md`; 8 critérios da Peach → `criterios_peach_f2.md`; 9 questões abertas → `questoes_abertas.md`; 10 lista de arquivos → este documento.

## 4. Errata do `plano.md` (não autorizado a editar)
`plano.md` afirma que um mecanismo de integridade "cobre v001 e v002". Tamanho e data de modificação iguais provam apenas que **esses metadados não mudaram**, não integridade byte a byte. Vale a redação de `parecer_f2_0.md` §3. `plano.md` ficou sem alteração.

## 5. Não feito (por limite)
Nenhum experimento novo; v001 e v002 não foram abertos, recalculados nem alterados; sem hooks, `settings.json`, agentes definitivos, instalação, `sudo`, configuração global; sem acesso a dados protegidos; sem commit/push.

## 6. Relatório final
**O que foi corrigido.** Parecer desatualizado (C1); Glob/Grep, agora "ausentes por padrão, documentado" e não "inexistentes" (I1); spawn sem teste real de negação (I2); `deny` prevalece sobre `allow` do hook no caso do `cat` (I3); sandbox não passou na verificação inicial (I5) e relação com `.cc-writes` é só correlação (I6); relato de agente não é evidência (I7); limite de tentativas (I8); orçamento e retomada (I9); integridade por tamanho/data reescrita; R12 e R13 reescritos. Lacunas C2 e C3 viraram riscos R18 a R21.

**Riscos que permanecem.** R1 (subprocesso sem isolamento comprovado), reload de configuração, socket de mensagens, conectores, processos filhos alterando controles, sombreamento, logs incompletos, rate limit, tentativas após bloqueios e exceções de runtime. Detalhe em `registro_riscos.md`. Quase todas as mitigações ainda são H.

**Como a arquitetura reduz a intervenção humana.** Você autoriza uma missão uma vez; o L0 externo conduz Yoshi, Mario, Luigi e Peach, roda os gates, repete ciclos até o limite, pausa e retoma por rate limit, registra evidências e entrega o relatório final. Sem pedidos por comando, teste, correção ou delegação (`matriz_autonomia.md`).

**O que ainda exige autorização.** Dados protegidos e 2024; mudança científica ou de escopo; dependências; `sudo` e sistema; alterar controles; ações irreversíveis e publicação; aceitar risco residual; iniciar qualquer subetapa nova (`matriz_decisoes_humanas.md`).

**Viabilidade no ambiente atual.** Viável para ferramentas de arquivo, hooks, identidade por `--agent` e sessões por papel (T). **Não provada** para isolamento do Bash: o sandbox do Claude Code não funciona aqui, e o `bwrap` direto passou só em teste mínimo. Autonomia total depende da F2.0-D.

**O que implementar primeiro (após sua autorização).** F2.0-D (provas de isolamento e hipóteses); em seguida F2.1, F2.2, F2.3 e o núcleo do L0 (F2.5), nessa ordem (`roadmap_f2_revisado.md`).

**Decisões suas agora.** D1 a D10 em `matriz_decisoes_humanas.md`, em especial D1 (aceitar ou não R1) e D3 (autorizar a F2.0-D).

Parado aqui, aguardando sua autorização expressa.
