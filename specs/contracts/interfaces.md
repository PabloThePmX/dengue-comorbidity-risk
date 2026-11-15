# Contratos — interfaces de entrada e saída

> Schemas e formatos que o código e a demo precisam cumprir. Só contrato, sem implementação.
> Requisitos em [spec.md](../spec.md); arquitetura em [plan.md](../plan.md). O que o professor
> exige e onde cada entregável está: [spec › Mapeamento acadêmico](../spec.md#mapeamento-acadêmico).

---

## Entrada de casos

Vale para a CLI (extra, FR-10 MAY) e para a aba Triagem da demo.

```
predict --model <caminho_artefato> --input casos.csv --output riscos.csv
```

Entrada (`casos.csv`), uma linha por caso. A coluna "Vira a feature" diz como cada entrada é
traduzida para o [data-model › Dicionário de features](../data-model.md#dicionário-de-features)
(D-61).

| Coluna | Tipo | Domínio | Vira a feature |
|---|---|---|---|
| `id_caso` | string | livre | — (devolvido na saída) |
| `idade_anos` | int | 0–120 | `idade_anos`, igual |
| `sexo` | string | `M`, `F` | `sexo`: `M` → M, `F` → F |
| `gestante` | string | `sim`, `nao`, `ignorado` | `gestante`: `sim` → 1; `nao` e `ignorado` → 0 (gestante = `CS_GESTANT` 1–4) |
| `diabetes`, `hematologica`, `hepatopatia`, `renal_cronica`, `hipertensao`, `acido_peptica`, `autoimune` | string | `sim`, `nao`, `ignorado` | `DIABETES`, `HEMATOLOG`, `HEPATOPAT`, `RENAL`, `HIPERTENSA`, `ACIDO_PEPT`, `AUTO_IMUNE`: `sim` → Sim, `nao` → Não, `ignorado` → Ausente |
| `febre`, `mialgia`, `cefaleia`, `exantema`, `vomito`, `nausea`, `dor_costas`, `conjuntvit`, `artrite`, `artralgia`, `dor_retro`, `petequia_n`, `leucopenia`, `laco` | string | `sim`, `nao`, `ignorado` | o campo de mesmo nome em maiúsculas: `sim` → Sim, `nao` → Não, `ignorado` → Ausente |
| `dias_ate_notificacao` | int | 0–60 | `dias_ate_notificacao`, igual |

- `n_comorbidades` não é entrada: é calculada como o nº de comorbidades = `sim`.
- Entrada fora do domínio é recusada com mensagem `[ASSUMPTION]`
  ([spec › Casos-limite](../spec.md#casos-limite)).

Saída (`riscos.csv`):

| Coluna | Tipo | Exemplo |
|---|---|---|
| `id_caso` | string | `abc-001` |
| `risco` | float | `0.042` (probabilidade calibrada) |
| `alto_risco` | bool | `true` (risco ≥ limiar) |
| `modelo_versao` | string | `m1-xgboost-2026-11-10-<hash>` |

## Tabela de perfis

FR-06. Formato:

| Perfil | Faixa etária | Risco estimado | IC 95% | Razão vs. "saudável" mesma faixa |
|---|---|---|---|---|
| Sem comorbidades | 60–79 | … | … | 1,0 |
| Só hipertensão | 60–79 | … | … | … |
| Diabetes + renal crônica | 60–79 | … | … | … |
| 3+ comorbidades | 60–79 | … | … | … |

**Fonte da tabela de perfis e da aba Perfil (D-20):** o modelo explicativo **E1** (só perfil: idade, sexo, gestação, comorbidades). A pergunta original ("se um hipertenso pegar dengue, qual o risco?") é feita antes dos sintomas, e E1 responde exatamente isso. M1 é o modelo preditivo de triagem, exposto na aba Triagem (D-27).
- `[ASSUMPTION]` E1 é ajustado em 2022–23 e tem calibração checada em 2024, como os demais modelos. ICs dos perfis vêm da matriz de covariância da logística (método delta).

## Demo

Streamlit, FR-11, D-27.

- **Aba Perfil (E1)**
  - Entrada: idade, sexo, gestação, 7 comorbidades.
  - Saída: risco de E1 com IC 95%, comparação com o perfil "sem comorbidades" da mesma faixa etária, e os OR das comorbidades marcadas.
- **Aba Triagem (M1)**
  - Entrada: as colunas de [Entrada de casos](#entrada-de-casos) (perfil + sintomas iniciais + dias até a notificação).
  - Saída: risco calibrado de M1 e "alto risco" sim/não no limiar escolhido ([spec › Plano de avaliação](../spec.md#plano-de-avaliação)).
  - Explicação (D-35): os 5 fatores que mais aumentaram ou reduziram o risco do caso (SHAP local), com a frase "contribuição no modelo, não causa".
    - Modelos de árvore: TreeSHAP exato. Elastic net: contribuição linear (coeficiente × valor). MLP: `shap.GradientExplainer` com amostra de fundo (D-51). Todos respeitando NFR-06. O TabFM nunca é o modelo da demo (D-69); se o melhor M1 não couber, vale o D-70.
  - `[ASSUMPTION]` SHOULD mostrar também se o caso cairia no grupo B pela regra do protocolo (B2, [spec › Baselines](../spec.md#baselines)), para o usuário comparar modelo e regra.
  - Sem IC por predição: a maioria dos candidatos de M1 não tem IC analítico por caso, e a escolha do modelo só sai no Marco 4. A incerteza do modelo fica no relatório (IC bootstrap das métricas).
- As duas abas explicam, em uma frase, a diferença entre elas: Perfil responde "qual o risco de quem tem estas condições"; Triagem responde "qual o risco deste paciente, com estes sintomas, agora".
- Aviso fixo nas duas abas: "Projeto acadêmico. Não é ferramenta clínica nem substitui avaliação médica." Na aba Triagem, o aviso fica em destaque, porque ela se parece mais com uma ferramenta clínica.
- Nenhum microdado embarcado; nenhuma entrada armazenada (NFR-03).

## Relatório de verificação

D-56. `reports/verificacao/<tarefa>.json`, gerado por `verify.write_report` no PC local (Marcos 2 e 3) ou no Colab (Marcos 4 e 5), conforme o D-66. Só agregados (R7).

```json
{
  "tarefa": "T-2.1",
  "gerado_em": "2026-11-10T14:03:00Z",
  "commit": "<sha do git onde o código rodou>",
  "ambiente": {"python": "3.13.x", "ram_gib": 12.7, "gpu": "T4"},
  "hash_dados": {"2022": "<sha256 do .dbc>", "2023": "<sha256 do .dbc>"},
  "checks": [
    {"nome": "casos_dev", "esperado": 2453208, "obtido": 2453208, "tolerancia": 0, "passou": true},
    {"nome": "eventos_dev", "esperado": 3985, "obtido": 3985, "tolerancia": 0, "passou": true}
  ],
  "passou": true
}
```

- `passou` (nível de cima) = todos os `checks` passaram.
- `hash_dados` usa o SHA-256 do `.dbc` original, e não do Parquet: o `.dbc` é o mesmo no PC e no
  Colab, enquanto o Parquet pode mudar de bytes com outra versão do pyarrow (D-72).
- `esperado` vem sempre de `config/esperado.yaml`; nunca é digitado no notebook.
- `obtido` só aceita número, texto ou booleano.
- Pelo MCP do Colab (D-64), `verify.show_report` imprime o arquivo e o SHA-256 dos seus bytes; a
  cópia salva em `reports/verificacao/` precisa ter o mesmo SHA-256. O formato do JSON não muda.

## Relatório da sessão dos modelos

D-57. `reports/verificacao/sessao-m1.json`, gravado por `verify.update_session_report` ao fim de
cada etapa de `run_all_models`.

```json
{
  "sessao": "sessao-m1",
  "gerado_em": "2026-11-12T18:40:00Z",
  "commit": "<sha do git no Colab>",
  "ambiente": {"python": "3.13.x", "gpu": "L4", "vcpus": 8, "ram_gib": 53.0},
  "hash_dados": {"2022": "<sha256 do .dbc>", "2023": "<sha256 do .dbc>"},
  "hash_dobras": "<sha256 do conteúdo das dobras, igual ao da T-2.3>",
  "blocos": [
    {"bloco": "checagem_inicial", "tarefa": "T-4.3b", "checks": [], "passou": true},
    {"bloco": "elastic_net", "tarefa": "T-4.6b", "checks": [], "passou": true},
    {"bloco": "xgboost", "tarefa": "T-4.5", "checks": [], "passou": true},
    {"bloco": "selecao", "tarefa": "T-4.9", "checks": [], "passou": true},
    {"bloco": "retreino", "tarefa": "T-4.10", "checks": [], "passou": true}
  ],
  "sessao_completa": true,
  "passou": true
}
```

- Cada `checks` tem o mesmo formato do [Relatório de verificação](#relatório-de-verificação).
- Blocos na ordem em que rodaram: `checagem_inicial`, os modelos na ordem do config, `selecao`,
  `shap`, `retreino`.
- `passou` (nível de cima) = `sessao_completa` e todos os blocos passaram.
