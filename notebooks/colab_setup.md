# Execução no Google Colab

Use o notebook passo a passo em [dengue_colab.ipynb](dengue_colab.ipynb). Ele monta o Drive,
instala o Python 3.13.12 exigido pelo projeto, prepara somente os dados de desenvolvimento
(2022–2023), persiste Optuna/relatórios/modelos no Drive e oferece células separadas para retomar
cada candidato.

Antes de abrir o notebook no Colab, envie para o GitHub o código atualizado, incluindo
`scripts/build_models.py`; o notebook clona o repositório publicado. Selecione runtime GPU antes de
executar a busca MLP. As buscas podem exceder a duração de uma sessão, então execute uma família por
vez. A configuração mantém todos os dados e resultados fora do checkout e do Git.

O notebook não baixa nem avalia 2024. Esse ano é o teste congelado e deve ser usado apenas uma vez,
pela rotina `dengue_sinan.evaluate.evaluate_test_once`, após o congelamento dos modelos.
