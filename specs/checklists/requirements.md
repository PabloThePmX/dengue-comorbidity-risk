# Checklist de qualidade do spec

> Checklist do padrão Spec Kit (D-55), adaptado para projeto acadêmico de ML. Ele substitui o
> checklist de "spec pronto" que ficava no `CLAUDE.md`. Refazer a cada mudança relevante do spec e
> antes da entrega (T-7.3).
> **Última avaliação:** 2026-11-04, spec v0.17, só o desenho (Marco 1 concluído; nada de modelagem).

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
- [ ] **Resultado final reprodutível a partir de semente, config e versão dos dados.** O desenho
  está no plan (§3.14), mas o método de verificar a NFR-02 sem violar R2 ainda não foi definido
  (T-7.3).

## Marcadores e decisões

- [x] Nenhum `[DECISION NEEDED]` aberto.
- [ ] **`[ASSUMPTION]` revisados pelo Programador.** São ~45 no total. Os principais estão em
  "Premissas" no spec; os demais, no texto. Nenhum foi revisado ainda.
- [ ] **Todo `[VERIFY]` conferido ou listado como pendente.** Pendentes:
  - dados: significado de `NDUPLIC_N` e `TP_SISTEMA` no dicionário; valores de `ALRM_*` nos casos
    10 (só no M2); eventos por par de comorbidades (Marco 2);
  - ambiente: saldo e GPUs do Colab Pro; vCPUs da VM e `PRAUC` do CatBoost em GPU; torch com
    CUDA 13 no Colab;
  - TabFM: licença para uso acadêmico, limite de contexto e de features, velocidade;
  - literatura: ler no texto completo Sangkaew et al., Steyerberg & Harrell e Collins (parte 1);
    conferir no PDF a validação de Huang et al.
- [x] Registro de decisões com uma entrada por escolha significativa (D-01 a D-55, research.md).
- [ ] **Perguntas em aberto respondidas.** Restam Q-08 (espaço de busca), Q-13 (profissional de
  saúde) e Q-14 (modelo da demo).

## Marcos

- [x] Marcos cobrem todos os FR com MUST e têm critérios de saída verificáveis (§3.18). Prazos
  ficam fora do spec (D-29, D-31).
