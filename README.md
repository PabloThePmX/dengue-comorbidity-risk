# Dengue e Comorbidades — SINAN/DataSUS

Projeto acadêmico para estudar associações entre comorbidades e desfechos graves em dengue,
além de avaliar modelos de risco conforme a especificação em [specs.md](specs.md).

## Ambiente local

Requer Python 3.13 e `uv`:

```powershell
uv sync
uv run pytest -q
uv run ruff check .
```

O arquivo `config/base.yaml` guarda os parâmetros e caminhos. Os microdados não são incluídos no
repositório. Para execução no Colab, abra o [notebook passo a passo](notebooks/dengue_colab.ipynb)
ou consulte [notebooks/colab_setup.md](notebooks/colab_setup.md).

## Demo

Depois de gerar os artefatos congelados `models/e1_final.joblib` e `models/m1_final.joblib`,
execute:

```powershell
uv run streamlit run app/streamlit_app.py
```

O diretório pode ser sobrescrito com `DENGUE_MODELS_DIR`. A demo carrega apenas os artefatos,
não lê microdados nem persiste as entradas. O app exibe aviso de uso acadêmico nas duas abas.
Publicação pública não foi feita.

O retreino final fica em `dengue_sinan.training`: `train_final_e1`, `train_final_b1` e
`train_final_m1` recebem os dados de desenvolvimento já carregados, a proveniência e as decisões de
calibração/perfis definidas pelo projeto. A rotina de avaliação de 2024 permanece isolada em
`dengue_sinan.evaluate.evaluate_test_once` e só deve ser executada após congelar os artefatos.

Para executar as etapas de M1 no Colab ou localmente, com os dados de desenvolvimento disponíveis
no caminho configurado:

```powershell
uv run python scripts/build_models.py --stage tune
uv run python scripts/build_models.py --stage select
uv run python scripts/build_models.py --stage train
```

`tune` roda os baselines e a busca dos cinco candidatos implementados; TabFM permanece bloqueado
até a verificação de licença/limites prevista em [TODO.md](TODO.md). `select` calibra OOF,
escolhe o modelo conforme a regra da especificação e escreve a comparação em `reports/m1/`.
`train` retreina em 2022–23 e congela M1 e B1. Para E1, os perfis de referência são decisões
explícitas: informe JSONs com o perfil RERI/AP e as idades de cada faixa, além da decisão de
gestação:

```powershell
uv run python scripts/build_models.py --stage e1 --reference-profile <arquivo.json> --age-references <arquivo.json> --gestante <sim|nao>
```

Essas etapas carregam apenas `anos_dev`. A avaliação de 2024 não é chamada pelo script e continua
sujeita ao lacre de execução única.

## Organização

- `src/dengue_sinan/`: download, validação, transformação, métricas e modelagem.
- `scripts/build_models.py`: etapas de tuning, seleção, retreino final e geração do E1.
- `app/streamlit_app.py`: demo local baseada nos artefatos finais, sem acesso aos microdados.
- `tests/`: testes unitários e de integração em dados sintéticos.
- `profiling/`: documentação do profiling que antecede os Marcos 2–7.
- `reports/`, `data/`, `mlruns/` e artefatos de modelo: resultados locais/Drive; microdados e
  predições linha a linha não devem ser versionados.

O conjunto de 2024 é o teste congelado. Somente a rotina de avaliação final pode carregá-lo, uma
única vez, conforme as salvaguardas de [TODO.md](TODO.md).
