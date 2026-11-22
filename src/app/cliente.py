"""Cliente HTTP da API, usado pelo frontend. Só traduz chamadas e erros; não valida regras."""

import requests


class ApiIndisponivel(RuntimeError):
    """Não foi possível falar com a API (fora do ar, recusou conexão, demorou ou cortou)."""


class ApiErro(RuntimeError):
    """A API respondeu com erro. `status` é o código HTTP; `itens` traz os detalhes."""

    def __init__(self, status: int, itens: list[str]):
        self.status = status
        self.itens = itens
        super().__init__(f"API respondeu {status}: " + "; ".join(itens))


def _detalhes(resp: requests.Response) -> list[str]:
    try:
        d = resp.json().get("detail")
    except (ValueError, AttributeError):
        return [f"resposta sem detalhe (HTTP {resp.status_code})"]
    if isinstance(d, str):
        return [d]
    if isinstance(d, list):
        out = []
        for item in d:
            if isinstance(item, dict):
                onde = f"registro {item['indice'] + 1}: " if item.get("indice") is not None else ""
                out.append(f"{onde}{item.get('campo', '?')}: {item.get('motivo', '?')}")
            else:
                out.append(str(item))
        return out
    return [f"resposta inesperada (HTTP {resp.status_code})"]


class ClienteAPI:
    def __init__(
        self, base_url: str, timeout_s: float = 5.0, sessao: requests.Session | None = None
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self._sessao = sessao or requests.Session()

    def _chamar(self, metodo: str, caminho: str, **kw) -> dict:
        try:
            resp = self._sessao.request(
                metodo, f"{self.base_url}{caminho}", timeout=self.timeout_s, **kw
            )
        except requests.RequestException as e:  # conexão, timeout, TLS, corte no meio, URL ruim
            raise ApiIndisponivel(f"sem resposta de {self.base_url} ({type(e).__name__})") from e
        if resp.status_code >= 400:
            raise ApiErro(resp.status_code, _detalhes(resp))
        try:
            corpo = resp.json()
        except ValueError as e:
            raise ApiErro(resp.status_code, ["a API devolveu um corpo que não é JSON"]) from e
        if not isinstance(corpo, dict):
            raise ApiErro(resp.status_code, ["a API devolveu um JSON de formato inesperado"])
        return corpo

    def saude(self) -> dict:
        return self._chamar("GET", "/saude")

    def versao(self) -> dict:
        return self._chamar("GET", "/versao")

    def contrato(self) -> dict:
        return self._chamar("GET", "/contrato")

    def relatorio(self) -> dict:
        return self._chamar("GET", "/relatorio")

    def prever(self, registros: list[dict]) -> dict:
        return self._chamar("POST", "/prever", json={"registros": registros})
