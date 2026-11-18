# Relatório F2.0-C.2 — portões, critérios experimentais e rastreabilidade

> **Nota C.3:** este relatório é histórico. Onde ele diz que D3(b) e D3(c) autorizariam o pacote B e os experimentos X20 e X21, e propõe `/tmp/dengue_f2d/` como local, vale o que consta em `portoes_f2.md`, `f2_0d_especificacao.md`, `matriz_decisoes_humanas.md` e `relatorio_f2_0c_3.md`: o pacote B está **bloqueado**, X20 e X21 estão fora de pacote e a proposta de local mudou.

**Natureza:** correção **somente documental**, dentro de `agentes/laboratorio/f2/`. Nada foi executado, testado ou implementado. **F2.0-D e F2.1 continuam bloqueadas.** Nenhuma decisão foi autorizada. R1 continua **ABERTO**.

## 1. Correções feitas
| Achado | O que mudou | Onde |
|---|---|---|
| AUD3-ALTO-1 (D3 aberta) | D3 virou autorização **fechada por pacotes**: hipóteses HD-1 a HD-16, 21 experimentos (X01–X21), executor de cada um, ambiente, local do canário, tetos de sessões/turnos/custo/duração, criação e remoção de arquivos, critérios de interrupção, proibições. Separa o que o Claude Code faz do que exige você. Sem autorização implícita | `f2_0d_especificacao.md`, `matriz_decisoes_humanas.md` D3 |
| AUD3-ALTO-2 (portões) | Tabela **única** de portões da F2.0-D à F2.7 (7 campos por etapa). R1 não bloqueia **entrada** na F2.1; bloqueia toda execução dependente de isolamento (EDI). F2.3 prova o isolamento (CP-5). Nenhuma etapa conclui só por documento; nenhuma inicia a seguinte | `portoes_f2.md` (normativo); roadmap virou resumo |
| AUD3-ALTO-3 (CP-1) | CP-1 com objetivo, precondições, procedimento determinístico, executor, registro independente, controle positivo, critérios de sucesso/falha/inconclusivo, contingência, limite de tentativas. Cinco categorias; "não tentado" nunca é "negado"; sem prova de tentativa → INCONCLUSIVO. Contingências: `bwrap` filho do Claude Code, rede, montagem, permissão, canário, timeout, rate limit, controle positivo impossível. Landlock e usuário Unix avaliados | `criterios_peach_f2.md`, `f2_0d_especificacao.md` §3, §5, §7 |
| AUD3-M-1 | IDs únicos por auditoria (AUD0–AUD3). "M5/M7" antigos = NÃO VERIFICÁVEL | `rastreabilidade.md` |
| AUD3-M-2 | Coluna "Hoje (comprovado)" nas linhas 51–54; 54 linhas conferidas | `matriz_autonomia.md` |
| AUD3-M-3 | `deny` de edição sem teste reclassificado D/H; o teste de `Read` não foi generalizado | `matriz_autonomia.md`, `registro_riscos.md` R3 |
| AUD3-M-4 | `onFailure`: só `continue` testado; campo ausente = D | `parecer_f2_0.md`, `limitacoes.md`, `resultados.md` |
| AUD3-M-5 | R11 corrigido; DX-3 (launcher e `disableAllHooks`) criada | `registro_riscos.md`, `matriz_decisoes_humanas.md` |
| AUD3-M-6, M-7 | TTY = hipótese, com teste de falsificação em pty do próprio harness; plano de isolamento cobre `/proc`, `/dev`, `/sys`, `.git`, rede do Claude Code (sem `--unshare-net`), `bwrap` aninhado, limites do Landlock; teste mínimo ≠ prova | `arquitetura_l0.md`, `plano_isolamento_r1.md` |
| AUD3-M-8 | Validade estrutural do JSON ≠ evidência; critérios V e J; aceite humano por arquivo | `criterios_peach_f2.md` |
| AUD3-M-9 | DX-1/DX-2 com alternativas e recomendação; DX-2 (hash dos arquivos de manifesto) é distinto de `manifesto.py verificar` | `matriz_decisoes_humanas.md`, `arquitetura_l0.md` |
| AUD3-M-10, M-11 | D1, D5, D7, D8, D10 sem ambiguidade; procedimento da sessão de bootstrap (D9); D10 como pré-requisito da F2.0-D | `matriz_decisoes_humanas.md`, `arquitetura_l0.md` |
| AUD3-B-1 a B-8 | Corrigidos conforme `rastreabilidade.md` §5 (B-7 parcial) | vários |

## 2. Arquivos
**Novos (3):** `portoes_f2.md`, `f2_0d_especificacao.md`, `relatorio_f2_0c_2.md`.
**Alterados (15):** `LEIA-ME.md`, `plano.md`, `parecer_f2_0.md`, `resultados.md`, `limitacoes.md`, `registro_riscos.md`, `matriz_autonomia.md`, `arquitetura_l0.md`, `plano_isolamento_r1.md`, `matriz_decisoes_humanas.md`, `roadmap_f2_revisado.md`, `criterios_peach_f2.md`, `questoes_abertas.md`, `consolidacao_f2_0c.md`, `rastreabilidade.md`, `relatorio_f2_0c_1.md` (banners e notas; 16 contando o relatório C.1).
**Não tocados:** `bin/`, `cfg/`, `evidencias/`, `sintetico/`, `saida/`, manifestos v001/v002, `DECISOES.md`, `.python-version`, `pyproject.toml`, `uv.lock`, qualquer arquivo fora de `f2/`.

## 3. Tratamento dos achados
Tabela completa, com origem, documento, correção e estado, em `rastreabilidade.md`. Resumo: tudo é **corrigido documentalmente**; **nada foi comprovado tecnicamente**. Itens sem texto original (AUD?-M5, AUD?-M7, AUD0-N1 a N7, AUD0-B4, matriz de 41 linhas, AUD2-B2) estão **NÃO VERIFICÁVEIS**. As auditorias foram recebidas como relatos de subagentes e nem sempre li o texto original completo; não reconstruí achados ausentes.

## 4. Nova tabela de portões (resumo; o normativo é `portoes_f2.md`)
| Etapa | Entrada exige | Bloqueada por |
|---|---|---|
| F2.0-D | D10 (critérios CP-1 aceitos), D3 com escopo escolhido, harness aprovado, **autorização de início separada** | tudo isso, hoje |
| F2.1 | CP-1 aprovado ou aceite escrito seu de cada experimento inconcluso; D1, D8, D9, D10 | F2.0-D não concluída; R1 **não** bloqueia a entrada |
| F2.2–F2.3 | etapa anterior aprovada; F2.3 prova isolamento (CP-5) | R1 bloqueia qualquer EDI até CP-5 |
| F2.4 | D7, DX-1, DX-2, DX-3 | — |
| F2.5 | D4, D5, D6 | — |
| F2.6–F2.7 | ver `portoes_f2.md` | — |
Regras: pausa se rate limit ≥ 0,95, ou 429, ou custo ≥ 80% do teto; nenhuma etapa inicia a seguinte; EDI antes do CP-5 só por ESH (código revisado pela Peach e lido por você, hash registrado, comando fixo iniciado por você, dados sintéticos).

## 5. D3 revisada (resumo)
Pacotes: **(a)** A (X01–X11, ambiente, rede, `/proc`/`/dev`/`/sys`, links, pytest, `bwrap` aninhado, Landlock, TTY em pty próprio); **(b)** A+B (X12–X19: negação real de `Agent`, cobertura de `deny`, `bwrap` filho do `claude`, recarga, flags, `.cc-writes`, `onFailure` ausente, `updatedInput`×`deny`); **(c)** A+B+C (X20–X21: `CLAUDE_CONFIG_DIR`/login, `claude` confinado); **(d)** experimentos individuais; **(e)** nenhum. Você precisa registrar 5 itens: IDs, local do canário (proposta `/tmp/dengue_f2d/`, alternativa `~/dengue_f2d/`), tetos, autorização de criar/remover, proibições. Tetos propostos: 24 sessões `claude -p`, 8 turnos, US$ 0,10 por sessão e US$ 1,00 no total, 120 s por tentativa, 10 min por sessão, 3 h no total (**propostas, não decididas**). **Recomendação: (d)**, começando por A e por X12–X16 e X19; X20/X21 só se quiser investigar o confinamento do `claude`.

## 6. CP-1 revisado (resumo)
Cada hipótese tem os 10 elementos da seção 1 acima. **Sucesso** = tentativa registrada de forma independente + controle positivo válido + resultado igual ao esperado. **Falha** = tentativa registrada e resultado oposto (hipótese refutada é achado válido, não falha da etapa). **Inconclusivo** = tentativa não provada, controle positivo ausente, canário falho, timeout, rate limit ou falha do harness. Categorias: tentada e negada / tentada e permitida / não tentada / não registrada / falha do harness; só a primeira conta como negada.

## 7. Pendências e limitações
- Auditoria independente da C.2 **ainda não feita**.
- Nenhuma hipótese H virou T. Segue aberto: negação real de `Agent`, recarga, injeção em socket, cobertura de `deny`, `bwrap` sob o `claude`/aninhado, ABI do Landlock, falsificação de TTY, causa de `.cc-writes`, `onFailure` ausente, `claude` confinado e login.
- Defeito de entrega (reenviar o mesmo arquivo pode gravar versão antiga): contornado por novo nome de arquivo e conferência `cmp`; causa não apurada (Q20).
- F3–F6 do plano anterior não foram relidas.
- Tetos e local do canário são propostas.

## 8. Decisões humanas necessárias
D10 e D3 primeiro (D10 antes de D3). Depois, conforme etapa: D1, D8, D9 (F2.1); D7, DX-1, DX-2, DX-3 (F2.4); D4, D5, D6 (F2.5); D2 em `matriz_decisoes_humanas.md`. Aceitar critérios (D10) **não** aprova resultados nem autoriza experimentos. Autorizar a F2.0-D exige escolha explícita sua do escopo de D3. DP-001 e Etapa 3.2 seguem sem aprovação científica.

## 9. Confirmação
Não foi executado nenhum experimento, teste, hook, script de segurança ou comando de sistema na máquina do projeto. Nada foi instalado; não houve `sudo`, alteração de permissões, usuários ou configuração do Claude Code. Não acessei dados protegidos nem de 2024. Manifestos não foram abertos nem alterados. Nada fora de `f2/` foi tocado. Sem commit nem push (o repositório não tem `.git`). F2.0-D e F2.1 **não** foram iniciadas.

## 10. Verificação
Conferência feita por conteúdo, não por tamanho:
- Os 18 arquivos de `f2/` (exceto este relatório, conferido em seguida) foram regravados no disco do projeto, relidos de lá e comparados byte a byte (`cmp`) com os mestres: **todos idênticos**.
- Verificações por script: matriz de autonomia com linhas 1 a 54 sem salto; riscos R1 a R33 completos; questões Q1 a Q29 em ordem; nenhuma referência a R, D, Q, CP, X ou HD acima do máximo existente; "D1–D8" e "A1–A9" aparecem só em frase explicativa do relatório C.1; nenhuma decisão marcada como autorizada; R1 com estado **ABERTO**; F2.0-D e F2.1 bloqueadas em `portoes_f2.md`, `LEIA-ME.md` e `matriz_decisoes_humanas.md`.
- Referências a arquivos que não existem em `f2/` (`l0.py`, `isolar.py`, `rodar_d.sh`, `limpar.sh`, `matriz_d.json`, `settings.local.json`) são **artefatos futuros**, descritos e não criados; `criterios_aprovacao.md` é citado só para dizer que não existe.
- **Limite:** esta conferência é minha, sem auditor independente. A releitura de coerência foi feita por script e por leitura parcial; a Peach ainda não auditou a C.2.
