import copy
from pathlib import Path

import optuna
import pytest

from dengue_sinan.config import load_config
from dengue_sinan.search_space import (
    PROIBIDOS_R3,
    EspacoModelo,
    _textos,
    load_search_space,
    sugerir,
)

BASE = Path(__file__).resolve().parents[1] / "config" / "base.yaml"


@pytest.fixture(scope="module")
def cfg():
    return load_config(BASE)


@pytest.fixture(scope="module")
def espacos(cfg):
    return load_search_space(cfg)


def test_carrega_espaco_do_config_na_ordem_dos_modelos(cfg, espacos):
    assert list(espacos) == cfg["ordem_modelos"]
    assert all(isinstance(e, EspacoModelo) for e in espacos.values())


def test_cada_modelo_tem_entrada_e_tabfm_nao_tem_busca(cfg):
    # D-91: o TabFM saiu da sessão do M1 (sem `tabfm` em ordem_modelos nem em busca).
    busca = cfg["busca"]
    assert cfg["ordem_modelos"] == ["elastic_net", "xgboost", "catboost", "mlp", "random_forest"]
    assert set(busca) == set(cfg["ordem_modelos"])
    for modelo in cfg["ordem_modelos"]:
        assert busca[modelo]["parametros"], modelo


def test_reativar_tabfm_pelo_config_continua_valido(cfg):
    # D-91, reversibilidade: o que o comentário do config manda fazer (incluir `tabfm` em
    # ordem_modelos e descomentar `busca.tabfm`) produz um espaço válido, com o TabFM sem busca.
    reativado = copy.deepcopy(cfg)
    reativado["ordem_modelos"] = [*cfg["ordem_modelos"], "tabfm"]
    reativado["busca"]["tabfm"] = {"sem_busca": True}
    espacos = load_search_space(reativado)
    assert list(espacos) == reativado["ordem_modelos"]
    assert espacos["tabfm"].sem_busca is True
    assert "tabfm" in cfg["orcamento_teto_min"]
    assert "tabfm" in cfg["optuna"]["max_tentativas"]
    assert "commit_pacote" in cfg["tabfm"]  # o bloco `tabfm:` fica no config


def test_tabfm_sem_entrada_em_busca_recusado_quando_esta_na_ordem(cfg):
    # Guarda contra reativar só num lado: `tabfm` em ordem_modelos sem busca levanta erro.
    ruim = copy.deepcopy(cfg)
    ruim["ordem_modelos"] = [*cfg["ordem_modelos"], "tabfm"]
    with pytest.raises(ValueError, match="tabfm"):
        load_search_space(ruim)


def test_nenhum_parametro_de_peso_de_classe_no_config(cfg):
    # R3: varre nomes e valores de todo o bloco `busca`, não só os nomes esperados.
    for texto in _textos(cfg["busca"]):
        for proibido in PROIBIDOS_R3:
            assert proibido not in texto.lower(), (proibido, texto)


def test_nenhum_parametro_de_peso_de_classe_no_espaco_carregado(espacos):
    nomes = {p.nome for e in espacos.values() for p in e.parametros}
    fixos = {k for e in espacos.values() for k in e.fixos}
    for nome in nomes | fixos:
        for proibido in PROIBIDOS_R3:
            assert proibido not in nome.lower()


def test_faixas_validas(espacos):
    for modelo, espaco in espacos.items():
        for p in espaco.parametros:
            where = (modelo, p.nome)
            if p.tipo == "categorico":
                assert p.valores and len(set(p.valores)) == len(p.valores), where
                continue
            assert p.minimo < p.maximo, where
            if p.escala == "log":
                assert p.minimo > 0, where


def test_tipos_coerentes(espacos):
    for modelo, espaco in espacos.items():
        for p in espaco.parametros:
            where = (modelo, p.nome)
            assert p.tipo in ("float", "int", "categorico"), where
            if p.tipo == "categorico":
                assert p.escala is None and p.minimo is None, where
                continue
            assert p.escala in ("linear", "log"), where
            if p.tipo == "int":
                assert isinstance(p.minimo, int) and isinstance(p.maximo, int), where
                assert not isinstance(p.minimo, bool), where
            else:
                assert isinstance(p.minimo, (int, float)), where
                assert isinstance(p.maximo, (int, float)), where


def test_sugerir_devolve_valores_dentro_das_faixas(espacos):
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    sampler = optuna.samplers.TPESampler(seed=20261103)
    for modelo, espaco in espacos.items():
        if espaco.sem_busca:
            assert sugerir(optuna.trial.FixedTrial({}), espaco) == {}
            continue
        visto = _sorteios(sampler, espaco, n_trials=15)
        assert len(visto) == 15
        for valores in visto:
            assert set(valores) == {p.nome for p in espaco.parametros}, modelo
            for p in espaco.parametros:
                v = valores[p.nome]
                if p.tipo == "categorico":
                    assert v in p.valores, (modelo, p.nome, v)
                else:
                    assert p.minimo <= v <= p.maximo, (modelo, p.nome, v)


def _sorteios(sampler, espaco, n_trials):
    """Roda um estudo em memória e devolve os valores sorteios por `sugerir` em cada tentativa."""
    visto = []

    def objetivo(trial):
        valores = sugerir(trial, espaco)
        visto.append(valores)
        return 0.0

    estudo = optuna.create_study(direction="maximize", sampler=sampler)
    estudo.optimize(objetivo, n_trials=n_trials)
    return visto


def test_sugerir_com_trial_fixo_usa_o_valor_informado(espacos):
    espaco = espacos["xgboost"]
    valores = {p.nome: p.minimo for p in espaco.parametros}
    trial = optuna.trial.FixedTrial(valores)
    assert sugerir(trial, espaco) == valores


# --- O carregador recusa configurações inválidas ---------------------------------------------

def _cfg_com(cfg, editar):
    novo = copy.deepcopy({"busca": cfg["busca"], "ordem_modelos": cfg["ordem_modelos"]})
    editar(novo)
    return novo


def test_recusa_peso_de_classe(cfg):
    ruim = _cfg_com(cfg, lambda c: c["busca"]["xgboost"]["fixos"].update(scale_pos_weight=10))
    with pytest.raises(ValueError, match="R3"):
        load_search_space(ruim)


def test_recusa_peso_de_classe_em_valor(cfg):
    ruim = _cfg_com(cfg, lambda c: c["busca"]["mlp"]["fixos"].update(perda="pos_weight"))
    with pytest.raises(ValueError, match="R3"):
        load_search_space(ruim)


def test_recusa_faixa_com_min_maior_que_max(cfg):
    def editar(c):
        c["busca"]["xgboost"]["parametros"]["max_depth"]["min"] = 9
    with pytest.raises(ValueError, match="max_depth"):
        load_search_space(_cfg_com(cfg, editar))


def test_recusa_log_com_min_zero(cfg):
    def editar(c):
        c["busca"]["elastic_net"]["parametros"]["C"]["min"] = 0.0
    with pytest.raises(ValueError, match="log exige"):
        load_search_space(_cfg_com(cfg, editar))


def test_recusa_escala_em_notacao_cientifica_sem_ponto(cfg):
    # YAML lê 1e-3 como texto: o carregador tem de recusar, não aceitar em silêncio.
    def editar(c):
        c["busca"]["elastic_net"]["parametros"]["C"]["min"] = "1e-3"
    with pytest.raises(ValueError, match="números"):
        load_search_space(_cfg_com(cfg, editar))


def test_recusa_modelo_sem_entrada(cfg):
    def editar(c):
        del c["busca"]["catboost"]
    with pytest.raises(ValueError, match="catboost"):
        load_search_space(_cfg_com(cfg, editar))


def test_recusa_entrada_sem_modelo_correspondente(cfg):
    def editar(c):
        c["busca"]["lightgbm"] = {"sem_busca": True}
    with pytest.raises(ValueError, match="lightgbm"):
        load_search_space(_cfg_com(cfg, editar))


def test_recusa_categorico_com_valores_repetidos(cfg):
    def editar(c):
        c["busca"]["mlp"]["parametros"]["batch_size"]["valores"] = [1024, 1024]
    with pytest.raises(ValueError, match="repetidos"):
        load_search_space(_cfg_com(cfg, editar))


# --- Ponto de partida da busca (T-4.3, decisão do Programador) -------------------------------

PRIMEIRA_RF = {"n_estimators": 200, "max_depth": 8, "min_samples_leaf": 100,
               "max_features": "sqrt", "max_samples": 0.1}


def test_primeira_tentativa_do_config_e_carregada(espacos):
    # RF: ponto conservador do próprio espaço (não o padrão do sklearn, que estoura a RAM).
    assert espacos["random_forest"].primeira_tentativa == PRIMEIRA_RF
    # Biblioteca: elastic net, XGBoost e CatBoost; MLP: ponto médio do espaço.
    assert espacos["elastic_net"].primeira_tentativa == {"C": 1.0, "l1_ratio": 0.5}
    assert espacos["xgboost"].primeira_tentativa == {
        "learning_rate": 0.3, "max_depth": 6, "min_child_weight": 1.0,
        "subsample": 1.0, "colsample_bytree": 1.0, "reg_lambda": 1.0,
    }
    assert espacos["catboost"].primeira_tentativa == {
        "learning_rate": 0.05, "depth": 6, "l2_leaf_reg": 3.0,
    }
    assert espacos["mlp"].primeira_tentativa == {
        "camadas_ocultas": "128", "dropout": 0.15, "weight_decay": 0.0001,
        "lr": 0.001, "batch_size": 1024,
    }
    assert "tabfm" not in espacos  # D-91: fora da sessão (o caso sem busca: teste de reativação)


def test_elastic_net_nao_fixa_penalty_deprecado(espacos):
    # penalty está deprecado no sklearn 1.9: o elastic net é definido por l1_ratio (T-4.6b).
    assert espacos["elastic_net"].fixos == {"solver": "saga", "max_iter": 500}


def test_primeira_tentativa_nao_tem_peso_de_classe(cfg):
    for modelo, entrada in cfg["busca"].items():
        for texto in _textos(entrada.get("primeira_tentativa", {})):
            for proibido in PROIBIDOS_R3:
                assert proibido not in texto.lower(), (modelo, texto)


def test_primeira_tentativa_esta_dentro_das_faixas(espacos):
    for modelo, espaco in espacos.items():
        if espaco.sem_busca:
            continue
        assert set(espaco.primeira_tentativa) == {p.nome for p in espaco.parametros}, modelo
        for p in espaco.parametros:
            v = espaco.primeira_tentativa[p.nome]
            if p.tipo == "categorico":
                assert v in p.valores, (modelo, p.nome)
            else:
                assert p.minimo <= v <= p.maximo, (modelo, p.nome, v)


def test_recusa_modelo_sem_primeira_tentativa(cfg):
    def editar(c):
        del c["busca"]["random_forest"]["primeira_tentativa"]
    with pytest.raises(ValueError, match="falta o ponto de partida"):
        load_search_space(_cfg_com(cfg, editar))


def test_recusa_primeira_tentativa_com_parametro_sobrando(cfg):
    def editar(c):
        c["busca"]["xgboost"]["primeira_tentativa"]["penalidade"] = 1
    with pytest.raises(ValueError, match="buscados"):
        load_search_space(_cfg_com(cfg, editar))


def test_recusa_primeira_tentativa_faltando_parametro(cfg):
    def editar(c):
        del c["busca"]["catboost"]["primeira_tentativa"]["depth"]
    with pytest.raises(ValueError, match="buscados"):
        load_search_space(_cfg_com(cfg, editar))


def test_recusa_primeira_tentativa_fora_da_faixa(cfg):
    def editar(c):
        c["busca"]["random_forest"]["primeira_tentativa"]["n_estimators"] = 1000
    with pytest.raises(ValueError, match="fora de"):
        load_search_space(_cfg_com(cfg, editar))


def test_recusa_primeira_tentativa_com_inteiro_fracionario(cfg):
    def editar(c):
        c["busca"]["xgboost"]["primeira_tentativa"]["max_depth"] = 6.5
    with pytest.raises(ValueError, match="inteiro"):
        load_search_space(_cfg_com(cfg, editar))


def test_recusa_primeira_tentativa_categorica_fora_dos_valores(cfg):
    def editar(c):
        c["busca"]["random_forest"]["primeira_tentativa"]["max_features"] = "log2"
    with pytest.raises(ValueError, match="fora de"):
        load_search_space(_cfg_com(cfg, editar))


def test_recusa_primeira_tentativa_com_peso_de_classe(cfg):
    # o nome do parâmetro não é buscado, então a recusa vem de R3 (varredura do bloco busca)
    def editar(c):
        c["busca"]["xgboost"]["primeira_tentativa"]["class_weight"] = 1
    with pytest.raises(ValueError, match="R3"):
        load_search_space(_cfg_com(cfg, editar))
