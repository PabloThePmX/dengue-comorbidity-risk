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

| Perfil | Faixa etária | Sexo | Risco estimado | IC 95% | Razão vs. "saudável" mesma faixa e sexo | Aviso |
|---|---|---|---|---|---|---|
| Sem comorbidades | 60–79 | F | … | … | 1,0 | — |
| Só hipertensão | 60–79 | F | … | … | … | — |
| Diabetes + renal crônica | 60–79 | F | … | … | … | — |
| 3 ou 4 comorbidades | 60–79 | F | … | … | … | — |

Sexo F e M em linhas separadas `[ASSUMPTION]`. Célula com menos de 10 casos observados: "—" (R7). Combinações de 5 ou mais comorbidades: "dados insuficientes", sem número (D-78). Perfis que usam pares que dependem do padrão suspeito levam o aviso (D-77).

**Fonte da tabela de perfis e da aba Perfil (D-20):** o modelo explicativo **E1** (só perfil: idade, sexo, gestação, comorbidades). A pergunta original ("se um hipertenso pegar dengue, qual o risco?") é feita antes dos sintomas, e E1 responde exatamente isso. M1 é o modelo preditivo de triagem, exposto na aba Triagem (D-27).
- `[ASSUMPTION]` E1 é ajustado em 2022–23 e tem calibração checada em 2024, como os demais modelos. ICs dos perfis vêm da matriz de covariância da logística (método delta).

## Artefato do modelo

FR-12, D-81. Cada modelo serializado é uma **pasta**, criada por `artifacts.save_bundle(obj, caminho,
metadados)` e lida por `artifacts.load_bundle(caminho)`:

```
models/<modelo>/
  metadata.json     schema_version, tipo_payload, criado_em_utc, versao_codigo.commit,
                    bibliotecas, config, dados (sha256_dbc e sha256_parquet por ano), data_treino,
                    metricas_validacao, features, payload (SHA-256 de cada arquivo)
  payload/          E1: e1.npz (coeficientes, covariância, nós) + e1.json (colunas, pares, features)
                    M1 (T-4.10): joblib do `ModeloFinal` (wrapper + Pipeline, D-85), com hash e versões no metadata
```

- Sem dados e sem contagens por termo ou nível (R7, NFR-03); sem pickle no E1.
- `load_bundle` recusa o artefato se algum SHA-256 do payload não bater, se o `schema_version` for de
  uma versão futura ou se o tipo for desconhecido (`ArtefatoInvalido`).
- O E1 carregado calcula risco, IC e razão de risco só com NumPy (sem `statsmodels`).
- M1 (D-85): quem carrega precisa importar `dengue_sinan.retreino` antes de `load_bundle` (é ali que o tipo `m1` é registrado). `models/m1_final*` e `models/m1_demo*` não vão ao git até o conteúdo do payload ser inspecionado (R7, D-85).

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
- **Modos (D-96):** seletor no topo, **Normal** por padrão e **Pro**. O Pro mostra tudo o que está acima. O Normal usa os mesmos campos e modelos, mas diz o risco como frequência ("cerca de 1 em N"), explica os fatores em palavras e não mostra IC, OR, log-odds, limiar, regra B2 nem o rótulo "alto risco". O aviso fixo e o aviso de subestimativa valem nos dois.
- Nenhum microdado embarcado; nenhuma entrada armazenada (NFR-03).

## Comparação em 2025

D-97, FR-23. Só agregados saem para o git (R7); previsões por caso ficam em `data/comparacao/` (ignorado).

- **Manifesto** (`config/comparacao/manifesto.yaml`, validado por `comparacao_manifesto.carregar_manifesto`):
  `versao`, `ano_comparacao` (igual ao do config), `comparacao` (métricas, orçamentos de alertas, reamostras),
  `modelo_por_branch`, `saidas`, `verificacoes_na_carga`, `modelos` e `fora_do_conjunto`. Cada modelo tem `id`,
  `papel`, `origem` (`branch`, `commit`), `artefato` (`caminho`, `sha256` de 64 hex; `null` para a regra B2),
  `treino_anos` (sem o ano de comparação), `limiar` (`valor` e `regra`, ou `null`) e, se houver, `validacao`.
- **Entrada comum** (`data/comparacao/entrada_<ano>.parquet` + `.json`): uma linha por caso da população
  (D-45); colunas `ANO` (int64), `LINHA` (int64, nº da linha no parquet do ano) e as features do
  [dicionário](../data-model.md#dicionário-de-features). O `.json` traz o ano, o número de linhas e o SHA-256
  do parquet. O `y` **não** vai na entrada; vem do lado da `main`, com a mesma `LINHA`.
- **Previsões** (`data/comparacao/p_<id>_<ano>.parquet`): `ANO`, `LINHA` e `p` (float64, em [0, 1], sem NaN),
  uma linha por linha da entrada, na mesma ordem e sem repetição. Um modelo com linha faltando é recusado.
- **Conformidade** (`.conformidade.json`, por modelo): `sha256` conferido, `variaveis` e se estão no dicionário
  (R4), parâmetros do estimador e a busca por correção de desbalanceamento (R3), anos de treino, versões do
  ambiente de execução e de treino, estatísticas de `p` (mínimo, máximo, média, nº de 0 e de 1, NaN). Sem
  nenhum valor de linha.
- **Lacre** (`reports/comparacao/LACRE.json`, escrito por último): `commit`, `sha256` do manifesto,
  `arvore_limpa`, SHA-256 de cada artefato e de cada previsão, SHA-256 do `.dbc` de 2025
  (`87831a1ee61d03d0f83dcb788c23b1a5cfd938ec22f7e44313833e9eb6445d29`), `semente`, `reamostras`,
  `gravado_em_utc`. Existir impede nova execução (R2).
- **Porta por variável de ambiente:** os scripts de `scripts/comparacao/` só aceitam o ano de comparação com
  `DENGUE_PORTA_COMPARACAO=1`. É um contrato, e não uma barreira: quem a define é só o avaliador
  (`comparar.executar`), depois das checagens go/no-go (manifesto commitado e limpo, lacre ausente, SHA-256).
- **Agregados** (`reports/comparacao/`): `metricas.md|json`, `diferencas.md|json`, `conformidade.md`,
  `orcamentos.md` e as figuras `.png`. Células com < 10 casos suprimidas.

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

D-57, D-86. `<caminhos.dados>/m1/sessao-m1.json` no Drive (o clone do Colab some numa queda), gravado por
`verify.update_session_report` ao fim de cada etapa de `run_all_models` e copiado para
`reports/verificacao/sessao-m1.json` com `verify.show_report` (SHA-256 conferido, D-64).

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
- Blocos na ordem de gravação (um bloco regravado vai para o fim): `checagem_inicial`, os modelos na ordem do config, `selecao`,
  `shap`, `retreino`.
- `passou` (nível de cima) = `sessao_completa` e todos os blocos passaram.
