# Relatório da F2.0-D0 (preparação do harness do pacote A)

**Data:** 2026-11-18. **Autor:** Mario (NUV). **Declaração:** **nenhum experimento foi executado.** Nem X01 a X21, nem `claude -p`, nem login, nem o harness. Mario rodou só leituras estáticas (`ast.parse`, `bash -n`, `grep`, contagens). X01 a X11 **não estão autorizados a rodar**; a F2.0-D espera autorização expressa e separada sua.

## 1. Decisões registradas (sua mensagem de 2026-11-18, 17:11)
| Decisão | Registro | Alcance |
|---|---|---|
| D10 | ACEITA COM COMPLEMENTO: critérios + revisão obrigatória do código do harness antes de qualquer experimento (CP-1H) | Leitura adotada: só CP-1 e CP-1H (Q34). CP-2 a CP-9 **não** foram aceitos |
| D3 | Pacote A (X01 a X11) | Autoriza **só a preparação da D0**. Itens 2 a 6 de D3 pendentes (Q35) |
| Mantidas | Pacote B: NÃO AUTORIZADO / BLOQUEADO. X20 e X21: fora da D3. R1: ABERTO | Nenhuma prova técnica de isolamento presumida |

## 2. As cinco médias da auditoria C.3 (AUD5-MED-1 a 5)
Incorporadas sem nova rodada de planejamento. Detalhe em `rastreabilidade.md` §5B. Todas **corrigidas documentalmente**; a lista de estado tolerado do CLI continua hipótese (Q32) e o hash do próprio harness continua sendo conferido por você (AUD5-MED-3, parcial). Também tratados: AUD5-BAIXO-1, 3, 4, 5, 6 (parcial), 7, 8 e 9. **AUD5-BAIXO-2 segue aberto** (editorial).

## 3. Arquivos
**Criados** em `agentes/laboratorio/f2/` (todos novos; nada existente foi movido, renomeado ou apagado):
- `f2d/harness.py` (1121 linhas), `f2d/landlock_launcher.py` (82), `f2d/rodar_d.sh` (23), `f2d/limpar.sh` (17), `f2d/matriz_d.json` (106), `f2d/testes_x08/test_soma.py` (7), `f2d/testes_x08/test_ler_canario.py` (10)
- `relatorio_f2_0d0.md` (este)
- `f2d/hashes_aprovados.sha256` (gerado pelo Luigi) e `parecer_peach_f2_0d0.md` (Peach): ver o relatório consolidado do Yoshi

**Alterados:** `matriz_decisoes_humanas.md`, `criterios_peach_f2.md` (CP-1H, H-01 a H-26), `f2_0d_especificacao.md`, `portoes_f2.md`, `plano_isolamento_r1.md` (só cabeçalho), `LEIA-ME.md`, `roadmap_f2_revisado.md`, `rastreabilidade.md` (§5B AUD5), `registro_riscos.md` (R38 a R40), `questoes_abertas.md` (Q34 a Q36).

## 4. Verificações feitas por Mario (leitura, sem executar o harness)
- `ast.parse` em `harness.py` e `landlock_launcher.py`: sintaxe válida. `bash -n` em `rodar_d.sh` e `limpar.sh`: sintaxe válida.
- `grep` por padrões proibidos no código (`shell=True`, `rm -rf`, `rmtree`, `pkill`, `sudo`, rede externa, caminhos de 2024 ou manifestos): só ocorrências em comentários e na lista `NAO_HASHEAR`.
- Consistência dos documentos: R1 a R40 sem salto (R1 ABERTO); Q1 a Q36 sem salto; matriz de autonomia 1 a 54; fichas X01 a X21 uma vez cada; nenhuma referência a R, Q ou X acima do máximo; nenhuma etapa além da D0 marcada como autorizada.
- Estas verificações são do autor. A conferência independente é do Luigi (integridade) e da Peach (CP-1H).

### 4B. Verificações estáticas do Luigi (2026-11-18; só os comandos 1 a 8 de `criterios_peach_f2.md`; nada foi executado)
- Comando 1 (`ast.parse` em memória, `python3 -I`, 4 arquivos .py): `sintaxe ok`; nenhum `__pycache__` criado (conferido com `find`).
- Comando 2 (`bash -n` em `rodar_d.sh` e `limpar.sh`): sintaxe ok.
- Comando 3: `f2d/hashes_aprovados.sha256` gerado com os 7 arquivos (não inclui ele mesmo). SHA-256 do próprio `hashes_aprovados.sha256` (esta versão): `d736afa263b7da17d0b90d7d2413aca01dbf5127994c962e0ef4f068e214b315`. **O hash que vale é o que você anotar por conta própria depois de ler o código; este valor é só do momento da geração.**
- Comando 4 (padrões proibidos): 2 ocorrências, ambas em comentário/docstring (`landlock_launcher.py` l.9 menciona `chmod`; `harness.py` l.982 menciona `rm -rf`/`pkill` em comentário).
- Comando 5 (imports): só biblioteca padrão; `harness.py` l.14-33 e os imports dentro dos scripts de sonda (l.527-598); `landlock_launcher.py` l.14-17 (`ctypes`, `os`, `struct`, `sys`).
- Comando 6 (`socket`): l.24, 565-575 (sonda), 762-770 (X05), 895-896 (X10). Julgamento de H-03 fica com a Peach.
- Comando 7 (X12–X21/XB0): só recusa em `harness.py` l.7 e 1076, `rodar_d.sh` l.17, lista de recusados em `matriz_d.json`; l.339 é um texto de relato de D7/X17, não código de X17.
- Comando 8: `harness.py` 1121 linhas, `landlock_launcher.py` 82, `rodar_d.sh` 23, `limpar.sh` 17, testes 10 e 7. `ls -R f2d/` mostra só os 8 arquivos da lista.
- Limite: estas verificações mostram sintaxe, hashes e ausência de padrões; **não** mostram comportamento. O harness nunca rodou.

## 5. Limitações e riscos abertos
- O harness **nunca rodou**; comportamento de `bwrap`, Landlock, pty e canários é H (Q36).
- Tamanho (cerca de 1.100 linhas) pode passar do que você revisa com conforto (R39, H-24). Se passar, a regra P8 manda reduzir o escopo de D3.
- Interpretações a confirmar por você: escopo de D10 (Q34); lista do §4.1 como "locais expressamente autorizados" (Q35).
- D3 itens 2 a 6, D1, D2, D4 a D9, DX-1 a DX-3, DP-001 e Etapas 3.2 e 3.3: sem decisão.
- X20 e X21: sessões sem contenção comprovada; proteção de credenciais só procedimental (R38).
- O commit deste material no dispositivo usa `device_commit_files`, o fluxo já estabelecido (não é git; o repositório não tem `.git`).

## 6. Necessidades fora do escopo
Nenhuma que exija interromper a D0. O que o harness precisaria para rodar (local-base, tetos, modo do CC-local, `bwrap` instalado) **não** foi pedido nem criado; fica para a F2.0-D, se você a autorizar.
