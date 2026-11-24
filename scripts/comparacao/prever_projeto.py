"""Probabilidades dos modelos do próprio projeto para a entrada comum da comparação (D-97, T-8.6).

Conjunto fechado do manifesto: m1_main (XGBoost calibrado), e1_main (logística com interações),
b0_main (prevalência), b1_main (logística simples) e b2_regra (regra do protocolo, B2). Roda com o
.venv da main: são artefatos do próprio projeto, sem carga isolada.

    .venv\\Scripts\\python.exe scripts/comparacao/prever_projeto.py
        --entrada data/comparacao/entrada_2025.parquet --saida-dir data/comparacao

Ordem, sem atalho:
1. lê o manifesto (valida com `comparacao_manifesto.carregar_manifesto`);
2. confere o SHA-256 de cada artefato presente contra o manifesto ANTES de qualquer carga. Se o
   artefato de B0 ou de B1 não existir (ficam no Drive até o Programador copiá-los), o modelo é
   pulado com aviso e `status: ausente` no relatório, sem previsão inventada. Os demais são
   obrigatórios;
3. regra de entrada: recusa o ano de teste (2024) sempre, e o ano de comparação (2025) a menos que
   `DENGUE_PORTA_COMPARACAO=1` (só o avaliador define essa variável). O ano vem da própria entrada,
   que tem de ser de um ano só;
4. confere o JSON de conferência da entrada (dicionário de features do projeto, R4);
5. carrega cada artefato (`artifacts.load_bundle`) e prevê em blocos. Com o ano de comparação, a
   previsão roda dentro de `guard.leitura_do_ano_de_comparacao()`; com ano de desenvolvimento, sob
   a guarda normal (`assert_dev_only`). Não usa `evaluate.predizer`, que só abre a porta do teste;
6. grava `p_<id>_<ano>.parquet` (ANO, LINHA, p; e1_main traz também `estimavel`) e
   `p_<id>_<ano>.conformidade.json` (só nomes, parâmetros e agregados, R7), mais o resumo
   `prever_projeto_<ano>.resumo.json` com o status de cada modelo.

E1 não estima alguns perfis (5 ou mais comorbidades; pares com poucos eventos). Nesses casos o `p`
fica NaN com `estimavel = false`: não se preenche com valor inventado. A decisão sobre o que fazer
com essas linhas é do Programador (ver a T-8.6 e o relatório de execução).
"""

import argparse
import contextlib
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from dengue_sinan import artifacts, baselines, comparacao_manifesto, explain, guard
from dengue_sinan.config import load_config
from dengue_sinan.profiling import COMORBIDADES

RAIZ = Path(__file__).resolve().parents[2]
PORTA_ENV = "DENGUE_PORTA_COMPARACAO"
BLOCO = 200_000
MODELOS = ("m1_main", "e1_main", "b0_main", "b1_main", "b2_regra")
OPCIONAIS = ("b0_main", "b1_main")  # podem faltar no disco até o Programador copiá-los do Drive
FEATURES_B2 = ("idade_anos", "gestante", *COMORBIDADES, "LACO", "PETEQUIA_N")
NOMES_R3 = ("class_weight", "scale_pos_weight", "is_unbalance", "auto_class_weights",
            "pos_weight", "sample_weight")
CHAVES_E1 = tuple(explain.CHAVES_PADRAO)


# --------------------------------------------------------------------------- manifesto e SHA-256
def sha256_arquivo(caminho: Path, bloco: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        while pedaco := f.read(bloco):
            h.update(pedaco)
    return h.hexdigest()


def modelo_do_manifesto(manifesto: dict, id_modelo: str) -> dict:
    for modelo in manifesto["modelos"]:
        if modelo["id"] == id_modelo:
            return modelo
    raise ValueError(f"manifesto: modelo {id_modelo} não encontrado")


@dataclass
class Plano:
    """O que o script faz com um modelo do manifesto, antes de carregar qualquer coisa."""

    id: str
    arquivo: Path | None  # payload declarado no manifesto; None para a regra (B2)
    pasta: Path | None  # pasta do artefato: metadata.json e payload/
    sha_declarado: str | None
    presente: bool = True
    sha_conferido: str | None = None


def planejar(manifesto: dict, ids: list[str], raiz: Path = RAIZ) -> list[Plano]:
    """Localiza os artefatos. Ausência só é aceita para B0 e B1 (aviso, status ausente)."""
    planos = []
    for mid in ids:
        artefato = modelo_do_manifesto(manifesto, mid)["artefato"]
        if artefato is None:
            planos.append(Plano(mid, None, None, None))
            continue
        arquivo = raiz / artefato["caminho"]
        presente = arquivo.is_file()
        if not presente and mid not in OPCIONAIS:
            raise SystemExit(f"{mid}: artefato ausente em {arquivo}")
        planos.append(Plano(mid, arquivo, arquivo.parent.parent, artefato["sha256"], presente))
    return planos


def conferir_sha(planos: list[Plano]) -> None:
    """SHA-256 de cada artefato presente contra o manifesto, antes de qualquer carga (D-97 g)."""
    for plano in planos:
        if plano.arquivo is None or not plano.presente:
            continue
        plano.sha_conferido = sha256_arquivo(plano.arquivo)
        if plano.sha_conferido != plano.sha_declarado:
            raise SystemExit(f"{plano.id}: SHA-256 do artefato ({plano.sha_conferido}) difere do "
                             f"manifesto ({plano.sha_declarado}): não carrego (D-97 g)")


# --------------------------------------------------------------------------- regra de entrada
def checar_anos(anos: set[int], ano_teste: int, ano_comparacao: int, porta_aberta: bool) -> None:
    """Regra de entrada (R1, R2, D-97). Levanta PermissionError se a entrada não pode ser lida."""
    if ano_teste in anos:
        raise PermissionError(f"recusado: a entrada tem {ano_teste}, o teste congelado (R1). "
                              "Nenhuma entrada com esse ano é lida aqui, em nenhum caso.")
    if ano_comparacao in anos and not porta_aberta:
        raise PermissionError(f"recusado: a entrada tem {ano_comparacao}, o ano de comparação. "
                              f"Só é lido com {PORTA_ENV}=1, definido pelo avaliador (R1, D-97).")


def ano_unico(anos: set[int]) -> int:
    if len(anos) != 1:
        raise SystemExit(f"a entrada deve ter um ano só; tem {sorted(anos)}")
    return next(iter(anos))


def checar_dicionario(features: list[str], dicionario: list[str]) -> list[str]:
    """Variáveis do modelo fora do dicionário de features do projeto (R4)."""
    return sorted(set(features) - set(dicionario))


# --------------------------------------------------------------------------- carga e previsão
def _registrar_tipos() -> None:
    """Importar estes módulos registra os tipos de payload (m1, b0, b1) antes do load_bundle."""
    from dengue_sinan import baselines_final, retreino  # noqa: F401


def carregar(plano: Plano):
    """Carrega o artefato. O M1 usa o carregador tolerante da demo (`app.servico`), porque o
    booster foi gravado com device `cuda:0` e a carga normal falha neste ambiente sem GPU. Paridade
    provada em `reports/verificacao/paridade-m1-demo.json` (T-6.1). O SHA-256 já foi conferido."""
    if plano.arquivo is None:
        return None
    if plano.id == "m1_main":
        from app import servico

        return servico.carregar_bundle_m1(plano.pasta)
    if plano.id in ("b0_main", "b1_main") and not _tem_metadados(plano):
        return _carregar_payload_baseline(plano)
    _registrar_tipos()
    return artifacts.load_bundle(plano.pasta)


def _tem_metadados(plano: Plano) -> bool:
    return (plano.pasta / artifacts.NOME_METADATA).is_file()


def _carregar_payload_baseline(plano: Plano):
    """B0 e B1 sem `metadata.json` (o Programador copiou só o payload do Drive). O `load_bundle`
    exige o metadata; aqui se usa o codec do próprio `baselines_final` sobre o payload, que é o
    que o `load_bundle` chama depois das suas checagens. O SHA-256 do payload já foi conferido
    contra o manifesto (antes da carga). Não se inventa metadado."""
    from dengue_sinan import baselines_final

    if plano.id == "b0_main":
        return baselines_final._carregar_b0(plano.arquivo.parent)
    return baselines_final._carregar_b1(plano.arquivo.parent)


def features_do_modelo(mid: str, obj) -> list[str]:
    if mid in ("m1_main", "e1_main"):
        return list(obj.features)
    if mid == "b0_main":
        return []  # a prevalência não usa variável
    if mid == "b1_main":
        return list(baselines.COLUNAS_B1)
    return list(FEATURES_B2)


def mascara_e1(df: pd.DataFrame, pares_excluidos) -> np.ndarray:
    """True onde o E1 estima o perfil. Mesma regra de `servico._sem_estimativa`: 5 ou mais
    comorbidades, ou um par que ficou fora do modelo (poucos eventos), não são estimados."""
    sim = np.column_stack([(df[c] == "Sim").to_numpy() for c in COMORBIDADES])
    marcadas = sim.sum(axis=1)
    estimavel = marcadas <= explain.MAX_COMORBIDADES_ESTIMADAS
    posicao = {c: i for i, c in enumerate(COMORBIDADES)}
    for a, b in pares_excluidos:
        estimavel &= ~((marcadas == 2) & sim[:, posicao[a]] & sim[:, posicao[b]])
    return estimavel


def prever_e1(e1, df: pd.DataFrame) -> np.ndarray:
    """Risco do E1 por linha, pelo mesmo caminho de `evaluate.prever_e1` (uma conta por padrão)."""
    if len(df) == 0:
        return np.empty(0, dtype=float)
    if df[list(CHAVES_E1)].isna().any().any():
        raise ValueError("há covariáveis ausentes no E1 (a população deveria excluí-las)")
    codigo = df.groupby(list(CHAVES_E1), observed=True, sort=False).ngroup().to_numpy()
    _, primeiros = np.unique(codigo, return_index=True)
    padroes = df.iloc[primeiros][list(CHAVES_E1)].reset_index(drop=True)
    X = explain.matriz_de_desenho(padroes, e1.nos, e1.pares_incluidos)
    if set(X.columns) != set(e1.colunas):
        raise ValueError("o desenho do E1 não bate com as colunas do artefato")
    eta = X[list(e1.colunas)].to_numpy(dtype=float) @ np.asarray(e1.params, dtype=float)
    return (1.0 / (1.0 + np.exp(-eta)))[codigo]


def prever_bloco(mid: str, obj, bloco: pd.DataFrame) -> tuple[np.ndarray, np.ndarray | None]:
    """Probabilidades do bloco e, no E1, a máscara de quem é estimado (None nos demais)."""
    if mid == "m1_main":
        # O M1 recebe o quadro com ANO (a guarda confere o ano dentro de prever_proba).
        return np.asarray(obj.prever_proba(bloco[[*obj.features, "ANO"]]), dtype=float), None
    if mid == "e1_main":
        estimavel = mascara_e1(bloco, obj.pares_excluidos)
        p = np.full(len(bloco), np.nan)
        p[estimavel] = prever_e1(obj, bloco[estimavel])
        return p, estimavel
    if mid in ("b0_main", "b1_main"):
        return np.asarray(obj.predizer(bloco), dtype=float), None
    return baselines.rule_b2(bloco).astype(float), None


def validar_p(mid: str, p: np.ndarray, estimavel: np.ndarray | None) -> None:
    if estimavel is not None:
        if np.isnan(p[estimavel]).any():
            raise ValueError(f"{mid}: NaN em linha estimada")
        valores = p[estimavel]
    else:
        if np.isnan(p).any():
            raise ValueError(f"{mid}: probabilidade ausente (NaN)")
        valores = p
    if ((valores < 0) | (valores > 1)).any():
        raise ValueError(f"{mid}: probabilidade fora de [0, 1]")


def prever_entrada(entrada: Path, objs: dict[str, object], colunas: list[str], ano: int,
                   ano_comparacao: int) -> dict[str, dict]:
    """Prevê em blocos, na ordem da entrada. Com o ano de comparação, tudo roda na porta."""
    porta = (guard.leitura_do_ano_de_comparacao() if ano == ano_comparacao
             else contextlib.nullcontext())
    acumulado: dict[str, dict] = {mid: {"ANO": [], "LINHA": [], "p": [], "est": []}
                                  for mid in objs}
    with porta:
        for lote in pq.ParquetFile(entrada).iter_batches(batch_size=BLOCO, columns=colunas):
            bloco = lote.to_pandas()
            guard.assert_dev_only(bloco)  # R1, em cada bloco
            for mid, obj in objs.items():
                p, est = prever_bloco(mid, obj, bloco)
                validar_p(mid, p, est)
                acu = acumulado[mid]
                acu["ANO"].append(bloco["ANO"].to_numpy(dtype="int64"))
                acu["LINHA"].append(bloco["LINHA"].to_numpy(dtype="int64"))
                acu["p"].append(p)
                acu["est"].append(est)
    resultado = {}
    for mid, acu in acumulado.items():
        estimavel = np.concatenate(acu["est"]) if mid == "e1_main" else None
        resultado[mid] = {"ANO": _concatenar(acu["ANO"], "int64"),
                          "LINHA": _concatenar(acu["LINHA"], "int64"),
                          "p": _concatenar(acu["p"], "float64"), "estimavel": estimavel}
    return resultado


def _concatenar(partes: list[np.ndarray], tipo: str) -> np.ndarray:
    """Junta os blocos; entrada vazia vira vetor vazio do tipo certo (nada é inventado)."""
    return np.concatenate(partes) if partes else np.empty(0, dtype=tipo)


# --------------------------------------------------------------------------- conformidade (R7)
def _primitivo(valor):
    """Valor de parâmetro em JSON estrito: número finito, texto ou booleano; o resto vira texto
    (inclusive Infinity e NaN, que o JSON padrão não aceita)."""
    if isinstance(valor, np.integer | np.floating):
        valor = valor.item()
    if valor is None or isinstance(valor, bool | str):
        return valor
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float) and np.isfinite(valor):
        return valor
    return str(valor)


def correcao_de_desbalanceamento(params: dict) -> dict[str, str]:
    """Parâmetros de R3 com valor que corrige desbalanceamento (vazio = nenhum)."""
    achados = {}
    for chave, valor in params.items():
        if chave.split("__")[-1] not in NOMES_R3:
            continue
        if valor not in (None, 1, 1.0, False):
            achados[chave] = str(valor)
    return achados


def _parametros(mid: str, obj) -> dict:
    if mid == "m1_main":
        estimador = getattr(obj.modelo, "_estimador", None)
        params = estimador.get_params() if estimador is not None else {}
        return {"estimador": type(estimador).__name__ if estimador is not None else None,
                "limiar": float(obj.limiar),
                **{k: _primitivo(v) for k, v in params.items()}}
    if mid == "e1_main":
        return {"colunas_do_desenho": len(obj.colunas),
                "pares_incluidos": len(obj.pares_incluidos),
                "pares_excluidos": len(obj.pares_excluidos),
                "idade_referencia": int(obj.idade_referencia)}
    if mid == "b0_main":
        return {"prevalencia": float(obj.prevalencia), "limiar": float(obj.limiar)}
    if mid == "b1_main":
        ultimo = obj.modelo.steps[-1][1]
        return {"limiar": float(obj.limiar), "ultimo_passo": type(ultimo).__name__,
                **{k: _primitivo(v) for k, v in ultimo.get_params().items()}}
    return {"regra": "baselines.rule_b2",
            "criterios": ["idade < 2 ou > 65 anos", "gestante = 1", "alguma comorbidade = Sim",
                          "LACO = Sim", "PETEQUIA_N = Sim"]}


def _r3(mid: str, obj) -> dict:
    if mid == "m1_main":
        estimador = getattr(obj.modelo, "_estimador", None)
        params = estimador.get_params() if estimador is not None else {}
    elif mid == "b1_main":
        params = obj.modelo.get_params(deep=True)
    else:
        return {"aplicavel": False,
                "motivo": "sem pesos de classe no ajuste" if mid == "e1_main" else "sem ajuste"}
    achados = correcao_de_desbalanceamento({k: _primitivo(v) for k, v in params.items()})
    return {"aplicavel": True, "parametros_com_correcao": achados,
            "com_correcao_de_desbalanceamento": bool(achados)}


def estatisticas(p: np.ndarray, estimavel: np.ndarray | None) -> dict:
    validos = p[~np.isnan(p)]
    saida = {
        "linhas": int(len(p)),
        "nans": int(np.isnan(p).sum()),
        "p_min": float(validos.min()) if len(validos) else None,
        "p_max": float(validos.max()) if len(validos) else None,
        "p_media": float(validos.mean()) if len(validos) else None,
        "p_iguais_a_0": int((validos == 0).sum()),
        "p_iguais_a_1": int((validos == 1).sum()),
    }
    if estimavel is not None:
        saida["estimaveis"] = int(estimavel.sum())
        saida["nao_estimaveis"] = int((~estimavel).sum())
        saida["fracao_nao_estimavel"] = float((~estimavel).mean()) if len(p) else None
    return saida


def conformidade(plano: Plano, obj, features: list[str], dicionario: list[str], ano: int,
                 ano_comparacao: int, manifesto_modelo: dict, estat: dict) -> dict:
    fora = checar_dicionario(features, dicionario)
    tem_meta = plano.pasta is not None and _tem_metadados(plano)
    meta = artifacts.ler_metadados(plano.pasta) if tem_meta else {}
    treino = list(manifesto_modelo["treino_anos"])
    limiar_manifesto = (manifesto_modelo.get("limiar") or {}).get("valor")
    limiar_artefato = getattr(obj, "limiar", None)
    return {
        "modelo": plano.id,
        "papel": manifesto_modelo["papel"],
        "status": "ok",
        "sha256_do_artefato_conferido": plano.sha_conferido,
        "metadata_json_presente": tem_meta if plano.arquivo is not None else None,
        "sha256_no_metadados_confere": (
            meta.get("payload", {}).get(plano.arquivo.name) == plano.sha_declarado
            if tem_meta else None),
        "variaveis": features,
        "n_variaveis": len(features),
        "variaveis_fora_do_dicionario_do_projeto": fora,
        "todas_no_dicionario_do_projeto": not fora,
        "parametros": _parametros(plano.id, obj),
        "r3_busca": _r3(plano.id, obj),
        "anos_de_treino_do_manifesto": treino,
        "anos_de_treino_dos_metadados": meta.get("config", {}).get("anos_dev"),
        "ano_de_comparacao_fora_do_treino": ano_comparacao not in treino,
        "limiar_confere_manifesto": (
            None if limiar_manifesto is None or limiar_artefato is None
            else float(limiar_artefato) == float(limiar_manifesto)),
        "versoes": artifacts.versoes_bibliotecas(),
        "previsoes": estat,
        "ano_da_entrada": ano,
    }


# --------------------------------------------------------------------------- orquestração
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Previsões dos modelos do projeto (D-97, T-8.6).")
    ap.add_argument("--entrada", required=True, type=Path)
    ap.add_argument("--saida-dir", required=True, type=Path)
    ap.add_argument("--manifesto", type=Path, default=comparacao_manifesto.MANIFESTO_PADRAO)
    ap.add_argument("--modelos", nargs="*", default=None,
                    help="subconjunto do manifesto (padrão: todos os cinco)")
    args = ap.parse_args(argv)

    cfg = load_config()
    manifesto = comparacao_manifesto.carregar_manifesto(args.manifesto, cfg)
    ids = list(args.modelos) if args.modelos else list(MODELOS)

    planos = planejar(manifesto, ids)  # 1. localiza e recusa ausência de quem é obrigatório
    conferir_sha(planos)  # 2. SHA-256 antes de qualquer carga

    anos = set(pq.read_table(args.entrada, columns=["ANO"]).column("ANO").to_pylist())
    checar_anos(anos, cfg["ano_teste"], cfg["ano_comparacao"],
                os.environ.get(PORTA_ENV) == "1")  # 3. regra de entrada
    ano = ano_unico(anos)

    sidecar = args.entrada.with_suffix(".json")  # 4. dicionário de features do projeto (R4)
    if not sidecar.is_file():
        raise SystemExit(f"falta o JSON de conferência da entrada ({sidecar}): exporte de novo")
    conferencia = json.loads(sidecar.read_text(encoding="utf-8"))
    if int(conferencia["ano"]) != ano:
        raise SystemExit("o JSON de conferência e o parquet têm anos diferentes")
    dicionario = list(conferencia["features_do_projeto"])

    objs: dict[str, object] = {}  # 5. carga, depois da recusa de ano
    avisos: dict[str, str] = {}
    for plano in planos:
        if plano.arquivo is not None and not plano.presente:
            avisos[plano.id] = (f"pulado: {plano.arquivo} não existe (B0 e B1 ficam no Drive até "
                                "o Programador copiá-los; sem previsão inventada)")
            print(f"AVISO {plano.id}: {avisos[plano.id]}", file=sys.stderr)
            continue
        objs[plano.id] = carregar(plano)

    colunas = [*dicionario, "ANO", "LINHA"]
    resultados = prever_entrada(args.entrada, objs, colunas, ano, cfg["ano_comparacao"])

    resumo: dict[str, dict] = {}
    args.saida_dir.mkdir(parents=True, exist_ok=True)
    for plano in planos:
        if plano.id in avisos:
            resumo[plano.id] = {"status": "ausente", "motivo": avisos[plano.id]}
            continue
        obj = objs[plano.id]
        res = resultados[plano.id]
        features = features_do_modelo(plano.id, obj)
        frame = pd.DataFrame({"ANO": res["ANO"], "LINHA": res["LINHA"], "p": res["p"]})
        if res["estimavel"] is not None:
            frame["estimavel"] = res["estimavel"]
        saida = args.saida_dir / f"p_{plano.id}_{ano}.parquet"
        frame.to_parquet(saida, index=False)
        estat = estatisticas(res["p"], res["estimavel"])
        conf = conformidade(plano, obj, features, dicionario, ano, cfg["ano_comparacao"],
                            modelo_do_manifesto(manifesto, plano.id), estat)
        caminho_conf = args.saida_dir / f"p_{plano.id}_{ano}.conformidade.json"
        caminho_conf.write_text(json.dumps(conf, indent=2, ensure_ascii=False, default=str) + "\n",
                                encoding="utf-8")
        resumo[plano.id] = {"status": "ok", "saida": str(saida),
                            "conformidade": str(caminho_conf), "linhas": estat["linhas"]}

    relatorio = args.saida_dir / f"prever_projeto_{ano}.resumo.json"
    relatorio.write_text(json.dumps({"ano": ano, "modelos": resumo}, indent=2,
                                    ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"ano": ano, "relatorio": str(relatorio), "modelos": resumo},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
