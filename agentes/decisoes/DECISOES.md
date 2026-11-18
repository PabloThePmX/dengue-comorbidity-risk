# Registro de decisões da equipe de agentes

> Só acréscimo. Prefixo `DA-` para não colidir com os `D-xx` do `research.md` nem com os `D1`–`D8` da Etapa 3.1.
> Todas as decisões abaixo vêm do usuário (Programador), nas mensagens de 2026-11-18 (09:13, 09:21 e 09:34, fuso America/Sao_Paulo).

| ID | Decisão | Origem |
|---|---|---|
| DA-001 | Arquitetura aprovada: Yoshi como agente principal (`--agent`); Mario, Luigi e Peach como subagentes em primeiro plano; sem agent teams; sem plugin; comunicação por arquivos. `autorizacao.json` só o usuário grava. | Aprovação da arquitetura |
| DA-002 | Roadmap principal = etapas do projeto. As T-x.y de `specs/tasks/` são mapeadas às etapas. Sem dois roadmaps conflitantes. | Decisão 1 |
| DA-003 | Limite padrão de 3 ciclos de correção. Ao atingi-lo, interromper a automação e pedir intervenção humana. | Decisão 2 |
| DA-004 | Opus para a Peach, se disponível; Sonnet para Mario, Luigi e Yoshi. Registrar o modelo efetivo nos relatórios. Indisponibilidade: informar, nunca substituir em silêncio. | Decisão 3 |
| DA-005 | A Peach pode reexecutar testes automatizados seguros. Não pode modificar código, instalar dependências, acessar dados protegidos, treinar modelos fora do `pytest` nem executar experimentos. Antes de rodar, verifica se os testes modificam arquivos. Prefere execução sem cache e arquivos temporários fora do repositório. | Decisão 4 |
| DA-006 | Python por meio de `uv run`, respeitando dependências e configurações existentes. As opções `--frozen --no-sync` são **proposta** a validar na F2, não decisão. | Decisão 5 |
| DA-007 | Parágrafo no `CLAUDE.md`: com a equipe em operação, a ficha da tarefa é a única fonte de escopo autorizado, sem eliminar nem enfraquecer restrições metodológicas. | D1 |
| DA-008 | Luigi e Peach podem rodar a suíte `pytest`, inclusive testes que treinam modelos pequenos, **só com os dados sintéticos dos testes**. Proibidos: treino por scripts avulsos, experimentos e microdados reais. | D2 |
| DA-009 | Leitura de bytes para SHA-256 dos históricos já contemplados nos testes. Proibido exibir, imprimir, interpretar, copiar ou usar o conteúdo. O relatório registra caminho, finalidade e hash. | D3 |
| DA-010 | Arquivos de 2024 **não** são movidos automaticamente. Implementar bloqueios de acesso agora; eles permanecem depois de qualquer movimentação. Antes de mover: lista exata com caminhos e hashes, e autorização expressa. | D4 |
| DA-011 | Mario: apenas `ruff --no-cache` e `python -m py_compile`, sem a suíte completa. | D5 |
| DA-012 | Vínculos de baixa confiança ficam **pendentes**. T-5.1 a T-5.4 bloqueadas por decisão humana. Divergência T-2.8 × Etapa 3.2 registrada sem alterar resultados. | D6 |
| DA-013 | Etapa 3.2 **em análise**, não aprovada. Aprovação técnica só depois do parecer da Peach. Aprovação técnica não é validação clínica. | D7 |
| DA-014 | Versão local confirmada pelo usuário: Claude Code 2.1.327 (nativo, linux-x64, commit f467840f2a4c). Observação do `doctor`: sem login no claude.ai nesse terminal; a disponibilidade do Opus **não** foi verificada. | Saída de `claude doctor` |
| DA-015 | Arquivos lidos por hooks ficam em JSON (hooks só com biblioteca padrão), em vez de YAML. Ajuste de implementação, sem efeito metodológico. | Ajuste da F1 |
| DA-016 | Política de proteção v2 (`protegidos.json`, esquema 2): dois eixos (leitura `livre<so_hash<nunca`; escrita `ficha<anexar<criar<humano`); vale o mais restritivo entre todos os itens que casam, sem depender da ordem; concessão a agente nunca anula classe mais restritiva; escrita nega por padrão; política inválida nega tudo; nenhum agente exclui, move ou renomeia. Os 9 arquivos `teste_*` e os 12 `oof_*.npz` passam a `SOMENTE_HASH`. | Autorização de implementação (09:52) |
| DA-017 | Semântica de `SOMENTE_HASH`: agentes não leem o conteúdo e não calculam hash por conta própria; integridade só por `manifesto.py verificar`. Processos de `pytest` podem calcular hash internamente (DA-008, DA-009). O `LACRE_TESTE_2024.json` é `SOMENTE_HASH` com `natureza: lacre_de_integridade`. | Idem |
| DA-018 | `DECISOES.md` é só-humano. O Yoshi propõe em `agentes/decisoes/propostas/DP-nnn.md` (só criação). `relatorios/` e `evidencias/` são só criação por agente; `execucoes.jsonl` é só acréscimo (Yoshi). `criterios/**` e `tarefas/_modelo.md` são só-humano. | Idem |
| DA-019 | `data/**`, `*.parquet`, `*.dbc`, `*.dbf` e `artefatos/oof/**` são `NUNCA_ACESSAR` (grupo `microdados`). Padrões de 2024 formam o grupo `2024`, permanente e sem diferenciar caixa, e continuam valendo depois de qualquer movimentação. Não foi criado padrão genérico `**/*2024*`, para não capturar o lacre. | Idem |
| DA-020 | Manifesto versionado e encadeado: `manifesto_hashes.json` = v001 (legado, intocado); v002+ em `estado/manifestos/` (nunca sobrescreve; cada versão guarda o hash da anterior e os hashes da política, do script e da biblioteca); `verificar [--versao]` e `comparar A B`; hashes de 2024 só em `local-2024-vNNN.json`, fora do Git, só com `--incluir-2024`. Contra a v001, `protegidos.json` aparece como ALTERADO de propósito. | Idem |
| DA-021 | Interpretação registrada de "autorizo a implementação" (09:52): implementar F1.1 a F1.4 (política, biblioteca, manifesto v2, testes, documentos). F1.5 (gerar o manifesto v002) é executada **pelo usuário**. F2 e os agentes **não** foram iniciados; sandbox **não** habilitado. Subdecisões sem resposta seguiram a recomendação e são reversíveis. | Interpretação do implementador, a confirmar |
