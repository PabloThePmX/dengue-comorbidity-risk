# Marco 6 — Demo (US3, P3)

> **Leia antes:** [00-como-usar.md](00-como-usar.md) (como executar, Verificação no Colab, Erros
> inesperados). Os registros de execução e de problemas ficam **lá**.

Spec: FR-11, NFR-03, NFR-06, D-27, D-35. Contrato completo da demo:
[contracts › Demo](../contracts/interfaces.md#demo). Critério de saída:
[spec › Marcos](../spec.md#marcos).

### [x] T-6.1 [US3] — App com as abas Perfil e Triagem (`src/app/streamlit_app.py`)

Inclui as antigas T-6.2 e T-6.3 (D-60).

- Duas abas: **Perfil** (E1) e **Triagem** (M1). Carrega os artefatos (`load_bundle`), **nunca**
  microdados (R7). Não grava entradas (NFR-03).
- Aviso fixo nas duas abas: "Projeto acadêmico. Não é ferramenta clínica nem substitui avaliação
  médica." Na aba Triagem, em destaque. Uma frase em cada aba explicando a diferença: Perfil =
  "qual o risco de quem tem estas condições"; Triagem = "qual o risco deste paciente, com estes
  sintomas, agora".
- **Aba Perfil:** entradas idade, sexo, gestação, 7 comorbidades; saídas risco com IC 95% (método
  delta), comparação com "sem comorbidades" na mesma faixa e OR das comorbidades marcadas.
- **Aba Triagem:** entradas de [contracts › Entrada de casos](../contracts/interfaces.md#entrada-de-casos),
  traduzidas para as features pela coluna "Vira a feature" (D-61); saídas risco calibrado, "alto
  risco" sim/não no limiar e os **5 fatores** que mais aumentaram ou reduziram o risco, pelo método
  do contrato para o modelo escolhido, com a frase "contribuição no modelo, não causa"; se o caso
  cairia no grupo B (B2) `[ASSUMPTION]`.
- Testes: a tradução entrada → feature segue a tabela do contrato; entrada fora do domínio é
  recusada.
- **Pronto quando:** o app sobe localmente com artefatos (ou fictícios, se o Marco 5 não acabou) e
  os testes passam.

### ~~[ ] T-6.2 [US3] — Aba Perfil (E1)~~

Fundida na T-6.1 (D-60).

### ~~[ ] T-6.3 [US3] — Aba Triagem (M1)~~

Fundida na T-6.1 (D-60).

### [~] T-6.4 [US3] — Verificação e publicação

- Teste: o app sobe (`streamlit run`) e as duas abas respondem em < 1 s (NFR-06) para 20 perfis.
- Conferir que nenhum arquivo de dados está no repositório (R7).
- Publicar no Streamlit Community Cloud **só depois do "ok" do Programador** (é publicação pública).
- **Pronto quando:** os 20 perfis respondem em < 1 s com os artefatos congelados e o app está
  publicado com o "ok".
