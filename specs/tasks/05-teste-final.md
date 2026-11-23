# Marco 5 — Avaliação final de E1 e M1 no teste (uma vez só)

> **Leia antes:** [00-como-usar.md](00-como-usar.md) (como executar, Verificação no Colab, Erros
> inesperados). Os registros de execução e de problemas ficam **lá**.

Spec: FR-09, D-36, D-39; [spec › Plano de avaliação](../spec.md#plano-de-avaliação). Critério de
saída: [spec › Marcos](../spec.md#marcos). **Pré-requisitos:** T-3.6 e T-4.10 prontas e commitadas,
e o "ok" do Programador para usar o teste (D-71).

Roda no Colab, onde estão 2024 e os artefatos (D-66). O Colab grava só agregados em texto (métricas,
pontos das curvas, tabelas por subgrupo); o agente os traz pelo MCP com SHA-256 conferido e desenha
as figuras de `reports/teste/` localmente.

### [x] T-5.0 — Congelar B0 e B1 antes do teste (`baselines.py`, D-93)

- `congelar_baselines(cfg, destino)`: com a população de **2022–23** (`load_population` com `anos_dev`; R1), ajusta o B1 (`ajustar_b1`, todo 2022–23, sem penalização, R3, R5) e calcula a prevalência do B0; salva com `save_bundle` em `models/b1_final/` e `models/b0_final/` (tipo registrado como o do M1; metadata FR-12 com versões, hashes dos dados e da config e SHA-256 do payload).
- O limiar de cada um é recalculado das OOF de B0 e B1 (`<dados>/oof/oof_B0.parquet` e `oof_B1.parquet`, T-2.8) com `threshold_for_min_recall` e o `recall_alvo` do `selecao.json` (critério do D-92, predição bruta), e **conferido contra a tabela de limiares de `reports/m1/comparacao_oof.md`** (a T-4.9 os calculou, mas só gravou os do M1 no `selecao.json`). É reprodução do mesmo cálculo, não reajuste. B0 e B1 não são calibrados.
- Teste: o artefato recarrega e reproduz as predições do ajuste; dado de 2024 é recusado (`guard`); mutação.
- Roda no Colab numa sessão **só com 2022–23** (D-66), antes do teste. O SHA-256 dos artefatos vai para o Registro e para o `LACRE.json` da T-5.1.
- **Pronto quando:** testes passam e o relatório de verificação (D-64) tem `"passou": true` no Colab.

### [x] T-5.1 — Avaliação única (`evaluate.py`)

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

### [x] T-5.2 — Curva de decisão, calibração e subgrupos

- Curva de decisão (0,1%–5%) para M1, B1 e B2, com "tratar todos" e "ninguém"; marcar o limiar principal (recall ≥ B2, D-92, congelado com o modelo) e o limiar F2 (secundário). O limiar F2 não está no modelo congelado: leia `limiar_f2` do `selecao.json` da T-4.9 (Colab, `<Drive>/data/m1/selecao.json`).
- Curva de calibração com bandas (2.000 bootstrap) para M1 e E1.
- Subgrupos: faixa etária; sexo; gestantes; região; **raça/cor** (com "ignorado"). PR-AUC, recall no
  limiar e calibração, com IC. Os subgrupos com poucos eventos
  ([spec › Tamanho do teste](../spec.md#tamanho-do-teste-e-das-dobras): sexo "I", sexo em branco,
  gestantes, Norte) recebem aviso de IC largo.
- **Pronto quando:** `reports/teste/` tem as figuras e tabelas.

### [x] T-5.3 — Análise de erros

- Os 100 falsos negativos com **maior** risco previsto entre os não detectados `[ASSUMPTION]`:
  descrever por perfil (faixa, comorbidades, região, atraso) **em agregados** (R7).
- Células de comorbidade com pior calibração.
- Olhar o Espírito Santo à parte (sistema de origem diferente,
  [data-model › Espírito Santo](../data-model.md#espírito-santo)).
- **Pronto quando:** `reports/teste/erros.md` sem nenhuma linha individual.

### [x] T-5.4 — Critérios de sucesso SC-01 a SC-04

Reportar cada um ([spec › Critérios de sucesso](../spec.md#critérios-de-sucesso)) como
passou/falhou, **sem mexer no modelo**.

Se o teste sair pior que a validação: **reportar como resultado (drift)**. É proibido voltar e
trocar modelo, peso, calibrador ou limiar (D-36).

- **Pronto quando:** `reports/teste/criterios.md` lista SC-01 a SC-04 com o valor medido, o IC e
  passou/falhou.
