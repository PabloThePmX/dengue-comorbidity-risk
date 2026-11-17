"""SHAP global do modelo de árvore do M1 (T-4.8, FR-13 SHOULD, R1, R7, R8, R10, P6).

Entrada: um modelo de árvore já ajustado (`XGBoostM1` ou `CatBoostM1`, dos wrappers `*_m1.py`) e o
DataFrame de desenvolvimento (2022–23, com `ANO`, `y` e as features). Qual modelo entra é decidido
pela seleção (T-4.9); esta função não escolhe.

Só agregados saem (R7), e nunca valores por linha:
- média do |SHAP| por feature, em log-odds (a margem do modelo);
- média do |interação SHAP| em matriz p × p. A diagonal é o efeito principal (convenção do SHAP);
  fora dela, a interação do par.

Cálculo: TreeSHAP exato pela rota nativa de cada biblioteca, porque cada uma lida com o próprio
formato de modelo:
- XGBoost: `Booster.predict` com `pred_contribs` e `pred_interactions`;
- CatBoost: `get_feature_importance` com `ShapValues` e `ShapInteractionValues`. Com categóricas, o
  CatBoost usa CTR; não verifiquei se o `shap.TreeExplainer` cobre CTR, então não o usei aqui.

Só as árvores até o melhor ponto entram (FR-22). XGBoost recebe `iteration_range`. CatBoost recebe
uma cópia encurtada com `shrink`, porque `get_feature_importance` não aceita `ntree_end`.

Subamostra: `shap.amostra` do config (50 mil) de 2022–23, estratificada pelo alvo, com a semente do
config (R8). Dentro dela, R1 é conferido de novo (`assert_dev_only`).

Features: as colunas que o modelo lê depois do pré-processamento. Na família "arvore" o mapeamento
é 1 para 1: cada coluna de saída tem o prefixo do transformador (ex.: `niveis__HIPERTENSA`), e o
nome original é o trecho depois de `__`. No CatBoost os nomes já são os originais. A codificação
ordinal de `sexo` (F, I, M = 0, 1, 2) faz a árvore tratar a categoria como se tivesse ordem; isso
aparece na atribuição e é limitação do modelo, não do SHAP.

Identidades conferidas em cada linha, guardando só o maior erro (nada por linha sai):
- aditividade: soma das contribuições = margem do modelo;
- coerência: soma das interações de cada feature = SHAP dessa feature;
- simetria: matriz de interações igual à sua transposta.

Notas de desempenho: o CatBoost calcula interações por linha e por árvore, então o tempo cresce com
o nº de árvores. Medir no Colab (T-4.10) antes de concluir que cabe na demo.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import xgboost as xgb
from catboost import CatBoostClassifier, Pool

from dengue_sinan.catboost_m1 import CatBoostM1
from dengue_sinan.guard import assert_dev_only
from dengue_sinan.preprocess import colunas_do_preprocessor, indices_cat_features_catboost
from dengue_sinan.xgboost_m1 import XGBoostM1

TAREFA = "T-4.8"
TAMANHO_LOTE = 10_000  # linhas por chamada à biblioteca: limita a memória das interações
TOLERANCIA_IDENTIDADE = 1e-4  # erro máximo aceito nas identidades (float32 no XGBoost)
ARQ_IMPORTANCIA = "shap_importancia.csv"
ARQ_INTERACOES = "shap_interacoes.csv"
ARQ_MANIFESTO = "shap_global.json"
ARQUIVOS_DADOS = (ARQ_IMPORTANCIA, ARQ_INTERACOES)
UNIDADE = "log-odds (margem do modelo)"
NOTA_DIAGONAL = (
    "Diagonal = efeito principal (convenção do SHAP); fora da diagonal = interação do par.")


@dataclass(frozen=True)
class ResultadoShap:
    """Agregados do SHAP global. Nenhum campo tem valor por linha (R7)."""

    tipo: str  # "xgboost" ou "catboost"
    n_arvores: int  # árvores usadas: melhor ponto + 1
    n_amostra: int
    n_positivos: int  # positivos na amostra (conferidos contra a supressão de células)
    seed: int
    n_colunas_entrada: int  # colunas que o pré-processador lê (1 para 1 com as de saída)
    colunas_modelo: tuple[str, ...]  # nomes depois do pré-processamento
    features: tuple[str, ...]  # nomes originais (dicionário de features)
    importancia_abs: np.ndarray  # média do |SHAP| por feature, shape (p,)
    interacoes_abs: np.ndarray  # média do |interação SHAP|, shape (p, p)
    erro_aditividade: float  # maior |soma das contribuições − margem| em uma linha
    erro_soma: float  # maior |soma das interações da feature − SHAP da feature| em uma linha
    erro_simetria: float  # maior |Φ − Φᵀ| em uma linha


def amostra_estratificada(y, n: int, seed: int) -> np.ndarray:
    """Posições (ordenadas) de `n` linhas, com a mesma proporção de cada valor de `y`.

    Sorteio sem reposição com `np.random.default_rng(seed)`: a mesma semente e os mesmos `y` dão a
    mesma amostra. O arredondamento que sobra vai para a classe maior, para dar exatamente `n`.
    """
    y = np.asarray(y)
    total = y.size
    if not 0 < n <= total:
        raise ValueError(f"amostra de {n} linhas fora de (0, {total}]")
    rng = np.random.default_rng(seed)
    classes, contagens = np.unique(y, return_counts=True)
    cotas = np.floor(contagens * n / total).astype(np.int64)
    cotas[np.argmax(contagens)] += n - int(cotas.sum())
    escolhidas = [
        rng.choice(np.flatnonzero(y == classe), size=int(cota), replace=False)
        for classe, cota in zip(classes, cotas, strict=True)
    ]
    return np.sort(np.concatenate(escolhidas))


def _nome_original(nome: str) -> str:
    """`niveis__HIPERTENSA` -> `HIPERTENSA`; sem prefixo, o próprio nome."""
    return nome.split("__", 1)[1] if "__" in nome else nome


def _componentes(modelo) -> tuple[str, object, object, int]:
    """(tipo, pré-processador ajustado, estimador ajustado, nº de árvores até o melhor ponto).

    Lê atributos privados dos wrappers (`_pipeline`, `_estimador`): é o único acesso a eles fora
    dos próprios módulos. Ver o relatório da T-4.8 (proposta: um acessor público nos wrappers).
    """
    if isinstance(modelo, XGBoostM1):
        tipo = "xgboost"
    elif isinstance(modelo, CatBoostM1):
        tipo = "catboost"
    else:
        raise ValueError(
            "SHAP global só para XGBoostM1 ou CatBoostM1 (modelo de árvore do M1); "
            f"recebi {type(modelo).__name__}")
    pre = modelo._pipeline.named_steps["preprocessamento"]
    if not hasattr(pre, "transformers_"):
        raise ValueError("o pré-processador do modelo não está ajustado")
    melhor = modelo.melhor_ponto()
    if melhor is None:
        raise ValueError("o modelo não foi ajustado (sem melhor ponto)")
    return tipo, pre, modelo._estimador, int(melhor) + 1


def _fatia(X, ini: int, fim: int):
    return X.iloc[ini:fim] if hasattr(X, "iloc") else X[ini:fim]


def _lote_xgboost(booster, bloco, n_arvores: int):
    """(contribuições (b, p+1), interações (b, p+1, p+1), margem (b,)), com o viés por último."""
    dm = xgb.DMatrix(np.asarray(bloco, dtype=np.float32))
    faixa = (0, n_arvores)
    contrib = booster.predict(dm, pred_contribs=True, iteration_range=faixa)
    inter = booster.predict(dm, pred_interactions=True, iteration_range=faixa)
    margem = booster.predict(dm, output_margin=True, iteration_range=faixa)
    return contrib, inter, margem


def _lote_catboost(copia, bloco, cat_idx: list[int]):
    """Mesma forma de `_lote_xgboost`. O CatBoost não põe viés na matriz de interações (a linha e
    a coluna do viés vêm zeradas); as colunas de features ficam iguais às do XGBoost."""
    pool = Pool(bloco, cat_features=cat_idx)
    contrib = copia.get_feature_importance(pool, type="ShapValues")
    inter = copia.get_feature_importance(pool, type="ShapInteractionValues")
    margem = copia.predict(pool, prediction_type="RawFormulaVal")
    return contrib, inter, margem


def agregar(estimador, n_arvores: int, X, cat_idx: list[int] | None = None,
            lote: int = TAMANHO_LOTE) -> dict:
    """Médias do |SHAP| e do |interação| sobre `X` (já pré-processado) e os maiores erros de
    identidade. Não guarda valor por linha: cada lote é somado e descartado.

    `estimador` é um XGBClassifier ou CatBoostClassifier ajustado; `n_arvores` limita as árvores.
    """
    n, p = X.shape[0], X.shape[1]
    if n == 0:
        raise ValueError("X vazio")
    if isinstance(estimador, CatBoostClassifier):
        copia = estimador.copy()
        copia.shrink(ntree_end=n_arvores)  # só as árvores até o melhor ponto (FR-22)
        if cat_idx is None:
            raise ValueError("CatBoost precisa de cat_idx")
    elif isinstance(estimador, xgb.XGBClassifier):
        booster = estimador.get_booster()
    else:
        raise ValueError(f"estimador sem TreeSHAP nativo aqui: {type(estimador).__name__}")

    soma_abs_phi = np.zeros(p)
    soma_abs_inter = np.zeros((p, p))
    erro_ad = erro_soma = erro_sim = 0.0
    for ini in range(0, n, lote):
        bloco = _fatia(X, ini, ini + lote)
        if isinstance(estimador, CatBoostClassifier):
            contrib, inter, margem = _lote_catboost(copia, bloco, cat_idx)
        else:
            contrib, inter, margem = _lote_xgboost(booster, bloco, n_arvores)
        phi = contrib[:, :p]
        inter_p = inter[:, :p, :p]
        soma_abs_phi += np.abs(phi).sum(axis=0)
        soma_abs_inter += np.abs(inter_p).sum(axis=0)
        erro_ad = max(erro_ad, float(np.abs(contrib.sum(axis=1) - margem).max()))
        soma_linhas = inter[:, :p, :].sum(axis=2)  # soma sobre todo j, inclusive o viés
        erro_soma = max(erro_soma, float(np.abs(soma_linhas - phi).max()))
        erro_sim = max(erro_sim, float(np.abs(inter_p - inter_p.transpose(0, 2, 1)).max()))
    return {
        "importancia_abs": soma_abs_phi / n,
        "interacoes_abs": soma_abs_inter / n,
        "erro_aditividade": erro_ad,
        "erro_soma": erro_soma,
        "erro_simetria": erro_sim,
        "n": n,
    }


def calcular_shap_global(modelo, df, cfg: dict) -> ResultadoShap:
    """SHAP global do modelo sobre a subamostra estratificada de `df` (2022–23).

    `df` precisa de `ANO`, `y` e as features do modelo. R1: recusa o ano de teste.
    """
    assert_dev_only(df)  # R1
    tipo, pre, estimador, n_arvores = _componentes(modelo)
    n = int(cfg["shap"]["amostra"])
    if n > len(df):
        raise ValueError(f"amostra de {n} linhas maior que os {len(df)} casos de desenvolvimento")
    y = df["y"].to_numpy()
    seed = int(cfg["seed"])  # R8
    posicoes = amostra_estratificada(y, n, seed)
    sub = df.iloc[posicoes]
    assert_dev_only(sub)  # R1, de novo na subamostra

    X_t = pre.transform(sub)
    colunas = tuple(str(c) for c in pre.get_feature_names_out())
    features = tuple(_nome_original(c) for c in colunas)
    if len(set(features)) != len(features):
        raise ValueError(f"nomes originais repetidos no pré-processador: {features}")
    cat_idx = indices_cat_features_catboost(pre) if tipo == "catboost" else None
    agregado = agregar(estimador, n_arvores, X_t, cat_idx=cat_idx)
    if agregado["n"] != n:
        raise RuntimeError("a subamostra não foi inteira")
    return ResultadoShap(
        tipo=tipo,
        n_arvores=n_arvores,
        n_amostra=n,
        n_positivos=int(y[posicoes].sum()),
        seed=seed,
        n_colunas_entrada=len(colunas_do_preprocessor(pre)),
        colunas_modelo=colunas,
        features=features,
        importancia_abs=agregado["importancia_abs"],
        interacoes_abs=agregado["interacoes_abs"],
        erro_aditividade=agregado["erro_aditividade"],
        erro_soma=agregado["erro_soma"],
        erro_simetria=agregado["erro_simetria"],
    )


def _sha256(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def _csv(linhas: list[list]) -> bytes:
    buffer = io.StringIO()
    escritor = csv.writer(buffer, lineterminator="\n")
    escritor.writerows(linhas)
    return buffer.getvalue().encode("utf-8")


def gravar_shap_global(resultado: ResultadoShap, out_dir: str | Path, cfg: dict) -> dict:
    """Grava os dois CSV de agregados e o manifesto JSON em `out_dir`; devolve o manifesto.

    O manifesto traz o SHA-256 de cada CSV (padrão de verify.py), para o que vier do Colab ser
    conferido antes de virar gráfico.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    importancia = [["feature", "coluna_modelo", "media_abs_shap"]] + [
        [f, c, f"{float(v):.10g}"]
        for f, c, v in zip(resultado.features, resultado.colunas_modelo,
                           resultado.importancia_abs, strict=True)
    ]
    interacoes = [["feature", *resultado.features]] + [
        [f, *(f"{float(v):.10g}" for v in linha)]
        for f, linha in zip(resultado.features, resultado.interacoes_abs, strict=True)
    ]
    conteudos = {ARQ_IMPORTANCIA: _csv(importancia), ARQ_INTERACOES: _csv(interacoes)}
    arquivos = {}
    for nome, dados in conteudos.items():
        (out / nome).write_bytes(dados)
        arquivos[nome] = {"sha256": hashlib.sha256(dados).hexdigest(), "bytes": len(dados)}

    manifesto = {
        "tarefa": TAREFA,
        "modelo": resultado.tipo,
        "unidade": UNIDADE,
        "nota_diagonal": NOTA_DIAGONAL,
        "n_arvores": resultado.n_arvores,
        "n_amostra": resultado.n_amostra,
        "n_positivos_amostra": resultado.n_positivos,
        "amostra_estratificada_por": "y",
        "seed": resultado.seed,
        "n_colunas_entrada": resultado.n_colunas_entrada,
        "n_features": len(resultado.features),
        "features": list(resultado.features),
        "medidas": {
            "erro_aditividade": resultado.erro_aditividade,
            "erro_soma": resultado.erro_soma,
            "erro_simetria": resultado.erro_simetria,
        },
        "arquivos": arquivos,
    }
    (out / ARQ_MANIFESTO).write_text(
        json.dumps(manifesto, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifesto


def carregar_manifesto(out_dir: str | Path) -> dict:
    return json.loads((Path(out_dir) / ARQ_MANIFESTO).read_text(encoding="utf-8"))


def arquivos_conferem(out_dir: str | Path, manifesto: dict) -> bool:
    """True se cada CSV listado no manifesto existe e tem o SHA-256 registrado."""
    out = Path(out_dir)
    for nome, meta in manifesto["arquivos"].items():
        caminho = out / nome
        if not caminho.is_file() or _sha256(caminho) != meta["sha256"]:
            return False
    return True


# --- Gancho do fim da sessão (T-4.8, runner.GANCHOS_PADRAO) ----------------------------------

MODELOS_DE_ARVORE_SHAP = ("xgboost", "catboost")  # os que têm TreeSHAP nativo aqui (D-35)


def escolher_modelo_shap(sel: dict) -> str:
    """Modelo cujo SHAP global sai: o vencedor da T-4.9 se for de árvore; senão o de maior PR-AUC
    média entre XGBoost e CatBoost (empate: a ordem de `MODELOS_DE_ARVORE_SHAP`)."""
    if sel["vencedor"] in MODELOS_DE_ARVORE_SHAP:
        return sel["vencedor"]
    return max(MODELOS_DE_ARVORE_SHAP,
               key=lambda m: (sel["modelos"][m]["pr_auc_media"],
                              -MODELOS_DE_ARVORE_SHAP.index(m)))


def executar_sessao(cfg: dict, resultados: dict) -> list[dict]:
    """Gancho `shap` do runner: refaz o ajuste do modelo escolhido em todo 2022–23 (parâmetros de
    `parametros.json`, nº de árvores = mediana dos melhores pontos, como no retreino), calcula os
    agregados na amostra estratificada de `shap.amostra` linhas, grava em `<relatorios>/shap/` e
    devolve os checks do bloco `shap` (o runner grava o bloco no relatório da sessão).

    Imports locais: `retreino` importa este módulo e `verificacao_shap` também.
    """
    from dengue_sinan import cv, runner, selecao, verificacao_shap
    from dengue_sinan.guard import assert_dev_only
    from dengue_sinan.retreino import contagem_final

    sel = runner._ler_json(runner.pasta_m1(cfg) / selecao.NOME_SELECAO)
    if sel is None:
        raise FileNotFoundError("sem selecao.json: a seleção (T-4.9) roda antes do SHAP")
    modelo_nome = escolher_modelo_shap(sel)
    if modelo_nome not in resultados:
        raise ValueError(f"{modelo_nome} não está nos resultados da sessão")
    pasta = Path(resultados[modelo_nome]["pasta"])
    parametros = runner._ler_json(pasta / runner.ARQ_PARAMETROS)
    metricas = runner._ler_json(pasta / runner.ARQ_METRICAS)
    if parametros is None or metricas is None:
        raise FileNotFoundError(f"sem parametros/metricas de {modelo_nome} em {pasta}")
    pontos = [metricas["melhores_pontos"].get(r) for r in cfg["ordem_dobras"]]
    n_iter = contagem_final(modelo_nome, pontos)

    df = runner._carregar_dados_de_desenvolvimento(cfg)
    assert_dev_only(df)  # R1
    modelo = cv.construir_modelo(modelo_nome, parametros["melhores_parametros"], cfg)
    modelo.fixar_iteracoes(n_iter)
    modelo.ajustar(df, df["y"].to_numpy())
    resultado = calcular_shap_global(modelo, df, cfg)
    out = runner._caminho(cfg, "relatorios") / "shap"
    manifesto = gravar_shap_global(resultado, out, cfg)
    return verificacao_shap.checks(manifesto, out, cfg)
