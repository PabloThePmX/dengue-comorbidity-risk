# `notebooks/` — modelo de risco de dengue grave/óbito

| Arquivo | Função |
|---|---|
| `modelo_risco_dengue.ipynb` | Notebook completo (19 seções). **Gerado**: não edite à mão. |
| `build_modelo_risco_dengue.py` | Gera o notebook copiando os módulos de `src/dengue_sinan/` para células (mesmo padrão de `profiling/build_notebook.py`). |
| `smoke_test_sintetico.py` | Teste de fumaça: gera Parquets **sintéticos** (nunca são dados do SINAN) e executa o notebook. Só verifica que o código roda; **nenhum número dali tem valor científico**. |

## Como executar

```bash
# raiz do repositório; instala o que faltar (a 1ª célula usa pip)
jupyter nbconvert --to notebook --execute --inplace notebooks/modelo_risco_dengue.ipynb
```

- **Colab:** abra o `.ipynb` e use *Executar tudo*; o Drive é montado e tudo fica em
  `MyDrive/dengue-comorbidity-risk/`.
- **Dados:** se `data/parquet/dengue_{ano}.parquet` não existir, o notebook baixa do FTP do DataSUS
  (2022–2023 na carga inicial; **2024 só na avaliação única do teste**).
- **Variáveis de ambiente:** `DENGUE_BASE`, `DENGUE_DATA_DIR`, `DENGUE_OUT_DIR`.
- **Saídas** (só agregados): `reports/modelo_risco_dengue/{tabelas,figuras,artefatos}`, `resultados.json`
  e `LACRE_TESTE_2024.json`.
- **Regerar o notebook** depois de editar um módulo: `python notebooks/build_modelo_risco_dengue.py`.
- **Testes:** `PYTHONPATH=src:tests pytest` (os testes dos módulos novos pulam sozinhos se scikit-learn
  ou statsmodels não estiverem instalados).

## Dependências além do `pyproject.toml`

`scikit-learn`, `statsmodels`, `scipy`, `patsy`, `matplotlib`, `joblib` (obrigatórias) e `xgboost`, `shap`
(opcionais: sem eles há HistGradientBoosting e importância por permutação). O `pyproject.toml` **não foi
alterado nas dependências** (decisão reservada ao Programador, tarefa T-2.0); a primeira célula do notebook
instala o que faltar com `pip`.

## Regras do projeto que o notebook faz cumprir

- **R1/R2:** 2024 só é lido na avaliação única; `assert_dev_only` bloqueia 2024 em treino/tuning/calibração;
  o lacre em disco falha uma segunda execução.
- **R3:** sem correção de desbalanceamento (a célula da seção 12 confere as grades).
- **R4:** `X` só com a lista fechada (`assert_features_permitidas`).
- **R5/R6:** pré-processamento com estado em `Pipeline`; early stopping só na validação interna do treino.
- **R7:** só agregados saem; células com < 10 eventos são suprimidas; `salvar_tabela` recusa tabelas grandes.
- **R10:** o ranking de comorbidades vem só do OR do E1.
