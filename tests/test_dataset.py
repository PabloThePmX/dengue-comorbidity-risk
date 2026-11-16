from pathlib import Path

import pandas as pd
import pytest
from populacao_sintetica import cfg_sintetico, dados_sinteticos, gravar, linha

from dengue_sinan import dataset as ds


@pytest.fixture
def cfg(tmp_path) -> dict:
    return cfg_sintetico(tmp_path)


@pytest.fixture
def dados(cfg) -> dict:
    return dados_sinteticos(cfg)


def test_load_population_conta_populacao_eventos_e_colunas(dados):
    pop = ds.load_population(dados, [2022, 2023])
    assert len(pop) == 5
    assert pop["y"].sum() == 2
    assert pop["ANO"].tolist() == [2022, 2022, 2022, 2022, 2023]
    for coluna in ("idade_anos", "faixa_etaria", "regiao", "gestante"):
        assert coluna in pop
    assert set(pop["regiao"]) == {"Sudeste"}


def test_load_population_grava_fluxograma_com_etapas(dados):
    # Com 7 linhas sintéticas, tudo ficaria suprimido (<10): baixa o limite só para ler os números.
    dados["supressao_min_celula"] = 1
    ds.load_population(dados, [2022, 2023])
    conteudo = Path(dados["caminhos"]["relatorios"], "fluxograma.md").read_text(encoding="utf-8")
    # 2022: 7 → 6 (CLASSI) → 5 (rótulo) → 4 (idade); 2023: 1 em todas as etapas.
    assert "| 1. Total baixado | 7 | 1 |" in conteudo
    assert "| 2. CLASSI_FIN ∈ {10, 11, 12} | 6 | 1 |" in conteudo
    assert "| 3. Rótulo conhecido (12, ou 10/11 com EVOLUCAO ∈ {1, 2}) | 5 | 1 |" in conteudo
    assert "| 4. Idade válida (0–120 anos) | 4 | 1 |" in conteudo


def test_fluxograma_suprime_celula_menor_que_10(dados):
    ds.load_population(dados, [2022, 2023])
    conteudo = Path(dados["caminhos"]["relatorios"], "fluxograma.md").read_text(encoding="utf-8")
    # CLASSI_FIN = 8 tem 1 caso em 2022 (sai no filtro 2): a célula vira "<10" (R7).
    assert "| 8 | <10 | 0 |" in conteudo
    # A nota sobre dedução por subtração (limitação aceita) fica no cabeçalho.
    assert "deduzida por subtração" in conteudo
    # R7: nenhuma célula publicada pode ser contagem de 1 a 9.
    assert _celulas_de_1_a_9(conteudo) == []


def _celulas_de_1_a_9(conteudo: str) -> list[str]:
    achados = []
    for linha_md in conteudo.splitlines():
        if not linha_md.startswith("|"):
            continue
        # A primeira célula é o rótulo (etapa ou código), não uma contagem.
        for celula in linha_md.strip("|").split("|")[1:]:
            numero = celula.strip().replace(" ", "")
            if numero.isdigit() and 1 <= int(numero) <= 9:
                achados.append(celula.strip())
    return achados


def test_load_population_recusa_2024_antes_de_abrir_arquivo(cfg):
    # Nenhum arquivo de 2024 existe aqui: se o código tentasse ler, falharia com outro erro.
    with pytest.raises(RuntimeError, match="2024 é teste congelado"):
        ds.load_population(cfg, [2022, 2024])


@pytest.mark.parametrize("anos", [[], [2022, 2022]])
def test_load_population_exige_lista_de_anos_valida(cfg, anos):
    with pytest.raises(ValueError):
        ds.load_population(cfg, anos)


def test_load_population_falha_com_coluna_faltando(cfg):
    colunas = [c for c in ds.POPULATION_COLUMNS if c != "DIABETES"]
    gravar(cfg, 2022, [linha()], colunas=colunas)
    with pytest.raises(ValueError, match="DIABETES"):
        ds.load_population(cfg, [2022])


def test_load_population_falha_com_classi_fin_fora_do_dominio(cfg):
    gravar(cfg, 2022, [linha(CLASSI_FIN="1")])
    with pytest.raises(ValueError, match="CLASSI_FIN"):
        ds.load_population(cfg, [2022])


def test_build_feature_frame_niveis_e_contagens():
    df = pd.DataFrame([
        linha(CS_SEXO="M", DIABETES="1", HIPERTENSA="1", FEBRE="9"),
        linha(CS_SEXO="X", DT_SIN_PRI="20220101", DT_NOTIFIC="20220401"),  # 90 dias
        linha(DT_SIN_PRI="20220110", DT_NOTIFIC="20220101"),               # −9 dias
    ])
    df["gestante"] = [False, True, False]
    out = ds.build_feature_frame(df)
    assert out["sexo"].tolist() == ["M", "I", "F"]
    assert out["n_comorbidades"].tolist() == [2, 0, 0]
    assert out["dias_ate_notificacao"].tolist() == [2, 60, 0]
    assert out["DIABETES"].tolist() == ["Sim", "Não", "Não"]
    assert out["FEBRE"].iloc[0] == "Ausente"  # "9" fora do domínio = Ausente (D-07)
    assert out["gestante"].dtype == "int8"
    assert out["gestante"].tolist() == [0, 1, 0]


def test_load_population_traz_ano_inteiro_e_linha_do_arquivo(dados):
    # LINHA é a posição no Parquet do ano (0-based, antes dos filtros): id das dobras (T-2.3).
    pop = ds.load_population(dados, [2022, 2023])
    assert pop["ANO"].dtype.kind == "i"
    assert pop.loc[pop["ANO"] == 2022, "LINHA"].is_unique
    assert set(pop.loc[pop["ANO"] == 2022, "LINHA"]) <= set(range(7))
    assert set(pop.loc[pop["ANO"] == 2023, "LINHA"]) <= set(range(1))
