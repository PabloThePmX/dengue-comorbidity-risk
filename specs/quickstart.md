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
  `%APPDATA%\Python\Python314\Scripts\uv.exe` (instalado com `pip install --user uv` em 2026-11-15;
  o `uv` roda no Python 3.14 do sistema, e o `.venv` do projeto usa o 3.13 que o `uv` instala).
- **`uv sync`, `uv add` e `uv python install` só no terminal do Programador**, nunca por agentes do
  app do Claude (Windows): o app é um pacote da Microsoft Store e redireciona `%APPDATA%` para os
  processos dele. A instalação gravava no caminho virtual, ficava muito lenta e deixou no registro
  uma chave `CPython3.13.18` apontando para um caminho que só o app enxerga (Registro de problemas,
  T-2.0). Os agentes só rodam `.venv\Scripts\python.exe -m pytest -q` e `.venv\Scripts\ruff.exe check .`.
- Se `uv sync` reclamar de interpretador não encontrado: `uv python install 3.13` (com `--force` se
  houver atalho antigo em `%USERPROFILE%\.local\bin`) e apague a chave de registro obsoleta
  (`HKCU:\Software\Python\Astral\CPython<versão>`) que aponta para um Python que não existe.
- Se `uv run pytest` falhar com "trampoline failed to canonicalize script path":
  `uv run python -m pytest -q` (o launcher do `.venv` ficou com um caminho antigo;
  `uv sync --reinstall-package pytest` regenera).
- Pacotes só entram com `uv add`, depois do "ok" do Programador; nunca `pip install` direto.
- Nenhum microdado no repositório (NFR-03): `data/` e `mlruns/` estão no `.gitignore`.

## Google Colab

Marco 4 (modelos) e Marco 5 (teste); os Marcos 2 e 3 rodam no PC local (D-66).

1. Montar o Google Drive. Pasta do projeto: `MyDrive/dengue-comorbidity-risk/`.
2. `git clone` do repositório e `pip install -e .` (ou `uv sync`). O código da tarefa precisa estar
   commitado e no GitHub antes; o orquestrador faz o commit e o push (D-66).
3. Conferir a GPU (Colab Pro, ou gratuito se houver):
   `nvidia-smi` e `python -c "import torch; print(torch.__version__, torch.cuda.is_available())"`.
   Se der `False` numa VM com GPU, **🛑 pare e pergunte**: o lock usa torch com CUDA 13 (ver a
   nota em [plan › Ambiente](plan.md#ambiente-de-execução-e-orçamento)).
4. Apontar `caminhos.dados` e `caminhos.mlruns` de `config/base.yaml` para a pasta do Drive
   (após T-2.0).
5. Rodar os notebooks, que só chamam funções de `src/` (NFR-05):
   - dados e profiling: `profiling/01_profiling.ipynb`;
   - modelos M1 em sessão única: `notebooks/04_modelos.ipynb` (após T-4.3b, D-53).
6. Relatório de verificação (D-56): pelo MCP, o agente traz o JSON
   ([Colab pelo MCP](#colab-pelo-mcp)). Sem o MCP, baixe o JSON (`reports/verificacao/T-x.y.json`;
   na sessão dos modelos, só `sessao-m1.json`, D-57) para a mesma pasta no repositório local e faça
   commit. O notebook também grava uma cópia no Drive. Não digite nenhum número.
7. Ao terminar, desconectar o ambiente, para não gastar unidades com GPU ociosa.

## Colab pelo MCP

Caminho padrão das verificações (D-64): o agente cria e executa as células num notebook aberto no
seu navegador, pelo [MCP oficial do Colab](https://github.com/googlecolab/colab-mcp). As ferramentas
só mexem em células; o ambiente e as autorizações continuam com você.

**Instalação (uma vez por máquina):** com o `uv` instalado,
`claude mcp add --scope local colab -- uvx git+https://github.com/googlecolab/colab-mcp`. As
ferramentas aparecem na sessão seguinte do Claude Code.

**O que fica com você:**
1. Estar logado no Google no navegador padrão. Quando o agente chamar
   `open_colab_browser_connection`, abre uma aba do Colab; ela tem 60 s para conectar.
2. Escolher o ambiente em *Ambiente de execução → Alterar o tipo de ambiente de execução*. Para a
   sessão dos modelos: GPU T4 + "RAM alta". **Salve e confira:** no teste de 2026-11-15, a RAM alta
   só foi aplicada na segunda vez. O agente confere GPU e RAM por código antes de rodar; a troca
   reinicia o ambiente, mas não derruba a conexão do MCP.
3. Autorizar o acesso ao Drive quando o Google pedir.
4. Deixar a aba aberta até o agente terminar, e desconectar o ambiente no fim.

O commit e o push antes de cada execução são feitos pelo orquestrador, com mensagem de uma linha e
sem co-autoria (D-66).

**Comportamento observado (2026-11-15):** `run_code_cell` só volta quando a célula termina
(testado até 2 min); um processo em segundo plano volta na hora e pode ser acompanhado por células
curtas; reiniciar a sessão mata o processo, mas o que já estava no Drive fica; o Drive pode falhar
ao criar um arquivo na primeira tentativa.

## Dados

- Download e conversão de um ano: `dengue_sinan.download.fetch_year(ano, data_dir)` (FR-01). Grava
  `data/parquet/dengue_{ano}.parquet` (todas as colunas como texto) e atualiza
  `data/manifest.json` com hash do `.dbc`, hash do Parquet e data de revisão no FTP.
- Se o Parquet do ano já existir, ele é reutilizado.
- **No PC local, baixe só 2022 e 2023** (D-66), em `data/` (fora do git). 2024 fica só no Drive e
  só é lido na T-5.1 (R1).

## Validação rápida

Depois de carregar a população (após T-2.1), as contagens devem bater com o
[data-model › Tamanho e prevalência](data-model.md#tamanho-e-prevalência) e com os
[eventos por região](data-model.md#eventos-por-região-e-subgrupo). Quem confere é o relatório de
verificação, com os valores de `config/esperado.yaml` (após T-2.0).

**2024 não é carregado antes da T-5.1** (R1). Os números de 2024 vêm do profiling e servem só para
conferir a T-5.1.
