# Tarefas — Fase 5 — Avaliação final no teste (Marco 5)

> **Leia antes:** [00-como-usar.md](00-como-usar.md) — regras (§0, R1–R10), referência rápida (§1),
> dependências (§7b) e os registros §9 e §10, que ficam **lá**, não neste arquivo. Os §0, §1, §7b,
> §9 e §10 citados abaixo são daquele arquivo.

---

## 5. Fase 5 — Avaliação final de US1 e US2 no teste (Marco 5, uma vez só)

Spec: FR-09, §3.12, D-36, D-39. **Pré-requisitos:** T-3.6 e T-4.10 prontos e commitados.

### [ ] T-5.1 — Avaliação única (`evaluate.py`)

- `evaluate_test_once(cfg)`:
  1. se `reports/teste/LACRE.json` existir → `raise RuntimeError("teste já avaliado (R2)")`;
  2. carregar 2024 com `load_population(cfg, [2024])` (único lugar autorizado);
  3. carregar os artefatos congelados de E1, M1, B1 (e regra B2);
  4. predizer; calcular todas as métricas da §1.4 com IC bootstrap (1.000; 2.000 nas bandas de
     calibração) e a **diferença de PR-AUC** M1 − B1 com IC;
  5. gravar `LACRE.json` com data, commit, hashes dos artefatos e dos dados.
- Teste: uma segunda chamada levanta erro.
- **Pronto quando:** `reports/teste/metricas.md` gerado e `LACRE.json` gravado.

### [ ] T-5.2 — Curva de decisão, calibração e subgrupos

- Curva de decisão (0,1%–5%) para M1, B1 e B2, com "tratar todos" e "ninguém"; marcar o limiar F2.
- Curva de calibração com bandas (2.000 bootstrap) para M1 e E1.
- Subgrupos: faixa etária; sexo; gestantes; região; **raça/cor** (com "ignorado"). PR-AUC, recall no
  limiar e calibração, com IC. Subgrupos com < 100 eventos (sexo "I") ou no limite (gestantes,
  Norte) recebem aviso de IC largo.
- **Pronto quando:** `reports/teste/` tem as figuras e tabelas.

### [ ] T-5.3 — Análise de erros

- Os 100 falsos negativos com **maior** risco previsto entre os não detectados `[ASSUMPTION]`:
  descrever por perfil (faixa, comorbidades, região, atraso) **em agregados** (R7).
- Células de comorbidade com pior calibração.
- Olhar o Espírito Santo à parte (sistema de origem diferente, spec §3.7).
- **Pronto quando:** `reports/teste/erros.md` sem nenhuma linha individual.

### [ ] T-5.4 — Critérios de sucesso SC-01 a SC-04 (spec, `[ASSUMPTION]`)

Reportar cada um como passou/falhou, **sem mexer no modelo**:
- M1 supera B0 em PR-AUC (IC da diferença não inclui 0);
- comparação com B1 (superar é desejável, não obrigatório);
- recall de M1 ≥ recall de B2, com precisão maior, no limiar;
- calibration slope no teste entre 0,8 e 1,2.

Se o teste sair pior que a validação: **reportar como resultado (drift)**. É proibido voltar e
trocar modelo, peso, calibrador ou limiar (D-36).
