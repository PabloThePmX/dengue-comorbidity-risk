"""Teste OPCIONAL com o artefato real (não roda por padrão).

Carregar o `.joblib` real executa o código do pickle (classes de `dengue_sinan.modelos`), por
isso só roda com `DENGUE_APP_TESTAR_REAL=1`, no ambiente do projeto, e só usa registros inventados.
Não lê dados de treino nem de 2024.
"""

import os

import pytest

from app.config import carregar_config
from app.servico import criar_servico

pytestmark = pytest.mark.skipif(
    os.environ.get("DENGUE_APP_TESTAR_REAL") != "1",
    reason="defina DENGUE_APP_TESTAR_REAL=1 no ambiente do projeto",
)


def test_modelo_real_carrega_e_preve():
    s = criar_servico(carregar_config())
    assert s.saude()["status"] == "ok"
    r = s.prever_m1([{"idade_anos": 34, "sexo": "F", "gestante": 0}, {"idade_anos": 70}])
    assert all(x["status"] == "ok" and 0 <= x["probabilidade"] <= 1 for x in r["resultados"])
    assert s.info()["m1"]["avaliacao_desenvolvimento"]["pr_auc"] is not None
