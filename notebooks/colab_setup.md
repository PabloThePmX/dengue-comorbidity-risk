# Execução no Google Colab

1. Monte o Google Drive:

   ```python
   from google.colab import drive
   drive.mount("/content/drive")
   ```

2. Clone o branch publicado que contém `runner.py` e instale as dependências aprovadas:

   ```bash
   !git clone --branch ricardo https://github.com/PabloThePmX/dengue-comorbidity-risk.git
   %cd dengue-comorbidity-risk
   !pip install -e .
   ```

3. Configure os caminhos de dados e saídas para as pastas correspondentes no Drive. O
   diretório de dados esperado é
   `/content/drive/MyDrive/dengue-comorbidity-risk/data`.

4. Importe e chame as funções de `src/dengue_sinan/`. Os notebooks devem orquestrar chamadas e não
   conter lógica de processamento ou modelagem.

5. Ao terminar a sessão, desconecte o ambiente do Colab para não manter recursos de GPU ociosos.

## Notebook de baselines

[`02_baselines_colab.ipynb`](./02_baselines_colab.ipynb) executa B0, B1 e B2 com 2022–2023. Ele
usa apenas Parquets de desenvolvimento, grava métricas agregadas e artefatos OOF no Drive e
prepara/verifica as dobras em `m1/dobras.npz`. Execute-o primeiro.

[`04_modelos.ipynb`](./04_modelos.ipynb) retoma o treino dos modelos M1 no Drive e grava o relatório
`reports/verificacao/sessao-m1.json` e o bundle final em `models/m1_final.joblib`. O runner exige o
relatório `reports/verificacao/T-2.3.json` e usa apenas 2022–2023; 2024 permanece congelado. Não
compartilhe os artefatos OOF nem o diretório `mlruns`: contêm dados por caso. Após a seleção e o
retreino, o bundle calibrado é registrado como `dengue-m1`; o alias
`models:/dengue-m1@melhor-validacao` aponta para a versão final. O SQLite do Model Registry fica em
`mlruns_registry.db`, ao lado de `mlruns/`; o registro não inclui exemplos de entrada com dados de
pacientes.