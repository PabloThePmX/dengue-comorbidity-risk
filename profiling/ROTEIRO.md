# Roteiro de profiling — SINAN Dengue 2022–2024

Objetivo: resolver os `[VERIFY]` de dados do [specs.md](../specs.md) **antes** de qualquer modelagem.
Cada passo diz *o que medir*, *por que importa*, *dicas* e *o que anotar*. O código é de vocês; no fim eu reviso.

**Ordem importa.** O passo 1 é bloqueante: se ele falhar, a definição do alvo muda e os passos seguintes mudam junto.

**Entregáveis:**
1. Um notebook (`profiling/01_profiling.ipynb`) que roda do zero: download → tabelas.
   - Já existe. Ele é **gerado** por `profiling/build_notebook.py`, que copia o código testado de `src/dengue_sinan/` para as células. Não editem o `.ipynb` à mão: editem `src/` e regerem com `uv run python profiling/build_notebook.py`.
   - No Colab: *Ambiente de execução → Executar tudo*. Tudo é gravado em `MyDrive/dengue-comorbidity-risk/`.
2. Um arquivo `profiling/RESULTADOS.md` preenchido com o template do fim deste roteiro.
   - O notebook gera esse arquivo sozinho, com a tabela-resumo e as tabelas detalhadas de cada passo.
3. As checagens que viraram regra, escritas como funções em `src/dengue_sinan/` (`features.py`, `profiling.py`, `download.py`), com testes em `tests/`. Elas viram o FR-03 do pipeline.

**Além do roteiro original, o notebook também mede:**
- No passo 1, o preenchimento de `GRAV_*` por `CLASSI_FIN`, que é a base de um alvo alternativo se aparecerem os códigos 1/2/8.
- No passo 2, os casos removidos por evolução, separados por `CLASSI_FIN`, para ver se graves saem por "evolução em branco".
- No passo 5, a distribuição do 1º dígito de `NU_IDADE_N` (unidade da idade).
- No passo 8, o ano de `DT_SIN_PRI` e de `DT_NOTIFIC` × ano do arquivo. Isso define qual data marca o "ano" no split temporal (D-08), que o spec ainda não fixa.
- No passo 10, a taxa por 100 mil com a população do Censo 2022 do IBGE (SIDRA, tabela 4709), usada para os três anos. É uma aproximação.

---

## Passo 0 — Ambiente e download

**O que fazer**
- Ambiente com `uv` (D-16): `pyreaddbc`, `dbfread`, `pandas`, `pyarrow`. Versões fixadas no `uv.lock`; no Colab, o notebook instala as mesmas versões de `pyreaddbc` e `dbfread`.
- Baixar `DENGBR22.dbc`, `DENGBR23.dbc` e `DENGBR24.dbc` **direto do FTP do DataSUS** (D-05): `ftp://ftp.datasus.gov.br/dissemin/publicos/SINAN/DADOS/FINAIS/`. Se o ano não existir em `FINAIS`, usar `PRELIM`.
- Converter cada `.dbc` em **um Parquet por ano**, com todas as colunas como texto cru (sem reinterpretar códigos), e salvar no Google Drive.
- Registrar em `data/manifest.json`, para cada ano:
  - URL, status no DataSUS (final ou preliminar) e **data de revisão do arquivo no FTP**;
  - data do download e **SHA-256 do `.dbc`** original;
  - linhas lidas, linhas declaradas no cabeçalho do DBF, colunas e nomes das colunas;
  - **SHA-256 do Parquet** e versões de Python, `pyreaddbc`, `dbfread`, `pyarrow` e `pandas`.

**Por que:** o DataSUS revisa os arquivos com o tempo, inclusive os "finais" (§3.7). Em 2026-11-02, os arquivos de 2022 e 2024 tinham sido revisados em março e fevereiro de 2026. Sem hash e data de revisão, ninguém reproduz o resultado (NFR-02).

**Por que FTP e não PySUS:** o PySUS 2.11.7 não baixa do DataSUS. Ele consulta um catálogo próprio em S3, e nesse catálogo o SINAN não tem nenhum arquivo indexado (detalhes em D-05).

**Dicas**
- O `.dbc` é um DBF comprimido. O `pyreaddbc` descomprime; o DBF tem registros de tamanho fixo e é lido em blocos, para 2024 caber na RAM do Colab.
- O Colab cai: salve os Parquets no Drive logo após converter e nunca dependa do disco local da sessão.
- Para o hash, `hashlib.sha256` lendo o arquivo em blocos.
- Confiram se "linhas lidas" = "linhas no cabeçalho do DBF". Diferença indica registros marcados como apagados.
- Anotem os nomes exatos das colunas (maiúsculas? `PETEQUIA_N` com ou sem acento?) e se o schema muda entre anos.

---

## Passo 1 — Códigos do alvo (BLOQUEANTE)

**O que medir:** a contagem de cada valor, **incluindo nulos**, de `CLASSI_FIN`, `EVOLUCAO` e `CRITERIO`, separada por ano.

**Por que:** os dois dicionários oficiais se contradizem (§3.6). O de 2015 diz 10/11/12 = dengue / com alarme / grave; o de 2024 diz 1/2/8 = confirmado / descartado / inconclusivo.

**Regra de decisão**
- Aparecem 10, 11 e 12 → a definição do alvo do spec vale. Sigam.
- Aparecem 1/2/8 (em algum ano) → **parem e me chamem.** D-02 precisa ser redecidido.
- Mistura dos dois ou valores inesperados → anotem tudo e me chamem.

**Dicas**
- `value_counts(dropna=False)` mostra os nulos; sem isso eles somem.
- Confiram o **tipo** da coluna: `"10"` (texto), `10` (inteiro) e `10.0` (float) parecem iguais na tela e quebram filtros.

---

## Passo 2 — Fluxograma de exclusão (FR-02)

**O que medir:** quantas linhas sobram, por ano, após cada filtro da população (§3.6), **nesta ordem**:
1. Total baixado.
2. `CLASSI_FIN` ∈ {10, 11, 12} (remove inconclusivos, código 0 e em branco; nos arquivos reais não há descartados nem chikungunya).
3. Rótulo conhecido: `CLASSI_FIN` = 12 com qualquer evolução, ou 10/11 com `EVOLUCAO` ∈ {1, 2} (D-45).
4. Idade válida, entre 0 e 120 anos (D-49).

**Por que:** é a primeira figura que o professor pede ("de onde vieram esses N casos?"), e mostra se algum filtro joga fora mais do que o esperado.

**Dica:** guardem também *quantos* saíram por *qual* motivo. Se muitos casos graves saírem por "evolução em branco", isso é um viés a discutir.

---

## Passo 3 — Prevalência e número de eventos

**O que medir** (após o filtro do passo 2; `y = 1` se `CLASSI_FIN` = 12 ou `EVOLUCAO` = 2):
- Prevalência de `y` por ano.
- Número de eventos (`y = 1`) por **região** em 2022–23 (as 5 dobras do leave-one-region-out).
- Número de eventos em **2024** por subgrupo: faixa etária, sexo, gestantes, região.

**Por que:** a literatura pede ≥ 100 eventos (idealmente ~200) para avaliar calibração com precisão (§3.8). Subgrupo abaixo disso tem IC largo demais para tirar conclusão.

**Dicas**
- A região sai da UF de residência (2 primeiros dígitos do código IBGE do município, ou a sigla). Usem a **residência**, não a notificação (é o que o portal do MS recomenda).
- Marquem com ⚠️ toda célula com < 100 eventos.
- Faixas etárias do spec: 0–4, 5–14, 15–39, 40–59, 60–79, 80+ (`[ASSUMPTION]`; se uma faixa ficar vazia, anotem).

---

## Passo 4 — Comorbidades e o check de vazamento

**O que medir**
- Para cada uma das 7 comorbidades: contagem de cada valor (1, 2, branco, outros) por ano.
- **O check principal:** % de "Ausente" (branco ou ≠ 1/2) em cada comorbidade, **separado por `y = 0` e `y = 1`**.

**Por que:** casos graves e óbitos são investigados e tendem a ter a ficha mais completa. Se "Ausente" for muito mais comum em `y = 0`, o modelo aprende "ficha incompleta = não grave". Isso é vazamento, não medicina (§3.8).

**Dicas**
- `pd.crosstab(..., normalize="columns")` dá as porcentagens por grupo direto.
- Reportem a razão: % ausente em `y = 0` ÷ % ausente em `y = 1`. Sugestão de alerta (decidam vocês): razão > 2 numa comorbidade → marcar para a análise de sensibilidade (Q-06).
- O dicionário diz que esses campos são obrigatórios e só aceitam 1/2. Se aparecer 9 ou branco em massa, isso por si só é um achado.

---

## Passo 5 — Idade

**O que medir**
- Decodificar `NU_IDADE_N` (1º dígito = unidade: 1 hora, 2 dia, 3 mês, 4 ano; §3.7) para anos.
- Distribuição, mínimo, máximo, quantos ficam fora de [0, 120], quantos são nulos.
- A idade decodificada bate com ano de `DT_SIN_PRI` − `ANO_NASC`? Os microdados não trazem `DT_NASC` (anonimização), só o ano, então a tolerância é de ±1 ano.

**Por que:** um erro na decodificação passa sem nenhum erro de execução e estraga a variável mais importante do modelo.

**Dica:** escrevam a decodificação como **função com teste unitário** (casos 1005, 2010, 3009, 4018, valor inválido). Ela vai para o pipeline depois.

---

## Passo 6 — Demografia

**O que medir**
- `CS_SEXO` (M/F/I), `CS_GESTANT` (1–6, 9) e `CS_RACA` (1–5, 9): contagens por ano.
- Inconsistências: gestante (1–4) com sexo M; gestante com idade < 10 anos.
- % de "ignorado" em raça/cor e escolaridade (responde Q-05).

---

## Passo 7 — Sinais clínicos e de alarme

**O que medir**
- Os 14 sinais do item 33 (`FEBRE` … `DOR_RETRO`, incluindo `LEUCOPENIA` e `LACO`): valores e % ausente por ano.
- Campos `ALRM_*`: % preenchido **por valor de `CLASSI_FIN`**.

**Por que:** pelo dicionário, `ALRM_*` só deveria estar preenchido quando `CLASSI_FIN` = 11 ou 12. Se isso se confirmar, a restrição de população do M2 (§3.6) está certa. Se `ALRM_*` aparecer preenchido em `CLASSI_FIN` = 10, anotem: muda a análise.

---

## Passo 8 — Datas

**O que medir**
- `DT_SIN_PRI` (primeiros sintomas) ≤ `DT_NOTIFIC` (notificação)? Quantos violam?
- Distribuição de dias entre sintomas e notificação: mediana, p95, p99 e máximo.

**Por que:** o spec trunca o atraso em 60 dias (`[ASSUMPTION]`, §3.9). Os dados dizem se 60 é razoável.

---

## Passo 9 — Duplicatas

**O que medir:** linhas repetidas pela chave composta `ANO_NASC` + idade + `CS_SEXO` + município de residência + `DT_SIN_PRI` (não há `DT_NASC` nos microdados). Total e % por ano. Comparar com `NDUPLIC_N`, a marcação de duplicidade do próprio SINAN.

**Por que:** duplicatas inflam contagens e podem cair em treino e teste ao mesmo tempo (responde Q-04).

**Dica:** reportem também quantas duplicatas têm **desfechos diferentes**. Isso indica notificações conflitantes, não só cópias.

---

## Passo 10 — Cobertura do Espírito Santo

**O que medir:** casos confirmados por UF e por ano. Comparem o ES com UFs vizinhas (MG, RJ, BA), de preferência por 100 mil habitantes.

**Por que:** desde 2020 o ES usa outro sistema (e-SUS VS), e o portal do MS avisa que os dados do ES vêm só do Sinan Online (§3.7). É provável que o ES esteja sub-representado.

---

## Passo 11 — Memória no Colab

**O que medir:** RAM total da sessão e memória do DataFrame dos 3 anos já filtrados, só com as colunas usadas.

**Por que:** define se RF e as 5 dobras cabem (NFR-01, risco em §3.17).

**Dica:** `df.memory_usage(deep=True).sum()`. Converter colunas de código para `category` costuma reduzir muito.

---

## Template — `profiling/RESULTADOS.md`

Uma linha por `[VERIFY]` do spec. Eu uso esta tabela para atualizar o spec e tirar os marcadores.

| # | Item | Seção do spec | Resultado (número ou achado) | Dentro do esperado? | Observação |
|---|---|---|---|---|---|
| 0 | Hash, data e versão de cada Parquet | §3.14 | | | |
| 1 | Valores de `CLASSI_FIN`/`EVOLUCAO`/`CRITERIO` por ano | §3.6 | | | |
| 2 | Fluxograma de exclusão | §3.6, FR-02 | | | |
| 3a | Prevalência de `y` por ano | §3.7 | | | |
| 3b | Eventos por região (2022–23) | §3.8 | | | |
| 3c | Eventos por subgrupo (2024) | §3.8, §3.12 | | | |
| 4a | Valores das comorbidades | §3.7 | | | |
| 4b | % ausente × `y` (vazamento) | §3.8 | | | |
| 5 | Idade: decodificação e faixa | §3.7, §3.9 | | | |
| 6 | Demografia e inconsistências | §3.7 | | | |
| 7a | Sinais clínicos: % ausente | §3.8 | | | |
| 7b | `ALRM_*` preenchido por `CLASSI_FIN` | §3.6 | | | |
| 8 | Atraso sintomas → notificação | §3.9 | | | |
| 9 | Duplicatas | §3.6 | | | |
| 10 | Cobertura do ES | §3.7 | | | |
| 11 | RAM do Colab e tamanho do DataFrame | NFR-01 | | | |

---

## Como eu vou revisar

Quando vocês terminarem, eu confiro:
- se o notebook roda do zero, com hash e versões registrados;
- se as contagens fecham entre si (soma por região = total, fluxograma consistente);
- se algum resultado contradiz o spec, e o que muda nesse caso;
- a qualidade do código das funções de checagem (nomes, testes, tratamento de nulos).
