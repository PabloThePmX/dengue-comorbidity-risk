# Pipeline de ML (Etapa 2)

Separa preparação, treino, avaliação e inferência. Código em `src/dengue_sinan/pipeline/`.
Não há API, frontend nem deploy. A v1 histórica (`reports/modelo_risco_dengue/`) não é tocada.

## 1. Arquitetura

| Módulo | Responsabilidade | Importa dados de treino? |
|---|---|---|
| `contrato.py` | Campos, tipos, categorias, padrões e lista de variáveis autorizadas | Não |
| `preprocessamento.py` | Validação de registros e matriz do modelo (usado no treino **e** na inferência) | Não |
| `preparacao.py` | Lê os Parquets de 2022–2023, aplica a população (D-45) e monta as variáveis | Sim |
| `treino.py` | Validação cruzada por região, calibrador, modelo final, metadados | Sim |
| `avaliacao.py` | Métricas de discriminação e calibração, com escopo e limitações | Não |
| `artefatos.py` | Grava e verifica `modelo.joblib` + JSONs, com hashes | Não |
| `inferencia.py` | Carrega o artefato e devolve probabilidades | **Não** |
| `cli.py` | `preparar`, `treinar`, `avaliar`, `prever` | — |

`inferencia.py` não importa `treino`, `preparacao`, `etapa1`, `download` nem `explain`
(um teste confere isso em subprocesso, sem Parquets).

A preparação reusa `etapa1.carregar_bruto_dev` (recusa 2024), `dataset.montar_populacao` e
`dataset.montar_features`. O treino reusa `modelos.ModeloM1`, `cv_oof`, `Calibrador`,
`calibrar_cruzado` e `ajustar_final`. A inferência usa a mesma `matriz_arvore` do treino.

## 2. Variáveis

`config/variaveis_autorizadas.json` lista as variáveis aceitas: **`idade_anos`, `sexo`,
`gestante`**. Comorbidades, sintomas, achados e `dias_ate_notificacao` ficam de fora: na auditoria
(J4) nenhuma foi classificada como Segura. Mudar essa lista é decisão do responsável pelo
projeto e deve ficar registrada no relatório da etapa.

## 3. Comandos (da raiz do repositório)

```bash
# ambiente: Python 3.13; instale com `uv sync` (ver pyproject.toml e uv.lock)
# o pipeline também precisa de scikit-learn, xgboost, joblib e statsmodels (ver seção 7)

# 1. Preparar (só 2022 e 2023; saída FORA de reports/)
python -m dengue_sinan.pipeline.cli preparar --data-dir data/parquet \
    --saida data/processed/dev_2022_2023.parquet

# 2. Treinar (grava artefatos/modelos/<nome>-<versão>/; nunca sobrescreve)
python -m dengue_sinan.pipeline.cli treinar --config config/treino_perfil.json \
    --dados data/processed/dev_2022_2023.parquet --saida artefatos/modelos

# 2b. Checar reprodução (treina duas vezes e compara; não grava artefato)
python -m dengue_sinan.pipeline.cli treinar --repetir-e-comparar \
    --config config/treino_perfil.json --dados data/processed/dev_2022_2023.parquet

# 3. Avaliar (mostra a avaliação de desenvolvimento guardada no treino)
python -m dengue_sinan.pipeline.cli avaliar --artefato artefatos/modelos/m1-perfil-2.0.0

# 4. Prever (json ou csv)
python -m dengue_sinan.pipeline.cli prever --artefato artefatos/modelos/m1-perfil-2.0.0 \
    --entrada registros.json
```

Em Python:

```python
from dengue_sinan.pipeline.inferencia import carregar_modelo, EntradaInvalida

modelo = carregar_modelo("artefatos/modelos/m1-perfil-2.0.0")   # confere os hashes
modelo.prever([{"idade_anos": 34, "sexo": "F", "gestante": 0}])
modelo.prever(registros, erros="marcar")                         # inválido vira status="invalido"
```

Para uma nova versão, copie `config/treino_perfil.json`, mude `versao_modelo` e passe
`--config`. O treino recusa gravar numa pasta que já existe.

## 4. Contrato de inferência

Entrada: lista de dicionários (ou DataFrame), um por paciente.

| Campo | Tipo | Obrigatório | Aceito | Se ausente ou nulo |
|---|---|---|---|---|
| `idade_anos` | número (int ou float) | **sim** | 0 a 120 | erro |
| `sexo` | texto | não | `"F"`, `"M"`, `"I"` (exato) | `"I"` |
| `gestante` | 0/1 ou false/true | não | 0, 1, false, true | `0` |

- Tipos são estritos: `"34"` (texto) e `true` como idade são recusados.
- Campo fora da lista (por exemplo `DIABETES` ou `CLASSI_FIN`) **sempre** levanta `EntradaInvalida`.
- Registro inválido: por padrão levanta `EntradaInvalida` (`.erros` traz linha, campo e motivo).
  Com `erros="marcar"`, a linha sai com `status="invalido"` e `probabilidade` nula.

Saída: um DataFrame na ordem da entrada, com `probabilidade` (float de 0 a 1, calibrada),
`status` (`ok` ou `invalido`), `erro` (texto) e `versao_modelo` (ex.: `m1-perfil-2.0.0`).
O desfecho é dengue grave (CLASSI_FIN = 12) ou óbito pelo agravo (EVOLUCAO = 2), em paciente
notificado com dengue (D-02). A mesma descrição está em `contrato.json` dentro do artefato.

## 5. Artefatos

Novos, em `artefatos/modelos/<nome>-<versão>/` (não em `reports/`):

| Arquivo | Conteúdo |
|---|---|
| `modelo.joblib` | Motor XGBoost e calibrador. Sem dados de treino |
| `metadados.json` | Versão, algoritmo, parâmetros, variáveis (ordem e tipos), pré-processamento, bibliotecas, anos, data de treino, hashes dos dados e dos arquivos, condições de reprodução, limitações |
| `contrato.json` | O que a inferência aceita e devolve |
| `avaliacao_dev.json` | Métricas de desenvolvimento (validação cruzada por região) e limitações |

Históricos da v1, preservados e distintos: `reports/modelo_risco_dengue/` (resultados, lacre,
`m1_congelado.joblib` e metadados), `notebooks/`. A v2 não os lê nem os substitui, e o teste de
2024 continua lacrado.

`joblib` executa código ao carregar. O hash em `metadados.json` detecta corrupção, não protege
contra quem troca arquivo e metadados juntos. Carregue só artefatos de origem confiável.

## 6. Reprodutibilidade

Condições para repetir um treino: mesmos dados na **mesma ordem de linhas e colunas** (o hash em
`metadados.json` cobre conteúdo e ordem), mesma configuração e semente (`20261103`), mesmas versões
de numpy, pandas, scikit-learn e xgboost. Nesta máquina, duas execuções com os mesmos insumos
deram predições idênticas.

Fontes de variação conhecidas (auditoria 1D): ordem das linhas, ordem das colunas e semente
alteram o ajuste do XGBoost, porque a parada antecipada usa poucos eventos. O número de threads
não alterou o resultado. Plataforma (sistema operacional e build do xgboost) não foi testada.
**Não há promessa de determinismo entre ambientes.**

## 7. Ambiente

`pyproject.toml` e `uv.lock` não foram alterados e não listam scikit-learn, xgboost, joblib nem
statsmodels, que o pipeline e `modelos.py` já exigem. Versões usadas nesta etapa: Python 3.13.18,
numpy 2.5.4, pandas 2.3.3, pyarrow 26.0.0, scikit-learn 1.9.1, xgboost 3.4.1, joblib 1.6.0.
Decidir se essas dependências entram no `pyproject.toml` é uma pendência (ver relatório).

## 8. Limitações

- Só três variáveis de entrada. A discriminação é baixa (ver `avaliacao_dev.json`).
- Métricas de desenvolvimento, não de teste. Não há validade clínica demonstrada.
- Os hiperparâmetros e o calibrador vêm da v1 e não foram reotimizados para três variáveis.
- Sensibilidade do ajuste a ordem e semente (seção 6).
- A falha de CRLF em `tests/test_hash_lacre.py` continua como estava (ver Etapa 1C).
- Sem Git na pasta; o commit do código não é registrado nos metadados.
