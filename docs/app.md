# API e frontend do protótipo

Protótipo de pesquisa. Não é diagnóstico, não orienta conduta e não substitui avaliação médica.
Estado honesto: a **camada de produto está implementada e testada com um modelo sintético**. O M1
real (`m1-perfil-2.0.0`) tem desempenho fraco e só três variáveis; o E1 ainda não existe.

## Estrutura

| Caminho | Papel |
|---|---|
| `src/dengue_sinan/servico/` | **Núcleo de serviço (único):** carga do artefato com conferência de hashes e pino opcional, validação, adaptador do contrato da especificação, relatório e "E1 indisponível" |
| `src/app/config.py` | Opções da camada HTTP/frontend (`DENGUE_APP_*`); o resto vem de `ConfigServico` |
| `src/app/servico.py` | Camada fina: cria o serviço da configuração e informa a versão do sistema |
| `src/app/api/` | Camada HTTP (FastAPI): rotas, esquemas, erros, logs |
| `src/app/cliente.py` | Cliente HTTP usado pelo frontend |
| `src/app/frontend/app.py` | Interface Streamlit (pt-BR) |
| `tests/app/` | Testes (modelo sintético; nenhum dado do projeto) |

A validação dos registros é feita **uma vez só**, no contrato do pipeline
(`dengue_sinan.pipeline.contrato`). A API só confere estrutura e tipos.

## Como rodar localmente

Pré-requisito: ambiente do projeto (Python 3.13) mais as dependências de `requirements-app.txt`.

    export PYTHONPATH=src
    python -m app.api                                   # API em http://127.0.0.1:8000
    python -m app.frontend                              # frontend em http://127.0.0.1:8501

Documentação interativa da API: http://127.0.0.1:8000/docs

Exemplo:

    curl -s -X POST http://127.0.0.1:8000/prever -H 'content-type: application/json' \
      -d '{"registros":[{"idade_anos":34,"sexo":"F","gestante":0}]}'

## Rotas

| Rota | O que faz |
|---|---|
| `GET /saude` | 200 com modelo carregado; 503 se o modelo não carregou |
| `GET /versao` | Versão do sistema, dados do modelo, métricas de desenvolvimento e estado do E1 |
| `GET /relatorio` | Relatório de desempenho e limitações, só com números gravados no artefato |
| `GET /contrato` | Contrato de entrada do modelo (campos, tipos, limites) |
| `POST /prever` | Probabilidades para 1 a N perfis (N = `DENGUE_LIMITE_REGISTROS`, padrão 1000). Registro com valor inválido volta com `status="invalido"` e o motivo; valores implausíveis (ex.: idade 3 e gestante) voltam em `avisos`, sem bloquear; campo desconhecido ou tipo errado dá 422; corpo maior que o limite dá 413. Nenhum limiar foi escolhido: a resposta não classifica ninguém |
| `POST /e1/perfil` | 501 enquanto o E1 não existir (ponto de extensão: `Servico.prever_e1`) |

## Configuração

| Variável | Padrão |
|---|---|
| `DENGUE_ARTEFATOS`, `DENGUE_M1`, `DENGUE_E1` | pasta e identificadores (também em `config/app.json`) |
| `DENGUE_LIMITE_REGISTROS` | `1000` |
| `DENGUE_APP_MODELO_SHA256` | vazio. Pino opcional do `modelo.joblib` (64 hex), vindo de fora da pasta do artefato |
| `DENGUE_APP_API_URL` | `http://127.0.0.1:8000` |
| `DENGUE_APP_MAX_CORPO_BYTES` | `262144` |
| `DENGUE_APP_LOG_NIVEL` | `INFO` |
| `DENGUE_APP_TIMEOUT_S` | `5` |

## Segurança e privacidade

- O artefato só carrega se os hashes de `metadados.json` conferirem; a pasta da v1
  (`reports/modelo_risco_dengue`) é recusada. Os hashes ficam na mesma pasta do modelo e só
  detectam corrupção; quem controla a pasta pode trocar tudo. O pino `DENGUE_APP_MODELO_SHA256`
  detecta a troca. Falha ao carregar deixa a API em modo degradado (503), nunca derruba a partida. `joblib` executa código ao carregar: só use
  artefatos de origem confiável.
- Os logs trazem método, rota, status, tempo e contagens. **Nenhum dado de paciente** é logado.
- O frontend não grava nada; o histórico mostrado vive só na sessão do navegador.

## Testes

    PYTHONPATH=src pytest tests/app -q

Cobrem configuração, serviço (hash adulterado, pino, pasta histórica, saída fora de [0, 1]),
cliente HTTP, API (413, 422, 501, 503, 500, OpenAPI, X-Request-ID, logs sem dados), interface (AppTest), fluxo ponta a ponta com
servidor `uvicorn` real e tempo (< 1 s para 20 perfis). O teste com o artefato real é opcional:

    DENGUE_APP_TESTAR_REAL=1 PYTHONPATH=src pytest tests/app/test_artefato_real.py

## Decisões técnicas

- FastAPI + pydantic estrito: documentação OpenAPI automática e tipos que não são convertidos
  em silêncio (texto não vira número).
- Sem Dockerfile: o projeto fixa Python 3.13 com `uv`, a demo roda local e não há publicação;
  um contêiner não traz ganho agora.
- O frontend fala só com a API (sem importar o modelo), então API e interface evoluem separados.

## Limites desta entrega

- Testado só com **modelo sintético**; o M1 real não foi carregado aqui (teste opcional acima).
- O E1 está explicitamente indisponível; a tela do E1 será feita quando existir um contrato.
- Dependências novas ainda **não** estão no `pyproject.toml` (ver `requirements-app.txt` e `requirements-test.txt`; o Streamlit exige `pandas<3`).
- `app` não está no wheel do projeto (`packages = ["src/dengue_sinan"]`): rode com `PYTHONPATH=src`.
