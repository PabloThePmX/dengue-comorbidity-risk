"""Avaliador comparativo da comparação em 2025 (T-8.7, D-97, D-99; R1, R2, R7, R8).

Funções puras sobre arrays e DataFrames que o chamador já leu. Este módulo não lê dado real (só
`carregar_previsoes` lê o arquivo que o chamador indica), não abre a porta do `guard`, não importa
função de treino, ajuste ou seleção, e não escolhe nada: só mede o que o manifesto declara.

Fluxo:
1. `alinhar`: junta as previsões de cada modelo com o `y` pela chave (ANO, LINHA). Recusa linha
   faltando, sobrando ou repetida, ano diferente do de comparação, `p` fora de [0, 1] e NaN fora do
   que o E1 declara (`estimavel = false`, D-99).
2. `calcular`: população principal (casos que o E1 estima, igual para todos) e completa
   (informação). Métricas sem limiar com IC 95% pelo `metrics.Reamostrador` (células estratificadas
   por alvo, os mesmos sorteios para todos os modelos, sementes do config; R8). Diferença de PR-AUC
   contra o M1 pareada. Recall e precisão nos orçamentos de alertas e no limiar próprio. Curva de
   decisão e calibração por caixas (`teste_analises`), e a conformidade R3 a R6 de cada modelo.
3. `escrever_agregados` grava `metricas.json` (formato do contrato) e os `.md` dele.
   `validar_agregados` recusa tudo que sai do formato, e as células de 1 a 9 (R7).

Convenções:
- Diferença de PR-AUC = PR-AUC do modelo − PR-AUC do `m1_main`. "melhor" quando o IC inferior é > 0,
  "pior" quando o superior é < 0, "sem diferença detectável" nos demais casos.
- Orçamento de X%: marca os `k = round(X · n)` casos de maior `p`; empate de `p` desempata pela
  LINHA crescente (determinístico, com teste).
- Ajuste de calibração que não converge (separação perfeita) sai como `valor: null`, sem derrubar a
  avaliação (modo tolerante do `Reamostrador`). Se mais de 5% das reamostras não convergem, o IC
  também sai `null`, como na T-5.2.
- `null` no lugar do bloco significa "o modelo não estima esta população" (E1 na completa) ou "não
  se aplica" (referência na diferença). `{"valor": null, "ic95": null}` significa "indisponível".
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from dengue_sinan import metrics
from dengue_sinan import teste_analises as ta

CHAVES = ("ANO", "LINHA")
MODELO_DE_REFERENCIA = "m1_main"
MODELO_DO_SUBCONJUNTO = "e1_main"
RAMO_DO_PROJETO = "main"
METRICAS = ("pr_auc", "roc_auc", "brier", "calibration_slope", "calibration_intercepto", "obs_esp")
POPULACOES = ("principal", "completa")
LEITURAS = ("melhor", "pior", "sem diferença detectável")
CONFORMIDADE = ("r3_sem_correcao", "r4_variaveis_no_dicionario", "treino_sem_ano_de_comparacao",
                "versoes_diferentes_do_treino", "externo")
NOMES_POPULACOES = {
    "principal": "casos que o E1 estima (D-99); igual para todos os modelos",
    "completa": "todos os casos da entrada (informação; o E1 não entra)",
}
R7_MINIMO = 10  # células de menos de 10 casos ou eventos não saem (R7)
CHAVES_TOPO = frozenset({
    "ano", "reamostras", "semente", "modelos", "modelo_de_referencia", "populacoes", "metricas",
    "diferencas_pr_auc_vs_referencia", "orcamentos", "no_limiar_proprio", "curva_decisao",
    "calibracao", "conformidade",
})


# --- Alinhamento -------------------------------------------------------------------------------

@dataclass(frozen=True)
class Alinhado:
    """Entrada alinhada: uma linha por caso, na ordem crescente de LINHA.

    `escores`: `p` de cada modelo (NaN só no E1, onde `principal` é False); `principal`: máscara da
    população principal (`estimavel` do E1); `ids`: os modelos, na ordem recebida.
    """

    ano: int
    linha: np.ndarray
    y: np.ndarray
    escores: dict[str, np.ndarray]
    principal: np.ndarray
    ids: tuple[str, ...]


def _exigir_colunas(df: pd.DataFrame, colunas: tuple[str, ...], nome: str) -> None:
    faltam = [c for c in colunas if c not in df.columns]
    if faltam:
        raise ValueError(f"{nome}: faltam as colunas {faltam}")


def _checar_chaves(df: pd.DataFrame, ano: int, nome: str) -> None:
    for coluna in CHAVES:
        if not pd.api.types.is_integer_dtype(df[coluna]):
            raise ValueError(f"{nome}: `{coluna}` precisa ser inteiro")
    fora = int((df["ANO"] != ano).sum())
    if fora:
        raise ValueError(f"{nome}: {fora} linha(s) de ano diferente de {ano} (ano de comparação)")
    repetidas = int(df.duplicated(list(CHAVES), keep=False).sum())
    if repetidas:
        raise ValueError(f"{nome}: {repetidas} linha(s) com (ANO, LINHA) repetido")


def carregar_previsoes(caminho: str | Path) -> pd.DataFrame:
    """Lê o parquet de previsões de um modelo (`p_<id>_<ano>.parquet`). Confere só as colunas; as
    regras das linhas ficam em `alinhar`."""
    df = pd.read_parquet(caminho)
    _exigir_colunas(df, ("ANO", "LINHA", "p"), f"previsões em {Path(caminho).name}")
    return df


def alinhar(referencia: pd.DataFrame, previsoes: dict[str, pd.DataFrame], *, ano: int) -> Alinhado:
    """Junta cada previsão com o `y` da entrada pela chave (ANO, LINHA) e recusa o que não bate.

    `referencia`: colunas ANO, LINHA e `y` (0/1), uma linha por caso. `previsoes`: id -> DataFrame
    com ANO, LINHA e `p`; o E1 traz também `estimavel` (bool), que define a população principal.
    """
    if not previsoes:
        raise ValueError("nenhuma previsão para alinhar")
    _exigir_colunas(referencia, ("ANO", "LINHA", "y"), "referência")
    _checar_chaves(referencia, ano, "referência")
    if referencia["y"].isna().any() or not referencia["y"].isin([0, 1]).all():
        raise ValueError("referência: `y` precisa ser 0 ou 1, sem NaN")
    base = referencia.set_index(list(CHAVES))[["y"]].sort_index()

    escores: dict[str, np.ndarray] = {}
    principal: np.ndarray | None = None
    for modelo, df in previsoes.items():
        _exigir_colunas(df, ("ANO", "LINHA", "p"), modelo)
        _checar_chaves(df, ano, modelo)
        indice = df.set_index(list(CHAVES))
        faltam = int(base.index.difference(indice.index).size)
        if faltam:
            raise ValueError(f"{modelo}: faltam {faltam} linha(s) da entrada")
        sobram = int(indice.index.difference(base.index).size)
        if sobram:
            raise ValueError(f"{modelo}: {sobram} linha(s) a mais que a entrada")
        alinhado = indice.reindex(base.index)
        p = alinhado["p"].astype(float).to_numpy()
        sem_p = np.isnan(p)
        if modelo == MODELO_DO_SUBCONJUNTO:
            if "estimavel" not in alinhado.columns or alinhado["estimavel"].dtype != bool:
                raise ValueError(f"{modelo}: falta `estimavel` (bool), que define a população "
                                 "(D-99)")
            estimavel = alinhado["estimavel"].to_numpy(dtype=bool)
            if (sem_p != ~estimavel).any():
                raise ValueError(f"{modelo}: NaN em `p` tem que coincidir com estimavel = false "
                                 "(D-99): há NaN onde estimavel é true, ou número onde é false")
            principal = estimavel
        elif sem_p.any():
            raise ValueError(f"{modelo}: {int(sem_p.sum())} `p` NaN (só o E1 pode ter)")
        valido = p[~sem_p]
        if ((valido < 0) | (valido > 1)).any():
            raise ValueError(f"{modelo}: `p` fora de [0, 1]")
        escores[modelo] = p

    if principal is None:
        raise ValueError(f"falta a previsão de {MODELO_DO_SUBCONJUNTO}, que define a população "
                         "principal (D-99)")
    return Alinhado(
        ano=int(ano),
        linha=base.index.get_level_values("LINHA").to_numpy(dtype=np.int64),
        y=base["y"].to_numpy(dtype=np.int64),
        escores=escores,
        principal=principal,
        ids=tuple(previsoes),
    )


# --- Orçamento de alertas ----------------------------------------------------------------------

def k_do_orcamento(orcamento: float, n: int) -> int:
    """Nº de alertas de um orçamento X% sobre `n` casos: X·n arredondado ao inteiro mais próximo."""
    if not 0.0 < orcamento < 1.0:
        raise ValueError(f"orçamento de alertas fora de (0, 1): {orcamento}")
    k = int(orcamento * n + 0.5)
    if k < 1:
        raise ValueError(f"orçamento {orcamento} com {n} casos marca zero alertas")
    return k


def marcar_orcamento(p: np.ndarray, linha: np.ndarray, k: int) -> np.ndarray:
    """Marca os `k` casos de maior `p`. Empate de `p`: vence a menor LINHA (determinístico)."""
    p = np.asarray(p, dtype=float)
    linha = np.asarray(linha)
    ordem = np.lexsort((linha, -p))  # primário: -p crescente (p decrescente); depois LINHA
    marcados = np.zeros(len(p), dtype=bool)
    marcados[ordem[:k]] = True
    return marcados


# --- Blocos do contrato -------------------------------------------------------------------------

SUPRIMIDA = "<10"


def _publicar_contagem(n: int) -> int | str:
    """R7 na PUBLICAÇÃO: contagem de 1 a 9 sai como "<10"; 0 e 10 ou mais continuam numéricos.
    Chamada só depois de calcular as métricas: nunca levanta, e não muda nenhum cálculo."""
    return SUPRIMIDA if 0 < n < R7_MINIMO else int(n)


def _contagem_publicada_valida(valor, caminho: str) -> None:
    """Aceita "<10" ou inteiro 0 ou >= 10. Recusa número de 1 a 9, texto que não seja "<10", float,
    bool, lista (valor por linha) e negativo."""
    if isinstance(valor, str):
        if valor != SUPRIMIDA:
            raise ValueError(f"{caminho}: texto só pode ser \"<10\" (R7), veio {valor!r}")
        return
    _inteiro(valor, caminho)
    if 0 < valor < R7_MINIMO:
        raise ValueError(f"{caminho}: contagem de 1 a 9 deve sair como \"<10\" (R7)")


def _rotulo(orcamento: float) -> str:
    return f"{orcamento:.2f}"


def _chave_orcamento(modelo: str, orcamento: float) -> str:
    return f"{modelo}|orc{_rotulo(orcamento)}"


def _chave_limiar(modelo: str) -> str:
    return f"{modelo}|limiar"


def _bloco(valor, valores, *, descartadas: int = 0, n: int) -> dict:
    """{"valor", "ic95"}. Valor ausente (None ou NaN) vira indisponível. IC None se não há
    reamostras válidas ou se mais de 5% das reamostras não convergiram (política da T-5.2)."""
    if valor is None or not math.isfinite(float(valor)):
        return {"valor": None, "ic95": None}
    if valores is None or descartadas > ta.LIMITE_DESCARTE * n:
        ic = None
    else:
        ic = ta.ic(valores)
    return {"valor": float(valor), "ic95": ic}


def _leitura_do_ic(ic: list[float] | None) -> str:
    """Convenção (contrato): "melhor" se o IC inferior > 0, "pior" se o superior < 0, senão
    "sem diferença detectável". A mesma regra vale no cálculo e na validação."""
    if ic is None:
        raise ValueError("diferença sem IC: não há reamostras")
    if ic[0] > 0:
        return "melhor"
    if ic[1] < 0:
        return "pior"
    return "sem diferença detectável"


def _caixa_r7(*, casos: int, eventos: int, previsto: float, dist: np.ndarray) -> dict:
    """Caixa de calibração com a supressão R7: menos de 10 casos some tudo; menos de 10 eventos
    some a taxa observada e o IC (o risco previsto médio e o nº de casos ficam)."""
    if casos < R7_MINIMO:
        return {"previsto": None, "observado": None, "ic95": None, "casos": "<10"}
    if eventos < R7_MINIMO:
        return {"previsto": float(previsto), "observado": None, "ic95": None, "casos": casos}
    return {"previsto": float(previsto), "observado": eventos / casos, "ic95": ta.ic(dist),
            "casos": casos}


# --- Conformidade (mapeamento dos JSON dos scripts de `scripts/comparacao/`) --------------------

def _campo(conf: dict, chave: str, modelo: str) -> Any:
    if chave not in conf:
        raise ValueError(f"{modelo}: conformidade sem a chave `{chave}`")
    return conf[chave]


def _versoes_diferem(execucao: dict | None, treino: dict | None) -> bool | None:
    """True se alguma versão em comum difere; None se não há como comparar."""
    if not execucao or not treino:
        return None

    def normalizar(d: dict) -> dict[str, str]:
        return {str(k).lower().replace("-", "_"): str(v) for k, v in d.items()}

    a, b = normalizar(execucao), normalizar(treino)
    comuns = sorted(set(a) & set(b))
    if not comuns:
        return None
    return any(a[k] != b[k] for k in comuns)


def conformidade_do_modelo(conf: dict, modelo: dict, ano: int) -> dict:
    """Os cinco campos de `conformidade` do contrato, a partir do JSON de conformidade de um script.

    Aceita as formas dos três scripts (projeto, soneca, lora). R3 e R4 vêm do que o script mediu;
    o ano de comparação é conferido contra o manifesto e contra os anos que o artefato declara; as
    versões são comparadas quando as duas listas existem (senão `null`); `externo` vem do ramo.
    """
    mid = modelo["id"]
    r3 = _campo(conf, "r3_busca", mid)
    r4 = bool(_campo(conf, "todas_no_dicionario_do_projeto", mid))
    anos = set(modelo.get("treino_anos") or [])
    for chave in ("anos_de_treino_dos_metadados", "anos_na_assinatura_dos_dados"):
        anos |= {int(a) for a in (conf.get(chave) or [])}
    meta_ramo = conf.get("metadados_da_branch") or {}
    anos |= {int(a) for a in (meta_ramo.get("anos_de_treino_config") or [])}
    treino_ok = ano not in anos
    if "ano_de_comparacao_fora_do_treino" in conf:
        treino_ok = treino_ok and bool(conf["ano_de_comparacao_fora_do_treino"])
    execucao = conf.get("versoes") or conf.get("versoes_do_ambiente")
    treino = meta_ramo.get("versoes_de_treino") or modelo.get("ambiente_de_origem")
    origem = modelo.get("origem") or {}
    return {
        "r3_sem_correcao": not bool(r3.get("com_correcao_de_desbalanceamento", False)),
        "r4_variaveis_no_dicionario": r4,
        "treino_sem_ano_de_comparacao": bool(treino_ok),
        "versoes_diferentes_do_treino": _versoes_diferem(execucao, treino),
        "externo": origem.get("branch") != RAMO_DO_PROJETO,
    }


# --- Bootstrap e agregados ----------------------------------------------------------------------

@dataclass(frozen=True)
class _Bootstrap:
    pontos: dict
    limiares: dict
    dist: dict


def _bootstrap(y, linha, escores: dict[str, np.ndarray], *, orcamentos, limiares: dict,
               n: int, seed: int, processos: int) -> _Bootstrap:
    """Um estado do `Reamostrador` para a população: escores, orçamentos e limiares próprios."""
    total = len(y)
    marcados: dict[str, np.ndarray] = {}
    for modelo, p in escores.items():
        for orcamento in orcamentos:
            marcados[_chave_orcamento(modelo, orcamento)] = marcar_orcamento(
                p, linha, k_do_orcamento(orcamento, total))
        if modelo in limiares:
            marcados[_chave_limiar(modelo)] = p >= limiares[modelo]
    estado, grandes, meta = metrics.montar_estado(y, escores, marcados, completo=True,
                                                  tolerante=True)
    pontos, limiar_pontos = estado.pontos()
    sementes = metrics.sementes_das_reamostras(seed, n)
    dist, _ = metrics.rodar_reamostras(estado, grandes, meta, sementes, processos)
    return _Bootstrap(pontos=pontos, limiares=limiar_pontos, dist=dist)


def _metricas(boot: _Bootstrap, modelos: list[str], n: int) -> dict:
    saida = {}
    for m in modelos:
        pt = boot.pontos[m]

        def valores(c: str, _m: str = m) -> np.ndarray | None:
            return boot.dist.get(f"{_m}/{c}")

        chave_descarte = f"{m}/calibracao_descartada"
        descartadas = (int(np.nansum(boot.dist[chave_descarte]))
                       if chave_descarte in boot.dist else 0)
        saida[m] = {
            "pr_auc": _bloco(pt["pr_auc"], valores("pr_auc"), n=n),
            "roc_auc": _bloco(pt.get("roc_auc"), valores("roc_auc"), n=n),
            "brier": _bloco(pt.get("brier"), valores("brier"), n=n),
            "calibration_slope": _bloco(pt.get("slope"), valores("slope"),
                                        descartadas=descartadas, n=n),
            "calibration_intercepto": _bloco(pt.get("intercepto"), valores("intercepto"),
                                             descartadas=descartadas, n=n),
            "obs_esp": _bloco(pt.get("obs_esp"), valores("obs_esp"), n=n),
        }
    return saida


def _diferencas(boot: _Bootstrap, modelos: list[str], n: int) -> dict:
    """PR-AUC do modelo − PR-AUC do M1, com as mesmas reamostras (pareado)."""
    saida: dict[str, dict | None] = {}
    ref = MODELO_DE_REFERENCIA
    for m in modelos:
        if m == ref:
            saida[m] = None
            continue
        valor = boot.pontos[m]["pr_auc"] - boot.pontos[ref]["pr_auc"]
        ic = ta.ic(boot.dist[f"{m}/pr_auc"] - boot.dist[f"{ref}/pr_auc"])
        saida[m] = {"valor": float(valor), "ic95": ic, "leitura": _leitura_do_ic(ic)}
    return saida


def _orcamentos(boot: _Bootstrap, modelos: list[str], orcamentos, n: int) -> dict:
    saida = {}
    for m in modelos:
        por_orcamento = {}
        for orcamento in orcamentos:
            c = _chave_orcamento(m, orcamento)
            pt = boot.limiares[c]
            por_orcamento[_rotulo(orcamento)] = {
                "alertas": int(round(pt["marcados"])),
                "vp": int(round(pt["vp"])),
                "recall": _bloco(pt["recall"], boot.dist[f"{c}/limiar_recall"], n=n),
                "precisao": _bloco(pt["precisao"], boot.dist[f"{c}/limiar_precisao"], n=n),
            }
        saida[m] = por_orcamento
    return saida


def _calibracao(y, escores: dict[str, np.ndarray], *, n: int, seed: int) -> dict:
    res = ta.calibracao_por_caixas(y, escores, caixas=ta.CAIXAS_CALIBRACAO, seed=seed, n=n)
    saida = {}
    for m in escores:
        saida[m] = [
            _caixa_r7(casos=int(res.n_caixa[m][b]), eventos=int(res.eventos_caixa[m][b]),
                      previsto=float(res.previsto_medio[m][b]), dist=res.dist[m][:, b])
            for b in range(len(res.n_caixa[m]))
        ]
    return saida


def _calcular_brutos(alinhado: Alinhado, manifesto: dict, cfg: dict,
                     conformidade: dict[str, dict], *,
             reamostras: int | None = None, processos: int = 1,
             ano_esperado: int | None = None) -> dict:
    """Agregados da comparação, no formato de `metricas.json` (contrato "Comparação em 2025").

    `conformidade`: id -> JSON de conformidade do script daquele modelo. `reamostras` padrão: o do
    manifesto (1.000). `processos`: do bootstrap (o resultado não depende dele, R8).
    `ano_esperado`: se dado, recusa entrada de outro ano. A T-8.9 passa `cfg["ano_comparacao"]`;
    os testes com anos sintéticos deixam None.
    """
    if ano_esperado is not None and alinhado.ano != ano_esperado:
        raise ValueError(f"entrada de {alinhado.ano}, mas o ano de comparação é "
                         f"{ano_esperado} (R1)")
    n = int(reamostras if reamostras is not None else manifesto["comparacao"]["bootstrap"])
    if n < 1:
        raise ValueError("reamostras: pelo menos uma")
    seed = int(cfg["seed"])
    orcamentos = tuple(float(b) for b in manifesto["comparacao"]["orcamentos_de_alertas"])
    modelos = list(manifesto["modelos"])
    ids = [m["id"] for m in modelos]
    if set(ids) != set(alinhado.ids):
        raise ValueError("modelos do manifesto e das previsões diferem: "
                         f"{sorted(set(ids) ^ set(alinhado.ids))}")
    if MODELO_DE_REFERENCIA not in ids:
        raise ValueError(f"o modelo de referência {MODELO_DE_REFERENCIA} não está no manifesto")
    faltam = [m for m in ids if m not in conformidade]
    if faltam:
        raise ValueError(f"sem conformidade para {faltam}")
    limiares = {m["id"]: float((m.get("limiar") or {})["valor"])
                for m in modelos if (m.get("limiar") or {}).get("valor") is not None}

    por_populacao: dict[str, dict] = {}
    populacoes: dict[str, dict] = {}
    booteados: dict[str, _Bootstrap] = {}
    estimam_por_populacao: dict[str, list[str]] = {}
    mascaras = {"principal": alinhado.principal,
                "completa": np.ones(len(alinhado.y), dtype=bool)}
    for pop in POPULACOES:
        mascara = mascaras[pop]
        y_p = alinhado.y[mascara]
        linha_p = alinhado.linha[mascara]
        if y_p.sum() == 0 or y_p.sum() == len(y_p):
            raise ValueError(f"população {pop}: precisa ter positivos e negativos (PR-AUC)")
        escores_p = {m: alinhado.escores[m][mascara] for m in ids}
        estimam = [m for m in ids if not np.isnan(escores_p[m]).any()]
        lim_pop = {m: v for m, v in limiares.items() if m in estimam} if pop == "principal" else {}
        boot = _bootstrap(y_p, linha_p, {m: escores_p[m] for m in estimam},
                          orcamentos=orcamentos, limiares=lim_pop, n=n, seed=seed,
                          processos=processos)
        booteados[pop] = boot
        estimam_por_populacao[pop] = estimam
        bloco_metricas = _metricas(boot, estimam, n)
        bloco_dif = _diferencas(boot, estimam, n)
        bloco_orc = _orcamentos(boot, estimam, orcamentos, n)
        por_populacao[pop] = {
            "metricas": {m: bloco_metricas.get(m, {k: None for k in METRICAS}) for m in ids},
            "diferencas": {m: bloco_dif.get(m) for m in ids},
            "orcamentos": {m: bloco_orc.get(m) for m in ids},
        }
        populacoes[pop] = {"nome": NOMES_POPULACOES[pop],
                           "casos": int(len(y_p)),
                           "eventos": int(y_p.sum()),
                           "prevalencia": float(y_p.mean())}

    principal = booteados["principal"]
    y_principal = alinhado.y[alinhado.principal]
    escores_principal = {m: alinhado.escores[m][alinhado.principal] for m in ids}
    no_limiar: dict[str, Any] = {}
    for m in ids:
        if m not in limiares:
            no_limiar[m] = None
            continue
        c = _chave_limiar(m)
        pt = principal.limiares[c]
        no_limiar[m] = {
            "limiar": limiares[m],
            "alertas": int(round(pt["marcados"])),
            "vp": int(round(pt["vp"])),
            "recall": _bloco(pt["recall"], principal.dist[f"{c}/limiar_recall"], n=n),
            "precisao": _bloco(pt["precisao"], principal.dist[f"{c}/limiar_precisao"], n=n),
        }

    grade = ta.grade_de_limiares(cfg)
    curva: dict[str, Any] = {"limiares": [float(t) for t in grade]}
    for m in ids:
        curva[m] = [float(v) for v in metrics.net_benefit(y_principal, escores_principal[m],
                                                          grade)["modelo"]]

    modelo_por_id = {m["id"]: m for m in modelos}
    return {
        "ano": int(alinhado.ano),
        "reamostras": n,
        "semente": seed,
        "modelos": ids,
        "modelo_de_referencia": MODELO_DE_REFERENCIA,
        "populacoes": populacoes,
        "metricas": {pop: por_populacao[pop]["metricas"] for pop in POPULACOES},
        "diferencas_pr_auc_vs_referencia": {pop: por_populacao[pop]["diferencas"]
                                            for pop in POPULACOES},
        "orcamentos": {pop: por_populacao[pop]["orcamentos"] for pop in POPULACOES},
        "no_limiar_proprio": no_limiar,
        "curva_decisao": curva,
        "calibracao": _calibracao(y_principal, escores_principal, n=n, seed=seed),
        "conformidade": {m: conformidade_do_modelo(conformidade[m], modelo_por_id[m], alinhado.ano)
                         for m in ids},
    }


# --- Publicação (R7) ----------------------------------------------------------------------------

def _publicar_bloco_alerta(bloco: dict) -> dict:
    """Publica um bloco de orçamento ou de limiar próprio com R7. Recall e precisão viram
    {"valor": null, "ic95": null} quando há 1 a 9 alertas OU 1 a 9 eventos capturados entre eles
    (VP). Alertas de 1 a 9 saem como "<10". Só depois do cálculo: nunca levanta."""
    alertas, vp = bloco["alertas"], bloco["vp"]
    suprimido = 0 < alertas < R7_MINIMO or 0 < vp < R7_MINIMO
    nulo = {"valor": None, "ic95": None}
    return {
        "alertas": _publicar_contagem(alertas),
        "recall": dict(nulo) if suprimido else bloco["recall"],
        "precisao": dict(nulo) if suprimido else bloco["precisao"],
    }


def publicar(bruto: dict) -> dict:
    """Aplica a publicação R7 ao resultado bruto de `_calcular_brutos`: contagens de 1 a 9 viram
    "<10", recall e precisão de linhas com VP ou alertas de 1 a 9 viram null, e o VP interno sai."""
    populacoes = {
        pop: {"nome": info["nome"], "casos": _publicar_contagem(info["casos"]),
              "eventos": _publicar_contagem(info["eventos"]),
              "prevalencia": info["prevalencia"]}
        for pop, info in bruto["populacoes"].items()
    }
    orcamentos = {
        pop: {m: (None if por is None else
                  {rot: _publicar_bloco_alerta(b) for rot, b in por.items()})
              for m, por in mods.items()}
        for pop, mods in bruto["orcamentos"].items()
    }
    no_limiar = {
        m: (None if b is None else {"limiar": b["limiar"], **_publicar_bloco_alerta(b)})
        for m, b in bruto["no_limiar_proprio"].items()
    }
    return {**bruto, "populacoes": populacoes, "orcamentos": orcamentos,
            "no_limiar_proprio": no_limiar}


def calcular(alinhado: Alinhado, manifesto: dict, cfg: dict, conformidade: dict[str, dict], *,
             reamostras: int | None = None, processos: int = 1,
             ano_esperado: int | None = None) -> dict:
    """Agregados PUBLICADOS da comparação (contrato "Comparação em 2025"): o cálculo de
    `_calcular_brutos` com a supressão R7 da publicação aplicada."""
    return publicar(_calcular_brutos(alinhado, manifesto, cfg, conformidade,
                                     reamostras=reamostras, processos=processos,
                                     ano_esperado=ano_esperado))


# --- Validação do formato (contrato) -------------------------------------------------------------

def _inteiro(valor, caminho: str, minimo: int = 0) -> None:
    if not isinstance(valor, int) or isinstance(valor, bool) or valor < minimo:
        raise ValueError(f"{caminho}: inteiro >= {minimo} esperado, veio {valor!r}")


def _real(valor, caminho: str) -> None:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor):
        raise ValueError(f"{caminho}: número finito esperado, veio {valor!r}")


def _chaves_exatas(dados, chaves, caminho: str) -> None:
    if not isinstance(dados, dict):
        raise ValueError(f"{caminho}: objeto esperado")
    faltam, sobram = set(chaves) - set(dados), set(dados) - set(chaves)
    if faltam or sobram:
        raise ValueError(f"{caminho}: chaves faltando {sorted(faltam)} ou sobrando "
                         f"{sorted(sobram)}")


def _validar_ic(bloco, caminho: str) -> None:
    _chaves_exatas(bloco, ("valor", "ic95"), caminho)
    if bloco["valor"] is None:
        if bloco["ic95"] is not None:
            raise ValueError(f"{caminho}: IC sem valor")
        return
    _real(bloco["valor"], f"{caminho}.valor")
    if bloco["ic95"] is not None:
        ic = bloco["ic95"]
        if not isinstance(ic, list) or len(ic) != 2:
            raise ValueError(f"{caminho}.ic95: lista de dois números esperada")
        _real(ic[0], f"{caminho}.ic95")
        _real(ic[1], f"{caminho}.ic95")
        if ic[0] > ic[1]:
            raise ValueError(f"{caminho}.ic95: limite inferior maior que o superior")


def _validar_alertas(bloco, caminho: str) -> None:
    _chaves_exatas(bloco, ("alertas", "recall", "precisao"), caminho)
    _contagem_publicada_valida(bloco["alertas"], f"{caminho}.alertas")
    _validar_ic(bloco["recall"], f"{caminho}.recall")
    _validar_ic(bloco["precisao"], f"{caminho}.precisao")
    if bloco["alertas"] == SUPRIMIDA:  # com 1 a 9 alertas, recall e precisão não saem (R7)
        for chave in ("recall", "precisao"):
            if bloco[chave]["valor"] is not None:
                raise ValueError(f"{caminho}.{chave}: com alertas \"<10\" não sai valor (R7)")


def _validar_caixa(caixa, caminho: str) -> None:
    _chaves_exatas(caixa, ("previsto", "observado", "ic95", "casos"), caminho)
    casos = caixa["casos"]
    if casos == "<10":
        if any(caixa[c] is not None for c in ("previsto", "observado", "ic95")):
            raise ValueError(f"{caminho}: caixa com menos de 10 casos não pode ter valores (R7)")
        return
    _inteiro(casos, f"{caminho}.casos", minimo=R7_MINIMO)
    if caixa["previsto"] is not None:
        _real(caixa["previsto"], f"{caminho}.previsto")
    if caixa["observado"] is None:
        if caixa["ic95"] is not None:
            raise ValueError(f"{caminho}: IC sem taxa observada")
        return
    _real(caixa["observado"], f"{caminho}.observado")
    if caixa["ic95"] is not None:
        _validar_ic({"valor": caixa["observado"], "ic95": caixa["ic95"]}, caminho)


def validar_agregados(dados: dict) -> None:
    """Recusa (ValueError) o que não está no formato do contrato de `metricas.json`.

    Confere as chaves exatas, os tipos, os IC (lo <= hi), as leituras da lista, a referência sem
    diferença contra si mesma, e o R7 (contagens de 1 a 9 não saem; caixa com menos de 10 casos ou
    eventos sem taxa). Não verifica a origem dos números: isso é do orquestrador.
    """
    _chaves_exatas(dados, CHAVES_TOPO, "raiz")
    _inteiro(dados["ano"], "ano")
    _inteiro(dados["reamostras"], "reamostras", minimo=1)
    _inteiro(dados["semente"], "semente")
    modelos = dados["modelos"]
    if (not isinstance(modelos, list) or not modelos or len(set(modelos)) != len(modelos)
            or not all(isinstance(m, str) and m for m in modelos)):
        raise ValueError("modelos: lista de ids distintos esperada")
    if dados["modelo_de_referencia"] != MODELO_DE_REFERENCIA or MODELO_DE_REFERENCIA not in modelos:
        raise ValueError("modelo_de_referencia: deve ser m1_main e estar em modelos")
    conjunto = set(modelos)

    pops = dados["populacoes"]
    _chaves_exatas(pops, POPULACOES, "populacoes")
    for pop in POPULACOES:
        info = pops[pop]
        _chaves_exatas(info, ("nome", "casos", "eventos", "prevalencia"), f"populacoes.{pop}")
        if not isinstance(info["nome"], str):
            raise ValueError(f"populacoes.{pop}.nome: texto esperado")
        _contagem_publicada_valida(info["casos"], f"populacoes.{pop}.casos")
        _contagem_publicada_valida(info["eventos"], f"populacoes.{pop}.eventos")
        if isinstance(info["casos"], int) and isinstance(info["eventos"], int):
            if info["eventos"] > info["casos"]:
                raise ValueError(f"populacoes.{pop}: mais eventos que casos")
        if info["prevalencia"] is not None:
            _real(info["prevalencia"], f"populacoes.{pop}.prevalencia")

    for pop in POPULACOES:
        _chaves_exatas(dados["metricas"][pop], conjunto, f"metricas.{pop}")
        for m in modelos:
            bloco = dados["metricas"][pop][m]
            if bloco is None:
                continue
            _chaves_exatas(bloco, METRICAS, f"metricas.{pop}.{m}")
            for metrica in METRICAS:
                if bloco[metrica] is not None:
                    _validar_ic(bloco[metrica], f"metricas.{pop}.{m}.{metrica}")
        _chaves_exatas(dados["diferencas_pr_auc_vs_referencia"][pop], conjunto,
                       f"diferencas.{pop}")
        if dados["diferencas_pr_auc_vs_referencia"][pop][MODELO_DE_REFERENCIA] is not None:
            raise ValueError("diferencas: a referência não se compara consigo mesma (null)")
        for m in modelos:
            dif = dados["diferencas_pr_auc_vs_referencia"][pop][m]
            if dif is None:
                continue
            _chaves_exatas(dif, ("valor", "ic95", "leitura"), f"diferencas.{pop}.{m}")
            _validar_ic({"valor": dif["valor"], "ic95": dif["ic95"]}, f"diferencas.{pop}.{m}")
            if dif["leitura"] not in LEITURAS:
                raise ValueError(f"diferencas.{pop}.{m}: leitura fora de {LEITURAS}")
            if dif["leitura"] != _leitura_do_ic(dif["ic95"]):
                raise ValueError(f"diferencas.{pop}.{m}: leitura {dif['leitura']!r} não bate com "
                                 f"o IC {dif['ic95']}")
        _chaves_exatas(dados["orcamentos"][pop], conjunto, f"orcamentos.{pop}")
        for m in modelos:
            por_orc = dados["orcamentos"][pop][m]
            if por_orc is None:
                continue
            _chaves_exatas(por_orc, tuple(_rotulo(b) for b in (0.05, 0.10, 0.14)),
                           f"orcamentos.{pop}.{m}")
            for rotulo, bloco in por_orc.items():
                _validar_alertas(bloco, f"orcamentos.{pop}.{m}.{rotulo}")

    _chaves_exatas(dados["no_limiar_proprio"], conjunto, "no_limiar_proprio")
    for m in modelos:
        bloco = dados["no_limiar_proprio"][m]
        if bloco is None:
            continue
        _chaves_exatas(bloco, ("limiar", "alertas", "recall", "precisao"),
                       f"no_limiar_proprio.{m}")
        _real(bloco["limiar"], f"no_limiar_proprio.{m}.limiar")
        _validar_alertas({"alertas": bloco["alertas"], "recall": bloco["recall"],
                          "precisao": bloco["precisao"]}, f"no_limiar_proprio.{m}")

    curva = dados["curva_decisao"]
    _chaves_exatas(curva, conjunto | {"limiares"}, "curva_decisao")
    limiares = curva["limiares"]
    if not isinstance(limiares, list) or not limiares:
        raise ValueError("curva_decisao.limiares: lista não vazia")
    for t in limiares:
        _real(t, "curva_decisao.limiares")
        if not 0 < t < 1:
            raise ValueError("curva_decisao.limiares: fora de (0, 1)")
    for m in modelos:
        if not isinstance(curva[m], list) or len(curva[m]) != len(limiares):
            raise ValueError(f"curva_decisao.{m}: um valor por limiar")
        for v in curva[m]:
            _real(v, f"curva_decisao.{m}")

    _chaves_exatas(dados["calibracao"], conjunto, "calibracao")
    for m in modelos:
        if not isinstance(dados["calibracao"][m], list):
            raise ValueError(f"calibracao.{m}: lista de caixas esperada")
        for i, caixa in enumerate(dados["calibracao"][m]):
            _validar_caixa(caixa, f"calibracao.{m}[{i}]")

    _chaves_exatas(dados["conformidade"], conjunto, "conformidade")
    for m in modelos:
        conf = dados["conformidade"][m]
        _chaves_exatas(conf, CONFORMIDADE, f"conformidade.{m}")
        for chave in ("r3_sem_correcao", "r4_variaveis_no_dicionario",
                      "treino_sem_ano_de_comparacao", "externo"):
            if not isinstance(conf[chave], bool):
                raise ValueError(f"conformidade.{m}.{chave}: bool esperado")
        if conf["versoes_diferentes_do_treino"] is not None and not isinstance(
                conf["versoes_diferentes_do_treino"], bool):
            raise ValueError(f"conformidade.{m}.versoes_diferentes_do_treino: bool ou null")


# --- Escrita: metricas.json e os .md gerados dele ------------------------------------------------

def _rodape(r: dict) -> str:
    return (f"Ano de comparação {r['ano']} · avaliação única (R2) · só agregados (R7; células com "
            f"menos de 10 suprimidas) · IC 95% por bootstrap pareado: {r['reamostras']} "
            f"reamostras, semente {r['semente']}.")


def _celula(bloco, casas: int) -> str:
    if bloco is None:
        return "não estima"
    return ta.ic_txt(bloco, casas)


def _contagem_md(valor) -> str | int:
    return valor if isinstance(valor, str) else ta.celula(valor)


def _cel_orc(bloco: dict, casas: int) -> str:
    """Recall ou precisão de um orçamento: null (R7) vira "<10"; senão valor e IC."""
    return "<10" if bloco["valor"] is None else ta.ic_txt(bloco, casas)


def _so_ic(ic: list[float] | None, casas: int) -> str:
    if ic is None:
        return "IC indisponível"
    return f"({ta.num(ic[0], casas)}; {ta.num(ic[1], casas)})"


def _rotulo_pct(rotulo: str) -> str:
    return f"{float(rotulo) * 100:.0f}%"


def markdown_metricas(r: dict) -> str:
    linhas = ["# Métricas da comparação em 2025", "", _rodape(r), "",
              "## Populações", ""]
    corpo = [[pop, r["populacoes"][pop]["nome"], _contagem_md(r["populacoes"][pop]["casos"]),
              _contagem_md(r["populacoes"][pop]["eventos"]),
              ta.num(r["populacoes"][pop]["prevalencia"], 5)] for pop in POPULACOES]
    linhas += ta._tabela_md(["População", "Descrição", "Casos", "Eventos", "Prevalência"], corpo)
    cabecalho = ["Modelo", "PR-AUC", "ROC-AUC", "Brier", "Slope", "Intercepto",
                 "Observado/esperado"]
    for pop in POPULACOES:
        linhas += ["", f"## Métricas sem limiar: população {pop}", ""]
        corpo = []
        for m in r["modelos"]:
            bloco = r["metricas"][pop][m]
            if bloco is None:
                corpo.append([m] + ["não estima"] * len(METRICAS))
                continue
            corpo.append([m] + [_celula(bloco[k], 3) for k in METRICAS])
        linhas += ta._tabela_md(cabecalho, corpo)
    return "\n".join(linhas) + "\n"


def markdown_diferencas(r: dict) -> str:
    linhas = ["# Diferenças de PR-AUC contra o M1", "", _rodape(r), "",
              "Diferença = PR-AUC do modelo − PR-AUC do `m1_main`, com as mesmas reamostras "
              "(pareada). Positiva: o modelo supera o M1. Leitura \"melhor\" se o IC 95% fica "
              "acima de 0; \"pior\" se fica abaixo; \"sem diferença detectável\" se o IC inclui "
              "0 (SC-09)."]
    for pop in POPULACOES:
        linhas += ["", f"## População {pop}", ""]
        corpo = []
        for m in r["modelos"]:
            dif = r["diferencas_pr_auc_vs_referencia"][pop][m]
            if m == r["modelo_de_referencia"]:
                corpo.append([m, "referência", "—", "—"])
            elif dif is None:
                corpo.append([m, "não estima", "—", "—"])
            else:
                corpo.append([m, ta.num(dif["valor"], 4), _so_ic(dif["ic95"], 4),
                              dif["leitura"]])
        linhas += ta._tabela_md(["Modelo", "Diferença", "IC 95%", "Leitura"], corpo)
    return "\n".join(linhas) + "\n"


def markdown_orcamentos(r: dict) -> str:
    linhas = ["# Recall e precisão por orçamento de alertas e no limiar próprio", "", _rodape(r),
              "", "Orçamento X%: os X% de casos de maior risco viram alerta (empate de risco "
              "desempatado pela LINHA). Limiar próprio: só informação, do manifesto."]
    for pop in POPULACOES:
        for orcamento in sorted(r["orcamentos"][pop][r["modelos"][0]] or {}, key=float):
            linhas += ["", f"## População {pop}, orçamento {_rotulo_pct(orcamento)}", ""]
            corpo = []
            for m in r["modelos"]:
                por_orc = r["orcamentos"][pop][m]
                if por_orc is None:
                    corpo.append([m, "não estima", "—", "—"])
                    continue
                bloco = por_orc[orcamento]
                corpo.append([m, _contagem_md(bloco["alertas"]), _cel_orc(bloco["recall"], 3),
                              _cel_orc(bloco["precisao"], 4)])
            linhas += ta._tabela_md(["Modelo", "Alertas", "Recall (IC 95%)", "Precisão (IC 95%)"],
                                    corpo)
    linhas += ["", "## Limiar próprio de cada modelo (população principal; só informação)", ""]
    corpo = []
    for m in r["modelos"]:
        bloco = r["no_limiar_proprio"][m]
        if bloco is None:
            corpo.append([m, "sem limiar", "—", "—", "—"])
            continue
        corpo.append([m, ta.num(bloco["limiar"], 6), _contagem_md(bloco["alertas"]),
                      _cel_orc(bloco["recall"], 3), _cel_orc(bloco["precisao"], 4)])
    linhas += ta._tabela_md(["Modelo", "Limiar", "Alertas", "Recall (IC 95%)", "Precisão (IC 95%)"],
                            corpo)
    return "\n".join(linhas) + "\n"


def markdown_conformidade(r: dict) -> str:
    def sn(v: bool | None) -> str:
        if v is None:
            return "não determinado"
        return "sim" if v else "não"

    linhas = ["# Conformidade dos modelos (R3 a R6)", "", _rodape(r), "",
              "Reporta, não exclui (D-97 f). \"Versões iguais ao treino\" é não determinado "
              "quando o ambiente de treino não declara as versões. \"Externo\" = modelo de outra "
              "branch, carregado em worktree e ambiente isolados."]
    corpo = []
    for m in r["modelos"]:
        c = r["conformidade"][m]
        corpo.append([m, sn(c["r3_sem_correcao"]), sn(c["r4_variaveis_no_dicionario"]),
                      sn(c["treino_sem_ano_de_comparacao"]),
                      sn(None if c["versoes_diferentes_do_treino"] is None
                         else not c["versoes_diferentes_do_treino"]),
                      sn(c["externo"])])
    linhas += ["", *ta._tabela_md(["Modelo", "R3 sem correção", "R4 variáveis no dicionário",
                                   "Treino sem 2025", "Versões iguais ao treino", "Externo"],
                                  corpo)]
    return "\n".join(linhas) + "\n"


def escrever_agregados(destino: str | Path, resultado: dict) -> list[Path]:
    """Valida e grava `metricas.json` e os `.md` gerados dele em `destino`. Devolve os caminhos."""
    validar_agregados(resultado)
    pasta = Path(destino)
    pasta.mkdir(parents=True, exist_ok=True)
    caminho_json = pasta / "metricas.json"
    caminho_json.write_text(json.dumps(resultado, indent=2, ensure_ascii=False, allow_nan=False)
                            + "\n", encoding="utf-8")
    arquivos = [caminho_json]
    textos = {
        "metricas.md": markdown_metricas(resultado),
        "diferencas.md": markdown_diferencas(resultado),
        "orcamentos.md": markdown_orcamentos(resultado),
        "conformidade.md": markdown_conformidade(resultado),
    }
    for nome, texto in textos.items():
        caminho = pasta / nome
        caminho.write_text(texto, encoding="utf-8")
        arquivos.append(caminho)
    return arquivos
