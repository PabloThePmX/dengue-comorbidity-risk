"""Espaço de busca de hiperparâmetros por modelo (T-4.0, Q-08, D-68).

As faixas vivem só em `config/base.yaml`, sob `busca:`. O `tune` (T-4.3) chama `sugerir` com o
espaço de cada modelo e não repete nenhuma faixa no código. O carregador valida o YAML e recusa
qualquer nome de peso de classe (R3), como segunda barreira além dos testes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

TIPOS = ("float", "int", "categorico")
ESCALAS = ("linear", "log")
CHAVES_ENTRADA = {"fixos", "parametros", "sem_busca", "primeira_tentativa"}
CHAVES_PARAMETRO = {"tipo", "escala", "min", "max", "valores"}
# R3: nada de correção de desbalanceamento em nenhum modelo (comparação sem nome/valor).
PROIBIDOS_R3 = (
    "class_weight",
    "scale_pos_weight",
    "is_unbalance",
    "auto_class_weights",
    "pos_weight",
    "balanced",
)


@dataclass(frozen=True)
class Parametro:
    nome: str
    tipo: str
    escala: str | None
    minimo: float | int | None
    maximo: float | int | None
    valores: tuple[Any, ...]


@dataclass(frozen=True)
class EspacoModelo:
    modelo: str
    parametros: tuple[Parametro, ...]
    fixos: dict[str, Any]
    sem_busca: bool
    # 1ª tentativa da busca (T-4.3): um valor por parâmetro buscado, dentro das faixas.
    primeira_tentativa: dict[str, Any] = field(default_factory=dict)


def load_search_space(cfg: dict) -> dict[str, EspacoModelo]:
    """Lê `busca:` do config e devolve um espaço por modelo, na ordem de `ordem_modelos`.

    Levanta ValueError se faltar modelo, sobrar modelo, uma faixa for inválida ou aparecer peso de
    classe (R3).
    """
    busca = cfg.get("busca")
    if not isinstance(busca, dict):
        raise ValueError("config: falta o mapa 'busca' com o espaço de cada modelo (T-4.0)")
    ordem = cfg.get("ordem_modelos")
    if not ordem:
        raise ValueError("config: falta 'ordem_modelos'")
    faltando = [m for m in ordem if m not in busca]
    sobrando = [m for m in busca if m not in ordem]
    if faltando or sobrando:
        raise ValueError(f"busca: modelos sem entrada {faltando}; entradas sem modelo {sobrando}")
    _recusa_peso_de_classe(busca)
    return {modelo: _espaco_do_modelo(modelo, busca[modelo]) for modelo in ordem}


def sugerir(trial, espaco: EspacoModelo) -> dict[str, Any]:
    """Sorteia os parâmetros buscados com `trial.suggest_*`. Os `fixos` ficam de fora."""
    valores: dict[str, Any] = {}
    for p in espaco.parametros:
        if p.tipo == "categorico":
            valores[p.nome] = trial.suggest_categorical(p.nome, list(p.valores))
        elif p.tipo == "float":
            valores[p.nome] = trial.suggest_float(
                p.nome, p.minimo, p.maximo, log=p.escala == "log"
            )
        else:
            valores[p.nome] = trial.suggest_int(p.nome, p.minimo, p.maximo, log=p.escala == "log")
    return valores


def _espaco_do_modelo(modelo: str, entrada: Any) -> EspacoModelo:
    if not isinstance(entrada, dict):
        raise ValueError(f"busca.{modelo}: deve ser um mapa")
    extra = set(entrada) - CHAVES_ENTRADA
    if extra:
        raise ValueError(f"busca.{modelo}: chaves desconhecidas {sorted(extra)}")
    sem_busca = bool(entrada.get("sem_busca", False))
    parametros_cfg = entrada.get("parametros") or {}
    if sem_busca and parametros_cfg:
        raise ValueError(f"busca.{modelo}: sem_busca não aceita parâmetros")
    if not sem_busca and not parametros_cfg:
        raise ValueError(f"busca.{modelo}: sem parâmetros; use sem_busca: true se for o caso")
    parametros = tuple(
        _parametro(modelo, nome, spec) for nome, spec in parametros_cfg.items()
    )
    primeira = _primeira_tentativa(modelo, parametros, entrada.get("primeira_tentativa"), sem_busca)
    return EspacoModelo(
        modelo=modelo,
        parametros=parametros,
        fixos=dict(entrada.get("fixos") or {}),
        sem_busca=sem_busca,
        primeira_tentativa=primeira,
    )


def _primeira_tentativa(
    modelo: str, parametros: tuple[Parametro, ...], valor: Any, sem_busca: bool
) -> dict[str, Any]:
    """Confere o ponto de partida: exatamente os parâmetros buscados, cada um dentro da faixa."""
    where = f"busca.{modelo}.primeira_tentativa"
    if sem_busca:
        if valor is not None:
            raise ValueError(f"{where}: sem_busca não aceita ponto de partida")
        return {}
    if not isinstance(valor, dict) or not valor:
        raise ValueError(f"{where}: falta o ponto de partida (mapa com um valor por parâmetro)")
    nomes = {p.nome for p in parametros}
    if set(valor) != nomes:
        raise ValueError(f"{where}: parâmetros {sorted(valor)} != buscados {sorted(nomes)}")
    for p in parametros:
        v = valor[p.nome]
        if p.tipo == "categorico":
            if v not in p.valores:
                raise ValueError(f"{where}.{p.nome}: {v!r} fora de {list(p.valores)}")
            continue
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError(f"{where}.{p.nome}: deve ser número, não {v!r}")
        if p.tipo == "int" and not isinstance(v, int):
            raise ValueError(f"{where}.{p.nome}: deve ser inteiro, não {v!r}")
        if not p.minimo <= v <= p.maximo:
            raise ValueError(f"{where}.{p.nome}: {v} fora de [{p.minimo}, {p.maximo}]")
    return dict(valor)


def _parametro(modelo: str, nome: str, spec: Any) -> Parametro:
    where = f"busca.{modelo}.{nome}"
    if not isinstance(spec, dict):
        raise ValueError(f"{where}: deve ser um mapa")
    extra = set(spec) - CHAVES_PARAMETRO
    if extra:
        raise ValueError(f"{where}: chaves desconhecidas {sorted(extra)}")
    tipo = spec.get("tipo")
    if tipo not in TIPOS:
        raise ValueError(f"{where}: tipo {tipo!r} inválido; use {TIPOS}")

    if tipo == "categorico":
        if set(spec) - {"tipo", "valores"}:
            raise ValueError(f"{where}: categórico aceita só 'valores'")
        valores = spec.get("valores")
        if not isinstance(valores, list) or not valores:
            raise ValueError(f"{where}: 'valores' deve ser uma lista não vazia")
        if any(not isinstance(v, (str, int, float)) or isinstance(v, bool) for v in valores):
            raise ValueError(f"{where}: valores devem ser texto ou número")
        if len({repr(v) for v in valores}) != len(valores):
            raise ValueError(f"{where}: valores repetidos")
        return Parametro(nome, tipo, None, None, None, tuple(valores))

    escala = spec.get("escala")
    if escala not in ESCALAS:
        raise ValueError(f"{where}: escala {escala!r} inválida; use {ESCALAS}")
    minimo, maximo = spec.get("min"), spec.get("max")
    if tipo == "int":
        numerico = all(isinstance(x, int) and not isinstance(x, bool) for x in (minimo, maximo))
    else:
        numerico = all(
            isinstance(x, (int, float)) and not isinstance(x, bool) for x in (minimo, maximo)
        )
    if not numerico:
        raise ValueError(f"{where}: min e max devem ser números do tipo {tipo}")
    if not minimo < maximo:
        raise ValueError(f"{where}: min ({minimo}) deve ser menor que max ({maximo})")
    if escala == "log" and minimo <= 0:
        raise ValueError(f"{where}: escala log exige min > 0")
    return Parametro(nome, tipo, escala, minimo, maximo, ())


def _recusa_peso_de_classe(busca: dict) -> None:
    for texto in _textos(busca):
        minusculo = texto.lower()
        for proibido in PROIBIDOS_R3:
            if proibido in minusculo:
                raise ValueError(
                    f"busca contém {proibido!r} (R3: sem correção de desbalanceamento)"
                )


def _textos(obj: Any):
    """Gera todas as chaves e valores (como texto) de uma estrutura aninhada."""
    if isinstance(obj, dict):
        for chave, valor in obj.items():
            yield str(chave)
            yield from _textos(valor)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            yield from _textos(item)
    else:
        yield str(obj)
