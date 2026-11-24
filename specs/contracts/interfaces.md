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
- **Previsões** (`data/comparacao/p_<id>_<ano>.parquet`): `ANO`, `LINHA` e `p` (float64, em [0, 1], sem NaN; no E1, NaN só onde `estimavel = false`, D-99),
  uma linha por linha da entrada, na mesma ordem e sem repetição. Um modelo com linha faltando é recusado.
- **Subconjunto do E1 (D-99):** as previsões do E1 trazem a coluna `estimavel` (bool); onde é `false`, `p` é
  NaN. O avaliador define a **população principal** como as linhas com `estimavel = true`, a mesma para todos os
  modelos, e reporta a população completa como informação.
- **Conformidade** (`.conformidade.json`, por modelo): `sha256` conferido, `variaveis` e se estão no dicionário
  (R4), parâmetros do estimador e a busca por correção de desbalanceamento (R3), anos de treino, versões do
  ambiente de execução e de treino, estatísticas de `p` (mínimo, máximo, média, nº de 0 e de 1, NaN). Sem
  nenhum valor de linha.
- **Lacre em duas fases** (`reports/comparacao/LACRE.json`, escrita atômica; `status` e `sha256_entrada` entram
  no lacre): a **fase 0** (`status: "previsoes_geradas"`) é gravada quando todas as previsões existem, passam na
  checagem de formato e foram alinhadas com o `y` (sem calcular nenhuma métrica), antes de `calcular`; a **fase
  final** (`"concluido"`, com `sha256_metricas`) depois dos agregados e antes das figuras. Qualquer falha a partir
  da fase 0 deixa o lacre e impede nova execução (R2). `--retomar` aceita só `previsoes_geradas`: confere o
  SHA-256 do manifesto, da entrada e das previsões contra o lacre **antes** de abrir a porta, que fica aberta só em
  volta da leitura da entrada e do alinhamento; recalcula com a mesma semente (mesmo resultado), sem ler o
  `.dbc`, sem o parquet bruto e sem `exportar_entrada`. Falha **antes** da fase 0 (um script externo, ou
  alinhamento inválido) não deixa lacre nem agregados: nenhuma métrica foi vista, e nova tentativa é permitida. A
  única janela que resta é a falha de escrita da própria fase 0. Campos: `commit`, `sha256` do manifesto,
  `arvore_limpa`, SHA-256 de cada artefato, de cada previsão e do JSON de conformidade de cada modelo
  (`sha256_conformidade`, conferido no `--retomar`), SHA-256 do `.dbc` de 2025
  (`87831a1ee61d03d0f83dcb788c23b1a5cfd938ec22f7e44313833e9eb6445d29`), `semente`, `reamostras`,
  `gravado_em_utc`. Existir impede nova execução (R2).
- **Porta por variável de ambiente:** os scripts de `scripts/comparacao/` só aceitam o ano de comparação com
  `DENGUE_PORTA_COMPARACAO=1`. É um contrato, e não uma barreira: quem a define é só o avaliador
  (`comparar_executar.executar`), depois das checagens go/no-go (manifesto commitado e limpo, lacre ausente, SHA-256).
- **Agregados** (`reports/comparacao/`): `metricas.json` (fonte única, formato abaixo) e, geradas dele,
  `metricas.md`, `diferencas.md`, `orcamentos.md`, `conformidade.md` e as figuras `.png`. Células com < 10
  casos suprimidas.
- **`metricas.json`** (escrito por `comparar.py`, lido por `comparar_graficos.py`; só agregados, R7). Chaves:
  - `ano` (int), `reamostras` (int), `semente` (int), `modelos` (lista de `id`, na ordem do manifesto) e
    `modelo_de_referencia` (`"m1_main"`).
  - `populacoes`: `{"principal": {"nome", "casos", "eventos", "prevalencia"}, "completa": {...}}`. A principal é
    o subconjunto que o E1 estima (D-99); a completa é informação.
  - `metricas[<populacao>][<id>]`: para cada uma de `pr_auc`, `roc_auc`, `brier`, `calibration_slope`,
    `calibration_intercepto`, `obs_esp`: `{"valor": float, "ic95": [inf, sup]}` (ou `null` se o modelo não
    estima a população, p. ex. E1 na completa).
  - `diferencas_pr_auc_vs_referencia[<populacao>][<id>]`: `{"valor", "ic95", "leitura"}`, com `leitura` em
    `"melhor"`, `"pior"` ou `"sem diferença detectável"` (o IC exclui 0 ou não, SC-09).
  - `orcamentos[<populacao>][<id>]["0.05" | "0.10" | "0.14"]`: `{"alertas": int, "recall": {"valor",
    "ic95"}, "precisao": {"valor", "ic95"}}` (recall e precisão entre os X% de maior risco).
  - `no_limiar_proprio[<id>]`: `{"limiar", "alertas", "recall", "precisao"}` (só informação; `null` sem limiar).
  - `curva_decisao`: `{"limiares": [floats em fração], "<id>": [net benefit por limiar]}` (população principal).
  - `calibracao[<id>]`: lista de caixas por quantil `{"previsto", "observado", "ic95", "casos"}`; caixa com
    menos de 10 casos ou eventos suprimida (R7).
  - `conformidade[<id>]`: `{"r3_sem_correcao": bool, "r4_variaveis_no_dicionario": bool,
    "treino_sem_ano_de_comparacao": bool, "versoes_diferentes_do_treino": bool|null, "externo": bool}`.
  - **Convenções** (fixadas na T-8.7 e T-8.8; `comparar.py` escreve, `comparar_graficos.py` lê):
    - `diferencas_pr_auc_vs_referencia[...]["valor"]` = PR-AUC do modelo **menos** a do `modelo_de_referencia`;
      `"melhor"` quando o IC inferior é > 0 (o modelo supera o M1), `"pior"` quando o IC superior é < 0.
      A entrada da própria referência é `null`.
    - `{"valor": null, "ic95": null}` quer dizer "indisponível" (modelo que não estima a população, métrica que
      não converge, B0 constante). `null` no lugar de um modelo inteiro vale o mesmo.
    - **Caixa de calibração suprimida (R7):** com menos de 10 casos, `{"previsto": null, "observado": null,
      "ic95": null, "casos": "<10"}`; com casos ≥ 10 e menos de 10 eventos, mantém `casos` e `previsto` e anula
      `observado` e `ic95`. Quem desenha **ignora** caixa suprimida e **recusa** caixa com `casos` numérico < 10.
    - `orcamentos`: `alertas = round(X · n)` (metade para cima); empate de `p` desempata pela menor `LINHA`.
    - **Supressão R7 na publicação (nunca recusa depois de calcular):** contagem de 1 a 9 em `alertas`
      (orçamentos e `no_limiar_proprio`), `casos` e `eventos` vira a string `"<10"` no JSON e nos `.md`; 0 e
      ≥ 10 continuam numéricos. Quando `alertas` está entre 1 e 9, ou os eventos capturados entre os alertas
      estão entre 1 e 9, o `recall` e a `precisao` dessa linha saem `{"valor": null, "ic95": null}` (`"<10"` nos
      `.md`) e o gráfico não os desenha. O cálculo interno não muda; os validadores aceitam `"<10"` e recusam um
      número entre 1 e 9. A saída de `comparar.py` nunca levanta por R7 depois de as métricas existirem, para
      que 2025 não seja lido duas vezes.
    - `curva_decisao` traz só os modelos e a grade de limiares; a linha "tratar todos" é derivada da
      prevalência de `populacoes.principal` (sem ler dados).
    - `versoes_diferentes_do_treino` é `null` quando não há como comparar (o projeto não grava as versões).

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
