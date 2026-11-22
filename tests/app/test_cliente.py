"""Cliente HTTP: toda falha de transporte vira ApiIndisponivel; erro da API vira ApiErro."""

import pytest
import requests

from app.cliente import ApiErro, ApiIndisponivel, ClienteAPI


class Resp:
    def __init__(self, status=200, corpo=None, texto_json=True):
        self.status_code = status
        self._corpo = corpo
        self._json = texto_json

    def json(self):
        if not self._json:
            raise ValueError("não é JSON")
        return self._corpo


class Sessao:
    def __init__(self, resp=None, erro=None):
        self.resp, self.erro = resp, erro

    def request(self, *a, **k):
        if self.erro:
            raise self.erro
        return self.resp


@pytest.mark.parametrize(
    "erro",
    [
        requests.ConnectionError("x"),
        requests.Timeout("x"),
        requests.exceptions.ChunkedEncodingError("x"),
        requests.exceptions.InvalidURL("x"),
        requests.exceptions.SSLError("x"),
    ],
)
def test_falha_de_transporte_vira_indisponivel(erro):
    with pytest.raises(ApiIndisponivel):
        ClienteAPI("http://x", sessao=Sessao(erro=erro)).saude()


def test_erro_http_com_detalhes():
    corpo = {"detail": [{"indice": 0, "campo": "idade_anos", "motivo": "tipo"}]}
    with pytest.raises(ApiErro) as e:
        ClienteAPI("http://x", sessao=Sessao(Resp(422, corpo))).prever([{}])
    assert e.value.status == 422 and e.value.itens == ["registro 1: idade_anos: tipo"]


def test_corpo_nao_json_e_formato_inesperado():
    with pytest.raises(ApiErro):
        ClienteAPI("http://x", sessao=Sessao(Resp(200, texto_json=False))).versao()
    with pytest.raises(ApiErro):
        ClienteAPI("http://x", sessao=Sessao(Resp(200, [1, 2]))).versao()
    with pytest.raises(ApiErro):
        ClienteAPI("http://x", sessao=Sessao(Resp(500, texto_json=False))).versao()


def test_sucesso():
    assert ClienteAPI("http://x/", sessao=Sessao(Resp(200, {"a": 1}))).saude() == {"a": 1}
