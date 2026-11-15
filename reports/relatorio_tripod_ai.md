# Relatório Técnico (TRIPOD+AI) — Risco de Desfecho Grave em Dengue por Perfil de Comorbidades

> **Status:** Relatório consolidado segundo o checklist TRIPOD+AI (T-7.1, T-7.2) com todas as métricas verificadas das Fases 2, 3, 4 e 5 (`reports/verificacao/*.json` e `reports/teste/LACRE.json`).

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

## 4. Resultados Consolidados (2022–2023 e Teste Cego 2024)

### 4.1 População e Análise Descritiva (`T-2.1`, `T-2.6`, `T-2.7`)
- **Desenvolvimento (2022–2023):** `2.453.208` casos confirmados elegíveis e `3.985` eventos graves/óbitos (`0,162%`). Das 21 combinações 2 a 2 de comorbidades, **15 pares** atingiram `≥ 10` eventos e entraram no modelo E1; **75 combinações de 3 ou mais comorbidades** atingiram `≥ 10` casos e compõem a tabela de perfis ([fluxograma.md](fluxograma.md), [tabela1.md](descritiva/tabela1.md), [riscos_brutos.md](descritiva/riscos_brutos.md), [pares_comorbidades.md](descritiva/pares_comorbidades.md), [combinacoes_3mais.md](descritiva/combinacoes_3mais.md)).
- **Teste Cego (2024):** `5.331.745` casos confirmados elegíveis e `11.338` eventos graves/óbitos (`0,213%`) ([teste/fluxograma_teste.md](teste/fluxograma_teste.md)).

### 4.2 Modelo Explicativo de Perfil E1 (`T-3.1` a `T-3.6`)
Ajustado por regressão logística binomial sem penalização com splines cúbicos de idade (`5 gl` principal, `3 gl` nas interações com hipertensão e diabetes) e os 15 pares de comorbidades elegíveis ([e1/coeficientes.md](e1/coeficientes.md), [e1/or_interacoes.md](e1/or_interacoes.md), [e1/reri_ap.md](e1/reri_ap.md), [e1/perfis_completo.md](e1/perfis_completo.md)).

**Ranking ajustado das 7 comorbidades pelo efeito principal ([e1/ranking.md](e1/ranking.md)):**

| Posição | Comorbidade | OR ajustado | IC 95% | Status de ordem (sobreposição de IC 95%) |
|---|---|---|---|---|
| 1 | `HEMATOLOG` | 9,2542 | 7,2216 – 11,8587 | sem ordem definida com: `RENAL` |
| 2 | `RENAL` | 6,7580 | 5,0381 – 9,0650 | sem ordem definida com: `HEMATOLOG`, `AUTO_IMUNE`, `HEPATOPAT`, `HIPERTENSA` |
| 3 | `AUTO_IMUNE` | 5,0686 | 3,8148 – 6,7346 | sem ordem definida com: `RENAL`, `HEPATOPAT`, `HIPERTENSA` |
| 4 | `HEPATOPAT` | 4,9157 | 3,6014 – 6,7095 | sem ordem definida com: `RENAL`, `AUTO_IMUNE`, `HIPERTENSA` |
| 5 | `HIPERTENSA` | 3,4545 | 2,2941 – 5,2018 | sem ordem definida com: `RENAL`, `AUTO_IMUNE`, `HEPATOPAT` |
| 6 | `DIABETES` | 1,2175 | 0,7178 – 2,0651 | sem ordem definida com: `ACIDO_PEPT` (interação positiva com idade avançada: `DIABETES_Sim:idade_sp3_1` $\beta = +0,8770$) |
| 7 | `ACIDO_PEPT` | 0,6998 | 0,4202 – 1,1655 | sem ordem definida com: `DIABETES` |

### 4.3 Comparação OOF dos Modelos de Triagem M1 em 2022–2023 (`T-4.3b` a `T-4.10`)
Avaliação nas 5 dobras geográficas leave-one-region-out ([m1/comparacao_oof.md](m1/comparacao_oof.md), [m1/comparacao_pareada.md](m1/comparacao_pareada.md), [shap/importancia_shap.md](shap/importancia_shap.md)):

| Modelo | PR-AUC média (5 dobras) | PR-AUC OOF | ROC-AUC | Brier | Calibrador | Limiar F2 | Recall | Precisão | F2 | Tentativas (OK/Podadas) |
|---|---|---|---|---|---|---|---|---|---|---|
| `B0 (prevalência)` | 0,0018 | 0,0015 | 0,4629 | 0,0016 | - | - | - | - | - | 0/0 |
| `B2 (protocolo MS)` | - | - | - | - | regra | - | 0,6843 | 0,0042 | 0,0206 | 0/0 |
| `B1 (logística perfil)` | 0,0126 | 0,0128 | 0,7241 | 0,0016 | isotonic | 0,0251 | 0,1338 | 0,0351 | 0,0856 | 1/0 |
| **`elastic_net` (Vencedor M1)** | **0,0266** | **0,0260** | **0,8316** | **0,0016** | **isotonic** | **0,0230** | **0,2043** | **0,0400** | **0,1121** | **2/0** |
| `xgboost` | 0,0283 | 0,0289 | 0,8501 | 0,0016 | isotonic | 0,0259 | 0,1920 | 0,0478 | 0,1197 | 21/7 |
| `catboost` | 0,0271 | 0,0273 | 0,8451 | 0,0016 | isotonic | 0,0230 | 0,2321 | 0,0382 | 0,1151 | 21/4 |
| `mlp` | 0,0284 | 0,0280 | 0,8494 | 0,0016 | isotonic | 0,0263 | 0,1957 | 0,0458 | 0,1183 | 2/0 |
| `random_forest` | 0,0262 | 0,0259 | 0,8440 | 0,0016 | isotonic | 0,0239 | 0,2198 | 0,0393 | 0,1146 | 5/0 |
| `tabfm` | 0,0121 | 0,0091 | 0,7710 | 0,0016 | isotonic | 0,0135 | 0,2110 | 0,0171 | 0,0646 | 1/0 |

- **Regra de seleção (§1.4):** empate técnico entre `mlp`, `xgboost`, `catboost`, `elastic_net` e `random_forest` (diferença de PR-AUC média `< 0,005` e ICs 95% sobrepostos); desempate pré-registrado por estabilidade na pior dobra, calibração e menor complexidade selecionou **`elastic_net`**.

### 4.4 Avaliação Única no Conjunto de Teste Congelado de 2024 (`T-5.1` a `T-5.4`)
Executada uma única vez sobre os `5.331.745` casos e `11.338` eventos de 2024 ([teste/metricas.md](teste/metricas.md), [teste/subgrupos.md](teste/subgrupos.md), [teste/erros.md](teste/erros.md), [teste/LACRE.json](teste/LACRE.json)):

| Modelo | PR-AUC (IC 95%) | ROC-AUC | Brier | Calibration Slope | Calibration Intercept | Limiar | Recall | Precisão | F2 |
|---|---|---|---|---|---|---|---|---|---|
| **`M1 (Triagem — elastic_net)`** | **0,0295 (0,0277–0,0316)** | **0,8132** | **0,0021** | **0,9378** | **0,2506** | **0,0230** | **0,2056** | **0,0468** | **0,1225** |
| `E1 (Perfil explicativo)` | 0,0221 (0,0207–0,0238) | 0,7282 | 0,0021 | 0,9576 | 0,1702 | - | - | - | - |
| `B1 (Baseline perfil)` | 0,0191 (0,0179–0,0204) | 0,7186 | 0,0021 | 0,9590 | 0,1717 | 0,0191 | 0,1522 | 0,0380 | 0,0950 |
| `B0 (Prevalência)` | 0,0021 (0,0021–0,0021) | 0,5000 | 0,0021 | 0,0000 | 0,0000 | - | - | - | - |
| `B2 (Protocolo MS)` | - | - | - | - | - | regra | 0,6601 | 0,0053 | 0,0256 |

- **Critérios de Sucesso no Teste 2024 (`T-5.4`):**
  - **SC-01 (`passou`):** `M1` supera `B0` em PR-AUC com diferença pareada de **`+0,0263` (IC 95%: `[0,0239, 0,0317]`)** (≈ 14× a prevalência de base).
  - **SC-02 (`passou`):** `M1` supera `B1` (apenas perfil demográfico/comorbidades) com ganho de PR-AUC de **`+0,0119` (IC 95%: `[0,0095, 0,0158]`)** e ganho de ROC-AUC de `0,7186` para `0,8132`, demonstrando o valor preditivo incremental dos sintomas iniciais e dos sinais clínicos (`LACO`, `PETEQUIA_N`, `LEUCOPENIA`).
  - **SC-03 (`falhou` — resultado honesto documentado, P10):** no limiar que maximiza $F_2$ (`0,0230`), `M1` multiplica a precisão por **8,8×** frente à regra do Grupo B (`0,0468` vs. `0,0053`) e multiplica o $F_2$ por **4,8×** (`0,1225` vs. `0,0256`), porém com menor sensibilidade bruta (`0,2056` vs. `0,6601`, já que a regra `B2` rotula ~26% de todos os pacientes como alto risco). Conforme a curva de decisão ([teste/curva_decisao.md](teste/curva_decisao.md)), `M1` apresenta maior benefício líquido (*Net Benefit*) que `B1`, `B2` e "tratar todos" em toda a faixa clínica de limiares acima de `0,5%`.
  - **SC-04 (`passou`):** o *calibration slope* de `M1` em 2024 foi de **`0,9378`** (dentro da faixa alvo `[0,80, 1,20]`), confirmando excelente preservação da calibração mesmo sob o *shift* epidêmico de 2024 (`intercept = +0,2506` reflete o aumento da prevalência basal de `0,16%` para `0,21%`).

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
