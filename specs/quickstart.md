# Quickstart — como rodar e validar

> Único guia de execução (D-60): as tarefas apontam para cá em vez de repetir os passos. Passos
> marcados "(após T-x)" só funcionam depois da tarefa indicada. Ambiente e orçamento:
> [plan › Ambiente de execução e orçamento](plan.md#ambiente-de-execução-e-orçamento).

---

## Local

Desenvolvimento e testes. Pré-requisito: [`uv`](https://docs.astral.sh/uv/). Ele instala o
Python 3.13 do projeto (`requires-python >=3.13,<3.14`, limite do `pyreaddbc`); o `python` do
sistema (3.14) não serve.

```bash
uv sync
uv run pytest -q
uv run ruff check .
```

- Se `uv` não estiver no PATH: `python -m uv ...` ou o caminho completo
  `%APPDATA%\Python\Python314\Scripts\uv.exe`.
- Se `uv run pytest` falhar com "trampoline failed to canonicalize script path":
  `uv run python -m pytest -q` (o launcher do `.venv` ficou com um caminho antigo;
  `uv sync --reinstall-package pytest` regenera).
- Pacotes só entram com `uv add`, depois do "ok" do Programador; nunca `pip install` direto.
- Nenhum microdado no repositório (NFR-03): `data/` e `mlruns/` estão no `.gitignore`.

## Google Colab

Dados, treino e avaliação.

1. Montar o Google Drive. Pasta do projeto: `MyDrive/dengue-comorbidity-risk/`.
2. `git clone` do repositório e `pip install -e .` (ou `uv sync`). O código da tarefa precisa estar
   commitado e no GitHub antes, porque o Colab clona o repositório.
3. Conferir a GPU (Colab Pro, ou gratuito se houver):
   `nvidia-smi` e `python -c "import torch; print(torch.__version__, torch.cuda.is_available())"`.
   Se der `False` numa VM com GPU, **🛑 pare e pergunte**: o lock usa torch com CUDA 13 (ver o
   `[VERIFY]` em [plan › Ambiente](plan.md#ambiente-de-execução-e-orçamento)).
4. Apontar `caminhos.dados` e `caminhos.mlruns` de `config/base.yaml` para a pasta do Drive
   (após T-2.0).
5. Rodar os notebooks, que só chamam funções de `src/` (NFR-05):
   - dados e profiling: `profiling/01_profiling.ipynb`;
   - modelos M1 em sessão única: `notebooks/04_modelos.ipynb` (após T-4.3b, D-53).
6. Se a tarefa gera relatório de verificação (D-56), baixe o JSON (`reports/verificacao/T-x.y.json`;
   na sessão dos modelos, só `sessao-m1.json`, D-57) para a mesma pasta no repositório local e faça
   commit. O notebook também grava uma cópia no Drive. Não digite nenhum número: o agente lê o
   arquivo.
7. Ao terminar, desconectar o ambiente, para não gastar unidades com GPU ociosa.

## Dados

- Download e conversão de um ano: `dengue_sinan.download.fetch_year(ano, data_dir)` (FR-01). Grava
  `data/parquet/dengue_{ano}.parquet` (todas as colunas como texto) e atualiza
  `data/manifest.json` com hash do `.dbc`, hash do Parquet e data de revisão no FTP.
- Se o Parquet do ano já existir, ele é reutilizado.

## Validação rápida

Depois de carregar a população (após T-2.1), as contagens devem bater com o
[data-model › Tamanho e prevalência](data-model.md#tamanho-e-prevalência) e com os
[eventos por região](data-model.md#eventos-por-região-e-subgrupo). No Colab, quem confere é o
relatório de verificação, com os valores de `config/esperado.yaml` (após T-2.0).

**2024 não é carregado antes da T-5.1** (R1). Os números de 2024 vêm do profiling e servem só para
conferir a T-5.1.
