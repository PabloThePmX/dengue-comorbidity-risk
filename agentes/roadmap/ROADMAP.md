# Roadmap principal — Dengue Comorbidity Risk

> **Um único roadmap.** As etapas abaixo são a referência. As tarefas `T-x.y` de `specs/tasks/` são o detalhe técnico ligado a cada etapa, não um segundo roadmap (DA-002).
> Este arquivo não conclui nada por conta própria: o estado muda com o parecer da Peach e a sua autorização.
> Idioma: pt-BR. Atualizado em 2026-11-18.

## 1. Etapas

| Etapa | Conteúdo | Estado | Relatório |
|---|---|---|---|
| 1 (1B a 1E) | Auditoria exploratória J1 a J16 (2022–2023) | Entregue; pendências em `reports/etapa1/README.md` | `reports/etapa1/relatorio_etapa1e.md` |
| 2 | Pipeline de treino e inferência; artefato `m1-perfil-2.0.0` | Entregue | `reports/etapa2/relatorio_etapa2.md` |
| 2.1 | Dependências (`pyproject.toml`, `uv.lock`) e `.gitignore` | Entregue | `reports/etapa2/relatorio_etapa2_1.md` |
| 3.1 | Auditoria metodológica e planejamento | Entregue | `reports/etapa3/relatorio_etapa3_1.md` |
| 3.2 | Infraestrutura de avaliação: OOF, baselines B0/B1/B1-idade, métricas, bootstrap por município | **Entregue — EM ANÁLISE. Sem aprovação técnica; aguarda auditoria independente da Peach (DA-013)** | `reports/etapa3/relatorio_etapa3_2.md` |
| 3.3 | Calibração aninhada e comparação de métodos | Não autorizada; depende de DH-05 | — |
| 3.4 | Estabilidade e validação temporal interna | Não autorizada | — |
| 3.5 | Pontos de operação em OOF, sem escolher limiar | Não autorizada | — |
| 3.6 | Decisão sobre o modelo definitivo (nunca sobrescrever o atual) | Não autorizada | — |
| 3.7 | Documentação, TRIPOD+AI e integridade | Não autorizada | — |
| 4 em diante | Não definidas | — | — |

Fonte da sequência 3.2 a 3.7: `reports/etapa3/relatorio_etapa3_1.md`, seção 9.

## 2. Mapa entre etapas e tarefas T-x.y

Colunas: **Vínculo** é `proposto` (confiança alta ou média, aguarda sua conferência) ou `PENDENTE` (confiança baixa; **não** é correspondência confirmada).

| Etapa | T-x.y | Confiança | Vínculo |
|---|---|---|---|
| 1 | Marco 1 (profiling; concluído em 2026-11-03) | Alta | proposto |
| 2 | T-2.0, T-2.1, T-2.2, T-2.3 | Média | proposto |
| 2 | T-4.10 (congelamento; só a parte já feita) | Média | proposto |
| 2.1 | T-2.0 | Alta | proposto |
| 3.1 | — (planejamento, sem T-x.y) | Alta | proposto |
| 3.2 | T-2.4, T-2.8, T-4.2 | Média | proposto |
| 3.3 | T-4.9 (só a parte de calibração) | Média | proposto |
| 3.4 | — | Baixa | **PENDENTE** |
| 3.5 | T-4.9 (limiar), T-5.2 (curva de decisão) | Baixa | **PENDENTE** |
| 3.6 | T-4.10 | Média | proposto |
| 3.7 | T-7.1, T-7.2, T-7.3 | Média | proposto |
| sem etapa | T-3.1 a T-3.6 (E1 explicativo) | Baixa | **PENDENTE** |
| sem etapa | T-6.1 a T-6.4 (demo) | Baixa | **PENDENTE** |
| sem etapa | T-4.0, T-4.1, T-4.3 a T-4.9 (modelos, busca) | Baixa | **PENDENTE** |

### Bloqueadas por decisão humana

| T-x.y | Motivo |
|---|---|
| T-5.1, T-5.2, T-5.3, T-5.4 | **BLOQUEADAS.** 2024 não será usado como teste para novas versões do modelo (D6 e D7 da decisão do usuário). A constituição (R1, R2) previa o teste único em 2024; a divergência fica registrada e **não** se resolve nesta estrutura. |

### Divergências registradas (sem corrigir resultados nem decisões anteriores)

| Item | `specs/tasks` | Etapa 3.2 |
|---|---|---|
| Baselines | T-2.8: B0, B1 e B2 | B0, B1 e B1-idade (D5 da Etapa 3.1) |

### Observações

- Nenhuma T-x.y está marcada como concluída em `specs/tasks/`, mas parte do código já existe. O "Pronto quando" de cada uma **nunca foi conferido**. O mapa não prova conclusão.
- O Yoshi **não** atualiza o §9 de `specs/tasks/00-como-usar.md` a menos que a ficha da tarefa autorize.
- Nada nesta tabela autoriza o início de etapa. Só `estado/autorizacao.json`, gravado por você, faz isso.
