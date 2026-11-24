"""Demo Streamlit (US3, FR-11, D-27): abas Perfil (E1) e Triagem (M1); modos Normal e Pro (D-96).

    streamlit run src/app/streamlit_app.py

A tela é fina: a validação e a tradução da entrada estão em `app.entrada`, os cálculos em
`app.servico`.

Privacidade (NFR-03, R7):
- nenhuma entrada é gravada em disco, registrada em log, enviada a serviço externo ou guardada em
  `st.session_state` além do estado dos próprios campos da tela (que o Streamlit mantém só durante
  a sessão do navegador);
- sem analytics (`.streamlit/config.toml` desliga `gatherUsageStats`);
- nenhum microdado embarcado: o app lê só os artefatos congelados (`models/`) e os agregados do
  teste (`reports/teste/metricas.json`). Caminhos configuráveis por `DENGUE_MODELOS` e
  `DENGUE_RELATORIOS` (ver `app.servico`).
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[1])
if _SRC not in sys.path:  # roda também sem instalar o pacote (ex.: Streamlit Community Cloud)
    sys.path.insert(0, _SRC)

import streamlit as st  # noqa: E402

from app import entrada, linguagem, servico  # noqa: E402

AVISO = "Projeto acadêmico. Não é ferramenta clínica nem substitui avaliação médica."
FRASE_PERFIL = "Esta aba responde: **qual o risco de quem tem estas condições** (sem sintomas)."
FRASE_TRIAGEM = "Esta aba responde: **qual o risco deste paciente, com estes sintomas, agora**."
RISCO_DE_QUE = ("Risco = probabilidade estimada de o caso notificado de dengue evoluir para "
                "dengue grave ou óbito pelo agravo.")
FRASE_SHAP = "contribuição no modelo, não causa"
NIVEIS = {"sim": "Sim", "nao": "Não", "ignorado": "Ignorado"}
SEXOS = {"F": "Feminino", "M": "Masculino"}


@st.cache_resource(show_spinner="Carregando os modelos...")
def _artefatos(modelos: str, relatorios: str) -> servico.Artefatos:
    return servico.carregar_artefatos(Path(modelos), Path(relatorios))


def _ic(ic: tuple[float, float]) -> str:
    return f"[{servico.porcentagem(ic[0])}; {servico.porcentagem(ic[1])}]"


def _painel_teste(a: servico.Artefatos, pro: bool) -> None:
    """Bloco fixo com os agregados do teste de 2024; some se o arquivo não existir."""
    if a.painel is None:
        return
    rotulo = "O que o teste de 2024 mostrou" if pro else "Como o programa se saiu no teste"
    linhas = servico.linhas_painel(a.painel) if pro else linguagem.linhas_painel(a.painel)
    with st.expander(rotulo, expanded=True):
        for linha in linhas:
            st.markdown(linha)


def _mostrar_erros(erro: entrada.EntradaInvalida) -> None:
    for mensagem in erro.erros:
        st.error(mensagem)


# --- Aba Perfil --------------------------------------------------------------------------------

def _resultado_perfil_normal(a: servico.Artefatos, res: servico.ResultadoPerfil,
                             tem_comorbidade: bool) -> None:
    st.metric("Risco estimado", linguagem.um_em(res.risco))
    st.markdown(linguagem.frase_risco(res.risco))
    st.markdown(linguagem.frase_comparacao(res.risco, res.risco_base, res.razao, tem_comorbidade))
    aviso = linguagem.aviso_subestimado(a.painel)
    if aviso:
        st.caption(aviso)

def aba_perfil(a: servico.Artefatos, pro: bool) -> None:
    st.info(AVISO)
    st.markdown(FRASE_PERFIL)
    st.caption(RISCO_DE_QUE if pro else linguagem.COMO_LER)
    if a.e1 is None:
        st.warning(a.erro_e1 if pro else linguagem.ABA_INDISPONIVEL)
        return

    col_a, col_b, col_c = st.columns(3)
    idade = col_a.number_input("Idade (anos)", entrada.IDADE_MIN, entrada.IDADE_MAX, 40, 1,
                               key="perfil_idade")
    sexo = col_b.radio("Sexo", list(SEXOS), format_func=SEXOS.get, horizontal=True,
                       key="perfil_sexo")
    gestante = False
    if sexo == "F":
        gestante = col_c.checkbox("Gestante", key="perfil_gestante")
    st.markdown("**Comorbidades**")
    marcadas = {}
    colunas = st.columns(4)
    for i, (campo, feature) in enumerate(entrada.CAMPOS_COMORBIDADES.items()):
        marcadas[campo] = colunas[i % 4].checkbox(entrada.ROTULOS_COMORBIDADES[feature],
                                                  key=f"perfil_{campo}")

    bruta = {"idade_anos": idade, "sexo": sexo, "gestante": "sim" if gestante else "nao",
             **{c: "sim" if marcada else "nao" for c, marcada in marcadas.items()}}
    try:
        perfil = entrada.validar_perfil(bruta)
    except entrada.EntradaInvalida as erro:
        _mostrar_erros(erro)
        return

    res = servico.avaliar_perfil(a.e1, perfil)
    st.divider()
    if not res.estimavel:
        if pro:
            st.warning(f"Sem estimativa para este perfil: {res.motivo}.")
        else:
            st.warning(linguagem.SEM_ESTIMATIVA)
        return
    if not pro:
        _resultado_perfil_normal(a, res, bool(perfil.comorbidades))
        return

    col1, col2 = st.columns(2)
    col1.metric("Risco estimado (E1)", servico.porcentagem(res.risco))
    col1.caption(f"IC 95% (método delta): {_ic(res.ic)}")
    col2.metric("Sem comorbidades, mesma idade, sexo e gestação",
                servico.porcentagem(res.risco_base))
    col2.caption(f"IC 95%: {_ic(res.ic_base)} · faixa etária {res.faixa}")
    if perfil.comorbidades:
        st.markdown(f"O risco deste perfil é **{servico.numero(res.razao)} vezes** o do perfil "
                    f"sem comorbidades (IC 95%: {servico.numero(res.ic_razao[0])} a "
                    f"{servico.numero(res.ic_razao[1])}).")
        st.markdown("**Razão de chances (OR) de cada comorbidade marcada**, contra não ter a "
                    "comorbidade, na idade informada e com as demais ausentes:")
        st.table([
            {"Comorbidade": entrada.ROTULOS_COMORBIDADES[o["comorbidade"]],
             "OR": servico.numero(o["or"]),
             "IC 95%": f"{servico.numero(o['ic_inferior'])} a {servico.numero(o['ic_superior'])}"}
            for o in res.odds])
    else:
        st.caption("Nenhuma comorbidade marcada: este é o próprio perfil de comparação.")
    for aviso in res.avisos:
        st.caption(f"Aviso: {aviso}.")
    st.caption("Associação, não causa: o E1 descreve o modelo ajustado em 2022–2023, não "
               "efeitos de tratamento.")


# --- Aba Triagem -------------------------------------------------------------------------------

def _seletor(rotulo: str, chave: str, container) -> str:
    return container.selectbox(rotulo, list(NIVEIS), index=1, format_func=NIVEIS.get, key=chave)


def _resultado_triagem_normal(a: servico.Artefatos, res: servico.ResultadoTriagem) -> None:
    st.metric("Risco estimado", linguagem.um_em(res.risco))
    st.markdown(linguagem.frase_risco(res.risco))
    aviso = linguagem.aviso_subestimado(a.painel)
    if aviso:
        st.caption(aviso)
    if res.explicacao_indisponivel:
        st.info(linguagem.EXPLICACAO_INDISPONIVEL)
        return
    st.markdown("**O que mais pesou neste caso**")
    st.table([{"Fator": f.rotulo, "O que foi informado": f.valor,
               "Efeito": linguagem.efeito(f.aumenta)} for f in res.fatores])
    st.caption(linguagem.NAO_E_CAUSA)


def aba_triagem(a: servico.Artefatos, pro: bool) -> None:
    st.warning(f"**{AVISO}** Esta aba se parece com uma ferramenta clínica, mas não é: o "
               "resultado não deve orientar conduta.")
    st.markdown(FRASE_TRIAGEM)
    st.caption(RISCO_DE_QUE if pro else linguagem.COMO_LER)
    if a.m1 is None:
        st.info(a.erro_m1 if pro else linguagem.ABA_INDISPONIVEL)
        return

    st.markdown("**Perfil**")
    col_a, col_b, col_c = st.columns(3)
    idade = col_a.number_input("Idade (anos)", entrada.IDADE_MIN, entrada.IDADE_MAX, 40, 1,
                               key="triagem_idade")
    sexo = col_b.radio("Sexo", list(SEXOS), format_func=SEXOS.get, horizontal=True,
                       key="triagem_sexo")
    gestante = "nao"
    if sexo == "F":
        gestante = _seletor("Gestante", "triagem_gestante", col_c)
    bruta: dict = {"idade_anos": idade, "sexo": sexo, "gestante": gestante}
    st.markdown("**Comorbidades**")
    colunas = st.columns(4)
    for i, (campo, feature) in enumerate(entrada.CAMPOS_COMORBIDADES.items()):
        bruta[campo] = _seletor(entrada.ROTULOS_COMORBIDADES[feature], f"triagem_{campo}",
                                colunas[i % 4])
    st.markdown("**Sintomas iniciais**")
    colunas = st.columns(4)
    for i, (campo, feature) in enumerate(entrada.CAMPOS_SINAIS.items()):
        bruta[campo] = _seletor(entrada.ROTULOS_SINAIS[feature], f"triagem_{campo}",
                                colunas[i % 4])
    bruta["dias_ate_notificacao"] = st.number_input(
        "Dias entre o início dos sintomas e a notificação", entrada.DIAS_MIN, entrada.DIAS_MAX,
        2, 1, key="triagem_dias")

    try:
        caso = entrada.validar_caso(bruta)
    except entrada.EntradaInvalida as erro:
        _mostrar_erros(erro)
        return

    res = servico.avaliar_caso(a.m1, caso)
    st.divider()
    if not pro:
        _resultado_triagem_normal(a, res)
        return
    col1, col2, col3 = st.columns(3)
    col1.metric("Risco estimado (M1, calibrado)", servico.porcentagem(res.risco))
    col2.metric("Alto risco", "Sim" if res.alto_risco else "Não")
    col2.caption(f"Limiar congelado: risco ≥ {servico.porcentagem(res.limiar, 4)}. "
                 f"{servico.legenda_alto_risco(a.painel)}")
    col3.metric("Regra do protocolo (grupo B)", "Sim" if res.grupo_b_b2 else "Não")
    col3.caption("Regra B2: idade < 2 ou > 65 anos, gestante, alguma comorbidade, prova do "
                 "laço ou petéquias.")

    if res.explicacao_indisponivel:
        st.info("A explicação por fator não está disponível para este modelo.")
    else:
        st.markdown("**Fatores que mais pesaram neste caso** (os 5 de maior contribuição, "
                    "TreeSHAP exato):")
        st.table([
            {"Fator": f.rotulo, "Informado": f.valor,
             "Efeito": "aumentou o risco" if f.aumenta else "reduziu o risco",
             "Contribuição (log-odds)": f"{f.contribuicao:+.2f}".replace(".", ",")}
            for f in res.fatores])
        demais = f"{res.outros_fatores:+.2f}".replace(".", ",")
        st.caption(f"Fatores: {FRASE_SHAP}. Valores em log-odds do modelo, antes da "
                   f"calibração; os demais fatores somam {demais}.")
    if a.versao_m1:
        st.caption(f"Modelo: {a.versao_m1}. Sem IC por predição; a incerteza do modelo está no "
                   "relatório (IC bootstrap das métricas).")


def principal() -> None:
    st.set_page_config(page_title="Risco de dengue grave: demo acadêmica", layout="wide")
    st.title("Risco de dengue grave ou óbito por comorbidades")
    a = _artefatos(str(servico.pasta_modelos()), str(servico.pasta_relatorios()))
    modo = st.radio("Modo de exibição", list(linguagem.MODOS), format_func=linguagem.MODOS.get,
                    horizontal=True, key="modo")
    pro = modo == linguagem.MODO_PRO
    rotulos = ["Perfil (E1)", "Triagem (M1)"] if pro else [linguagem.ABA_PERFIL,
                                                           linguagem.ABA_TRIAGEM]
    perfil, triagem = st.tabs(rotulos)
    with perfil:
        aba_perfil(a, pro)
    with triagem:
        aba_triagem(a, pro)
    _painel_teste(a, pro)


principal()
