"""Erros próprios da camada de serviço (a API os traduz em códigos HTTP)."""


class ModeloIndisponivel(RuntimeError):
    """O modelo pedido não existe ou não pode ser usado agora. `motivo` explica em português."""

    def __init__(self, modelo: str, motivo: str):
        self.modelo = modelo
        self.motivo = motivo
        super().__init__(f"{modelo} indisponível: {motivo}")


class LoteGrande(ValueError):
    """Pedido com mais registros do que o limite configurado."""

    def __init__(self, n: int, limite: int):
        self.n, self.limite = n, limite
        super().__init__(f"{n} registros; o limite por pedido é {limite}")
