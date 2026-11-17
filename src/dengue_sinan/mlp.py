"""MLP do M1 em PyTorch (T-4.6b, D-53, R1, R3, R5, R6, R8, FR-22).

Entra no `REGISTRO` de `cv.py` como `"mlp"`; o laço não muda. É iterativo: o laço passa o treino
sem a validação interna em `X_treino` e a validação interna (R6, das 4 regiões de treino) em
`X_parada`. A parada usa só `X_parada`: ao fim de cada época, a PR-AUC da validação interna. Nunca
usa a região deixada de fora.

Pré-processamento: família "linear" (spline + escala + one-hot, sem interações: a rede aprende as
interações; D-63). Dentro de um `Pipeline` (R5), ajustado só com o treino da dobra. A saída é CSR
float32, e a rede nunca recebe a matriz inteira densa: cada lote de treino e cada bloco de
predição vira denso só naquelas linhas (`_linhas`).

Rede: camadas ocultas com ReLU e dropout, uma saída (logit). Perda `BCEWithLogitsLoss` **sem
`pos_weight`** (R3), otimizador Adam com `weight_decay`. Sem peso de classe em nenhum lugar.

Early stopping (R6): paciência de `paciencia_epocas` épocas sem melhora da PR-AUC na validação
interna, com teto `epocas_max`. Ao fim, restaura os pesos da melhor época. `melhor_ponto` é esse
número de épocas (1-based: "treinou 37 épocas e a melhor foi a 37ª").

Rótulos das camadas (o espaço de busca guarda texto): "64" = [64]; "128x64" = [128, 64].

Semente (R8): `torch.manual_seed` e `torch.cuda.manual_seed_all` com a semente do config, no início
de cada ajuste, e um gerador próprio para embaralhar os lotes. Determinismo garantido no CPU (mesma
semente, mesmos bits). No GPU, `CUBLAS_WORKSPACE_CONFIG` é fixado para as multiplicações serem
deterministas; mesmo assim a conferência bit a bit é feita no CPU (testes), e o GPU fica registrado.

Dispositivo: `"cuda"` se houver GPU, senão `"cpu"`. Um parâmetro `device` explícito tem prioridade,
e `"cuda"` sem GPU levanta erro (sem troca silenciosa). Contrato `ModeloM1` em `cv.py`.
"""

from __future__ import annotations

import os
import re
from typing import Any

import mlflow
import numpy as np
import scipy.sparse as sp
import torch
from sklearn.base import BaseEstimator
from sklearn.pipeline import Pipeline
from torch import nn

from dengue_sinan import metrics
from dengue_sinan.guard import assert_dev_only
from dengue_sinan.preprocess import make_preprocessor
from dengue_sinan.search_space import PROIBIDOS_R3

PERDA = "BCEWithLogitsLoss"
OTIMIZADOR = "Adam"
CHAVE_DISPOSITIVO = "device"  # parâmetro opcional: "cpu" ou "cuda"; sobrepõe a detecção
PARAM_MLFLOW_DISPOSITIVO = "mlp.device"
METRICA_MLFLOW_MELHOR = "mlp.melhor_epoca"
TAMANHO_BLOCO_PREDICAO = 65_536  # linhas densas por bloco na predição (memória)
_CAMADAS = re.compile(r"^\d+(x\d+)*$")
_OBRIGATORIOS = {
    "camadas_ocultas", "dropout", "weight_decay", "lr", "batch_size", "epocas_max",
    "paciencia_epocas",
}
def _preparar_determinismo() -> None:
    """CUBLAS_WORKSPACE_CONFIG é exigido pelo torch para algoritmos deterministas no CUDA. Só vale
    antes do primeiro uso da GPU no processo, por isso é definido aqui, no início do ajuste."""
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")


def camadas_de_rotulo(rotulo: str) -> list[int]:
    """"64" -> [64]; "128x64" -> [128, 64]. Levanta ValueError para outro texto ou tamanho <= 0."""
    if not isinstance(rotulo, str) or not _CAMADAS.match(rotulo):
        raise ValueError(f"camadas_ocultas {rotulo!r} inválido; use texto como '64' ou '128x64'")
    camadas = [int(parte) for parte in rotulo.split("x")]
    if min(camadas) < 1:
        raise ValueError(f"camadas_ocultas {rotulo!r}: cada camada precisa de 1 neurônio ou mais")
    return camadas


def detectar_dispositivo() -> str:
    """"cuda" se o torch enxerga uma GPU, senão "cpu"."""
    return "cuda" if torch.cuda.is_available() else "cpu"


def _linhas(X, sel) -> np.ndarray:
    """Linhas `sel` de `X` como array denso float32. Com CSR, só essas linhas viram densas."""
    parte = X[sel]
    if sp.issparse(parte):
        parte = parte.toarray()
    return np.asarray(parte, dtype=np.float32)


def _rede(d_entrada: int, camadas: list[int], dropout: float) -> nn.Sequential:
    modulos: list[nn.Module] = []
    d = d_entrada
    for h in camadas:
        modulos += [nn.Linear(d, h), nn.ReLU(), nn.Dropout(dropout)]
        d = h
    modulos.append(nn.Linear(d, 1))  # logit
    return nn.Sequential(*modulos)


def _probabilidades(rede: nn.Module, X, dispositivo: torch.device) -> np.ndarray:
    """P(y = 1) de cada linha de X, em blocos (nunca a matriz inteira densa)."""
    rede.eval()
    saida = np.empty(X.shape[0], dtype=np.float64)
    with torch.no_grad():
        for ini in range(0, X.shape[0], TAMANHO_BLOCO_PREDICAO):
            sel = slice(ini, min(ini + TAMANHO_BLOCO_PREDICAO, X.shape[0]))
            logit = rede(torch.from_numpy(_linhas(X, sel)).to(dispositivo)).squeeze(1)
            saida[sel] = torch.sigmoid(logit).double().cpu().numpy()
    return saida


class EstimadorMLP(BaseEstimator):
    """Rede PyTorch com interface sklearn (`fit`, `predict_proba`) para entrar no `Pipeline` (R5).

    `fit` recebe a validação interna (`X_parada`, `y_parada`) já transformada pelo pré-processador
    do treino; ela só serve à parada antecipada (R6).
    """

    def __init__(self, camadas=(64,), dropout=0.0, weight_decay=0.0, lr=1e-3, batch_size=1024,
                 epocas_max=200, paciencia_epocas=10, seed=0, dispositivo="cpu",
                 epocas_fixas=None):
        self.camadas = camadas
        self.dropout = dropout
        self.weight_decay = weight_decay
        self.lr = lr
        self.batch_size = batch_size
        self.epocas_max = epocas_max
        self.paciencia_epocas = paciencia_epocas
        self.seed = seed
        self.dispositivo = dispositivo
        self.epocas_fixas = epocas_fixas  # retreino final (T-4.10): sem parada, nº fixo de épocas

    def fit(self, X, y, X_parada=None, y_parada=None):
        if self.epocas_fixas is not None:
            if X_parada is not None or y_parada is not None:
                raise ValueError("MLP com épocas fixas não usa validação de parada")
            y_p = None
        else:
            if X_parada is None or y_parada is None:
                raise ValueError("MLP é iterativo: precisa de X_parada e y_parada (R6)")
            y_p = np.asarray(y_parada)
            if not (y_p == 1).any():
                raise ValueError("validação interna sem positivos: a parada não tem o que medir")
        y = np.asarray(y, dtype=np.float32)
        _preparar_determinismo()
        torch.manual_seed(int(self.seed))  # R8
        torch.cuda.manual_seed_all(int(self.seed))  # R8
        dispositivo = torch.device(self.dispositivo)
        anterior = torch.are_deterministic_algorithms_enabled()
        torch.use_deterministic_algorithms(True, warn_only=True)
        try:
            self._treinar(X, y, X_parada, y_p, dispositivo)
        finally:
            torch.use_deterministic_algorithms(anterior)
        return self

    def _treinar(self, X, y, X_parada, y_p, dispositivo) -> None:
        fixo = self.epocas_fixas is not None
        rede = _rede(X.shape[1], list(self.camadas), float(self.dropout)).to(dispositivo)
        otimizador = torch.optim.Adam(
            rede.parameters(), lr=float(self.lr), weight_decay=float(self.weight_decay))
        perda_fn = nn.BCEWithLogitsLoss()  # sem pos_weight (R3)
        gerador = torch.Generator().manual_seed(int(self.seed))  # embaralhamento dos lotes (R8)
        n = X.shape[0]
        self.historico_: list[dict[str, float]] = []
        limite = int(self.epocas_fixas) if fixo else int(self.epocas_max)
        melhor_pr, melhor_epoca, melhor_estado, sem_melhora = -np.inf, None, None, 0
        for epoca in range(1, limite + 1):
            rede.train()
            perm = torch.randperm(n, generator=gerador).numpy()
            soma = 0.0
            for ini in range(0, n, int(self.batch_size)):
                sel = perm[ini:ini + int(self.batch_size)]
                xb = torch.from_numpy(_linhas(X, sel)).to(dispositivo)
                yb = torch.from_numpy(y[sel]).to(dispositivo)
                perda = perda_fn(rede(xb).squeeze(1), yb)
                otimizador.zero_grad()
                perda.backward()
                otimizador.step()
                soma += float(perda.detach()) * len(sel)
            if fixo:  # sem validação e sem restauração: fica a rede da última época
                self.historico_.append({"epoca": epoca, "perda_treino": soma / n})
                continue
            pr = metrics.pr_auc(y_p, _probabilidades(rede, X_parada, dispositivo))  # R6
            self.historico_.append({"epoca": epoca, "perda_treino": soma / n, "pr_auc_parada": pr})
            if pr > melhor_pr:
                melhor_pr, melhor_epoca, sem_melhora = pr, epoca, 0
                melhor_estado = {k: v.detach().clone().cpu() for k, v in rede.state_dict().items()}
            else:
                sem_melhora += 1
                if sem_melhora >= int(self.paciencia_epocas):
                    break
        if fixo:
            melhor_epoca = limite
        else:
            rede.load_state_dict(melhor_estado)  # FR-22: pesos da melhor época
        self._rede = rede
        self._dispositivo_efetivo = dispositivo
        self.melhor_epoca_ = int(melhor_epoca)

    def predict_proba(self, X) -> np.ndarray:
        if not hasattr(self, "_rede"):
            raise RuntimeError("chame fit antes de prever")
        p = _probabilidades(self._rede, X, self._dispositivo_efetivo)
        return np.column_stack([1.0 - p, p])

    def para_cpu(self) -> None:
        """Move a rede ajustada para a CPU. Um artefato salvo com tensores de GPU não carrega
        numa máquina sem GPU (a demo), então o salvamento chama isto antes."""
        if not hasattr(self, "_rede"):
            raise RuntimeError("chame fit antes de mover")
        self._rede.cpu()
        self._dispositivo_efetivo = torch.device("cpu")
        self.dispositivo = "cpu"


class MLPM1:
    """MLP como `ModeloM1` (ver `cv.py`). Um objeto novo por dobra."""

    iterativo = True

    def __init__(self, params: dict[str, Any], seed: int) -> None:
        params = dict(params)
        dispositivo = params.pop(CHAVE_DISPOSITIVO, None)
        proibidos = sorted(k for k in params if any(p in k.lower() for p in PROIBIDOS_R3))
        if proibidos:
            raise ValueError(f"parâmetros de peso de classe proibidos (R3): {proibidos}")
        if params.get("perda") != PERDA:
            raise ValueError(f"mlp: perda deve ser {PERDA!r} (R3: sem pos_weight)")
        if params.get("otimizador") != OTIMIZADOR:
            raise ValueError(f"mlp: otimizador deve ser {OTIMIZADOR!r}")
        del params["perda"], params["otimizador"]
        faltando = sorted(_OBRIGATORIOS - set(params))
        sobrando = sorted(set(params) - _OBRIGATORIOS)
        if faltando or sobrando:
            raise ValueError(f"mlp: faltam {faltando}; sobram {sobrando}")
        if dispositivo not in (None, "cpu", "cuda"):
            raise ValueError(f"mlp: device {dispositivo!r} inválido; use 'cpu' ou 'cuda'")
        for nome in ("epocas_max", "paciencia_epocas", "batch_size"):
            if int(params[nome]) < 1:
                raise ValueError(f"mlp: {nome} deve ser pelo menos 1")
        self._dispositivo = dispositivo or detectar_dispositivo()
        if self._dispositivo == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("mlp: device 'cuda' pedido, mas o torch não enxerga GPU")
        self._estimador = EstimadorMLP(
            camadas=tuple(camadas_de_rotulo(params["camadas_ocultas"])),
            dropout=float(params["dropout"]),
            weight_decay=float(params["weight_decay"]),
            lr=float(params["lr"]),
            batch_size=int(params["batch_size"]),
            epocas_max=int(params["epocas_max"]),
            paciencia_epocas=int(params["paciencia_epocas"]),
            seed=int(seed),  # R8
            dispositivo=self._dispositivo,
        )
        self._pipeline = Pipeline([
            ("preprocessamento", make_preprocessor("linear")),  # R4, R5
            ("mlp", self._estimador),
        ])
        self._melhor: int | None = None
        self._fixas: int | None = None

    def fixar_iteracoes(self, n: int) -> None:
        """Retreino final (T-4.10): treina exatamente `n` épocas, sem validação de parada e sem
        restaurar a melhor época. Chame antes de `ajustar`. O laço de validação não usa isto."""
        if isinstance(n, bool) or not isinstance(n, int) or n < 1:
            raise ValueError(f"mlp: nº de épocas fixo deve ser inteiro >= 1, não {n!r}")
        self._estimador.epocas_fixas = n
        self._fixas = n

    def para_cpu(self) -> None:
        """Move a rede para a CPU antes de salvar (ver `EstimadorMLP.para_cpu`)."""
        self._estimador.para_cpu()
        self._dispositivo = "cpu"

    def ajustar(self, X_treino, y_treino, X_parada=None, y_parada=None) -> None:
        assert_dev_only(X_treino)  # R1
        y = np.asarray(y_treino)
        pre = self._pipeline.named_steps["preprocessamento"]
        if self._fixas is not None:  # retreino final: sem validação de parada
            if X_parada is not None or y_parada is not None:
                raise ValueError("mlp com épocas fixas não usa validação de parada")
            X_t = pre.fit_transform(X_treino, y)  # R5
            self._estimador.fit(X_t, y)
        else:
            if X_parada is None or y_parada is None:
                raise ValueError("mlp é iterativo: precisa de X_parada e y_parada (R6)")
            assert_dev_only(X_parada)  # R1
            y_p = np.asarray(y_parada)
            X_t = pre.fit_transform(X_treino, y)  # R5: ajuste só com o treino da dobra
            X_p = pre.transform(X_parada)  # R5: validação transformada com o ajuste do treino
            self._estimador.fit(X_t, y, X_parada=X_p, y_parada=y_p)
        self._melhor = self._estimador.melhor_epoca_
        if mlflow.active_run() is not None:
            mlflow.log_param(PARAM_MLFLOW_DISPOSITIVO, self._dispositivo)
            mlflow.log_metric(METRICA_MLFLOW_MELHOR, float(self._melhor))

    def prever_proba(self, X) -> np.ndarray:
        if self._melhor is None:
            raise RuntimeError("chame ajustar antes de prever")
        assert_dev_only(X)  # R1
        X_t = self._pipeline.named_steps["preprocessamento"].transform(X)
        return np.asarray(self._estimador.predict_proba(X_t)[:, 1], dtype=float)

    def melhor_ponto(self) -> int | None:
        return self._melhor


def construir_mlp(params: dict[str, Any], cfg: dict) -> MLPM1:
    """Entrada do `REGISTRO`: cria um MLP novo (não ajustado), com a semente do config."""
    return MLPM1(params, seed=cfg["seed"])
