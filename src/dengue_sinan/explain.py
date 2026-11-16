"""Modelo explicativo E1: logística sem penalização para associação ajustada (T-3.1 e T-3.2).

A T-3.2 (OR, RERI, AP, BH e ranking) fica no fim do módulo, a partir do ajuste salvo.

Spec: FR-05, FR-19, D-40, D-41; [plan › Modelo explicativo (E1)](../../specs/plan.md);
R9 (sem penalização), R7 (só agregados), P6 (associação, não causa).

Ajustado em 2022–23 com todos os dados de desenvolvimento, sem dobras: é inferência, não predição.
`guard.assert_dev_only` roda no início de `ajustar_e1` (R1).

Termos do E1 (ordem do código):
- idade: spline natural com 5 graus de liberdade (gl), sem constante própria;
- sexo: F é a referência; M e I entram como indicadores;
- gestante: 0/1;
- cada comorbidade: 3 níveis, referência "Não"; "Ausente" é um nível próprio (D-07);
- interações 2 a 2: produto dos indicadores "Sim" só dos pares com >= 10 eventos, lidos de
  `data/descritiva/pares_comorbidades.csv` (T-2.6). Os outros pares ficam de fora, como
  "eventos insuficientes". "Ausente" nunca entra em interação;
- HIPERTENSA e DIABETES x spline da idade com 3 gl (indicador "Sim"), **centrada na idade de
  referência `IDADE_REFERENCIA` (40)**: a coluna é `Sim * (B_j(idade) - B_j(40))`. Assim o efeito
  principal de "DIABETES: Sim" e "HIPERTENSA: Sim" é o log-OR aos 40 anos. É só reparametrização:
  o espaço de colunas é o mesmo e o modelo e as previsões não mudam.

Decisões de implementação (small, reversíveis, listadas no relatório da T-3.1):
- Spline próprio em vez de `patsy.cr`. O `cr(df=5)` do patsy inclui a constante, então colide
  com o intercepto (posto 5 de 6, medido). Além disso, os nós e o centro dele são calculados
  sobre as linhas que recebe. Com dados agrupados, isso mudaria o modelo. Aqui os nós vêm dos
  quantis das linhas da população e são guardados no ajuste (`nos`). A base tem gl colunas sem
  constante, como `ns(df=)` do R.
- Ajuste agrupado: a logística depende das covariáveis só pelo padrão (idade exata, sexo,
  gestante, níveis das 7 comorbidades). Por isso ajustamos um GLM binomial com resposta
  [eventos, não eventos] por padrão. É a mesma MLE e a mesma covariância, porque a logística
  tem a soma dos eventos por padrão como estatística suficiente. `checar_equivalencia` confere
  que a log-verossimilhança, o escore e a informação são iguais nas duas formas, no ponto ajustado
  e numa amostra aleatória. Ajustar as duas formas na amostra não converge: alguns termos raros
  (comorbidade "Ausente", sexo I, pares) ficam sem eventos nela.
  Agrupamos pela idade em anos fracionários exatos, e não em anos inteiros: arredondar a idade
  mudaria a variável que o spline vê. Na prática, quase todas as idades já são inteiras.
- Supressão (R7): o coeficiente de um termo de comorbidade, de sexo ou de gestante com menos de
  `supressao_min_celula` eventos no nível não é publicado. Os valores ficam no ajuste interno.
"""

from __future__ import annotations

import itertools
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import yaml

from dengue_sinan import dataset, descriptive, verify
from dengue_sinan.config import load_config
from dengue_sinan.guard import assert_dev_only
from dengue_sinan.profiling import COMORBIDADES, FAIXAS, FAIXAS_ROTULOS, parse_date

if TYPE_CHECKING:  # só para anotar: ler o E1 salvo (T-3.6) não precisa do statsmodels
    from statsmodels.genmod.generalized_linear_model import GLMResults

logger = logging.getLogger(__name__)

COLUNA_IDADE = "idade_anos"
GL_IDADE = 5          # spline da idade no efeito principal (`[ASSUMPTION]` do spec, mantido)
GL_IDADE_INTERACAO = 3  # spline da idade nas interações com HIPERTENSA e DIABETES
# Idade em que "DIABETES: Sim" e "HIPERTENSA: Sim" valem como log-OR. O OR muda com a idade:
# a leitura por faixa etária é feita na T-3.2 com `log_or_na_idade`.
IDADE_REFERENCIA = 40
MIN_EVENTOS_PAR = 10  # interação entra no E1 só com >= 10 eventos (spec, plan › E1)
TAMANHO_AMOSTRA_EQUIVALENCIA = 200_000
TOLERANCIA_EQUIVALENCIA = 1e-8  # diferença relativa máxima entre as duas formas
Z95 = 1.959963984540054
COM_IDADE = ("HIPERTENSA", "DIABETES")  # comorbidades com interação com a idade (T-3.1)
ALFA_FDR = 0.05  # Benjamini-Hochberg nos pares (D-40)
N_SIMULACOES = 10_000  # conferência do método delta em RERI e AP (T-3.2)
CHAVES_PADRAO = [COLUNA_IDADE, "sexo", "gestante", *COMORBIDADES]
PARES = list(itertools.combinations(COMORBIDADES, 2))  # 21 pares (D-52)
NOME_RESULTADOS = "e1_resultados.pickle"
NOME_METADADOS = "e1_metadados.json"
AVISO_P6 = (
    "> **Modelo explicativo: associação, não causa (P6).** Os coeficientes são associações "
    "ajustadas por idade e sexo, não efeitos causais. Descrevem o modelo, não o mundo."
)


@dataclass
class E1Ajustado:
    """Resultado do E1 com os metadados para previsão e relatório. Não guarda linhas (R7)."""

    resultados: GLMResults
    colunas: list[str]
    nos: dict[str, list[float]]
    pares_incluidos: list[tuple[str, str]]
    pares_excluidos: list[tuple[str, str]]
    eventos_por_termo: dict[str, int]
    n_casos: int
    n_eventos: int
    n_padroes: int
    tempo_ajuste_s: float
    log_verossimilhanca: float

    @property
    def params(self) -> np.ndarray:
        """Coeficientes β na ordem de `colunas`: o que o risco e os contrastes leem."""
        return np.asarray(self.resultados.params, dtype=float)

    @property
    def cov(self) -> np.ndarray:
        """Covariância de β (Σ), na mesma ordem: base dos IC pelo método delta."""
        return np.asarray(self.resultados.cov_params(), dtype=float)

    @property
    def idade_referencia(self) -> int:
        return IDADE_REFERENCIA


# --- Splines e desenho -------------------------------------------------------------------------

def _nos(idade: np.ndarray, gl: int) -> list[float]:
    """gl + 1 nós: os dois extremos dos dados e gl - 1 quantis igualmente espaçados.

    Os quantis vêm das linhas (uma por caso), não dos padrões agrupados.
    """
    interiores = np.quantile(idade, np.arange(1, gl) / gl)
    nos = [float(idade.min()), *map(float, interiores), float(idade.max())]
    if any(b <= a for a, b in itertools.pairwise(nos)):
        raise ValueError(f"nós da idade não estritamente crescentes: {nos}")
    return nos


def _base_spline(x: np.ndarray, nos: list[float]) -> np.ndarray:
    """Base natural cúbica sem constante (Hastie et al., ESL eq. 5.4-5.5): x e N3..NK.

    Tem len(nos) - 1 colunas, ou seja, gl colunas. Linear para além dos extremos.
    """
    k = len(nos)

    def d(j: int) -> np.ndarray:
        return (np.maximum(x - nos[j], 0) ** 3 - np.maximum(x - nos[-1], 0) ** 3) / (
            nos[-1] - nos[j])

    return np.column_stack([x, *(d(j) - d(k - 2) for j in range(k - 2))])


def matriz_de_desenho(df: pd.DataFrame, nos: dict[str, list[float]],
                      pares: list[tuple[str, str]]) -> pd.DataFrame:
    """Matriz do E1 (com intercepto) para as linhas de `df`, na ordem fixa de `colunas`.

    `df` é linha a linha ou agrupada por `CHAVES_PADRAO` (mesmas colunas). Os nós vêm de fora,
    para o mesmo desenho servir ao ajuste, à checagem de equivalência e à previsão de perfis.
    """
    idade = df[COLUNA_IDADE].to_numpy(dtype=float)
    sim = {c: (df[c] == "Sim").to_numpy(dtype=float) for c in COMORBIDADES}
    colunas: dict[str, np.ndarray] = {"Intercepto": np.ones(len(df))}
    base = _base_spline(idade, nos["idade"])
    for j in range(base.shape[1]):
        colunas[f"Idade (spline) {j + 1}"] = base[:, j]
    for nivel in ("M", "I"):
        colunas[f"Sexo: {nivel} (ref. F)"] = (df["sexo"] == nivel).to_numpy(dtype=float)
    colunas["Gestante: Sim"] = df["gestante"].to_numpy(dtype=float)
    for c in COMORBIDADES:
        colunas[f"{c}: Ausente"] = (df[c] == "Ausente").to_numpy(dtype=float)
        colunas[f"{c}: Sim"] = sim[c]
    for a, b in pares:
        colunas[f"{a} x {b}"] = sim[a] * sim[b]
    interacao = _base_spline(idade, nos["idade_interacao"])
    referencia = _base_spline(np.array([float(IDADE_REFERENCIA)]), nos["idade_interacao"])[0]
    for c in ("HIPERTENSA", "DIABETES"):
        for j in range(interacao.shape[1]):
            colunas[f"{c} x Idade (spline) {j + 1}"] = sim[c] * (interacao[:, j] - referencia[j])
    return pd.DataFrame(colunas, index=df.index)


def _contraste_or(e1: E1Ajustado, comorbidade: str, idade: float) -> np.ndarray:
    """Vetor c tal que c @ β é o log-OR de `comorbidade` na `idade` (ver `log_or_na_idade`).

    Só DIABETES e HIPERTENSA têm termo com a idade; para as outras, c é o indicador "Sim".
    """
    if comorbidade not in COMORBIDADES:
        raise ValueError(f"comorbidade desconhecida: {comorbidade}")
    colunas = list(e1.colunas)
    contraste = np.zeros(len(colunas))
    contraste[colunas.index(f"{comorbidade}: Sim")] = 1.0
    if comorbidade in COM_IDADE:
        base = _base_spline(np.array([float(idade), float(IDADE_REFERENCIA)]),
                            e1.nos["idade_interacao"])
        dif = base[0] - base[1]
        for j, valor in enumerate(dif):
            contraste[colunas.index(f"{comorbidade} x Idade (spline) {j + 1}")] = valor
    return contraste


def log_or_na_idade(e1: E1Ajustado, comorbidade: str, idade: float) -> dict[str, float]:
    """Log-OR de `comorbidade` = Sim contra Não, na `idade`, com os demais termos fixos.

    Contraste linear sobre o ajuste: β["<C>: Sim"] + Σ_j γ_j (B_j(idade) − B_j(IDADE_REFERENCIA)),
    com a base da interação e os nós do ajuste. Devolve estimativa, erro-padrão e IC 95% pela
    covariância dos coeficientes. Para o OR, use exp(estimativa) e exp(IC). Para comorbidades
    sem termo com a idade, a idade não muda o resultado.
    """
    contraste = _contraste_or(e1, comorbidade, idade)
    beta = e1.params
    cov = e1.cov
    estimativa = float(contraste @ beta)
    erro = float(np.sqrt(contraste @ cov @ contraste))
    return {
        "idade": float(idade),
        "estimativa": estimativa,
        "erro_padrao": erro,
        "ic_inferior": estimativa - Z95 * erro,
        "ic_superior": estimativa + Z95 * erro,
    }


# --- Pares (arquivo de T-2.6) ------------------------------------------------------------------

def _caminho_pares(cfg: dict) -> Path:
    return Path(cfg["caminhos"]["dados"]) / "descritiva" / "pares_comorbidades.csv"


def ler_pares(caminho: Path) -> pd.DataFrame:
    """Lê o arquivo de contagens de pares e confere que traz os 21 pares, sem repetição."""
    tabela = pd.read_csv(caminho)
    esperadas = {"comorbidade_1", "comorbidade_2", "casos", "eventos"}
    if not esperadas.issubset(tabela.columns):
        raise ValueError(f"{caminho}: faltam as colunas {sorted(esperadas - set(tabela.columns))}")
    pares = set(zip(tabela["comorbidade_1"], tabela["comorbidade_2"], strict=True))
    if pares != set(PARES) or len(tabela) != len(PARES):
        raise ValueError(f"{caminho}: esperados os {len(PARES)} pares das 7 comorbidades")
    return tabela


def pares_do_arquivo(
    tabela: pd.DataFrame,
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Separa os pares em (incluídos, eventos insuficientes) pelo mínimo de 10 eventos."""
    incluidos, excluidos = [], []
    for r in tabela.itertuples(index=False):
        (incluidos if r.eventos >= MIN_EVENTOS_PAR else excluidos).append(
            (r.comorbidade_1, r.comorbidade_2))
    return incluidos, excluidos


def _conferir_pares(tabela: pd.DataFrame, df: pd.DataFrame) -> None:
    """O arquivo tem de bater com a contagem feita sobre o `df` que está sendo ajustado."""
    recalculada = descriptive.pair_event_counts(df).set_index(["comorbidade_1", "comorbidade_2"])
    lido = tabela.set_index(["comorbidade_1", "comorbidade_2"])
    recalculada = recalculada.loc[lido.index]
    if not (recalculada[["casos", "eventos"]].to_numpy() == lido[["casos", "eventos"]].to_numpy()
            ).all():
        raise ValueError("pares_comorbidades.csv não bate com os dados: refaça a T-2.6")


# --- Ajuste ------------------------------------------------------------------------------------

def _agrupar(df: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por padrão de covariáveis, com casos e eventos (estatística suficiente)."""
    if df[CHAVES_PADRAO].isna().any().any():
        raise ValueError("há valores ausentes nas covariáveis do E1 (idade, sexo, gestante ou "
                         "comorbidade): a população deveria excluí-los")
    grupos = df.groupby(CHAVES_PADRAO, observed=True, sort=False)["y"]
    agrupado = grupos.agg(casos="size", eventos="sum").reset_index()
    agrupado["eventos"] = agrupado["eventos"].astype("int64")
    return agrupado


def _ajustar_glm(X: np.ndarray, eventos: np.ndarray, casos: np.ndarray) -> GLMResults:
    """GLM binomial sem penalização com resposta [eventos, não eventos] por padrão (R9)."""
    import statsmodels.api as sm  # local: só o ajuste precisa do statsmodels

    resposta = np.column_stack([eventos, casos - eventos]).astype(float)
    modelo = sm.GLM(resposta, np.asarray(X, dtype=float), family=sm.families.Binomial())
    return modelo.fit(maxiter=100, tol=1e-10)


def _log_verossimilhanca(eventos: np.ndarray, casos: np.ndarray, mu: np.ndarray) -> float:
    """Log-verossimilhança de Bernoulli, igual à da regressão linha a linha."""
    return float(np.sum(eventos * np.log(mu) + (casos - eventos) * np.log1p(-mu)))


def ajustar_e1(cfg: dict, df: pd.DataFrame) -> E1Ajustado:
    """Ajusta o E1 sobre `df` (população de 2022–23 com as features de `build_feature_frame`).

    Levanta RuntimeError se o ano de teste aparecer (R1), ValueError se o arquivo de pares não
    bater com os dados ou se um nível não tiver casos, e RuntimeError se o ajuste não convergir.
    Não penaliza nada (R9).
    """
    assert_dev_only(df)
    tabela_pares = ler_pares(_caminho_pares(cfg))
    _conferir_pares(tabela_pares, df)
    incluidos, excluidos = pares_do_arquivo(tabela_pares)
    nos = {
        "idade": _nos(df[COLUNA_IDADE].to_numpy(dtype=float), GL_IDADE),
        "idade_interacao": _nos(df[COLUNA_IDADE].to_numpy(dtype=float), GL_IDADE_INTERACAO),
    }
    agrupado = _agrupar(df)
    X = matriz_de_desenho(agrupado, nos, incluidos)
    niveis_vazios = [c for c in X.columns if X[c].sum() == 0]
    if niveis_vazios:
        raise ValueError(f"termos sem nenhum caso (matriz singular): {niveis_vazios}")
    eventos = agrupado["eventos"].to_numpy(dtype=float)
    casos = agrupado["casos"].to_numpy(dtype=float)

    inicio = time.perf_counter()
    resultados = _ajustar_glm(X, eventos, casos)
    tempo = time.perf_counter() - inicio
    if not resultados.converged:
        raise RuntimeError("E1 não convergiu: ver Erros inesperados antes de qualquer correção")

    # Termos binários (nível de sexo, gestante, Sim/Ausente de comorbidade): base do R7.
    termos_binarios = [c for c in X.columns if ": " in c and "spline" not in c]
    eventos_por_termo = {c: int((X[c].to_numpy() * eventos).sum()) for c in termos_binarios}
    return E1Ajustado(
        resultados=resultados,
        colunas=list(X.columns),
        nos=nos,
        pares_incluidos=incluidos,
        pares_excluidos=excluidos,
        eventos_por_termo=eventos_por_termo,
        n_casos=int(casos.sum()),
        n_eventos=int(eventos.sum()),
        n_padroes=len(agrupado),
        tempo_ajuste_s=tempo,
        log_verossimilhanca=_log_verossimilhanca(eventos, casos, resultados.mu),
    )


def _verossimilhanca(X: np.ndarray, eventos: np.ndarray, casos: np.ndarray,
                     beta: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
    """Log-verossimilhança, escore e informação de Fisher da logística agrupada em `beta`.

    Com `casos` = 1 e `eventos` = y, é a de linha a linha. Numericamente estável (logaddexp).
    """
    eta = X @ beta
    mu = np.exp(eta - np.logaddexp(0.0, eta))
    ll = float(np.sum(eventos * eta - casos * np.logaddexp(0.0, eta)))
    escore = X.T @ (eventos - casos * mu)
    informacao = (X * (casos * mu * (1.0 - mu))[:, None]).T @ X
    return ll, escore, informacao


def checar_equivalencia(df: pd.DataFrame, e1: E1Ajustado, pares: list[tuple[str, str]],
                        n: int, seed: int) -> dict:
    """Confere que o E1 agrupado e o linha a linha são a mesma função de verossimilhança.

    Usa uma amostra aleatória de `n` linhas (semente do config, R8) e o ponto ajustado `beta`
    do ajuste completo. Compara log-verossimilhança, escore e informação das duas formas. Se elas
    são iguais em `beta`, o máximo e a covariância também são (R9: sem penalização).
    Erros relativos acima de `TOLERANCIA_EQUIVALENCIA` reprovam.
    """
    assert_dev_only(df)
    amostra = df.sample(n=min(n, len(df)), random_state=seed)
    beta = np.asarray(e1.resultados.params, dtype=float)
    y = amostra["y"].to_numpy(dtype=float)
    X_linha = matriz_de_desenho(amostra, e1.nos, pares).to_numpy(dtype=float)
    ll_linha, esc_linha, info_linha = _verossimilhanca(X_linha, y, np.ones_like(y), beta)
    agrupado = _agrupar(amostra)
    X_agr = matriz_de_desenho(agrupado, e1.nos, pares).to_numpy(dtype=float)
    ll_agr, esc_agr, info_agr = _verossimilhanca(
        X_agr, agrupado["eventos"].to_numpy(dtype=float),
        agrupado["casos"].to_numpy(dtype=float), beta)
    dif_ll = abs(ll_linha - ll_agr) / max(1.0, abs(ll_linha))
    dif_escore = float(np.max(np.abs(esc_linha - esc_agr))) / max(
        1.0, float(np.max(np.abs(esc_linha))))
    dif_info = float(np.max(np.abs(info_linha - info_agr))) / max(
        1.0, float(np.max(np.abs(info_linha))))
    maximo = max(dif_ll, dif_escore, dif_info)
    return {
        "n_linhas": int(len(amostra)),
        "n_padroes": int(len(agrupado)),
        "seed": seed,
        "dif_relativa_log_verossimilhanca": dif_ll,
        "dif_relativa_escore": dif_escore,
        "dif_relativa_informacao": dif_info,
        "tolerancia": TOLERANCIA_EQUIVALENCIA,
        "passou": bool(maximo < TOLERANCIA_EQUIVALENCIA),
    }


# --- Persistência (sem dados, R7) --------------------------------------------------------------

def _pasta_e1(cfg: dict) -> Path:
    return Path(cfg["caminhos"]["dados"]) / "e1"


def salvar_e1(cfg: dict, e1: E1Ajustado, equivalencia: dict | None = None) -> Path:
    """Grava o ajuste em `data/e1/` (fora do git, R7) sem as linhas: coeficientes, covariância,
    nós e colunas. A serialização formal com metadados é a T-3.6."""
    pasta = _pasta_e1(cfg)
    pasta.mkdir(parents=True, exist_ok=True)
    e1.resultados.save(pasta / NOME_RESULTADOS, remove_data=True)
    metadados = {
        "colunas": e1.colunas,
        "nos": e1.nos,
        "pares_incluidos": [list(p) for p in e1.pares_incluidos],
        "pares_excluidos": [list(p) for p in e1.pares_excluidos],
        "eventos_por_termo": e1.eventos_por_termo,
        "n_casos": e1.n_casos,
        "n_eventos": e1.n_eventos,
        "n_padroes": e1.n_padroes,
        "log_verossimilhanca": e1.log_verossimilhanca,
        "tempo_ajuste_s": e1.tempo_ajuste_s,
        "equivalencia": equivalencia,
        "idade_referencia": IDADE_REFERENCIA,
    }
    (pasta / NOME_METADADOS).write_text(
        json.dumps(metadados, ensure_ascii=False, indent=2), encoding="utf-8")
    return pasta


def load_e1(cfg: dict) -> E1Ajustado:
    """Lê o E1 salvo por `salvar_e1`. Levanta FileNotFoundError se ele não existir."""
    pasta = _pasta_e1(cfg)
    import statsmodels.api as sm  # local: o pickle do statsmodels só é lido aqui

    resultados = sm.load_pickle(pasta / NOME_RESULTADOS)
    meta = json.loads((pasta / NOME_METADADOS).read_text(encoding="utf-8"))
    return E1Ajustado(
        resultados=resultados,
        colunas=meta["colunas"],
        nos=meta["nos"],
        pares_incluidos=[tuple(p) for p in meta["pares_incluidos"]],
        pares_excluidos=[tuple(p) for p in meta["pares_excluidos"]],
        eventos_por_termo=meta["eventos_por_termo"],
        n_casos=meta["n_casos"],
        n_eventos=meta["n_eventos"],
        n_padroes=meta["n_padroes"],
        tempo_ajuste_s=meta["tempo_ajuste_s"],
        log_verossimilhanca=meta["log_verossimilhanca"],
    )


# --- Relatório (só agregados, R7) --------------------------------------------------------------

def _numero(x: float) -> str:
    return f"{x:.4f}".replace(".", ",")


def _linhas_coeficientes(e1: E1Ajustado, minimo: int) -> list[str]:
    params = np.asarray(e1.resultados.params)
    erros = np.asarray(e1.resultados.bse)
    cabecalho = [
        "| Termo | Coeficiente (logit) | Erro-padrão | IC 95% inferior | IC 95% superior |",
        "|---|---|---|---|---|",
    ]
    linhas = []
    for nome, b, ep in zip(e1.colunas, params, erros, strict=True):
        eventos = e1.eventos_por_termo.get(nome)
        if eventos is not None and eventos < minimo:
            linhas.append(f"| {nome} | suprimido (R7) | suprimido (R7) | suprimido (R7) | "
                          f"suprimido (R7) |")
            continue
        linhas.append(f"| {nome} | {_numero(b)} | {_numero(ep)} | {_numero(b - Z95 * ep)} | "
                      f"{_numero(b + Z95 * ep)} |")
    return cabecalho + linhas


def escrever_relatorio(cfg: dict, e1: E1Ajustado, equivalencia: dict | None = None) -> Path:
    """Grava `reports/e1/coeficientes.md`: coeficientes, IC e a situação de cada par."""
    minimo = int(cfg["supressao_min_celula"])
    res = e1.resultados
    linhas = [
        "# Modelo explicativo E1: coeficientes (T-3.1)",
        "",
        AVISO_P6,
        "",
        "Ajuste em 2022–23 (dados de desenvolvimento, sem dobras). Logística sem penalização (R9). "
        "Coeficientes na escala do logit; erro-padrão e IC 95% pelo método de Wald.",
        "",
        f"- Casos: {e1.n_casos:,} · eventos: {e1.n_eventos:,} · padrões agrupados: "
        f"{e1.n_padroes:,} · parâmetros: {len(e1.colunas)}".replace(",", " "),
        f"- Convergiu: {'sim' if res.converged else 'não'} · log-verossimilhança: "
        f"{e1.log_verossimilhanca:.2f}".replace(".", ","),
        f"- Tempo de ajuste: {e1.tempo_ajuste_s:.1f} s".replace(".", ","),
    ]
    if equivalencia is not None:
        pior = max(equivalencia["dif_relativa_log_verossimilhanca"],
                   equivalencia["dif_relativa_escore"],
                   equivalencia["dif_relativa_informacao"])
        situacao = "passou" if equivalencia["passou"] else "NÃO passou"
        n_txt = f"{equivalencia['n_linhas']:,}".replace(",", " ")
        texto = (
            f"- Equivalência agrupado x linha a linha: em {n_txt} linhas aleatórias "
            f"(semente {equivalencia['seed']}) e no ponto ajustado, a maior diferença relativa de "
            f"log-verossimilhança, escore e informação é {pior:.1e}; {situacao} "
            f"(tolerância {equivalencia['tolerancia']:.0e})"
        )
        linhas.append(texto.replace(".", ","))
    linhas += [
        "",
        "## Coeficientes",
        "",
        f"Termos com menos de {minimo} eventos no nível aparecem como suprimidos (R7), inclusive "
        "\"Ausente\" (nível próprio de cada comorbidade). O intercepto e a base da idade "
        "(spline) não têm interpretação direta; a curva da idade sai na tabela de perfis. "
        "\"DIABETES: Sim\" e \"HIPERTENSA: Sim\" são o log-OR aos 40 anos (IDADE_REFERENCIA), com "
        "as demais comorbidades em Não, sexo F e não gestante. O OR varia com a idade (há "
        "interação com a idade): a leitura por faixa etária é da T-3.2.",
        "",
        "Escolhas registradas: base natural própria para a idade (nós nos quantis das linhas; "
        "`patsy.cr` teria constante colineal com o intercepto). Supressão de 8 coeficientes com "
        "menos de 10 eventos no nível (Sexo: I e os \"Ausente\" das 7 comorbidades) confirmada "
        "pelo Programador.",
        "",
        *_linhas_coeficientes(e1, minimo),
        "",
        "## Interações 2 a 2 entre comorbidades",
        "",
        "Entram no E1 os pares com pelo menos 10 eventos. Os demais aparecem como "
        "\"eventos insuficientes\", sem contagem.",
        "",
        "| Par | Situação |",
        "|---|---|",
    ]
    linhas += [f"| {a} + {b} | incluído no E1 |" for a, b in e1.pares_incluidos]
    linhas += [f"| {a} + {b} | eventos insuficientes |" for a, b in e1.pares_excluidos]
    caminho = Path(cfg["caminhos"]["relatorios"]) / "e1" / "coeficientes.md"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return caminho


# --- OR, interações aditivas e ranking (T-3.2) -------------------------------------------------

def _ic_wald(estimativa: float, erro: float) -> tuple[float, float]:
    return estimativa - Z95 * erro, estimativa + Z95 * erro


def or_efeitos_principais(e1: E1Ajustado) -> list[dict]:
    """OR de cada comorbidade contra Não, com as demais em Não, aos 40 anos para DIABETES e
    HIPERTENSA (as outras não têm termo com a idade)."""
    linhas = []
    for c in COMORBIDADES:
        r = log_or_na_idade(e1, c, IDADE_REFERENCIA)
        inferior, superior = _ic_wald(r["estimativa"], r["erro_padrao"])
        linhas.append({
            "comorbidade": c,
            "or": float(np.exp(r["estimativa"])),
            "ic_inferior": float(np.exp(inferior)),
            "ic_superior": float(np.exp(superior)),
        })
    return linhas


def ajustar_bh(pvalores: list[float]) -> list[float]:
    """p-valores ajustados por Benjamini-Hochberg (FDR), na ordem de entrada (D-40)."""
    if not pvalores:
        return []
    from statsmodels.stats.multitest import multipletests  # local: só o BH usa

    return [float(p) for p in multipletests(pvalores, alpha=ALFA_FDR, method="fdr_bh")[1]]


def or_interacoes(e1: E1Ajustado) -> list[dict]:
    """OR da interação de cada par incluído (exp do coeficiente do produto), com IC 95%, p de
    Wald e p ajustado por Benjamini-Hochberg entre os pares incluídos."""
    beta = np.asarray(e1.resultados.params, dtype=float)
    erros = np.asarray(e1.resultados.bse, dtype=float)
    pvalores = np.asarray(e1.resultados.pvalues, dtype=float)
    linhas = []
    for a, b in e1.pares_incluidos:
        i = e1.colunas.index(f"{a} x {b}")
        inferior, superior = _ic_wald(float(beta[i]), float(erros[i]))
        linhas.append({
            "comorbidade_1": a,
            "comorbidade_2": b,
            "or": float(np.exp(beta[i])),
            "ic_inferior": float(np.exp(inferior)),
            "ic_superior": float(np.exp(superior)),
            "p": float(pvalores[i]),
        })
    for linha, p_ajustado in zip(linhas, ajustar_bh([r["p"] for r in linhas]), strict=True):
        linha["p_ajustado"] = p_ajustado
    return linhas


def idades_representativas() -> list[tuple[str, float]]:
    """Uma idade por faixa de `profiling.FAIXAS`: o meio do intervalo [inicio, fim). A faixa
    aberta 80+ usa 80 (limite inferior), porque não tem meio."""
    saida = []
    for rotulo, inicio, fim in zip(FAIXAS_ROTULOS, FAIXAS[:-1], FAIXAS[1:], strict=True):
        meio = float(inicio) if np.isinf(fim) else (float(inicio) + float(fim)) / 2
        saida.append((rotulo, meio))
    return saida


def or_por_faixa(e1: E1Ajustado) -> list[dict]:
    """OR de DIABETES e HIPERTENSA contra Não em cada faixa etária, com IC 95% (via
    `log_or_na_idade`). As demais comorbidades ficam em Não, sexo F, não gestante."""
    linhas = []
    for rotulo, idade in idades_representativas():
        linha: dict = {"faixa": rotulo, "idade": idade}
        for c in COM_IDADE:
            r = log_or_na_idade(e1, c, idade)
            inferior, superior = _ic_wald(r["estimativa"], r["erro_padrao"])
            linha[c] = {"or": float(np.exp(r["estimativa"])),
                        "ic_inferior": float(np.exp(inferior)),
                        "ic_superior": float(np.exp(superior))}
        linhas.append(linha)
    return linhas


def _contrastes_do_par(e1: E1Ajustado, a: str, b: str) -> np.ndarray:
    """Matriz (colunas do E1) x 3: colunas que dão logit(OR_A), logit(OR_B) e logit(OR_AB−interação)
    aos 40 anos, com sexo F, não gestante e demais comorbidades em Não."""
    produto = np.zeros(len(e1.colunas))
    produto[e1.colunas.index(f"{a} x {b}")] = 1.0
    return np.column_stack([
        _contraste_or(e1, a, IDADE_REFERENCIA),
        _contraste_or(e1, b, IDADE_REFERENCIA),
        produto,
    ])


def reri_ap_delta(theta: np.ndarray, sigma: np.ndarray) -> dict:
    """RERI e AP de um par, com IC 95% pelo método delta.

    `theta` = (logit OR_A, logit OR_B, coeficiente da interação) e `sigma` a covariância de theta.
    OR_AB = exp(a + b + c); RERI = OR_AB − OR_A − OR_B + 1; AP = RERI / OR_AB. Gradientes:
      dRERI/da = E − A, dRERI/db = E − B, dRERI/dc = E   (E = OR_AB, A = OR_A, B = OR_B);
      dAP/da = (E − A − RERI)/E, dAP/db = (E − B − RERI)/E, dAP/dc = (E − RERI)/E.
    IC = valor ± Z95 · sqrt(gᵀ Σ g).
    """
    a, b, c = (float(x) for x in theta)
    ou_a, ou_b, ou_ab = np.exp(a), np.exp(b), np.exp(a + b + c)
    reri = ou_ab - ou_a - ou_b + 1
    ap = reri / ou_ab
    g_reri = np.array([ou_ab - ou_a, ou_ab - ou_b, ou_ab])
    g_ap = np.array([(ou_ab - ou_a - reri) / ou_ab,
                     (ou_ab - ou_b - reri) / ou_ab,
                     (ou_ab - reri) / ou_ab])
    erro_reri = float(np.sqrt(g_reri @ sigma @ g_reri))
    erro_ap = float(np.sqrt(g_ap @ sigma @ g_ap))
    return {
        "or_a": float(ou_a), "or_b": float(ou_b), "or_ab": float(ou_ab),
        "reri": float(reri), "reri_ic": _ic_wald(float(reri), erro_reri),
        "ap": float(ap), "ap_ic": _ic_wald(float(ap), erro_ap),
    }


def reri_ap_simulacao(theta: np.ndarray, sigma: np.ndarray, rng: np.random.Generator,
                      n: int = N_SIMULACOES) -> dict:
    """Conferência do delta: sorteia theta ~ N(theta, sigma) e toma os quantis 2,5% e 97,5% de
    RERI e AP. É uma simulação paramétrica dos coeficientes, não um bootstrap dos dados."""
    sorteios = rng.multivariate_normal(np.asarray(theta, dtype=float), sigma, size=n)
    ou_a, ou_b = np.exp(sorteios[:, 0]), np.exp(sorteios[:, 1])
    ou_ab = np.exp(sorteios.sum(axis=1))
    reri = ou_ab - ou_a - ou_b + 1
    ap = reri / ou_ab
    return {
        "reri_ic": tuple(float(q) for q in np.quantile(reri, [0.025, 0.975])),
        "ap_ic": tuple(float(q) for q in np.quantile(ap, [0.025, 0.975])),
    }


def _situacao_aditiva(ic: tuple[float, float]) -> str:
    if ic[0] > 0:
        return "supra-aditivo"
    if ic[1] < 0:
        return "sub-aditivo"
    return "compatível com aditividade (IC inclui zero)"


def _inclui_zero(ic: tuple[float, float]) -> bool:
    return ic[0] <= 0 <= ic[1]


def medidas_sensiveis_ao_metodo(p: dict) -> list[str]:
    """RERI e/ou AP cujo IC delta e IC por simulação discordam sobre incluir o zero.

    Intervalos fechados: zero na borda conta como incluído. Só o zero importa aqui; IC diferentes
    que continuam do mesmo lado do zero não marcam o par.
    """
    saida = []
    if _inclui_zero(p["reri_ic"]) != _inclui_zero(p["reri_sim_ic"]):
        saida.append("RERI")
    if _inclui_zero(p["ap_ic"]) != _inclui_zero(p["ap_sim_ic"]):
        saida.append("AP")
    return saida


def reri_ap_pares(e1: E1Ajustado, seed: int, n: int = N_SIMULACOES) -> list[dict]:
    """RERI e AP dos pares incluídos no E1, pelo delta e com a conferência por simulação."""
    beta = np.asarray(e1.resultados.params, dtype=float)
    cov = np.asarray(e1.resultados.cov_params(), dtype=float)
    rng = np.random.default_rng(seed)
    linhas = []
    for a, b in e1.pares_incluidos:
        contrastes = _contrastes_do_par(e1, a, b)
        theta = contrastes.T @ beta
        sigma = contrastes.T @ cov @ contrastes
        delta = reri_ap_delta(theta, sigma)
        sim = reri_ap_simulacao(theta, sigma, rng, n)
        linhas.append({
            "comorbidade_1": a,
            "comorbidade_2": b,
            **{k: delta[k] for k in ("or_a", "or_b", "or_ab", "reri", "reri_ic", "ap", "ap_ic")},
            "reri_sim_ic": sim["reri_ic"],
            "ap_sim_ic": sim["ap_ic"],
            "dif_reri_extremos": max(abs(delta["reri_ic"][i] - sim["reri_ic"][i])
                                     for i in (0, 1)),
            "dif_ap_extremos": max(abs(delta["ap_ic"][i] - sim["ap_ic"][i]) for i in (0, 1)),
            "situacao": _situacao_aditiva(delta["reri_ic"]),
        })
    return linhas


def se_sobrepoe(ic_1: tuple[float, float], ic_2: tuple[float, float]) -> bool:
    """Intervalos fechados se sobrepõem se têm algum ponto em comum. Tocar na borda conta como
    sobreposição: só há ordem quando a separação é estrita (escolha conservadora)."""
    return ic_1[0] <= ic_2[1] and ic_2[0] <= ic_1[1]


def ranking_comorbidades(principais: list[dict]) -> dict:
    """Ordena pelo OR (maior primeiro) e marca "sem ordem definida" por PAR de IC sobrepostos
    (FR-19). A relação não é transitiva: A pode se sobrepor a B e B a C sem que A e C se
    sobreponham. Por isso o resultado é uma lista de pares, não grupos."""
    ordenadas = sorted(principais, key=lambda r: r["or"], reverse=True)
    ic = {r["comorbidade"]: (r["ic_inferior"], r["ic_superior"]) for r in ordenadas}
    linhas = []
    for r in ordenadas:
        empatadas = [s["comorbidade"] for s in ordenadas
                     if s["comorbidade"] != r["comorbidade"]
                     and se_sobrepoe(ic[r["comorbidade"]], ic[s["comorbidade"]])]
        linhas.append({**r, "sem_ordem_com": empatadas})
    pares = [(x["comorbidade"], y["comorbidade"])
             for i, x in enumerate(ordenadas) for y in ordenadas[i + 1:]
             if se_sobrepoe(ic[x["comorbidade"]], ic[y["comorbidade"]])]
    return {"ordem": linhas, "pares_sem_ordem": pares}


def _dec(x: float, casas: int = 2) -> str:
    return f"{x:.{casas}f}".replace(".", ",")


def _ic_txt(inferior: float, superior: float, casas: int = 2) -> str:
    return f"[{_dec(inferior, casas)}; {_dec(superior, casas)}]"


def _p_txt(p: float) -> str:
    return "< 0,001" if p < 0.001 else _dec(p, 3)


def _tabela(cabecalho: list[str], linhas: list[list[str]]) -> list[str]:
    return ["| " + " | ".join(cabecalho) + " |", "|" + "---|" * len(cabecalho),
            *("| " + " | ".join(linha) + " |" for linha in linhas)]


def _amplitude(f: dict, comorbidade: str) -> float:
    return f[comorbidade]["ic_superior"] - f[comorbidade]["ic_inferior"]


def _prosa_faixas(faixas: list[dict]) -> list[str]:
    """Três parágrafos sobre a tabela por faixa, derivados dos números. Cada afirmação só sai
    se os dados a sustentam (ex.: 'cai depois do máximo' só se o OR cai em todas as faixas
    seguintes)."""
    rotulos = [f["faixa"] for f in faixas]
    abaixo_20 = [f for f in faixas if f["idade"] < 20]
    de_20_em_diante = [f for f in faixas if f["idade"] >= 20]

    def faixa_ampl(lista: list[dict], c: str) -> str:
        valores = [_amplitude(f, c) for f in lista]
        return f"de {_dec(min(valores))} a {_dec(max(valores))}"

    paragrafo_1 = (
        f"Abaixo de 20 anos, a amplitude do IC de DIABETES vai "
        f"{faixa_ampl(abaixo_20, 'DIABETES')} e a de HIPERTENSA vai "
        f"{faixa_ampl(abaixo_20, 'HIPERTENSA')} (escala do OR); nas faixas de 20 anos ou mais, "
        f"vai {faixa_ampl(de_20_em_diante, 'DIABETES')} e "
        f"{faixa_ampl(de_20_em_diante, 'HIPERTENSA')}.")
    if all(min(_amplitude(f, c) for f in abaixo_20) > max(_amplitude(f, c) for f in de_20_em_diante)
           for c in COM_IDADE):
        paragrafo_1 += (" Nos dois efeitos, os IC abaixo de 20 anos são mais largos do que os de "
                        "qualquer faixa de 20 anos ou mais.")

    ors_d = [f["DIABETES"]["or"] for f in faixas]
    pico = int(np.argmax(ors_d))
    if pico == len(ors_d) - 1:
        paragrafo_2 = f"O OR de DIABETES é máximo na última faixa ({rotulos[pico]})."
    elif all(ors_d[i] > ors_d[i + 1] for i in range(pico, len(ors_d) - 1)):
        paragrafo_2 = (f"O OR de DIABETES é máximo na faixa {rotulos[pico]} "
                       f"({_dec(ors_d[pico])}) e cai em todas as faixas seguintes, até "
                       f"{_dec(ors_d[-1])} em {rotulos[-1]}.")
    else:
        paragrafo_2 = (f"O OR de DIABETES é máximo na faixa {rotulos[pico]} "
                       f"({_dec(ors_d[pico])}), e não cai em todas as faixas seguintes.")

    ors_h = [f["HIPERTENSA"]["or"] for f in faixas]
    inicio = next(i for i, f in enumerate(faixas) if f["idade"] >= 15)
    if all(ors_h[i] <= ors_h[i + 1] for i in range(inicio, len(ors_h) - 1)):
        paragrafo_3 = (f"O OR de HIPERTENSA não cai com a idade a partir da faixa "
                       f"{rotulos[inicio]}: vai de {_dec(ors_h[inicio])} a {_dec(ors_h[-1])} "
                       f"em {rotulos[-1]}.")
    else:
        paragrafo_3 = (f"O OR de HIPERTENSA não cresce em todas as faixas a partir de "
                       f"{rotulos[inicio]}.")
    return [paragrafo_1, "", paragrafo_2, "", paragrafo_3]


def _bloco(paragrafos: list[str]) -> list[str]:
    """Parágrafos separados por linha em branco (vazio se não houver nenhum)."""
    return [linha for paragrafo in paragrafos for linha in (paragrafo, "")]


def _md_or_interacoes(efeitos: list[dict], interacoes: list[dict], faixas: list[dict],
                      n_excluidos: int, nota: list[str] = ()) -> list[str]:
    linhas = [
        "# Modelo explicativo E1: OR e interações 2 a 2 (T-3.2)",
        "",
        AVISO_P6,
        "",
        *_bloco(list(nota)),
        "Ajuste do E1 em 2022–23 (dados de desenvolvimento, sem dobras). Logística sem penalização "
        "(R9). IC 95% pelo método de Wald, com a covariância do ajuste. P-valor de Wald; o p "
        "ajustado usa Benjamini-Hochberg (FDR 5%) sobre os pares incluídos (FR-05, D-40).",
        "",
        "Leitura: o que orienta é o tamanho do efeito e o IC. O p ajustado só diz se o par "
        "passa na correção de múltiplas comparações.",
        "",
        "## Efeitos principais: OR de cada comorbidade contra Não",
        "",
        "Comorbidade isolada: as demais em Não, sexo F, não gestante. DIABETES e HIPERTENSA aos "
        "40 anos (o OR delas varia com a idade; ver a tabela por faixa abaixo).",
        "",
        *_tabela(["Comorbidade", "OR", "IC 95%"],
                 [[r["comorbidade"], _dec(r["or"]), _ic_txt(r["ic_inferior"], r["ic_superior"])]
                  for r in efeitos]),
        "",
        "## Interações 2 a 2 (pares com pelo menos 10 eventos)",
        "",
        "OR da interação = exp(coeficiente do produto), na escala multiplicativa. OR de 1 quer "
        "dizer que o OR de uma comorbidade não muda na presença da outra. A escala aditiva está "
        "em [reri_ap.md](reri_ap.md).",
        "",
        *_tabela(["Par", "OR da interação", "IC 95%", "p (Wald)", "p ajustado (BH)"],
                 [[f"{r['comorbidade_1']} × {r['comorbidade_2']}", _dec(r["or"]),
                   _ic_txt(r["ic_inferior"], r["ic_superior"]), _p_txt(r["p"]),
                   _p_txt(r["p_ajustado"])] for r in interacoes]),
        "",
        f"{n_excluidos} pares têm eventos insuficientes (menos de 10) e não entram no E1 nem nesta "
        "tabela. Aparecem sem contagem em [coeficientes.md](coeficientes.md) (R7).",
        "",
        "## OR de DIABETES e HIPERTENSA por faixa etária",
        "",
        "Idade usada: o meio de cada faixa; na faixa aberta 80+, 80 (limite inferior). As demais "
        "comorbidades em Não, sexo F, não gestante. Quanto mais largo o IC, menos preciso o OR "
        "naquela idade.",
        "",
        *_tabela(["Faixa", "Idade usada", "DIABETES: OR", "DIABETES: IC 95%",
                  "HIPERTENSA: OR", "HIPERTENSA: IC 95%"],
                 [[f["faixa"], _dec(f["idade"], 1),
                   _dec(f["DIABETES"]["or"]),
                   _ic_txt(f["DIABETES"]["ic_inferior"], f["DIABETES"]["ic_superior"]),
                   _dec(f["HIPERTENSA"]["or"]),
                   _ic_txt(f["HIPERTENSA"]["ic_inferior"], f["HIPERTENSA"]["ic_superior"])]
                  for f in faixas]),
        "",
        *_prosa_faixas(faixas),
        "",
    ]
    return linhas


def _md_reri_ap(pares: list[dict], seed: int, n: int, n_excluidos: int,
                nota: list[str] = ()) -> list[str]:
    pior_reri = max(p["dif_reri_extremos"] for p in pares)
    pior_ap = max(p["dif_ap_extremos"] for p in pares)
    sensiveis = [(f"{p['comorbidade_1']} × {p['comorbidade_2']}", medidas_sensiveis_ao_metodo(p))
                 for p in pares]
    sensiveis = [(par, medidas) for par, medidas in sensiveis if medidas]
    lista_sensiveis = (", ".join(f"{par} ({' e '.join(medidas)})" for par, medidas in sensiveis)
                       if sensiveis else "nenhum")
    return [
        "# Interação aditiva: RERI e AP (T-3.2)",
        "",
        AVISO_P6,
        "",
        *_bloco(list(nota)),
        "Referência: idade 40, sexo F, não gestante, demais comorbidades em Não. OR_A, OR_B e "
        "OR_AB são contra \"nenhuma das duas\".",
        "",
        "- RERI = OR_AB − OR_A − OR_B + 1 (excesso de risco relativo devido à interação). "
        "RERI > 0: supra-aditivo; RERI < 0: sub-aditivo; RERI = 0: aditivo.",
        "- AP = RERI / OR_AB (proporção do risco com as duas comorbidades atribuível à interação).",
        "- IC 95% oficial: método delta, com a covariância dos coeficientes (D-40). Os IC do "
        "delta são simétricos em torno do ponto estimado.",
        f"- Sensibilidade: {f'{n:,}'.replace(',', '.')} sorteios da normal multivariada dos "
        f"coeficientes (semente {seed}); os quantis 2,5% e 97,5% dão IC por simulação. Não é "
        "bootstrap dos dados. A simulação não substitui o delta: mostra a assimetria do RERI, "
        "que é função exponencial dos coeficientes. Onde os dois IC discordam sobre incluir o "
        "zero, a conclusão aditiva do par é incerta (coluna \"Sensível ao método\").",
        "",
        *_tabela(["Par", "OR_A", "OR_B", "OR_AB", "RERI [IC 95%, delta]", "AP [IC 95%, delta]",
                  "Leitura (IC do delta)", "Sensível ao método"],
                 [[f"{p['comorbidade_1']} × {p['comorbidade_2']}", _dec(p["or_a"]),
                   _dec(p["or_b"]), _dec(p["or_ab"]),
                   f"{_dec(p['reri'])} {_ic_txt(*p['reri_ic'])}",
                   f"{_dec(p['ap'])} {_ic_txt(*p['ap_ic'])}",
                   p["situacao"], ", ".join(medidas_sensiveis_ao_metodo(p)) or "—"]
                  for p in pares]),
        "",
        "## Conferência: delta × simulação",
        "",
        f"Maior diferença entre os extremos dos dois IC, nos {len(pares)} pares: RERI "
        f"{_dec(pior_reri, 2)}; AP {_dec(pior_ap, 2)} (na escala de cada medida).",
        "",
        f"Pares sensíveis ao método (o IC delta e o IC por simulação discordam sobre incluir o "
        f"zero): {lista_sensiveis}. Nesses pares, a conclusão aditiva é incerta.",
        "",
        *_tabela(["Par", "RERI: delta", "RERI: simulação", "AP: delta", "AP: simulação"],
                 [[f"{p['comorbidade_1']} × {p['comorbidade_2']}", _ic_txt(*p["reri_ic"]),
                   _ic_txt(*p["reri_sim_ic"]), _ic_txt(*p["ap_ic"]), _ic_txt(*p["ap_sim_ic"])]
                  for p in pares]),
        "",
        f"{n_excluidos} pares com eventos insuficientes não entram nesta tabela (R7).",
        "",
    ]


def _md_ranking(ranking: dict, nota: list[str] = ()) -> list[str]:
    linhas = [
        "# Ranking de comorbidades (T-3.2, FR-19)",
        "",
        AVISO_P6,
        "",
        *_bloco(list(nota)),
        "Fonte: só os OR do E1 (R10), efeito principal de cada comorbidade contra Não, ajustado "
        "por idade e sexo. DIABETES e HIPERTENSA aos 40 anos: o OR delas muda com a idade (ver "
        "[or_interacoes.md](or_interacoes.md)), então o ranking vale para 40 anos. É associação "
        "ajustada, não causa.",
        "",
        "Regra: duas comorbidades cujos IC 95% se sobrepõem ficam marcadas \"sem ordem definida\" "
        "entre si. Intervalos que só tocam na borda contam como sobrepostos.",
        "",
        "A sobreposição não é transitiva: A pode se sobrepor a B, e B a C, sem que A e C se "
        "sobreponham. Por isso o ranking marca pares e não forma grupos fechados.",
        "",
        *_tabela(["Posição", "Comorbidade", "OR", "IC 95%", "Sem ordem definida com"],
                 [[str(i + 1), r["comorbidade"], _dec(r["or"]),
                   _ic_txt(r["ic_inferior"], r["ic_superior"]),
                   ", ".join(r["sem_ordem_com"]) if r["sem_ordem_com"] else "—"]
                  for i, r in enumerate(ranking["ordem"])]),
        "",
        "## Pares sem ordem definida",
        "",
    ]
    if ranking["pares_sem_ordem"]:
        linhas += [f"- {a} e {b}" for a, b in ranking["pares_sem_ordem"]]
    else:
        linhas.append("Nenhum par tem IC sobreposto.")
    return [*linhas, ""]


def executar_or(cfg: dict) -> dict[str, Path]:
    """Lê o E1 salvo em `data/e1/` (sem recarregar os dados) e grava os três relatórios da T-3.2
    em `reports/e1/`: OR e interações, RERI e AP, ranking. Só agregados (R7)."""
    e1 = load_e1(cfg)
    seed = int(cfg["seed"])
    efeitos = or_efeitos_principais(e1)
    interacoes = or_interacoes(e1)
    faixas = or_por_faixa(e1)
    pares = reri_ap_pares(e1, seed=seed)
    ranking = ranking_comorbidades(efeitos)
    n_excluidos = len(e1.pares_excluidos)
    nota = nota_padrao(contexto_padrao(cfg))  # a mesma nota nos três relatórios
    pasta = Path(cfg["caminhos"]["relatorios"]) / "e1"
    pasta.mkdir(parents=True, exist_ok=True)
    escritos = {
        "or_interacoes": pasta / "or_interacoes.md",
        "reri_ap": pasta / "reri_ap.md",
        "ranking": pasta / "ranking.md",
    }
    conteudo = {
        "or_interacoes": _md_or_interacoes(efeitos, interacoes, faixas, n_excluidos, nota),
        "reri_ap": _md_reri_ap(pares, seed, N_SIMULACOES, n_excluidos, nota),
        "ranking": _md_ranking(ranking, nota),
    }
    for chave, caminho in escritos.items():
        caminho.write_text("\n".join(conteudo[chave]) + "\n", encoding="utf-8")
    return escritos


# --- Tabela de perfis (T-3.5, FR-06, D-52) -----------------------------------------------------

NOME_CELULAS = "contagens_celulas.csv"
ARQUIVO_COMBINACOES = "combinacoes_3_ou_mais.csv"
SEXOS_VALIDOS = ("F", "M", "I")
SEXOS_PERFIL = ("F", "M")  # [ASSUMPTION] F e M separados; I fica fora da tabela
TOP_RESUMO = 10  # perfis além do saudável no resumo, por contagem observada (não publicada)
FAIXA_RESUMO = "60–79"
GRUPOS_PERFIS = {
    1: "Referência",
    2: "Uma comorbidade",
    3: "Pares de comorbidades",
    4: "Três ou mais comorbidades",
}
NOTA_TRIO = ("risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem termo "
             "próprio para o trio")
NOTA_COMBINACAO = ("risco estimado pela soma dos efeitos individuais e dos pares; o E1 não tem "
                   "termo próprio para a combinação")
SEM_DADOS = "dados insuficientes"
SEM_DADOS_5_MAIS = ("dados insuficientes (5+ comorbidades: poucos eventos; extrapolação instável "
                    "do E1)")
MAX_COMORBIDADES_ESTIMADAS = 4  # T-3.5: perfis com 5 ou mais comorbidades não têm estimativa
AVISO_PADRAO = "depende do padrão suspeito (ver sensibilidade)"
SUPRIMIDO = "—"
CABECALHO_PERFIS = ["Perfil", "Faixa etária", "Sexo", "Risco estimado", "IC 95%",
                    'Razão vs. "saudável" (mesma faixa e sexo), IC 95%']


@dataclass(frozen=True)
class Perfil:
    """Um perfil da tabela (D-52): comorbidades "Sim" (as demais, "Não") e a situação do par."""

    nome: str
    grupo: int
    comorbidades: tuple[str, ...]
    dados_insuficientes: bool = False


def _mascara(comorbidades) -> int:
    """Bit i marca COMORBIDADES[i] como "Sim" (a mesma chave de 7 bits da T-2.6)."""
    marcadas = set(comorbidades)
    return sum(1 << i for i, c in enumerate(COMORBIDADES) if c in marcadas)


def _expit(eta: float) -> float:
    return float(1.0 / (1.0 + np.exp(-eta)))


def _validar_perfil(idade: float, sexo: str, gestante: int, comorbidades) -> set[str]:
    if not 0 <= float(idade) <= 120:
        raise ValueError(f"idade fora de [0, 120]: {idade}")
    if sexo not in SEXOS_VALIDOS:
        raise ValueError(f"sexo deve ser F, M ou I: {sexo!r}")
    if gestante not in (0, 1):
        raise ValueError(f"gestante deve ser 0 ou 1: {gestante}")
    if gestante == 1 and sexo != "F":
        raise ValueError("gestante só é possível com sexo F")
    marcadas = set(comorbidades)
    desconhecidas = marcadas - set(COMORBIDADES)
    if desconhecidas:
        raise ValueError(f"comorbidades desconhecidas: {sorted(desconhecidas)}")
    return marcadas


def _vetor_perfil(e1: E1Ajustado, idade: float, sexo: str, gestante: int,
                  comorbidades) -> np.ndarray:
    """Linha do desenho do E1 para o perfil, na ordem de `e1.colunas`.

    Usa o mesmo `matriz_de_desenho` do ajuste, então não há termo de trio: só efeitos individuais,
    de idade e sexo, e os pares que estão no E1.
    """
    marcadas = _validar_perfil(idade, sexo, gestante, comorbidades)
    linha = {
        COLUNA_IDADE: float(idade),
        "sexo": sexo,
        "gestante": int(gestante),
        **{c: "Sim" if c in marcadas else "Não" for c in COMORBIDADES},
    }
    X = matriz_de_desenho(pd.DataFrame([linha]), e1.nos, e1.pares_incluidos)
    # Ajustes de sensibilidade têm indicadores do padrão todas as 7 = Sim: o perfil ganha 1 só
    # se tem as 7, e 0 nos indicadores por covariáveis (que não se aplicam a perfis novos).
    for c in e1.colunas:
        if c in X.columns:
            continue
        if c == NOME_PADRAO_DUMMY:
            X[c] = float(len(marcadas) == len(COMORBIDADES))
        elif c.startswith(f"{NOME_PADRAO_DUMMY}: covariáveis"):
            X[c] = 0.0
        else:
            raise ValueError(f"termo do E1 sem valor para o perfil: {c}")
    if set(X.columns) != set(e1.colunas):
        raise ValueError("o desenho do perfil não bate com as colunas do E1")
    return X[list(e1.colunas)].to_numpy(dtype=float)[0]


def risco_perfil(e1: E1Ajustado, idade: float, sexo: str, gestante: int,
                 comorbidades) -> dict:
    """Risco previsto pelo E1 para um perfil, com IC 95% pelo método delta na escala do logit.

    η = xᵀβ e Var(η) = xᵀΣx, com x a linha do desenho do E1. IC = expit(η ± Z95·√Var): o IC é
    calculado no logit e só depois passa pela logística. Qualquer combinação é calculável aqui,
    mesmo as que não estão na tabela de perfis (a demo usa esta função).
    """
    x = _vetor_perfil(e1, idade, sexo, gestante, comorbidades)
    beta = e1.params
    cov = e1.cov
    eta = float(x @ beta)
    erro = float(np.sqrt(max(float(x @ cov @ x), 0.0)))
    inferior, superior = _ic_wald(eta, erro)
    return {
        "risco": _expit(eta),
        "ic_inferior": _expit(inferior),
        "ic_superior": _expit(superior),
        "logit": eta,
        "erro_logit": erro,
    }


def razao_de_risco(e1: E1Ajustado, idade: float, sexo: str, gestante: int,
                   comorbidades) -> dict:
    """Razão de risco contra "sem comorbidades" na mesma idade, sexo e gestação.

    log RR = dᵀβ, com d = x_perfil − x_saudável. Var(log RR) = dᵀΣd, que equivale a
    Var(η_perfil) + Var(η_saudável) − 2·Cov(η_perfil, η_saudável): os dois logits compartilham
    idade, sexo e gestação, e essa covariância entra pela Σ. IC = exp(log RR ± Z95·√Var).
    """
    x = _vetor_perfil(e1, idade, sexo, gestante, comorbidades)
    d = x - _vetor_perfil(e1, idade, sexo, gestante, ())
    beta = e1.params
    cov = e1.cov
    log_rr = float(d @ beta)
    erro = float(np.sqrt(max(float(d @ cov @ d), 0.0)))
    inferior, superior = _ic_wald(log_rr, erro)
    return {
        "razao": float(np.exp(log_rr)),
        "ic_inferior": float(np.exp(inferior)),
        "ic_superior": float(np.exp(superior)),
        "log_razao": log_rr,
        "erro_log_razao": erro,
    }


# --- Lista de perfis (gerada do E1 e das contagens) ---------------------------------------------

def ler_combinacoes(cfg: dict) -> pd.DataFrame:
    """Lê `combinacoes_3_ou_mais.csv` (T-2.6, em `data/descritiva/`, fora do git)."""
    caminho = Path(cfg["caminhos"]["dados"]) / "descritiva" / ARQUIVO_COMBINACOES
    tabela = pd.read_csv(caminho)
    esperadas = {"combinacao", "n_comorbidades", "casos", "eventos"}
    if not esperadas.issubset(tabela.columns):
        raise ValueError(f"{caminho}: faltam as colunas {sorted(esperadas - set(tabela.columns))}")
    return tabela


def gerar_perfis(e1: E1Ajustado, combinacoes: pd.DataFrame, minimo: int) -> list[Perfil]:
    """Lista de perfis (D-52), gerada do E1 e das contagens; nenhum perfil é escrito à mão.

    Grupo 1: sem comorbidades. Grupo 2: cada comorbidade sozinha. Grupo 3: cada um dos 21 pares;
    os que entraram no E1 viram perfis, e os outros ficam como "dados insuficientes". Grupo 4:
    cada combinação exata de 3 ou mais comorbidades com pelo menos `minimo` casos. As de 3 e 4
    têm estimativa; as de 5 ou mais ficam como "dados insuficientes" (sem número, T-3.5).
    """
    incluidos = set(e1.pares_incluidos)
    excluidos = set(e1.pares_excluidos)
    if incluidos & excluidos or set(PARES) != incluidos | excluidos:
        raise ValueError("os pares do E1 não cobrem as 21 combinações de 2 comorbidades")
    perfis = [Perfil("Sem comorbidades", 1, ())]
    perfis += [Perfil(c, 2, (c,)) for c in COMORBIDADES]
    for a, b in PARES:
        perfis.append(Perfil(f"{a} + {b}", 3, (a, b), dados_insuficientes=(a, b) in excluidos))
    for r in combinacoes.itertuples(index=False):
        nomes = tuple(str(r.combinacao).split(" + "))
        if (int(r.n_comorbidades) < 3 or len(nomes) != int(r.n_comorbidades)
                or not set(nomes) <= set(COMORBIDADES)):
            raise ValueError(f"combinação mal formada no arquivo: {r.combinacao!r}")
        if int(r.casos) >= minimo:
            sem_estimativa = len(nomes) > MAX_COMORBIDADES_ESTIMADAS
            perfis.append(Perfil(str(r.combinacao), 4, nomes, dados_insuficientes=sem_estimativa))
    return perfis


# --- Contagens observadas por célula (R7: interno, não publicado) --------------------------------

def contagens_por_padrao(df: pd.DataFrame) -> pd.DataFrame:
    """Casos por padrão de comorbidades "Sim", faixa etária, sexo e gestação (interno, R7).

    Padrão = máscara de 7 bits (bit i = COMORBIDADES[i] "Sim"); "Não" e "Ausente" não são Sim.
    Isso é a definição de combinação exata da T-2.6, então a soma por padrão bate com o CSV.
    """
    assert_dev_only(df)
    mascara = np.zeros(len(df), dtype=np.int64)
    for i, c in enumerate(COMORBIDADES):
        mascara |= (df[c] == "Sim").to_numpy().astype(np.int64) << i
    faixa = pd.cut(df[COLUNA_IDADE], FAIXAS, right=False, labels=FAIXAS_ROTULOS).astype(str)
    chaves = pd.DataFrame({
        "mascara": mascara,
        "faixa_etaria": faixa.to_numpy(),
        "sexo": df["sexo"].to_numpy(),
        "gestante": df["gestante"].to_numpy().astype(np.int64),
    })
    return (chaves.groupby(["mascara", "faixa_etaria", "sexo", "gestante"])
            .size().rename("casos").reset_index())


def conferir_contagens(celulas: pd.DataFrame, combinacoes: pd.DataFrame) -> None:
    """As contagens por padrão têm de bater com `combinacoes_3_ou_mais.csv` (T-2.6)."""
    por_padrao = celulas.groupby("mascara")["casos"].sum()
    for r in combinacoes.itertuples(index=False):
        if int(por_padrao.get(_mascara(str(r.combinacao).split(" + ")), 0)) != int(r.casos):
            raise ValueError(f"contagem de {r.combinacao!r} não bate com o CSV: refaça a T-2.6")
    n_com_3 = sum(1 for m, casos in por_padrao.items()
                  if bin(int(m)).count("1") >= 3 and casos > 0)
    if n_com_3 != len(combinacoes):
        raise ValueError("nº de combinações de 3+ com casos não bate com o CSV: refaça a T-2.6")


def contar_celulas(cfg: dict) -> Path:
    """Passada pelos dados de 2022–23 (~6,5 min com a carga): salva em `data/e1/` as contagens por
    padrão, faixa, sexo e gestação. Fora do git; a tabela só publica o que tem >= 10 casos."""
    populacao = dataset.load_population(cfg, list(cfg["anos_dev"]))
    assert_dev_only(populacao)
    df = dataset.build_feature_frame(populacao)
    del populacao
    n = len(df)
    celulas = contagens_por_padrao(df)
    del df
    if int(celulas["casos"].sum()) != n:
        raise ValueError("a soma das contagens por padrão não bate com a população")
    conferir_contagens(celulas, ler_combinacoes(cfg))
    _pasta_e1(cfg).mkdir(parents=True, exist_ok=True)
    caminho = _pasta_e1(cfg) / NOME_CELULAS
    celulas.to_csv(caminho, index=False)
    logger.info("contagens salvas: %d linhas, %d casos", len(celulas), n)
    return caminho


def ler_celulas(cfg: dict) -> pd.DataFrame:
    caminho = _pasta_e1(cfg) / NOME_CELULAS
    if not caminho.exists():
        raise FileNotFoundError(f"{caminho}: rode contar_celulas(cfg) antes")
    return pd.read_csv(caminho, dtype={"faixa_etaria": str, "sexo": str})


def _casos_observados(celulas: pd.DataFrame, comorbidades) -> dict[tuple[str, str], int]:
    """Casos observados por (faixa, sexo) de um perfil, com gestante Não."""
    sel = celulas[(celulas["mascara"] == _mascara(comorbidades)) & (celulas["gestante"] == 0)]
    return {(f, s): int(c) for f, s, c in
            zip(sel["faixa_etaria"], sel["sexo"], sel["casos"], strict=True)}


# --- Tabela (só células com >= minimo casos aparecem com número, R7) ----------------------------

def _pct(x: float) -> str:
    return f"{_dec(100 * x, 3)}%"


def _ic_pct(inferior: float, superior: float) -> str:
    return f"[{_pct(inferior)}; {_pct(superior)}]"


def _nota(perfil: Perfil) -> str:
    return NOTA_TRIO if len(perfil.comorbidades) == 3 else NOTA_COMBINACAO


def _linhas_do_perfil(e1: E1Ajustado, perfil: Perfil, celulas: pd.DataFrame, minimo: int,
                      faixas: list[tuple[str, float]] | None = None
                      ) -> list[tuple[list[str], bool]]:
    """Linhas de um perfil: (valores, se a célula foi publicada), uma por faixa e sexo."""
    if perfil.dados_insuficientes:
        motivo = SEM_DADOS_5_MAIS if len(perfil.comorbidades) > MAX_COMORBIDADES_ESTIMADAS \
            else SEM_DADOS
        return [([perfil.nome, SUPRIMIDO, SUPRIMIDO, motivo, SUPRIMIDO, SUPRIMIDO], False)]
    observados = _casos_observados(celulas, perfil.comorbidades)
    saudaveis = _casos_observados(celulas, ())
    linhas = []
    for rotulo, idade in (faixas or idades_representativas()):
        for sexo in SEXOS_PERFIL:
            if observados.get((rotulo, sexo), 0) < minimo:
                linhas.append(([perfil.nome, rotulo, sexo, SUPRIMIDO, SUPRIMIDO, SUPRIMIDO],
                               False))
                continue
            risco = risco_perfil(e1, idade, sexo, 0, perfil.comorbidades)
            if saudaveis.get((rotulo, sexo), 0) < minimo:
                razao = SUPRIMIDO
            else:
                rr = razao_de_risco(e1, idade, sexo, 0, perfil.comorbidades)
                razao = f"{_dec(rr['razao'])} {_ic_txt(rr['ic_inferior'], rr['ic_superior'])}"
            linhas.append(([perfil.nome, rotulo, sexo, _pct(risco["risco"]),
                            _ic_pct(risco["ic_inferior"], risco["ic_superior"]), razao], True))
    return linhas


def _aviso(perfil: Perfil, sensiveis) -> str:
    """Aviso do perfil quando ele contém um dos pares que dependem do padrão suspeito."""
    marcadas = set(perfil.comorbidades)
    depende = any(a in marcadas and b in marcadas for a, b in sensiveis)
    return AVISO_PADRAO if depende else SUPRIMIDO


def _lista_pares(pares) -> str:
    return _lista_e([f"{a} × {b}" for a, b in pares])


def _lista_e(itens: list[str]) -> str:
    """Junta itens em português: 'a', 'a e b', 'a, b e c'."""
    if not itens:
        return "nenhum"
    if len(itens) == 1:
        return itens[0]
    return ", ".join(itens[:-1]) + " e " + itens[-1]


def _md_completa(e1: E1Ajustado, perfis: list[Perfil], celulas: pd.DataFrame, minimo: int,
                 n_omitidas: int, sensiveis=()) -> tuple[list[str], dict]:
    """Markdown da tabela completa e as contagens de cada grupo (usadas na verificação).

    `sensiveis`: pares do E1 que só têm >= 10 eventos por causa do padrão suspeito (ver
    `contexto_padrao`); os perfis que os contêm recebem o aviso.
    """
    estatisticas: dict[int, dict] = {}
    secoes = []
    for grupo, titulo in GRUPOS_PERFIS.items():
        do_grupo = [p for p in perfis if p.grupo == grupo]
        insuficientes = sum(p.dados_insuficientes for p in do_grupo)
        linhas, publicadas, avaliadas, total = [], 0, 0, 0
        for perfil in do_grupo:
            aviso = _aviso(perfil, sensiveis)
            for valores, publicada in _linhas_do_perfil(e1, perfil, celulas, minimo):
                valores = [*valores, aviso]
                if grupo == 4:
                    nota = SUPRIMIDO if perfil.dados_insuficientes else _nota(perfil)
                    valores = [*valores, nota]
                linhas.append(valores)
                total += 1
                if not perfil.dados_insuficientes:
                    avaliadas += 1
                    publicadas += int(publicada)
        estatisticas[grupo] = {"perfis": len(do_grupo), "insuficientes": insuficientes,
                               "linhas": total, "publicadas": publicadas, "avaliadas": avaliadas}
        complementos = f"; {insuficientes} com dados insuficientes" if insuficientes else ""
        cabecalho = [*CABECALHO_PERFIS, "Aviso", *(["Nota"] if grupo == 4 else [])]
        secoes += [
            f"## Grupo {grupo}: {titulo} ({len(do_grupo)} perfis{complementos})",
            "",
            f"Células suprimidas (R7) neste grupo: {avaliadas - publicadas} de {avaliadas}.",
            "",
            *_tabela(cabecalho, linhas),
            "",
        ]
    linhas_md = [
        "# Tabela de perfis de risco (T-3.5, FR-06)",
        "",
        AVISO_P6,
        "",
        "Modelo: E1, logística sem penalização (R9), ajustada em 2022–23 com idade (spline), sexo, "
        "gestação e comorbidades. Os perfis vêm do E1 e das contagens de 2022–23 (D-52); nenhum "
        "perfil foi escrito à mão.",
        "",
        "- **Risco estimado:** probabilidade prevista de dengue grave ou óbito para o perfil, "
        "em %, com 3 casas. IC 95%: método delta na escala do logit (η ± 1,96 · EP), "
        "transformado pela logística.",
        "- **Razão vs. \"saudável\":** risco do perfil dividido pelo risco de \"sem comorbidades\" "
        "na mesma faixa e sexo, com 2 casas. IC 95%: método delta na escala do log da razão, com "
        "Var = dᵀΣd, em que d é a diferença entre as linhas do desenho dos dois perfis. A "
        "covariância entre os dois logits entra pela Σ.",
        "- **Perfil:** só as comorbidades listadas estão \"Sim\"; as demais, \"Não\" (referência "
        "do modelo). Gestante: Não. Idade: meio da faixa (80+ usa 80). Sexo: F e M separados "
        "(`[ASSUMPTION]`); I não aparece.",
        "- **Supressão (R7):** a célula observada é o nº de casos de 2022–23 com o mesmo padrão de "
        "comorbidades, na mesma faixa e sexo e gestante Não; as demais comorbidades não Sim, "
        "inclusive \"Ausente\", como na T-2.6. Com menos de 10 casos, risco, IC e razão saem como "
        "\"—\", sem contagem. A supressão usa a célula observada porque o risco é previsto pelo "
        "modelo, não contado. Por cautela, a razão também sai \"—\" se a célula do saudável "
        "estiver suprimida. Nenhuma contagem de 1 a 9 é publicada.",
        "- **Pares sem termo:** os pares com \"dados insuficientes\" (menos de 10 eventos) não têm "
        "termo no E1. Um perfil que contém um desses pares não recebe efeito para ele.",
        "- **Três ou quatro comorbidades:** têm estimativa. A nota da linha diz \"trio\" (3) ou "
        "\"combinação\" (4): risco estimado pela soma dos efeitos individuais e dos pares, porque "
        "o E1 não tem termo próprio para elas.",
        "- **Cinco ou mais comorbidades:** não têm estimativa. São combinações com menos de 10 "
        "eventos no total; o E1 não tem termo para elas e a extrapolação é instável. Aparecem como "
        "\"dados insuficientes\", sem número de eventos (R7).",
        "- **Aviso:** "
        + ("o perfil contém um dos pares que só têm 10 ou mais eventos por causa do padrão "
           f"suspeito \"todas as 7 comorbidades = Sim\" ({_lista_pares(sensiveis)}). Sem o padrão, "
           "esses pares saem do E1; ver [sensibilidade](sensibilidade_padrao_todas_sim.md)."
           if sensiveis else "nenhum par do E1 depende do padrão suspeito."),
        f"- **Combinações omitidas:** combinações de 3 ou mais comorbidades com menos de 10 casos "
        f"em 2022–23, que não aparecem na tabela (R7): {n_omitidas}.",
        "- **Demo:** a demo calcula qualquer combinação pelo E1 (`risco_perfil`), mesmo as que não "
        "estão nesta tabela.",
        "- Leitura: associação ajustada, não causa. Não é ferramenta clínica nem substitui "
        "avaliação médica.",
        "",
        "Referência: \"sem comorbidades\" tem razão 1,00 por definição.",
        "",
        *secoes,
    ]
    return linhas_md, estatisticas


def _perfis_frequentes(perfis: list[Perfil], celulas: pd.DataFrame, n: int) -> list[Perfil]:
    """Os `n` perfis com mais casos observados (grupos 2 a 4, com dados); a contagem não sai."""
    candidatos = [p for p in perfis if p.grupo >= 2 and not p.dados_insuficientes]
    return sorted(candidatos,
                  key=lambda p: -sum(_casos_observados(celulas, p.comorbidades).values()))[:n]


def _md_resumo(e1: E1Ajustado, perfis: list[Perfil], celulas: pd.DataFrame,
               minimo: int, sensiveis=()) -> list[str]:
    faixa = [(r, i) for r, i in idades_representativas() if r == FAIXA_RESUMO]
    escolhidos = [p for p in perfis if p.grupo == 1]
    escolhidos += _perfis_frequentes(perfis, celulas, TOP_RESUMO)
    corpo = []
    for perfil in escolhidos:
        aviso = _aviso(perfil, sensiveis)
        for valores, _ in _linhas_do_perfil(e1, perfil, celulas, minimo, faixa):
            nota = _nota(perfil) if perfil.grupo == 4 else SUPRIMIDO
            corpo.append([valores[0], valores[2], valores[3], valores[4], valores[5], aviso, nota])
    return [
        "# Tabela de perfis de risco: resumo (T-3.5, faixa 60–79)",
        "",
        AVISO_P6,
        "",
        "Versão curta de [perfis_completo.md](perfis_completo.md): faixa 60–79, sexo F e M, e os "
        f"{TOP_RESUMO} perfis mais frequentes entre os que têm dados, além do saudável. A ordem "
        "vem da contagem observada, que não é publicada. Mesmas definições, supressão (R7) e notas "
        "da tabela completa.",
        "",
        *_tabela(["Perfil", "Sexo", "Risco estimado", "IC 95%",
                  'Razão vs. "saudável", IC 95%', "Aviso", "Nota"], corpo),
        "",
    ]


ESPERADO_PADRAO = Path(__file__).resolve().parents[2] / "config" / "esperado.yaml"


def ler_esperado_e1(caminho: Path = ESPERADO_PADRAO) -> dict:
    """Seção `e1` de config/esperado.yaml: os números que as verificações T-3.5 e T-3.6 conferem."""
    return yaml.safe_load(Path(caminho).read_text(encoding="utf-8"))["e1"]


def executar_perfis(cfg: dict, esperado_path: Path = ESPERADO_PADRAO) -> dict[str, Path]:
    """Grava `reports/e1/perfis_completo.md` e `perfis_resumo.md` e a verificação T-3.5.

    Usa o E1 salvo e as contagens de `contar_celulas`. Só agregados (R7). Os esperados da
    verificação vêm de `config/esperado.yaml` (seção `e1`), nunca do código.
    """
    esperado = ler_esperado_e1(esperado_path)
    e1 = load_e1(cfg)
    minimo = int(cfg["supressao_min_celula"])
    combinacoes = ler_combinacoes(cfg)
    celulas = ler_celulas(cfg)
    sensiveis = contexto_padrao(cfg)["pares_sensiveis"]
    perfis = gerar_perfis(e1, combinacoes, minimo)
    n_grupo4 = sum(1 for p in perfis if p.grupo == 4)
    completa, estatisticas = _md_completa(e1, perfis, celulas, minimo,
                                          len(combinacoes) - n_grupo4, sensiveis)
    resumo = _md_resumo(e1, perfis, celulas, minimo, sensiveis)
    pasta = Path(cfg["caminhos"]["relatorios"]) / "e1"
    pasta.mkdir(parents=True, exist_ok=True)
    caminhos = {"completa": pasta / "perfis_completo.md", "resumo": pasta / "perfis_resumo.md"}
    caminhos["completa"].write_text("\n".join(completa) + "\n", encoding="utf-8")
    caminhos["resumo"].write_text("\n".join(resumo) + "\n", encoding="utf-8")
    checks = _checks_perfis(e1, perfis, combinacoes, celulas, minimo, estatisticas,
                            "\n".join(completa), esperado)
    caminhos["verificacao"] = verify.write_report(
        "T-3.5", checks, Path(cfg["caminhos"]["relatorios"]) / "verificacao", cfg)
    return caminhos


def _checks_perfis(e1: E1Ajustado, perfis: list[Perfil], combinacoes: pd.DataFrame,
                   celulas: pd.DataFrame, minimo: int, estatisticas: dict,
                   texto: str, esperado: dict) -> list[dict]:
    """Checks da T-3.5. Cada esperado é lido de `esperado` (seção `e1` de config/esperado.yaml);
    nada de número esperado escrito aqui (R: a verificação não calcula o que confere).
    `numeros_1_a_9_nas_tabelas` é a regra R7, não um número do modelo."""
    com_minimo = combinacoes["casos"] >= minimo
    n_com_minimo = int(com_minimo.sum())
    publicadas = sum(e["publicadas"] for e in estatisticas.values())
    total_linhas = sum(e["linhas"] for e in estatisticas.values())
    ints_1_9 = sum(1 for linha in texto.splitlines() if linha.startswith("|")
                   for celula in linha.split("|") if celula.strip().isdigit()
                   and 1 <= int(celula.strip()) <= 9)
    return [
        verify.check("perfis_grupo_1", esperado["perfis_grupo_1"], estatisticas[1]["perfis"]),
        verify.check("perfis_grupo_2", esperado["perfis_grupo_2"], estatisticas[2]["perfis"]),
        verify.check("perfis_grupo_3", esperado["perfis_grupo_3"], estatisticas[3]["perfis"]),
        verify.check("pares_dados_insuficientes", esperado["pares_excluidos"],
                     estatisticas[3]["insuficientes"]),
        verify.check("pares_incluidos", esperado["pares_incluidos"], len(e1.pares_incluidos)),
        verify.check("combinacoes_3_ou_mais_no_arquivo", esperado["combinacoes_3_ou_mais"],
                     len(combinacoes)),
        verify.check("combinacoes_3_ou_mais_com_minimo",
                     esperado["combinacoes_3_ou_mais_com_minimo"], n_com_minimo),
        verify.check("perfis_grupo_4_com_minimo", esperado["perfis_grupo_4"],
                     estatisticas[4]["perfis"]),
        verify.check("perfis_grupo_4_com_estimativa", esperado["perfis_grupo_4_com_estimativa"],
                     estatisticas[4]["perfis"] - estatisticas[4]["insuficientes"]),
        verify.check("perfis_grupo_4_dados_insuficientes",
                     esperado["perfis_grupo_4_dados_insuficientes"],
                     estatisticas[4]["insuficientes"]),
        verify.check("celulas_publicadas_com_minimo", esperado["celulas_publicadas"], publicadas),
        verify.check("numeros_1_a_9_nas_tabelas", 0, ints_1_9),
        verify.check("linhas_completa", esperado["linhas_tabela_perfis"], total_linhas),
    ]


# --- Padrão "todas as 7 comorbidades = Sim": investigação e sensibilidade -----------------------
# Diagnóstico pedido pelo Programador. Nada aqui muda a população, os dados de data/e1/ nem os
# relatórios aprovados. As colunas de diagnóstico não entram em modelo algum (R4).

NOME_PADRAO_DUMMY = "Padrão todas as 7 = Sim"
# DT_NOTIFIC já está na população (POPULATION_COLUMNS); só vêm as colunas que faltam.
COLUNAS_DIAGNOSTICO = ["ID_UNIDADE", "ID_MUNICIP", "SG_UF_NOT"]
SEM_CODIGO = "(sem código)"


def _pasta_qualidade(cfg: dict) -> Path:
    return Path(cfg["caminhos"]["dados"]) / "qualidade"


def padrao_todas_sim(df: pd.DataFrame) -> pd.Series:
    """Casos com as 7 comorbidades = Sim. Só diagnóstico e sensibilidade (nunca feature, R4)."""
    assert_dev_only(df)
    return (df[list(COMORBIDADES)] == "Sim").all(axis=1)


def _mascara_linhas(df: pd.DataFrame) -> np.ndarray:
    mascara = np.zeros(len(df), dtype=np.int64)
    for i, c in enumerate(COMORBIDADES):
        mascara |= (df[c] == "Sim").to_numpy().astype(np.int64) << i
    return mascara


def _acrescentar_diagnostico(cfg: dict, df: pd.DataFrame) -> pd.DataFrame:
    """Junta à população as colunas de diagnóstico do Parquet, pela linha de origem (ANO, LINHA).

    `LINHA` é a posição da linha no Parquet do ano (T-2.1), então o pareamento é exato.
    """
    assert_dev_only(df)
    partes = []
    for ano in sorted(int(a) for a in df["ANO"].unique()):
        mascara_ano = (df["ANO"] == ano).to_numpy()
        linhas = df.loc[mascara_ano, "LINHA"].to_numpy()
        tabela = pq.read_table(dataset.parquet_path(cfg, ano),
                               columns=COLUNAS_DIAGNOSTICO).to_pandas()
        parte = tabela.iloc[linhas].copy()
        parte.index = df.index[mascara_ano]
        partes.append(parte)
    return df.join(pd.concat(partes))


def _chave(df: pd.DataFrame, coluna: str) -> np.ndarray:
    return df[coluna].astype(object).where(df[coluna].notna(), SEM_CODIGO).astype(str).to_numpy()


def _tabela_por(chave: np.ndarray, padrao: np.ndarray, y: np.ndarray) -> pd.DataFrame:
    """Casos, eventos e os mesmos com o padrão, por categoria de `chave`."""
    tab = pd.DataFrame({"chave": chave, "casos": 1, "eventos": y, "casos_padrao": padrao,
                        "eventos_padrao": y * padrao})
    return tab.groupby("chave").sum()


def concentracao(tab: pd.DataFrame) -> dict:
    """Quantas unidades (ou municípios) respondem por 50% e 90% dos casos, nas duas distribuições.

    `tab` tem uma linha por unidade, com `casos_padrao` e `casos`. Sem código não entra. HHI é a
    soma dos quadrados das participações (1 = tudo em uma unidade; perto de 0 = disperso).
    """
    tab = tab.drop(index=SEM_CODIGO, errors="ignore")
    saida = {"unidades_com_padrao": int((tab["casos_padrao"] > 0).sum()),
             "unidades_com_casos": int((tab["casos"] > 0).sum())}
    for nome, serie in (("padrao", tab["casos_padrao"]), ("geral", tab["casos"])):
        s = serie[serie > 0].sort_values(ascending=False).astype(float)
        total = float(s.sum())
        cum = s.cumsum() / total
        participacao = s / total
        saida[nome] = {
            "n_50": int((cum < 0.5).sum() + 1),
            "n_90": int((cum < 0.9).sum() + 1),
            "top1": float(participacao.iloc[0]),
            "top10": float(participacao.iloc[:10].sum()),
            "hhi": float((participacao ** 2).sum()),
        }
    return saida


def _mes_publicavel(datas: pd.Series) -> np.ndarray:
    mes = datas.dt.strftime("%Y-%m").fillna(SEM_CODIGO)
    dentro = mes.str[:4].isin(["2022", "2023"]) | (mes == SEM_CODIGO)
    return np.where(dentro, mes, "fora de 2022–23").astype(object)


def resumo_padrao(df: pd.DataFrame) -> dict:
    """Agregados da investigação: escalares, tabelas por categoria e concentração (interno)."""
    assert_dev_only(df)
    padrao = padrao_todas_sim(df).to_numpy().astype(np.int64)
    y = df["y"].to_numpy().astype(np.int64)
    datas = parse_date(df["DT_NOTIFIC"])
    mascara = _mascara_linhas(df)
    tabelas = {
        "ano": _tabela_por(df["ANO"].astype(str).to_numpy(), padrao, y),
        "uf_notificacao": _tabela_por(_chave(df, "SG_UF_NOT"), padrao, y),
        "faixa_etaria": _tabela_por(df["faixa_etaria"].astype(str).to_numpy(), padrao, y),
        "sexo": _tabela_por(df["sexo"].astype(str).to_numpy(), padrao, y),
        "desfecho": _tabela_por(np.where(y == 1, "grave_ou_obito", "outro"), padrao, y),
        "n_comorbidades": _tabela_por(df["n_comorbidades"].astype(str).to_numpy(), padrao, y),
        # Datas fora de 2022–23 (notificações tardias de casos do arquivo) viram uma linha só:
        # a publicação não mostra 2024 (regra do projeto).
        "mes_notificacao": _tabela_por(_mes_publicavel(datas), padrao, y),
    }
    por_dia = _tabela_por(datas.dt.strftime("%Y-%m-%d").fillna(SEM_CODIGO).to_numpy(), padrao, y)
    por_dia = por_dia.drop(index=SEM_CODIGO, errors="ignore")
    seis = {}
    for m in range(1 << len(COMORBIDADES)):
        if bin(m).count("1") == len(COMORBIDADES) - 1:
            faltante = COMORBIDADES[next(i for i in range(len(COMORBIDADES)) if not m >> i & 1)]
            sel = mascara == m
            seis[f"todas exceto {faltante}"] = {"casos": int(sel.sum()),
                                                "eventos": int(y[sel].sum())}
    unidades = _tabela_por(_chave(df, "ID_UNIDADE"), padrao, y)
    municipios = _tabela_por(_chave(df, "ID_MUNICIP"), padrao, y)
    n_padrao = int(padrao.sum())
    escalares = {
        "casos": len(df), "eventos": int(y.sum()),
        "casos_padrao": n_padrao, "eventos_padrao": int(y[padrao == 1].sum()),
        "sem_unidade_no_padrao": int(((_chave(df, "ID_UNIDADE") == SEM_CODIGO)
                                      & (padrao == 1)).sum()),
        "sem_municipio_no_padrao": int(((_chave(df, "ID_MUNICIP") == SEM_CODIGO)
                                        & (padrao == 1)).sum()),
        "concentracao_unidade": concentracao(unidades),
        "concentracao_municipio": concentracao(municipios),
        "dia_pico_padrao": int(por_dia["casos_padrao"].max()),
        "top3_dias_padrao": float(por_dia["casos_padrao"].nlargest(3).sum() / max(n_padrao, 1)),
        "top3_dias_geral": float(por_dia["casos"].nlargest(3).sum() / len(df)),
    }
    return {"escalares": escalares, "tabelas": tabelas, "seis_comorbidades": seis,
            "unidades": unidades, "municipios": municipios, "por_dia": por_dia}


def investigar_padrao_todas_sim(cfg: dict) -> dict[str, Path]:
    """Investiga onde se concentram os casos com as 7 comorbidades = Sim em 2022–23.

    Saída interna (ids de unidade e de município, fora do git) em `data/qualidade/`, e o resumo
    publicável em `reports/qualidade/padrao_todas_sim.md`, só com agregados e células < 10
    suprimidas (R7). Não exclui nada: a decisão é do Programador.
    """
    populacao = dataset.load_population(cfg, list(cfg["anos_dev"]))
    assert_dev_only(populacao)
    df = dataset.build_feature_frame(populacao)
    del populacao
    df = _acrescentar_diagnostico(cfg, df)
    resumo = resumo_padrao(df)
    pasta_q = _pasta_qualidade(cfg)
    pasta_q.mkdir(parents=True, exist_ok=True)
    caminhos = {
        "unidades": pasta_q / "padrao_unidades.csv",
        "municipios": pasta_q / "padrao_municipios.csv",
        "resumo": pasta_q / "padrao_resumo.json",
        "publico": Path(cfg["caminhos"]["relatorios"]) / "qualidade" / "padrao_todas_sim.md",
    }
    resumo["unidades"].to_csv(caminhos["unidades"])
    resumo["municipios"].to_csv(caminhos["municipios"])
    interno = {"escalares": resumo["escalares"], "seis_comorbidades": resumo["seis_comorbidades"]}
    caminhos["resumo"].write_text(json.dumps(interno, ensure_ascii=False, indent=2, default=str),
                                  encoding="utf-8")
    caminhos["publico"].parent.mkdir(parents=True, exist_ok=True)
    minimo = int(cfg["supressao_min_celula"])
    caminhos["publico"].write_text(
        "\n".join(_md_investigacao(resumo, minimo)) + "\n", encoding="utf-8")
    return caminhos


def _celula(valor: int, minimo: int) -> str:
    return "—" if 0 < valor < minimo else str(valor)


def _md_investigacao(resumo: dict, minimo: int) -> list[str]:
    e = resumo["escalares"]
    t = resumo["tabelas"]
    cu, cm = e["concentracao_unidade"], e["concentracao_municipio"]

    def linhas_tabela(tab: pd.DataFrame, cabecalho: str) -> list[str]:
        # Cada tabela é uma partição dos casos com o padrão (somam 2.000, publicado no total). Uma
        # única célula suprimida sairia por subtração; então suprime-se também a menor célula
        # publicável, e a soma deixa de determinar a suprimida. Sem eventos por categoria: o nº
        # de eventos do padrão é "menos de 10" (R7), e uma contagem por categoria o revelaria.
        padrao = [int(v) for v in tab["casos_padrao"]]
        suprimidas = {i for i, v in enumerate(padrao) if 0 < v < minimo}
        if len(suprimidas) == 1:
            publicaveis = [i for i, v in enumerate(padrao) if v >= minimo]
            if publicaveis:
                suprimidas.add(min(publicaveis, key=lambda i: padrao[i]))
        corpo = []
        for i, (chave, r) in enumerate(tab.iterrows()):
            celula = "—" if i in suprimidas else _celula(padrao[i], minimo)
            corpo.append([str(chave), _celula(int(r["casos"]), minimo), celula])
        return [*_tabela([cabecalho, "Casos (todos)", "Casos com o padrão"], corpo), ""]

    def conc_linha(nome: str, c: dict) -> list[str]:
        return [nome, str(c["unidades_com_padrao"]), str(c["unidades_com_casos"]),
                f"{c['padrao']['n_50']} / {c['geral']['n_50']}",
                f"{c['padrao']['n_90']} / {c['geral']['n_90']}",
                _dec(100 * c["padrao"]["top1"], 1) + "%",
                _dec(100 * c["padrao"]["top10"], 1) + "%",
                _dec(c["padrao"]["hhi"], 3), _dec(c["geral"]["hhi"], 3)]

    seis_linhas = [[k, _celula(v["casos"], minimo), _celula(v["eventos"], minimo)
                    if v["casos"] >= minimo else "—"]
                   for k, v in resumo["seis_comorbidades"].items()]
    return [
        "# Padrão \"todas as 7 comorbidades = Sim\": investigação (diagnóstico)",
        "",
        AVISO_P6,
        "",
        "Dados de 2022–23 (desenvolvimento), população do D-45. Só agregados. Células com menos de "
        f"{minimo} casos aparecem como \"—\" (R7). Códigos de unidade e de município não são "
        "publicados; a concentração aparece só como número de unidades ou de municípios. A decisão "
        "sobre o padrão é do Programador; este relatório não exclui nada.",
        "",
        "A leitura é circunstancial; a causa do padrão não foi provada.",
        "",
        "## Total",
        "",
        f"- Casos com o padrão: {_dec(e['casos_padrao'], 0).replace(',', '.')} de "
        f"{_dec(e['casos'], 0).replace(',', '.')} (proporção "
        f"{_dec(100 * e['casos_padrao'] / e['casos'], 3)}%).",
        "- Eventos com o padrão: "
        + (str(e["eventos_padrao"]) if e["eventos_padrao"] >= minimo
           else f"menos de {minimo} (R7)")
        + f". Eventos do total de 2022–23: {e['eventos']}; risco geral de "
        f"{_dec(100 * e['eventos'] / e['casos'], 2)}%.",
        "",
        "## Por ano, UF de notificação, faixa e sexo",
        "",
        *linhas_tabela(t["ano"], "Ano"),
        *linhas_tabela(t["uf_notificacao"], "UF de notificação"),
        *linhas_tabela(t["faixa_etaria"], "Faixa etária"),
        *linhas_tabela(t["sexo"], "Sexo"),
        "## Número de comorbidades (exatas, de 0 a 7)",
        "",
        *linhas_tabela(t["n_comorbidades"], "Nº de comorbidades"),
        "## Mês de notificação",
        "",
        *linhas_tabela(t["mes_notificacao"], "Mês"),
        f"- Dia com mais casos do padrão: {_celula(e['dia_pico_padrao'], minimo)} casos. Os 3 dias "
        f"com mais casos do padrão concentram {_dec(100 * e['top3_dias_padrao'], 1)}% dos casos "
        "com "
        f"o padrão, contra {_dec(100 * e['top3_dias_geral'], 2)}% de todos os casos.",
        "",
        "## Padrões com 6 comorbidades (exatas)",
        "",
        *_tabela(["Padrão", "Casos", "Eventos"], seis_linhas),
        "",
        "## Concentração por unidade notificadora e por município de notificação",
        "",
        "N / N: primeiro número é a distribuição do padrão; o segundo, a dos casos gerais. N50 e "
        "N90 são o nº de unidades (ou municípios) que respondem por 50% e 90% dos casos. HHI perto "
        "de 0 "
        "é distribuição dispersa; perto de 1, concentrada.",
        "",
        *_tabela(["Coluna", "Unid. com o padrão", "Unid. com casos", "N50 (padrão / geral)",
                  "N90 (padrão / geral)", "Maior participação", "10 maiores", "HHI padrão",
                  "HHI geral"],
                 [conc_linha("Unidade notificadora", cu), conc_linha("Município", cm)]),
        "",
        "Casos do padrão sem código de unidade: "
        + (str(e["sem_unidade_no_padrao"]) if e["sem_unidade_no_padrao"] == 0 or
           e["sem_unidade_no_padrao"] >= minimo else f"menos de {minimo}")
        + " (os demais têm código).",
        "",
    ]


# --- Sensibilidade do E1 ao padrão (A: exclusão; B: dummy único; B saturado: verificação) -------

def _pares_de(df: pd.DataFrame) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Pares com >= MIN_EVENTOS_PAR eventos nesses dados (mesma regra do E1 principal)."""
    incluidos, excluidos = [], []
    for r in descriptive.pair_event_counts(df).itertuples(index=False):
        (incluidos if r.eventos >= MIN_EVENTOS_PAR else excluidos).append(
            (r.comorbidade_1, r.comorbidade_2))
    return incluidos, excluidos


def _ajustar_sobre(df: pd.DataFrame, nos: dict, incluidos: list, excluidos: list,
                   dummy: str | None = None) -> E1Ajustado:
    """Ajuste do E1 com a mesma fórmula, sobre `df`, com o desenho e os nós dados.

    dummy: None; "unico" (um indicador do padrão todas as 7 = Sim); "saturado" (um indicador por
    padrão de covariáveis do grupo, que equivale a excluir o grupo para os demais coeficientes).
    """
    assert_dev_only(df)
    agrupado = _agrupar(df)
    X = matriz_de_desenho(agrupado, nos, incluidos)
    niveis_vazios = [c for c in X.columns if X[c].sum() == 0]
    if niveis_vazios:
        raise ValueError(f"termos sem nenhum caso (matriz singular): {niveis_vazios}")
    padrao = (agrupado[list(COMORBIDADES)] == "Sim").all(axis=1).to_numpy()
    if dummy == "unico":
        X[NOME_PADRAO_DUMMY] = padrao.astype(float)
    elif dummy == "saturado":
        idx = np.flatnonzero(padrao)
        indicadores = np.zeros((len(agrupado), len(idx)))
        indicadores[idx, np.arange(len(idx))] = 1.0
        nomes = [f"{NOME_PADRAO_DUMMY}: covariáveis {k}" for k in range(1, len(idx) + 1)]
        X = pd.concat([X, pd.DataFrame(indicadores, index=X.index, columns=nomes)], axis=1)
    elif dummy is not None:
        raise ValueError(f"dummy desconhecido: {dummy}")
    eventos = agrupado["eventos"].to_numpy(dtype=float)
    casos = agrupado["casos"].to_numpy(dtype=float)
    inicio = time.perf_counter()
    resultados = _ajustar_glm(X, eventos, casos)
    tempo = time.perf_counter() - inicio
    if not resultados.converged:
        raise RuntimeError("E1 de sensibilidade não convergiu: ver Erros inesperados")
    termos_binarios = [c for c in X.columns if ": " in c and "spline" not in c]
    return E1Ajustado(
        resultados=resultados,
        colunas=list(X.columns),
        nos=nos,
        pares_incluidos=list(incluidos),
        pares_excluidos=list(excluidos),
        eventos_por_termo={c: int((X[c].to_numpy() * eventos).sum()) for c in termos_binarios},
        n_casos=int(casos.sum()),
        n_eventos=int(eventos.sum()),
        n_padroes=len(agrupado),
        tempo_ajuste_s=tempo,
        log_verossimilhanca=_log_verossimilhanca(eventos, casos, resultados.mu),
    )


def plausibilidade_3mais(e1: E1Ajustado, combinacoes: list[tuple[str, ...]],
                         idade: float = 70.0, sexo: str = "F") -> dict:
    """Perfis de 3 ou mais: quantos têm razão < 1 e quantos ficam abaixo do maior componente.

    Mesma idade e sexo da leitura principal (meio da faixa 60–79, F). "Componente" é o risco de
    cada comorbidade sozinha, na mesma idade e sexo.
    """
    razao_menor_1, abaixo_componente = [], []
    for nomes in combinacoes:
        nome = " + ".join(nomes)
        razao = razao_de_risco(e1, idade, sexo, 0, nomes)["razao"]
        risco = risco_perfil(e1, idade, sexo, 0, nomes)["risco"]
        maior = max(risco_perfil(e1, idade, sexo, 0, (c,))["risco"] for c in nomes)
        if razao < 1:
            razao_menor_1.append(nome)
        if risco < maior:
            abaixo_componente.append(nome)
    return {"n": len(combinacoes), "razao_menor_1": razao_menor_1,
            "abaixo_componente": abaixo_componente}


def _combinacoes_3_mais(cfg: dict, minimo: int) -> list[tuple[str, ...]]:
    tabela = ler_combinacoes(cfg)
    return [tuple(str(c).split(" + ")) for c, k, casos in
            zip(tabela["combinacao"], tabela["n_comorbidades"], tabela["casos"], strict=True)
            if int(k) >= 3 and int(casos) >= minimo]


def sensibilidade_e1(cfg: dict) -> dict[str, Path]:
    """Reajusta o E1 sem o padrão (A) e com um indicador dele (B), e compara com o principal.

    Os ajustes vão para `data/e1/sens/` (fora do git); `data/e1/` não é tocado. O relatório
    publicável é `reports/e1/sensibilidade_padrao_todas_sim.md` (só agregados, R7).
    """
    principal = load_e1(cfg)
    populacao = dataset.load_population(cfg, list(cfg["anos_dev"]))
    assert_dev_only(populacao)
    df = dataset.build_feature_frame(populacao)
    del populacao
    nos = principal.nos
    padrao = padrao_todas_sim(df).to_numpy()
    incl_full, _ = _pares_de(df)
    if set(incl_full) != set(principal.pares_incluidos):
        raise ValueError("pares do dado completo não batem com o E1 principal: refaça a T-3.1")
    df_a = df.loc[~padrao]
    incl_a, excl_a = _pares_de(df_a)
    ajustes = {
        "principal": principal,
        "A": _ajustar_sobre(df_a, nos, incl_a, excl_a),
        "B": _ajustar_sobre(df, nos, principal.pares_incluidos, principal.pares_excluidos,
                            dummy="unico"),
    }
    b_saturado = _ajustar_sobre(df, nos, incl_a, excl_a, dummy="saturado")
    pasta = _pasta_e1(cfg) / "sens"
    pasta.mkdir(parents=True, exist_ok=True)
    for nome in ("A", "B"):
        ajustes[nome].resultados.save(pasta / f"{nome}.pickle", remove_data=True)
    b_saturado.resultados.save(pasta / "B_saturado.pickle", remove_data=True)
    saida = escrever_sensibilidade(cfg, ajustes, b_saturado)
    saida["pasta_ajustes"] = pasta
    return saida


def escrever_sensibilidade(cfg: dict, ajustes: dict[str, E1Ajustado],
                           b_saturado: E1Ajustado) -> dict:
    """Calcula a comparação dos ajustes (principal, A, B e B saturado) e grava o relatório
    público. Não lê dados: só usa os ajustes e as contagens de `data/`. Chamada pelo ajuste
    (`sensibilidade_e1`) e pela regeneração a partir dos pickles (`regerar_sensibilidade`)."""
    principal = ajustes["principal"]
    minimo = int(cfg["supressao_min_celula"])
    seed = int(cfg["seed"])
    beta_a = pd.Series(np.asarray(ajustes["A"].resultados.params, dtype=float),
                       index=ajustes["A"].colunas)
    beta_s = pd.Series(np.asarray(b_saturado.resultados.params, dtype=float),
                       index=b_saturado.colunas)
    diferenca_saturado = float(np.max(np.abs(beta_a - beta_s[beta_a.index])))
    identificados = beta_a[beta_a.abs() < 10].index  # |β| >= 10: separação, não identificado
    diferenca_saturado_identificados = float(
        np.max(np.abs(beta_a[identificados] - beta_s[identificados])))
    beta_p = pd.Series(np.asarray(principal.resultados.params, dtype=float),
                       index=principal.colunas)
    beta_b = pd.Series(np.asarray(ajustes["B"].resultados.params, dtype=float),
                       index=ajustes["B"].colunas)
    diferenca_b_principal = float(np.max(np.abs(beta_p - beta_b[beta_p.index])))
    combinacoes = _combinacoes_3_mais(cfg, minimo)
    resultados = {}
    for nome, e1 in ajustes.items():
        resultados[nome] = {
            "efeitos": or_efeitos_principais(e1),
            "interacoes": or_interacoes(e1),
            "ranking": ranking_comorbidades(or_efeitos_principais(e1)),
            "reri_ap": reri_ap_pares(e1, seed=seed),
            "plausibilidade": plausibilidade_3mais(e1, combinacoes),
            "n_casos": e1.n_casos,
            "n_eventos": e1.n_eventos,
            "pares_incluidos": list(e1.pares_incluidos),
        }
    equivalencia = {
        "diferenca_maxima_A_x_B_saturado": diferenca_saturado,
        "diferenca_maxima_A_x_B_saturado_identificados": diferenca_saturado_identificados,
        "n_nao_identificados": int((beta_a.abs() >= 10).sum()),
        "diferenca_maxima_principal_x_B": diferenca_b_principal,
        "casos_excluidos_em_A": principal.n_casos - ajustes["A"].n_casos,
        "seed": seed,
    }
    publico = Path(cfg["caminhos"]["relatorios"]) / "e1" / "sensibilidade_padrao_todas_sim.md"
    publico.parent.mkdir(parents=True, exist_ok=True)
    publico.write_text("\n".join(_md_sensibilidade(principal, resultados, equivalencia,
                                                   minimo)) + "\n", encoding="utf-8")
    return {"publico": publico, "equivalencia": equivalencia, "resultados": resultados}


def _contagens_do_padrao(cfg: dict) -> dict:
    """Casos e eventos do padrão em 2022–23, de `data/qualidade/padrao_resumo.json` (interno)."""
    caminho = _pasta_qualidade(cfg) / "padrao_resumo.json"
    if not caminho.exists():
        raise FileNotFoundError(f"{caminho}: rode investigar_padrao_todas_sim(cfg) antes")
    escalares = json.loads(caminho.read_text(encoding="utf-8"))["escalares"]
    return {"casos": int(escalares["casos_padrao"]), "eventos": int(escalares["eventos_padrao"])}


def _ajustes_salvos(cfg: dict) -> dict[str, E1Ajustado]:
    """Principal, A, B e B saturado a partir de `data/e1/` e `data/e1/sens/`, sem recarregar
    os dados.

    Os pickles do statsmodels não guardam os nomes das colunas (`remove_data`), então as colunas
    são refeitas com o mesmo `matriz_de_desenho` e conferidas contra o nº de parâmetros de cada
    ajuste. Os pares de A saem de `pares_comorbidades.csv` menos os eventos do padrão: todo caso
    do padrão tem as 7 = Sim, então cada par perde exatamente esses eventos (a mesma regra de
    `_pares_de`, aplicada a dados sem o padrão).
    """
    import statsmodels.api as sm  # local: os pickles de sensibilidade são do statsmodels

    principal = load_e1(cfg)
    pasta = _pasta_e1(cfg) / "sens"
    tabela = pd.read_csv(Path(cfg["caminhos"]["dados"]) / "descritiva" / "pares_comorbidades.csv")
    eventos = {(r.comorbidade_1, r.comorbidade_2): int(r.eventos)
               for r in tabela.itertuples(index=False)}
    if set(p for p in PARES if eventos[p] >= MIN_EVENTOS_PAR) != set(principal.pares_incluidos):
        raise ValueError("pares de pares_comorbidades.csv não batem com o E1 principal: refaça a "
                         "T-2.6 e a T-3.1")
    padrao = _contagens_do_padrao(cfg)
    incl_a = [p for p in PARES if eventos[p] - padrao["eventos"] >= MIN_EVENTOS_PAR]
    excl_a = [p for p in PARES if p not in incl_a]
    molde = pd.DataFrame([{COLUNA_IDADE: float(IDADE_REFERENCIA), "sexo": "F", "gestante": 0,
                           **{c: "Não" for c in COMORBIDADES}}])
    colunas_a = list(matriz_de_desenho(molde, principal.nos, incl_a).columns)
    colunas_b = [*principal.colunas, NOME_PADRAO_DUMMY]

    def carregar(nome: str, colunas: list[str], incl: list, excl: list, n_casos: int,
                 n_eventos: int) -> E1Ajustado:
        resultados = sm.load_pickle(pasta / f"{nome}.pickle")
        if len(colunas) != len(resultados.params):
            raise ValueError(f"{nome}: {len(colunas)} colunas e {len(resultados.params)} "
                             "parâmetros: refaça a sensibilidade (T-3.5)")
        return E1Ajustado(
            resultados=resultados, colunas=colunas, nos=principal.nos, pares_incluidos=incl,
            pares_excluidos=excl, eventos_por_termo={}, n_casos=n_casos, n_eventos=n_eventos,
            n_padroes=0, tempo_ajuste_s=0.0, log_verossimilhanca=0.0,
        )

    a = carregar("A", colunas_a, incl_a, excl_a,
                 principal.n_casos - padrao["casos"], principal.n_eventos - padrao["eventos"])
    b = carregar("B", colunas_b, list(principal.pares_incluidos),
                 list(principal.pares_excluidos), principal.n_casos, principal.n_eventos)
    n_extra = len(sm.load_pickle(pasta / "B_saturado.pickle").params) - len(colunas_a)
    colunas_s = [*colunas_a, *(f"{NOME_PADRAO_DUMMY}: covariáveis {k}"
                               for k in range(1, n_extra + 1))]
    s = carregar("B_saturado", colunas_s, incl_a, excl_a, principal.n_casos, principal.n_eventos)
    return {"principal": principal, "A": a, "B": b, "B_saturado": s}


def contexto_padrao(cfg: dict) -> dict:
    """O que os relatórios do E1 dizem sobre o padrão, derivado do cenário A (salvo, sem dados)."""
    ajustes = _ajustes_salvos(cfg)
    principal, a = ajustes["principal"], ajustes["A"]
    sem_padrao = set(a.pares_incluidos)
    padrao = _contagens_do_padrao(cfg)

    def ranking(e1: E1Ajustado) -> list[str]:
        return [r["comorbidade"] for r in ranking_comorbidades(or_efeitos_principais(e1))["ordem"]]

    return {
        "casos_padrao": padrao["casos"],
        "casos": principal.n_casos,
        "pares_sensiveis": [p for p in principal.pares_incluidos if p not in sem_padrao],
        "ranking_principal": ranking(principal),
        "ranking_a": ranking(a),
    }


def nota_padrao(ctx: dict) -> list[str]:
    """Nota sobre o padrão suspeito, igual nos relatórios de OR, RERI e AP e de ranking (T-3.2)."""
    casos = f"{ctx['casos_padrao']:,}".replace(",", ".")
    proporcao = _dec(100 * ctx["casos_padrao"] / ctx["casos"], 2)
    pares = ctx["pares_sensiveis"]
    if len(pares) == 1:
        pares_txt = (f"O par {_lista_pares(pares)} só tem 10 ou mais eventos por causa do padrão; "
                     "sem ele, sai do E1.")
    elif pares:
        pares_txt = (f"Os pares {_lista_pares(pares)} só têm 10 ou mais eventos por causa do "
                     "padrão; sem ele, saem do E1.")
    else:
        pares_txt = "Nenhum par do E1 depende do padrão."
    rp, ra = ctx["ranking_principal"], ctx["ranking_a"]
    diferentes = [i for i, (p, a) in enumerate(zip(rp, ra, strict=True)) if p != a]
    if diferentes:
        posicoes = _lista_e([str(i + 1) for i in diferentes])
        ranking_txt = (
            f"Sem o padrão, o ranking muda nas posições {posicoes}: "
            f"passa a ser {_lista_e([ra[i] for i in diferentes])} (no principal, "
            f"{_lista_e([rp[i] for i in diferentes])}).")
    else:
        ranking_txt = "Sem o padrão, o ranking não muda."
    return [
        f"**Padrão suspeito \"todas as 7 comorbidades = Sim\".** {casos} casos ({proporcao}% da "
        "população de 2022–23) têm as 7 comorbidades = Sim, com risco parecido com o geral. Esse "
        "padrão influencia parte dos resultados. A sensibilidade oficial, sem esses casos, está em "
        f"[sensibilidade_padrao_todas_sim.md](sensibilidade_padrao_todas_sim.md). {pares_txt} "
        f"{ranking_txt}",
    ]


def regerar_sensibilidade(cfg: dict) -> Path:
    """Regrava `reports/e1/sensibilidade_padrao_todas_sim.md` a partir dos ajustes salvos,
    sem recarregar os dados (a mudança de texto não exige refazer os ajustes)."""
    ajustes = _ajustes_salvos(cfg)
    return escrever_sensibilidade(cfg, {k: ajustes[k] for k in ("principal", "A", "B")},
                                  ajustes["B_saturado"])["publico"]


def _md_sensibilidade(principal: E1Ajustado, res: dict, equivalencia: dict,
                      minimo: int) -> list[str]:
    def or_txt(linha: dict) -> str:
        return f"{_dec(linha['or'])} {_ic_txt(linha['ic_inferior'], linha['ic_superior'])}"

    efeitos = {n: {r["comorbidade"]: r for r in res[n]["efeitos"]} for n in res}
    efeitos_linhas = [[c, or_txt(efeitos["principal"][c]), or_txt(efeitos["A"][c]),
                       or_txt(efeitos["B"][c])] for c in COMORBIDADES]
    inter = {n: {(r["comorbidade_1"], r["comorbidade_2"]): r for r in res[n]["interacoes"]}
             for n in res}
    todos_pares = sorted(set().union(*(set(inter[n]) for n in res)),
                         key=lambda p: explain_ordem(p))
    inter_linhas = []
    for par in todos_pares:
        linha = [f"{par[0]} × {par[1]}"]
        for n in ("principal", "A", "B"):
            r = inter[n].get(par)
            if r is None:
                linha.append("—")
            else:
                linha.append(f"{_dec(r['or'])} {_ic_txt(r['ic_inferior'], r['ic_superior'])}; "
                             f"p ajust. {_p_txt(r['p_ajustado'])}")
        inter_linhas.append(linha)
    entram_a = sorted(set(inter["A"]) - set(inter["principal"]), key=explain_ordem)
    saem_a = sorted(set(inter["principal"]) - set(inter["A"]), key=explain_ordem)
    entram_b = sorted(set(inter["B"]) - set(inter["principal"]), key=explain_ordem)
    saem_b = sorted(set(inter["principal"]) - set(inter["B"]), key=explain_ordem)
    rank = {n: [r["comorbidade"] for r in res[n]["ranking"]["ordem"]] for n in res}
    rank_linhas = [[str(i + 1), rank["principal"][i], rank["A"][i], rank["B"][i]]
                   for i in range(len(COMORBIDADES))]
    plaus = {n: res[n]["plausibilidade"] for n in res}
    plaus_linhas = [[n, str(plaus[n]["n"]), str(len(plaus[n]["razao_menor_1"])),
                     str(len(plaus[n]["abaixo_componente"]))] for n in res]
    mudancas = [f"{c}: {_dec(efeitos['principal'][c]['or'])} → {_dec(efeitos['A'][c]['or'])}"
                for c in COMORBIDADES]
    pior = max(abs(np.log(efeitos["A"][c]["or"] / efeitos["principal"][c]["or"]))
               for c in COMORBIDADES)
    posicoes_que_mudam = [i for i in range(len(COMORBIDADES))
                          if rank["principal"][i] != rank["A"][i]]
    ic_negativo = {n: sum(1 for r in res[n]["interacoes"] if r["ic_superior"] < 1) for n in res}
    or_acido = {n: efeitos[n]["ACIDO_PEPT"]["or"] for n in ("principal", "A")}

    def lista(xs: list[tuple[str, str]]) -> str:
        return ", ".join(f"{a} × {b}" for a, b in xs) or "nenhum"

    ordem_txt = (
        "A ordem é a mesma nas 7 posições." if not posicoes_que_mudam else
        "A ordem muda nas posições " + _lista_e([str(i + 1) for i in posicoes_que_mudam])
        + ": " + _lista_e([f"{rank['A'][i]} (principal: {rank['principal'][i]})"
                           for i in posicoes_que_mudam]) + ".")
    acido_txt = (
        f"Sem o padrão, ACIDO_PEPT fica **mais** protetor ({_dec(or_acido['A'])} contra "
        f"{_dec(or_acido['principal'])} no principal). A hipótese de que o padrão explica o OR "
        "protetor de ACIDO_PEPT **não se confirmou**."
        if or_acido["A"] < or_acido["principal"] else
        f"Sem o padrão, ACIDO_PEPT deixa de ser mais protetor ({_dec(or_acido['A'])} contra "
        f"{_dec(or_acido['principal'])} no principal): a hipótese de que o padrão explica o OR "
        "protetor se confirmou.")
    negativas_txt = (
        f"As interações com IC 95% inteiro abaixo de 1 são {ic_negativo['A']} em A (contra "
        f"{ic_negativo['principal']} no principal). As interações negativas **persistem** sem o "
        "padrão: ele explica só parte delas."
        if ic_negativo["A"] > 0 else
        "Sem o padrão, nenhuma interação tem IC 95% inteiro abaixo de 1.")

    return [
        "# Sensibilidade do E1 ao padrão \"todas as 7 comorbidades = Sim\"",
        "",
        AVISO_P6,
        "",
        "A leitura é circunstancial; a causa do padrão não foi provada.",
        "**Sensibilidade oficial: o cenário A** (decisão do Programador). É a análise citada nos "
        "demais relatórios do E1. Três ajustes com a mesma fórmula, os mesmos nós de idade e o "
        f"recentramento em 40 (D-41/T-3.1). Principal: todos os casos de 2022–23. **A**: sem os "
        f"casos com as 7 comorbidades = Sim ({equivalencia['casos_excluidos_em_A']} casos "
        "excluídos; pares recalculados nesse dado). **B**: o principal mais um indicador do "
        "padrão, sem excluir casos. Logística sem penalização (R9). IC 95% pelo delta, como no "
        "principal (D-40). P-valores ajustados por Benjamini-Hochberg sobre os pares incluídos.",
        "",
        "## Verificação de equivalência",
        "",
        "- A × B com **indicador por padrão de covariáveis** (saturado): em teoria, equivale a "
        "excluir o grupo para os demais coeficientes. **Não confirmado com estes dados**: maior "
        f"diferença nos coeficientes identificados (|β| < 10) = "
        f"{_dec(equivalencia['diferenca_maxima_A_x_B_saturado_identificados'], 3)}, "
        "contra a tolerância "
        f"de 1e-6. Com {equivalencia['n_nao_identificados']} termos em separação quase perfeita "
        "(|β| ≥ 10), o MLE dos indicadores por caso não converge de forma estável.",
        f"- Principal × B com **um único indicador**: maior diferença nos coeficientes comuns = "
        f"{_dec(equivalencia['diferenca_maxima_principal_x_B'], 3)} (no log-OR). "
        "**B não equivale a "
        "excluir os casos.** A equivalência só valeria com um indicador por padrão de covariáveis "
        "(bullet acima), e não se confirmou aqui. Por isso B é só leitura complementar; A é a "
        "referência.",
        "",
        "## Efeitos principais (OR, IC 95%)",
        "",
        *_tabela(["Comorbidade", "Principal", "A (sem o padrão)", "B (indicador único)"],
                 efeitos_linhas),
        "",
        "DIABETES e HIPERTENSA aos 40 anos, como no principal.",
        "",
        f"Maior variação de OR de efeito principal entre o principal e A: |log| = {_dec(pior, 3)}. "
        "Mudanças "
        f"(principal → A): {'; '.join(mudancas)}.",
        "",
        "## Interações 2 a 2 (OR da interação, IC 95%, p ajustado BH)",
        "",
        *_tabela(["Par", "Principal", "A", "B"], inter_linhas),
        "",
        f"Pares que **entram** no E1 em A: {lista(entram_a)}. Pares que **saem** em A: "
        f"{lista(saem_a)}.",
        f"Em B: entram {lista(entram_b)}; saem {lista(saem_b)}.",
        "",
        "## Ranking de comorbidades (só pelo E1, R10)",
        "",
        *_tabela(["Posição", "Principal", "A", "B"], rank_linhas),
        "",
        "## Plausibilidade dos perfis de 3 ou mais (razão vs. saudável, 60–79, F)",
        "",
        *_tabela(["Ajuste", "Perfis de 3+", "Razão < 1", "Abaixo do maior componente"],
                 plaus_linhas),
        "",
        f"Perfis com razão < 1 em A: {', '.join(plaus['A']['razao_menor_1']) or 'nenhum'}.",
        "",
        "## Conclusão objetiva",
        "",
        f"- Efeitos principais: a maior variação de OR entre principal e A é um fator de "
        f"{_dec(np.exp(pior))}.",
        f"- Ranking: principal {' > '.join(rank['principal'][:3])} …; A "
        f"{' > '.join(rank['A'][:3])} …. {ordem_txt}",
        f"- Interações: {len(inter['principal'])} pares no principal, {len(inter['A'])} em A, "
        f"{len(inter['B'])} em B. {negativas_txt}",
        f"- ACIDO_PEPT: {acido_txt}",
        f"- Perfis de 3+ com razão < 1: principal {len(plaus['principal']['razao_menor_1'])}, "
        f"A {len(plaus['A']['razao_menor_1'])}, B {len(plaus['B']['razao_menor_1'])} (de "
        f"{plaus['principal']['n']}).",
        "",
        "Sensibilidade oficial: cenário A, decidida pelo Programador. Os relatórios principais do "
        "E1 não excluem os casos do padrão; citam este cenário.",
        "",
    ]


def explain_ordem(par: tuple[str, str]) -> tuple[int, int]:
    """Ordem fixa dos pares (a de PARES), para tabelas estáveis."""
    return (PARES.index(par) if par in PARES else len(PARES), 0)


# --- Execução ----------------------------------------------------------------------------------

def executar_e1(cfg: dict) -> E1Ajustado:
    """Carrega 2022–23, ajusta o E1, checa a equivalência, salva e escreve o relatório."""
    anos = list(cfg["anos_dev"])
    populacao = dataset.load_population(cfg, anos)
    assert_dev_only(populacao)
    df = dataset.build_feature_frame(populacao)
    del populacao
    e1 = ajustar_e1(cfg, df)
    logger.info("E1 ajustado em %.1f s", e1.tempo_ajuste_s)
    equivalencia = checar_equivalencia(df, e1, e1.pares_incluidos,
                                       TAMANHO_AMOSTRA_EQUIVALENCIA, int(cfg["seed"]))
    salvar_e1(cfg, e1, equivalencia)
    escrever_relatorio(cfg, e1, equivalencia)
    return e1


if __name__ == "__main__":
    executar_e1(load_config())
