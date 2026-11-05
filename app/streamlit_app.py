"""Demo acadêmica de risco de dengue com E1 e M1 congelados."""

import os
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import shap
import streamlit as st
import torch

from dengue_sinan.artifacts import load_bundle
from dengue_sinan.baselines import rule_b2
from dengue_sinan.dataset import build_feature_frame
from dengue_sinan.explain import E1Bundle, predict_e1
from dengue_sinan.profiling import COMORBIDADES

_COMORBIDITY_FIELDS = {
    "diabetes": "DIABETES",
    "hematologica": "HEMATOLOG",
    "hepatopatia": "HEPATOPAT",
    "renal_cronica": "RENAL",
    "hipertensao": "HIPERTENSA",
    "acido_peptica": "ACIDO_PEPT",
    "autoimune": "AUTO_IMUNE",
}
_SYMPTOM_FIELDS = {
    "febre": "FEBRE",
    "mialgia": "MIALGIA",
    "cefaleia": "CEFALEIA",
    "exantema": "EXANTEMA",
    "vomito": "VOMITO",
    "nausea": "NAUSEA",
    "dor_costas": "DOR_COSTAS",
    "conjuntivite": "CONJUNTVIT",
    "artrite": "ARTRITE",
    "artralgia": "ARTRALGIA",
    "dor_retro_orbital": "DOR_RETRO",
    "petéquias": "PETEQUIA_N",
    "leucopenia": "LEUCOPENIA",
    "prova_do_laco": "LACO",
}
_CHOICES = {"sim": "1", "nao": "2", "ignorado": "9"}
_LABELS = {"sim": "Sim", "nao": "Não", "ignorado": "Ignorado"}


def _validate_profile(values: dict) -> None:
    age = values.get("idade_anos")
    if isinstance(age, bool) or not isinstance(age, (int, np.integer)) or not 0 <= age <= 120:
        raise ValueError("idade_anos deve ser um inteiro entre 0 e 120")
    if values.get("sexo") not in {"F", "M"}:
        raise ValueError("sexo deve ser F ou M")
    if values.get("gestante") not in _CHOICES:
        raise ValueError("gestante deve ser sim, nao ou ignorado")
    for field in (*_COMORBIDITY_FIELDS, *_SYMPTOM_FIELDS):
        if field in values and values[field] not in _CHOICES:
            raise ValueError(f"{field} deve ser sim, nao ou ignorado")
    if "dias_ate_atendimento" in values:
        days = values["dias_ate_atendimento"]
        if (
            isinstance(days, bool)
            or not isinstance(days, (int, np.integer))
            or not 0 <= days <= 60
        ):
            raise ValueError("dias_ate_atendimento deve ser um inteiro entre 0 e 60")


def _e1_frame(values: dict) -> pd.DataFrame:
    _validate_profile(values)
    return pd.DataFrame([{
        "idade_anos": values["idade_anos"],
        "CS_SEXO": values["sexo"],
        "gestante": values["gestante"] == "sim",
        **{
            raw: _CHOICES[values.get(field, "nao")]
            for field, raw in _COMORBIDITY_FIELDS.items()
        },
    }])


def _m1_features(values: dict) -> pd.DataFrame:
    _validate_profile(values)
    if "dias_ate_atendimento" not in values:
        raise ValueError("dias_ate_atendimento é obrigatório para M1")
    onset = date(2020, 1, 1)
    notification = onset + timedelta(days=values["dias_ate_atendimento"])
    row = {
        "idade_anos": values["idade_anos"],
        "DT_SIN_PRI": onset.strftime("%Y%m%d"),
        "DT_NOTIFIC": notification.strftime("%Y%m%d"),
        "CS_SEXO": values["sexo"],
        "CS_GESTANT": _CHOICES[values["gestante"]]
        if values["gestante"] != "nao"
        else "6",
        **{
            raw: _CHOICES[values.get(field, "nao")]
            for field, raw in _COMORBIDITY_FIELDS.items()
        },
        **{
            raw: _CHOICES[values.get(field, "ignorado")]
            for field, raw in _SYMPTOM_FIELDS.items()
        },
    }
    return build_feature_frame(pd.DataFrame([row]))


def _marked_odds_ratios(bundle: E1Bundle, values: dict) -> pd.DataFrame:
    rows = []
    for field, raw in _COMORBIDITY_FIELDS.items():
        if values.get(field) != "sim":
            continue
        prefix = (
            f'C({raw}, Treatment(reference="Não"), '
            'levels=["Não", "Sim", "Ausente"])[T.Sim]'
        )
        index = bundle.columns.index(prefix)
        rows.append({
            "Comorbidade": field,
            "OR ajustada": float(np.exp(bundle.coefficients[index])),
        })
    return pd.DataFrame(rows)


def _top_factors(bundle: dict, features: pd.DataFrame) -> pd.DataFrame:
    pipeline = bundle["pipeline"]
    preprocessor = pipeline.named_steps["preprocess"]
    row = np.asarray(preprocessor.transform(features))
    family = bundle["modelo"]
    if family in {"random_forest", "xgboost", "catboost"}:
        values = bundle["explainer"](row).values
        if values.ndim == 3:
            values = values[0, :, 1]
        else:
            values = values[0]
    elif family == "elastic_net":
        values = pipeline.named_steps["model"].coef_.reshape(-1) * row.reshape(-1)
    elif family == "mlp":
        sample = torch.as_tensor(row, dtype=torch.float32)
        values = np.asarray(bundle["explainer"].shap_values(sample)).reshape(-1)
    else:
        raise ValueError(f"modelo sem explicador local: {family}")

    names = preprocessor.get_feature_names_out()
    order = np.argsort(np.abs(values))[-5:][::-1]
    return pd.DataFrame({
        "Fator": [str(names[index]) for index in order],
        "Contribuição": [float(values[index]) for index in order],
        "Direção": ["Aumentou" if values[index] > 0 else "Reduziu" for index in order],
    })


@st.cache_resource
def _load_model(path: str):
    return load_bundle(path)


def _load_if_present(filename: str):
    path = Path(os.environ.get("DENGUE_MODELS_DIR", "models")) / filename
    if not path.is_file():
        st.warning(f"Artefato ausente: {path}. Treine e congele o modelo antes de usar esta aba.")
        return None
    model = _load_model(str(path.resolve()))[0]
    if filename == "m1_final.joblib" and "explainer" not in model:
        family = model["modelo"]
        estimator = model["pipeline"].named_steps["model"]
        if family in {"random_forest", "xgboost", "catboost"}:
            model["explainer"] = shap.TreeExplainer(estimator)
        elif family == "mlp":
            background = torch.as_tensor(model["shap_background"], dtype=torch.float32)
            model["explainer"] = shap.GradientExplainer(estimator.model_, background)
    return model


def _profile_inputs(prefix: str, include_symptoms: bool = False) -> dict:
    values = {}
    left, right = st.columns(2)
    values["idade_anos"] = left.number_input(
        "Idade (anos)", min_value=0, max_value=120, value=60, key=f"{prefix}_idade"
    )
    values["sexo"] = right.selectbox("Sexo", ["F", "M"], key=f"{prefix}_sexo")
    values["gestante"] = st.selectbox(
        "Gestação", list(_CHOICES), format_func=lambda value: _LABELS[value],
        key=f"{prefix}_gestante",
    )
    st.markdown("**Comorbidades**")
    for field in _COMORBIDITY_FIELDS:
        values[field] = st.selectbox(
            field.replace("_", " ").capitalize(),
            list(_CHOICES),
            format_func=lambda value: _LABELS[value],
            key=f"{prefix}_{field}",
        )
    if include_symptoms:
        st.markdown("**Sintomas e sinais iniciais**")
        for field in _SYMPTOM_FIELDS:
            values[field] = st.selectbox(
                field.replace("_", " ").capitalize(),
                list(_CHOICES),
                format_func=lambda value: _LABELS[value],
                key=f"{prefix}_{field}",
            )
        values["dias_ate_atendimento"] = st.number_input(
            "Dias entre início dos sintomas e atendimento",
            min_value=0,
            max_value=60,
            value=2,
            key=f"{prefix}_dias",
        )
    return values


def main() -> None:
    st.set_page_config(page_title="Risco de dengue — projeto acadêmico", page_icon="🦟")
    st.title("Risco de desfecho grave em dengue")
    st.caption(
        "Projeto acadêmico. Não é ferramenta clínica nem substitui avaliação médica."
    )
    profile_tab, triage_tab = st.tabs(["Perfil (E1)", "Triagem (M1)"])

    with profile_tab:
        st.write("Perfil: qual o risco de quem tem estas condições?")
        e1 = _load_if_present("e1_final.joblib")
        values = _profile_inputs("e1")
        if st.button("Calcular perfil", key="calculate_e1") and e1 is not None:
            if not isinstance(e1, E1Bundle):
                st.error("O artefato E1 não contém um bundle válido.")
            else:
                profile = _e1_frame(values)
                estimate = predict_e1(e1, profile).iloc[0]
                healthy = profile.copy()
                for raw in COMORBIDADES:
                    healthy[raw] = "2"
                reference = predict_e1(e1, healthy).iloc[0]
                st.metric("Risco estimado", f"{estimate.risco:.2%}")
                st.write(f"IC 95%: {estimate.ic_inf:.2%}–{estimate.ic_sup:.2%}")
                st.write(f"Sem comorbidades, mesma faixa: {reference.risco:.2%}")
                ratios = _marked_odds_ratios(e1, values)
                if not ratios.empty:
                    st.dataframe(ratios, hide_index=True)

    with triage_tab:
        st.error("Projeto acadêmico. Não é ferramenta clínica nem substitui avaliação médica.")
        st.write("Triagem: qual o risco deste paciente, com estes sintomas, agora?")
        m1 = _load_if_present("m1_final.joblib")
        values = _profile_inputs("m1", include_symptoms=True)
        if st.button("Calcular triagem", key="calculate_m1") and m1 is not None:
            features = _m1_features(values)
            raw_probability = m1["pipeline"].predict_proba(features)[:, 1]
            probability = float(m1["calibrator"].transform(raw_probability)[0])
            threshold = float(m1["threshold"])
            st.metric("Risco calibrado", f"{probability:.2%}")
            st.write(f"Alto risco: **{'Sim' if probability >= threshold else 'Não'}**")
            st.caption(f"Limiar congelado: {threshold:.4f}")
            st.write(f"Regra B2: {'grupo B' if rule_b2(features).iloc[0] else 'fora do grupo B'}")
            st.dataframe(_top_factors(m1, features), hide_index=True)
            st.caption("Contribuição no modelo, não causa.")


if __name__ == "__main__":
    main()
