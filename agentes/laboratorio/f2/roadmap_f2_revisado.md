# Roadmap F2 revisado (F2.0-C.3; estado D0 em 2026-11-18)

**Fonte normativa de portões: `portoes_f2.md`.** Este roadmap só resume. Em caso de conflito, vale `portoes_f2.md`. Todas as etapas estão **bloqueadas** até autorização humana expressa para cada uma. Nenhuma etapa inicia a seguinte. Esforço e datas não estimados.

## Ordem única
F2.0-D0 → F2.0-D → F2.1 → F2.2 → F2.3 → F2.4 → F2.5 → F2.6 → F2.7. O isolamento é **investigado** na F2.0-D e **provado** na F2.3. R1 bloqueia execução dependente de isolamento, não a entrada em etapas (`portoes_f2.md` P3 e P5).

## Mapa
| Etapa | Conteúdo | Critério | Observação |
|---|---|---|---|
| F2.0-D0 | Redação e revisão do harness e da lista fechada de arquivos (**sem execução**) | revisão CP-1H (Mario, Luigi, Peach), sua leitura, hashes | Nova na C.3; **autorizada só a preparar (17:11)**; harness escrito, não executado; `portoes_f2.md` |
| F2.0-D | Experimentos do escopo fechado de D3 (**pacote A**); **pacote B bloqueado**; X20/X21 só individualmente | CP-1 | `f2_0d_especificacao.md`; só dados sintéticos; sem `sudo` |
| F2.1 | Gerador de regras `deny`, `tools` por agente, `--settings` por papel, manifesto de controle | CP-2, CP-3 | Bootstrap D9; testes só por ESH |
| F2.2 | Hook central: identidade, política, lista de `Agent`, `onFailure: "block"`, hash a cada chamada | CP-4 | Bootstrap D9; testes por ESH |
| F2.3 | Perfis de Bash e invólucro de isolamento; prova com canários | CP-5 | R1 pode fechar aqui, se provado |
| F2.4 | `verificar_ambiente` e exceções de runtime | CP-6 | D7, DX-1, DX-2, DX-3 |
| F2.5 | Núcleo do L0 | CP-7 | D4, D5, D6 |
| F2.6 | Orquestração por papéis e relatório final; primeira missão pequena | CP-8 | Missão confirmada por você em TTY |
| F2.7 | Ensaio adversarial, auditoria, manifesto v003, congelamento | CP-9 | Riscos residuais aceitos por você por escrito |

## O que mudou
1. O portão de cada etapa é único (`portoes_f2.md`), com pré-requisitos, atividades, conclusão, evidências, reprovação, pausa e autorizações.
2. A F2.1 não é bloqueada por R1 aberto; Bash e `pytest` autônomos continuam bloqueados até o CP-5.
3. Testes de controles antes do CP-5 só por ESH.
4. D10 (CP-1) vem antes da F2.0-D0 e da F2.0-D; cada CP seguinte é aceito antes da sua etapa.
5. (C.3) O pacote B (sessões `claude -p`) está **NÃO AUTORIZADO / BLOQUEADO** até X20, X21 (ou aceite expresso) e XB0, e uma decisão nova "D3-B".

## Depois (F3–F6)
O plano de F3 a F6 consta de documentos fora de `f2/` e **não foi relido** nesta etapa. Só começam com missões autorizadas sobre o sistema congelado. Nenhuma decisão científica (Etapa 3.2, DP-001) depende deste roadmap, e ele não decide sobre elas.

## Primeiro passo técnico recomendado (após sua autorização)
Decididos em 17:11: D10 (aceita com complemento CP-1H) e D3 (pacote A, só para preparar a D0). **Faltam:** sua leitura e aprovação do harness; anotar o hash de `hashes_aprovados.sha256`; D3 itens 2 a 6; D1, D2, D4 a D9; autorização de início **separada** da F2.0-D. X01 a X11 **não** foram autorizados a rodar.
