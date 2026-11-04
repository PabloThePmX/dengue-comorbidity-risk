# Tarefas — Fase 3 — US1: perfil de risco (Marco 3)

> **Leia antes:** [00-como-usar.md](00-como-usar.md) — regras (§0, R1–R10), referência rápida (§1),
> dependências (§7b) e os registros §9 e §10, que ficam **lá**, não neste arquivo. Os §0, §1, §7b,
> §9 e §10 citados abaixo são daquele arquivo.

---

## 3. Fase 3 — US1: perfil de risco (Marco 3, P1) 🎯 MVP

Spec: FR-05, FR-06, FR-19, §3.11, §3.13, D-40, D-41. Ajustado em 2022–23 (todos os dados de
desenvolvimento, sem dobras — é inferência, não predição).

### [ ] T-3.1 [US1] — Ajustar o E1 (`explain.py`)

- Arquivo: `src/dengue_sinan/explain.py`. Use `statsmodels` (`smf.logit` ou `sm.GLM` binomial)
  para ter matriz de covariância (R9: sem penalização).
- Fórmula: `y ~ cr(idade_anos, df=5) + sexo + gestante + <7 comorbidades Sim/Não> +
  <interações 2 a 2 entre comorbidades> + HIPERTENSA:cr(idade_anos, df=3) +
  DIABETES:cr(idade_anos, df=3)`. Graus de liberdade dos splines `[ASSUMPTION]`.
- **Interações:** inclua só os pares com **≥ 10 eventos** (T-2.7). Os demais pares não entram
  no modelo e são listados como "eventos insuficientes".
- Comorbidade "Ausente": é ~0% na população. Trate como categoria de referência à parte ou
  🛑 PERGUNTE se a contagem for > 0 e o modelo não convergir.
- Se o ajuste não convergir: registre em §10 e tente só correções técnicas (regra 4b: mais iterações,
  outro método de otimização). Se ainda não convergir, **🛑 PARE E PERGUNTE**. Nunca remova termos
  por conta própria.
- **Pronto quando:** modelo converge; resumo salvo em `reports/e1/coeficientes.md`; tempo de ajuste anotado no §9.

### [ ] T-3.2 [US1] — OR, IC e correção múltipla

- Para cada comorbidade: OR do efeito principal com IC 95%.
- Para cada par incluído: OR da interação com IC 95% e p-valor; **Benjamini-Hochberg** (FDR 5%)
  nos pares. Reportar p ajustado.
- No relatório, interpretar **tamanho do efeito e IC**, não p-valor (spec §3.11).
- **Pronto quando:** `reports/e1/or_interacoes.md` existe com OR, IC, p e p ajustado.

### [ ] T-3.3 [US1] — Interação aditiva: RERI e AP (FR-05, D-40)

- Para cada par incluído (A, B): calcule, a partir do E1 (mesma idade/sexo de referência),
  `OR_A`, `OR_B`, `OR_AB` contra "nenhuma das duas";
  `RERI = OR_AB − OR_A − OR_B + 1`; `AP = RERI / OR_AB`.
- IC 95% pelo **método delta** usando a covariância dos coeficientes (ou bootstrap de 1.000).
- Teste unitário com coeficientes inventados: RERI e AP batem com a conta à mão.
- **Pronto quando:** `reports/e1/reri_ap.md` com RERI, AP e IC de cada par.

### [ ] T-3.4 [US1] — Ranking de comorbidades (FR-19)

- Ordenar as 7 comorbidades pelo OR do efeito principal.
- Duas comorbidades com IC sobrepostos ficam marcadas **"sem ordem definida"** entre si.
- Fonte: só E1 (R10).
- **Pronto quando:** `reports/e1/ranking.md` existe e teste unitário da lógica de sobreposição passa.

### [ ] T-3.5 [US1] — Tabela de perfis (FR-06)

- Perfis (D-52) — **todas as comorbidades**, gerados automaticamente (não escreva a lista à mão):
  1. sem comorbidades (referência);
  2. cada uma das **7 comorbidades sozinha**;
  3. cada **par** de comorbidades que entrou no E1 (os pares com ≥ 10 eventos, T-2.7); os pares
     que não entraram aparecem na tabela como "dados insuficientes";
  4. **3 ou mais:** **todas** as combinações de 3+ comorbidades que tenham ≥ 10 casos em 2022–23
     (sem limite fixo; a contagem vem da T-2.7), cada uma nomeada pelas doenças que contém. Cada
     linha leva a nota: "risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem
     termo próprio para o trio".
- Para cada perfil × faixa etária (idade no meio da faixa) × sexo (F e M separados `[ASSUMPTION]`):
  risco previsto pelo E1 com IC 95% (método delta na escala logit e depois transformar) e razão
  contra "sem comorbidades" na mesma faixa e sexo.
- Suprimir perfis cuja célula observada tenha < 10 casos (R7).
- A tabela completa vai para `reports/e1/perfis_completo.md`. O relatório mostra uma versão curta
  (faixa 60–79, os perfis mais frequentes) e aponta para a completa. A demo calcula **qualquer**
  combinação pelo E1, mesmo as que não estão na tabela.
- **Pronto quando:** `reports/e1/perfis_completo.md` no formato do spec §3.15, com os 4 grupos de
  perfis acima; teste unitário confirma que a lista de perfis é gerada a partir dos pares do E1.

### [ ] T-3.6 [US1] — Serializar o E1 (FR-12)

- Arquivo: `src/dengue_sinan/artifacts.py`. `save_bundle(obj, caminho, metadados)` e
  `load_bundle(caminho)`.
- Metadados obrigatórios: versão do código (commit), hashes dos dados, config, data de treino,
  métricas de validação, lista de features, versão das bibliotecas.
- O artefato do E1 guarda os coeficientes e a covariância (para IC na demo), **sem dados**.
- **Pronto quando:** `load_bundle` recupera o modelo e reproduz o risco de um perfil com diferença < 1e-9.
