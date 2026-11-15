# Checklist de qualidade do spec

> Checklist do padrão Spec Kit (D-55), adaptado para projeto acadêmico de ML. Ele substitui o
> checklist de "spec pronto" que ficava no `CLAUDE.md`. Refazer a cada mudança relevante do spec e
> antes da entrega (T-7.3).
> **Última avaliação:** 2026-11-15, spec v0.18, Marcos 1 a 7 concluídos (pipeline completo e teste de 2024 lacrado).

## Requisitos

- [x] Todo FR e NFR tem ID e é testável. 22 FR (FR-15 riscado) e 6 NFR. Ressalva: NFR-04 (ética)
  se verifica pelo texto do relatório, não por teste automático.
- [x] Requisitos sem detalhe de implementação. Ressalvas que ficaram de propósito: FR-11 cita
  Streamlit (D-17) e FR-07/FR-22 citam o MLflow como lugar do registro.
- [x] Critérios de sucesso mensuráveis (SC-01 a SC-08).
- [x] Histórias US1–US3 com prioridade, teste independente e cenários Dado/Quando/Então.
- [x] Casos-limite listados.
- [x] Não-objetivos listados (§3.3).

## Formulação de ML

- [x] Alvo, unidade de predição e momento da predição definidos (§3.6).
- [x] Split coerente com o uso real (temporal + leave-one-region-out), e o teste é usado uma vez
  (§3.8, R1, R2).
- [x] Toda coluna passou pela revisão de vazamento: as 121 colunas do arquivo de 2022 (§3.8).
- [x] Baselines definidos (§3.10) e critérios de sucesso relativos a eles (SC-01, SC-02, SC-04).
- [x] Métrica primária justificada pelo custo dos erros (§3.4, §3.12); incerteza com IC bootstrap.
- [x] Avaliação por subgrupo planejada (§3.12), com aviso para subgrupos com < 100 eventos.
- [x] **Resultado final reprodutível a partir de semente, config e versão dos dados.** Verificado
  por semente única `20261103`, hashes SHA-256 dos parquets e dos bundles congelados
  (`models/e1_final.joblib` e `models/m1_final.joblib`) registrados em `reports/teste/LACRE.json`
  e validados com precisão `< 1e-9` em `reports/verificacao/T-3.1_a_T-3.6.json`,
  `reports/verificacao/sessao-m1.json` e `reports/verificacao/T-5.1_a_T-5.4.json` (T-7.3).

## Marcadores e decisões

- [x] Nenhum `[DECISION NEEDED]` aberto.
- [x] **`[ASSUMPTION]` revisados pelo Programador.** Revisados e mantidos na execução final dos
  Marcos 2 a 7.
- [x] **Todo `[VERIFY]` conferido ou listado como pendente.** Conferidos na execução real:
  - dados: `NDUPLIC_N` e `TP_SISTEMA` auditados em `reports/verificacao/T-2.1.json`; 15 de 21
    pares de comorbidades com $\ge 10$ eventos em `reports/descritiva/pares_comorbidades.md`;
  - ambiente: executado em GPU NVIDIA L4 (22,5 GB VRAM, 53 GB RAM) no Colab Pro; CatBoost em GPU
    com métrica `PRAUC` em CPU; PyTorch CUDA funcional;
  - TabFM (`TabPFN v2`, Apache-2.0): executado com subamostra estratificada de 10.000 linhas por
    fold (`PR-AUC OOF = 0,0121`);
  - literatura: citações e achados documentados no relatório TRIPOD+AI (`reports/relatorio_tripod_ai.md`).
- [x] Registro de decisões com uma entrada por escolha significativa (D-01 a D-55, research.md).
- [x] **Perguntas em aberto respondidas.** Q-08 fechada em `configs/m1.yaml`; Q-13 documentada no
  Apêndice D de `reports/relatorio_tripod_ai.md`; Q-14 fechada com os bundles reais congelados
  (`models/e1_final.joblib` e `models/m1_final.joblib`).

## Marcos

- [x] Marcos cobrem todos os FR com MUST e têm critérios de saída verificáveis (§3.18). Prazos
  ficam fora do spec (D-29, D-31).
