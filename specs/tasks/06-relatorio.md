# Tarefas — Fase 7 — Polimento: relatório (Marco 7)

> **Leia antes:** [00-como-usar.md](00-como-usar.md) — regras (§0, R1–R10), referência rápida (§1),
> dependências (§7b) e os registros §9 e §10, que ficam **lá**, não neste arquivo. Os §0, §1, §7b,
> §9 e §10 citados abaixo são daquele arquivo.

---

## 7. Fase 7 — Polimento: relatório TRIPOD+AI (Marco 7)

Spec: FR-20, FR-21, D-22, D-28.

### [ ] T-7.1 — Rascunho do relatório

- Estrutura pelo checklist TRIPOD+AI. Seções mínimas: título/resumo; introdução (com trabalhos
  relacionados e diferencial, §3.2); métodos (fonte, população, alvo, preditores, split, modelos,
  métricas); resultados (fluxograma, descritiva, E1, M1, teste, subgrupos); discussão (limitações:
  duplicatas, ES/`TP_SISTEMA`, leucopenia "não feito", sem doenças respiratórias, idade por
  `ANO_NASC`, drift 2024); conclusão.
- Parágrafo obrigatório: por que o alvo difere do pré-projeto (D-22, spec §3.6).
- Ética (NFR-04): dados públicos e **desidentificados** (não "anonimizados"); dispensa pela CNS
  510/2016, art. 1º, parágrafo único, inciso II.
- Explicar F2 vs F0.5 (D-33) e por que não há correção de desbalanceamento (D-38).

### [ ] T-7.2 — Apêndices

- A: registro de decisões (copiar §3.16 do spec), destacando D-22 a D-25.
- B: fluxograma de exclusão e resultados do profiling.
- C: "passos seguidos" — cronologia exportada do MLflow (config, hash dos dados, métricas por run).
- D: revisão do profissional de saúde (FR-21), se houver. Sugestões que mudariam o modelo viram
  limitação, não retreino.

### [ ] T-7.3 — Checklist final

- Rodar o [checklists/requirements.md](../checklists/requirements.md) e o TRIPOD+AI; listar o que falhou.
- Confirmar NFR-02: rodar de novo do zero e obter as métricas de teste com as mesmas 3 casas
  decimais — **sem reavaliar o teste**: a reprodução usa o mesmo pipeline e compara com
  `reports/teste/metricas.md` numa cópia isolada, e o resultado é anotado, não usado para mudar nada.
  🛑 Confirme com o Programador como fazer essa verificação sem violar R2.
