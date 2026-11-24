"""Probabilidades do m1_lora para a entrada comum da comparação (D-97), em ambiente isolado.

O m1_lora é o elastic net congelado da branch `feat/lora` (decisão do Programador): um
`FittedM1Model` (pipeline + calibrador isotônico OOF + limiar F2), que a branch publica com
`predict_proba` (ver `evaluate.py`). A probabilidade comparada é a calibrada.

Roda com o Python do worktree da branch (o `joblib` executa código ao carregar, então o artefato
só é carregado lá). Este arquivo é da `main`; o código de modelo é o da branch.

    <worktree>\\.venv\\Scripts\\python.exe scripts/comparacao/prever_lora.py
        --worktree <worktree> --entrada <entrada.parquet> --saida <previsoes.parquet>
        --manifesto config/comparacao/manifesto.yaml

Ordem, sem atalho:
1. confere o interpretador (venv do worktree da branch);
2. lê o manifesto e confere o SHA-256 do artefato ANTES de qualquer carga;
3. regra de entrada: recusa o ano de teste (2024) sempre, e o ano de comparação (2025) a menos que
   `DENGUE_PORTA_COMPARACAO=1` (só o avaliador define essa variável). O ano vem da própria entrada;
4. carrega com `load_bundle` da branch e, depois, restaura o remendo de BSpline e os nomes em
   `__main__` que a carga tocou;
5. adapta o quadro do projeto às colunas de `model.feature_cols`, coluna a coluna (`ADAPTADOR`),
   prevê em blocos e grava ANO, LINHA e p (probabilidade calibrada);
6. grava o JSON de conformidade (R3 a R6), só com agregados e nomes (R7).
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

MODELO = "m1_lora"
ANO_TESTE = 2024  # espelha config/base.yaml (ano_teste); um teste da main confere o valor
PORTA_ENV = "DENGUE_PORTA_COMPARACAO"
BLOCO = 200_000
ARTEFATO_DO_MODELO = "models/m1_final.joblib"
CLASSE_DO_MODELO = "FittedM1Model"
TERMOS_R3 = ("class_weight", "scale_pos_weight", "is_unbalance", "auto_class_weights",
             "pos_weight", "SMOTE")
NOMES_R3_NOS_PARAMETROS = ("class_weight", "scale_pos_weight", "is_unbalance",
                           "auto_class_weights", "pos_weight")

SEXO_CATEGORIAS = ("F", "M", "I")  # ordem de dataset.build_feature_frame da branch
NIVEL3 = ("Sim", "Não", "Ausente")  # ordem de dataset._tres_niveis da branch
COMORBIDADES = ("DIABETES", "HEMATOLOG", "HEPATOPAT", "RENAL", "HIPERTENSA", "ACIDO_PEPT",
                "AUTO_IMUNE")
SINAIS = ("FEBRE", "MIALGIA", "CEFALEIA", "EXANTEMA", "VOMITO", "NAUSEA", "DOR_COSTAS",
          "CONJUNTVIT", "ARTRITE", "ARTRALGIA", "PETEQUIA_N", "LEUCOPENIA", "LACO", "DOR_RETRO")

# Tabela explícita: feature (mesmo nome na branch e no dicionário do projeto) -> (tipo, domínio).
# "numero": float64, NaN recusado (o SplineTransformer da branch usa handle_missing='error');
# "inteiro": int8, NaN e valores fora do domínio recusados;
# "categoria": pd.Categorical com as categorias da branch, valor fora delas recusado.
# Os 21 indicadores de 3 níveis seguem uma só regra, por isso vêm de uma compreensão.
ADAPTADOR: dict[str, tuple[str, tuple | None]] = {
    "idade_anos": ("numero", None),
    "dias_ate_notificacao": ("numero", None),
    "gestante": ("inteiro", (0, 1)),
    "n_comorbidades": ("inteiro", tuple(range(len(COMORBIDADES) + 1))),
    "sexo": ("categoria", SEXO_CATEGORIAS),
    **{c: ("categoria", NIVEL3) for c in (*COMORBIDADES, *SINAIS)},
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
        tipo, dominio = ADAPTADOR[nome]
        serie = quadro[nome]
        if tipo == "numero":
            numerica = pd.to_numeric(serie, errors="raise").astype("float64")
            if numerica.isna().any():
                raise ValueError(f"{nome}: valor ausente; o pipeline da branch não aceita NaN")
            out[nome] = numerica
        elif tipo == "inteiro":
            if serie.isna().any():
                raise ValueError(f"{nome}: valor ausente; o contrato não aceita")
            valores = serie.astype("int64")
            fora = ~valores.isin(list(dominio))
            if fora.any():
                raise ValueError(f"{nome}: valores fora de {list(dominio)}: "
                                 f"{sorted(set(valores[fora].astype(str)))[:5]}")
            out[nome] = valores.astype("int8")
        else:  # "categoria": valor fora do domínio levanta erro; nada é adivinhado
            valores = serie.astype(object)
            fora = ~valores.isin(list(dominio))
            if fora.any():
                raise ValueError(f"{nome}: valores fora de {list(dominio)}: "
                                 f"{sorted(set(valores[fora].astype(str)))[:5]}")
            out[nome] = pd.Categorical(valores, categories=list(dominio))
    return out


def _versoes() -> dict:
    nomes = ("numpy", "pandas", "pyarrow", "scikit-learn", "scipy", "joblib")
    versoes = {"python": platform.python_version()}
    for nome in nomes:
        try:
            versoes[nome] = metadata.version(nome)
        except metadata.PackageNotFoundError:
            versoes[nome] = None
    return versoes


def _primitivo(valor):
    """Valor de parâmetro em forma de JSON: número, texto ou booleano; o resto vira texto."""
    if valor is None or isinstance(valor, bool | int | float | str):
        return valor
    if isinstance(valor, np.integer | np.floating):
        return valor.item()
    return str(valor)


def _ocorrencias_r3(src: Path) -> dict[str, int]:
    """Conta menções aos termos de R3 no código da branch (só contagens, sem trechos).

    Inclui comentários: a contagem diz onde o termo aparece, não se é usado. Quem decide é
    `correcao_de_desbalanceamento`, que olha os parâmetros do estimador carregado.
    """
    contagem = {t: 0 for t in TERMOS_R3}
    for arquivo in src.rglob("*.py"):
        texto = arquivo.read_text(encoding="utf-8", errors="ignore")
        for termo in TERMOS_R3:
            contagem[termo] += len(re.findall(re.escape(termo), texto))
    return contagem


def correcao_de_desbalanceamento(pipeline) -> dict[str, str]:
    """Parâmetros de R3 com valor que corrige desbalanceamento (vazio = nenhum; R3)."""
    achados: dict[str, str] = {}
    for chave, valor in pipeline.get_params(deep=True).items():
        if chave.split("__")[-1] not in NOMES_R3_NOS_PARAMETROS:
            continue
        if valor not in (None, 1, 1.0, False):
            achados[chave] = str(valor)
    return achados


def conformidade(bundle, model, features: list[str], dicionario: list[str], worktree: Path,
                 sha: str, removidos_de_main: list[str]) -> dict:
    clf = model.pipeline.named_steps["clf"]
    params = {k: _primitivo(v) for k, v in clf.get_params().items()}
    fora = checar_dicionario(features, dicionario)
    achados_r3 = correcao_de_desbalanceamento(model.pipeline)
    meta = bundle["metadados"]
    config = meta.get("config", {})
    return {
        "modelo": MODELO,
        "sha256_do_artefato_conferido": sha,
        "classe_do_bundle": type(model).__name__,
        "calibrador": f"ProbabilityCalibrator({model.calibrator.method})",
        "limiar_f2_do_artefato": float(model.limiar),
        "variaveis": list(features),
        "n_variaveis": len(features),
        "variaveis_fora_do_dicionario_do_projeto": fora,
        "todas_no_dicionario_do_projeto": not fora,
        "parametros_do_estimador_final": params,
        "r3_busca": {
            "ocorrencias_no_codigo_da_branch": _ocorrencias_r3(worktree / "src" / "dengue_sinan"),
            "parametros_com_correcao_de_desbalanceamento": achados_r3,
            "com_correcao_de_desbalanceamento": bool(achados_r3),
        },
        "metadados_da_branch": {
            "versao_codigo": meta.get("versao_codigo"),
            "data_treino": meta.get("data_treino"),
            "anos_de_treino_config": [int(a) for a in config.get("anos_dev", [])],
            "ano_teste_config": config.get("ano_teste"),
            "hashes_dados_quantidade": len(meta.get("hashes_dados", {})),
            "lista_features_quantidade": len(meta.get("lista_features", [])),
            "sha256_no_metadados": meta.get("sha256_modelo"),
            "versoes_de_treino": meta.get("versoes_bibliotecas", {}),
        },
        "versoes_do_ambiente": _versoes(),
        "nomes_removidos_de_main_apos_carga": removidos_de_main,
    }


def prever(model, entrada: Path, features: list[str], saida: Path) -> dict:
    import pyarrow.parquet as pq

    arquivo = pq.ParquetFile(entrada)
    colunas = [*features, "ANO", "LINHA"]
    anos, linhas, probs = [], [], []
    for lote in arquivo.iter_batches(batch_size=BLOCO, columns=colunas):
        bloco = lote.to_pandas()
        x = adaptar(bloco, features)
        # predict_proba do FittedM1Model: pipeline e calibrador isotônico, a probabilidade que
        # a branch publica (evaluate.py: m1_bundle.predict_proba(feat)[:, 1])
        p = np.clip(np.asarray(model.predict_proba(x), dtype="float64")[:, 1], 0.0, 1.0)
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
def remendos_restaurados(criados: list[str], classe_scipy=None):
    """Restaura o que a carga muda em estado global: o `__setstate__` do BSpline (o remendo de
    `artifacts._ensure_scipy_bspline_compat` da branch) e os nomes criados em `__main__`.

    `criados` recebe, antes da remoção, os nomes que a carga criou em `__main__`; a lista deve
    sair vazia em uso normal. A restauração acontece mesmo se a carga falhar.
    """
    import __main__

    if classe_scipy is None:
        from scipy.interpolate import BSpline

        classe_scipy = BSpline
    ausente = object()
    setstate_antes = classe_scipy.__dict__.get("__setstate__", ausente)
    main_antes = dict(vars(__main__))
    try:
        yield
    finally:
        criados.extend(sorted(set(vars(__main__)) - set(main_antes)))
        if setstate_antes is ausente:
            if "__setstate__" in classe_scipy.__dict__:
                delattr(classe_scipy, "__setstate__")
        else:
            classe_scipy.__setstate__ = setstate_antes
        for nome in criados:
            if hasattr(__main__, nome):
                delattr(__main__, nome)
        for nome, valor in main_antes.items():
            if vars(__main__).get(nome, ausente) is not valor:
                setattr(__main__, nome, valor)


def carregar_bundle(worktree: Path, artefato: Path) -> tuple[object, list[str]]:
    """Carrega o pacote da branch com o código dela; devolve (bundle, nomes criados em __main__).

    O import de `dengue_sinan` vem do `src` do worktree, conferido pelo caminho do módulo.
    """
    src = worktree / "src"
    sys.path.insert(0, str(src))
    import dengue_sinan

    if not Path(dengue_sinan.__file__).resolve().is_relative_to(src.resolve()):
        raise SystemExit("dengue_sinan não veio do worktree da branch")
    from dengue_sinan import artifacts

    criados: list[str] = []
    with remendos_restaurados(criados):
        bundle = artifacts.load_bundle(artefato)
    return bundle, criados


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Previsões do m1_lora (D-97).")
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

    bundle, removidos = carregar_bundle(worktree, artefato)
    model = bundle["model"]
    if type(model).__name__ != CLASSE_DO_MODELO:
        raise SystemExit(f"o bundle não tem {CLASSE_DO_MODELO} (tem {type(model).__name__})")
    features = list(model.feature_cols)

    conf = conformidade(bundle, model, features, dicionario, worktree, sha, removidos)
    resumo = prever(model, args.entrada, features, args.saida)
    conf["previsoes"] = resumo
    caminho_conf = args.saida.with_name(args.saida.stem + ".conformidade.json")
    caminho_conf.write_text(json.dumps(conf, indent=2, ensure_ascii=False, default=str) + "\n",
                            encoding="utf-8")
    print(json.dumps({"saida": str(args.saida), "conformidade": str(caminho_conf),
                      "linhas": resumo["linhas"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
