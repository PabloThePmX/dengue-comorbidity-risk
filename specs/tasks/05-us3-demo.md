# Tarefas — Fase 6 — US3: demo (Marco 6)

> **Leia antes:** [00-como-usar.md](00-como-usar.md) — regras (§0, R1–R10), referência rápida (§1),
> dependências (§7b) e os registros §9 e §10, que ficam **lá**, não neste arquivo. Os §0, §1, §7b,
> §9 e §10 citados abaixo são daquele arquivo.

---

## 6. Fase 6 — US3: demo (Marco 6, P3)

Spec: FR-11, NFR-03, NFR-06, §3.15, D-27, D-35.

### [ ] T-6.1 [US3] — Estrutura do app

- `src/app/streamlit_app.py` com duas abas: **Perfil** (E1) e **Triagem** (M1).
- Carrega os artefatos (`load_bundle`), **nunca** microdados (R7). Não grava entradas (NFR-03).
- Aviso fixo nas duas abas: "Projeto acadêmico. Não é ferramenta clínica nem substitui avaliação
  médica." Na aba Triagem, em destaque.
- Uma frase em cada aba explicando a diferença: Perfil = "qual o risco de quem tem estas
  condições"; Triagem = "qual o risco deste paciente, com estes sintomas, agora".

### [ ] T-6.2 [US3] — Aba Perfil (E1)

- Entradas: idade, sexo, gestação, 7 comorbidades.
- Saídas: risco com IC 95% (método delta), comparação com "sem comorbidades" na mesma faixa, OR das
  comorbidades marcadas.

### [ ] T-6.3 [US3] — Aba Triagem (M1)

- Entradas: schema da CLI (§3.15 do spec): perfil + sintomas + dias até o atendimento.
- Saídas: risco calibrado; "alto risco" sim/não no limiar; **5 fatores** que mais aumentaram ou
  reduziram o risco (TreeSHAP para árvore; coeficiente × valor para elastic net; para MLP,
  `shap.GradientExplainer` com amostra de fundo; para TabFM, SHAP aproximado) com a frase "contribuição no modelo, não causa"; se o caso cairia no grupo B
  (B2) `[ASSUMPTION]`.

### [ ] T-6.4 [US3] — Verificação e publicação

- Teste: o app sobe (`streamlit run`) e as duas abas respondem em < 1 s (NFR-06) para 20 perfis.
- Conferir que nenhum arquivo de dados está no repositório (R7).
- Publicar no Streamlit Community Cloud **só depois do "ok" do Programador** (é publicação pública).
