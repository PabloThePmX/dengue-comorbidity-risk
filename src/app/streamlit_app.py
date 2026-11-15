"""App Streamlit com abas Perfil (E1) e Triagem (M1) (T-6.1 a T-6.4, FR-11, NFR-03, NFR-06)."""

import os
from pathlib import Path
from typing import Any

import pandas as pd

from dengue_sinan.artifacts import load_bundle
from dengue_sinan.baselines import rule_b2
from dengue_sinan.dataset import COMORBIDADES, SINAIS
from dengue_sinan.explain import E1Artifact, extract_or_and_interactions

DISCLAIMER_TEXT = "Projeto acadêmico. Não é ferramenta clínica nem substitui avaliação médica."
PERFIL_SUBTITLE = "Qual o risco de quem tem estas condições"
TRIAGEM_SUBTITLE = "Qual o risco deste paciente, com estes sintomas, agora"
SHAP_LOCAL_PHRASE = "contribuição no modelo, não causa"

COMORB_LABELS: dict[str, str] = {
    "DIABETES": "Diabetes",
    "HEMATOLOG": "Doença hematológica",
    "HEPATOPAT": "Hepatopatia",
    "RENAL": "Doença renal crônica",
    "HIPERTENSA": "Hipertensão arterial",
    "ACIDO_PEPT": "Doença ácido-péptica",
    "AUTO_IMUNE": "Doença autoimune",
}

SINAIS_LABELS: dict[str, str] = {
    "FEBRE": "Febre",
    "MIALGIA": "Mialgia",
    "CEFALEIA": "Cefaleia",
    "EXANTEMA": "Exantema",
    "VOMITO": "Vômito",
    "NAUSEA": "Náusea",
    "DOR_COSTAS": "Dor nas costas",
    "CONJUNTVIT": "Conjuntivite",
    "ARTRITE": "Artrite",
    "ARTRALGIA": "Artralgia intensa",
    "DOR_RETRO": "Dor retro-orbital",
    "PETEQUIA_N": "Petéquias",
    "LEUCOPENIA": "Leucopenia",
    "LACO": "Prova do laço positiva",
}


def compute_perfil_tab(
    e1_bundle: Any,
    *,
    idade_anos: float,
    sexo: str,
    gestante: bool,
    comorbidades_ativas: list[str],
) -> dict[str, Any]:
    """Executa a lógica pura da aba Perfil (E1) sem armazenar entradas (T-6.2, NFR-03)."""
    e1_model: E1Artifact = e1_bundle["model"]
    pred = e1_model.predict_profile_risk(
        idade_anos=float(idade_anos),
        sexo=str(sexo),
        gestante=int(bool(gestante)),
        comorbidades_ativas=comorbidades_ativas,
    )
    ref = e1_model.predict_profile_risk(
        idade_anos=float(idade_anos),
        sexo=str(sexo),
        gestante=0,
        comorbidades_ativas=[],
    )
    razao_ref = pred["risco"] / ref["risco"] if ref["risco"] > 0 else 1.0

    main_or_df, _ = extract_or_and_interactions(e1_model)
    selected_or = main_or_df[main_or_df["comorbidade"].isin(comorbidades_ativas)].copy()

    return {
        "aviso": DISCLAIMER_TEXT,
        "frase_aba": PERFIL_SUBTITLE,
        "risco": pred["risco"],
        "ic95_inf": pred["ic95_inf"],
        "ic95_sup": pred["ic95_sup"],
        "risco_sem_comorbidades": ref["risco"],
        "razao_vs_saudavel": float(razao_ref),
        "or_comorbidades_marcadas": selected_or,
    }


def build_triage_case_df(
    *,
    idade_anos: float,
    sexo: str,
    gestante: bool,
    comorbidades_ativas: list[str],
    sinais_ativos: list[str],
    dias_ate_atendimento: float,
) -> pd.DataFrame:
    """Constrói um DataFrame de 1 linha no schema de features de M1 e B2 (T-6.3, §3.15)."""
    active_c = set(comorbidades_ativas)
    active_s = set(sinais_ativos)
    row: dict[str, Any] = {
        "idade_anos": float(idade_anos),
        "sexo": str(sexo),
        "gestante": int(bool(gestante)),
        "n_comorbidades": int(len(active_c)),
        "dias_ate_notificacao": float(max(0.0, min(60.0, float(dias_ate_atendimento)))),
    }
    for c in COMORBIDADES:
        row[c] = "Sim" if c in active_c else "Não"
    for s in SINAIS:
        row[s] = "Sim" if s in active_s else "Não"
    return pd.DataFrame([row])


def compute_triagem_tab(
    m1_bundle: Any,
    *,
    idade_anos: float,
    sexo: str,
    gestante: bool,
    comorbidades_ativas: list[str],
    sinais_ativos: list[str],
    dias_ate_atendimento: float,
) -> dict[str, Any]:
    """Executa a lógica pura da aba Triagem (M1 + B2 + top-5 fatores locais) (T-6.3, NFR-06)."""
    case_df = build_triage_case_df(
        idade_anos=idade_anos,
        sexo=sexo,
        gestante=gestante,
        comorbidades_ativas=comorbidades_ativas,
        sinais_ativos=sinais_ativos,
        dias_ate_atendimento=dias_ate_atendimento,
    )
    m1_model = m1_bundle["model"]
    risco_cal = float(m1_model.predict_proba(case_df)[0, 1])
    limiar = float(m1_bundle["metadata"].get("limiar_f2", getattr(m1_model, "limiar", 0.5)))
    alto_risco = bool(risco_cal >= limiar)
    fatores = m1_model.explain_case(case_df, top_k=5)
    grupo_b_b2 = bool(rule_b2(case_df)[0])

    return {
        "aviso": DISCLAIMER_TEXT,
        "frase_aba": TRIAGEM_SUBTITLE,
        "risco_calibrado": risco_cal,
        "limiar": limiar,
        "alto_risco": alto_risco,
        "top_5_fatores": fatores,
        "frase_shap": SHAP_LOCAL_PHRASE,
        "grupo_b_protocolo_ms": grupo_b_b2,
        "modelo_versao": str(m1_bundle["metadata"].get("modelo_tipo", "m1")),
    }


def main() -> None:
    """Renderiza a interface gráfica do Streamlit (T-6.1 a T-6.3)."""
    import streamlit as st

    st.set_page_config(
        page_title="Risco em Dengue por Perfil de Comorbidades",
        layout="wide",
    )
    st.title("Avaliação de Risco de Desfecho Grave em Dengue (SINAN)")

    models_dir = Path(os.environ.get("DENGUE_MODELS_DIR", "models"))
    e1_path = models_dir / "e1_final.joblib"
    if not e1_path.is_file():
        e1_path = models_dir / "e1.joblib"
    m1_path = models_dir / "m1_final.joblib"

    tab_perfil, tab_triagem = st.tabs(["Perfil (E1)", "Triagem (M1)"])

    with tab_perfil:
        st.info(DISCLAIMER_TEXT)
        st.subheader(PERFIL_SUBTITLE)

        if not e1_path.is_file():
            st.warning(f"Artefato E1 não encontrado em `{e1_path}`. Execute a Fase 3 primeiro.")
        else:
            e1_bundle = load_bundle(e1_path)
            col1, col2 = st.columns(2)
            with col1:
                idade_p = st.slider("Idade (anos)", 0, 110, 55, key="p_idade")
                sexo_p = st.selectbox("Sexo", ["F", "M"], key="p_sexo")
                gest_p = (
                    st.checkbox("Gestante", value=False, key="p_gest")
                    if sexo_p == "F"
                    else False
                )
            with col2:
                st.markdown("**Comorbidades pré-existentes:**")
                ativas_p = [
                    c
                    for c in COMORBIDADES
                    if st.checkbox(COMORB_LABELS.get(c, c), value=False, key=f"p_{c}")
                ]

            res_p = compute_perfil_tab(
                e1_bundle,
                idade_anos=idade_p,
                sexo=sexo_p,
                gestante=gest_p,
                comorbidades_ativas=ativas_p,
            )
            m_col1, m_col2, m_col3 = st.columns(3)
            m_col1.metric(
                "Risco estimado (E1)",
                f"{res_p['risco'] * 100:.2f}%",
                help=f"IC 95%: [{res_p['ic95_inf'] * 100:.2f}%, {res_p['ic95_sup'] * 100:.2f}%]",
            )
            m_col2.metric(
                "Sem comorbidades (mesma idade/sexo)",
                f"{res_p['risco_sem_comorbidades'] * 100:.2f}%",
            )
            m_col3.metric(
                "Razão vs. sem comorbidades",
                f"{res_p['razao_vs_saudavel']:.2f}x",
            )
            st.caption(
                f"Intervalo de confiança de 95% (método delta): "
                f"{res_p['ic95_inf'] * 100:.2f}% a {res_p['ic95_sup'] * 100:.2f}%."
            )
            if not res_p["or_comorbidades_marcadas"].empty:
                st.markdown("**Odds Ratios (OR) dos efeitos principais marcados (E1):**")
                or_cols = ["comorbidade", "OR", "IC95_inf", "IC95_sup"]
                st.dataframe(
                    res_p["or_comorbidades_marcadas"][or_cols],
                    use_container_width=True,
                )

    with tab_triagem:
        st.error(f"**AVISO IMPORTANTE:** {DISCLAIMER_TEXT}")
        st.subheader(TRIAGEM_SUBTITLE)

        if not m1_path.is_file():
            st.warning(f"Artefato M1 não encontrado em `{m1_path}`. Execute a Fase 4 primeiro.")
        else:
            m1_bundle = load_bundle(m1_path)
            c1, c2, c3 = st.columns(3)
            with c1:
                idade_t = st.slider("Idade (anos)", 0, 110, 55, key="t_idade")
                sexo_t = st.selectbox("Sexo", ["F", "M"], key="t_sexo")
                gest_t = (
                    st.checkbox("Gestante", value=False, key="t_gest")
                    if sexo_t == "F"
                    else False
                )
                dias_t = st.slider("Dias desde o início dos sintomas", 0, 60, 3, key="t_dias")
            with c2:
                st.markdown("**Comorbidades:**")
                ativas_tc = [
                    c
                    for c in COMORBIDADES
                    if st.checkbox(COMORB_LABELS.get(c, c), value=False, key=f"t_{c}")
                ]
            with c3:
                st.markdown("**Sintomas e sinais iniciais:**")
                ativos_ts = [
                    s
                    for s in SINAIS
                    if st.checkbox(SINAIS_LABELS.get(s, s), value=False, key=f"t_{s}")
                ]

            res_t = compute_triagem_tab(
                m1_bundle,
                idade_anos=idade_t,
                sexo=sexo_t,
                gestante=gest_t,
                comorbidades_ativas=ativas_tc,
                sinais_ativos=ativos_ts,
                dias_ate_atendimento=dias_t,
            )
            k1, k2, k3 = st.columns(3)
            k1.metric("Risco calibrado (M1)", f"{res_t['risco_calibrado'] * 100:.2f}%")
            k2.metric(
                f"Classificação no limiar F2 ({res_t['limiar'] * 100:.2f}%)",
                "ALTO RISCO" if res_t["alto_risco"] else "Baixo risco",
            )
            b2_label = (
                "Grupo B (Alto risco)"
                if res_t["grupo_b_protocolo_ms"]
                else "Não enquadrado no Grupo B"
            )
            k3.metric("Regra do Protocolo MS (Grupo B / B2)", b2_label)

            st.markdown(f"**5 fatores que mais influenciaram a predição ({SHAP_LOCAL_PHRASE}):**")
            st.dataframe(pd.DataFrame(res_t["top_5_fatores"]), use_container_width=True)


if __name__ == "__main__":
    main()
