# Objetivo do projeto

> Ponto de entrada da documentação. O objetivo fica **só aqui** (D-59); os outros arquivos apontam
> para cá. Mudar o objetivo exige uma entrada no
> [research › Registro de decisões](research.md#registro-de-decisões).
> Todos os artefatos estão em pt-BR (entregável acadêmico).

---

## Objetivo geral

Estimar, para um caso confirmado de dengue no Brasil, a probabilidade de evoluir para **dengue
grave ou óbito pelo agravo**, usando os dados do SINAN (DataSUS) de 2022–2024.

- **Foco principal: explicar** quais comorbidades e combinações (hipertensão, diabetes, doença
  renal etc.) estão associadas a maior risco, ajustando por idade e sexo (D-01).
- **Foco secundário: prever** esse risco no primeiro atendimento, para apoiar médicos na triagem e
  analistas de vigilância.
- O resultado é comparado com a regra de estratificação de risco já usada pelo Ministério da
  Saúde, para mostrar se o ML acrescenta algo.

## Objetivos específicos

1. Quantificar a associação entre cada comorbidade da ficha (e pares de comorbidades) e o desfecho
   grave ou óbito, com IC 95%, ajustada por idade e sexo (US1; FR-05, FR-19).
2. Produzir uma **tabela de perfis**: risco estimado para pacientes-tipo (ex.: sem comorbidades, só
   hipertensão, diabetes + renal, 3+ comorbidades), por faixa etária (US1; FR-06).
3. Treinar e comparar modelos preditivos para o momento do primeiro atendimento (US2; FR-07).
4. Entregar o que o professor exige (D-26): os modelos serializados (E1 e M1), uma demo Streamlit com duas abas, executada localmente por ora e publicável depois (US3; FR-11; D-94) e um relatório TRIPOD+AI (FR-20), apoiados por um pipeline reprodutível.

## Mapa dos artefatos

Único mapa da documentação (D-60). Os arquivos seguem as convenções do GitHub Spec Kit (D-55).

| Arquivo | Responde | Seções principais |
|---|---|---|
| [constitution.md](constitution.md) | O que nunca pode ser quebrado | Princípios P1–P10, regras R1–R10, decisões reservadas ao Programador, governança |
| [spec.md](spec.md) | **O quê** e **por quê** | Problema, cenários US1–US3, requisitos FR/NFR, critérios de sucesso SC, formulação, split e vazamento, baselines, avaliação, riscos, marcos |
| [plan.md](plan.md) | **Como** | Arquitetura do código, ambiente e orçamento, features e pré-processamento, modelagem, reprodutibilidade |
| [data-model.md](data-model.md) | Quais dados | Entidades, dados (fonte, tamanhos, codificação, qualidade), dicionário de features |
| [contracts/interfaces.md](contracts/interfaces.md) | Formatos de entrada e saída | Entrada de casos, tabela de perfis, demo, relatórios de verificação |
| [research.md](research.md) | Por que cada escolha | Literatura, evidências e o Registro de decisões (D-01 em diante) |
| [quickstart.md](quickstart.md) | Como rodar | Ambiente local, Colab, validação rápida |
| [tasks/00-como-usar.md](tasks/00-como-usar.md) | O que fazer agora | Regras de execução, ordem dos marcos e registros; uma tarefa-arquivo por marco (`02` a `07`) |
| [checklists/requirements.md](checklists/requirements.md) | O spec está pronto? | Checklist de qualidade |

**Como ler as referências.** Seções são citadas pelo nome, com link:
[spec › Split e vazamento](spec.md#split-e-vazamento). Os IDs (US, FR, NFR, SC, D, Q, P, R, T)
valem em todos os arquivos e nunca são renumerados; item removido fica ~~riscado~~.

**Perguntas frequentes**

| Pergunta | Onde |
|---|---|
| Por que o problema importa e por que ML (ou não) | [spec › Problema e contexto](spec.md#problema-e-contexto) |
| O que fica fora do escopo | [spec › Não-objetivos](spec.md#não-objetivos) |
| Como saber se deu certo | [spec › Critérios de sucesso](spec.md#critérios-de-sucesso) |
| Em que ponto o projeto está | [spec › Marcos](spec.md#marcos) e [tasks › Registro de execução](tasks/00-como-usar.md#registro-de-execução) |
