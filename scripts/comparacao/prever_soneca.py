"""Probabilidades do m1_soneca para a entrada comum da comparação (D-97), em ambiente isolado.

Roda com o Python do worktree da branch `feat/soneca` (o `joblib` executa código ao carregar, então
o artefato só é carregado lá). Este arquivo é da `main`; o código de modelo é o da branch.

    <worktree>\\.venv\\Scripts\\python.exe scripts/comparacao/prever_soneca.py
        --worktree <worktree> --entrada <entrada.parquet> --saida <previsoes.parquet>
        --manifesto config/comparacao/manifesto.yaml

Ordem, sem atalho:
1. lê o manifesto e confere o SHA-256 do artefato ANTES de qualquer carga;
2. regra de entrada: recusa o ano de teste (2024) sempre, e o ano de comparação (2025) a menos que
   `DENGUE_PORTA_COMPARACAO=1` (só o avaliador define essa variável). O ano vem da própria entrada;
3. carrega o artefato com o código da branch e confere as variáveis contra o dicionário de features
   do projeto (JSON ao lado da entrada, gravado pelo exportador);
4. adapta o quadro do projeto ao contrato da branch, coluna a coluna (`ADAPTADOR`), prevê em blocos
   e grava ANO, LINHA e p (probabilidade calibrada);
5. grava o JSON de conformidade (R3 a R6), só com agregados e nomes de variáveis (R7).
"""

import argparse
import contextlib
import hashlib
import json
import os
import platform
import re
import sys
from importlib import metadata
from pathlib import Path

import numpy as np
import pandas as pd

MODELO = "m1_soneca"
ANO_TESTE = 2024  # espelha config/base.yaml (ano_teste); um teste da main confere o valor
PORTA_ENV = "DENGUE_PORTA_COMPARACAO"
BLOCO = 200_000
ARTEFATO_DO_MODELO = "reports/modelo_risco_dengue/artefatos/m1_congelado.joblib"
METADADOS_DO_MODELO = "reports/modelo_risco_dengue/artefatos/m1_congelado_metadados.json"
TERMOS_R3 = ("class_weight", "scale_pos_weight", "is_unbalance", "SMOTE")
CLASSES_DO_ARTEFATO = ("ModeloM1", "ModeloB1", "Calibrador")

SEXO_CATEGORIAS = ("F", "M", "I")  # ordem da branch (dataset.SEXOS): define o código ordinal
NIVEL3 = ("Não", "Sim", "Ausente")  # ordem da branch (dataset.NIVEIS): Não=0, Sim=1, Ausente=2

# Tabela explícita coluna a coluna: nome no contrato da branch -> (tipo, categorias).
# "numero": float64 com NaN preservado; "inteiro": int8; "sexo" e "nivel3": pd.Categorical com a
# ordem acima. Qualquer valor fora da tabela ou sem conversão levanta erro; nada é adivinhado.
ADAPTADOR: dict[str, tuple[str, tuple | None]] = {
    "idade_anos": ("numero", None),
    "sexo": ("sexo", SEXO_CATEGORIAS),
    "gestante": ("inteiro", None),
    "DIABETES": ("nivel3", NIVEL3),
    "HEMATOLOG": ("nivel3", NIVEL3),
    "HEPATOPAT": ("nivel3", NIVEL3),
    "RENAL": ("nivel3", NIVEL3),
    "HIPERTENSA": ("nivel3", NIVEL3),
    "ACIDO_PEPT": ("nivel3", NIVEL3),
    "AUTO_IMUNE": ("nivel3", NIVEL3),
    "n_comorbidades": ("inteiro", None),
    "FEBRE": ("nivel3", NIVEL3),
    "MIALGIA": ("nivel3", NIVEL3),
    "CEFALEIA": ("nivel3", NIVEL3),
    "EXANTEMA": ("nivel3", NIVEL3),
    "VOMITO": ("nivel3", NIVEL3),
    "NAUSEA": ("nivel3", NIVEL3),
    "DOR_COSTAS": ("nivel3", NIVEL3),
    "CONJUNTVIT": ("nivel3", NIVEL3),
    "ARTRITE": ("nivel3", NIVEL3),
    "ARTRALGIA": ("nivel3", NIVEL3),
    "PETEQUIA_N": ("nivel3", NIVEL3),
    "DOR_RETRO": ("nivel3", NIVEL3),
    "LEUCOPENIA": ("nivel3", NIVEL3),
    "LACO": ("nivel3", NIVEL3),
    "dias_ate_notificacao": ("numero", None),
}


def sha256_arquivo(caminho: Path, bloco: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        while pedaco := f.read(bloco):
            h.update(pedaco)
    return h.hexdigest()


def ler_manifesto(caminho: Path) -> dict:
    """Lê o manifesto. O worktree da branch não tem PyYAML: a `main` exporta o YAML validado para
    JSON (`comparacao_manifesto.exportar_json`) e o script lê esse JSON. YAML também serve, se
    o ambiente tiver PyYAML."""
    if Path(caminho).suffix.lower() == ".json":
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    import yaml

    with open(caminho, encoding="utf-8") as f:
        return yaml.safe_load(f)


def modelo_do_manifesto(manifesto: dict, id_modelo: str = MODELO) -> dict:
    for modelo in manifesto["modelos"]:
        if modelo["id"] == id_modelo:
            return modelo
    raise ValueError(f"manifesto: modelo {id_modelo} não encontrado")


def checar_anos(anos: set[int], ano_comparacao: int, porta_aberta: bool) -> None:
    """Regra de entrada (R1, R2, D-97). Levanta PermissionError se a entrada não pode ser lida."""
    if ANO_TESTE in anos:
        raise PermissionError(f"recusado: a entrada tem {ANO_TESTE}, o teste congelado (R1). "
                              "Nenhuma entrada com esse ano é lida aqui, em nenhum caso.")
    if ano_comparacao in anos and not porta_aberta:
        raise PermissionError(f"recusado: a entrada tem {ano_comparacao}, o ano de comparação. "
                              f"Só é lido com {PORTA_ENV}=1, definido pelo avaliador (R1, D-97).")


def checar_dicionario(features: list[str], dicionario: list[str]) -> list[str]:
    """Devolve as variáveis do modelo que não estão no dicionário de features do projeto (R4)."""
    return sorted(set(features) - set(dicionario))


def adaptar(quadro: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    """Converte o quadro do projeto para o contrato da branch, na ordem `features` do modelo."""
    desconhecidas = [f for f in features if f not in ADAPTADOR]
    if desconhecidas:
        raise ValueError(f"adaptador sem regra para: {desconhecidas}")
    faltam = [f for f in features if f not in quadro.columns]
    if faltam:
        raise ValueError(f"quadro sem as colunas do modelo: {faltam}")
    out = pd.DataFrame(index=quadro.index)
    for nome in features:
        tipo, categorias = ADAPTADOR[nome]
        serie = quadro[nome]
        if tipo == "numero":
            out[nome] = serie.astype("float64")
        elif tipo == "inteiro":
            if serie.isna().any():
                raise ValueError(f"{nome}: valor ausente, o contrato não aceita")
            out[nome] = serie.astype("int8")
        else:  # "sexo" ou "nivel3": valor fora das categorias vira NaN no pd.Categorical
            valores = serie.astype(object)
            fora = ~valores.isin(list(categorias))
            if fora.any():
                raise ValueError(f"{nome}: valores fora de {list(categorias)}: "
                                 f"{sorted(set(valores[fora].astype(str)))[:5]}")
            out[nome] = pd.Categorical(valores, categories=list(categorias))
    return out


def _versoes() -> dict:
    nomes = ("numpy", "pandas", "pyarrow", "scikit-learn", "xgboost", "joblib", "PyYAML")
    versoes = {"python": platform.python_version()}
    for nome in nomes:
        try:
            versoes[nome] = metadata.version(nome)
        except metadata.PackageNotFoundError:
            versoes[nome] = None
    return versoes


def _ocorrencias_r3(src: Path) -> dict[str, int]:
    """Conta menções aos termos de R3 no código da branch (só contagens, sem trechos)."""
    contagem = {t: 0 for t in TERMOS_R3}
    for arquivo in src.rglob("*.py"):
        texto = arquivo.read_text(encoding="utf-8", errors="ignore")
        for termo in TERMOS_R3:
            contagem[termo] += len(re.findall(re.escape(termo), texto))
    return contagem


def conformidade(bundle: dict, features: list[str], chave_features: str, dicionario: list[str],
                 worktree: Path, meta_modelo: dict, sha: str) -> dict:
    motor = bundle["m1"].motor_
    params = {k: (v if isinstance(v, (int, float, str, bool, type(None))) else str(v))
              for k, v in motor.get_params().items()}
    params_branch = {k: str(v) for k, v in bundle["m1"].params.items()}
    fora = checar_dicionario(features, dicionario)
    r3_motor = {
        "class_weight": params.get("class_weight"),
        "scale_pos_weight": params.get("scale_pos_weight"),
        "is_unbalance": params.get("is_unbalance"),
    }
    com_correcao = (
        r3_motor["scale_pos_weight"] not in (None, 1, 1.0)
        or bool(r3_motor["is_unbalance"])
        or r3_motor["class_weight"] not in (None, {}, "None")
    )
    return {
        "modelo": MODELO,
        "sha256_do_artefato_conferido": sha,
        "chave_das_variaveis_no_artefato": chave_features,
        "variaveis": list(features),
        "n_variaveis": len(features),
        "variaveis_fora_do_dicionario_do_projeto": fora,
        "todas_no_dicionario_do_projeto": not fora,
        "parametros_do_motor": params,
        "parametros_declarados_pela_branch": params_branch,
        "r3_busca": {
            "ocorrencias_no_codigo_da_branch": _ocorrencias_r3(worktree / "src" / "dengue_sinan"),
            "parametros_do_motor": r3_motor,
            "com_correcao_de_desbalanceamento": com_correcao,
        },
        "calibrador": f"{type(bundle['calibrador']).__name__}({bundle['calibrador'].tipo})",
        "versoes": _versoes(),
        "anos_de_treino_dos_metadados": meta_modelo.get("config", {}).get("ANOS_DEV"),
        "anos_na_assinatura_dos_dados": sorted(
            int(a) for a in meta_modelo.get("assinatura_dados_dev", {})),
        "sha256_no_metadados_confere": meta_modelo.get("sha256_modelo") == sha,
    }


def prever(bundle: dict, entrada: Path, features: list[str], saida: Path) -> dict:
    import pyarrow.parquet as pq

    arquivo = pq.ParquetFile(entrada)
    colunas = [*features, "ANO", "LINHA"]
    anos, linhas, probs = [], [], []
    for lote in arquivo.iter_batches(batch_size=BLOCO, columns=colunas):
        bloco = lote.to_pandas()
        x = adaptar(bloco, features)
        bruto = bundle["m1"].prever(x)
        p = np.clip(np.asarray(bundle["calibrador"].prever(bruto), dtype="float64"), 0.0, 1.0)
        if np.isnan(p).any():
            raise ValueError("probabilidade ausente (NaN) em um bloco")
        anos.append(bloco["ANO"].to_numpy(dtype="int64"))
        linhas.append(bloco["LINHA"].to_numpy(dtype="int64"))
        probs.append(p)
    previsoes = pd.DataFrame({
        "ANO": np.concatenate(anos), "LINHA": np.concatenate(linhas), "p": np.concatenate(probs),
    })
    saida.parent.mkdir(parents=True, exist_ok=True)
    previsoes.to_parquet(saida, index=False)
    p = previsoes["p"]
    return {
        "linhas": int(len(previsoes)),
        "p_min": float(p.min()), "p_max": float(p.max()), "p_media": float(p.mean()),
        "p_iguais_a_0_ou_1": int(((p == 0) | (p == 1)).sum()),
        "nans": int(p.isna().sum()),
    }


def checar_interpretador(worktree: Path, prefixo: str) -> None:
    """Recusa rodar fora do venv do worktree da branch (o joblib executa código ao carregar)."""
    venv = (Path(worktree) / ".venv").resolve()
    if Path(prefixo).resolve() != venv:
        raise SystemExit(f"interpretador fora do venv do worktree ({venv}): rode com "
                         f"{venv / 'Scripts' / 'python.exe'} (D-97 g)")


@contextlib.contextmanager
def classes_do_artefato(modelos):
    """Aponta as classes de `__main__` (nomes do notebook) para as da branch, só durante a carga.

    Ao sair, restaura o valor anterior de cada nome, ou remove o atributo se ele não existia.
    """
    import __main__

    anteriores = {n: getattr(__main__, n) for n in CLASSES_DO_ARTEFATO if hasattr(__main__, n)}
    try:
        for nome in CLASSES_DO_ARTEFATO:
            setattr(__main__, nome, getattr(modelos, nome))
        yield
    finally:
        for nome in CLASSES_DO_ARTEFATO:
            if nome in anteriores:
                setattr(__main__, nome, anteriores[nome])
            elif hasattr(__main__, nome):
                delattr(__main__, nome)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Previsões do m1_soneca (D-97).")
    ap.add_argument("--worktree", required=True, type=Path)
    ap.add_argument("--entrada", required=True, type=Path)
    ap.add_argument("--saida", required=True, type=Path)
    ap.add_argument("--manifesto", required=True, type=Path)
    args = ap.parse_args(argv)

    import pyarrow.parquet as pq

    worktree = args.worktree.resolve()
    checar_interpretador(worktree, sys.prefix)  # antes de qualquer carga (joblib executa código)
    manifesto = ler_manifesto(args.manifesto)
    modelo = modelo_do_manifesto(manifesto)
    artefato = worktree / ARTEFATO_DO_MODELO
    declarado = modelo["artefato"]["sha256"]
    if modelo["artefato"]["caminho"] != ARTEFATO_DO_MODELO:
        raise SystemExit("manifesto e script apontam para artefatos diferentes")
    sha = sha256_arquivo(artefato)
    if sha != declarado:
        raise SystemExit(f"SHA-256 do artefato ({sha}) difere do manifesto ({declarado}): "
                         "não carrego (D-97 g)")

    anos = set(pq.read_table(args.entrada, columns=["ANO"]).column("ANO").to_pylist())
    checar_anos(anos, manifesto["ano_comparacao"], os.environ.get(PORTA_ENV) == "1")

    sidecar = args.entrada.with_suffix(".json")
    if not sidecar.is_file():
        raise SystemExit(f"falta o JSON de conferência da entrada ({sidecar}): exporte de novo")
    dicionario = json.loads(sidecar.read_text(encoding="utf-8"))["features_do_projeto"]

    src = worktree / "src"
    sys.path.insert(0, str(src))
    import joblib

    import dengue_sinan
    from dengue_sinan import modelos

    if not Path(dengue_sinan.__file__).resolve().is_relative_to(src.resolve()):
        raise SystemExit("dengue_sinan não veio do worktree da branch")
    with classes_do_artefato(modelos):  # só durante a carga; depois o __main__ volta ao normal
        bundle = joblib.load(artefato)
    chave = "variaveis" if "variaveis" in bundle else "features"
    features = list(bundle[chave])
    meta_modelo = json.loads((worktree / METADADOS_DO_MODELO).read_text(encoding="utf-8"))

    conf = conformidade(bundle, features, chave, dicionario, worktree, meta_modelo, sha)
    resumo = prever(bundle, args.entrada, features, args.saida)
    conf["previsoes"] = resumo
    caminho_conf = args.saida.with_name(args.saida.stem + ".conformidade.json")
    caminho_conf.write_text(json.dumps(conf, indent=2, ensure_ascii=False, default=str) + "\n",
                            encoding="utf-8")
    print(json.dumps({"saida": str(args.saida), "conformidade": str(caminho_conf),
                      "linhas": resumo["linhas"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
