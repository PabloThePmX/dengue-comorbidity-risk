# Regras permanentes

> Não duplicam o projeto. A fonte é `specs/constitution.md` (P1–P10 e R1–R10), `CLAUDE.md` e `specs/tasks/00-como-usar.md`. Em conflito, vale a constituição e o agente **para e avisa** o Programador.

## Do projeto (por referência)

- 2024 permanece protegido; não serve para seleção de variáveis, hiperparâmetros, calibração ou limiares (R1; DA-010).
- Variáveis do M1: somente `idade_anos`, `sexo` e `gestante`. Comorbidades pertencem à trilha E1 e não entram no M1 automaticamente (R4).
- Município só como agrupamento estatístico, quando autorizado; nunca como preditor (R4).
- Sem correção de desbalanceamento (R3); pré-processamento ajustado só dentro da dobra de treino (R5); semente única (R8).
- Nenhum microdado no git, em app ou em relatório; células com menos de 10 casos suprimidas, inclusive derivadas (R7).
- Associação não é causa. Aprovação técnica não é validade clínica nem validação externa.

## Da equipe de agentes

1. Nenhum agente avança etapa sem autorização expressa em `estado/autorizacao.json`.
2. Nenhum agente faz commit ou push, instala dependência, apaga arquivo ou executa comando destrutivo.
3. Artefatos históricos e resultados congelados não são sobrescritos (ver `estado/protegidos.json`, esquema 2: eixos de leitura e de escrita).
4. Não afirmar que uma validação foi feita sem evidência. Números vêm da execução.
5. Pendência não vira decisão aprovada. `[OPEN QUESTION]`, `[ASSUMPTION]` e `[DECISION NEEDED]` viram "decisão humana necessária".
6. Cada agente grava só o seu relatório. Nenhum agente aprova o próprio trabalho.
7. Falha de teste nunca é ignorada. Falha pré-existente é rotulada como tal, com origem investigada ou "não investigada".
8. Relatórios registram caminho, finalidade e hash dos protegidos, nunca o conteúdo (DA-009).
9. Sem Git no projeto: mudanças são detectadas por manifesto de hashes, não por `git diff`.
10. Todo relatório registra o modelo efetivamente usado (DA-004).
11. `SOMENTE_HASH`: nenhum agente lê o conteúdo nem calcula hash por conta própria. A integridade vem de `manifesto.py verificar` (DA-017).
12. Escrita com negação por padrão. Relatórios e evidências são só de criação; o histórico de execuções é só de acréscimo; nenhum agente exclui, move ou renomeia arquivo (DA-016).
13. `DECISOES.md` só o usuário grava. O Yoshi propõe em `decisoes/propostas/DP-nnn.md` (DA-018).
14. `data/**` e os formatos de microdados (`.parquet`, `.dbc`, `.dbf`) são inacessíveis para sempre aos agentes (DA-019).
15. Escrita é por agente e por ação. A ficha só autoriza o Mario, e nunca em estado, decisões, histórico, fichas, scripts ou testes de agentes (proposta DP-001).
16. Arquivos de 2024 são bloqueados por nome e extensão em qualquer pasta, inclusive depois de movidos (proposta DP-001).
