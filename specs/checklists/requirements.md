# Checklist de qualidade do spec

> Adaptado do Spec Kit para projeto acadêmico de ML. Refazer a cada mudança relevante do spec e
> antes da entrega (T-7.3).
> **Última avaliação:** 2026-11-23, spec v0.20 e plan v0.19 (Marcos 1 a 6 concluídos; teste de 2024 avaliado uma vez; Marco 7 em andamento). Pendente: edições propostas no D-94 e conferência da Sakura.

## Requisitos

- [x] Todo FR e NFR tem ID e é testável. 22 FR (FR-15 riscado) e 6 NFR. Ressalva: NFR-04 (ética)
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
- [x] **Resultado final reprodutível a partir de semente, config e versão dos dados.** Verificado em 2026-11-23 (T-7.3): 17 de 17 arquivos idênticos byte a byte, sem reavaliar o lacre original (`reports/verificacao/T-7.3-nfr02.json`). Ressalva: reproduz a avaliação com os modelos congelados; não retreinou do zero.

## Marcadores e decisões

- [x] Nenhum `[DECISION NEEDED]` aberto.
- [ ] **`[ASSUMPTION]` revisados pelo Programador.** São 41 marcadores de fato em 2026-11-23 (`spec.md` 11, `plan.md` 18, `data-model.md` 3, `contracts/interfaces.md` 4, `tasks/03` 2, `tasks/04` 1, `tasks/05` 1 e `tasks/06` 1; as demais ocorrências do texto são menções; o FR-21 deixou de ser marcador no D-94). Os principais estão em
  [spec › Premissas](../spec.md#premissas); os demais, no texto. Nenhum foi revisado ainda (decisão do Programador: revisão adiada).
- [ ] **Todo `[VERIFY]` conferido ou listado como pendente.** Pendentes:
  - dados: significado de `NDUPLIC_N` e `TP_SISTEMA` no dicionário;
  - ambiente: saldo do Colab Pro; `PRAUC` do CatBoost em GPU e torch com CUDA 13 no Colab (a confirmar no Registro; vCPUs e RAM alta conferidos em 2026-11-15: 8 vCPUs, 50,99 GiB);
  - literatura: ler no texto completo Sangkaew et al., Steyerberg & Harrell e Collins (parte 1);
    conferir no PDF a validação de Huang et al. e a ficha do protocolo do MS.
  - Fechados em D-94: eventos por par de comorbidades; TabFM (limite de contexto e velocidade, D-91); SQLite do Optuna no Drive; `tabfm_v1_1_0` (D-90); `ALRM_*` em casos 10, não aplicável (M2 não implementado).
- [x] [Registro de decisões](../research.md#registro-de-decisões) com uma entrada por escolha
  significativa (D-01 a D-94).
- [x] **Perguntas em aberto respondidas.** Q-13 respondida no D-94 (não houve revisão por profissional de saúde; limitação registrada); Q-08 foi delegada ao agente (D-68) e Q-14 resolvida (D-70).

## Marcos

- [x] [Marcos](../spec.md#marcos) cobrem todos os FR com MUST e têm critérios de saída
  verificáveis. Prazos ficam fora do spec (D-29, D-31). Marcos 5 e 6 concluídos; o teste cumpriu SC-01, SC-03 e SC-04 e falhou em SC-02 (reportado).
