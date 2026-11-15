# Marco 5 — Avaliação final de E1 e M1 no teste (uma vez só)

> **Leia antes:** [00-como-usar.md](00-como-usar.md) (como executar, Verificação no Colab, Erros
> inesperados). Os registros de execução e de problemas ficam **lá**.

Spec: FR-09, D-36, D-39; [spec › Plano de avaliação](../spec.md#plano-de-avaliação). Critério de
saída: [spec › Marcos](../spec.md#marcos). **Pré-requisitos:** T-3.6 e T-4.10 prontas e commitadas.

### [ ] T-5.1 — Avaliação única (`evaluate.py`)

- `evaluate_test_once(cfg)`:
  1. se `reports/teste/LACRE.json` existir → `raise RuntimeError("teste já avaliado (R2)")`;
  2. carregar 2024 com `load_population(cfg, [2024])` (único lugar autorizado);
  3. carregar os artefatos congelados de E1, M1, B1 (e regra B2);
  4. predizer; calcular todas as métricas do [Plano de avaliação](../spec.md#plano-de-avaliação)
     com IC bootstrap (1.000; 2.000 nas bandas de calibração) e a **diferença de PR-AUC** M1 − B1
     com IC;
  5. gravar `LACRE.json` com data, commit, hashes dos artefatos e dos dados.
- Antes de rodar, acrescente ao `config/esperado.yaml` a população e os eventos de 2024
  ([data-model › Tamanho e prevalência](../data-model.md#tamanho-e-prevalência)) e confira o
  carregamento contra eles.
- Teste: uma segunda chamada levanta erro.
- **Pronto quando:** `reports/teste/metricas.md` gerado e `LACRE.json` gravado.

### [ ] T-5.2 — Curva de decisão, calibração e subgrupos

- Curva de decisão (0,1%–5%) para M1, B1 e B2, com "tratar todos" e "ninguém"; marcar o limiar F2.
- Curva de calibração com bandas (2.000 bootstrap) para M1 e E1.
- Subgrupos: faixa etária; sexo; gestantes; região; **raça/cor** (com "ignorado"). PR-AUC, recall no
  limiar e calibração, com IC. Os subgrupos com poucos eventos
  ([spec › Tamanho do teste](../spec.md#tamanho-do-teste-e-das-dobras): sexo "I", sexo em branco,
  gestantes, Norte) recebem aviso de IC largo.
- **Pronto quando:** `reports/teste/` tem as figuras e tabelas.

### [ ] T-5.3 — Análise de erros

- Os 100 falsos negativos com **maior** risco previsto entre os não detectados `[ASSUMPTION]`:
  descrever por perfil (faixa, comorbidades, região, atraso) **em agregados** (R7).
- Células de comorbidade com pior calibração.
- Olhar o Espírito Santo à parte (sistema de origem diferente,
  [data-model › Espírito Santo](../data-model.md#espírito-santo)).
- **Pronto quando:** `reports/teste/erros.md` sem nenhuma linha individual.

### [ ] T-5.4 — Critérios de sucesso SC-01 a SC-04

Reportar cada um ([spec › Critérios de sucesso](../spec.md#critérios-de-sucesso)) como
passou/falhou, **sem mexer no modelo**.

Se o teste sair pior que a validação: **reportar como resultado (drift)**. É proibido voltar e
trocar modelo, peso, calibrador ou limiar (D-36).

- **Pronto quando:** `reports/teste/criterios.md` lista SC-01 a SC-04 com o valor medido, o IC e
  passou/falhou.
