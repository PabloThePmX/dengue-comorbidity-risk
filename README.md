# dengue-comorbidity-risk

Projeto acadêmico de predição da gravidade de dengue (dengue grave ou óbito pelo agravo) a partir
de comorbidades e sintomas iniciais, com dados abertos do SINAN (DataSUS). A especificação, as
decisões e as tarefas estão em `specs/`.

## Demo (Streamlit)

> **Projeto acadêmico. Não é ferramenta clínica nem substitui avaliação médica.**

Duas abas: **Perfil** (modelo explicativo E1: o risco de quem tem certas condições) e **Triagem**
(modelo preditivo M1: o risco de um paciente, com sintomas, agora).

**Instalar e rodar**

```
uv sync
uv run streamlit run src/app/streamlit_app.py
```

**Onde ficam os artefatos**

| Variável | Conteúdo | Padrão |
|---|---|---|
| `DENGUE_MODELOS` | pasta com `e1/` e `m1_final/` (ou `m1_demo/`) | `models/` (do `config/base.yaml`) |
| `DENGUE_RELATORIOS` | pasta com `teste/metricas.json`, que alimenta o painel "O que o teste de 2024 mostrou" | `reports/` |

- `models/e1` está no git.
- `models/m1_final` **não está no git** (R7, D-85). Para obtê-lo, reproduza a T-4.10 ou pegue-o no
  Drive do projeto. O SHA-256 do payload (`payload/m1.joblib`) é
  `394c0f19e9384dc41e4e13b872a29ac8b8fb9de1d0f0413ba5c72321d0e9901a`. Sem ele, só a aba Perfil
  funciona, e a aba Triagem mostra uma mensagem.
- Sem `reports/teste/metricas.json`, o painel do teste simplesmente não aparece.
- O XGBoost deve ser o 3.4.1 do `uv.lock`. O `m1_final` foi gravado com o booster em GPU e, sem
  GPU, a leitura completa falha; o app tem um contorno que lê só as árvores. A paridade com a
  carga normal foi provada por hash do dump das árvores e por predições
  (`reports/verificacao/paridade-m1-demo.json`).

**Privacidade:** a demo não grava, não registra em log nem envia as entradas, não tem analytics e
não embarca microdados.

**Resultado do teste de 2024 (sem eufemismo):** o critério SC-02 (recall do M1 igual ou maior que o
da regra B2, com precisão maior) **não foi atendido**: o recall do M1 foi 0,6528 contra 0,6601 da regra (diferença de −0,0072, IC de
−0,0151 a 0,0005, que mal inclui zero), com precisão maior (0,00975 contra 0,00529) e 46% menos alertas.
O modelo também **subestimou o risco em cerca de 30%** (o observado foi maior que o previsto). O sinal "alto risco" tem baixa precisão: cerca de 99%
dos casos marcados não evoluíram para grave ou óbito. Detalhes em `reports/teste/`.
