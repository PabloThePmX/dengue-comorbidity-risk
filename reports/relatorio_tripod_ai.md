# Relatório Técnico (TRIPOD+AI) — Risco de Desfecho Grave em Dengue por Perfil de Comorbidades

> **Status:** Estrutura completa segundo o checklist TRIPOD+AI (T-7.1, T-7.2). As tabelas numéricas finais de E1, M1 e teste 2024 são preenchidas automaticamente em `reports/` após a execução dos notebooks `02_fundacao.ipynb`, `03_perfil_e1.ipynb`, `04_modelos.ipynb` e `05_teste_final.ipynb` no Google Colab.

---

## 1. Título e Resumo Estruturado (TRIPOD+AI Itens 1–2)

- **Título:** Desenvolvimento e validação temporal-geográfica de modelos explicativo (E1) e preditivo de triagem (M1) para desfecho grave ou óbito por dengue segundo o perfil de comorbidades no Brasil (SINAN, 2022–2024).
- **Contexto e Objetivos:** Quantificar o efeito independente e combinado das 7 comorbidades registradas na ficha do SINAN-Dengue sobre o risco de dengue grave ou óbito (US1 — modelo explicativo E1) e apoiar a triagem clínica inicial com sintomas no momento da notificação (US2 — modelo preditivo M1).
- **Fontes de Dados:** Microdados públicos e desidentificados do SINAN-Dengue (DataSUS, arquivos `FINAIS` de 2022, 2023 e 2024), totalizando 7.784.953 casos confirmados elegíveis (2.453.208 em 2022–2023 com 3.985 eventos; 5.331.745 em 2024 com 11.338 eventos).
- **Desfecho (Alvo):** Dengue grave (`CLASSI_FIN == 12`) ou óbito pelo agravo (`EVOLUCAO == 2`).

---

## 2. Introdução e Diferencial (TRIPOD+AI Itens 3–4, Spec §3.2)

1. **Problema Clínico e Epidemiológico:** A dengue apresenta baixa prevalência de desfecho grave/óbito (~0,16% em 2022–2023 e ~0,21% em 2024 entre casos confirmados), mas o volume absoluto em anos epidêmicos sobrecarrega a rede assistencial.
2. **Diferencial frente aos Trabalhos Relacionados (§3.2):**
   - Separação estrita entre **inferência epidemiológica de perfil (E1)** — ajustada exclusivamente com variáveis pré-infecção (idade em spline, sexo, gestação, 7 comorbidades e interações) para evitar bloqueio de mediadores — e **predição de triagem clínica (M1)** com sintomas iniciais.
   - Avaliação de **interação aditiva (RERI e Proporção Atribuível — AP)** além da escala multiplicativa (Odds Ratio com correção de Benjamini-Hochberg).
   - Validação cruzada geográfica **leave-one-region-out (LORO)** em 2022–2023 seguida de **teste temporal cego em 2024** (ano de reintrodução do DENV-3 e epidemia histórica).

---

## 3. Métodos (TRIPOD+AI Itens 5–12)

### 3.1 Fonte de Dados e Ética (NFR-04)
- Microdados públicos e **desidentificados** (não "anonimizados", pois combinações raras de idade, município e data exigem supressão de células `< 10` conforme regra R7) provenientes do FTP oficial do DataSUS (`SINAN/DADOS/FINAIS/DENGBR{22,23,24}.dbc`).
- Dispensa de apreciação pelo sistema CEP/CONEP nos termos da **Resolução CNS nº 510/2016, art. 1º, parágrafo único, inciso II**.

### 3.2 População e Definição do Desfecho (D-22, Spec §3.6)
- **Critério de inclusão:** Casos confirmados de dengue (`CLASSI_FIN` ∈ {10, 11, 12}) com rótulo de evolução conhecido e idade válida em `[0, 120]` anos (com recuperação de idade por `ANO_NASC` quando `NU_IDADE_N` vem sem dígito de unidade, especialmente no Espírito Santo em 2022 — D-50).
- **Por que o alvo difere do pré-projeto (D-22, Spec §3.6):** No pré-projeto cogitou-se incluir `CLASSI_FIN == 11` (dengue com sinais de alarme) no desfecho ou usar `HOSPITALIZ` como proxy. O profiling revelou que `ALRM_*` está preenchido em 99,8% dos casos `11` e define o próprio código `11` (circularidade tautológica), enquanto `HOSPITALIZ` sofre de preenchimento tardio e variação assistencial. Assim, o desfecho principal `y` foi fixado estritamente como **dengue grave (`CLASSI_FIN == 12`) ou óbito por dengue (`EVOLUCAO == 2`)** (D-02, D-22).

### 3.3 Preditores e Prevenção de Vazamento (R4, R5)
- **Lista fechada de preditores (`data-model.md §D`):**
  - **E1 (Perfil):** `idade_anos` (spline cúbica restrita), `sexo`, `gestante`, e as 7 comorbidades (`DIABETES`, `HEMATOLOG`, `HEPATOPAT`, `RENAL`, `HIPERTENSA`, `ACIDO_PEPT`, `AUTO_IMUNE`).
  - **M1 (Triagem):** Perfil + `n_comorbidades` + 12 sintomas (`FEBRE`, `MIALGIA`, `CEFALEIA`, `EXANTEMA`, `VOMITO`, `NAUSEA`, `DOR_COSTAS`, `CONJUNTVIT`, `ARTRITE`, `ARTRALGIA`, `DOR_RETRO`, `PETEQUIA_N`) + `LEUCOPENIA` e `LACO` + `dias_ate_notificacao` truncado em `[0, 60]`.
  - **Exclusões contra vazamento (R4):** Ficam de fora `PETEQUIAS` e `LACO_N` (campos legados de FHD que atuam como proxy do rótulo), `ALRM_*`, `GRAV_*`, `HOSPITALIZ`, `DT_INTERNA`, `DT_OBITO`, `regiao`, `faixa_etaria`, `CS_RACA` e `ANO`.

### 3.4 Partição de Dados, Modelos e Hiperparâmetros (R1, R3, R6, D-33, D-38)
- **Split temporal e geográfico:** Desenvolvimento em 2022–2023 com 5 dobras geográficas LORO (`Sudeste`, `Sul`, `Centro-Oeste`, `Nordeste`, `Norte`) e parada antecipada (*early stopping*) em subamostra estratificada interna de 10% das 4 regiões de treino (R6). Teste cego e único em 2024 (R1, R2).
- **Ausência de correção de desbalanceamento (R3, D-38):** Não são utilizados `class_weight`, `scale_pos_weight`, `auto_class_weights`, `pos_weight`, SMOTE ou undersampling sem correção analítica, pois tais técnicas distorcem as probabilidades previstas e degradam severamente a calibração clínica num evento de ~0,16%.
- **Escolha de F2 vs. F0.5 na definição do limiar (D-33):** Na triagem de dengue grave/óbito, o custo clínico de um falso negativo (alta indevida de paciente que evolui para choque/óbito) supera amplamente o custo de um falso positivo (observação/hidratação adicional do Grupo B). Por isso o limiar operacional é escolhido maximizando **$F_2$** (que atribui peso 2× maior ao *recall* que à precisão) nas predições OOF calibradas.

---

## 4. Resultados (Referência aos Artefatos Gerados)

1. **Fluxograma de Exclusão (FR-02):** Ver `reports/fluxograma.md`.
2. **Análise Descritiva e Pares/Trincas (T-2.6, T-2.7):** Ver `reports/descritiva/tabela1.md`, `reports/descritiva/riscos_brutos.md`, `reports/descritiva/pares_comorbidades.md` e `reports/descritiva/combinacoes_3mais.md`.
3. **Baselines B0, B1 e B2 (T-2.8):** Ver `reports/baselines.md`.
4. **Modelo Explicativo E1, RERI/AP, Ranking e Tabela de Perfis (T-3.1 a T-3.6):** Ver `reports/e1/efeitos_principais.md`, `reports/e1/interacoes_or_bh.md`, `reports/e1/interacao_aditiva_reri_ap.md`, `reports/e1/ranking_comorbidades.md` e `reports/e1/tabela_perfis.md`.
5. **Comparação de Modelos de Triagem M1 e SHAP Global (T-4.3b a T-4.10):** Ver `reports/m1/comparacao_oof.md`, `reports/m1/comparacao_pareada.md` e `reports/shap/importancia_shap.md`.
6. **Avaliação Final no Conjunto de Teste 2024 (T-5.1 a T-5.4):** Ver `reports/teste/metricas.md`, `reports/teste/subgrupos.md`, `reports/teste/erros.md` e `reports/teste/LACRE.json`.

---

## 5. Discussão e Limitações (TRIPOD+AI Itens 18–22)

1. **Duplicatas sem chave unívoca (D-47):** Os microdados públicos não contêm `DT_NASC` nem CPF/CNS; chaves compostas por ano de nascimento, sexo, município e data de sintomas colidem em até 42,4% na epidemia de 2024. Conforme D-47, não se deduplica por chave composta.
2. **Particularidades do Espírito Santo e `TP_SISTEMA` (§3.7):** O ES utiliza o e-SUS VS desde 2020 (`TP_SISTEMA` = `0` ou branco) e codificou `NU_IDADE_N` em anos simples em 2022 (corrigido pelo fallback de `ANO_NASC`, D-50). O desempenho específico no ES é reportado separadamente em `reports/teste/erros.md`.
3. **Leucopenia "não realizado" vs. "ausente":** A ficha de notificação não distingue hemograma normal de exame ainda não colhido no atendimento inicial.
4. **Ausência de campo para doenças respiratórias crônicas:** O item 34 da ficha do SINAN-Dengue contempla 7 comorbidades, sem DPOC ou asma.
5. **Mudança de sorotipo (DENV-3) e *drift* temporal em 2024 (§3.7):** O aumento da prevalência de desfecho grave de 0,16% (2022–2023) para 0,21% (2024) e a reintrodução do DENV-3 representam *dataset shift* real, avaliado sem reajuste pós-teste (D-36).

---

## Apêndices (T-7.2)

- **Apêndice A — Registro de Decisões (D-01 a D-57):** Consolidado em `specs/spec.md` (§3.16), destacando as decisões pós-profiling D-22 a D-25 e D-45 a D-57.
- **Apêndice B — Fluxograma de Exclusão e Profiling:** Consolidado em `reports/fluxograma.md` e `profiling/RELATORIO_PROFILING.md`.
- **Apêndice C — Cronologia e Reprodutibilidade (MLflow):** Runs exportados em `mlruns/` e relatórios verificáveis em `reports/verificacao/`.
- **Apêndice D — Revisão Clínica (FR-21):** Espaço reservado para observações de profissional de saúde (eventuais sugestões que alterassem preditores são registradas como limitação para trabalhos futuros, sem retreino pós-teste — R2).
