# Peach — auditoria independente

> Papel exercido pela sessão de implementação (os agentes ainda não existem como arquivos). Modelo efetivo: Claude Sonnet 5.5 (Peach: subagente de mesmo modelo, contexto separado).

**Parecer: REPROVADO.** Rodou `tests/agentes` na cópia: 221/221. Atendidos: C2; `.gitignore`/`.python-version` na raiz; arquivo novo em área só-humana (caso comum); v001 intocada (sha256 e modo 444 conferidos). Abertos: A1 (extensões e `.json` de 2024 não cobertos; Mario poderia gravar `tests/x_2024.json`), A2 (lacre movido perde `SOMENTE_HASH`), B1 (`pode_escrever` sem normalização), B2 (`.gitignore` aninhado), B3 (pastas podadas e link simbólico no `verificar`), B4 (novo em `PRESERVADO`/`SOMENTE_HASH` só gera `NOVO`). Limite: nada é aplicado por hook até a F2. Detalhes e correções propostas em `agentes/decisoes/propostas/DP-001.md`.
