# Marco 7 — Relatório TRIPOD+AI

> **Leia antes:** [00-como-usar.md](00-como-usar.md) (como executar, Verificação no Colab, Erros
> inesperados). Os registros de execução e de problemas ficam **lá**.

Spec: FR-20, FR-21, D-22, D-28. Critério de saída: [spec › Marcos](../spec.md#marcos). Pode ser
escrito ao longo do projeto; fecha depois dos Marcos 5 e 6.

### [ ] T-7.1 — Relatório e apêndices

Inclui a antiga T-7.2 (D-60).

- Estrutura pelo checklist TRIPOD+AI. Seções mínimas: título/resumo; introdução (com trabalhos
  relacionados e diferencial, [spec › Problema e contexto](../spec.md#trabalhos-relacionados-e-diferencial));
  métodos (fonte, população, alvo, preditores, split, modelos, métricas); resultados (fluxograma,
  descritiva, E1, M1, teste, subgrupos); discussão (limitações: duplicatas, ES/`TP_SISTEMA`,
  leucopenia "não feito", sem doenças respiratórias, idade por `ANO_NASC`, drift 2024); conclusão.
- Parágrafo obrigatório: por que o alvo difere do pré-projeto (D-22,
  [spec › Formulação do problema](../spec.md#formulação-do-problema)).
- Ética (NFR-04): dados públicos e **desidentificados** (não "anonimizados"); dispensa pela CNS
  510/2016, art. 1º, parágrafo único, inciso II.
- Explicar F2 vs F0.5 (D-33) e por que não há correção de desbalanceamento (D-38).
- Apêndices:
  - A: [registro de decisões](../research.md#registro-de-decisões), destacando D-22 a D-25;
  - B: fluxograma de exclusão e resultados do profiling;
  - C: "passos seguidos" — cronologia exportada do MLflow (config, hash dos dados, métricas por run);
  - D: revisão do profissional de saúde (FR-21), se houver. Sugestões que mudariam o modelo viram
    limitação, não retreino.
- **Pronto quando:** todas as seções e os apêndices A–C existem, com números vindos de
  `reports/` (nenhum digitado de memória).

### ~~[ ] T-7.2 — Apêndices~~

Fundida na T-7.1 (D-60).

### [ ] T-7.3 — Checklist final

- Rodar o [checklists/requirements.md](../checklists/requirements.md) e o TRIPOD+AI; listar o que falhou.
- Confirmar NFR-02: rodar de novo do zero e obter as métricas de teste com as mesmas 3 casas
  decimais — **sem reavaliar o teste**: a reprodução usa o mesmo pipeline e compara com
  `reports/teste/metricas.md` numa cópia isolada, e o resultado é anotado, não usado para mudar nada.
  🛑 Confirme com o Programador como fazer essa verificação sem violar R2.
