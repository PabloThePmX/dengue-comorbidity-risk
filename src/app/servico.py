"""Serviço da demo: carrega os artefatos e calcula o que a tela mostra (T-6.1, FR-11, NFR-03/06).

Sem Streamlit e sem estado global: funções puras sobre o que `carregar_artefatos` devolve.

**Privacidade (NFR-03, R7).** A demo só lê artefatos congelados (`models/e1`, `models/m1_final`
ou `models/m1_demo`) e os agregados do teste (`reports/teste/metricas.json`). Nenhuma entrada é
gravada em disco, registrada em log (este módulo nem importa `logging`), enviada a serviço externo
ou guardada além da execução da tela. Nenhum microdado é embarcado nem lido.

**Onde ficam os artefatos.** Pela variável de ambiente `DENGUE_MODELOS` (pasta com `e1/` e
`m1_final/`) e `DENGUE_RELATORIOS` (pasta com `teste/metricas.json`); sem elas, os caminhos do
`config/base.yaml` (`caminhos.modelos` e `caminhos.relatorios`, padrão `models` e `reports`),
relativos à raiz do repositório. O `m1_final` não está no git (R7, D-85): sem ele, a aba Triagem
mostra uma mensagem e a aba Perfil segue funcionando.
"""

from __future__ import annotations

import contextlib
import json
import os
import warnings
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from app.entrada import ROTULOS_FEATURES, Caso, Perfil
from dengue_sinan import artifacts, baselines, explain
from dengue_sinan.config import load_config
from dengue_sinan.profiling import FAIXAS, FAIXAS_ROTULOS

RAIZ = Path(__file__).resolve().parents[2]
ENV_MODELOS = "DENGUE_MODELOS"
ENV_RELATORIOS = "DENGUE_RELATORIOS"
NOME_E1 = "e1"
NOMES_M1 = ("m1_demo", "m1_final")  # D-70: a demo usa m1_demo se existir; senão, o m1_final
ARQUIVO_TESTE = Path("teste") / "metricas.json"
N_FATORES = 5

MSG_E1_AUSENTE = ("O modelo de perfil (E1) não está disponível nesta instalação: a pasta do "
                  "artefato não foi encontrada.")
MSG_M1_AUSENTE = ("O modelo de triagem (M1) não está disponível nesta instalação: o artefato "
                  "não foi encontrado (ele não é versionado no git). A aba Perfil continua "
                  "funcionando.")
MSG_FALHA = "O artefato existe, mas não pôde ser carregado ({tipo})."

# D-77: os dois pares do E1 que só têm eventos suficientes por causa do padrão suspeito "todas as 7
# comorbidades = Sim". Mesma regra da tabela de perfis (`explain._aviso`); o conjunto é fixado aqui
# porque `explain.contexto_padrao` lê dados de treino, que a demo não pode ler (R7).
PARES_PADRAO_SUSPEITO = (("HEMATOLOG", "HEPATOPAT"), ("HEMATOLOG", "RENAL"))


# --- Caminhos e carga --------------------------------------------------------------------------

def pasta_modelos() -> Path:
    env = os.environ.get(ENV_MODELOS)
    return Path(env) if env else RAIZ / load_config()["caminhos"]["modelos"]


def pasta_relatorios() -> Path:
    env = os.environ.get(ENV_RELATORIOS)
    return Path(env) if env else RAIZ / load_config()["caminhos"]["relatorios"]


@dataclass(frozen=True)
class PainelTeste:
    """Agregados do teste de 2024, lidos de `reports/teste/metricas.json` (nada digitado aqui)."""

    casos: int
    eventos: int
    limiar: float
    fracao_alto_risco: float
    precisao: float
    recall: float
    precisao_b2: float
    recall_b2: float
    obs_esp_m1: float
    obs_esp_e1: float | None
    sc02_passou: bool
    sc02_dif_recall: float
    sc02_dif_recall_ic: tuple[float, float]


@dataclass(frozen=True)
class Artefatos:
    """O que a tela usa. Um artefato ausente ou ilegível vira `None` com a mensagem ao lado."""

    e1: object | None = None
    erro_e1: str | None = None
    m1: object | None = None
    erro_m1: str | None = None
    versao_m1: str | None = None
    painel: PainelTeste | None = None


def _booster_com_leitura_tolerante():
    """Troca `xgboost.Booster.__setstate__` por uma versão que, se a desserialização completa
    falhar, lê só as árvores (`load_model`). Devolve um gerenciador de contexto.

    Motivo (medido): o joblib congelado do M1 foi gravado no Colab com o booster em GPU (`device`
    `cuda:0`) e, no XGBoost 3.4.1 deste ambiente sem GPU, `Booster.__setstate__` falha com
    "input stream corrupted", embora o bloco `Model` do mesmo bytes carregue sem erro. O modelo
    (árvores, base_score, objetivo) é o mesmo; só se descarta o bloco `Config` de treino.
    """
    import xgboost as xgb

    original = xgb.Booster.__setstate__
    chave = b"L" + (5).to_bytes(8, "big") + b"Model"

    def tolerante(self, estado):
        try:
            original(self, estado)
        except xgb.core.XGBoostError:
            bruto = bytes(estado["handle"])
            i = bruto.find(chave)
            if i < 0 or not bruto.endswith(b"}"):
                raise
            modelo = bruto[i + len(chave):-1]  # valor da chave "Model": vai até o "}" da raiz
            temporario = xgb.Booster()
            temporario.load_model(bytearray(modelo))
            self.handle, temporario.handle = temporario.handle, None  # um só dono do handle
            self.__dict__.update({k: v for k, v in estado.items() if k != "handle"})

    @contextlib.contextmanager
    def gerenciador() -> Iterator[None]:
        xgb.Booster.__setstate__ = tolerante
        try:
            yield
        finally:
            xgb.Booster.__setstate__ = original

    return gerenciador()


def carregar_bundle_m1(pasta: Path):
    """Carrega o artefato do M1. Importar `dengue_sinan.retreino` registra o tipo `m1` (D-85).

    Se a desserialização completa do XGBoost falhar (artefato gravado em GPU), lê só as árvores
    (ver `_booster_com_leitura_tolerante`). Paridade com a carga normal: o hash do booster é
    `sha256("\n".join(booster.get_dump(dump_format="json")).encode("utf-8"))`, e deve ser igual
    nas duas cargas (`reports/verificacao/paridade-m1-demo.json`).
    """
    from xgboost.core import XGBoostError

    from dengue_sinan import retreino  # noqa: F401

    with warnings.catch_warnings():
        # o artefato veio de uma GPU: o XGBoost avisa que o dispositivo mudou para CPU (esperado)
        warnings.simplefilter("ignore", UserWarning)
        try:
            return artifacts.load_bundle(pasta)
        except XGBoostError:
            pass  # plano B abaixo
        with _booster_com_leitura_tolerante():
            return artifacts.load_bundle(pasta)


def versao_modelo(meta: dict) -> str | None:
    """`m1-<modelo>-<data do treino>-<8 primeiros do SHA-256 do payload>` (contrato, saída)."""
    try:
        sha = next(iter(meta["payload"].values()))
        return f"m1-{meta['m1']['modelo']}-{meta['data_treino'][:10]}-{sha[:8]}"
    except (KeyError, StopIteration, TypeError):
        return None


def _carregar_e1(pasta: Path):
    if not (pasta / NOME_E1 / artifacts.NOME_METADATA).is_file():
        return None, MSG_E1_AUSENTE
    try:
        return artifacts.load_bundle(pasta / NOME_E1), None
    except Exception as erro:
        return None, MSG_FALHA.format(tipo=type(erro).__name__)


def _carregar_m1(pasta: Path):
    for nome in NOMES_M1:
        destino = pasta / nome
        if not (destino / artifacts.NOME_METADATA).is_file():
            continue
        try:
            modelo = carregar_bundle_m1(destino)
            return modelo, None, versao_modelo(artifacts.ler_metadados(destino))
        except Exception as erro:
            return None, MSG_FALHA.format(tipo=type(erro).__name__), None
    return None, MSG_M1_AUSENTE, None


def ler_painel(relatorios: Path) -> PainelTeste | None:
    """Lê os agregados do teste; arquivo ausente ou fora do formato esperado = sem painel."""
    arquivo = Path(relatorios) / ARQUIVO_TESTE
    try:
        d = json.loads(arquivo.read_text(encoding="utf-8"))
        modelos = d["analises"]["metricas"]["modelos"]
        m1 = modelos["M1"]
        sc02 = d["analises"]["criterios"]["sc02"]
        recall = sc02["detalhe"]["recall"]
        precisao = sc02["detalhe"]["precisao"]
        e1 = modelos.get("E1", {}).get("obs_esp", {}).get("valor")
        return PainelTeste(
            casos=int(d["casos"]),
            eventos=int(d["eventos"]),
            limiar=float(m1["limiar"]),
            fracao_alto_risco=float(m1["no_limiar"]["alertas"]) / float(d["casos"]),
            precisao=float(m1["no_limiar"]["precisao"]["valor"]),
            recall=float(m1["no_limiar"]["recall"]["valor"]),
            precisao_b2=float(precisao["B2"]["valor"]),
            recall_b2=float(recall["B2"]["valor"]),
            obs_esp_m1=float(m1["obs_esp"]["valor"]),
            obs_esp_e1=None if e1 is None else float(e1),
            sc02_passou=bool(sc02["passou"]),
            sc02_dif_recall=float(recall["diferenca"]["valor"]),
            sc02_dif_recall_ic=tuple(float(x) for x in recall["diferenca"]["ic95"]),
        )
    except (OSError, ValueError, KeyError, TypeError, ZeroDivisionError):
        return None


def carregar_artefatos(modelos: Path | None = None, relatorios: Path | None = None) -> Artefatos:
    """Carrega E1, M1 e o painel do teste. Nunca levanta por artefato ausente ou ilegível."""
    modelos = Path(modelos) if modelos is not None else pasta_modelos()
    relatorios = Path(relatorios) if relatorios is not None else pasta_relatorios()
    e1, erro_e1 = _carregar_e1(modelos)
    m1, erro_m1, versao = _carregar_m1(modelos)
    return Artefatos(e1=e1, erro_e1=erro_e1, m1=m1, erro_m1=erro_m1, versao_m1=versao,
                     painel=ler_painel(relatorios))


# --- Formatação pt-BR (sem `locale`: o resultado não depende do servidor) -----------------------

def numero(x: float, casas: int = 2) -> str:
    return f"{x:.{casas}f}".replace(".", ",")


def inteiro(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def porcentagem(fracao: float, casas: int | None = None) -> str:
    """Fração como porcentagem pt-BR. Padrão: 3 casas abaixo de 1% e 2 de 1% para cima."""
    if casas is None:
        casas = 3 if abs(fracao) < 0.01 else 2
    return f"{numero(100 * fracao, casas)}%"


def faixa_etaria(idade: float) -> str:
    return FAIXAS_ROTULOS[int(np.digitize(idade, FAIXAS[1:-1]))]


# --- Aba Perfil (E1) ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ResultadoPerfil:
    estimavel: bool
    motivo: str | None  # por que não há número ("dados insuficientes"), quando `estimavel` é False
    faixa: str
    risco: float | None = None
    ic: tuple[float, float] | None = None
    risco_base: float | None = None  # sem comorbidades, mesma idade, sexo e gestação
    ic_base: tuple[float, float] | None = None
    razao: float | None = None
    ic_razao: tuple[float, float] | None = None
    odds: list[dict] = field(default_factory=list)  # OR de cada comorbidade marcada
    avisos: list[str] = field(default_factory=list)


def _sem_estimativa(e1, marcadas: tuple[str, ...]) -> str | None:
    """Motivo de "dados insuficientes", com a mesma regra da tabela de perfis (D-78, T-3.5)."""
    if len(marcadas) > explain.MAX_COMORBIDADES_ESTIMADAS:
        return explain.SEM_DADOS_5_MAIS
    excluidos = {frozenset(p) for p in e1.pares_excluidos}
    if len(marcadas) == 2 and frozenset(marcadas) in excluidos:
        return (f"{explain.SEM_DADOS}: este par de comorbidades tem poucos eventos no treino e "
                "não entrou no modelo")
    return None


def _avisos_perfil(marcadas: tuple[str, ...]) -> list[str]:
    avisos = []
    if len(marcadas) >= 3:
        avisos.append(explain.NOTA_TRIO if len(marcadas) == 3 else explain.NOTA_COMBINACAO)
    conjunto = set(marcadas)
    if any(a in conjunto and b in conjunto for a, b in PARES_PADRAO_SUSPEITO):
        avisos.append(explain.AVISO_PADRAO)
    return avisos


def avaliar_perfil(e1, perfil: Perfil) -> ResultadoPerfil:
    """Risco do E1 com IC 95% (método delta), comparação com "sem comorbidades" e OR das marcadas.

    Tudo vem de `explain` (`risco_perfil`, `razao_de_risco`, `log_or_na_idade`); aqui só se monta
    o resultado e se aplica a regra de "dados insuficientes".
    """
    faixa = faixa_etaria(perfil.idade_anos)
    motivo = _sem_estimativa(e1, perfil.comorbidades)
    if motivo is not None:
        return ResultadoPerfil(estimavel=False, motivo=motivo, faixa=faixa)
    base = (perfil.idade_anos, perfil.sexo, perfil.gestante)
    r = explain.risco_perfil(e1, *base, perfil.comorbidades)
    r0 = explain.risco_perfil(e1, *base, ())
    rr = explain.razao_de_risco(e1, *base, perfil.comorbidades)
    odds = []
    for campo in perfil.comorbidades:
        lo = explain.log_or_na_idade(e1, campo, perfil.idade_anos)
        odds.append({
            "comorbidade": campo,
            "or": float(np.exp(lo["estimativa"])),
            "ic_inferior": float(np.exp(lo["ic_inferior"])),
            "ic_superior": float(np.exp(lo["ic_superior"])),
        })
    return ResultadoPerfil(
        estimavel=True, motivo=None, faixa=faixa,
        risco=r["risco"], ic=(r["ic_inferior"], r["ic_superior"]),
        risco_base=r0["risco"], ic_base=(r0["ic_inferior"], r0["ic_superior"]),
        razao=rr["razao"], ic_razao=(rr["ic_inferior"], rr["ic_superior"]),
        odds=odds, avisos=_avisos_perfil(perfil.comorbidades),
    )


# --- Aba Triagem (M1) --------------------------------------------------------------------------

@dataclass(frozen=True)
class Fator:
    campo: str
    rotulo: str
    valor: str  # o que foi informado, em texto
    contribuicao: float  # em log-odds do modelo, antes da calibração

    @property
    def aumenta(self) -> bool:
        return self.contribuicao > 0


@dataclass(frozen=True)
class ResultadoTriagem:
    risco: float
    alto_risco: bool
    limiar: float
    grupo_b_b2: bool  # a regra do protocolo (B2) marcaria o caso
    fatores: list[Fator]  # os que mais pesaram, por |contribuição|; vazio se não houver explicação
    outros_fatores: float | None  # soma das contribuições dos que não aparecem
    valor_base: float | None  # log-odds médio do modelo (ponto de partida da soma)
    log_odds: float | None  # valor_base + soma de todas as contribuições
    explicacao_indisponivel: bool = False


def _valor_do_fator(caso: Caso, campo: str) -> str:
    if campo in caso.comorbidades:
        return caso.comorbidades[campo].replace("Ausente", "Ignorado")
    if campo in caso.sinais:
        return caso.sinais[campo].replace("Ausente", "Ignorado")
    return {
        "idade_anos": f"{caso.idade_anos} anos",
        "sexo": "Feminino" if caso.sexo == "F" else "Masculino",
        "gestante": "Sim" if caso.gestante else "Não",
        "dias_ate_notificacao": f"{caso.dias_ate_notificacao} dias",
        "n_comorbidades": str(caso.n_comorbidades),
    }[campo]


def contribuicoes(final, X) -> tuple[np.ndarray, float | None]:
    """(contribuição de cada coluna em log-odds do modelo, valor base).

    As contribuições são as de `retreino.shap_local` (TreeSHAP exato no XGBoost, como o `retreino`
    mede em NFR-06). O valor base só existe aqui para o XGBoost: é a coluna de viés do próprio
    TreeSHAP, e `base + soma(contribuições)` é o log-odds previsto (aditividade). Nos outros
    modelos o valor base é None.
    """
    from dengue_sinan import retreino, shap_global
    from dengue_sinan.xgboost_m1 import XGBoostM1

    contrib = retreino.shap_local(final, X)
    base = None
    if isinstance(final.modelo, XGBoostM1):
        import xgboost as xgb

        _, pre, estimador, n_arvores = shap_global._componentes(final.modelo)
        dm = xgb.DMatrix(np.asarray(pre.transform(X), dtype=np.float32))
        com_vies = estimador.get_booster().predict(dm, pred_contribs=True,
                                                   iteration_range=(0, n_arvores))
        base = float(com_vies[0, -1])
    return contrib, base


def avaliar_caso(final, caso: Caso, n_fatores: int = N_FATORES) -> ResultadoTriagem:
    """Risco calibrado do M1, "alto risco" no limiar congelado do artefato e os fatores locais."""
    X = caso.para_frame()
    risco = float(final.prever_proba(X)[0])
    b2 = bool(baselines.rule_b2(X)[0])
    fatores: list[Fator] = []
    outros = base = log_odds = None
    indisponivel = False
    try:
        contrib, base = contribuicoes(final, X)
        if len(contrib) != len(final.features):
            raise ValueError("contribuições não correspondem às features")
    except (ValueError, ImportError):  # modelo sem explicação por feature (ex.: elastic net)
        indisponivel = True
    else:
        ordem = np.argsort(-np.abs(contrib), kind="stable")
        for i in ordem[:n_fatores]:
            campo = final.features[i]
            fatores.append(Fator(campo, ROTULOS_FEATURES[campo], _valor_do_fator(caso, campo),
                                 float(contrib[i])))
        outros = float(contrib[ordem[n_fatores:]].sum())
        if base is not None:
            log_odds = base + float(contrib.sum())
    return ResultadoTriagem(
        risco=risco, alto_risco=risco >= final.limiar, limiar=float(final.limiar),
        grupo_b_b2=b2, fatores=fatores, outros_fatores=outros, valor_base=base,
        log_odds=log_odds, explicacao_indisponivel=indisponivel,
    )


# --- Painel "O que o teste de 2024 mostrou" ----------------------------------------------------

LEGENDA_ALTO_RISCO_GENERICA = "É um sinal de triagem de baixa precisão, não um diagnóstico."


def legenda_alto_risco(p: PainelTeste | None) -> str:
    """Legenda do rótulo "Alto risco": o número vem da precisão do teste de 2024 (1 − precisão)."""
    if p is None:
        return LEGENDA_ALTO_RISCO_GENERICA
    return (f"No teste de 2024, cerca de {porcentagem(1 - p.precisao, 0)} dos casos marcados assim "
            "não evoluíram para grave ou óbito: é um sinal de triagem de baixa precisão, não um "
            "diagnóstico.")


def linhas_painel(p: PainelTeste) -> list[str]:
    """Frases do painel, com os números formatados em pt-BR a partir do `PainelTeste`."""
    linhas = [
        f"No teste de 2024 ({inteiro(p.casos)} casos, {inteiro(p.eventos)} com desfecho grave ou "
        f"óbito) o limiar de 'alto risco' ({porcentagem(p.limiar, 4)}) marcou cerca de "
        f"{porcentagem(p.fracao_alto_risco, 0)} dos casos. Entre os marcados, "
        f"{porcentagem(p.precisao, 2)} evoluíram para grave ou óbito (precisão). "
        f"O recall no limiar foi {porcentagem(p.recall, 0)}: o modelo marcou cerca de "
        f"{porcentagem(p.recall, 0)} dos casos que evoluíram para grave ou óbito.",
    ]
    desvio = abs(p.obs_esp_m1 - 1)
    sentido = "maior" if p.obs_esp_m1 > 1 else "menor"
    verbo = "subestimou" if p.obs_esp_m1 > 1 else "superestimou"
    frase = (f"**O modelo {verbo} o risco em 2024: o observado foi cerca de "
             f"{porcentagem(desvio, 0)} {sentido} que o previsto** (observado/esperado = "
             f"{numero(p.obs_esp_m1)}). 2024 foi um ano de epidemia, com prevalência maior que "
             "a do treino (2022–2023).")
    if p.obs_esp_m1 > 1:
        frase += (" O risco mostrado pode estar abaixo do risco real; trate-o como uma estimativa "
                  "possivelmente baixa.")
    linhas.append(frase)
    if p.obs_esp_e1 is not None and p.obs_esp_e1 > 1:
        linhas.append(f"O mesmo vale para o modelo de perfil (E1): o observado foi cerca de "
                      f"{porcentagem(p.obs_esp_e1 - 1, 0)} maior que o previsto.")
    resultado = "atendido" if p.sc02_passou else "não atendido"
    inf, sup = p.sc02_dif_recall_ic
    linhas.append(
        f"Critério SC-02 (recall do M1 ≥ o da regra B2 e precisão maior): **{resultado}**. "
        f"Recall: M1 {porcentagem(p.recall, 1)} contra {porcentagem(p.recall_b2, 1)} da regra B2 "
        f"(diferença {numero(100 * p.sc02_dif_recall, 1)} ponto percentual, IC 95% de "
        f"{numero(100 * inf, 1)} a {numero(100 * sup, 1)}). Precisão: M1 "
        f"{porcentagem(p.precisao, 2)} contra {porcentagem(p.precisao_b2, 2)} da B2.")
    linhas.append("Os números do teste valem para casos notificados com desfecho conhecido (a "
                  "população usada para definir o rótulo).")
    return linhas

