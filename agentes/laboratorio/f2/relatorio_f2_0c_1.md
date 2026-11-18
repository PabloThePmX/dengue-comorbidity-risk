# Relatório F2.0-C.1 — correção documental e preparação das decisões humanas

> **Atualização F2.0-C.2:** os portões desta versão (seção 6, "R1 aberto bloqueia a F2.1") foram **substituídos** por `portoes_f2.md`. D3 e CP-1 foram reescritos. Este relatório fica como registro histórico.

Etapa **somente documental**. Nada foi executado: nenhum experimento, hook, configuração, instalação, `sudo`, commit, push ou acesso a dados protegidos. v001, v002, `DECISOES.md`, resultados científicos, modelo e dados não foram tocados. F2.0-D e F2.1 continuam **bloqueadas**. D1 a D10 **não estão autorizadas**.

## 1. Correções realizadas
- **A1 bootstrap:** `arquitetura_l0.md` §2A; D9; R29.
- **A2 autorização de missão:** `arquitetura_l0.md` §2 (resumo legível, TTY, arquivo fora do alcance dos agentes, verificação antes de executar; HMAC insuficiente contra o mesmo usuário); D4 revisada; R30.
- **A3 decisão por evidências:** `criterios_peach_f2.md` §2 a §4 (resultado estruturado, três aprovações distintas, regras de crítico e importante, INCONCLUSIVO); linha 38 da matriz alinhada; R31.
- **A4 proteção preventiva:** `arquitetura_l0.md` §10 e `plano_isolamento_r1.md` §6 (confinar o `claude` inteiro, controles somente leitura, verificação por chamada e por evento, falha encerra, limites dos hashes); entrou no escopo da F2.0-D; R32.
- **A5 allowlist:** `plano_isolamento_r1.md` (tabela de 12 itens, cinco tipos de proteção, canários fora do repositório, hardlink e symlink); R33.
- **M1 a M9:** ver `rastreabilidade.md`. Em especial: flags reclassificadas como D (confirmado em `rodar.sh`), `limitacoes.md` com histórico marcado, R16 desambiguado (R-L16), I4 acrescentado a `resultados.md` B4, exceção de runtime só por caminho exato, proveniência do `resumo.md`, ordem do roadmap unificada, critérios renomeados CP-1 a CP-9.
- **Matriz de autonomia:** coluna "Hoje (comprovado)", seção 0 (alvo × comprovado), linhas 51 a 54 novas. Enquanto R1 está aberto, Bash e `pytest` seguem nível 3.
- **D1 a D10:** reescritas com pergunta, contexto, alternativas, consequências, recomendação, riscos, dependências e o que cada alternativa autoriza. D9 e D10 incluídas. DX-1 e DX-2 como decisões complementares.
- **Correção de uma afirmação minha:** a F2.0-C dizia que as reservas N1–N7/B4 estavam "tratadas" nos critérios. Não havia base; foi retirado e registrado como pendente.

## 2. Arquivos
**Alterados (existentes):** `LEIA-ME.md`, `plano.md` (errata e frase de integridade), `parecer_f2_0.md`, `resultados.md`, `limitacoes.md`, `registro_riscos.md`, `matriz_autonomia.md`, `arquitetura_l0.md`, `plano_isolamento_r1.md`, `matriz_decisoes_humanas.md`, `roadmap_f2_revisado.md`, `criterios_peach_f2.md`, `questoes_abertas.md`, `consolidacao_f2_0c.md`.
**Criados:** `rastreabilidade.md`, `relatorio_f2_0c_1.md`.
Todos em `agentes/laboratorio/f2/`. Caminho do `LEIA-ME.md` confirmado: `agentes/laboratorio/f2/LEIA-ME.md` (o `evidencias/LEIA-ME.md` é outro arquivo e não foi alterado).

## 3. Achados resolvidos
Tratados **no papel** (texto corrigido): A1 a A5, M1, M2, M4 a M9, B2, C1 (parecer), I1 a I9, R12, R13. **Nenhum foi resolvido por prova técnica.** Quase tudo o que é desenho de L0, isolamento e bootstrap é H.

## 4. Achados pendentes
- **M3, rastreabilidade parcial:** o texto original da primeira auditoria (M5, M7, N1–N7 e a matriz de 41 linhas) não está em `f2/`. Q21 e Q22.
- **B1:** documentos de projeto seguem numa pasta chamada "laboratório" (mover é decisão sua).
- **Causas não apuradas:** defeito de entrega C1 (Q20); origem de `.cc-writes` (Q6).
- Provas técnicas A4 e A5 (F2.0-D).

## 5. Decisões que dependem de você
D1 (risco R1), D2 (usuário Unix), D3 (F2.0-D e local dos canários), D4 (autorização de missão), D5 (limites), D6 (estado do L0), D7 (exceções de runtime), D8 (matriz de autonomia), D9 (bootstrap), D10 (critérios da Peach), mais DX-1 (versão do Claude Code) e DX-2 (recálculo de hashes). Detalhe em `matriz_decisoes_humanas.md`. DP-001 e Etapa 3.2 continuam sem decisão e fora desta etapa.

## 6. Riscos que continuam bloqueando
- **F2.0-D:** D3 não decidida; local dos canários não indicado.
- **F2.1:** R1 aberto; R18 a R21 sem prova; R29 (D9) e R30 (D4) sem decisão; CP-1 não cumprido; D8, D10 sem decisão.

## 7. Verificação documental
Feita **relendo o conteúdo do disco do computador** depois da gravação (não só o tamanho). O resultado está na seção 8 deste relatório, escrita após a verificação.

## 8. Resultado da verificação
Após gravar os 16 arquivos, reli do disco do computador (cópia obtida do dispositivo) e conferi:
- **Conteúdo:** cada um dos 16 arquivos é **idêntico byte a byte** à versão mestre (comparação por conteúdo, não só tamanho).
- **Referências cruzadas:** todos os `.md` citados existem (exceções esperadas: `resumo.md` em `evidencias/`, e `PEND-nnn.md`, `relatorio_final.md`, que são arquivos futuros do L0); R1 a R33, D1 a D10, Q1 a Q25 e CP-1 a CP-9 não ultrapassam os limites existentes.
- **Identificadores:** matriz de autonomia com linhas 1 a 54 sem salto; registro de riscos com R1 a R33 sem salto; questões Q1 a Q25 sem salto; D1 a D10 presentes uma vez cada. Referências antigas a "D1–D8" e a critérios "A1–A9" foram corrigidas (restam apenas citações explicativas de que mudaram).
- **D1 a D10 sem autorização:** o texto declara que nenhuma está autorizada; as únicas ocorrências de "autorizada/o" são negações, condições ou descrição do que cada alternativa autorizaria se escolhida.
- **F2.0-D e F2.1:** continuam bloqueadas (`LEIA-ME.md`, este relatório, `parecer_f2_0.md` §8).
- **Limites da verificação:** não reproduzi nenhuma prova técnica; a verificação cobre consistência documental. Não verifiquei contra o texto original das auditorias anteriores (não está em `f2/`). Revisão independente do pacote por outra instância não foi feita nesta etapa.
