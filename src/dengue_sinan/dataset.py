"""Carrega a população em memória (T-2.1): lê só as colunas necessárias dos Parquets por ano.

Ordem por ano: checks bloqueantes e alertas → fluxograma (FR-02) → população (D-45) → derivadas.
Recebe a lista de anos explicitamente (R1): quem chama escolhe os anos.
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from dengue_sinan import checks, guard
from dengue_sinan.profiling import (
    COMORBIDADES,
    SINAIS,
    add_derived,
    code,
    exclusion_flow,
    exclusion_reasons,
    markdown_table,
    parse_date,
    population_mask,
)

logger = logging.getLogger(__name__)

# Colunas lidas do Parquet: as do dicionário de features (data-model) mais as usadas para alvo,
# população, idade, região e alertas. DT_NASC não existe nos públicos (só ANO_NASC).
POPULATION_COLUMNS = [
    "CLASSI_FIN", "EVOLUCAO", "NU_IDADE_N", "ANO_NASC", "DT_SIN_PRI", "DT_NOTIFIC",
    "CS_SEXO", "CS_GESTANT", "CS_RACA", "ID_MN_RESI", "SG_UF",
    *COMORBIDADES, *SINAIS,
]


def parquet_path(cfg: dict, ano: int) -> Path:
    """Caminho do Parquet de um ano (ex.: data/parquet/dengue_2022.parquet)."""
    return Path(cfg["caminhos"]["dados"]) / "parquet" / f"dengue_{ano}.parquet"


def _validar_anos(cfg: dict, anos: list[int], teste: bool = False,
                  comparacao: bool = False) -> None:
    if teste and comparacao:
        raise ValueError("teste e comparacao não podem ser pedidos juntos (R1, D-97)")
    if not anos:
        raise ValueError("anos vazio: informe os anos explicitamente")
    if len(set(anos)) != len(anos):
        raise ValueError(f"anos repetidos: {anos}")
    # R1: o ano de teste não pode entrar em nenhuma carga de desenvolvimento.
    # Validado antes de abrir qualquer arquivo. A única exceção é a avaliação final (teste=True),
    # que aceita só o ano de teste: 2022–23 continua recusado nesse caminho.
    if teste:
        if not guard.leitura_do_teste_aberta():
            raise RuntimeError("teste=True só funciona dentro de guard.leitura_do_teste() "
                               "(R1, R2): "
                               "a porta do teste está fechada")
        if list(anos) != [cfg["ano_teste"]]:
            raise RuntimeError(f"teste=True só carrega o ano de teste ({cfg['ano_teste']}) "
                               f"(R1): recebi {anos}")
        return
    if comparacao:
        if not guard.leitura_da_comparacao_aberta():
            raise RuntimeError("comparacao=True só funciona dentro de "
                               "guard.leitura_do_ano_de_comparacao() (R1, R2, D-97): "
                               "a porta da comparação está fechada")
        ano = cfg.get("ano_comparacao")
        if ano is None:
            raise RuntimeError("comparacao=True sem `ano_comparacao` no config (R1, D-97)")
        if list(anos) != [ano]:
            raise RuntimeError(f"comparacao=True só carrega o ano de comparação ({ano}) "
                               f"(R1, D-97): recebi {anos}")
        return
    if cfg["ano_teste"] in anos:
        raise RuntimeError(f"{cfg['ano_teste']} é teste congelado (R1)")
    ano_comparacao = cfg.get("ano_comparacao")
    if ano_comparacao is not None and ano_comparacao in anos:
        raise RuntimeError(f"{ano_comparacao} é ano de comparação congelado (R1, D-97)")


def _ler_ano(cfg: dict, ano: int) -> pd.DataFrame:
    """Lê as colunas necessárias de um ano e acrescenta ANO (ano do arquivo, D-46).

    LINHA é o nº da linha no Parquet do ano (0-based, antes de qualquer filtro): com ANO,
    identifica o caso para as dobras (T-2.3).
    """
    caminho = parquet_path(cfg, ano)
    checks.check_columns(pq.read_schema(caminho).names, POPULATION_COLUMNS, ano)
    df = pq.read_table(caminho, columns=POPULATION_COLUMNS).to_pandas(
        strings_to_categorical=True)
    df["ANO"] = np.int64(ano)
    df["LINHA"] = np.arange(len(df), dtype="int64")
    return df


def load_population_with_flow(
    cfg: dict, anos: list[int], *, teste: bool = False, comparacao: bool = False
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    """Carrega a população e devolve também o fluxograma e os motivos de exclusão.

    Devolve (população com derivadas, fluxograma por ano, motivos por ano). Os fluxogramas são
    contados antes do filtro de população, linha a linha, como em profiling.exclusion_flow.
    `teste=True` é o único caminho que aceita o ano de teste, e só ele; `comparacao=True`, o único
    que aceita o ano de comparação (ver `_validar_anos`).
    """
    _validar_anos(cfg, anos, teste, comparacao)
    populacoes, fluxos = [], []
    motivos: dict[str, list[pd.DataFrame]] = {}
    for ano in anos:
        bruto = _ler_ano(cfg, ano)
        checks.check_domains(bruto)
        for alerta in checks.quality_alerts(bruto):
            logger.warning("alerta FR-03 (%s): %s", ano, alerta)
        fluxos.append(exclusion_flow(bruto))
        for nome, tabela in exclusion_reasons(bruto).items():
            motivos.setdefault(nome, []).append(tabela)
        populacoes.append(bruto[population_mask(bruto)])
        del bruto
    flow = pd.concat(fluxos, axis=1).reindex(columns=anos)
    # Um ano sem nenhum caso no motivo deixa a tabela sem a coluna: alinha aos anos pedidos.
    reasons = {
        nome: pd.concat(tabelas, axis=1).reindex(columns=anos).fillna(0).astype(int)
        for nome, tabelas in motivos.items()
    }
    populacao = add_derived(pd.concat(populacoes, ignore_index=True))
    return populacao, flow, reasons


def load_population(cfg: dict, anos: list[int], *, teste: bool = False,
                    comparacao: bool = False) -> pd.DataFrame:
    """População (D-45) dos anos pedidos, com y, idade, faixa, região e gestante.

    Também grava o fluxograma em `reports/fluxograma.md` (FR-02). Com `teste=True` (só o ano de
    teste, T-5.1), não grava nada: a avaliação final só grava ao terminar (D-93). O mesmo vale
    para `comparacao=True` (só o ano de comparação, dentro da porta própria, D-97).
    """
    populacao, flow, reasons = load_population_with_flow(
        cfg, anos, teste=teste, comparacao=comparacao)
    if not teste and not comparacao:
        write_fluxograma(cfg, flow, reasons)
    return populacao


def _suprimir(tabela: pd.DataFrame, minimo: int) -> pd.DataFrame:
    """Células com 0 < n < minimo viram '<minimo' (R7)."""
    return tabela.astype(object).mask((tabela > 0) & (tabela < minimo), f"<{minimo}")


def write_fluxograma(cfg: dict, flow: pd.DataFrame, reasons: dict[str, pd.DataFrame]) -> Path:
    """Grava reports/fluxograma.md; células abaixo de supressao_min_celula são suprimidas."""
    minimo = cfg["supressao_min_celula"]
    flow = flow.copy()
    flow.index.name = "etapa"
    partes = [
        "# Fluxograma de exclusão (FR-02)",
        "",
        "Contagem de linhas após cada filtro, por ano do arquivo. Células com menos de "
        f"{minimo} casos são suprimidas (R7).",
        "",
        f"Nota: células com menos de {minimo} casos aparecem como \"<{minimo}\" (R7). A supressão "
        "é simples: como os totais de cada filtro são publicados, a célula suprimida pode ser "
        "deduzida por subtração (total do filtro menos as demais células). É uma limitação "
        "conhecida e aceita para agregados de dados abertos. Nenhuma contagem de 1 a 9 é "
        "publicada.",
        "",
        markdown_table(_suprimir(flow, minimo), decimals=0),
    ]
    for nome, tabela in reasons.items():
        partes += ["", f"**{nome}**", "", markdown_table(_suprimir(tabela, minimo), decimals=0)]
    caminho = Path(cfg["caminhos"]["relatorios"]) / "fluxograma.md"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text("\n".join(partes) + "\n", encoding="utf-8")
    return caminho


def _tres_niveis(serie: pd.Series) -> pd.Series:
    """Sim (1) / Não (2) / Ausente (branco ou fora do domínio), D-07."""
    valores = code(serie).fillna("")
    niveis = np.where(valores == "1", "Sim", np.where(valores == "2", "Não", "Ausente"))
    return pd.Series(niveis, index=serie.index).astype(
        pd.CategoricalDtype(["Sim", "Não", "Ausente"]))


def build_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Colunas finais do dicionário de features (data-model › Dicionário de features).

    Devolve uma cópia com: sexo (M/F/I), gestante 0/1, n_comorbidades (0–7),
    dias_ate_notificacao truncado em [0, 60], e as comorbidades e sintomas em 3 níveis.
    """
    out = df.copy()
    sexo = code(out["CS_SEXO"]).fillna("")
    out["sexo"] = sexo.where(sexo.isin(["M", "F"]), "I")
    out["gestante"] = out["gestante"].astype("int8")
    out["n_comorbidades"] = sum(
        (code(out[c]).fillna("") == "1").astype("int8") for c in COMORBIDADES)
    dias = (parse_date(out["DT_NOTIFIC"]) - parse_date(out["DT_SIN_PRI"])).dt.days
    out["dias_ate_notificacao"] = dias.clip(lower=0, upper=60)
    for campo in [*COMORBIDADES, *SINAIS]:
        out[campo] = _tres_niveis(out[campo])
    return out
