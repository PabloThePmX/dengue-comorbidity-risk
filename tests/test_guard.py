import pandas as pd
import pytest

from dengue_sinan import guard


def test_passa_com_anos_de_desenvolvimento():
    df = pd.DataFrame({"ANO": [2022, 2022, 2023], "y": [0, 1, 0]})
    guard.assert_dev_only(df)  # não levanta


def test_falha_com_uma_linha_de_2024():
    df = pd.DataFrame({"ANO": [2022, 2023, 2024], "y": [0, 0, 1]})
    with pytest.raises(RuntimeError, match="2024 é teste congelado"):
        guard.assert_dev_only(df)


def test_falha_com_coluna_ano_categorica():
    df = pd.DataFrame({"ANO": pd.Categorical([2023, 2024])})
    with pytest.raises(RuntimeError, match="2024 é teste congelado"):
        guard.assert_dev_only(df)


def test_le_o_ano_de_teste_do_config(monkeypatch):
    # Se o ano de teste mudar no config, a guarda segue o config, não um 2024 fixo no código.
    monkeypatch.setattr(guard, "load_config", lambda: {"ano_teste": 2030})
    guard.assert_dev_only(pd.DataFrame({"ANO": [2024]}))  # 2024 agora é desenvolvimento
    with pytest.raises(RuntimeError, match="2030 é teste congelado"):
        guard.assert_dev_only(pd.DataFrame({"ANO": [2030]}))


def test_falha_sem_coluna_ano():
    with pytest.raises(ValueError, match="sem coluna ANO"):
        guard.assert_dev_only(pd.DataFrame({"y": [0, 1]}))


def test_leitura_do_teste_aceita_so_2024():
    df = pd.DataFrame({"ANO": [2024, 2024]})
    with guard.leitura_do_teste():
        guard.assert_dev_only(df)  # não levanta: só o ano de teste


def test_leitura_do_teste_recusa_2022_e_mistura():
    with guard.leitura_do_teste():
        with pytest.raises(RuntimeError, match="só entram linhas de 2024"):
            guard.assert_dev_only(pd.DataFrame({"ANO": [2022]}))
        with pytest.raises(RuntimeError, match="só entram linhas de 2024"):
            guard.assert_dev_only(pd.DataFrame({"ANO": [2023, 2024]}))


def test_leitura_do_teste_restaura_o_estado_mesmo_com_erro():
    with pytest.raises(ZeroDivisionError):
        with guard.leitura_do_teste():
            raise ZeroDivisionError
    with pytest.raises(RuntimeError, match="2024 é teste congelado"):
        guard.assert_dev_only(pd.DataFrame({"ANO": [2024]}))


def test_ano_aceito_no_bloco_vem_do_config_e_nao_de_2024_fixo(monkeypatch):
    # Com outro ano de teste no config, o bloco aceita esse ano (não 2024) e recusa 2024.
    monkeypatch.setattr(guard, "load_config", lambda: {"ano_teste": 2030})
    with guard.leitura_do_teste():
        guard.assert_dev_only(pd.DataFrame({"ANO": [2030, 2030]}))
        with pytest.raises(RuntimeError, match="só entram linhas de 2030"):
            guard.assert_dev_only(pd.DataFrame({"ANO": [2024]}))


def test_bloco_aninhado_nao_fecha_o_externo_antes_da_hora():
    with guard.leitura_do_teste():
        with guard.leitura_do_teste():
            pass
        # saiu do bloco interno: o externo ainda está aberto
        guard.assert_dev_only(pd.DataFrame({"ANO": [2024]}))
    with pytest.raises(RuntimeError, match="2024 é teste congelado"):
        guard.assert_dev_only(pd.DataFrame({"ANO": [2024]}))


def test_bloco_interno_com_erro_nao_deixa_a_guarda_aberta_nem_fecha_o_externo():
    with guard.leitura_do_teste():
        with pytest.raises(ZeroDivisionError):
            with guard.leitura_do_teste():
                raise ZeroDivisionError
        guard.assert_dev_only(pd.DataFrame({"ANO": [2024]}))  # externo continua aberto
    with pytest.raises(RuntimeError):
        guard.assert_dev_only(pd.DataFrame({"ANO": [2024]}))


def test_dataframe_vazio_dentro_do_bloco_e_recusado():
    vazio = pd.DataFrame({"ANO": pd.Series([], dtype="int64")})
    with guard.leitura_do_teste(), pytest.raises(RuntimeError, match="vazio é recusado"):
        guard.assert_dev_only(vazio)


def test_dataframe_vazio_fora_do_bloco_continua_passando():
    # Regra antiga, fora do bloco: nada do ano de teste, então passa.
    guard.assert_dev_only(pd.DataFrame({"ANO": pd.Series([], dtype="int64")}))


def test_porta_e_por_thread_outra_thread_com_a_porta_fechada_recusa_2024():
    import threading

    resultado = {}

    def outra_thread():
        resultado["aberta"] = guard.leitura_do_teste_aberta()
        try:
            guard.assert_dev_only(pd.DataFrame({"ANO": [2024]}))
        except RuntimeError as e:
            resultado["erro"] = str(e)

    with guard.leitura_do_teste():
        assert guard.leitura_do_teste_aberta()
        guard.assert_dev_only(pd.DataFrame({"ANO": [2024]}))  # esta thread: porta aberta
        fio = threading.Thread(target=outra_thread)
        fio.start()
        fio.join()
    assert resultado["aberta"] is False
    assert "2024 é teste congelado" in resultado["erro"]
    assert not guard.leitura_do_teste_aberta()


def test_porta_aberta_em_outra_thread_nao_abre_esta():
    import threading

    aberta, fechar = threading.Event(), threading.Event()

    def segura_a_porta():
        with guard.leitura_do_teste():
            aberta.set()
            fechar.wait(timeout=10)

    fio = threading.Thread(target=segura_a_porta)
    fio.start()
    assert aberta.wait(timeout=10)
    try:
        with pytest.raises(RuntimeError, match="2024 é teste congelado"):
            guard.assert_dev_only(pd.DataFrame({"ANO": [2024]}))
    finally:
        fechar.set()
        fio.join()


# --- Ano de comparação (D-97): 2025, segunda porta, mesma disciplina do teste --------------------

CFG_COMPARACAO = {"ano_teste": 2024, "ano_comparacao": 2025}


@pytest.fixture
def com_comparacao(monkeypatch):
    monkeypatch.setattr(guard, "load_config", lambda: CFG_COMPARACAO)


def test_ano_de_comparacao_e_recusado_no_desenvolvimento(com_comparacao):
    with pytest.raises(RuntimeError, match="2025 é ano de comparação congelado"):
        guard.assert_dev_only(pd.DataFrame({"ANO": [2022, 2025]}))
    with pytest.raises(RuntimeError, match="2024 é teste congelado"):  # o teste segue igual
        guard.assert_dev_only(pd.DataFrame({"ANO": [2024]}))
    guard.assert_dev_only(pd.DataFrame({"ANO": [2022, 2023]}))


def test_sem_ano_de_comparacao_no_config_nada_muda(monkeypatch):
    monkeypatch.setattr(guard, "load_config", lambda: {"ano_teste": 2024})
    guard.assert_dev_only(pd.DataFrame({"ANO": [2025]}))  # sem a chave, 2025 não é tratado


def test_porta_de_comparacao_aceita_so_2025(com_comparacao):
    with guard.leitura_do_ano_de_comparacao():
        assert guard.leitura_da_comparacao_aberta()
        guard.assert_dev_only(pd.DataFrame({"ANO": [2025, 2025]}))
        for anos in ([2022], [2024], [2023, 2025], [2024, 2025]):
            with pytest.raises(RuntimeError, match="só entram linhas de 2025"):
                guard.assert_dev_only(pd.DataFrame({"ANO": anos}))
    assert not guard.leitura_da_comparacao_aberta()


def test_porta_de_comparacao_recusa_dataframe_vazio(com_comparacao):
    vazio = pd.DataFrame({"ANO": pd.Series([], dtype="int64")})
    with guard.leitura_do_ano_de_comparacao(), pytest.raises(RuntimeError, match="vazio"):
        guard.assert_dev_only(vazio)


def test_porta_de_comparacao_sem_ano_no_config_recusa(monkeypatch):
    monkeypatch.setattr(guard, "load_config", lambda: {"ano_teste": 2024})
    with guard.leitura_do_ano_de_comparacao(), pytest.raises(RuntimeError, match="ano_comparacao"):
        guard.assert_dev_only(pd.DataFrame({"ANO": [2025]}))


def test_porta_do_teste_nao_libera_2025(com_comparacao):
    with guard.leitura_do_teste():
        guard.assert_dev_only(pd.DataFrame({"ANO": [2024]}))
        with pytest.raises(RuntimeError, match="só entram linhas de 2024"):
            guard.assert_dev_only(pd.DataFrame({"ANO": [2025]}))


def test_as_duas_portas_abertas_juntas_sao_recusadas(com_comparacao):
    with guard.leitura_do_teste(), guard.leitura_do_ano_de_comparacao():
        with pytest.raises(RuntimeError, match="as duas portas"):
            guard.assert_dev_only(pd.DataFrame({"ANO": [2025]}))


def test_porta_de_comparacao_restaura_o_estado_e_e_aninhavel(com_comparacao):
    with pytest.raises(ZeroDivisionError):
        with guard.leitura_do_ano_de_comparacao():
            raise ZeroDivisionError
    assert not guard.leitura_da_comparacao_aberta()
    with guard.leitura_do_ano_de_comparacao():
        with guard.leitura_do_ano_de_comparacao():
            pass
        assert guard.leitura_da_comparacao_aberta()  # o externo continua aberto
    with pytest.raises(RuntimeError, match="2025 é ano de comparação congelado"):
        guard.assert_dev_only(pd.DataFrame({"ANO": [2025]}))


def test_porta_de_comparacao_e_por_thread(com_comparacao):
    import threading

    resultado = {}

    def outra_thread():
        resultado["aberta"] = guard.leitura_da_comparacao_aberta()
        try:
            guard.assert_dev_only(pd.DataFrame({"ANO": [2025]}))
        except RuntimeError as e:
            resultado["erro"] = str(e)

    with guard.leitura_do_ano_de_comparacao():
        fio = threading.Thread(target=outra_thread)
        fio.start()
        fio.join()
    assert resultado["aberta"] is False
    assert "2025 é ano de comparação congelado" in resultado["erro"]
