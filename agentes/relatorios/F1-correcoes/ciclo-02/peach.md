# Peach — reauditoria

> Papel exercido pela sessão de implementação. Modelo efetivo: Claude Sonnet 5.5 (Peach: subagente de mesmo modelo, nova instância, contexto separado). Ciclo extra autorizado pelo usuário (D-e, 2026-11-18 10:42).

**Parecer: APROVADO COM RESSALVAS** (sem achado crítico, sem regressão). 319/319 testes. A1, A2, B1, B2 e B3 resolvidos nos cenários indicados. Sem falso positivo contra os 181 caminhos da v001. Ordem dos itens irrelevante (7.840 decisões comparadas). v001 intocada.

Ressalvas não críticas, **abertas**:
- N1: link simbólico que substitui a própria pasta humana (`.claude`, `tests/agentes`, `agentes/scripts`) não é sinalizado (o padrão `pasta/**` exige algo depois da barra).
- N2: pasta com nome de cache (`.pytest_cache` etc.) e `.pyc` em `__pycache__` são ignorados sem olhar o conteúdo; um `.pyc` forjado seria ignorado.
- N3: a lista de extensões de 2024 é lista negra e não cobre, por exemplo, `.parq`, `.mat`, `.safetensors`, `.sql`, `.sh`, `.py`. Nas áreas do Mario qualquer nome com 2024 é só-humano. Em `agentes/evidencias/*/ciclo-*/mario/**` o Mario ainda cria `x_2024.json`.
- N4: padrão de tipo errado em `protegidos.json` gera TypeError (não `PoliticaInvalida`); os pontos `*_seguro` negam, o `main` do manifesto mostraria traceback.
- N5: `.DS_Store` ou arquivo de editor em área só-humana reprova o `verificar`; contra a v001, vários arquivos só-humanos aparecem como novos até gerar a v002.
- N6: desempenho linear, cerca de 115 µs por arquivo; sem laço de links.
- N7: 21 arquivos da v001 mudam de PRESERVADO para SOMENTE_HASH (`CLASSE_ALTERADA`, não reprova), intencional (R7).
Limites aceitos: B4; `.py`/`.json` de 2024 fora das áreas do Mario; nada é aplicado por hook até a F2.
