"""Testes das dobras leave-one-region-out (T-2.3) com dados sintéticos (nenhum microdado real)."""

import numpy as np
import pandas as pd
import pytest

from dengue_sinan import folds

ORDEM = ["Sudeste", "Sul", "Centro-Oeste", "Nordeste", "Norte"]


def _cfg(tmp_path) -> dict:
    return {
        "seed": 20261103,
        "ordem_dobras": ORDEM,
        "validacao_interna_frac": 0.10,
        "ano_teste": 2024,
        "caminhos": {"dados": str(tmp_path / "data"), "relatorios": str(tmp_path / "reports")},
    }


def _df(n_por_regiao=200, prevalencia=0.1, seed=0) -> pd.DataFrame:
    """Casos sintéticos de 2022 e 2023 nas cinco regiões, com ANO inteiro e LINHA por arquivo."""
    rng = np.random.default_rng(seed)
    linhas = []
    for r, regiao in enumerate(ORDEM):
        for i in range(n_por_regiao):
            # LINHA é única dentro de cada ano, como no Parquet real.
            linha = r * n_por_regiao + i
            linhas.append({
                "ANO": 2022 if i % 2 == 0 else 2023,
                "LINHA": linha,
                "regiao": regiao,
                "y": int(rng.random() < prevalencia),
            })
    return pd.DataFrame(linhas)


def test_loro_folds_cinco_dobras_na_ordem_do_config(tmp_path):
    dobras = folds.loro_folds(_cfg(tmp_path), _df())
    assert [regiao for regiao, _, _ in dobras] == ORDEM


def test_cada_validacao_tem_uma_regiao_e_treino_nao_cruza(tmp_path):
    df = _df()
    dobras = folds.loro_folds(_cfg(tmp_path), df)
    vistos = np.zeros(len(df), dtype=int)
    for regiao, treino, validacao in dobras:
        assert set(df["regiao"].iloc[validacao]) == {regiao}
        assert set(df["regiao"].iloc[treino]) == set(ORDEM) - {regiao}
        assert np.intersect1d(treino, validacao).size == 0
        vistos[validacao] += 1
    assert (vistos == 1).all()  # cada linha aparece em exatamente uma validação


def test_inner_split_preserva_prevalencia_e_particiona_o_treino():
    rng = np.random.default_rng(1)
    y = (rng.random(200_000) < 0.05).astype(int)
    idx_treino = np.arange(len(y))
    ajuste, parada = folds.inner_split(idx_treino, y, frac=0.10, seed=7)
    # Partição: juntas formam o treino, sem repetição.
    assert np.array_equal(np.sort(np.concatenate([ajuste, parada])), idx_treino)
    assert abs(y[ajuste].mean() - y[parada].mean()) < 0.0001  # < 0,01 pp
    assert abs(len(parada) / len(y) - 0.10) < 0.001


def test_inner_split_so_usa_o_treino_passado():
    y = np.array([0, 1] * 50)
    idx_treino = np.arange(0, 100, 2)  # só as posições pares
    ajuste, parada = folds.inner_split(idx_treino, y, frac=0.2, seed=3)
    assert set(np.concatenate([ajuste, parada])) == set(idx_treino)


def test_inner_split_mesma_semente_mesmo_resultado():
    y = (np.arange(1000) % 7 == 0).astype(int)
    a1, p1 = folds.inner_split(np.arange(1000), y, 0.1, seed=11)
    a2, p2 = folds.inner_split(np.arange(1000), y, 0.1, seed=11)
    assert np.array_equal(a1, a2) and np.array_equal(p1, p2)


def test_loro_recusa_ano_de_teste(tmp_path):
    df = _df()
    df.loc[0, "ANO"] = 2024
    with pytest.raises(RuntimeError, match="teste congelado"):
        folds.loro_folds(_cfg(tmp_path), df)


def test_loro_recusa_ano_em_texto(tmp_path):
    df = _df()
    df["ANO"] = df["ANO"].astype(str)
    with pytest.raises(ValueError, match="inteira"):
        folds.loro_folds(_cfg(tmp_path), df)


def test_loro_recusa_regiao_nula(tmp_path):
    df = _df()
    df.loc[3, "regiao"] = None
    with pytest.raises(ValueError, match="regiao nula"):
        folds.loro_folds(_cfg(tmp_path), df)


def test_loro_recusa_regiao_fora_da_ordem(tmp_path):
    df = _df()
    df.loc[3, "regiao"] = "Brasil"
    with pytest.raises(ValueError, match="ordem_dobras"):
        folds.loro_folds(_cfg(tmp_path), df)


def test_build_folds_frame_papeis_e_colunas(tmp_path):
    cfg = _cfg(tmp_path)
    df_folds = folds.build_folds_frame(cfg, _df())
    assert df_folds["ANO"].dtype == np.int64
    assert df_folds["id"].iloc[0] == f"{df_folds['ANO'].iloc[0]}-{df_folds['LINHA'].iloc[0]}"
    for regiao in ORDEM:
        papel = df_folds[f"papel_{regiao}"]
        # Para a dobra de cada região: a própria região é validação; as outras, ajuste/parada.
        assert set(papel[df_folds["dobra"] == regiao]) == {"validacao"}
        assert set(papel[df_folds["dobra"] != regiao]) == {"ajuste", "parada"}


def test_hash_nao_depende_da_ordem_das_linhas(tmp_path):
    df_folds = folds.build_folds_frame(_cfg(tmp_path), _df())
    embaralhado = df_folds.sample(frac=1, random_state=5)
    assert folds.folds_hash(embaralhado) == folds.folds_hash(df_folds)


def test_hash_muda_quando_uma_linha_troca_de_dobra(tmp_path):
    df_folds = folds.build_folds_frame(_cfg(tmp_path), _df())
    alterado = df_folds.copy()
    alterado.loc[0, "dobra"] = "Norte" if alterado.loc[0, "dobra"] != "Norte" else "Sul"
    assert folds.folds_hash(alterado) != folds.folds_hash(df_folds)


def test_mesma_semente_mesmo_hash_em_duas_execucoes(tmp_path):
    cfg = _cfg(tmp_path)
    df = _df()
    h1 = folds.save_folds(cfg, df, tmp_path / "a.parquet")
    h2 = folds.save_folds(cfg, df, tmp_path / "b.parquet")
    assert h1 == h2


def test_load_folds_confere_o_hash(tmp_path):
    cfg = _cfg(tmp_path)
    caminho = tmp_path / "dobras.parquet"
    h = folds.save_folds(cfg, _df(), caminho)
    lido = folds.load_folds(caminho, h)
    assert len(lido) == 5 * 200
    with pytest.raises(ValueError, match="hash das dobras"):
        folds.load_folds(caminho, "0" * 64)


def test_save_folds_recusa_ano_de_teste(tmp_path):
    df = _df()
    df.loc[0, "ANO"] = 2024
    with pytest.raises(RuntimeError, match="teste congelado"):
        folds.save_folds(_cfg(tmp_path), df, tmp_path / "x.parquet")
    assert not (tmp_path / "x.parquet").exists()


def test_hash_recusa_id_de_caso_repetido(tmp_path):
    df_folds = folds.build_folds_frame(_cfg(tmp_path), _df())
    df_folds.loc[1, ["ANO", "LINHA"]] = df_folds.loc[0, ["ANO", "LINHA"]].to_numpy()
    with pytest.raises(ValueError, match="repetido"):
        folds.folds_hash(df_folds)
