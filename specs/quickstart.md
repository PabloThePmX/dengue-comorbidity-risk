# Quickstart — como rodar e validar

> Guia de execução no padrão Spec Kit (D-55). Passos marcados "(após T-x)" só funcionam depois da
> tarefa indicada em [tasks/](tasks/00-como-usar.md). Ambiente e orçamento: [plan.md](plan.md), §B.
> Idioma: pt-BR (entregável acadêmico).

---

## 1. Local (desenvolvimento e testes)

Pré-requisito: [`uv`](https://docs.astral.sh/uv/). Ele instala o Python 3.13 do projeto
(`requires-python >=3.13,<3.14`, limite do `pyreaddbc`).

```bash
uv sync
uv run pytest -q
uv run ruff check .
```

- Se `uv` não estiver no PATH: `python -m uv ...`.
- Se `uv run pytest` falhar com "trampoline failed to canonicalize script path":
  `uv run python -m pytest -q` (o launcher do `.venv` ficou com um caminho antigo;
  `uv sync --reinstall-package pytest` regenera).
- Nenhum microdado no repositório (NFR-03): `data/` e `mlruns/` estão no `.gitignore`.

## 2. Google Colab (dados, treino e avaliação)

1. Montar o Google Drive. Pasta do projeto: `MyDrive/dengue-comorbidity-risk/`.
2. `git clone -b feat/lora https://github.com/PabloThePmX/dengue-comorbidity-risk.git` e `pip install -e .` (a 1ª célula de cada notebook já faz o clone, checkout da branch `feat/lora`, instalação e montagem do Drive automaticamente via `prepare_colab_project`).
3. Conferir a GPU (Colab Pro, ou gratuito se houver):
   `nvidia-smi` e `python -c "import torch; print(torch.__version__, torch.cuda.is_available())"`.
   Se der `False` numa VM com GPU, ver o `[VERIFY]` do torch com CUDA 13 em [plan.md](plan.md), §B.
4. Apontar `caminhos.dados` e `caminhos.mlruns` de `config/base.yaml` para a pasta do Drive
   (após T-2.0 — feito automaticamente por `dengue_sinan.colab.prepare_colab_project`).
5. Rodar os notebooks, que só chamam funções de `src/` (NFR-05):
   - **Pipeline unificado (Fases 2, 3 e 4 em sequência):** `notebooks/00_pipeline_colab.ipynb` ([Abrir no Colab](https://colab.research.google.com/github/PabloThePmX/dengue-comorbidity-risk/blob/feat/lora/notebooks/00_pipeline_colab.ipynb));
   - dados e profiling: `profiling/01_profiling.ipynb` (Marco 1, concluído);
   - Fase 2 (Fundação): `notebooks/02_fundacao.ipynb` ([Abrir no Colab](https://colab.research.google.com/github/PabloThePmX/dengue-comorbidity-risk/blob/feat/lora/notebooks/02_fundacao.ipynb));
   - Fase 3 (Perfil E1): `notebooks/03_perfil_e1.ipynb` ([Abrir no Colab](https://colab.research.google.com/github/PabloThePmX/dengue-comorbidity-risk/blob/feat/lora/notebooks/03_perfil_e1.ipynb));
   - Fase 4 (Modelos M1 em sessão única): `notebooks/04_modelos.ipynb` ([Abrir no Colab](https://colab.research.google.com/github/PabloThePmX/dengue-comorbidity-risk/blob/feat/lora/notebooks/04_modelos.ipynb), após T-4.3b, D-53);
   - Fase 5 (Teste final 2024 — rodar uma única vez): `notebooks/05_teste_final.ipynb` ([Abrir no Colab](https://colab.research.google.com/github/PabloThePmX/dengue-comorbidity-risk/blob/feat/lora/notebooks/05_teste_final.ipynb), R2).
6. Ao final de cada notebook, `sync_and_package_reports(cfg)` sincroniza `reports/verificacao/*.json` no Drive e faz o download automático do `.zip` para você extrair na pasta `reports/` do repositório local. Não digite nenhum número: o agente lê os arquivos JSON.
7. Ao terminar, desconectar o ambiente, para não gastar unidades com GPU ociosa.

## 3. Dados

- Download e conversão de um ano: `dengue_sinan.download.fetch_year(ano, data_dir)` (FR-01). Grava
  `data/parquet/dengue_{ano}.parquet` (todas as colunas como texto) e atualiza
  `data/manifest.json` com hash do `.dbc`, hash do Parquet e data de revisão no FTP.
- Se o Parquet do ano já existir, ele é reutilizado.

## 4. Validação rápida

Depois de carregar a população (após T-2.1), as contagens devem bater com o profiling
([RESULTADOS.md](../profiling/RESULTADOS.md)):

| | 2022 | 2023 | 2024 |
|---|---|---|---|
| População final | 1.148.299 | 1.304.909 | 5.331.745 |
| Eventos (y = 1) | 1.869 | 2.116 | 11.338 |

- Desenvolvimento (2022–23): 2.453.208 casos e 3.985 eventos.
- Eventos por região no desenvolvimento: Centro-Oeste 736, Nordeste 582, Norte 121, Sudeste 1.736,
  Sul 810.
- **2024 não é carregado antes da T-5.1** (constituição, R1). Os números de 2024 acima vêm do
  profiling e servem só para conferir a T-5.1.
