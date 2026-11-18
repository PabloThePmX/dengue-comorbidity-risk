# Questões abertas (F2.0-C.3)

Nada abaixo foi provado. Cada item diz o que falta para responder. Classe atual: **H** hipótese ou **L** limitação.

## A. Técnicas (resolvem na F2.0-D)
| # | Questão | Por que importa | Como testar |
|---|---|---|---|
| Q1 | Uma negação real de `Agent` (spawn) funciona? | Controla delegação (I2) | Hook nega `Agent` de nome fora da lista; ver log |
| Q2 | Alterar `.claude/settings*.json` durante a sessão muda o comportamento? | R18 | Editar o arquivo no meio da sessão, observar hook |
| Q3 | Filho do Bash consegue usar o socket `uds-messaging`? | R19 | Tentar conexão a partir de processo confinado e não confinado |
| Q4 | `deny` cobre `python -c`, `head`, `base64`, `sed`? | R1 | Canário sintético em cada comando |
| Q5 | `--tools` traz `Glob`/`Grep`? O hook os vê? | I1 | Rodar com `--tools` listando-os |
| Q6 | O que cria `.claude/.cc-writes/` sem sandbox? | I6, R12 | Sessão sem sandbox com Bash e Write |
| Q7 | Landlock está disponível e em qual ABI? | Alternativa a bwrap | `landlock_create_ruleset` com a flag de versão |
| Q8 | `bwrap` roda `pytest` com o repositório? | Viabilidade de R1 | Teste sintético confinado |
| Q9 | `updatedInput` reescrito interage como com `deny`? | Encaixe hook+isolamento | Teste com `cat` de canário nos dois casos |
| Q10 | `CLAUDE_CONFIG_DIR` por missão mantém o login? | Isolar `~/.claude` | Teste em diretório temporário |
| Q11 | Agente de arquivo × `--agents` (sombreamento), `~/.claude/agents`, plugins | R28 | Reverter E10a quando houver caminho de gravação autorizado |
| Q12 | Por que o sandbox do CLI falha e o `bwrap` direto funciona? | Escolher caminho | Comparar capacidades, AppArmor; sem alterar o sistema |
| Q13 | Comportamento com modelo de produção, não só Haiku | Generalização | Repetir pontos críticos |
| Q14 | `--max-budget-usd` ultrapassa por quanto na prática? | Margem de custo (D5). **Falta:** nenhuma medição; a flag nem foi usada | Sessão controlada com teto baixo, medindo `total_cost_usd` contra o teto |
| Q15 | O que dispara a mensagem de `bypassPermissions` negado? | Interpretação (I4) | Isolar `disableBypassPermissionsMode` |

## B. De processo e ambiente
| # | Questão | Observação |
|---|---|---|
| Q16 | O repositório não tem `.git`: como fazer commits locais e comparar diffs? | Linha 45 da matriz; exige decisão (inicializar é nível 3) |
| Q17 | Rate limit de conta ~0,94: qual é a janela e o custo esperado por missão? | Pode limitar autonomia (D5). **Falta:** janela de renovação (a Peach foi interrompida por 429 com hora de reset), custo por sessão de cada papel, custo de uma missão pequena. Só medição dá isso |
| Q18 | Onde fica o arquivo de missão fora do alcance dos agentes, e como você o confirma em TTY de forma confortável? | D4. **Falta:** o local (D6) e a prova de que agentes confinados não o alcançam (CP-5); sem confinamento, o mesmo usuário Unix altera o arquivo |
| Q19 | Quem mantém e audita `l0.py` e `isolar.py`? | Ponto único de falha |
| Q20 | Entrega de arquivos pelo dispositivo teve falha silenciosa (C1). A causa? | Mitigação: reler e conferir tamanho |
| Q21 | Mapeamento linha a linha da matriz de 41 linhas da auditoria anterior para as 54 atuais | O texto original não está nos documentos de `f2/`; precisa do arquivo da auditoria anterior (M3) |
| Q22 | Texto original de M5, M7 e N1–N7 da auditoria anterior | Os significados em `registro_riscos.md` são inferidos do uso (ver `rastreabilidade.md`) |
| Q23 | Tamanho do código de bootstrap a revisar | Falta estimativa para você decidir D9 |
| Q24 | Valor de `fs.protected_hardlinks`/`protected_symlinks` no kernel local | Importa para R33; verificação é leitura de `sysctl`, a testar na F2.0-D |
| Q25 | O `claude` confinado mantém o login e as escritas necessárias? | Base de R32 (A4) |
| Q26 | Local dos canários fora do repositório (D3) | Você indica; proposta C.3: `~/dengue_f2d/` (0700), alternativa subdiretório aleatório em `/tmp` (a proposta C.2, `/tmp/dengue_f2d/`, tinha nome previsível) |
| Q27 | Como manter a API acessível ao `claude` confinado sem abrir rede aos filhos | `plano_isolamento_r1.md` §6A; X09, X14, X21 |
| Q28 | Forja de TTY por processo filho (X11 num pty do harness) | M-6 da terceira auditoria |
| Q29 | Quem revisa o harness antes de rodar (Peach e você) e como registrar o hash | Pré-requisito da F2.0-D |
| Q30 | Valores exatos das flags citadas no perfil B (`--setting-sources`, `--tools ""`, `--agents`, `--permission-mode dontAsk`) na versão 2.1.327 | Conferir na D0 pela documentação instalada (`claude --help`); não verificado aqui; `claude --help` é execução do CLI e só entra se a D0 permitir, caso contrário fica H |
| Q31 | `--strict-mcp-config` exclui também os conectores da conta (Drive)? | H; só o `init` de XB0 responde; se não excluir, o pacote B continua bloqueado |
| Q32 | Lista exata dos subdiretórios de estado do CLI em `~/.claude` (tolerados no snapshot) | Proposta em `f2_0d_especificacao.md` §4.6; a medir na F2.0-D (a D0 não executa nada) |
| Q33 | Como revogar a sessão de login criada em X20 depois da limpeza, e se a remoção do diretório basta | Não verificado; decisão e ação suas |
| Q34 | Escopo de D10: o texto "aceita com complemento" vale só para CP-1 e CP-1H (leitura adotada) ou também para CP-2 a CP-9? | Leitura registrada em `matriz_decisoes_humanas.md`; confirmação sua pendente. CP-2 a CP-9 **não** foram aceitos |
| Q35 | A lista do §4.1 (itens 1 a 7) é a dos "locais expressamente autorizados" da D0? E D3 itens 2 a 6 (local-base, tetos, criar e remover, modo do CC-local, reafirmação de §4.3 e §4.6) | Interpretação adotada na D0; decisão sua pendente; os itens 2 a 6 são exigidos na F2.0-D |
| Q36 | Comportamento real de `bwrap`, Landlock (ABI), pty e dos canários no seu ambiente | H; o harness foi escrito sem execução; só a F2.0-D, se autorizada, responde |

Fora do escopo da F2.0-D (não testáveis aqui): Q11 (parcial; `~/.claude/agents` e plugins exigem tocar o `~/.claude` real, proibido), Q13 (modelo de produção) e Q15 (`bypassPermissions`: sem experimento definido). Ficam H ou L.

## C. Pendentes de decisão humana
D1 a D10 (D3 inclui D3-B futura), DX-1 (versão do Claude Code), DX-2 (hash dos arquivos de manifesto) e DX-3 (confiança no lançador) em `matriz_decisoes_humanas.md`; DP-001; Etapa 3.2 (sem aprovação científica). Nenhuma foi decidida.
