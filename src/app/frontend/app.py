"""Frontend Streamlit do protótipo (pt-BR). Fala só com a API HTTP.

    PYTHONPATH=src streamlit run src/app/frontend/app.py

Duas abas de trabalho: Triagem (M1) e Perfil (E1). O E1 aparece como indisponível enquanto não
existir artefato E1. Nenhum dado digitado é gravado.
"""

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from app.cliente import ApiErro, ApiIndisponivel, ClienteAPI  # noqa: E402
from app.config import carregar_config  # noqa: E402

SEXOS = {"Feminino": "F", "Masculino": "M", "Ignorado": "I"}
MAX_HISTORICO = 20

st.set_page_config(page_title="Risco de dengue grave: protótipo", page_icon="🦟", layout="centered")


def _cliente() -> ClienteAPI:
    cfg = carregar_config()
    return ClienteAPI(cfg.api_url, cfg.timeout_s)


def _pct(p: float) -> str:
    return f"{p * 100:.2f}".replace(".", ",") + "%"


def _carregar_versao():
    """Consulta /versao uma vez por sessão. Devolve (dados, mensagem_de_erro)."""
    if "versao" not in st.session_state:
        try:
            st.session_state["versao"] = _cliente().versao()
            st.session_state["erro_versao"] = None
        except ApiIndisponivel:
            st.session_state["versao"] = None
            st.session_state["erro_versao"] = (
                "Não consegui falar com a API. Confira se ela está ligada "
                "(veja docs/app.md) e recarregue a página."
            )
        except ApiErro as e:
            st.session_state["versao"] = None
            st.session_state["erro_versao"] = "A API não está pronta: " + "; ".join(e.itens)
    return st.session_state["versao"], st.session_state["erro_versao"]


def _avisos_fixos():
    st.warning(
        "**Protótipo de pesquisa.** Este sistema não é diagnóstico, não orienta conduta e "
        "**não substitui avaliação médica**."
    )


def _aba_inicio(versao):
    st.subheader("Sobre este protótipo")
    st.write(
        "O projeto estima, a partir de notificações de dengue do SINAN (2022 e 2023), a "
        "probabilidade de desfecho grave (dengue grave ou óbito pelo agravo) para um perfil. "
        "Hoje o modelo de triagem (M1) usa só **idade, sexo e gestante**."
    )
    st.write(
        "Como usar: abra a aba **Triagem (M1)**, informe o perfil e peça o cálculo. A aba "
        "**Perfil (E1)** vai explicar o papel das comorbidades quando o modelo explicativo existir."
    )
    if versao:
        m = versao["modelo"]
        st.write(
            f"**O que a probabilidade mede:** {m.get('desfecho') or 'não informado'}.  \n"
            f"**Como foi avaliado:** {m.get('validacao') or 'não informado'}."
        )
        st.caption(
            f"Modelo em uso: {m['identificador']} · API {versao['sistema']['app']} · "
            f"treinado com dados de {', '.join(map(str, m.get('anos_desenvolvimento') or []))}"
        )


def _aba_triagem(versao):
    st.subheader("Triagem (M1)")
    if versao is None:
        st.info("A triagem fica disponível quando a API estiver no ar.")
        return
    aval = versao["modelo"]["avaliacao_desenvolvimento"]
    prevalencia = aval.get("prevalencia")
    with st.form("form_perfil"):
        idade = st.number_input(
            "Idade (anos)", min_value=0.0, max_value=120.0, value=30.0, step=1.0, key="idade"
        )
        sexo_rotulo = st.selectbox("Sexo", list(SEXOS), key="sexo")
        gestante = st.checkbox("Gestante", key="gestante")
        enviar = st.form_submit_button("Calcular probabilidade")
    incoerente = SEXOS[sexo_rotulo] == "M" and gestante
    if incoerente:
        st.warning(
            "Você marcou sexo masculino e gestante. Corrija o perfil: o cálculo fica bloqueado "
            "enquanto essa combinação estiver marcada."
        )
    if enviar and not incoerente:
        registro = {
            "idade_anos": float(idade),
            "sexo": SEXOS[sexo_rotulo],
            "gestante": int(gestante),
        }
        try:
            with st.spinner("Calculando..."):
                resp = _cliente().prever([registro])
        except ApiIndisponivel:
            st.error("A API não respondeu. Confira se ela está ligada e tente de novo.")
            return
        except ApiErro as e:
            st.error("A API recusou o pedido: " + "; ".join(e.itens))
            return
        previsao = resp["previsoes"][0]
        if previsao["status"] != "ok":
            st.error("Perfil inválido: " + previsao["erro"])
            return
        historico = st.session_state.setdefault("historico", [])
        historico.append(
            {
                "Idade": registro["idade_anos"],
                "Sexo": sexo_rotulo,
                "Gestante": "Sim" if gestante else "Não",
                "Probabilidade (%)": round(previsao["probabilidade"] * 100, 3),
            }
        )
        del historico[:-MAX_HISTORICO]
        st.session_state["ultimo"] = previsao["probabilidade"]
        st.session_state["avisos_ultimo"] = previsao.get("avisos") or []
    if "ultimo" in st.session_state:
        p = st.session_state["ultimo"]
        st.metric("Probabilidade estimada", _pct(p))
        if prevalencia:
            st.caption(
                f"Para comparar: nos dados de desenvolvimento, a proporção média do desfecho foi "
                f"de {_pct(prevalencia)}."
            )
            st.bar_chart(
                pd.DataFrame(
                    {"%": [p * 100, prevalencia * 100]},
                    index=["Este perfil", "Média no desenvolvimento"],
                )
            )
        for aviso in st.session_state.get("avisos_ultimo", []):
            st.warning("Aviso do cálculo: " + aviso)
        st.warning(
            "A capacidade do M1 de separar perfis é limitada (leia a aba Limitações). "
            "Esta probabilidade é exploratória e não deve ser usada para decidir conduta."
        )
    historico = st.session_state.get("historico")
    if historico:
        st.write("Perfis calculados nesta sessão (não são gravados):")
        st.dataframe(pd.DataFrame(historico), hide_index=True)


def _aba_e1(versao):
    st.subheader("Perfil de comorbidades (E1)")
    if versao is None:
        st.info("Esta aba fica disponível quando a API estiver no ar.")
        return
    e1 = versao["e1"]
    if not e1["disponivel"]:
        st.info("**E1 indisponível.** " + e1["motivo"])
    else:
        st.info("O E1 está disponível na API, mas esta tela ainda não o exibe.")


def _aba_limitacoes(versao):
    st.subheader("Limitações")
    st.write(
        "- Protótipo de pesquisa: não é diagnóstico e não substitui avaliação médica.\n"
        "- O modelo usa só três variáveis (idade, sexo, gestante); não há comorbidades nem "
        "sintomas.\n"
        "- As métricas abaixo são de desenvolvimento (validação cruzada por região em 2022 e "
        "2023), não de desempenho em dado futuro.\n"
        "- Associação não é causalidade."
    )
    if versao is None:
        return
    aval = versao["modelo"]["avaliacao_desenvolvimento"]
    linhas = {
        "Proporção do desfecho (prevalência)": aval.get("prevalencia"),
        "PR-AUC": aval.get("pr_auc"),
        "ROC-AUC": aval.get("roc_auc"),
        "Brier": aval.get("brier"),
        "Brier de referência (só a prevalência)": aval.get("brier_referencia_prevalencia"),
    }
    st.table(
        pd.DataFrame(
            {
                "Valor": [
                    f"{v:.4f}".replace(".", ",") if v is not None else "n/d"
                    for v in linhas.values()
                ]
            },
            index=list(linhas),
        )
    )
    pr, prev = aval.get("pr_auc"), aval.get("prevalencia")
    br, br_ref = aval.get("brier"), aval.get("brier_referencia_prevalencia")
    if pr and prev and br and br_ref:
        ganho = (br_ref - br) / br_ref * 100
        st.write(
            f"Com desfecho raro, a PR-AUC deve ser lida contra a prevalência: "
            f"{f'{pr:.4f}'.replace('.', ',')} contra {f'{prev:.4f}'.replace('.', ',')}. "
            f"O Brier melhora só {f'{ganho:.1f}'.replace('.', ',')}% sobre a referência que usa "
            "apenas a prevalência. A capacidade de separar perfis de maior e menor risco é "
            "limitada."
        )
    for lim in versao["modelo"].get("limitacoes", []):
        st.caption("• " + lim)


def principal():
    st.title("Risco de dengue grave")
    _avisos_fixos()
    versao, erro = _carregar_versao()
    if erro:
        st.error(erro)
    abas = st.tabs(["Início", "Triagem (M1)", "Perfil (E1)", "Limitações"])
    with abas[0]:
        _aba_inicio(versao)
    with abas[1]:
        _aba_triagem(versao)
    with abas[2]:
        _aba_e1(versao)
    with abas[3]:
        _aba_limitacoes(versao)


principal()
