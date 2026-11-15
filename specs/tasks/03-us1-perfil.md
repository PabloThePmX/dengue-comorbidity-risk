# Marco 3 — Modelo explicativo E1: perfil de risco (US1, P1) 🎯 MVP

> **Leia antes:** [00-como-usar.md](00-como-usar.md) (como executar, Verificação no Colab, Erros
> inesperados). Os registros de execução e de problemas ficam **lá**.

Spec: FR-05, FR-06, FR-19, D-40, D-41; [plan › Modelo explicativo (E1)](../plan.md#modelo-explicativo-e1);
[spec › Interpretabilidade](../spec.md#interpretabilidade-e-equidade). Ajustado em 2022–23 (todos
os dados de desenvolvimento, sem dobras — é inferência, não predição).

Critério de saída ([spec › Marcos](../spec.md#marcos)): OR com IC 95% e Benjamini-Hochberg;
interações só com ≥ 10 eventos; ranking com empates marcados; tabela de perfis com células < 10
suprimidas.

### [ ] T-3.1 [US1] — Ajustar o E1 (`explain.py`)

- Arquivo: `src/dengue_sinan/explain.py`. Use `statsmodels` (`smf.logit` ou `sm.GLM` binomial)
  para ter matriz de covariância (R9: sem penalização).
- Fórmula: `y ~ cr(idade_anos, df=5) + sexo + gestante + <7 comorbidades Sim/Não> +
  <interações 2 a 2 entre comorbidades> + HIPERTENSA:cr(idade_anos, df=3) +
  DIABETES:cr(idade_anos, df=3)`. Graus de liberdade dos splines `[ASSUMPTION]`.
- **Interações:** inclua só os pares com **≥ 10 eventos** (contagem da T-2.6). Os demais pares não
  entram no modelo e são listados como "eventos insuficientes".
- Comorbidade "Ausente": é ~0% na população. Trate como categoria de referência à parte ou
  🛑 PERGUNTE se a contagem for > 0 e o modelo não convergir.
- Se o ajuste não convergir: siga [Erros inesperados](00-como-usar.md#erros-inesperados) (só
  correções técnicas: mais iterações, outro método de otimização). Se ainda não convergir,
  **🛑 PARE E PERGUNTE**. Nunca remova termos por conta própria.
- **Pronto quando:** modelo converge; resumo salvo em `reports/e1/coeficientes.md`; tempo de ajuste
  anotado no Registro de execução.

### [ ] T-3.2 [US1] — OR, interações aditivas e ranking (`explain.py`)

FR-05, FR-19, D-40. Inclui as antigas T-3.3 e T-3.4 (D-60).

- **OR e correção múltipla:** para cada comorbidade, OR do efeito principal com IC 95%; para cada
  par incluído, OR da interação com IC 95% e p-valor, com **Benjamini-Hochberg** (FDR 5%) nos
  pares (reportar o p ajustado). No relatório, interpretar **tamanho do efeito e IC**, não p-valor.
- **Interação aditiva (RERI e AP):** para cada par incluído (A, B), calcular a partir do E1 (mesma
  idade/sexo de referência) `OR_A`, `OR_B`, `OR_AB` contra "nenhuma das duas";
  `RERI = OR_AB − OR_A − OR_B + 1`; `AP = RERI / OR_AB`. IC 95% pelo **método delta** usando a
  covariância dos coeficientes (ou bootstrap de 1.000).
- **Ranking (FR-19):** ordenar as 7 comorbidades pelo OR do efeito principal; duas comorbidades com
  IC sobrepostos ficam marcadas **"sem ordem definida"** entre si. Fonte: só E1 (R10).
- Testes unitários: RERI e AP com coeficientes inventados batem com a conta à mão; lógica de
  sobreposição do ranking.
- **Pronto quando:** `reports/e1/or_interacoes.md` (OR, IC, p e p ajustado),
  `reports/e1/reri_ap.md` (RERI, AP e IC de cada par) e `reports/e1/ranking.md` existem e os testes
  passam.

### ~~[ ] T-3.3 [US1] — Interação aditiva: RERI e AP~~

Fundida na T-3.2 (D-60).

### ~~[ ] T-3.4 [US1] — Ranking de comorbidades~~

Fundida na T-3.2 (D-60).

### [ ] T-3.5 [US1] — Tabela de perfis (FR-06)

- Perfis (D-52) — **todas as comorbidades**, gerados automaticamente (não escreva a lista à mão):
  1. sem comorbidades (referência);
  2. cada uma das **7 comorbidades sozinha**;
  3. cada **par** de comorbidades que entrou no E1 (os pares com ≥ 10 eventos, T-2.6); os pares
     que não entraram aparecem na tabela como "dados insuficientes";
  4. **3 ou mais:** **todas** as combinações de 3+ comorbidades que tenham ≥ 10 casos em 2022–23
     (sem limite fixo; a contagem vem da T-2.6), cada uma nomeada pelas doenças que contém. Cada
     linha leva a nota: "risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem
     termo próprio para o trio".
- Para cada perfil × faixa etária (idade no meio da faixa) × sexo (F e M separados `[ASSUMPTION]`):
  risco previsto pelo E1 com IC 95% (método delta na escala logit e depois transformar) e razão
  contra "sem comorbidades" na mesma faixa e sexo.
- Suprimir perfis cuja célula observada tenha < 10 casos (R7).
- A tabela completa vai para `reports/e1/perfis_completo.md`. O relatório mostra uma versão curta
  (faixa 60–79, os perfis mais frequentes) e aponta para a completa. A demo calcula **qualquer**
  combinação pelo E1, mesmo as que não estão na tabela.
- **Pronto quando:** `reports/e1/perfis_completo.md` no formato de
  [contracts › Tabela de perfis](../contracts/interfaces.md#tabela-de-perfis), com os 4 grupos de
  perfis acima; teste unitário confirma que a lista de perfis é gerada a partir dos pares do E1.

### [ ] T-3.6 [US1] — Serializar o E1 (FR-12)

- Arquivo: `src/dengue_sinan/artifacts.py`. `save_bundle(obj, caminho, metadados)` e
  `load_bundle(caminho)`.
- Metadados obrigatórios: versão do código (commit), hashes dos dados, config, data de treino,
  métricas de validação, lista de features, versão das bibliotecas.
- O artefato do E1 guarda os coeficientes e a covariância (para IC na demo), **sem dados**.
- **Pronto quando:** `load_bundle` recupera o modelo e reproduz o risco de um perfil com diferença < 1e-9.
