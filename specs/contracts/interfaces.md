# Contratos — interfaces de entrada e saída

> Contratos do padrão Spec Kit (D-55): schemas e formatos que o código e a demo precisam cumprir.
> Só contrato, sem implementação. Requisitos em [spec.md](../spec.md); arquitetura em [plan.md](../plan.md).
> Idioma: pt-BR (entregável acadêmico).

---

## 3.15 Entregáveis e interfaces

**Entregáveis exigidos pelo professor (D-26):** um modelo, uma demo para testá-lo e um relatório explicando processo, decisões, resultados e passos seguidos.

| Exigido | O que o projeto entrega | IDs |
|---|---|---|
| Modelo | E1 (perfil) e M1 (triagem), serializados com metadados | FR-05, FR-07, FR-12 |
| Demo | App Streamlit público com duas abas | FR-11, D-17, D-27 |
| Relatório | Relatório TRIPOD+AI com apêndices de decisões, fluxograma e passos | FR-20, D-28 |

Apoio (não exigido, mas necessário para o relatório e a reprodutibilidade): pipeline em módulos Python, notebooks de profiling, explicação e avaliação, e MLflow. CLI só como extra (FR-10, MAY).

**Contrato da CLI** (extra, FR-10 MAY; só contrato, sem implementação). O mesmo schema de entrada vale para a aba Triagem da demo.

```
predict --model <caminho_artefato> --input casos.csv --output riscos.csv
```

Entrada (`casos.csv`), uma linha por caso:

| Coluna | Tipo | Domínio |
|---|---|---|
| `id_caso` | string | livre (devolvido na saída) |
| `idade_anos` | int | 0–120 |
| `sexo` | string | `M`, `F` |
| `gestante` | string | `sim`, `nao`, `ignorado` |
| `diabetes`, `hematologica`, `hepatopatia`, `renal_cronica`, `hipertensao`, `acido_peptica`, `autoimune` | string | `sim`, `nao`, `ignorado` |
| sintomas de §3.8 | string | `sim`, `nao`, `ignorado` |
| `dias_ate_atendimento` | int | 0–60 |

Saída (`riscos.csv`):

| Coluna | Tipo | Exemplo |
|---|---|---|
| `id_caso` | string | `abc-001` |
| `risco` | float | `0.042` (probabilidade calibrada) |
| `alto_risco` | bool | `true` (risco ≥ limiar) |
| `modelo_versao` | string | `m1-xgboost-2026-11-10-<hash>` |

**Tabela de perfis** (FR-06) — formato:

| Perfil | Faixa etária | Risco estimado | IC 95% | Razão vs. "saudável" mesma faixa |
|---|---|---|---|---|
| Sem comorbidades | 60–79 | … | … | 1,0 |
| Só hipertensão | 60–79 | … | … | … |
| Diabetes + renal crônica | 60–79 | … | … | … |
| 3+ comorbidades | 60–79 | … | … | … |

**Fonte da tabela de perfis e da aba Perfil (D-20):** o modelo explicativo **E1** (só perfil: idade, sexo, gestação, comorbidades). A pergunta original ("se um hipertenso pegar dengue, qual o risco?") é feita antes dos sintomas, e E1 responde exatamente isso. M1 é o modelo preditivo de triagem, exposto na aba Triagem (D-27).
- `[ASSUMPTION]` E1 é ajustado em 2022–23 e tem calibração checada em 2024, como os demais modelos. ICs dos perfis vêm da matriz de covariância da logística (método delta).

**Demo Streamlit (FR-11, D-27)**
- **Aba Perfil (E1)**
  - Entrada: idade, sexo, gestação, 7 comorbidades.
  - Saída: risco de E1 com IC 95%, comparação com o perfil "sem comorbidades" da mesma faixa etária, e os OR das comorbidades marcadas.
- **Aba Triagem (M1)**
  - Entrada: os campos do schema de entrada da CLI (perfil + sintomas iniciais + dias até o atendimento).
  - Saída: risco calibrado de M1 e "alto risco" sim/não no limiar escolhido (§3.12).
  - Explicação (D-35): os 5 fatores que mais aumentaram ou reduziram o risco do caso (SHAP local), com a frase "contribuição no modelo, não causa".
    - Modelos de árvore: TreeSHAP exato. Elastic net: contribuição linear (coeficiente × valor). MLP ou TabFM: SHAP aproximado com amostra de fundo `[ASSUMPTION]`, respeitando NFR-06.
  - `[ASSUMPTION]` SHOULD mostrar também se o caso cairia no grupo B pela regra do protocolo (B2, §3.10), para o usuário comparar modelo e regra.
  - Sem IC por predição: M1 é modelo de árvore, sem IC analítico. A incerteza do modelo fica no relatório (IC bootstrap das métricas).
- As duas abas explicam, em uma frase, a diferença entre elas: Perfil responde "qual o risco de quem tem estas condições"; Triagem responde "qual o risco deste paciente, com estes sintomas, agora".
- Aviso fixo nas duas abas: "Projeto acadêmico. Não é ferramenta clínica nem substitui avaliação médica." Na aba Triagem, o aviso fica em destaque, porque ela se parece mais com uma ferramenta clínica.
- Nenhum microdado embarcado; nenhuma entrada armazenada (NFR-03).

**Relatório de verificação** (D-56) — `reports/verificacao/<tarefa>.json`, gerado por
`verify.write_report` no Colab. Só agregados (R7).

```json
{
  "tarefa": "T-2.1",
  "gerado_em": "2026-11-10T14:03:00Z",
  "commit": "<sha do git no Colab>",
  "ambiente": {"python": "3.13.x", "ram_gib": 12.7, "gpu": "T4"},
  "hash_dados": {"2022": "<sha256 do Parquet>", "2023": "<sha256 do Parquet>"},
  "checks": [
    {"nome": "casos_dev", "esperado": 2453208, "obtido": 2453208, "tolerancia": 0, "passou": true},
    {"nome": "eventos_dev", "esperado": 3985, "obtido": 3985, "tolerancia": 0, "passou": true}
  ],
  "passou": true
}
```

- `passou` (nível de cima) = todos os `checks` passaram.
- `esperado` vem sempre de `config/esperado.yaml`; nunca é digitado no notebook.
- `obtido` só aceita número, texto ou booleano.

**Relatório da sessão dos modelos** (D-57) — `reports/verificacao/sessao-m1.json`, gravado por
`verify.update_session_report` ao fim de cada etapa de `run_all_models`.

```json
{
  "sessao": "sessao-m1",
  "gerado_em": "2026-11-12T18:40:00Z",
  "commit": "<sha do git no Colab>",
  "ambiente": {"python": "3.13.x", "gpu": "L4", "vcpus": 8, "ram_gib": 53.0},
  "hash_dados": {"2022": "<sha256>", "2023": "<sha256>"},
  "hash_dobras": "<sha256 do arquivo de dobras (T-2.3)>",
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

- Cada `checks` tem o mesmo formato do relatório de verificação acima.
- Blocos na ordem em que rodaram: `checagem_inicial`, os modelos na ordem do config, `selecao`,
  `shap`, `retreino`.
- `passou` (nível de cima) = `sessao_completa` e todos os blocos passaram.
