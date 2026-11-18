# Luigi — testes

> Papel exercido pela sessão de implementação (os agentes ainda não existem como arquivos). Modelo efetivo: Claude Sonnet 5.5 (Peach: subagente de mesmo modelo, contexto separado).

Só `tests/agentes`, em cópia fora do repositório, com `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`, `--basetemp` em /tmp. Ciclo 1: 7 falhas (expectativa de versão no teste). Ciclo 2: 1 falha (caso `CLAUDE2.md` fora de área só-humana). Ciclo 3: **221 passaram**. `ruff check` limpo. Sem `__pycache__` na cópia. Não executado: suíte completa, F1.5, geração de manifesto.
