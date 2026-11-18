"""Calibração, limiar e seleção do M1 (T-4.9, FR-07, FR-08, FR-17, D-53, R1, R3, R7, R8).

Gancho `dengue_sinan.selecao:executar` do fim da sessão (`runner.GANCHOS_PADRAO`). Recebe a
configuração e o resultado de cada modelo (`resultados[modelo]["pasta"]` é a pasta com o
`oof.parquet`, o `metricas.json` e o `parametros.json`) e faz, nesta ordem:

1. **Carga**: as predições fora da dobra (OOF, 2022–23) de cada candidato e as dos baselines
   B0, B1 e B2 (`<dados>/oof/oof_<B>.parquet`, gravadas pelo T-2.8). Todas precisam estar na
   mesma ordem de linhas (ANO, região e alvo iguais). Passa pela guarda R1.
2. **Calibração**: para cada candidato, isotônica e Platt. A escolha é a de menor Brier **fora da
   dobra**: o calibrador de cada região é ajustado nas outras quatro e aplicado à região deixada
   de fora (plan › Regra de seleção, "fora da dobra"). O calibrador vencedor é reajustado nas
   predições OOF inteiras e gravado (`<dados>/m1/<modelo>/calibrador.{json,npz}`).
3. **Limiar**: `metrics.best_f2_threshold` nas predições OOF calibradas (FR-08, D-33).
4. **Bootstrap pareado** (`metrics.paired_bootstrap_pr_auc`, uma passagem para todos os modelos,
   mesmos sorteios): IC 95% da PR-AUC média de cada modelo e de cada par (15 pares com B1).
   É só reportado em `reports/m1/comparacao_pareada.md`, e a seleção **não** lê a tabela de pares.
5. **Seleção**: `escolher_modelo` aplica a regra do plan, com os resumos dos candidatos.
6. **Saídas**: `<dados>/m1/selecao.json` (vencedor, motivo, limiar, calibrador), registro no MLflow
   (run `selecao`) e os dois relatórios em `reports/m1/`, só com agregados (R7).

Guarda R1 (documentação, sem mudança de comportamento): a checagem `assert_dev_only` fica em
`_ler_oof`, na carga do OOF. Os auxiliares públicos que recebem só arrays (`ajustar_platt`,
`ajustar_isotonica`, `brier_fora_da_dobra`, `escolher_calibrador`, `escolher_modelo`) não veem o
ano: quem os chama tem de passar só predições de 2022–23. O gancho `executar` passa pela carga.

Decisões de implementação (registradas no relatório da tarefa):
- O calibrador é guardado em `calibrador.npz` (só números, `allow_pickle=False`) e
  `calibrador.json` (tipo e SHA-256 do `.npz`). Não usa pickle nem joblib: o isotônico são duas
  listas de pontos e a Platt são dois números. A carga confere o hash.
- A PR-AUC da seleção é a das predições brutas, como no T-4.2: a Platt é monotônica (não muda a
  PR-AUC) e a isotônica só agrupa empates. O Brier, o slope, o intercepto e as métricas no limiar
  são das predições calibradas.
- Empate: o critério "diferença < 0,005 ou ICs sobrepostos" vale para a PR-AUC. No desempate por
  Brier usa-se o menor valor exato, porque com prevalência de 0,16% o Brier fica perto de 0,002 e
  uma diferença de 0,005 o tornaria inútil.
"""

from __future__ import annotations

import datetime as dt
import itertools
from dataclasses import dataclass
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
import yaml
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from dengue_sinan import baselines, metrics, tracking, verify
from dengue_sinan.guard import assert_dev_only
from dengue_sinan.runner import (
    _caminho,
    _gravar_atomico,
    _gravar_json,
    _ler_json,
    _sha256,
    pasta_m1,
)

TAREFA = "T-4.9"
NOME_RUN = "selecao"
NOME_SELECAO = "selecao.json"
ARQ_CALIBRADOR_NPZ = "calibrador.npz"
ARQ_CALIBRADOR_JSON = "calibrador.json"
ARQ_ORACAO = "oof.parquet"
ARQ_METRICAS = "metricas.json"
ARQ_PARAMETROS = "parametros.json"
COLUNAS_OOF = ("ANO", "regiao", "y", "p")
BASELINES = ("B0", "B1", "B2")
BASELINE_PAREADO = "B1"  # entra nos pares (D-53); B0 e B2 não têm PR-AUC pareável (B2 é regra)

TIPO_PLATT = "platt"
TIPO_ISOTONICA = "isotonica"
ORDEM_CALIBRADOR = (TIPO_PLATT, TIPO_ISOTONICA)  # empate exato no Brier: a mais simples
_EPS_PROBABILIDADE = 1e-12

PRECISAO_EMPATE_PR_AUC = 0.005  # plan › Regra de seleção (D-53)
# Simplicidade para o último desempate (plan: EN < RF < XGB/CatBoost < MLP < TabFM).
RANK_SIMPLICIDADE = {"elastic_net": 0, "random_forest": 1, "xgboost": 2, "catboost": 2,
                     "mlp": 3, "tabfm": 4}


# --- Calibradores (sem pickle) ----------------------------------------------------------------

def _logit(p) -> np.ndarray:
    p_arr = np.clip(np.asarray(p, dtype=float), _EPS_PROBABILIDADE, 1 - _EPS_PROBABILIDADE)
    return np.log(p_arr / (1 - p_arr))


@dataclass(frozen=True)
class Calibrador:
    """Calibrador de um tipo ("platt" ou "isotonica") com seus números em `arrays`."""

    tipo: str
    arrays: dict[str, np.ndarray]

    def aplicar(self, p) -> np.ndarray:
        """Probabilidade calibrada de cada `p`, em [0, 1]."""
        p_arr = np.asarray(p, dtype=float)
        if self.tipo == TIPO_PLATT:
            z = self.arrays["coef"][0] * _logit(p_arr) + self.arrays["intercepto"][0]
            return 1.0 / (1.0 + np.exp(-z))
        if self.tipo == TIPO_ISOTONICA:
            x, y = self.arrays["x"], self.arrays["y"]
            # mesma regra do sklearn com out_of_bounds="clip": interpolação linear entre os nós
            return np.interp(np.clip(p_arr, x[0], x[-1]), x, y)
        raise ValueError(f"tipo de calibrador desconhecido: {self.tipo!r}")


def ajustar_platt(p, y) -> Calibrador:
    """Platt: logística de y em logit(p), sem penalização (R3: sem pesos de classe)."""
    modelo = LogisticRegression(C=np.inf, solver="lbfgs", max_iter=1000)
    modelo.fit(_logit(p).reshape(-1, 1), np.asarray(y))
    return Calibrador(TIPO_PLATT, {
        "coef": modelo.coef_[0].astype(float),
        "intercepto": modelo.intercept_.astype(float),
    })


def ajustar_isotonica(p, y) -> Calibrador:
    """Isotônica: função não decrescente de p, ajustada por PAV (sklearn), com saída em [0, 1]."""
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    iso.fit(np.asarray(p, dtype=float), np.asarray(y, dtype=float))
    return Calibrador(TIPO_ISOTONICA, {
        "x": iso.X_thresholds_.astype(float),
        "y": iso.y_thresholds_.astype(float),
    })


AJUSTADORES = {TIPO_PLATT: ajustar_platt, TIPO_ISOTONICA: ajustar_isotonica}


def brier_fora_da_dobra(p, y, dobra, ajustar) -> tuple[float, np.ndarray]:
    """Brier das predições calibradas com o calibrador de cada dobra ajustado nas outras dobras.

    `dobra` é o código inteiro da região de cada linha. Devolve (Brier agrupado, predições
    calibradas fora da dobra). Uma linha nunca é calibrada por um ajuste que a viu.
    """
    p_arr = np.asarray(p, dtype=float)
    y_arr = np.asarray(y)
    cal_fora = np.empty(p_arr.shape, dtype=float)
    for d in np.unique(dobra):
        dentro = dobra == d
        cal_fora[dentro] = ajustar(p_arr[~dentro], y_arr[~dentro]).aplicar(p_arr[dentro])
    return metrics.brier(y_arr, cal_fora), cal_fora


def escolher_calibrador(brier: dict[str, float]) -> str:
    """Tipo com menor Brier fora da dobra. Empate exato: Platt (dois parâmetros, mais simples)."""
    if not brier:
        raise ValueError("nenhum calibrador para escolher")
    return min(brier, key=lambda t: (brier[t], ORDEM_CALIBRADOR.index(t)))


def salvar_calibrador(calibrador: Calibrador, pasta: Path) -> dict:
    """Grava `calibrador.npz` (números) e `calibrador.json` (tipo, chaves e SHA-256 do .npz)."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    destino_npz = pasta / ARQ_CALIBRADOR_NPZ
    _gravar_atomico(destino_npz, lambda tmp: np.savez(tmp, **calibrador.arrays))
    meta = {
        "tipo": calibrador.tipo,
        "arquivo": ARQ_CALIBRADOR_NPZ,
        "chaves": sorted(calibrador.arrays),
        "sha256": _sha256(destino_npz),
    }
    _gravar_json(pasta / ARQ_CALIBRADOR_JSON, meta)
    return meta


def carregar_calibrador(pasta: Path) -> Calibrador:
    """Carrega o calibrador gravado. Recusa SHA-256 que não bate e chaves diferentes."""
    pasta = Path(pasta)
    meta = _ler_json(pasta / ARQ_CALIBRADOR_JSON)
    if meta is None:
        raise ValueError(f"sem {ARQ_CALIBRADOR_JSON} em {pasta}")
    destino = pasta / meta["arquivo"]
    if _sha256(destino) != meta["sha256"]:
        raise ValueError(f"SHA-256 de {destino.name} não bate: calibrador adulterado ou corrompido")
    with np.load(destino, allow_pickle=False) as npz:
        arrays = {chave: np.array(npz[chave]) for chave in npz.files}
    if sorted(arrays) != meta["chaves"]:
        raise ValueError("chaves do calibrador diferentes das gravadas")
    return Calibrador(meta["tipo"], arrays)


# --- Regra de seleção (plan › Regra de seleção) -----------------------------------------------

def _ics_sobrepostos(a: dict, b: dict) -> bool:
    return a["ic_inf"] <= b["ic_sup"] and b["ic_inf"] <= a["ic_sup"]


def escolher_modelo(resumos: dict[str, dict], ordem: list[str]) -> dict:
    """Aplica a regra de seleção aos candidatos e devolve vencedor, empatados e motivo.

    `resumos[modelo]` tem `pr_auc_media`, `ic_inf`, `ic_sup` (IC 95% da PR-AUC média) e `brier`
    (calibrado, fora da dobra). Regra: maior PR-AUC média; empatam com ele os modelos com
    diferença < 0,005 **ou** ICs sobrepostos; entre os empatados, menor Brier; se ainda empatar,
    o mais simples (RANK_SIMPLICIDADE) e, por último, a ordem do config.

    A comparação pareada não é argumento desta função: ela só é reportada (D-53).
    """
    if not resumos:
        raise ValueError("nenhum candidato para escolher")
    desconhecidos = sorted(set(resumos) - set(RANK_SIMPLICIDADE))
    if desconhecidos:
        raise ValueError(f"modelos sem posição de simplicidade: {desconhecidos}")
    ordenados = sorted(resumos, key=lambda m: (-resumos[m]["pr_auc_media"], ordem.index(m)))
    topo = ordenados[0]
    empatados = [topo]
    for modelo in ordenados[1:]:
        diferenca = resumos[topo]["pr_auc_media"] - resumos[modelo]["pr_auc_media"]
        if diferenca < PRECISAO_EMPATE_PR_AUC or _ics_sobrepostos(resumos[topo], resumos[modelo]):
            empatados.append(modelo)

    if len(empatados) == 1:
        motivo = (f"maior PR-AUC média ({_pt(resumos[topo]['pr_auc_media'], 5)}); nenhum modelo "
                  "empatado pela regra (diferença ≥ 0,005 e ICs sem sobreposição)")
        return {"vencedor": topo, "empatados": empatados, "motivo": motivo}

    vencedor = min(empatados, key=lambda m: (resumos[m]["brier"], RANK_SIMPLICIDADE[m],
                                             ordem.index(m)))
    desempate = "menor Brier calibrado fora da dobra"
    if len({resumos[m]["brier"] for m in empatados}) == 1:
        desempate = "mais simples (Brier igual)"
    motivo = (f"maior PR-AUC média: {topo} ({_pt(resumos[topo]['pr_auc_media'], 5)}); empatados "
              f"pela regra (diferença < 0,005 ou ICs sobrepostos): {', '.join(empatados)}; "
              f"desempate por {desempate}")
    return {"vencedor": vencedor, "empatados": empatados, "motivo": motivo}


# --- Carga -------------------------------------------------------------------------------------

@dataclass(frozen=True)
class _Oof:
    """Predições fora da dobra de um modelo, em arrays (sem nomes de região por linha)."""

    ano: np.ndarray
    dobra: np.ndarray  # código inteiro da região, na ordem de cfg["ordem_dobras"]
    y: np.ndarray
    p: np.ndarray


def _ler_oof(caminho: Path, ordem_dobras: list[str]) -> _Oof:
    """Lê as colunas do OOF. A guarda R1 roda aqui: ano de teste levanta RuntimeError."""
    if not caminho.exists():
        raise FileNotFoundError(f"OOF ausente: {caminho}")
    df = pd.read_parquet(caminho, columns=list(COLUNAS_OOF))
    assert_dev_only(df)  # R1
    regioes = set(df["regiao"].unique())
    if not regioes <= set(ordem_dobras):
        raise ValueError(f"{caminho.name}: regiões fora de ordem_dobras: "
                         f"{sorted(regioes - set(ordem_dobras))}")
    codigos = {regiao: i for i, regiao in enumerate(ordem_dobras)}
    return _Oof(
        ano=df["ANO"].to_numpy(dtype=np.int64),
        dobra=df["regiao"].map(codigos).to_numpy(dtype=np.int64),
        y=df["y"].to_numpy(dtype=np.int64),
        p=df["p"].to_numpy(dtype=float),
    )


def _conferir_mesma_ordem(referencia: _Oof, outro: _Oof, nome: str) -> None:
    """Pareamento: todas as predições precisam estar nas mesmas linhas, na mesma ordem."""
    iguais = (
        np.array_equal(referencia.ano, outro.ano)
        and np.array_equal(referencia.dobra, outro.dobra)
        and np.array_equal(referencia.y, outro.y)
    )
    if not iguais:
        raise ValueError(f"{nome}: linhas do OOF fora de ordem em relação ao primeiro candidato; "
                         "a comparação pareada exige as mesmas linhas na mesma ordem")


def _carregar_predicoes(cfg: dict, resultados: dict) -> tuple[dict[str, _Oof], dict[str, _Oof]]:
    ordem_dobras = list(cfg["ordem_dobras"])
    candidatos = {m: _ler_oof(Path(resultados[m]["pasta"]) / ARQ_ORACAO, ordem_dobras)
                  for m in cfg["ordem_modelos"]}
    pasta_baselines = _caminho(cfg, "dados") / "oof"
    base = {b: _ler_oof(pasta_baselines / f"oof_{b}.parquet", ordem_dobras) for b in BASELINES}
    referencia = next(iter(candidatos.values()))
    for nome, oof in [*candidatos.items(), *base.items()]:
        _conferir_mesma_ordem(referencia, oof, nome)
    return candidatos, base


# --- Análise por modelo ------------------------------------------------------------------------

def _pr_por_dobra(oof: _Oof, n_dobras: int) -> np.ndarray:
    return np.array([metrics.pr_auc(oof.y[oof.dobra == d], oof.p[oof.dobra == d])
                     for d in range(n_dobras)], dtype=float)


def _analisar_candidato(oof: _Oof, n_dobras: int) -> dict:
    """Calibração escolhida fora da dobra, calibrador no OOF inteiro, limiar e métricas."""
    brier_por_tipo: dict[str, float] = {}
    for tipo in ORDEM_CALIBRADOR:
        brier_por_tipo[tipo], _ = brier_fora_da_dobra(oof.p, oof.y, oof.dobra, AJUSTADORES[tipo])
    tipo = escolher_calibrador(brier_por_tipo)
    calibrador = AJUSTADORES[tipo](oof.p, oof.y)
    p_cal = calibrador.aplicar(oof.p)
    limiar = metrics.best_f2_threshold(oof.y, p_cal)
    slope, intercepto = metrics.calibration_slope_intercept(oof.y, p_cal)
    pr_dobras = _pr_por_dobra(oof, n_dobras)
    return {
        "calibrador": calibrador,
        "calibrador_tipo": tipo,
        "brier_fora_da_dobra": brier_por_tipo,
        "brier_bruto": metrics.brier(oof.y, oof.p),
        "brier_calibrado": brier_por_tipo[tipo],
        "roc_auc": metrics.roc_auc(oof.y, oof.p),
        "pr_auc_por_dobra": pr_dobras,
        "pr_auc_media": float(pr_dobras.mean()),
        "slope": float(slope),
        "intercepto": float(intercepto),
        "limiar": float(limiar),
        "no_limiar": metrics.threshold_metrics(oof.y, p_cal, limiar),
    }


def _analisar_baseline(nome: str, oof: _Oof, n_dobras: int) -> dict:
    """B0 e B1: predições brutas e limiar de F2 próprio. B2: a regra (sem PR-AUC)."""
    if nome == "B2":
        return {"no_limiar": baselines.metricas_regra(oof.y, oof.p), "limiar": None}
    probabilisticas = baselines.metricas_probabilisticas(oof.y, oof.p)
    limiar = metrics.best_f2_threshold(oof.y, oof.p)
    pr_dobras = _pr_por_dobra(oof, n_dobras)
    return {
        "pr_auc_por_dobra": pr_dobras,
        "pr_auc_media": float(pr_dobras.mean()),
        "roc_auc": probabilisticas["roc_auc"],
        "brier_bruto": probabilisticas["brier"],
        "slope": probabilisticas["calibracao_slope"],
        "intercepto": probabilisticas["calibracao_intercept"],
        "limiar": float(limiar),
        "no_limiar": metrics.threshold_metrics(oof.y, oof.p, limiar),
    }


def _ic_95(valores: np.ndarray) -> tuple[float, float]:
    inf, sup = np.quantile(valores, (0.025, 0.975))
    return float(inf), float(sup)


def _pares(modelos: list[str]) -> list[tuple[str, str]]:
    return list(itertools.combinations(modelos, 2))


def _comparacao_pareada(cfg: dict, escores: dict[str, np.ndarray], pr_fora: dict[str, np.ndarray],
                        y: np.ndarray, dobra: np.ndarray) -> dict:
    """Bootstrap pareado de PR-AUC para os candidatos e B1 (uma passagem, mesmos sorteios).

    `escores` tem as predições brutas de cada modelo do par; `pr_fora` a PR-AUC de cada dobra.
    """
    modelos = list(escores)
    reamostras = int(cfg["bootstrap_pareado"])
    boot = metrics.paired_bootstrap_pr_auc(escores, y, dobra, n=reamostras, seed=int(cfg["seed"]))
    ics = {m: _ic_95(boot["media"][m]) for m in modelos}
    pares = {}
    for a, b in _pares(modelos):
        diferenca_dobras = pr_fora[a] - pr_fora[b]
        estimativa = float(diferenca_dobras.mean())
        ic_inf, ic_sup = _ic_95(boot["media"][a] - boot["media"][b])
        pares[(a, b)] = {
            "diferenca_por_dobra": diferenca_dobras,
            "estimativa": estimativa,
            "ic_inf": ic_inf,
            "ic_sup": ic_sup,
        }
    return {"reamostras": reamostras, "seed": int(cfg["seed"]), "ics": ics, "pares": pares,
            "pr_fora": pr_fora}


# --- Relatórios (R7: só agregados) -------------------------------------------------------------

def _pt(valor, casas: int) -> str:
    return baselines._num(valor, casas)


def _tabela(cabecalho: list[str], linhas: list[list[str]]) -> list[str]:
    alinhamento = ["---"] + ["---:"] * (len(cabecalho) - 1)
    saida = ["| " + " | ".join(cabecalho) + " |", "| " + " | ".join(alinhamento) + " |"]
    saida += ["| " + " | ".join(linha) + " |" for linha in linhas]
    return saida


def _texto_ic(ic: tuple[float, float]) -> str:
    return f"[{_pt(ic[0], 5)}; {_pt(ic[1], 5)}]"


def escrever_relatorio_oof(cfg: dict, analises: dict, base: dict[str, _Oof], pareada: dict,
                           selecao: dict, caminho: Path) -> Path:
    """`reports/m1/comparacao_oof.md`: candidatos e baselines no OOF, e a seleção."""
    dobras = list(cfg["ordem_dobras"])
    minimo = cfg["supressao_min_celula"]
    candidatos = list(cfg["ordem_modelos"])
    cab_dobras = ["Modelo", *dobras, "Média", "IC 95% da média"]
    pr_linhas = []
    for m in [*candidatos, "B0", "B1"]:
        pr = analises[m]["pr_auc_por_dobra"]
        # B0 não entra no bootstrap pareado (é só referência de piso): IC "—".
        ic = _texto_ic(pareada["ics"][m]) if m in pareada["ics"] else "—"
        pr_linhas.append([m, *[_pt(v, 5) for v in pr], _pt(analises[m]["pr_auc_media"], 5), ic])
    pr_linhas.append(["B2", *["—"] * len(dobras), "—", "—"])

    cal_linhas = []
    for m in candidatos:
        a = analises[m]
        cal_linhas.append([m, a["calibrador_tipo"], _pt(a["brier_bruto"], 6),
                           _pt(a["brier_calibrado"], 6), _pt(a["slope"], 3),
                           _pt(a["intercepto"], 3), _pt(a["roc_auc"], 4)])
    for b in ("B0", "B1"):
        a = analises[b]
        cal_linhas.append([b, "—", _pt(a["brier_bruto"], 6), "—", _pt(a["slope"], 3),
                           _pt(a["intercepto"], 3), _pt(a["roc_auc"], 4)])
    cal_linhas.append(["B2", "—", "—", "—", "—", "—", "—"])

    lim_linhas = []
    for m in candidatos:
        a = analises[m]
        t = a["no_limiar"]
        lim_linhas.append([m, _pt(a["limiar"], 6), _pt(t["recall"], 4), _pt(t["precisao"], 4),
                           _pt(t["f2"], 4)])
    for b in ("B0", "B1"):
        a = analises[b]
        t = a["no_limiar"]
        lim_linhas.append([b, _pt(a["limiar"], 6), _pt(t["recall"], 4), _pt(t["precisao"], 4),
                           _pt(t["f2"], 4)])
    t2 = analises["B2"]["no_limiar"]
    lim_linhas.append(["B2", "regra", _pt(t2["recall"], 4), _pt(t2["precisao"], 4),
                       _pt(t2["f2"], 4)])

    busca_linhas = []
    for m in candidatos:
        tun = analises[m]["tuning"]
        busca_linhas.append([m, _pt(tun["t_cronometragem_s"] / 60, 2),
                             _pt(tun["orcamento_s"] / 60, 2),
                             "sim" if tun["subamostra"] else "não",
                             str(tun["tentativas_concluidas"]), str(tun["tentativas_podadas"]),
                             str(tun["tentativas_falhas"])])

    eventos = {dobra: int(base["B0"].y[base["B0"].dobra == i].sum())
               for i, dobra in enumerate(dobras)}
    eventos_linha = [f"{dobra}: {baselines._contagem(eventos[dobra], minimo)}" for dobra in dobras]

    partes = [
        "# Comparação dos candidatos e baselines no OOF (T-4.9)",
        "",
        "Predições fora da dobra (leave-one-region-out) de 2022–23, com as dobras da T-2.3 e a "
        f"semente {cfg['seed']} do config. Ano de teste não lido (R1). Só agregados (R7): contagem "
        f"abaixo de {minimo} aparece como <{minimo}.",
        "",
        "## 1. PR-AUC por dobra (métrica primária, sobre a predição bruta)",
        "",
        *_tabela(cab_dobras, pr_linhas),
        "",
        "IC 95% da média: bootstrap pareado com a semente do config (mesmos sorteios para todos os "
        "modelos). B2 é regra e não tem PR-AUC.",
        "",
        "## 2. Calibração e discriminação (OOF)",
        "",
        "Calibrador: escolhido pelo menor Brier fora da dobra. Brier, slope e intercepto dos "
        "candidatos são os das predições calibradas com o calibrador reajustado no OOF inteiro "
        "(slope e intercepto do calibrado são do próprio OOF, não fora da dobra).",
        "",
        *_tabela(["Modelo", "Calibrador", "Brier bruto", "Brier calibrado (fora da dobra)",
                  "Slope", "Intercepto", "ROC-AUC"], cal_linhas),
        "",
        "## 3. Métricas no limiar",
        "",
        "Candidatos: limiar de F2 máximo nas predições calibradas do OOF. B0 e B1: o mesmo "
        "critério, nas predições brutas. B2: a regra do protocolo.",
        "",
        *_tabela(["Modelo", "Limiar", "Recall", "Precisão", "F2"], lim_linhas),
        "",
        "## 4. Busca de hiperparâmetros (cronometragem, orçamento e tentativas)",
        "",
        *_tabela(["Modelo", "Cronometragem (min)", "Orçamento (min)", "Subamostra",
                  "Tentativas concluídas", "Podadas", "Falhas"], busca_linhas),
        "",
        "## 5. Eventos por dobra (contexto, R7)",
        "",
        "; ".join(eventos_linha),
        "",
        "## 6. Seleção",
        "",
        f"**Vencedor: {selecao['vencedor']}.** {selecao['motivo']}.",
        "",
        f"- Calibrador do vencedor: {analises[selecao['vencedor']]['calibrador_tipo']} "
        "(menor Brier fora da dobra).",
        "- Limiar (F2 máximo, predições calibradas do OOF): "
        f"{_pt(analises[selecao['vencedor']]['limiar'], 6)}.",
        "- A comparação pareada (`comparacao_pareada.md`) é só reportada (D-53).",
    ]
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    _gravar_atomico(caminho, lambda tmp: tmp.write_text("\n".join(partes) + "\n", encoding="utf-8"))
    return caminho


def escrever_relatorio_pareado(cfg: dict, pareada: dict, caminho: Path) -> Path:
    """`reports/m1/comparacao_pareada.md`: diferença de PR-AUC por dobra e IC 95% de cada par."""
    dobras = list(cfg["ordem_dobras"])
    cabecalho = ["Par (A − B)", *dobras, "Diferença média", "IC 95%", "IC exclui 0"]
    linhas = []
    for (a, b), r in pareada["pares"].items():
        exclui = not (r["ic_inf"] <= 0 <= r["ic_sup"])
        diferencas = [_pt(v, 5) for v in r["diferenca_por_dobra"]]
        linhas.append([f"{a} − {b}", *diferencas,
                       _pt(r["estimativa"], 5), _texto_ic((r["ic_inf"], r["ic_sup"])),
                       "sim" if exclui else "não"])
    partes = [
        "# Comparação pareada da PR-AUC (T-4.9, D-53)",
        "",
        "Diferença de PR-AUC (A − B) por dobra e média das dobras, com IC 95% por bootstrap "
        f"pareado: {pareada['reamostras']} reamostras, semente {pareada['seed']}, "
        "estratificadas por "
        "dobra e alvo. Os mesmos sorteios valem para todos os pares.",
        "",
        "**Não entra na seleção.** A regra do plan usa a PR-AUC média e os ICs de cada modelo "
        "(comparacao_oof.md). Esta tabela só informa o que a diferença entre dois modelos mostra.",
        "",
        *_tabela(cabecalho, linhas),
        "",
        "Pares com B1 (logística sem penalização) incluídos. Só agregados (R7).",
    ]
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    _gravar_atomico(caminho, lambda tmp: tmp.write_text("\n".join(partes) + "\n", encoding="utf-8"))
    return caminho


# --- Gancho da sessão --------------------------------------------------------------------------

def _agora() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _populacao_esperada() -> int:
    caminho = verify.REPO / "config" / "esperado.yaml"
    dados = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    return int(dados["desenvolvimento"]["populacao_total"])


def executar(cfg: dict, resultados: dict) -> list[dict]:
    """Gancho `selecao` do runner (T-4.9). Devolve os checks do bloco `selecao`.

    Escreve os calibradores e `selecao.json` em `<dados>/m1/`, o run `selecao` no MLflow e os dois
    relatórios em `<relatorios>/m1/`. Levanta erro se algum OOF faltar, estiver fora de ordem ou
    tiver ano de teste (R1): a sessão para e nada é escolhido.
    """
    dobras = list(cfg["ordem_dobras"])
    candidatos_ordem = list(cfg["ordem_modelos"])
    candidatos, base = _carregar_predicoes(cfg, resultados)
    referencia = candidatos[candidatos_ordem[0]]
    n_dobras = len(dobras)

    analises = {m: _analisar_candidato(candidatos[m], n_dobras) for m in candidatos_ordem}
    for b in BASELINES:
        analises[b] = _analisar_baseline(b, base[b], n_dobras)
    for m in candidatos_ordem:
        parametros = _ler_json(Path(resultados[m]["pasta"]) / ARQ_PARAMETROS)
        if parametros is None or "tuning" not in parametros:
            raise ValueError(f"{m}: sem parametros.json com o bloco tuning (T-4.3b)")
        analises[m]["tuning"] = parametros["tuning"]

    escores = {m: candidatos[m].p for m in candidatos_ordem}
    escores[BASELINE_PAREADO] = base[BASELINE_PAREADO].p
    pr_fora = {m: analises[m]["pr_auc_por_dobra"] for m in escores}
    pareada = _comparacao_pareada(cfg, escores, pr_fora, referencia.y, referencia.dobra)

    resumos = {m: {
        "pr_auc_media": analises[m]["pr_auc_media"],
        "ic_inf": pareada["ics"][m][0],
        "ic_sup": pareada["ics"][m][1],
        "brier": analises[m]["brier_calibrado"],
    } for m in candidatos_ordem}
    escolha = escolher_modelo(resumos, candidatos_ordem)
    vencedor = escolha["vencedor"]

    raiz = pasta_m1(cfg)
    metas = {}
    for m in candidatos_ordem:
        metas[m] = salvar_calibrador(analises[m]["calibrador"], raiz / m)
    recarregado = carregar_calibrador(raiz / vencedor)
    cal_ok = bool(np.array_equal(recarregado.aplicar(candidatos[vencedor].p),
                                 analises[vencedor]["calibrador"].aplicar(candidatos[vencedor].p)))

    selecao = {
        "tarefa": TAREFA,
        "vencedor": vencedor,
        "empatados": escolha["empatados"],
        "motivo": escolha["motivo"],
        "calibrador": analises[vencedor]["calibrador_tipo"],
        "limiar": analises[vencedor]["limiar"],
        "reamostras_pareadas": pareada["reamostras"],
        "semente": pareada["seed"],
        "gerado_em_utc": _agora(),
        "modelos": {m: {
            "pr_auc_media": resumos[m]["pr_auc_media"],
            "ic_95": [resumos[m]["ic_inf"], resumos[m]["ic_sup"]],
            "brier_calibrado": resumos[m]["brier"],
            "brier_fora_da_dobra": analises[m]["brier_fora_da_dobra"],
            "calibrador": analises[m]["calibrador_tipo"],
            "limiar": analises[m]["limiar"],
        } for m in candidatos_ordem},
    }
    _gravar_json(raiz / NOME_SELECAO, selecao)

    relatorio_oof = _caminho(cfg, "relatorios") / "m1" / "comparacao_oof.md"
    relatorio_par = _caminho(cfg, "relatorios") / "m1" / "comparacao_pareada.md"
    escrever_relatorio_oof(cfg, analises, base, pareada, selecao, relatorio_oof)
    escrever_relatorio_pareado(cfg, pareada, relatorio_par)

    with tracking.start_run(cfg, NOME_RUN, tags={"etapa": TAREFA}):
        mlflow.log_params({
            "selecao.vencedor": vencedor,
            "selecao.motivo": escolha["motivo"],
            "selecao.empatados": ",".join(escolha["empatados"]),
            "selecao.calibrador": analises[vencedor]["calibrador_tipo"],
            "selecao.reamostras": str(pareada["reamostras"]),
        })
        mlflow.log_metrics({
            "selecao.limiar": analises[vencedor]["limiar"],
            "selecao.pr_auc_media": resumos[vencedor]["pr_auc_media"],
            "selecao.brier_calibrado": resumos[vencedor]["brier"],
        })
        mlflow.log_dict(selecao, NOME_SELECAO)

    anos = set(np.unique(referencia.ano).tolist())
    max_diferenca = 0.0
    for m in candidatos_ordem:
        metricas = _ler_json(Path(resultados[m]["pasta"]) / ARQ_METRICAS)
        if metricas is None:
            max_diferenca = float("inf")
            break
        diferenca = abs(metricas["pr_auc_media"] - resumos[m]["pr_auc_media"])
        max_diferenca = max(max_diferenca, diferenca)

    limiar = analises[vencedor]["limiar"]
    arquivos = [raiz / NOME_SELECAO, relatorio_oof, relatorio_par,
                *[raiz / m / ARQ_CALIBRADOR_JSON for m in candidatos_ordem]]
    esperado_pares = len(_pares([*candidatos_ordem, BASELINE_PAREADO]))
    return [
        verify.check("candidatos_com_oof", len(candidatos_ordem), len(candidatos)),
        verify.check("linhas_oof", _populacao_esperada(), len(referencia.y)),
        verify.check("anos_do_oof_no_desenvolvimento", True,
                     bool(anos <= set(int(a) for a in cfg["anos_dev"]))),
        verify.check("pr_auc_confere_com_cv", True, bool(max_diferenca <= 1e-9)),
        verify.check("pares_calculados", esperado_pares, len(pareada["pares"])),
        verify.check("reamostras_pareadas", int(cfg["bootstrap_pareado"]), pareada["reamostras"]),
        verify.check("modelo_unico_escolhido", True, vencedor in candidatos_ordem),
        verify.check("calibrador_recarregado_igual", True, cal_ok),
        verify.check("limiar_no_intervalo", True, bool(0.0 <= limiar <= 1.0)),
        verify.check("arquivos_gerados", True, all(Path(a).exists() for a in arquivos)),
    ]
