"""Camada de produto do dengue-comorbidity-risk: serviço, API HTTP e frontend Streamlit.

Protótipo de pesquisa. Não é diagnóstico e não substitui avaliação médica.
A lógica de negócio fica em `app.servico`; a API (`app.api`) e o frontend (`app.frontend`)
só a chamam. A validação dos registros é do contrato do pipeline (`dengue_sinan.pipeline`).
"""

VERSAO_APP = "0.1.0"
