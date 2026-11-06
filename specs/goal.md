# Objetivo do projeto

> Fonte única do objetivo geral (D-59). Todos os arquivos de `specs/` apontam para cá em vez de
> repetir o objetivo. Se ele mudar, muda só aqui, com uma entrada no Registro de decisões
> ([research.md](research.md), §3.16).
> Idioma: pt-BR (entregável acadêmico).

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
4. Entregar o que o professor exige (D-26): os modelos serializados (E1 e M1), uma demo pública com
   duas abas (US3; FR-11) e um relatório TRIPOD+AI (FR-20), apoiados por um pipeline reprodutível.

## Onde cada parte é detalhada

| Pergunta | Onde |
|---|---|
| Por que o problema importa e por que ML (ou não) | [spec.md](spec.md), §3.2 |
| O que fica fora do escopo | [spec.md](spec.md), §3.3 (não-objetivos) |
| Como saber se deu certo | [spec.md](spec.md), Critérios de sucesso (SC-01 a SC-08) |
| Princípios que não podem ser quebrados | [constitution.md](constitution.md) |
| Como é construído | [plan.md](plan.md) |
| O que fazer agora | [tasks/00-como-usar.md](tasks/00-como-usar.md) |
