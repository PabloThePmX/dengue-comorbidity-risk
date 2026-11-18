# Matriz de decisões humanas D1–D10, DX-1 a DX-3 (F2.0-D0)

**Nota C.3 (2026-11-18):** D3 reescrita (pacote B bloqueado; X20 e X21 fora de pacote; local-base proposto novo; D3 não inicia a etapa); D1(c) **não selecionável antes do CP-5**; D10(d) explicitada; nova etapa preparatória F2.0-D0 em `portoes_f2.md`. **Continua sem nenhuma decisão autorizada.**

**Nota F2.0-D0 (2026-11-18, 17:11):** o usuário decidiu **D10 (aceita com complemento)** e **D3 (pacote A selecionado)**; ver a seção "Decisões humanas registradas" abaixo. **Nenhuma das duas autoriza executar experimentos.** Todas as outras decisões continuam pendentes.

**Nenhuma outra decisão abaixo está autorizada.** Sem uma escolha sua, por escrito, nada é autorizado, e a opção "não decidir" equivale a "não autorizar". As recomendações são técnicas e não substituem a sua escolha. Nada aqui é decisão científica: a Etapa 3.2 e a DP-001 continuam sem aprovação e fora desta matriz. Quando uma decisão é necessária e para qual etapa: `portoes_f2.md` (fonte normativa).

Classes: **T** testado, **D** documentação, **H** hipótese, **L** limitação. Executores (NUV, CC-local, HUM, PEACH): `portoes_f2.md` §1 P6.

## Decisões humanas registradas (fonte: mensagem do usuário, 2026-11-18, 17:11, America/Sao_Paulo)
Esta seção registra **só o que o usuário escreveu**. Nada foi acrescentado como decisão.

| Decisão | Estado | Texto do usuário (resumido) | O que **não** significa |
|---|---|---|---|
| **D10** | **ACEITA COM COMPLEMENTO** | Aceitar os critérios da D10, acrescentando ao CP-1 a **revisão obrigatória do código do harness antes de qualquer experimento**, com critérios objetivos, arquivos e componentes abrangidos, verificação de integridade, evidências reproduzíveis e critérios de aprovação, reprovação e inconclusivo. | A aprovação documental **não** é comprovação técnica e **não** autoriza experimentos. Aceitar critérios não aprova resultados. Pela alternativa (d), só CP-1 está aceito; CP-2 e CP-3 precisam ser decididos antes da F2.1, e cada CP seguinte antes da sua etapa. O complemento está em `criterios_peach_f2.md` (CP-1H). **Ambiguidade registrada:** o texto diz "aceitar os critérios da D10" e não diz se CP-2 a CP-9 estão incluídos; por prudência foi tomada a leitura mais estreita (alternativa (d): só CP-1 e o complemento). Se você quis aceitar todos, diga por escrito. |
| **D3** | **PACOTE A SELECIONADO** | Selecionar exclusivamente o Pacote A (X01 a X11). A seleção **autoriza somente a preparação da F2.0-D0**. **Não autoriza executar X01 a X11.** | Não inicia a F2.0-D. Pacote B (X12 a X19): **NÃO AUTORIZADO / BLOQUEADO**. **X20 e X21: fora de qualquer pacote autorizado** (não fazem parte da D3). Os itens 2 a 6 da escolha de D3 (local-base, tetos, autorização de criar e remover arquivos de execução, modo do CC-local, reafirmação de §4.3 e §4.6) **não foram decididos**: continuam **pendentes** e são necessários antes da F2.0-D. |
| **F2.0-D0** | Início autorizado pelo usuário **na mesma mensagem**, só para preparar o harness | "Conduza a F2.0-D0 para produzir e revisar o harness necessário aos experimentos do Pacote A", sem executar nada. | Não autoriza executar X01 a X21, sessões `claude -p`, login, mudança de configuração global, instalação, permissões, dados de 2024 ou manifestos, commit ou push. **Concluir a D0 não autoriza a F2.0-D.** A lista de arquivos de `f2_0d_especificacao.md` §4.1 (itens 1 a 7) foi tomada como "os locais expressamente autorizados pela ficha da F2.0-D0"; isto é **interpretação** a confirmar na sua leitura final. |

**Restrições mantidas:** R1 **ABERTO**; nenhuma comprovação técnica de isolamento pode ser presumida; D1, D2, D4 a D9 e DX-1 a DX-3 continuam pendentes.

## Resumo
| ID | Pergunta | Recomendação técnica | Necessária para |
|---|---|---|---|
| D1 | Aceitar ou não o risco R1 (Bash e `pytest` sem isolamento comprovado)? | (a) exigir isolamento provado | F2.1 (qualquer alternativa) e F2.3 |
| D2 | Você quer criar um usuário Unix separado? | (a) não agora | F2.3, só se escolhido |
| D3 | Qual escopo fechado da F2.0-D você escolhe? (D3 **não inicia** a etapa) | **DECIDIDA em parte (17:11):** pacote A selecionado; só prepara a D0; itens 2 a 6 pendentes | F2.0-D0 e F2.0-D |
| D4 | Qual procedimento autoriza uma missão? | (a) resumo legível + TTY + arquivo fora do alcance | F2.5, F2.6 |
| D5 | Quais limites padrão de missão? | (a) adiar números até medir | F2.5 |
| D6 | Onde fica o estado do L0? | (a) fora do repositório | F2.5 |
| D7 | Como tratar exceções de runtime no manifesto? | (a) exceção exata por caminho e conteúdo | F2.4 |
| D8 | Aprovar a matriz de autonomia como base de desenho? | (a) aprovar | F2.1 |
| D9 | Autorizar o bootstrap dos controles, e como? | (b) por subetapa, com revisão humana | F2.1 a F2.5, por arquivo |
| D10 | Aceitar os critérios CP-1 a CP-9 da Peach? (**aceitar critérios não é autorizar nada**) | **DECIDIDA (17:11): aceita com complemento** (CP-1 com revisão obrigatória do harness, CP-1H); só CP-1 aceito; demais antes das suas etapas | F2.0-D0 e F2.0-D (CP-1); cada CP antes da sua etapa |
| DX-1 | Fixar a versão do Claude Code? | (a) fixar 2.1.327 | F2.4 |
| DX-2 | Registrar o hash dos arquivos de manifesto v001 e v002? | (a) não agora | F2.4 |
| DX-3 | Quem pode lançar sessões e como tratar `disableAllHooks`? | (a) só o L0; detecção por heartbeat | F2.4 |

## D1 — Risco R1 (subprocessos do Bash)
- **Pergunta:** o Bash e o `pytest` dos agentes podem rodar sem isolamento comprovado?
- **Contexto:** o `deny` de `Read` só foi provado contra `cat` (T). `python -c`, `head`, `base64` e filhos de `pytest` não foram testados. O sandbox do Claude Code falha aqui (T). O `bwrap` passou só em teste mínimo (T), que **não** prova isolamento. Ver `plano_isolamento_r1.md`.
- **Termo definido:** **perfil de Bash sem interpretadores** = lista fechada de comandos de leitura e navegação, sem `python`, `python3`, `node`, `sh -c`, `bash -c`, `eval`, `pytest` nem redirecionamento arbitrário. Os gates (`pytest`, `ruff`, `manifesto.py verificar`) **não** rodam pelo agente: rodam pelo L0 (depois da F2.5) ou por ESH.
- **Alternativas:**
  - **(a) Exigir isolamento provado (CP-5) antes de liberar Bash e `pytest`.** *Consequência:* até lá, qualquer execução de código de agente é nível 3 (só ESH, `portoes_f2.md` P4). *Autoriza:* nada novo.
  - **(b) Liberar o perfil de Bash sem interpretadores.** *Consequência:* agentes leem e editam; testes seguem por ESH. *Autoriza:* só os comandos da lista (definida na F2.2/F2.3 e revisada por você).
  - **(c) Aceitar R1 por escrito e liberar Bash e `pytest`.** **NÃO SELECIONÁVEL antes do CP-5 aprovado (C.3).** *Motivo:* contradiz `portoes_f2.md` P3 e P5 (R1 bloqueia EDI até o CP-5). Depois do CP-5, (c) vale só como aceite do **risco residual**, não como substituto da prova. *Consequência descrita (se um dia selecionável):* um teste ou script de agente alcança tudo o que o seu usuário alcança, inclusive protegidos, `~/.claude` e controles. *Autoriza hoje:* nada.
- **Recomendação:** (a). **Riscos:** (c) removeria a barreira de arquivos e deixaria os controles alteráveis. **Dependências:** a prova vem da F2.0-D (D3) e da F2.3. **R1 permanece aberto em qualquer alternativa até o CP-5.** Para a entrada na F2.1, D1 precisa estar decidida com **(a) ou (b)**.

## D2 — Usuário Unix separado
- **Pergunta:** você quer criar, por conta própria e com o seu `sudo`, um usuário Unix dedicado aos agentes?
- **Contexto:** é a barreira de arquivos mais forte contra processos do mesmo usuário (D). Nenhum agente usará `sudo` em nenhuma alternativa. Não é testável aqui.
- **Alternativas:** **(a) não agora.** *Autoriza:* nada. **(b) reavaliar depois da F2.0-D, se `bwrap` e Landlock não bastarem.** *Autoriza:* nada agora. **(c) agora.** *Consequência:* mexe no sistema antes de saber se é necessário; o login do Claude Code precisa ser refeito para o novo usuário (H, X20); refaz-se o CP-5. *Autoriza:* nada a agentes; é ação sua.
- **Recomendação:** (a), reavaliar em (b). **Riscos:** complexidade operacional. **Dependências:** D3.

## D3 — Escopo fechado da F2.0-D (reescrita na C.3; decidida em parte na F2.0-D0)
**Registro (17:11):** pacote A (X01 a X11) selecionado, **exclusivamente**; a seleção autoriza **só a preparação da F2.0-D0**, **não** a execução de X01 a X11. **X20 e X21 não fazem parte da seleção e não são autorizados.** Pacote B: bloqueado. Itens 2 a 6 da lista abaixo: **pendentes** (necessários antes da F2.0-D). Mudança do harness depois do hash registrado exige nova decisão.
- **Pergunta:** quais experimentos da F2.0-D você escolhe, com qual local-base, tetos e modo do CC-local?
- **D3 escolhe escopo; não inicia a etapa.** A autorização de início da F2.0-D0 e a da F2.0-D são **outros textos seus**, separados (`portoes_f2.md`). Mudança no harness depois que o hash for registrado exige **nova decisão**.
- **Contexto:** a especificação completa está em `f2_0d_especificacao.md`: 21 experimentos (X01 a X21) com ficha completa **no papel** (objetivo, pré-condições, procedimento, executor, registro independente, controle positivo, esperado, sucesso, falha, inconclusivo, contingência, tentativas, limpeza). Você não tem shell próprio: o **CC-local** roda só `rodar_d.sh <ID>` (ou **você digita** o comando, modo 1 de §4.7); a **NUV** só grava documentos e scripts. O que depende de **você**: abrir a sessão, login (X20), indicar o local-base, aprovar o harness (D0), ler os resultados.
- **Estado dos blocos:** **pacote A (X01–X11): selecionável.** **Pacote B (X12–X19, XB0): NÃO AUTORIZADO / BLOQUEADO e não selecionável aqui**: não há garantia técnica de contenção das sessões `claude -p` (conectores do Drive, repositório com dados protegidos, estado em `~/.claude`); condições de desbloqueio em `f2_0d_especificacao.md` §5B.2; só uma decisão futura **"D3-B"**, distinta desta, pode liberar. **X20 e X21: fora de qualquer pacote**; só individualmente, por decisão separada; X20 é pré-requisito de qualquer desbloqueio do B.
- **O que a sua escolha precisa conter (todos os itens):**
  1. a lista de IDs escolhidos (do pacote A; opcionalmente X20 ou X21 individualmente, com a razão);
  2. o **local-base dos canários, fora do repositório** (proposta: `~/dengue_f2d/`, 0700, criado e controlado pelo harness; alternativa: subdiretório de nome aleatório em `/tmp`; **nunca** `~/.claude`). Mudança C.3: a proposta anterior `/tmp/dengue_f2d/` tinha nome fixo e previsível;
  3. a confirmação ou alteração dos tetos de `f2_0d_especificacao.md` §4.2 (**propostas, não decisões**: 120 s por tentativa do harness, 10 min por sessão `claude`, 3 h no total, pausa com rate limit ≥ 0,95; os tetos de 24 sessões e US$ 1,00 pertencem ao pacote B bloqueado; pacote A não usa API);
  4. a autorização de **criar** os arquivos da lista fechada de §4.1 (na D0) e de **removê-los** com `limpar.sh`, que só remove o que `registro_criados.json` lista (§4.4);
  5. o **modo do CC-local** (§4.7: modo 1, você digita; ou modo 2, aprovação por comando);
  6. a confirmação de que as operações proibidas de §4.3 continuam proibidas, **inclusive** a regra de `~/.claude` (§4.6: escrita de estado do CLI tolerada; alterar configuração, credenciais, agentes e hooks, proibido).
- **Alternativas:**
  - **(a) Pacote A inteiro** (X01 a X11; sem custo de API). *Autoriza (quando houver autorização de início):* os 11 experimentos, canários no local-base, `limpar.sh`. **Não** autoriza sessões `claude -p`.
  - **(b) Pacotes A + B.** **NÃO SELECIONÁVEL (bloqueado).**
  - **(c) Pacotes A + B + C.** **NÃO SELECIONÁVEL (bloqueado).**
  - **(d) Seleção individual:** você lista IDs **do pacote A**; X20 ou X21 só se listados **um a um, expressamente**. Tudo o que não está na lista **não** é autorizado.
  - **(e) Não escolher.** *Consequência:* R1 e R18 a R21 seguem H; a F2.1 só entra se você aceitar o risco de cada experimento não feito (`portoes_f2.md` F2.1).
- **Risco aceito a informar se X20 ou X21 vierem a ser listados um a um (AUD5-MED-2):** são sessões `claude -p` Haiku, **sem contenção comprovada** (a mesma razão do bloqueio do pacote B); a mitigação é H (`--tools ""`, turno único, teto de US$ 0,05, abort pelo `init`) e os conectores da conta podem aparecer apesar de `--strict-mcp-config` (Q31). A proteção contra leitura de credenciais de X20 por agente é **procedural** (L): no modo 2 do CC-local depende da sua atenção (AUD5-BAIXO-1). **Hoje não são selecionáveis**: nem X20 nem X21 foram escolhidos.
- **Recomendação:** (d), começando pelo pacote A. Sem sessões `claude`, o pacote A não gasta cota. **Riscos:** o pacote A não resolve o estado do `claude` em `~/.claude` nem a contenção das sessões; só X20 e X21 investigam isso. Resultado FALHA é achado, não problema do processo. **Dependências:** D10 (CP-1 aceito antes dos resultados); F2.0-D0 (harness revisado por Peach e por você, com hash); autorização de início **separada e expressa**.
- **Fora do escopo desta decisão, sempre:** F2.1, qualquer controle definitivo, alterar o escopo nomeado de `~/.claude` real, `sudo`, instalar, tocar manifestos, dados protegidos, commit ou push.
- **Exemplo de resposta válida:** "D3: escolho X01 a X09 (pacote A, parcial); local-base `~/dengue_f2d/`; tetos conforme a proposta; CC-local modo 1; criar os arquivos da lista de §4.1 e remover com `limpar.sh` nos termos da §4.4. Isto não inicia a D0 nem a F2.0-D." Resposta sem esses itens não escolhe nada, e **nenhuma resposta a D3 autoriza iniciar**.

## D4 — Autorização de missão
- **Pergunta:** que procedimento conta como "você autorizou esta missão"?
- **Contexto:** um hash impresso não prova que você leu o escopo (`arquitetura_l0.md` §2). **Falta de informação (Q18):** o local do arquivo de missão fora do alcance dos agentes (depende de D6 e do confinamento provado no CP-5). Sem confinamento, o mesmo usuário Unix altera o arquivo.
- **Alternativas:**
  - **(a) Resumo legível + confirmação digitada em TTY + arquivo fora do repositório e fora do alcance dos agentes + verificação antes da execução.** *Autoriza:* uma missão por confirmação. *Limite:* o arquivo só fica protegido com confinamento provado; o TTY contra forja é **H** (X11).
  - **(b) (a) + assinatura HMAC.** *Consequência:* detecta alteração por processo que não lê a chave; **não** protege contra o mesmo usuário Unix sem confinamento (L).
  - **(c) Só o arquivo e o hash.** *Consequência:* "carimbo"; não recomendado.
- **Recomendação:** (a); (b) como camada opcional. **Riscos:** R30. **Dependências:** D6, e a prova do confinamento. Necessária na F2.5 e F2.6.

## D5 — Limites padrão de missão
- **Pergunta:** quais tetos valem por padrão (ciclos por tarefa, negações por tarefa, turnos, custo, duração, tentativas por passo)?
- **Contexto:** ciclos 3 e negações 5 são **propostas deste documento**, sem base de medição. **Falta de informação:** Q14 (quanto `--max-budget-usd` ultrapassa na prática; X16 mede) e Q17 (janela e custo reais; a conta registrou uso ≈ 0,94 em todas as sessões, I9). Sem essas medidas não há base para fixar valores em USD ou duração.
- **Alternativas:** **(a) Adiar os valores numéricos até X16 e a F2.5 medirem; fixar só ciclos 3 e negações 5 como tetos provisórios.** *Autoriza:* tetos provisórios. **(b) Você define os números agora.** *Consequência:* valores sem medição podem travar missões úteis ou deixar passar gasto. **(c) Sem teto global.** Não recomendado.
- **Recomendação:** (a). **Riscos:** uma missão pode consumir toda a cota e deixar a Peach sem sessão. **Dependências:** X16, que pertence ao pacote B **bloqueado** (C.3); sem ele, Q14 continua aberta e os valores ficam provisórios. Necessária na F2.5.

## D6 — Estado do L0
- **Pergunta:** onde o L0 guarda estado, contadores, eventos e hashes de controle?
- **Contexto:** precisa ficar fora do repositório e fora do alcance dos agentes; o mesmo usuário Unix só garante isso com confinamento (CP-5). O HMAC ficou em D4(b).
- **Alternativas:** **(a) um diretório seu fora do repositório** (exemplo: `~/.local/state/dengue-l0/`). **(b) Dentro do repositório, ignorado pelo Git** (o agente alcança o caminho; protege só `deny` e hook). **(c) Outro local que você indicar.**
- **Recomendação:** (a). **Riscos:** perda do estado se a pasta for limpa. **Dependências:** a prova de ocultação (X04). Necessária na F2.5.

## D7 — Exceções de runtime no manifesto
- **Pergunta:** como tratar `.claude/.cc-writes/` e criações semelhantes do runtime?
- **Contexto:** a pasta apareceu, vazia, e a causa não está comprovada (H, R12; X17 investiga). `.claude/` também guarda `settings.local.json` e `agents/`, então não pode virar exceção genérica.
- **Alternativas:**
  - **(a) Exceção exata:** caminho completo (`.claude/.cc-writes` relativo ao `cwd` da sessão) e conteúdo esperado (diretório vazio; qualquer arquivo dentro é violação). A lista fica em arquivo **SOMENTE_HUMANO** conferido por hash. *(Assinatura não é proteção contra o mesmo usuário Unix; não é prometida.)*
  - **(b) Ignorar `.claude/` inteira.** *Consequência:* abre `settings.local.json` e `agents/`. Rejeitada tecnicamente.
  - **(c) Sem exceção:** o L0 trata como violação e abre PEND a cada sessão que criar a pasta.
- **Recomendação:** (a). **Riscos:** R12, R28. **Dependências:** X17, que pertence ao pacote B **bloqueado** (C.3); sem ele, a causa de `.cc-writes` continua H. Necessária na F2.4.

## D8 — Matriz de autonomia
- **Pergunta:** aprova `matriz_autonomia.md` (nível desejado × nível comprovado) como base do desenho?
- **Contexto:** a matriz separa o alvo do que está comprovado hoje (quase nada: só a política F1 e os mecanismos do laboratório). Linhas 29, 38 e 51 a 54 corrigidas; `deny` de edição reclassificado como D/H.
- **Alternativas:** **(a) Aprovar como está.** *Autoriza:* usar a matriz como base de desenho; **não libera nenhuma ação**. **(b) Aprovar após ajustes seus.** *Só tem efeito depois que você registrar a lista de ajustes ou "sem ajustes"; antes disso vale (c).* **(c) Não aprovar.** *Consequência:* a F2.1 não inicia.
- **Recomendação:** (a), depois de ler a seção 0 da matriz. **Riscos:** tratar o "alvo" como estado atual. **Dependências:** nenhuma. Necessária na F2.1.

## D9 — Bootstrap dos controles
- **Pergunta:** quem escreve `l0.py`, o hook, `isolar.py` e o gerador de configuração, e sob qual autorização específica?
- **Contexto:** estes arquivos são N3★ (nenhuma missão comum os concede) e os controles não podem aprovar a si mesmos. O procedimento, inclusive a **sessão de bootstrap**, está em `arquitetura_l0.md` §2A.
- **Alternativas:**
  - **(a) Você escreve ou aprova linha a linha cada controle; agentes só escrevem testes e documentação.** Mais seguro; mais trabalho seu. *Autoriza:* nada a agentes sobre controles. *Cuidado:* testes escritos por agente também precisam de revisão (um teste fraco dá falsa segurança).
  - **(b) Bootstrap por subetapa, em sessão própria, com o Mario como redator** (`arquitetura_l0.md` §2A): lista exata de arquivos; autorização por arquivo; sessão iniciada por você com `--settings` escrito por você que libera `Write`/`Edit` **só** nos arquivos da lista; snapshot antes e depois como registro independente; diff revisado pela Peach **e** por você antes da ativação; a primeira ativação é sua; versão anterior preservada. *Autoriza:* escrita dos arquivos listados, nada mais.
  - **(c) Adiar o bootstrap.** *Consequência:* a F2 inteira para.
- **Recomendação:** (b), com revisão humana obrigatória. **Falta de informação:** o tamanho do código a revisar não foi medido (Q23). **Riscos:** R29. **Dependências:** D8, D10; autorização de cada etapa (`portoes_f2.md`).

## D10 — Critérios de aprovação da Peach
- **Pergunta:** aceita `criterios_peach_f2.md` (CP-1 a CP-9) como regra de aprovação das subetapas?
- **Contexto:** o arquivo ganhou o formato estruturado do resultado da Peach, a verificação do L0 além da validade do JSON (V e J), a regra de crítico e importante e a separação entre três aprovações. **Aceitar critérios não equivale a aprovar resultados, nem a autorizar experimentos, nem a iniciar etapa.**
- **Alternativas:**
  - **(a) Aceitar CP-1 a CP-9 como estão.** *Autoriza:* a Peach usar esses critérios para aprovar etapas; nada mais.
  - **(b) Aceitar com ajustes.** *Só tem efeito depois que você registrar a lista de ajustes; antes disso vale (c).*
  - **(c) Não aceitar.** *Consequência:* nenhuma subetapa tem regra de aprovação.
  - **(d) Aceitar só CP-1 agora** (o suficiente para a F2.0-D0 e a F2.0-D) **e aceitar cada CP seguinte antes da etapa que ele aprova** (CP-2 e CP-3 antes da F2.1; CP-4 antes da F2.2; e assim por diante: `portoes_f2.md`). *Autoriza:* a Peach usar CP-1 **na revisão do harness da F2.0-D0 (CP-1H) e na F2.0-D** (esclarecimento AUD5-BAIXO-7). **Não autoriza** a D0, a F2.0-D nem nenhuma outra etapa.
  - **Decisão registrada (17:11): aceita com complemento.** A forma escolhida corresponde a (d) **mais** o complemento CP-1H (revisão obrigatória do código do harness antes de qualquer experimento). A aceitação vale para CP-1 e CP-1H; CP-2 e CP-3 e os seguintes **não** foram aceitos ainda.
- **Recomendação:** (d). **Riscos:** critérios fracos aprovam cedo demais; critérios mudados depois de ver resultados invalidam a aprovação (por isso D10 vem **antes** da F2.0-D). **Dependências:** nenhuma.

## DX-1 — Versão do Claude Code
- **Pergunta:** fixar a versão do Claude Code?
- **Contexto:** os testes valem para a 2.1.327. Mudanças de versão podem mudar hooks, eventos e flags. Desligar a atualização automática altera configuração global (ação sua, não de agente).
- **Alternativas:** **(a) Fixar 2.1.327;** o L0 recusa outra versão. *Consequência:* atualizações exigem reteste (CP-6). **(b) Aceitar uma faixa** de versões, com reteste dos CP-4 a CP-6 a cada mudança. **(c) Não fixar.** *Consequência:* o ambiente pode quebrar sem aviso.
- **Recomendação:** (a). **Riscos:** versão fixa pode ter falha conhecida. **Dependências:** nenhuma. Necessária na F2.4.

## DX-2 — Hash dos arquivos de manifesto v001 e v002
- **Pergunta:** registrar o hash dos **arquivos** de manifesto v001 e v002 para provar integridade byte a byte deles mesmos?
- **Esclarecimento (resolve a contradição apontada):** são coisas diferentes. (i) **Verificar** os arquivos protegidos com `manifesto.py verificar` é o mecanismo autorizado da F1, e o L0 o roda a cada missão; **não** depende desta decisão. (ii) **Gerar** uma versão nova (v003) é nível 2 se estiver prevista na missão (matriz, linha 31). (iii) **Alterar ou recalcular** v001 e v002 é proibido (N3★). Esta decisão trata só de **calcular o hash dos dois arquivos de manifesto, sem abrir o conteúdo**, e registrar o resultado em arquivo novo. Registros anteriores da F1 trazem um hash de v001; não o recalculei nem o verifiquei aqui.
- **Alternativas:** **(a) Não agora.** *Consequência:* a integridade de v001 e v002 continua só por tamanho e data (fraca). **(b) Calcular e registrar o hash dos dois arquivos** por comando fixo executado pelo CC-local (ESH) e gravar em arquivo novo em `f2/`. *Autoriza:* só esse cálculo, sem abrir, sem alterar, sem regenerar. **(c) Gerar v003 com o hash dos manifestos antigos** (F2.7).
- **Recomendação:** (a) agora; (b) antes da F2.4. **Riscos:** (b) manipula arquivos protegidos de forma só leitura. **Dependências:** F2.4.

## DX-3 — Confiança no lançador e `disableAllHooks`
- **Pergunta:** quem pode lançar sessões e como você aceita o risco de que quem lança pode desligar hooks?
- **Contexto:** `--settings '{"disableAllHooks": true}'` desliga hooks por execução (D). O controle protege contra o agente, não contra quem inicia a sessão (R11, R23).
- **Alternativas:** **(a) Só o L0 lança sessões de agente; detecção por heartbeat (a primeira chamada de ferramenta precisa gerar registro do hook); o L0 recusa `disableAllHooks`.** *Limite:* quem tem o seu usuário Unix e roda `claude` à mão não é impedido (L). **(b) (a) mais confinamento do lançador** (depende de X21; H). **(c) Aceitar o risco sem detecção.** Não recomendado.
- **Recomendação:** (a). **Riscos:** R11, R23. **Dependências:** F2.4 e F2.5. Necessária na F2.4.

## Pendentes de etapas anteriores (não decididos aqui)
**DP-001 (D-a a D-d), Etapa 3.2 (aguarda aprovação científica), Etapa 3.3 (não autorizada)** e reservas N1–N7 de auditoria anterior (origem não localizada) continuam abertos.

## O que sempre exige decisão humana (nível 3 e N3★)
Dados protegidos, 2024, microdados; mudança científica; mudança de escopo ou limites da missão; instalação ou alteração de dependências; `sudo`, usuário, AppArmor, sistema; alterar controles, hook, política, L0; operações irreversíveis (apagar, mover, renomear, push, merge, publicação); aceitar risco residual; **iniciar** qualquer etapa nova.
