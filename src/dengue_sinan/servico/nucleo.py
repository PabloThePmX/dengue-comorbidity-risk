"""Serviço de risco: o que a API e o Streamlit chamam. Sem HTTP e sem interface aqui."""

import json
import logging
import math
import threading
from importlib import metadata
from pathlib import Path

from dengue_sinan.pipeline.artefatos import HISTORICO, ArtefatoInvalido, sha256_arquivo
from dengue_sinan.pipeline.inferencia import EntradaInvalida, Preditor, carregar_modelo
from dengue_sinan.servico import adaptador_spec, registro, relatorio
from dengue_sinan.servico.config import ConfigServico
from dengue_sinan.servico.erros import LoteGrande, ModeloIndisponivel

log = logging.getLogger("dengue_sinan.servico")

AVISO = relatorio.AVISO
MOTIVO_E1 = (
    "O modelo explicativo E1 ainda não foi treinado nem serializado. Ele precisa de "
    "comorbidades, que hoje não estão autorizadas (config/variaveis_autorizadas.json)."
)


def _avisos_registro(r: dict) -> list[str]:
    """Avisos de plausibilidade. Não bloqueiam: o contrato do modelo aceita estes valores."""
    avisos = []
    if r.get("gestante") == 1:
        if r.get("sexo") == "M":
            avisos.append("gestante com sexo M: combinação improvável; confira o cadastro.")
        idade = r.get("idade_anos")
        if isinstance(idade, int | float) and not isinstance(idade, bool) and not 10 <= idade <= 55:
            avisos.append("gestante fora de 10 a 55 anos: confira a idade.")
    return avisos


def _pasta_confiavel(pasta: Path) -> Path:
    """Recusa pasta na área histórica da v1 e exige o layout de um artefato."""
    pasta = Path(pasta).expanduser().resolve()
    if pasta == HISTORICO or HISTORICO in pasta.parents:
        raise ModeloIndisponivel("M1", "recusado: pasta na área dos artefatos históricos da v1")
    if not (pasta / "metadados.json").is_file():
        raise ModeloIndisponivel("M1", f"artefato não encontrado em {pasta.name}")
    return pasta


def _texto_ou_nao_informado(valor) -> str:
    return valor.strip() if isinstance(valor, str) and valor.strip() else "não informado"


class Servico:
    def __init__(self, config: ConfigServico | None = None):
        self.config = config or ConfigServico.carregar()
        self._m1: Preditor | None = None
        self._erro_m1: str | None = None
        self._trava = threading.Lock()

    # ------------------------------------------------------------------ carga
    def _identificador_m1(self) -> str | None:
        return self.config.m1 or registro.mais_recente(self.config.pasta_artefatos, "m1")

    def carregar(self) -> None:
        """Carrega o M1 uma vez (hashes conferidos). Qualquer falha vira `_erro_m1`, não exceção.

        O servidor sobe em modo degradado (`saude()` = degradado) em vez de cair: metadados com
        JSON quebrado, arquivo ausente, hash diferente, pino divergente ou pasta histórica.
        """
        with self._trava:
            if self._m1 is not None or self._erro_m1 is not None:
                return
            ident = self._identificador_m1()
            if ident is None:
                self._erro_m1 = f"nenhum artefato m1-* em {self.config.pasta_artefatos}"
                return
            try:
                pasta = _pasta_confiavel(self.config.pasta_artefatos / ident)
                self._conferir_pino(pasta)
                self._m1 = carregar_modelo(pasta)
                log.info("M1 carregado: %s", self._m1.versao)
            except ModeloIndisponivel as e:
                self._erro_m1 = f"{ident}: {e.motivo}"
            except ArtefatoInvalido as e:
                self._erro_m1 = f"{ident}: {e}"
            except Exception as e:  # metadados quebrados, pickle ruim, versão incompatível etc.
                self._erro_m1 = f"{ident}: falha ao carregar o artefato ({type(e).__name__})"
            if self._m1 is None:
                log.error("M1 não carregou: %s", self._erro_m1)

    def _conferir_pino(self, pasta: Path) -> None:
        """Se há pino configurado, o `modelo.joblib` tem de ter exatamente esse SHA-256."""
        pino = self.config.m1_sha256
        if pino is None:
            return
        arquivo = pasta / "modelo.joblib"
        if not arquivo.is_file():
            raise ArtefatoInvalido("arquivo ausente no artefato: modelo.joblib")
        if sha256_arquivo(arquivo) != pino:
            raise ArtefatoInvalido("modelo.joblib não confere com o pino configurado")

    def _preditor_m1(self) -> Preditor:
        self.carregar()
        if self._m1 is None:
            raise ModeloIndisponivel("M1", self._erro_m1 or "não carregado")
        return self._m1

    # ------------------------------------------------------------- consultas
    def estado_e1(self) -> dict:
        """E1 nunca é inventado: sem artefato utilizável, devolve `indisponivel` e o motivo."""
        achado = registro.mais_recente(self.config.pasta_artefatos, "e1")
        if achado is None:
            return {"status": "indisponivel", "motivo": MOTIVO_E1}
        return {
            "status": "indisponivel",
            "motivo": f"Há um artefato '{achado}', mas o formato de serialização do E1 ainda não "
            "foi definido; a camada de serviço não o carrega.",
        }

    def saude(self) -> dict:
        """Prontidão: 'ok' se o M1 carrega; 'degradado' se não. O E1 ausente não degrada."""
        self.carregar()
        return {
            "status": "ok" if self._m1 is not None else "degradado",
            "m1": "disponivel" if self._m1 is not None else "indisponivel",
            "e1": self.estado_e1()["status"],
        }

    def info(self) -> dict:
        try:
            versao_pacote = metadata.version("dengue-comorbidity-risk")
        except metadata.PackageNotFoundError:
            versao_pacote = None
        self.carregar()
        m1 = None
        if self._m1 is not None:
            meta = self._m1.metadados
            aval = self._avaliacao_m1()
            cal = aval.get("calibrado_validacao_cruzada", {})
            saida = (self._m1.contrato.get("saida") or {}) if self._m1.contrato else {}
            m1 = {
                "identificador": self._m1.versao,
                "algoritmo": meta.get("algoritmo"),
                "calibrador": meta.get("calibrador"),
                "variaveis": self._m1.variaveis,
                "anos_desenvolvimento": meta.get("anos_desenvolvimento"),
                "hashes_conferidos": True,
                "pino_configurado": self.config.m1_sha256 is not None,
                "hashes_sha256": meta.get("hashes_sha256"),
                "data_treinamento_utc": meta.get("data_treinamento_utc"),
                "aviso": meta.get("aviso"),
                "limitacoes": list(aval.get("limitacoes") or meta.get("limitacoes") or []),
                # Texto lido do artefato; se o artefato não traz, diz "não informado".
                "desfecho": _texto_ou_nao_informado(saida.get("probabilidade")),
                "validacao": _texto_ou_nao_informado(aval.get("escopo")),
                "avaliacao_desenvolvimento": {
                    "escopo": aval.get("escopo"),
                    "e_teste_historico": aval.get("e_teste_historico"),
                    "prevalencia": cal.get("prevalencia", meta.get("prevalencia_desenvolvimento")),
                    "pr_auc": cal.get("pr_auc"),
                    "roc_auc": cal.get("roc_auc"),
                    "brier": cal.get("brier"),
                    "brier_referencia_prevalencia": cal.get("brier_referencia_prevalencia"),
                },
            }
        return {
            "pacote": versao_pacote,
            "m1": m1,
            "m1_motivo_indisponivel": self._erro_m1,
            "e1": self.estado_e1(),
            "limite_registros_por_pedido": self.config.limite_registros,
            "aviso": AVISO,
        }

    def _avaliacao_m1(self) -> dict:
        """`avaliacao_dev.json` do M1 carregado (já conferido por hash). Vazio se não legível."""
        try:
            pasta = self.config.pasta_artefatos / self._m1.versao
            return json.loads((pasta / "avaliacao_dev.json").read_text("utf-8"))
        except (OSError, ValueError):
            return {}

    def contrato(self, modelo: str = "m1") -> dict:
        if modelo == "m1":
            return self._preditor_m1().contrato
        if modelo == "e1":
            raise ModeloIndisponivel("E1", self.estado_e1()["motivo"])
        raise ValueError("modelo deve ser 'm1' ou 'e1'")

    def relatorio(self) -> dict:
        p = self._preditor_m1()
        return relatorio.montar(self.config.pasta_artefatos / p.versao)

    # -------------------------------------------------------------- predição
    def _checar_lote(self, n: int) -> None:
        if n > self.config.limite_registros:
            raise LoteGrande(n, self.config.limite_registros)

    def prever_m1(self, registros: list[dict]) -> dict:
        """Probabilidades do M1. Registro inválido sai marcado, sem derrubar o lote.

        Campo desconhecido ou entrada que não é lista de dicionários levanta `EntradaInvalida`
        (erro de quem chama). `alto_risco` é sempre None: não há limiar escolhido.
        """
        p = self._preditor_m1()
        lista = list(registros) if not isinstance(registros, dict) else registros
        if isinstance(lista, list):
            self._checar_lote(len(lista))
        saida = p.prever(lista, erros="marcar")
        resultados = []
        for i, linha in saida.iterrows():
            ok = linha["status"] == "ok"
            if ok and not (
                math.isfinite(linha["probabilidade"]) and 0 <= linha["probabilidade"] <= 1
            ):
                raise RuntimeError("o modelo devolveu probabilidade fora de [0, 1]")
            resultados.append(
                {
                    "indice": int(i),
                    "status": linha["status"],
                    "probabilidade": float(linha["probabilidade"]) if ok else None,
                    "alto_risco": None,
                    "erro": linha["erro"] or None,
                    "avisos": _avisos_registro(lista[i]) if ok and isinstance(lista, list) else [],
                }
            )
        log.info(
            "M1: %d registros, %d inválidos",
            len(resultados),
            sum(r["status"] != "ok" for r in resultados),
        )
        return {
            "modelo": "m1",
            "versao_modelo": p.versao,
            "resultados": resultados,
            "alto_risco_motivo": "nenhum limiar de decisão foi escolhido; não há classificação",
            "aviso": AVISO,
        }

    def prever_m1_spec(self, registros_spec: list[dict]) -> dict:
        """Aceita o formato da especificação (§3.15) e o converte; declara o que ignorou."""
        if not isinstance(registros_spec, list):
            raise EntradaInvalida(
                [{"indice": None, "campo": "(entrada)", "motivo": "esperada uma lista"}]
            )
        self._checar_lote(len(registros_spec))
        convertidos, ignorados, erros_adapt, ids = [], [], {}, []
        for i, r in enumerate(registros_spec):
            conv, ign, err = adaptador_spec.adaptar(r)
            convertidos.append(conv)
            ignorados.append(ign)
            ids.append(r.get("id_caso") if isinstance(r, dict) else None)
            if err:
                erros_adapt[i] = "; ".join(err)
        limpos = [c if i not in erros_adapt else {} for i, c in enumerate(convertidos)]
        saida = self.prever_m1(limpos) if limpos else self.prever_m1([])
        for i, res in enumerate(saida["resultados"]):
            res["id_caso"] = ids[i]
            res["campos_ignorados_pelo_modelo"] = ignorados[i]
            if i in erros_adapt:
                res.update(status="invalido", probabilidade=None, erro=erros_adapt[i], avisos=[])
            if ignorados[i]:
                res["avisos"] = [
                    *res["avisos"],
                    "campos fora do modelo não influenciam o risco: " + ", ".join(ignorados[i]),
                ]
        saida["contrato"] = "especificacao"
        return saida

    def prever_e1(self, registros: list[dict]) -> dict:
        """E1 ainda não existe: levanta `ModeloIndisponivel` em vez de inventar um resultado."""
        raise ModeloIndisponivel("E1", self.estado_e1()["motivo"])


def criar(pasta_artefatos: str | Path | None = None, **sobrepor) -> Servico:
    """Atalho para testes e scripts: Servico com a pasta dada."""
    base = ConfigServico.carregar()
    cfg = ConfigServico(
        pasta_artefatos=Path(pasta_artefatos) if pasta_artefatos else base.pasta_artefatos,
        m1=sobrepor.get("m1", base.m1),
        e1=sobrepor.get("e1", base.e1),
        limite_registros=sobrepor.get("limite_registros", base.limite_registros),
        m1_sha256=sobrepor.get("m1_sha256", base.m1_sha256),
    )
    return Servico(cfg)
