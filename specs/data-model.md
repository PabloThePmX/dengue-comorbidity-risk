# Modelo de dados — Risco de desfecho grave em dengue por perfil de comorbidades

> Artefato de dados no padrão Spec Kit (D-55): entidades, campos, regras de validação e o
> dicionário de features. Requisitos em [spec.md](spec.md) (§3.6 define população, alvo e momento
> da predição; §3.8, o que pode ser feature). Os IDs valem em todos os arquivos de `specs/`.
> Idioma: pt-BR (entregável acadêmico).

---

## C. Entidades

| Entidade | O que representa | Campos principais | Regras e relações |
|---|---|---|---|
| **Notificação** | Uma linha do arquivo SINAN-Dengue de um ano (§3.7). | Perfil (`NU_IDADE_N`, `ANO_NASC`, `CS_SEXO`, `CS_GESTANT`, `CS_RACA`), 7 comorbidades, sintomas, `DT_SIN_PRI`, `DT_NOTIFIC`, `CLASSI_FIN`, `EVOLUCAO`, `ID_MN_RESI`, `SG_UF`. | Todas as colunas lidas como texto cru. Sem identificador pessoal; duplicatas só reportadas (D-47). |
| **Caso da população** | Notificação que passa nos filtros de §3.6. | Os campos da notificação + `y`, `idade_anos`, `idade_de_ano_nasc`, `faixa_etaria`, `regiao`, `gestante`, `ANO` (ano do arquivo, D-46). | Filtros aplicados em ordem e contados no fluxograma (FR-02). `regiao`, `faixa_etaria`, `CS_RACA` e `ANO` nunca entram como feature. |
| **Perfil** | Combinação de faixa etária, sexo, gestação e comorbidades, sem sintomas. | Faixa, sexo, gestante, as 7 comorbidades. | Unidade da tabela de perfis (FR-06) e da aba Perfil; células com < 10 casos suprimidas (NFR-03). |
| **Dobra** | Uma região deixada de fora na validação leave-one-region-out (§3.8). | Região de validação, índices de treino e de validação, validação interna (10%). | 5 dobras, ordem fixa (D-53), salvas com hash e reutilizadas por todos os modelos. |
| **Modelo** | E1 (explicativo), M1 (triagem) ou baseline B0–B2. | Pipeline, calibrador, limiar, metadados (FR-12). | Ajustado só em 2022–23; avaliado em 2024 uma vez (FR-09). |
| **Predição** | Saída de um modelo para um caso. | Risco calibrado, "alto risco" no limiar, versão do modelo; na Triagem, os 5 fatores SHAP. | Formatos em [contracts/interfaces.md](contracts/interfaces.md) (§3.15). |

**Ciclo de vida de uma notificação** (fluxograma, FR-02): arquivo do ano → `CLASSI_FIN` ∈ {10, 11, 12}
→ rótulo conhecido (D-45) → idade válida (D-49, D-50) → caso da população com `y`.

---

## 3.7 Dados

- **Fonte:** SINAN — Dengue (agravo `DENG`), microdados públicos do DataSUS, baixados direto do FTP oficial (D-05): `ftp.datasus.gov.br/dissemin/publicos/SINAN/DADOS/FINAIS/DENGBR{AA}.dbc`.
  - Verificado em 2026-11-02: os arquivos de 2022, 2023 e 2024 estão em `FINAIS` (não em `PRELIM`). Datas de revisão no FTP: 2022 = 19/03/2026, 2023 = 17/03/2026, 2024 = 27/02/2026. Ou seja, o DataSUS revisa arquivos "finais" anos depois; o hash e a data de revisão são registrados no manifesto (§3.14).
  - Leitura do `.dbc` (DBF comprimido) com `pyreaddbc` + `dbfread`, versões pinadas no `uv.lock` (D-16).
- **Licença / acesso:** verificado em 2026-11-01 na [página do dataset Sinan/Dengue](https://dadosabertos.saude.gov.br/dataset/arboviroses-dengue). O portal declara, para todo o site, licença **Creative Commons Atribuição-SemDerivações 3.0**; a página do dataset não tem licença própria. Autoria: CGARB/DEDT/SVSA/MS e CGIAE/DAENT/SVSA/MS. Regra do projeto: citar a fonte e não redistribuir os microdados (NFR-03).
- **Notas oficiais do dataset que afetam o projeto** (mesma página):
  - Para série histórica, o MS usa bases **congeladas** por ano; os dados mais recentes mudam diariamente. Por isso o hash do snapshot (§3.14) é obrigatório.
  - **Espírito Santo:** desde 2020 o estado usa o e-SUS Vigilância em Saúde, e o portal considera para dengue no ES só os dados do Sinan Online. **A hipótese de sub-representação não se confirmou**: a taxa do ES foi 236 / 2.855 / 3.053 casos por 100 mil (2022 / 2023 / 2024), contra 132 / 237 / 1.419 de mediana entre BA, MG e RJ (população do Censo 2022). O ES é o maior da vizinhança em 2023.
    - **Idade no ES em 2022:** `NU_IDADE_N` vem em anos simples ("33"), sem o dígito de unidade: 11.175 dos 11.241 registros. Esses anos concordam 100% com ano dos sintomas − `ANO_NASC` (verificado em 2026-11-03 numa leitura temporária do arquivo de 2022, já apagada). Sem correção, o filtro de idade excluiria o ES 2022 inteiro (D-50).
    - O que difere é a **origem do registro**: no ES (2022–24), `TP_SISTEMA` é "0" (116.208) ou branco (119.121), com 206 "2" e 25 "/"; em MG, RJ e BA é quase sempre "2". Diferença de sistema pode significar diferença de preenchimento. Fica como limitação e como subgrupo a olhar na análise de erros (§3.12). `[VERIFY]` Significado dos códigos de `TP_SISTEMA` no dicionário.
- **Período e cobertura (D-04):** Brasil, 2022–2024. 2017–2024 só na análise de sensibilidade extra (FR-16).
- **Tamanho**, com a população final (D-45 e idade com o fallback de D-50):

  | | 2022 | 2023 | 2024 |
  |---|---|---|---|
  | Notificações no arquivo | 1.405.095 | 1.645.956 | 6.564.924 |
  | Após `CLASSI_FIN` ∈ {10, 11, 12} | 1.254.238 | 1.426.773 | 6.014.359 |
  | Após rótulo conhecido (D-45) | 1.148.338 | 1.304.949 | 5.331.924 |
  | Após idade válida (D-50) | 1.148.299 | 1.304.909 | 5.331.745 |
  | Eventos (y = 1) | 1.869 | 2.116 | 11.338 |
  | Prevalência de y | 0,16% | 0,16% | 0,21% |

  - Desenvolvimento (2022–23): 2.453.208 casos e 3.985 eventos; teste (2024): 5.331.745 casos e 11.338 eventos. População total: 7.784.953.
  - A prevalência é **muito baixa** (cerca de 1 evento a cada 470–630 casos). A PR-AUC de B0 fica entre ~0,0016 e ~0,0021.
  - **Fallback de idade verificado:** 11.428 / 48 / 95 idades recuperadas por `ANO_NASC`; só 123 / 63 / 256 notificações ficam sem idade, e na população isso remove 39 / 40 / 179 casos. O ES de 2022 tem 9.062 casos (236 por 100 mil).
- **Dicionários de dados:**
  - [Dicionário de dengue do portal de dados abertos do MS](https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SINAN/Dengue/dic_dados_dengue.pdf) (recurso criado em 22/02/2024, atualizado em 22/03/2024) — o mais recente, mas contraditório em `CLASSI_FIN` (§3.6).
  - [Dicionário SINAN Online — Dengue/Chikungunya (MS/GT-SINAN, rev. 2015)](https://app.wiki.saude.es.gov.br/vigilancia/microdados/dic_dados_dengue.pdf).
  - [Dicionário da notificação individual — SINAN Net v5.0 (rev. nov/2018)](https://rfsaldanha.github.io/sis/assets/sinan/agravos/NINDIN_DIC_DADOS.pdf) (cópia não oficial) — campos de idade, sexo, gestação e raça/cor.
  - Regra geral: **os dados mandam.** Quando dicionário e dados divergirem, vale o que o profiling mostrar, e a divergência é documentada.
- **Codificação do alvo (§3.6, D-02).** Códigos nos dicionários oficiais (conferidos em 2026-11-01):
  - Dicionário SINAN Online de dengue, rev. 2015: `CLASSI_FIN` 5 = descartado, 10 = dengue, 11 = dengue com sinais de alarme, 12 = dengue grave, 13 = chikungunya. `EVOLUCAO` 1 = cura, 2 = óbito pelo agravo, 3 = óbito por outras causas, 4 = óbito em investigação, 9 = ignorado. `CRITERIO` 1 = laboratório, 2 = clínico-epidemiológico, 3 = em investigação.
  - Dicionário de dengue publicado no portal de dados abertos do MS (arquivo de 2024): `EVOLUCAO` igual ao de 2015, mas `CLASSI_FIN` aparece como branco/0/9 = ignorado, 1 = confirmado, 2 = descartado, 8 = inconclusivo, e `CRITERIO` ganha 3 = clínico. **O mesmo documento**, nas regras dos campos `ALRM_*` e `GRAV_*`, ainda cita "Classificação = 11 / 12". Ou seja, o dicionário de 2024 se contradiz.
  - **Verificado no profiling: a regra de D-02 vale.** Valores de `CLASSI_FIN`: 10, 11, 12, 8 (inconclusivo) e branco nos três anos, e 0 só em 2022–23; **1 e 2 não aparecem**, e 5 (descartado) e 13 (chikungunya) também não. Os arquivos públicos usam a codificação 10/11/12 do dicionário de 2015, com o 8 = inconclusivo do dicionário de 2024.
  - Contagens: `CLASSI_FIN` = 12 em 1.548 / 1.686 / 8.831; `EVOLUCAO` = 2 em 1.056 / 1.192 / 6.337 (2022 / 2023 / 2024, todas as notificações).
  - `CLASSI_FIN` = 0 (8.442 linhas: 330 em 2022 e 8.112 em 2023) tem `ALRM_*` e `GRAV_*` preenchidos em 100% das linhas: código anômalo, fora da população.
  - Nas notas do portal, o MS define "casos graves" como **dengue com sinais de alarme + dengue grave**. O alvo deste projeto (D-02) é mais estrito (só dengue grave + óbito). Ao comparar com números oficiais no relatório, explicitar essa diferença.
- **`ALRM_*` por classe (restrição do M2, §3.6):** algum `ALRM_*` está preenchido em **99,8%** dos casos 11, **92,9%** dos 12 e só **3,3%** dos 10 (todos os anos). `[VERIFY]` Na implementação do M2: quais valores aparecem nos 3,3% dos casos 10.
- **Duplicidade (D-47):** os microdados não trazem `DT_NASC`, só `ANO_NASC`. Pela chave composta (ano de nascimento + idade + sexo + município de residência + data de sintomas), os grupos "duplicados" somam **17,3% (2022), 21,1% (2023) e 42,4% (2024)** da população. Isso é implausível como duplicidade real: num ano de epidemia, pessoas diferentes da mesma cidade, com mesmo sexo, idade e dia de sintomas, são comuns. Remover pela chave apagaria ~1,6 milhão de casos de 2024 (1.594.148 linhas excedentes).
  - `NDUPLIC_N` (marcação do próprio SINAN), na população final: em branco em 99,9% / 99,85% / 97,6% das linhas; "1" em 1.304 / 1.918 / 12.491; "0" em 116.455 (só 2024); "/" em 26 (só 2023). `[VERIFY]` Significado dos códigos no dicionário antes de usar.
- **Comorbidades disponíveis (item 34 da ficha, "Doenças pré-existentes")** — verificado nos dois dicionários (2026-11-01) e nos dados:
  `DIABETES`, `HEMATOLOG` (doenças hematológicas), `HEPATOPAT` (hepatopatias), `RENAL` (doença renal crônica), `HIPERTENSA` (hipertensão arterial), `ACIDO_PEPT` (doença ácido-péptica), `AUTO_IMUNE` (doenças autoimunes).
  **Não há campo de doença respiratória.**
- **Codificação das comorbidades e dos sinais clínicos:** verificado em 2026-11-01. Os dois dicionários listam só **1 = sim, 2 = não**, como "campo obrigatório", **sem** a categoria 9 = ignorado.
  - **Nos dados**: aparecem 1, 2, branco e ~210 linhas com "9" por comorbidade (fora do domínio do dicionário). O branco é **da seção inteira**: o mesmo número de linhas (56.222 / 52.954 / 114.119) está em branco nas 7 comorbidades, e os 14 sinais clínicos também ficam em branco juntos (4,0% / 3,2% / 1,7%).
  - Frequência entre as notificações de 2024: hipertensão 10,1%; diabetes 4,4%; autoimune 0,7%; hematológica, hepatopatia, ácido-péptica e renal ~0,5% cada.
  - Consequência para D-07: o 3º nível passa a ser "ausente/fora do domínio" (branco ou qualquer valor ≠ 1/2), e não "ignorado" declarado. O tratamento continua o mesmo.
- **Demografia** (dicionário da notificação individual, verificado em 2026-11-01):
  - `NU_IDADE_N`: 1º dígito = unidade (1 = hora, 2 = dia, 3 = mês, 4 = ano), restante = valor. Ex.: 3009 = 9 meses, 4018 = 18 anos. Calculada a partir da data de nascimento quando houver. Os microdados públicos não trazem `DT_NASC`, só `ANO_NASC` (verificado em 2026-11-02).
  - `CS_SEXO`: M, F, I = ignorado.
  - `CS_GESTANT`: 1–3 = 1º–3º trimestre, 4 = idade gestacional ignorada, 5 = não, 6 = não se aplica, 9 = ignorado. "Gestante" no projeto = 1–4 `[ASSUMPTION]`.
  - `CS_RACA`: 1 = branca, 2 = preta, 3 = amarela, 4 = parda, 5 = indígena, 9 = ignorado.
- **Missingness**:
  - Na **população final**, "Ausente" nas comorbidades é quase inexistente: 0,00% em y = 0 e 0,01% em y = 1. Os brancos estão nas linhas que a regra de população já exclui. O vazamento por completude (§3.8) **não se confirmou**, e a análise de sensibilidade de Q-06 é dispensada (D-49). A categoria "Ausente" de D-07 fica mantida, mas quase vazia.
  - Raça/cor: 19,8% / 16,5% / 16,2% de ignorado ou branco. Escolaridade: 51,5% / 50,2% / 53,9% (D-48).
  - Não medido: missingness por UF.
- **Vieses conhecidos:**
  - Subnotificação de casos leves → o risco estimado é condicional a "ser notificado e confirmado", não à população infectada.
  - Confirmação laboratorial depende de acesso a exame (viés regional).
  - **Mudança de sorotipo:** o DENV-3, ausente por anos, voltou a circular em 2023–2024. Até 13/12/2023 havia 130 casos de DENV-3 confirmados em 11 estados, numa população muito suscetível ([Viruses/MDPI 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC10974589); [São Paulo, PubMed 39848015](https://pubmed.ncbi.nlm.nih.gov/39848015/)). Verificado em 2026-11-01 (resumos). É uma fonte plausível de drift entre treino (2022–23) e teste (2024).
  - **Subnotificação na COVID (2020–21):** em 19 de 25 estados, houve menos casos que o esperado em 2020, e a diferença foi explicada principalmente por subnotificação ([Martinelli/Roster et al., PLOS NTD 2024](https://consensus.app/papers/details/7900fddd46c15471b49d6525ff752d3c/)). Verificado em 2026-11-01 (resumo). Reforça deixar 2017–2024 só como sensibilidade (FR-16).
- **Checks de qualidade (FR-03):**
  - Bloqueantes: schema esperado presente em todos os anos (121 colunas, idêntico em 2022–24); alvo sem valores fora do domínio. **Idade fora de [0, 120] ou código inválido deixou de ser bloqueante** (D-49): primeiro tenta-se a idade por `ANO_NASC` (D-50); só o que sobrar sem idade é excluído e contado no fluxograma. Códigos inválidos: 11.507 + 44 fora da faixa em 2022 (quase todos do ES), 55 + 56 em 2023 e 111 + 240 em 2024. Em 2022, 11.428 dos 11.551 inválidos têm `ANO_NASC` utilizável.
  - Alertas: data de primeiros sintomas > data de notificação; gestante com sexo masculino; taxa de "ignorado" > 50% em alguma comorbidade numa UF/ano.
  - Duplicatas por chave composta: só reportar a taxa (D-47).
- **Dados pessoais:** microdados são anonimizados, mas combinações raras (idade + município + data) podem identificar pessoas. Por isso não se publica nada linha a linha (NFR-03), e a tabela de perfis só reporta células com contagem mínima (§3.12).

---

## D. Dicionário de features

Lista fechada (regra R4 da constituição). O [tasks/00-como-usar.md](tasks/00-como-usar.md) §1.3 traz uma cópia para
referência rápida; se divergir, vale esta.

| Feature | Origem | Tipo | Transformação |
|---|---|---|---|
| `idade_anos` | `NU_IDADE_N` decodificado; fallback por `ANO_NASC` (D-50) | contínua | logística/MLP: spline (5 nós `[ASSUMPTION]`) + escala; árvores: crua |
| `sexo` | `CS_SEXO` | categórica: M, F, I/branco → "I" | one-hot (logística/MLP); nativa/ordinal (árvores) |
| `gestante` | `CS_GESTANT` ∈ {1, 2, 3, 4} | binária | 0/1 |
| 7 comorbidades | `DIABETES`, `HEMATOLOG`, `HEPATOPAT`, `RENAL`, `HIPERTENSA`, `ACIDO_PEPT`, `AUTO_IMUNE` | 3 níveis: Sim (1) / Não (2) / Ausente (resto), D-07 | one-hot (logística/MLP); ordinal/nativa (árvores) |
| `n_comorbidades` | soma das comorbidades = Sim | inteira 0–7 | crua |
| 12 sintomas | `FEBRE`, `MIALGIA`, `CEFALEIA`, `EXANTEMA`, `VOMITO`, `NAUSEA`, `DOR_COSTAS`, `CONJUNTVIT`, `ARTRITE`, `ARTRALGIA`, `DOR_RETRO`, `PETEQUIA_N` | 3 níveis | igual às comorbidades |
| `LEUCOPENIA`, `LACO` | item 33 da ficha | 3 níveis | igual às comorbidades |
| `dias_ate_notificacao` | `DT_NOTIFIC` − `DT_SIN_PRI` (dias) | contínua | truncar em [0, 60] |

- **E1 e B1** usam só o perfil: `idade_anos` (spline), `sexo`, `gestante`, 7 comorbidades e
  `n_comorbidades` (só B1). Sem sintomas.
- **Atenção a nomes parecidos:** entram `PETEQUIA_N` e `LACO` (item 33). Ficam fora `PETEQUIAS` e
  `LACO_N`, da classificação antiga de febre hemorrágica, que funcionam como proxy do rótulo (§3.8).
