"""Verificação da T-3.6 (Marco 3, no PC local, D-66): grava reports/verificacao/T-3.6.json.

Gera `models/e1/` a partir do E1 salvo em `data/e1/` e confere:
- num processo em que o statsmodels está bloqueado (a demo não o tem), a carga reproduz o risco,
  o IC 95% e a razão de risco de 10 perfis do E1 original, com diferença < 1e-9;
- os SHA-256 do payload batem com o metadata, o payload não tem pickle e o bundle tem < 1 MB;
- R7 e NFR-03: nenhuma matriz com ordem de grandeza do nº de linhas e nenhum inteiro de 1 a 9
  no metadata nem no e1.json;
- NFR-06: carga + risco de um perfil em menos de 1 s, no processo sem statsmodels.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

from dengue_sinan import artifacts, explain, verify

RAIZ = Path(__file__).resolve().parents[2]
ESPERADO_PADRAO = RAIZ / "config" / "esperado.yaml"
TOLERANCIA = 1e-9
LIMITE_TAMANHO_BYTES = 1_000_000
LIMITE_TEMPO_S = 1.0  # NFR-06
CAMPOS_FR12 = ("schema_version", "tipo_payload", "criado_em_utc", "versao_codigo", "bibliotecas",
               "payload", "config", "dados", "data_treino", "metricas_validacao", "features")
# 10 perfis reais: faixas etárias, sexos, gestação, comorbidades simples e combinadas, pares
# incluídos (DIABETES x HIPERTENSA, HEMATOLOG x RENAL, HEPATOPAT x HIPERTENSA, HIPERTENSA x
# AUTO_IMUNE) e pares excluídos ("eventos insuficientes": RENAL x ACIDO_PEPT,
# HEPATOPAT x AUTO_IMUNE).
PERFIS = [
    (40, "F", 0, ()),
    (3, "I", 0, ()),
    (12, "M", 0, ("ACIDO_PEPT",)),
    (30, "F", 1, ("HEMATOLOG", "RENAL")),
    (63, "F", 0, ("DIABETES", "HIPERTENSA")),
    (25, "M", 0, ("DIABETES",)),
    (72, "M", 0, ("HEPATOPAT", "HIPERTENSA", "AUTO_IMUNE")),
    (50, "F", 0, ("DIABETES", "HIPERTENSA", "RENAL")),
    (85, "M", 0, ("RENAL", "ACIDO_PEPT")),
    (33, "F", 0, ("HEPATOPAT", "AUTO_IMUNE")),
]

# Roda num processo novo, sem statsmodels. Imprime uma linha JSON com os resultados e os tempos.
BLOQUEIO = """
import sys
class _Bloqueio:
    def find_spec(self, nome, caminho=None, alvo=None):
        if nome.split('.')[0] == 'statsmodels':
            raise ImportError('statsmodels bloqueado')
        return None
sys.meta_path.insert(0, _Bloqueio())
"""
CODIGO_CARGA = """
import json, statistics, sys, time
try:
    import statsmodels  # noqa: F401
    bloqueio_ativo = False
except ImportError:
    bloqueio_ativo = True
from dengue_sinan import artifacts, explain

perfis = json.loads(sys.argv[2])

def calcular(e1, perfil):
    idade, sexo, gestante, comorbidades = perfil
    r = explain.risco_perfil(e1, idade, sexo, gestante, comorbidades)
    rr = explain.razao_de_risco(e1, idade, sexo, gestante, comorbidades)
    return {"risco": r["risco"], "ic_inferior": r["ic_inferior"], "ic_superior": r["ic_superior"],
            "razao": rr["razao"], "rr_ic_inferior": rr["ic_inferior"],
            "rr_ic_superior": rr["ic_superior"]}

t0 = time.perf_counter()
e1 = artifacts.load_bundle(sys.argv[1])
primeiro = calcular(e1, perfis[0])
t1 = time.perf_counter()
repeticoes = []
for _ in range(50):
    inicio = time.perf_counter()
    explain.risco_perfil(e1, *perfis[0][:3], perfis[0][3])
    repeticoes.append(time.perf_counter() - inicio)
resultados = [primeiro] + [calcular(e1, p) for p in perfis[1:]]
print(json.dumps({
    "bloqueio_ativo": bloqueio_ativo,
    "statsmodels_no_processo": "statsmodels" in sys.modules,
    "perfis": resultados,
    "tempo_carga_e_um_perfil_s": t1 - t0,
    "tempo_risco_um_perfil_mediano_s": statistics.median(repeticoes),
}))
"""


def _calcular_original(e1: explain.E1Ajustado, perfil: tuple) -> dict:
    idade, sexo, gestante, comorbidades = perfil
    r = explain.risco_perfil(e1, idade, sexo, gestante, comorbidades)
    rr = explain.razao_de_risco(e1, idade, sexo, gestante, comorbidades)
    return {"risco": r["risco"], "ic_inferior": r["ic_inferior"], "ic_superior": r["ic_superior"],
            "razao": rr["razao"], "rr_ic_inferior": rr["ic_inferior"],
            "rr_ic_superior": rr["ic_superior"]}


def _carregar_sem_statsmodels(pasta: Path) -> dict:
    ambiente = {**os.environ, "PYTHONPATH": str(RAIZ / "src")}
    perfis = [[idade, sexo, gestante, list(comorbidades)]
              for idade, sexo, gestante, comorbidades in PERFIS]
    resultado = subprocess.run(
        [sys.executable, "-c", BLOQUEIO + CODIGO_CARGA, str(pasta), json.dumps(perfis)],
        capture_output=True, text=True, timeout=300, env=ambiente, cwd=RAIZ, check=False,
    )
    if resultado.returncode != 0:
        raise RuntimeError(f"carga sem statsmodels falhou: {resultado.stderr[-2000:]}")
    return json.loads(resultado.stdout.strip().splitlines()[-1])


def _maior_diferenca(a: dict, b: dict, campos: tuple[str, ...]) -> float:
    return max(abs(float(a[c]) - float(b[c])) for c in campos)


def _tamanho(pasta: Path) -> int:
    return sum(p.stat().st_size for p in pasta.rglob("*") if p.is_file())


def _checks_esperado_e1(esperado: dict, descricao: dict) -> list[dict]:
    """Confere o `e1.json` do bundle com a seção `e1` de config/esperado.yaml (nunca com número
    escrito aqui). `descricao` é o JSON já lido; `colunas` tem o mesmo tamanho de `params`."""
    return [
        verify.check("parametros_no_bundle", esperado["parametros"], len(descricao["colunas"])),
        verify.check("pares_incluidos_no_bundle", esperado["pares_incluidos"],
                     len(descricao["pares_incluidos"])),
    ]


def executar(cfg: dict, esperado_path: Path = ESPERADO_PADRAO) -> tuple[Path, dict]:
    """Gera o bundle, confere e grava o relatório T-3.6. Devolve (relatório, medidas)."""
    esperado = explain.ler_esperado_e1(esperado_path)
    original = explain.load_e1(cfg)
    pasta = artifacts.gerar_bundle_e1(cfg)
    meta = artifacts.ler_metadados(pasta)
    saida = _carregar_sem_statsmodels(pasta)

    referencia = [_calcular_original(original, p) for p in PERFIS]
    obtidos = saida["perfis"]
    campos_risco = ("risco", "ic_inferior", "ic_superior")
    campos_razao = ("razao", "rr_ic_inferior", "rr_ic_superior")
    dif_risco = max(_maior_diferenca(r, o, campos_risco) for r, o in zip(referencia, obtidos,
                                                                         strict=True))
    dif_razao = max(_maior_diferenca(r, o, campos_razao) for r, o in zip(referencia, obtidos,
                                                                         strict=True))

    k = len(original.colunas)
    with np.load(pasta / artifacts.PASTA_PAYLOAD / artifacts.E1_NPZ) as npz:
        ordem_de_linhas = any(max(npz[n].shape) > k or npz[n].size > k * k for n in npz.files)
    texto = (pasta / artifacts.NOME_METADATA).read_text(encoding="utf-8")
    texto += (pasta / artifacts.PASTA_PAYLOAD / artifacts.E1_JSON).read_text(encoding="utf-8")
    descricao = json.loads((pasta / artifacts.PASTA_PAYLOAD / artifacts.E1_JSON).read_text(
        encoding="utf-8"))
    pequenos = artifacts.inteiros_pequenos(meta) + artifacts.inteiros_pequenos(descricao)
    tamanho = _tamanho(pasta)
    tempo_total = saida["tempo_carga_e_um_perfil_s"]

    checks = [
        verify.check("bloqueio_statsmodels_ativo", True, saida["bloqueio_ativo"]),
        verify.check("carga_sem_statsmodels_no_processo", False, saida["statsmodels_no_processo"]),
        verify.check("perfis_comparados", len(PERFIS), len(obtidos)),
        verify.check("diferenca_max_risco_e_ic", 0.0, dif_risco, TOLERANCIA),
        verify.check("diferenca_max_razao_de_risco_e_ic", 0.0, dif_razao, TOLERANCIA),
        verify.check("metadata_fr12_completo", True, all(c in meta for c in CAMPOS_FR12)),
        verify.check("tipo_payload_e1", "e1", meta["tipo_payload"]),
        verify.check("payload_sem_pickle", True, all(
            not n.endswith((".pkl", ".pickle")) for n in meta["payload"])),
        *[verify.check(f"sha256_{n.replace('.', '_')}", sha,
                       artifacts._sha256(pasta / artifacts.PASTA_PAYLOAD / n))
          for n, sha in meta["payload"].items()],
        verify.check("bundle_menor_que_1_MB", True, tamanho < LIMITE_TAMANHO_BYTES),
        verify.check("matrizes_sem_ordem_de_linhas", True, not ordem_de_linhas),
        verify.check("sem_contagem_de_1_a_9", True, pequenos == []),
        verify.check("sem_eventos_por_termo", True, "eventos_por_termo" not in texto),
        verify.check("nos_e_colunas_do_bundle_iguais_ao_ajuste", True,
                     descricao["colunas"] == original.colunas
                     and descricao["nos"] == original.nos),
        verify.check("carga_mais_um_perfil_abaixo_de_1s_NFR06", True,
                     tempo_total < LIMITE_TEMPO_S),
        *_checks_esperado_e1(esperado, descricao),
    ]
    relatorio = verify.write_report("T-3.6", checks,
                                    Path(cfg["caminhos"]["relatorios"]) / "verificacao", cfg)
    medidas = {
        "bundle": str(pasta),
        "tamanho_bytes": tamanho,
        "tempo_carga_e_um_perfil_s": tempo_total,
        "tempo_risco_um_perfil_mediano_s": saida["tempo_risco_um_perfil_mediano_s"],
        "diferenca_max_risco_e_ic": dif_risco,
        "diferenca_max_razao_de_risco_e_ic": dif_razao,
        "perfis": len(PERFIS),
        "passou": json.loads(relatorio.read_text(encoding="utf-8"))["passou"],
    }
    return relatorio, medidas


if __name__ == "__main__":
    from dengue_sinan.config import load_config

    caminho, medidas = executar(load_config())
    print(json.dumps(medidas, indent=2, ensure_ascii=False))
    print(f"relatório: {caminho}")
