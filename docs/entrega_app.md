# produto_final: API + frontend + núcleo de serviço (unificado)

Só arquivos NOVOS. Copiar por cima da raiz do repositório não sobrescreve nada existente.
Não altera `pyproject.toml`, `uv.lock`, manifestos nem dados.

## Estado
- Testes no sandbox (modelo sintético): `tests/app` + `tests/test_servico.py` = 89 passam, 1 pulado (reconferido pela Peach)
  (teste opcional com o artefato real, `DENGUE_APP_TESTAR_REAL=1`). Suíte completa sem
  `tests/agentes`: relato do Mario: 274 passam e 4 falham por falta de `.gitignore`/arquivos no sandbox (a Peach NÃO reproduziu estes números).
- ruff check e format limpos.
- O M1 real nunca foi carregado aqui. O E1 está indisponível (sem artefato e sem variáveis autorizadas).

## O que mudou frente às entregas anteriores
- Camada de serviço única (`dengue_sinan.servico`); `app.servico` só delega.
- Carga degradada (503) em qualquer falha, pasta histórica recusada, pino SHA-256 opcional.
- API: avisos de plausibilidade, `/relatorio`, 413 por tamanho de corpo, X-Request-ID validado.
- Frontend: bloqueia masculino+gestante, mostra avisos, desfecho e forma de avaliação (ou "não informado"),
  sobe só em 127.0.0.1 e sem telemetria (`python -m app.frontend`, `.streamlit/config.toml`).

## Depende de autorização (pedido único)
`pyproject.toml`: dependências de `requirements-app.txt` (com `pandas<3`) e `requirements-test.txt`.
Execução: `PYTHONPATH=src python -m app.api` e `python -m app.frontend` (veja `docs/app.md`).


## Limitações conhecidas (BAIXO, não bloqueiam o protótipo local)
- F1: a listagem de artefatos ordena por nome antes de versão; hoje `config/app.json` fixa o M1, então não afeta.
- F2: a introdução do frontend ainda fixa 'SINAN 2022 e 2023'.
- F3: o teste de 1 s usa o melhor de 5 medidas.
- F4: o pino SHA-256 é conferido antes de abrir o arquivo (janela curta).
- F5: `gestante="ignorado"` vira 0 sem aviso.
