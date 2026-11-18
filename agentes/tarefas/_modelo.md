# Ficha de tarefa — modelo

> Copie para `agentes/tarefas/<etapa>/<id>.md`. O bloco JSON é lido por hooks (só biblioteca padrão); o texto abaixo dele é para pessoas. Só o Yoshi cria fichas, e só para uma etapa autorizada.

```json
{
  "id": "E3.3-T001",
  "etapa": "3.3",
  "tarefas_tecnicas_relacionadas": ["T-4.9"],
  "objetivo": "",
  "escopo_autorizado": [],
  "arquivos_modificaveis": [],
  "restricoes": [],
  "criterios_de_aceitacao": [],
  "evidencias_exigidas": [],
  "comandos_autorizados": [],
  "estado": "PREPARANDO",
  "responsavel": "yoshi",
  "ciclo": 0
}
```

## Observações

- `arquivos_modificaveis` é uma lista fechada de caminhos. Fora dela, o Mario não grava. Para `config/**`, `pyproject.toml`, `uv.lock`, `reports/etapa2/**` e `reports/etapa3/**` vale **só o caminho exato** (sem curinga). Arquivos protegidos nunca entram, mesmo que listados.
- `comandos_autorizados` lista os comandos que a tarefa permite, dentro da lista fechada da política (ex.: `ruff --no-cache`, `python -X pycache_prefix=<tmp fora do repo> -m py_compile <arquivo>`). Vazio = nenhum comando além do mínimo do papel.
- `restricoes` repete só o que é específico da tarefa. As regras permanentes ficam em `criterios/regras_permanentes.md`.
- `criterios_de_aceitacao` precisa ser verificável por comando ou por leitura de arquivo.
