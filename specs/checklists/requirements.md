# Checklist de qualidade do spec

> Adaptado do Spec Kit para projeto acadêmico de ML. Refazer a cada mudança relevante do spec e
> antes da entrega (T-7.3).
> **Última avaliação:** 2026-11-24, spec v0.21 e plan v0.20 (Marcos 1 a 7 concluídos; teste de 2024 avaliado uma vez). A seção "Comparação em 2025 (Marco 8)", no fim, tem itens abertos de propósito (SC-09 no spec e auditoria da T-8.13). Seção Comparação revisada em 2026-11-24 (T-8.12): itens abertos são o `.docx` e a linha do SC-09 (T-8.12) e a auditoria (T-8.13).

## Requisitos

- [x] Todo FR e NFR tem ID e é testável. 22 IDs de FR, 21 ativos (FR-15 riscado), e 6 NFR. Ressalva: NFR-04 (ética)
  se verifica pelo texto do relatório, não por teste automático. FR-21 não cumprido, registrado como limitação (D-94).
- [x] Requisitos sem detalhe de implementação. Ressalvas que ficaram de propósito: FR-11 cita
  Streamlit (D-17) e FR-07/FR-22 citam o MLflow como lugar do registro. FR-11 passa a citar a demo local, com publicação adiada (D-94).
- [x] Critérios de sucesso mensuráveis (SC-01 a SC-08).
- [x] Histórias US1–US3 com prioridade, teste independente e cenários Dado/Quando/Então.
- [x] Casos-limite listados.
- [x] [Não-objetivos](../spec.md#não-objetivos) listados.

## Formulação de ML

- [x] Alvo, unidade de predição e momento da predição definidos ([spec › Formulação do problema](../spec.md#formulação-do-problema)).
- [x] Split coerente com o uso real (temporal + leave-one-region-out), e o teste é usado uma vez
  ([spec › Split e vazamento](../spec.md#split-e-vazamento), R1, R2).
- [x] Toda coluna passou pela [revisão de vazamento](../spec.md#revisão-de-vazamento): as 121 colunas do arquivo de 2022.
- [x] [Baselines](../spec.md#baselines) definidos e critérios de sucesso relativos a eles (SC-01, SC-02, SC-04).
- [x] Métrica primária justificada pelo custo dos erros ([spec › Usuários e custo dos erros](../spec.md#usuários-e-custo-dos-erros), [Plano de avaliação](../spec.md#plano-de-avaliação)); incerteza com IC bootstrap.
- [x] Avaliação por subgrupo planejada, com aviso para subgrupos com < 100 eventos.
- [x] **Resultado final reprodutível a partir de semente, config e versão dos dados.** Verificado em 2026-11-23 (T-7.3): os 14 arquivos regerados pelo `evaluate` saíram idênticos byte a byte (mais 3 PNGs que já estavam no clone e não são regerados; só o `LACRE.json` difere, em `commit` e `gravado_em_utc`), sem reavaliar o lacre original (`reports/verificacao/T-7.3-nfr02.json`). Ressalva: reproduz a avaliação com os modelos congelados; não retreinou do zero.

## Marcadores e decisões

- [x] Nenhum `[DECISION NEEDED]` aberto.
- [x] **`[ASSUMPTION]` revisados pelo Programador.** Revisados em 2026-11-23 (D-95): 41 marcadores de fato (`spec.md` 11, `plan.md` 18, `data-model.md` 3, `contracts/interfaces.md` 4, `tasks/03` 2, `tasks/04` 1, `tasks/05` 1 e `tasks/06` 1), 37 confirmados em bloco e 4 com decisão consciente (FR-21, mapeamento do B2, células < 10 e ordem de simplicidade). Marcadores mantidos no texto, como histórico; os principais estão em
  [spec › Premissas](../spec.md#premissas).
  - Reconciliada em 2026-11-23: a diferença de 3 em `spec.md` (14 contra 11 do D-95) era a frase de SC-01 a SC-04 (agora ratificada pelo D-95, sem marcador), uma menção ao próprio marcador (linha 212) e o marcador de Marcos, que o Programador confirmou como está em 2026-11-23 (marcador retirado).
- [x] **Todo `[VERIFY]` conferido ou fechado.** Fechados em 2026-11-23 (T-7.3): `TP_SISTEMA` e `NDUPLIC_N` (não constam no dicionário oficial, limitação declarada); marcadores do ambiente, da literatura e do relatório retirados por decisão do Programador. Restam apenas menções históricas no Registro de decisões (D-82, D-94). Fechados antes, em D-94: eventos por par de comorbidades; TabFM (D-91); SQLite do Optuna no Drive; `tabfm_v1_1_0` (D-90); `ALRM_*` em casos 10, não aplicável (M2 não implementado).
- [x] [Registro de decisões](../research.md#registro-de-decisões) com uma entrada por escolha
  significativa (D-01 a D-95).
- [x] **Perguntas em aberto respondidas.** Q-13 respondida no D-94 (não houve revisão por profissional de saúde; limitação registrada); Q-08 foi delegada ao agente (D-68) e Q-14 resolvida (D-70).

## Marcos

- [x] [Marcos](../spec.md#marcos) cobrem todos os FR com MUST e têm critérios de saída
  verificáveis. Prazos ficam fora do spec (D-29, D-31). Marcos 5 e 6 concluídos; o teste cumpriu SC-01, SC-03 e SC-04 e falhou em SC-02 (reportado). Marco 7 concluído em 2026-11-23: este checklist passa, sem itens abertos.

## Relatório TRIPOD+AI (T-7.3, 2026-11-23)

- [x] Cada item do Apêndice D (`reports/relatorio/relatorio.md`) aponta para uma seção que existe: Capa, Resumo, Abstract, 1.1 a 1.4, 2.1 a 2.10, 3.1 a 3.5.5, 4.1 a 4.3, 5, Tabela 1 e Tabela 2. Ressalva: o item "Métodos: equidade" cita a 2.7, que não fala de subgrupos (eles aparecem só em 3.5.5).
- [x] Itens "Parcial" e "Não feito" têm motivo na própria tabela: 5 Parcial e 1 Não feito, de 17 itens.
- [x] Amostra de 12 números do relatório contra `reports/`: PR-AUC do M1 0,03463 e IC, recall 0,6528, precisão 0,00975, 759.006 alertas, OR 9,32, 6,80 e 5,02, 0,194% e 2,987%, PR-AUC da validação 0,02838, Brier 0,002086, observado/esperado 1,301, B1 0,0166. Todos batem com a fonte.
- [x] "Outras informações": financiamento e conflitos declarados pelo Programador em 2026-11-23 (sem financiamento externo, sem conflitos); o usuário do GitHub na URL do repositório foi autorizado por ele.
- [x] Capa: por decisão do Programador (2026-11-23), o relatório não tem capa com instituição e autor nem folha de rosto; a capa traz só o título da pesquisa. Nenhum `[PREENCHER]` no `.md` nem no `.docx`.
- [x] `[VERIFY]` no relatório: nenhum aberto.

## Comparação em 2025 (Marco 8)

- [x] FR-23, SC-09 e US4 existem no spec com IDs novos, sem renumerar, e a seção do plan e o contrato
  correspondentes (T-8.0). Os `[ASSUMPTION]` novos (orçamentos de alertas 5%, 10% e 14%; 1.000 reamostras; regra de
  "melhor" pelo IC da diferença) aguardam a revisão do Programador.
- [x] Constituição 1.5 (R1 e R2 com o ano de comparação) e D-97 registrados; porta, config e manifesto com testes
  (T-8.1 a T-8.3).
- [x] Scripts isolados da `soneca` e da `lora` validados, sem leitura de 2024 nem de 2025 (T-8.4 e T-8.5).
- [x] Previsões do próprio projeto dentro da porta (T-8.6); B0 e B1 finais copiados do Drive. Verificado na T-8.6: 42 testes, previsões de 2022 sem métrica, `prever_projeto.py` com SHA-256 conferido antes da carga.
- [x] Avaliador, gráficos e orquestrador com ensaio ponta a ponta em ano sintético (T-8.7 a T-8.9). Verificado nas tarefas T-8.7 a T-8.9 (testes e ensaio em tmp, sem 2025 nem 2024).
- [x] "Ok" do Programador e execução única em 2025, com lacre (T-8.10 e T-8.11). Lacre em `reports/comparacao/LACRE.json`; `reports/verificacao/T-8.11.json` com `passou: true` em 6 checks.
- [x] Relatório e README atualizados com o resultado real (T-8.12). `reports/relatorio/relatorio.md` (seções 3.7 e 4.4, Resumo, Abstract, Apêndices A, C, D e E), o `.docx` (regerado com `gerar_docx.js` e reduzido por `comprimir_docx.py`, para caber no limite do R7) e `README.md`, com números de `reports/comparacao/`.
- [ ] SC-09 com o resultado real registrado no spec (T-8.12). **Pendente:** o agente não edita o spec; a prova do SC-09 está na seção 3.7 do relatório (bloco "SC-09") e a linha a registrar depende do Programador.
- [ ] Auditoria do marco e limpeza dos worktrees (T-8.13). Fora do escopo da T-8.12.
