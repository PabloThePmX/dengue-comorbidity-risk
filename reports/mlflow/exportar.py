"""Exporta o resumo dos registros do MLflow (arquivo de passagem retorno-mlruns/) para
reports/mlflow/cronologia.md e runs.csv. Só agregados (R7): nome, data, status e métricas de busca e
seleção. Os parâmetros de configuração não entram (estão em config/ e nos hashes de dados).
Uso: python reports/mlflow/exportar.py <pasta do experimento>"""
import csv
import datetime as dt
import hashlib
import pathlib
import sys

import yaml

STATUS = {1: "RUNNING", 2: "SCHEDULED", 3: "FINISHED", 4: "FAILED", 5: "KILLED"}
exp = pathlib.Path(sys.argv[1])
saida = pathlib.Path(__file__).parent


def fmt(ms):
    return dt.datetime.fromtimestamp(ms / 1000, dt.UTC).strftime("%Y-%m-%d %H:%M")


runs = []
for d in exp.iterdir():
    if not (d / "meta.yaml").exists() or d.name == "models":
        continue
    y = yaml.safe_load((d / "meta.yaml").read_text(encoding="utf-8"))
    met = {}
    for f in (d / "metrics").rglob("*") if (d / "metrics").exists() else []:
        if f.is_file():
            linhas = f.read_text().strip().splitlines()
            if linhas:
                met[f.relative_to(d / "metrics").as_posix()] = float(linhas[-1].split()[1])
    runs.append(dict(inicio=y["start_time"], nome=y["run_name"],
                     status=STATUS.get(y["status"], str(y["status"])), met=met))
runs.sort(key=lambda r: (r["inicio"], r["nome"]))

# sessão = de um "sessao-m1" até o próximo
sessao, n_sessao = 0, 0
for r in runs:
    if r["nome"] == "sessao-m1":
        n_sessao += 1
    r["sessao"] = n_sessao


def g(r, k, nd=4):
    v = r["met"].get(k)
    return "" if v is None else (f"{v:.{nd}f}" if nd else f"{v:.0f}")


colunas = ["sessao", "inicio_utc", "run", "status", "pr_auc_busca", "tentativas_concluidas",
           "tentativas_podadas", "tempo_busca_s", "oof_pr_auc", "pr_auc_media", "tempo_treino_s",
           "limiar", "limiar_f2", "recall_no_limiar", "brier_calibrado"]
linhas = []
for r in runs:
    m = r["met"]
    linhas.append([
        r["sessao"], fmt(r["inicio"]), r["nome"], r["status"], g(r, "tuning.melhor_pr_auc"),
        g(r, "tuning.tentativas_concluidas", 0), g(r, "tuning.tentativas_podadas", 0),
        g(r, "tuning.tempo_busca_total_s", 0), g(r, "final.oof_pr_auc"),
        g(r, "final.pr_auc_media"), g(r, "final.tempo_treino_s", 0),
        g(r, "selecao.limiar", 6), g(r, "selecao.limiar_f2", 6),
        g(r, "selecao.recall_no_limiar"), g(r, "selecao.brier_calibrado", 6),
    ])

with open(saida / "runs.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh, lineterminator="\n")
    w.writerow(colunas)
    w.writerows(linhas)

md = ["# Cronologia dos experimentos (MLflow)", "",
      f"Exportado de `{exp.parent.name}/` (cópia do `mlruns/` do Drive). Experimento "
      "`dengue-comorbidity-risk`; %d execuções em %d sessões (cada sessão começa em uma execução "
      "`sessao-m1`). Horários em UTC, como gravados pelo MLflow. Só agregados (R7): não há "
      "microdados nem parâmetros de configuração; esses estão em `config/` e nos hashes de dados "
      "dos registros." % (len(runs), n_sessao), "",
      "Leitura das colunas: `pr_auc_busca` é a melhor PR-AUC da busca de hiperparâmetros; "
      "`oof_pr_auc` e `pr_auc_media` são do modelo final, fora da dobra (OOF) e média por dobra; "
      "`tempo_busca_s` e `tempo_treino_s` em segundos; `limiar`, `limiar_f2` e "
      "`recall_no_limiar` vêm da execução `selecao`. "
      "A diferença entre início e fim registrada pelo MLflow é zero em várias execuções, então "
      "esta tabela não a usa: os tempos vêm das métricas `tempo_busca_s` e `tempo_treino_s`. "
      "A execução `tune-elastic_net` de 2026-11-17 13:00 está como FAILED; a repetição das 13:27 "
      "terminou (FINISHED). Os pares de execuções `selecao` de 2026-11-18 23:54 e 2026-11-19 "
      "01:38 trazem os mesmos números.", ""]
cab = "| " + " | ".join(colunas) + " |"
md += [cab, "|" + "|".join("---" for _ in colunas) + "|"]
md += ["| " + " | ".join(str(x) for x in linha) + " |" for linha in linhas]
(saida / "cronologia.md").write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")
for n in ("cronologia.md", "runs.csv"):
    print(n, hashlib.sha256((saida / n).read_bytes()).hexdigest())
print(len(runs), "execuções,", n_sessao, "sessões")
