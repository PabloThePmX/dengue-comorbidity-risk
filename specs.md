# Spec — Risco de desfecho grave em dengue por perfil de comorbidades (SINAN/DataSUS)

> Status: **rascunho v0.10** — 2026-11-03. Revisão de boas práticas via Consensus (D-38 a D-41); orçamento de tempo por modelo (D-42), com Colab Pro como acelerador; Optuna (D-43); tabela de vazamento cobrindo as 121 colunas. Retorno do professor sobre o pré-projeto incorporado (D-32 a D-35); melhores pesos só pela validação (D-36, D-37). Itens de documento verificados; spec alinhado ao pré-projeto enviado ao professor (D-22 a D-25) e às exigências de entrega (D-26 a D-28); cronograma retirado (D-29), com marcos sem datas (D-31); dúvidas de CEP e licença retiradas (D-30). Nenhuma decisão pendente, mas D-02 pode reabrir conforme o primeiro check do profiling (`CLASSI_FIN`, §3.6). Restam `[VERIFY]` de dados e `[OPEN QUESTION]` (§3.20).
> Idioma: pt-BR (entregável acadêmico).

---

## 3.1 Resumo

Estimar, para um caso confirmado de dengue no Brasil, a probabilidade de evoluir para **dengue grave ou óbito pelo agravo**, usando dados do SINAN (DataSUS) de 2022–2024.
O foco principal é **explicar** quais comorbidades e combinações (hipertensão, diabetes, doença renal etc.) estão associadas a maior risco, ajustando por idade e sexo.
O foco secundário é **prever** esse risco no primeiro atendimento, para apoiar médicos na triagem e analistas de vigilância.
O resultado é comparado com a regra de estratificação de risco já usada pelo Ministério da Saúde, para mostrar se o ML acrescenta algo.

## 3.2 Problema e contexto

- **Dor hoje:** em epidemias (ex.: 2024), serviços recebem volume muito acima da capacidade. Priorizar quem deve ser acompanhado de perto é crítico.
- **Como é feito hoje:** o protocolo do Ministério da Saúde classifica pacientes em grupos de manejo (A/B/C/D). Verificado em 2026-11-01 em *Dengue: diagnóstico e manejo clínico — adulto e criança*, 6ª ed., MS, 2024 (versão eletrônica preliminar), §6.2 e fluxograma:
  - **Grupo B** = dengue sem sinais de alarme, com sangramento de pele espontâneo ou induzido (prova do laço), **ou** com condição clínica especial / risco social / comorbidade.
  - Condições listadas: lactentes (< 24 meses), gestantes, adultos > 65 anos, hipertensão ou outras doenças cardiovasculares graves, diabetes, DPOC, asma, obesidade, doenças hematológicas crônicas, doença renal crônica, doença ácido-péptica, hepatopatias e doenças autoimunes.
  - Hemograma é **obrigatório** no grupo B e "a critério médico" no grupo A.
  - Observação para o relatório: o protocolo considera asma, DPOC e obesidade fatores de risco, mas a ficha do SINAN não registra nenhum deles (D-18).
- **Desafio ao próprio projeto:**
  - A pergunta "quais combinações são mais perigosas?" é de **inferência**. Ela é respondida por regressão logística com interações e taxas por perfil, não exige ML complexo.
  - A pergunta "qual o risco deste paciente?" é de **predição**. Aqui o ML só se justifica se superar a regra do protocolo (baseline B2, §3.10) e a logística simples (B1).
  - Se o boosting não superar B1/B2, isso é um **resultado válido** e deve ser reportado como tal.
- **Objetivo declarado:** explicação primeiro, predição depois (D-01).

### Trabalhos relacionados e diferencial (D-25)

- **Rosa, Tavares e Recamonde-Mendoza (SBCAS 2026)**, [doi:10.5753/sbcas.2026.21367](https://doi.org/10.5753/sbcas.2026.21367). Lido no texto completo em 2026-11-01. É o trabalho mais próximo: SINAN nacional, sem exames laboratoriais, Random Forest.
  - **Dados:** 716.917 casos via Base dos Dados. Classes de alarme e grave vêm de 2014–2025; a classe de baixo risco vem **só de 2021**, escolhida para reduzir o desbalanceamento.
  - **Desenho:** multiclasse nas 3 categorias da OMS (baixo risco, alarme, grave). Split aleatório estratificado 85/15, CV aninhada de 5 dobras, Optuna, pesos de classe.
  - **Features:** 28, incluindo as **mesmas 7 comorbidades** deste projeto, sintomas, `LEUCOPENIA`, `LACO`, região de residência e hierarquia urbana (REGIC/IBGE).
  - **Resultados:** macro-F1 = 0,63 e acurácia = 0,76 no teste; recall de dengue grave = 40%. No SHAP, hipertensão, diabetes e doença renal aparecem como preditores positivos fortes de dengue grave.
  - **Limitações relevantes para nós:**
    - Amostragem dependente do desfecho: a classe se confunde com o ano. Qualquer feature ligada ao ano (região, epidemias locais, sorotipo) pode ganhar poder preditivo artificial, inclusive o ganho atribuído à hierarquia urbana.
    - Não há calibração, e a prevalência foi alterada pela amostragem; as probabilidades não representam risco real.
    - Não há validação externa. Os próprios autores a citam como trabalho futuro.
  - **Comparabilidade:** os números deles **não** se comparam diretamente aos nossos (multiclasse, prevalência artificial, macro-F1). Citar como contexto, não como alvo a bater.
- **Huang et al. (PLOS NTD 2020)**, [doi:10.1371/journal.pntd.0008960](https://doi.org/10.1371/journal.pntd.0008960). Lido via Consensus em 2026-11-01 (trechos do texto completo; `research/consensus-huang-trindade.md` (cópia local, fora do repositório: termos do Consensus)).
  - Hospital único em Taiwan, surto de DENV-2 de 2015: 798 pacientes, 138 graves.
  - Features: idade, sexo e exames qualitativos (NS1, IgM, IgG) do dia 1 de atendimento. **Sem comorbidades.**
  - Compara logística, RF, gradient boosting, SVC e rede neural. Melhor resultado: rede neural, ROC-AUC 0,83 e acurácia balanceada 0,75.
  - Limitações declaradas: retrospectivo, centro único, um sorotipo, possível viés de seleção de casos graves.
  - Uso no relatório: contraste. Depende de exame laboratorial, não usa comorbidade e não tem validação externa.
  - `[VERIFY]` O resumo do Consensus não traz o esquema de validação (split/CV) nem fala de calibração. Conferir no PDF se o relatório for citar esses pontos.
- **Trindade et al. (BJID 2024, v. 28, supl. 1)**, [doi:10.1016/j.bjid.2024.103821](https://doi.org/10.1016/j.bjid.2024.103821). Verificado via Consensus em 2026-11-01: **resumo de congresso**.
  - Revisão narrativa de **5 artigos** do PubMed (10 anos), sem método sistemático.
  - Conclui que gravidez, DM2, obesidade, doenças renais, idade < 12 anos e infecção secundária são fatores de risco para dengue grave.
  - Evidência fraca para sustentar sozinha o argumento central. No relatório, citar no máximo como complemento das meta-análises abaixo.
- **Meta-análises sobre comorbidade e gravidade** (encontradas via Consensus em 2026-11-01; lidos só os resumos). Substituem Trindade como base do argumento "comorbidade é fator de risco":
  - [Sangkaew et al., Lancet Infect Dis 2021](https://consensus.app/papers/details/00be11dc21125c09b83d58c00ccbcf69/): 150 estudos, preditores na fase febril. OR **bruto** para dengue grave: diabetes 4,38 (2,58–7,43), hipertensão 2,19 (1,36–3,53), doença renal 4,67 (2,21–9,88), doença cardiovascular 2,79 (1,04–7,50). Risco de viés moderado a alto por confundimento.
  - [Tsheten et al., Infect Dis Poverty 2021](https://consensus.app/papers/details/450b348261d65e4b86fa489ca4ef82d1/): 143 estudos. Diabetes OR 2,88 (1,72–4,81), doença renal OR 4,54 (1,55–13,31).
  - [Lima Chagas et al., Trop Med Int Health 2022](https://consensus.app/papers/details/8e17b3321f4c592aa9aafbb95e72ef87/): óbito por dengue, 18 estudos com medidas ajustadas. Diabetes OR 3,70 (1,20–11,43).
  - Ponte para o projeto: os OR da literatura são majoritariamente **brutos** e de estudos pequenos. E1 estima OR **ajustados** por idade e sexo, em milhões de casos, e testa **combinações**. Hipertensão é o caso típico de confundimento por idade.
  - `[VERIFY]` Pegar os DOIs e ler pelo menos Sangkaew et al. no texto completo antes de citar os números no relatório.

**Diferencial deste projeto** (reformula o do pré-projeto, que dizia que as comorbidades são "pouco exploradas como eixo central"; Rosa et al. já as usam e as destacam no SHAP):
1. **Combinações:** interações 2 a 2 entre comorbidades, com OR e IC 95% (E1, FR-05), e ranking com incerteza (FR-19). As meta-análises acima reportam comorbidades isoladas e, em geral, OR brutos.
2. **Risco absoluto calibrado por perfil** (FR-06), não só importância de feature.
3. **Comparação com a regra do protocolo do MS** (B2, §3.10).
4. **Validação externa temporal (2024) e geográfica (leave-one-region-out)** (D-08), com prevalência natural e todas as classes vindas dos mesmos anos.

## 3.3 Objetivos e não-objetivos

**Objetivos**
- Quantificar a associação entre cada comorbidade da ficha (e pares de comorbidades) e o desfecho grave/óbito, com IC 95%, ajustada por idade e sexo.
- Produzir uma **tabela de perfis**: risco estimado para pacientes-tipo (ex.: saudável, só hipertensão, diabetes + renal, 3+ comorbidades), por faixa etária.
- Treinar e comparar modelos preditivos para o momento do primeiro atendimento (M1).
- Entregar o que o professor exige (D-26): modelos serializados (E1 e M1), demo pública com duas abas e relatório TRIPOD+AI, apoiados por um pipeline reprodutível.

**Não-objetivos**
- **Doenças respiratórias** (asma, DPOC etc.): a ficha do SINAN não tem esse campo (verificado, §3.7). Limitação documentada no relatório (D-18).
- Linkagem com SIH/SIM ou qualquer outra base.
- Inferência **causal** ("hipertensão causa piora"). Só associação ajustada.
- Ferramenta clínica real. O app é demonstração acadêmica, sem validação clínica.
- Previsão de surtos / número de casos (série temporal).
- Uso de resultados laboratoriais e sinais de gravidade como preditores (§3.8).
- UF/região como **feature** (D-21). Região é usada só como subgrupo de avaliação e eixo da validação interna-externa.
- **Extras** (fora do escopo base): M2 pós-alarme (D-03) e análise de sensibilidade com 2017–2024 (D-08). CatBoost e MLP deixaram de ser extras em D-32.

## 3.4 Usuários e decisões apoiadas

`[ASSUMPTION]` Não há usuário clínico real; os usuários abaixo são hipotéticos, para guiar as escolhas de métrica.

| Usuário | Decisão que muda |
|---|---|
| Médico / enfermeiro na triagem | Quem recebe retorno precoce, reavaliação em 24–48 h ou observação. |
| Analista de vigilância / gestor | Quais perfis priorizar em campanhas e orientação (ex.: renais crônicos). |
| Banca / professor | Se o modelo acrescenta valor sobre a regra do protocolo. |

**Custo dos erros (D-14)**
- **Falso negativo** (diz "baixo risco" para quem evolui para grave/óbito): erro **muito mais caro**. Pode atrasar o reconhecimento de um paciente que vai piorar.
- **Falso positivo** (diz "alto risco" para quem não piora): custa monitoramento extra e ocupação do serviço.
- Consequência: o limiar prioriza recall alto. O recall mínimo será definido após o baseline (`[OPEN QUESTION]` Q-03).

## 3.5 Requisitos

### Funcionais

- **FR-01** — O pipeline MUST baixar os microdados SINAN-Dengue (Brasil, 2022–2024; D-04) direto do FTP do DataSUS (D-05) e salvá-los em Parquet com hash SHA-256 registrado, junto com o hash do `.dbc` original e a data de revisão do arquivo no DataSUS.
- **FR-02** — O pipeline MUST aplicar os filtros de população (§3.6) e gerar o alvo, emitindo um **fluxograma de exclusão** com a contagem de linhas após cada filtro.
- **FR-03** — O pipeline MUST executar os checks de qualidade de §3.7 e falhar com mensagem clara se algum check bloqueante falhar.
- **FR-04** — O pipeline MUST treinar e avaliar os baselines B0, B1 e B2 (§3.10).
- **FR-05** — O pipeline MUST ajustar a regressão logística com interações 2 a 2 entre comorbidades (§3.11) e reportar, para cada par, a interação **multiplicativa** (OR) e a **aditiva** (RERI e AP), com IC 95% e correção para comparações múltiplas (D-40).
- **FR-06** — O pipeline MUST gerar a tabela de perfis (§3.15) com risco calibrado e IC 95% para cada perfil.
- **FR-07** — O pipeline MUST treinar e comparar, para M1, os seis candidatos de §3.11 nas mesmas dobras (D-32): logística elastic net, XGBoost, Random Forest, CatBoost, MLP e TabFM. A busca de hiperparâmetros é registrada no MLflow; o TabFM é zero-shot e não tem busca.
- **FR-08** — O pipeline MUST calibrar as probabilidades e escolher o limiar de decisão usando **apenas** dados de validação.
- **FR-09** — O pipeline MUST avaliar o modelo final no conjunto de teste **uma única vez**, reportando as métricas de §3.12 com IC bootstrap e por subgrupo.
- **FR-10** — O projeto MAY expor uma CLI que recebe um CSV no schema de §3.15 e grava um CSV de predições. Rebaixado de MUST em D-26: a demo cumpre o papel de testar o modelo.
- **FR-11** — O projeto MUST publicar uma demo Streamlit (Streamlit Community Cloud), com aviso de uso acadêmico, em **duas abas** (D-27):
  - **Perfil:** risco de E1 para idade, sexo, gestação e comorbidades.
  - **Triagem:** risco calibrado de M1, com a classificação "alto risco" no limiar escolhido e os 5 fatores que mais aumentaram ou reduziram o risco daquele caso (SHAP local, D-35).
  - Detalhes em §3.15.
- **FR-12** — O modelo serializado MUST incluir metadados: versão do código, hash dos dados, config, data de treino e métricas de validação.
- **FR-13** — O pipeline SHOULD calcular SHAP interaction values para o modelo de árvore, em subamostra estratificada (§3.13).
- **FR-14** — O pipeline MAY treinar o modelo M2 (pós-sinais de alarme) — extra.
- ~~**FR-15** — O pipeline MAY treinar CatBoost e MLP — extra.~~ Absorvido por FR-07 em D-32: CatBoost e MLP passaram a ser obrigatórios.
- **FR-16** — O pipeline MAY repetir o desenho de §3.8 com dados de 2017–2024 como análise de sensibilidade (D-08) — extra.
- **FR-17** — O pipeline MUST gerar as predições fora da dobra da validação leave-one-region-out (§3.8) e usá-las para tuning, calibração e escolha do limiar.
- **FR-18** — O pipeline MUST gerar a análise descritiva da população final (D-23), só com dados de desenvolvimento (2022–23), que são os usados no treino:
  - Tabela de características por desfecho (`y = 0` vs `y = 1`): idade, sexo, gestação, raça/cor, cada comorbidade, nº de comorbidades.
  - Risco bruto de `y = 1`, com IC 95%, por comorbidade, por nº de comorbidades (0, 1, 2, 3+) e por faixa etária.
  - Gráficos comparativos desses riscos.
  - Células com < 10 casos não são publicadas (§3.12).
  - Os riscos brutos são descritivos. Eles **não** substituem E1 nem alimentam a tabela de perfis (D-10, D-20).
- **FR-19** — O pipeline MUST gerar o **ranking de comorbidades** pelo OR ajustado de E1 (efeito principal, ajustado por idade e sexo), com IC 95% (D-23). Duas comorbidades cujos IC se sobrepõem são marcadas como **sem ordem definida** entre si.
- **FR-20** — O projeto MUST entregar um relatório estruturado pelo checklist **TRIPOD+AI** ([Collins et al., BMJ 2024](https://doi.org/10.1136/bmj-2023-074819)) (D-28), com:
  - processo, decisões e resultados de E1 e M1, incluindo baselines e a comparação logística vs Random Forest;
  - apêndice A: registro de decisões (§3.16), com o que mudou desde o pré-projeto (D-22 a D-25);
  - apêndice B: fluxograma de exclusão (FR-02) e resultados do profiling;
  - apêndice C: "passos seguidos", uma cronologia das execuções exportada do MLflow (config, hash dos dados, métricas por execução);
  - apêndice D: revisão do profissional de saúde (FR-21), se houver.
- **FR-21** — O projeto SHOULD submeter os resultados a um profissional de saúde (médico, enfermeiro ou estudante da área) depois da avaliação no teste (Marco 5) (D-34). `[ASSUMPTION]` SHOULD, e não MUST, porque depende de conseguir alguém (Q-13).
  - O que é revisado: plausibilidade dos OR e do ranking de comorbidades (FR-19), tabela de perfis (FR-06), falsos negativos da análise de erros (§3.12) e uso da demo (FR-11).
  - As observações entram no relatório (apêndice D), com quem revisou (função, sem dados pessoais) e quando.
  - **Regra:** sugestões que exigiriam mudar o modelo **não** são aplicadas, porque o teste de 2024 já foi usado (§3.8). Elas entram como limitação e trabalho futuro.
- **FR-22** — O pipeline MUST guardar os melhores pesos encontrados **na validação** (D-36, D-37), nunca no teste:
  - **Modelos iterativos (XGBoost, CatBoost, MLP):** early stopping com restauração do melhor ponto (melhor nº de árvores / melhor época), monitorando a PR-AUC numa validação interna da dobra (§3.11). O melhor ponto e o modelo daquele ponto são salvos por dobra no MLflow.
  - **Busca de hiperparâmetros:** a melhor tentativa de cada modelo (config + artefato) é registrada no MLflow com o alias `melhor-validacao`. Tentativas piores não sobrescrevem a melhor.
  - **Modelos sem iteração (elastic net, Random Forest):** "melhor peso" = configuração da melhor tentativa. **TabFM:** não tem pesos treinados; nada a guardar além da subamostra de contexto e da semente.
  - **Retreino final:** sem validação sobrando em 2022–23, os modelos iterativos usam a **mediana** dos melhores pontos das 5 dobras, sem early stopping (D-37).
  - **O teste de 2024 nunca escolhe peso.** Se o resultado no teste for pior que o da validação, isso é reportado como resultado (drift, §3.8), e não motivo para trocar de peso.

### Não funcionais

- **NFR-01 (compute)** — Todo o pipeline MUST rodar tanto no Google Colab gratuito quanto no Colab Pro (D-44), com **orçamento de tempo por modelo** (D-42), e não um limite para o pipeline inteiro.
  - **Limites do Colab gratuito** (fontes secundárias, 2026; o FAQ do Google diz que os limites não são publicados e variam): sessão de até ~12 h, desconexão após ~90 min sem interação, GPU (em geral T4) não garantida, ~12 GB de RAM. A RAM e a GPU de fato obtidas são registradas em cada execução.
  - **Colab Pro / plano de estudante** (pesquisado em 2026-11-03; fontes secundárias, valores mudam):
    - **Como se obtém — varia por país** (pesquisado em 2026-11-03):
      - **Colab Pro grátis por 1 ano:** só para estudantes e docentes de instituições dos **EUA** ([anúncio do Google](https://blog.google/products-and-platforms/products/education/colab-higher-education/); [TalkAndroid, 07/2025](https://www.talkandroid.com/512277-google-collab-pro-free-education/)). Não vale para universidade brasileira.
      - **Planos Google AI para estudantes:** em 2025, estudantes no Brasil tiveram ofertas do **Google AI Pro** grátis (15 meses, inscrição até 30/06/2025; reaberta com 1 ano até 06/10/2025) ([MacMagazine](https://macmagazine.com.br/post/2025/05/21/estudantes-no-brasil-tem-acesso-gratis-ao-plano-google-ai-pro-por-15-meses/); [Canaltech](https://canaltech.com.br/inteligencia-artificial/google-libera-acesso-gratis-a-plano-de-ia-avancado-para-estudantes-por-1-ano/)). Na oferta de agosto de 2026, os EUA recebem AI Pro e os demais **140+ países** recebem **Google AI Plus** por 1 ano ([ETV Bharat, 20/08/2026](https://www.etvbharat.com/en/technology/google-launches-one-year-free-ai-plus-plan-for-indian-and-global-college-students-enn26082002492)); o Brasil não é citado nominalmente.
      - **O que o plano dá no Colab:** desde 22/09/2026, assinantes Google AI têm **prioridade** de acesso a aceleradores mais rápidos e máquinas mais potentes; só o Ultra tem execução em segundo plano e GPUs Premium. O anúncio oficial **não informa unidades de computação** por plano, e a liberação acontece aos poucos nos países com Colab ([Google Developers Blog, 22/09/2026](https://developers.googleblog.com/colab-is-now-part-of-your-google-ai-plan/)). Segundo uma fonte secundária, Plus e Pro têm os mesmos benefícios no Colab ([Pillitteri, 23/09/2026](https://pasqualepillitteri.it/en/news/17594/colab-google-ai-plans-premium-gpu)). Outra fonte cita 200 unidades/mês no AI Pro ([Inside, 09/2026](https://www.inside.com.tw/article/42497-google-ai-pro-colab-200-compute-units-a100-cli)), sem confirmação oficial.
      - **Colab Pro avulso:** 100 unidades/mês; as não usadas valem por 90 dias. Assinatura do Colab e plano Google AI se somam.
      - **Plano do Pablo (informado em 2026-11-03):** **Google AI Pro para estudantes**, com 75% de desconto (R$ 23,99/mês em vez de R$ 96,99), oferecido pelo próprio seletor de GPUs Premium do Colab ([página da oferta](https://one.google.com/ai-student?g1_landing_page=75), exige login). Fontes divergem sobre a duração: "até 4 anos" ([Canaltech](https://canaltech.com.br/inteligencia-artificial/google-ai-pro-gemini-de-graca-por-1-ano-brasil/)) ou 12 meses, com preço mantido até 28/02/2027 ([TecMundo](https://www.tecmundo.com.br/mercado/414909-fim-dos-15-meses-gratis-google-ai-pro-lanca-nova-promocao-para-estudantes.htm)). É uma assinatura **paga**, não gratuita.
      - **O que o plano dá no Colab** (confirmado pelo Pablo na página da oferta, 2026-11-03): **200 unidades de computação por mês**, acesso a aceleradores mais potentes, sessões mais longas e limites maiores do Gemini. Isso confirma a fonte secundária ([Inside](https://www.inside.com.tw/article/42497-google-ai-pro-colab-200-compute-units-a100-cli)).
      - **Folga do orçamento:** com 10 a 45 unidades por ciclo completo de modelos (ver abaixo), 200 unidades/mês cobrem cerca de 4 ciclos em A100 e mais de 10 em T4/L4.
      - `[VERIFY]` Depois de assinar: conferir no Colab (*Ambiente de execução → Ver recursos*) se o saldo aparece como 200 e quais GPUs ficam disponíveis, e se as unidades não usadas acumulam (no Colab Pro avulso, valem por 90 dias).
    - **Consumo medido em março de 2026** ([McCormick](https://mccormickml.com/2024/04/23/colab-gpus-features-and-pricing/); outras fontes dão valores maiores): T4 ≈ 1,2 unidade/h; L4 ≈ 1,7/h; A100 40 GB ≈ 5,4/h; A100 80 GB ≈ 6,8/h. GPU ociosa continua consumindo unidades.
    - **RAM:** a opção "High RAM" dá bem mais memória (até ~53 GB em uma fonte, sem confirmação de 2026). Com ela, Random Forest e as 5 dobras com todos os dados devem caber sem subamostra.
    - **Custo estimado do orçamento de modelos (≈ 8 h):** ~10 unidades em T4, ~14 em L4, ~45 em A100. Cabe com folga em 100 ou 200 unidades/mês, inclusive com 2 ou 3 reexecuções completas em T4/L4.
    - **Como usar `[ASSUMPTION]`:** o Pro é um **acelerador**, não muda os orçamentos de tempo da tabela abaixo (mantém a comparação justa entre modelos). L4 ou T4 para MLP e TabFM; CPU com High RAM para elastic net, Random Forest, XGBoost e CatBoost, que não precisam de GPU; A100 só se o TabFM exigir. Desconectar o ambiente ao fim de cada modelo, para não gastar unidades com GPU ociosa.
    - **Reprodutibilidade (D-44):** mesmo executado no Pro, o pipeline MUST continuar executável no Colab gratuito, ainda que mais devagar ou com subamostra na busca. Assim o professor ou outra pessoa consegue reproduzir sem assinatura.
  - **Orçamento por modelo** `[ASSUMPTION]` (relógio de parede, incluindo busca, as 5 dobras e o retreino final):

    | Modelo | Orçamento | Observação |
    |---|---|---|
    | Logística elastic net | 60 min | CPU. |
    | Random Forest | 90 min | CPU; subamostra de negativos se faltar memória (§3.9). |
    | XGBoost | 90 min | CPU (`hist`) ou GPU, se disponível. |
    | CatBoost | 90 min | CPU ou GPU. |
    | MLP | 90 min | GPU preferível. |
    | TabFM | 60 min | GPU; sem busca, só predição nas 5 dobras e no teste. |

    Total previsto ≈ 8 h, distribuídas em **sessões separadas, uma por modelo**. Cada sessão cabe com folga no limite de ~12 h, e uma queda do Colab perde no máximo o modelo em andamento.
  - **Regras do orçamento:**
    - A busca para no que vier primeiro: o tempo do orçamento ou 50 tentativas `[ASSUMPTION]` (§3.11).
    - Poda: uma tentativa claramente pior que a mediana depois das primeiras dobras é interrompida, para gastar o tempo nas promissoras.
    - A busca é **retomável**: o estado fica salvo no Drive (ex.: SQLite do Optuna), então uma desconexão não perde as tentativas já feitas. As melhores tentativas já ficam salvas pela FR-22.
    - Se nem uma tentativa completa (5 dobras) couber, a busca usa uma **subamostra estratificada pelo alvo** (mesma prevalência, sem corrigir desbalanceamento, D-38) de cada dobra `[ASSUMPTION]`. O retreino final e as predições fora da dobra do modelo escolhido usam todos os dados.
    - Cada execução registra no MLflow: tempo gasto, nº de tentativas concluídas e podadas, hardware (CPU/GPU, RAM). Modelos rápidos fazem mais tentativas no mesmo orçamento; o relatório mostra esse número junto do resultado.
  - **Por que orçamento por modelo** (verificado em 2026-11-02): em dado clínico grande, com poucas features e sinal forte, os métodos de busca dão ganhos parecidos entre si, e qualquer busca melhora a discriminação e a calibração do XGBoost em relação ao padrão ([Meaney et al., BMC Med Res Methodol 2025](https://consensus.app/papers/details/404aec96444654a2bc7ee5a2e2d000aa/)). Ou seja, uma busca modesta e igual para todos basta; não compensa gastar o tempo todo num modelo só. Orçamento fixo, poda e avaliação em subamostra são práticas recomendadas de otimização de hiperparâmetros ([Bischl et al., WIREs 2021](https://consensus.app/papers/details/3d8f7d0790ba5fc9959c3e3e5e22eb75/)).
- **NFR-02 (reprodutibilidade)** — Partindo de um checkout limpo + snapshot de dados com o hash registrado, a reexecução MUST reproduzir as métricas de teste com as mesmas 3 casas decimais.
- **NFR-03 (privacidade)** — Nenhum microdado (linha a linha) MUST ser versionado no repositório nem embarcado no app. O app MUST NOT armazenar as entradas do usuário.
- **NFR-04 (ética)** — Dados públicos e desidentificados (sem nome, CPF, endereço nem data de nascimento completa, mas com ano de nascimento, idade, sexo e município; §3.7). Nenhum trâmite de ética é previsto (D-30).
  - No relatório, a dispensa se apoia na Resolução CNS 510/2016, art. 1º, parágrafo único, inciso II ("informações de acesso público", Lei 12.527/2011), e não em "não haver coleta direta", como no pré-projeto. Os dados são chamados de "desidentificados", não "anonimizados".
- **NFR-05 (manutenibilidade)** — Código em módulos Python (não só notebooks), com testes unitários (pytest) para geração do alvo, filtros de população e decodificação de idade; lint com ruff.
- **NFR-06 (latência)** — `[ASSUMPTION]` O app SHOULD responder em < 1 s por perfil.

## 3.6 Formulação do problema de ML

- **Tipo:** classificação binária (com probabilidade calibrada como produto principal).
- **Unidade de predição:** uma notificação de caso confirmado de dengue (uma linha do SINAN).
  - `[VERIFY]` Taxa de duplicidade (mesma pessoa notificada mais de uma vez). Não há identificador pessoal; a deduplicação possível é por chave composta (ano de nascimento + idade + sexo + município + data de sintomas) — ver §3.7. Os microdados públicos não trazem `DT_NASC` (verificado em 2026-11-02 no arquivo de 2022), só `ANO_NASC`, o que deixa a chave mais fraca. Há também o campo `NDUPLIC_N`, marcação de duplicidade do próprio SINAN, medido no profiling.
- **População (D-06):** casos com classificação final = dengue, dengue com sinais de alarme ou dengue grave **e** evolução conhecida (cura ou óbito pelo agravo).
  - Excluídos: descartados, inconclusivos, outras arboviroses, óbito por outras causas, óbito em investigação, evolução ignorada/em branco.
- **Alvo (D-02):** `y = 1` se `CLASSI_FIN = dengue grave` **OU** `EVOLUCAO = óbito pelo agravo`; senão `y = 0`.
  - **Códigos nos dicionários oficiais (conferidos em 2026-11-01):**
    - Dicionário SINAN Online de dengue, rev. 2015: `CLASSI_FIN` 5 = descartado, 10 = dengue, 11 = dengue com sinais de alarme, 12 = dengue grave, 13 = chikungunya. `EVOLUCAO` 1 = cura, 2 = óbito pelo agravo, 3 = óbito por outras causas, 4 = óbito em investigação, 9 = ignorado. `CRITERIO` 1 = laboratório, 2 = clínico-epidemiológico, 3 = em investigação.
    - Dicionário de dengue publicado no portal de dados abertos do MS (arquivo de 2024): `EVOLUCAO` igual ao de 2015, mas `CLASSI_FIN` aparece como branco/0/9 = ignorado, 1 = confirmado, 2 = descartado, 8 = inconclusivo, e `CRITERIO` ganha 3 = clínico. **O mesmo documento**, nas regras dos campos `ALRM_*` e `GRAV_*`, ainda cita "Classificação = 11 / 12". Ou seja, o dicionário de 2024 se contradiz.
  - `[VERIFY]` **Bloqueante, primeiro item do profiling:** contar os valores de `CLASSI_FIN` em cada ano (2022, 2023, 2024). Se aparecer 10/11/12, a regra acima vale. Se aparecer 1/2/8, a definição de "dengue grave" precisa ser refeita (ex.: via campos `GRAV_*` preenchidos), e D-02 volta para decisão.
  - Indício a favor de 10/11/12 (não substitui o profiling): Rosa et al. (SBCAS 2026, §3.2) separaram as 3 categorias da OMS em 2014–2025 a partir do SINAN via Base dos Dados. A Base dos Dados pode ter recodificado o campo, então o check continua bloqueante.
  - Contexto: nas notas do portal, o MS define "casos graves" como **dengue com sinais de alarme + dengue grave**. O alvo deste projeto (D-02) é mais estrito (só dengue grave + óbito). Ao comparar com números oficiais no relatório, explicitar essa diferença.
  - **Divergência do pré-projeto (D-22):** o pré-projeto enviado ao professor define agravamento como hospitalização, sinais de alarme, dengue grave ou óbito (de `EVOLUCAO`, `CLASSI_FIN` e `HOSPITALIZ`). O spec mantém o alvo estrito. O relatório MUST ter um parágrafo explicando a mudança e os dois motivos:
    - **Hospitalização é circular:** a decisão de internar depende da conduta médica, que já usa comorbidade como critério (§3.2), e da disponibilidade de leitos. Parte da associação "comorbidade → hospitalização" mediria a conduta, não a evolução do paciente.
    - **Sinais de alarme são um estado intermediário:** eles indicam risco de progressão, não um desfecho. Também são o ponto de partida do M2.
  - Casos de borda: óbito pelo agravo com classificação "dengue" (sem grave) → `y = 1`. Dengue grave com evolução em branco → excluído pela regra de população.
- **Momento da predição (D-03):**
  - **M1 — primeiro atendimento (base):** só informação disponível na notificação: perfil do paciente, comorbidades, sintomas iniciais. Sinais de alarme e gravidade ficam de fora.
  - **M2 — após sinais de alarme (extra):** M1 + campos `ALRM_*`. Responde "dado que já apareceram sinais de alarme, vai virar grave/óbito?".
    - **Restrição obrigatória (do dicionário):** os campos `ALRM_*` só são habilitados quando `CLASSI_FIN` = 11 ou 12. Em casos com `CLASSI_FIN` = 10, eles ficam em branco por regra do sistema. Se M2 incluísse esses casos, "campo preenchido vs. em branco" revelaria a classificação final. Por isso a população de M2 é **só** `CLASSI_FIN` ∈ {11, 12}, com `y = 1` se 12 ou óbito pelo agravo.
  - Em **nenhum** dos dois entram sinais de gravidade (`GRAV_*`): eles definem "dengue grave" e seriam o próprio rótulo.
- **Fonte e qualidade do rótulo:** classificação feita pela vigilância no encerramento do caso.
  - Ruído conhecido: subnotificação de casos leves, encerramento por critério clínico-epidemiológico, variação de qualidade entre UFs.
  - Óbitos passam por investigação, o que pode deixar suas fichas **mais completas** que as de casos leves — ver risco de vazamento em §3.8.

## 3.7 Dados

- **Fonte:** SINAN — Dengue (agravo `DENG`), microdados públicos do DataSUS, baixados direto do FTP oficial (D-05): `ftp.datasus.gov.br/dissemin/publicos/SINAN/DADOS/FINAIS/DENGBR{AA}.dbc`.
  - Verificado em 2026-11-02: os arquivos de 2022, 2023 e 2024 estão em `FINAIS` (não em `PRELIM`). Datas de revisão no FTP: 2022 = 19/03/2026, 2023 = 17/03/2026, 2024 = 27/02/2026. Ou seja, o DataSUS revisa arquivos "finais" anos depois; o hash e a data de revisão são registrados no manifesto (§3.14).
  - Leitura do `.dbc` (DBF comprimido) com `pyreaddbc` + `dbfread`, versões pinadas no `uv.lock` (D-16).
- **Licença / acesso:** verificado em 2026-11-01 na [página do dataset Sinan/Dengue](https://dadosabertos.saude.gov.br/dataset/arboviroses-dengue). O portal declara, para todo o site, licença **Creative Commons Atribuição-SemDerivações 3.0**; a página do dataset não tem licença própria. Autoria: CGARB/DEDT/SVSA/MS e CGIAE/DAENT/SVSA/MS. Regra do projeto: citar a fonte e não redistribuir os microdados (NFR-03).
- **Notas oficiais do dataset que afetam o projeto** (mesma página):
  - Para série histórica, o MS usa bases **congeladas** por ano; os dados mais recentes mudam diariamente. Por isso o hash do snapshot (§3.14) é obrigatório.
  - **Espírito Santo:** desde 2020 o estado usa o e-SUS Vigilância em Saúde, e o portal considera para dengue no ES só os dados do Sinan Online. `[VERIFY]` No profiling, comparar o volume de casos do ES com o de outros estados: provável sub-representação, a reportar como lacuna de cobertura.
- **Período e cobertura (D-04):** Brasil, 2022–2024. 2017–2024 só na análise de sensibilidade extra (FR-16).
- **Tamanho:** `[VERIFY]` Linhas por ano antes/depois dos filtros; número de positivos por ano. Esperado: milhões de linhas em 2024 (ano de epidemia recorde) — só o profiling confirma.
- **Dicionários de dados:**
  - [Dicionário de dengue do portal de dados abertos do MS](https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SINAN/Dengue/dic_dados_dengue.pdf) (recurso criado em 22/02/2024, atualizado em 22/03/2024) — o mais recente, mas contraditório em `CLASSI_FIN` (§3.6).
  - [Dicionário SINAN Online — Dengue/Chikungunya (MS/GT-SINAN, rev. 2015)](https://app.wiki.saude.es.gov.br/vigilancia/microdados/dic_dados_dengue.pdf).
  - [Dicionário da notificação individual — SINAN Net v5.0 (rev. nov/2018)](https://rfsaldanha.github.io/sis/assets/sinan/agravos/NINDIN_DIC_DADOS.pdf) (cópia não oficial) — campos de idade, sexo, gestação e raça/cor.
  - Regra geral: **os dados mandam.** Quando dicionário e dados divergirem, vale o que o profiling mostrar, e a divergência é documentada.
- **Comorbidades disponíveis (item 34 da ficha, "Doenças pré-existentes")** — verificado em 2026-10-19 nos metadados do PySUS (biblioteca usada na época) e em 2026-11-01 nos dois dicionários:
  `DIABETES`, `HEMATOLOG` (doenças hematológicas), `HEPATOPAT` (hepatopatias), `RENAL` (doença renal crônica), `HIPERTENSA` (hipertensão arterial), `ACIDO_PEPT` (doença ácido-péptica), `AUTO_IMUNE` (doenças autoimunes).
  **Não há campo de doença respiratória.**
- **Codificação das comorbidades e dos sinais clínicos:** verificado em 2026-11-01. Os dois dicionários listam só **1 = sim, 2 = não**, como "campo obrigatório", **sem** a categoria 9 = ignorado.
  - `[VERIFY]` No profiling: quais valores aparecem de fato (branco, 9, outros?) e com que frequência.
  - Consequência para D-07: o 3º nível passa a ser "ausente/fora do domínio" (branco ou qualquer valor ≠ 1/2), e não "ignorado" declarado. O tratamento continua o mesmo.
- **Demografia** (dicionário da notificação individual, verificado em 2026-11-01):
  - `NU_IDADE_N`: 1º dígito = unidade (1 = hora, 2 = dia, 3 = mês, 4 = ano), restante = valor. Ex.: 3009 = 9 meses, 4018 = 18 anos. Calculada a partir da data de nascimento quando houver. Os microdados públicos não trazem `DT_NASC`, só `ANO_NASC` (verificado em 2026-11-02).
  - `CS_SEXO`: M, F, I = ignorado.
  - `CS_GESTANT`: 1–3 = 1º–3º trimestre, 4 = idade gestacional ignorada, 5 = não, 6 = não se aplica, 9 = ignorado. "Gestante" no projeto = 1–4 `[ASSUMPTION]`.
  - `CS_RACA`: 1 = branca, 2 = preta, 3 = amarela, 4 = parda, 5 = indígena, 9 = ignorado.
- **Missingness:** `[VERIFY]` Taxa de "ignorado"/branco por comorbidade, por ano, por UF e **por valor do alvo** (crítico para o risco de vazamento de §3.8).
- **Vieses conhecidos:**
  - Subnotificação de casos leves → o risco estimado é condicional a "ser notificado e confirmado", não à população infectada.
  - Confirmação laboratorial depende de acesso a exame (viés regional).
  - **Mudança de sorotipo:** o DENV-3, ausente por anos, voltou a circular em 2023–2024. Até 13/12/2023 havia 130 casos de DENV-3 confirmados em 11 estados, numa população muito suscetível ([Viruses/MDPI 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC10974589); [São Paulo, PubMed 39848015](https://pubmed.ncbi.nlm.nih.gov/39848015/)). Verificado em 2026-11-01 (resumos). É uma fonte plausível de drift entre treino (2022–23) e teste (2024).
  - **Subnotificação na COVID (2020–21):** em 19 de 25 estados, houve menos casos que o esperado em 2020, e a diferença foi explicada principalmente por subnotificação ([Martinelli/Roster et al., PLOS NTD 2024](https://consensus.app/papers/details/7900fddd46c15471b49d6525ff752d3c/)). Verificado em 2026-11-01 (resumo). Reforça deixar 2017–2024 só como sensibilidade (FR-16).
- **Checks de qualidade (FR-03):**
  - Bloqueantes: schema esperado presente em todos os anos; alvo sem valores fora do domínio; idade decodificada em [0, 120].
  - Alertas: data de primeiros sintomas > data de notificação; gestante com sexo masculino; taxa de "ignorado" > 50% em alguma comorbidade numa UF/ano.
  - Duplicatas por chave composta — reportar taxa; `[OPEN QUESTION]` Q-04 se remove ou só reporta.
- **Dados pessoais:** microdados são anonimizados, mas combinações raras (idade + município + data) podem identificar pessoas. Por isso não se publica nada linha a linha (NFR-03), e a tabela de perfis só reporta células com contagem mínima (§3.12).

## 3.8 Split e vazamento

### Estratégia de split — D-08: temporal + validação interna-externa por região

| Etapa | Dados | Uso |
|---|---|---|
| **Desenvolvimento** | 2022–2023, todas as regiões | Validação cruzada **leave-one-region-out** (5 dobras: Norte, Nordeste, Centro-Oeste, Sudeste, Sul). Em cada dobra, treina em 4 regiões e prediz a 5ª. |
| Tuning | Predições fora da dobra (2022–23) | Hiperparâmetros escolhidos pela PR-AUC média entre as 5 dobras (§3.11). |
| Calibração e limiar | Predições fora da dobra (2022–23), agrupadas | Calibrador (isotônica/Platt) e limiar ajustados nessas predições (§3.12). |
| **Modelo final** | 2022–2023 completo | Retreino com os hiperparâmetros escolhidos; aplica o calibrador e o limiar da etapa anterior. |
| **Teste (congelado)** | 2024 | Avaliado **uma única vez**, no fim (FR-09). Conta como validação externa temporal. |

Por que esse desenho (evidência via Consensus, 2026-10-19 — análise completa em `research/consensus-split-temporal.md` (cópia local, fora do repositório: termos do Consensus); reforço em 2026-11-03):
- Para modelos de ML, validação cruzada estima o desempenho melhor que a correção de otimismo por bootstrap, que superestima a AUC em modelos não paramétricos ([Zhang et al., J Clin Epidemiol 2025](https://consensus.app/papers/details/11194399c43055c2934748a9267f5596/); [Coley et al., BMC Med Res Methodol 2023](https://consensus.app/papers/details/25a2cb5ca5d35d4b8150140dbc335023/), Random Forest em 9,6 mi de registros).
- Split aleatório é desaconselhado mesmo com muitos dados; a validação interna-externa (deixar de fora uma região ou período por vez) e a validação temporal são as preferidas, com o modelo final ajustado sobre todos os dados de desenvolvimento ([Steyerberg & Harrell, J Clin Epidemiol 2016](https://doi.org/10.1016/j.jclinepi.2015.04.005); [Collins et al., BMJ 2024](https://doi.org/10.1136/bmj-2023-074819)).
- Drift temporal é comum em modelos clínicos, e a **calibração** piora com mais frequência que a discriminação ([Guo et al., Appl Clin Inform 2021](https://doi.org/10.1055/s-0041-1735184)). Por isso testar em 2024, ano de epidemia, é informativo.
- Na literatura de dengue, a validação externa é rara e o risco de viés é alto (112/146 estudos) ([Delpino et al., IJID 2026](https://doi.org/10.1016/j.ijid.2026.108879); [Díaz-Arocutipa et al., AJTMH 2025](https://doi.org/10.4269/ajtmh.24-0653)).
- `[VERIFY]` Os artigos foram selecionados e resumidos pelo agente do Consensus; ler pelo menos Steyerberg & Harrell e Collins (parte 1) no texto completo antes de citar no relatório.

Opções descartadas (registradas em D-08): split aleatório estratificado com todos os anos (esconde o drift e superestima o desempenho); corte dentro de 2024 (confundido com sazonalidade); treino só em 2022 (desperdiça 2023); 2017–2024 como desenho principal (subnotificação de 2020–21 na pandemia de COVID, §3.7) — fica como sensibilidade extra (FR-16).

**Tamanho do teste.** Teste grande é vantagem: o que importa é o número de **eventos**. A regra prática é ≥ 100 eventos e 100 não-eventos, com ~200/200 para avaliar calibração com precisão; o cálculo específico de [Riley et al. (Stat Med 2021)](https://doi.org/10.1002/sim.9025) é preferível a regras fixas.
- `[VERIFY]` Número de eventos em 2024 no total e **por subgrupo** de §3.12. Subgrupos com < 100 eventos são reportados com aviso de IC largo, sem conclusões.
- `[VERIFY]` Número de eventos por região em 2022–23 (cada dobra precisa de eventos suficientes para calibração).

Regras gerais:
- Todo pré-processamento (imputação, encoding, calibração) é ajustado só nos dados de desenvolvimento, dentro de cada dobra.
- `[ASSUMPTION]` Ano e semana epidemiológica **não** entram como features: com split temporal, o modelo não pode extrapolar um ano que nunca viu.
- UF/região **não** entram como features (D-21): em leave-one-region-out, a região deixada de fora nunca apareceria no treino, e as predições fora da dobra não representariam o modelo final.
- Limitação conhecida: tuning e calibração usam as mesmas predições fora da dobra, o que pode deixar as métricas de desenvolvimento um pouco otimistas. Por isso o teste de 2024 continua intocado.

### Revisão de vazamento (por grupo de campos)

Nomes de campo conferidos nos dicionários em 2026-11-01. Grafia no arquivo real (ex.: `PETEQUIA_N` vs. `PETÉQUIA_N`, maiúsculas/minúsculas) a confirmar no primeiro download.

| Campo(s) | Disponível em M1? | Decisão | Motivo |
|---|---|---|---|
| Idade (`NU_IDADE_N`, decodificada), sexo (`CS_SEXO`), gestação (`CS_GESTANT`) | Sim | Entra | Perfil do paciente. |
| Raça/cor (`CS_RACA`), escolaridade (`CS_ESCOL_N`) | Sim | `[OPEN QUESTION]` Q-05 | Disponíveis, mas alto "ignorado" e risco de proxy socioeconômico; decidir após profiling. |
| UF / região de residência (`SG_UF`, `ID_MN_RESI`) | Sim | **Fora como feature** (D-21) | Incompatível com leave-one-region-out; usada como subgrupo e eixo da validação. |
| 7 comorbidades do item 34 (`DIABETES`, `HEMATOLOG`, `HEPATOPAT`, `RENAL`, `HIPERTENSA`, `ACIDO_PEPT`, `AUTO_IMUNE`) + nº de comorbidades (derivada) | Sim | Entra | Objeto central do estudo. |
| Sintomas iniciais (`FEBRE`, `MIALGIA`, `CEFALEIA`, `EXANTEMA`, `VOMITO`, `NAUSEA`, `DOR_COSTAS`, `CONJUNTVIT`, `ARTRITE`, `ARTRALGIA`, `DOR_RETRO`, `PETEQUIA_N`) | Sim | Entra | Coletados na notificação. |
| `LEUCOPENIA`, `LACO` (prova do laço) | Sim | Entra `[ASSUMPTION]` | Ambos estão no item 33 da ficha ("sinais clínicos ou achados laboratoriais inespecíficos"), campo obrigatório 1/2. Ressalva: o hemograma só é obrigatório no grupo B do protocolo, então "não" em leucopenia pode significar "não foi feito". Documentar como limitação. |
| Dias entre início dos sintomas e notificação (`DT_NOTIFIC` − `DT_SIN_PRI`; as datas em si não entram) | Sim | Entra `[ASSUMPTION]` | Conhecido na notificação; proxy de busca por atendimento. |
| Resultados laboratoriais: sorologia (`DT_SORO`, `RESUL_SORO`), NS1 (`DT_NS1`, `RESUL_NS1`), isolamento viral (`DT_VIRAL`, `RESUL_VI_N`), PCR (`DT_PCR`, `RESUL_PCR_`), `SOROTIPO`, histopatologia (`HISTOPA_N`), imuno-histoquímica (`IMUNOH_N`) | **Não** | Fora | Chegam dias depois. |
| `CRITERIO` (laboratorial vs clínico-epidemiológico) | **Não** | Fora | Definido no encerramento. |
| `HOSPITALIZ`, data de internação (`DT_INTERNA`) | **Não** | Fora | Posterior à triagem e quase um desfecho. |
| Sinais de alarme (`ALRM_*`, `DT_ALRM`) | Não | Fora em M1; entra só em M2, com população restrita a `CLASSI_FIN` ∈ {11, 12} | Definem o momento M2. Só são habilitados para 11/12, então o preenchimento revela a classe (§3.6). |
| Sinais de gravidade (`GRAV_*`, `DT_GRAV`) | Não | **Fora sempre** | Definem o rótulo "dengue grave". |
| `CLASSI_FIN`, `EVOLUCAO`, `DT_OBITO`, `DT_ENCERRA` | Não | Fora | São o rótulo ou derivados dele. |
| Classificação antiga de febre hemorrágica (FHD): `MANI_HEMOR`, `EPISTAXE`, `GENGIVO`, `METRO`, `PETEQUIAS`, `HEMATURA`, `SANGRAM`, `LACO_N`, `PLASMATICO`, `EVIDENCIA`, `PLAQ_MENOR`, `CON_FHD`, `COMPLICA` | Não | **Fora sempre** | Manifestações hemorrágicas, extravasamento plasmático e plaquetopenia são critérios de gravidade: proxies do rótulo. Também tendem a ser preenchidos só em casos investigados (vazamento por completude). **Atenção:** `PETEQUIAS` e `LACO_N` são campos diferentes de `PETEQUIA_N` e `LACO` do item 33, que entram em M1. |
| Exames de chikungunya e PRNT: `DT_CHIK_S1`, `DT_CHIK_S2`, `RES_CHIKS1`, `RES_CHIKS2`, `DT_PRNT`, `RESUL_PRNT` | Não | Fora | Resultados laboratoriais; chegam depois da triagem (mesmo motivo da linha de exames). |
| Investigação e local de infecção: `DT_INVEST`, `TPAUTOCTO`, `COUFINF`, `COPAISINF`, `COMUNINF`, `DOENCA_TRA`, `CLINC_CHIK` | Não | Fora | Preenchidos na investigação ou no encerramento, depois da triagem. |
| Unidade e local de notificação: `ID_UNIDADE`, `ID_MUNICIP`, `SG_UF_NOT`, `ID_REGIONA`, `UF`, `MUNICIPIO` | Sim | Fora | A unidade notificadora é um proxy do tipo de serviço: casos notificados por hospital tendem a ser mais graves, então ela vazaria a gravidade. A geografia já está fora por D-21. |
| Administrativos e de sistema: `TP_NOT`, `ID_AGRAVO`, `NU_ANO`, `SEM_NOT`, `SEM_PRI`, `ID_PAIS`, `ID_RG_RESI`, `DT_DIGITA`, `TP_SISTEMA`, `NDUPLIC_N`, `CS_FLXRET`, `FLXRECEBI`, `MIGRADO_W` | — | Fora | Sem conteúdo clínico. `DT_DIGITA` é posterior à notificação; semana epidemiológica fora pela mesma razão do ano (§3.8); `TP_SISTEMA` e `NDUPLIC_N` são usados só no profiling (cobertura do ES e duplicatas). |
| Ocupação (`ID_OCUPA_N`) | Sim | Fora `[ASSUMPTION]` | Alta ausência e códigos genéricos (Rosa et al. removeram pelo mesmo motivo, §3.2). Reavaliar se o profiling mostrar preenchimento razoável. |
| Ano de nascimento (`ANO_NASC`) | Sim | Fora | Redundante com a idade decodificada; usado só para checar a decodificação e na chave de duplicatas. Os microdados não trazem `DT_NASC`. |

Cobertura da tabela: conferida em 2026-11-02 contra as **121 colunas** do arquivo `DENGBR22.dbc`. Toda coluna do arquivo aparece em alguma linha acima; as que não estão marcadas "Entra" ficam fora do modelo.

**Vazamento sutil — completude da ficha.** Óbitos e casos graves são investigados, então suas comorbidades tendem a vir preenchidas, enquanto casos leves ficam mais vezes com "ignorado". Se isso acontecer, a categoria "Ignorado" vira um marcador indireto de "não grave".
- Check obrigatório no profiling: taxa de "ignorado" por comorbidade × alvo.
- Se a diferença for grande: `[OPEN QUESTION]` Q-06 — análise de sensibilidade (modelo só com casos de comorbidades preenchidas) e discussão no relatório.

## 3.9 Features e pré-processamento

- **Lista de features:** campos marcados "Entra" na tabela de §3.8.
- **Idade:** decodificar `NU_IDADE_N` pela regra verificada em §3.7 (1º dígito = unidade; converter tudo para anos fracionários), com teste unitário cobrindo 1xxx, 2xxx, 3xxx e 4xxx. Usar idade contínua (splines na logística) e faixas para perfis e subgrupos.
  - `[ASSUMPTION]` Faixas: 0–4, 5–14, 15–39, 40–59, 60–79, 80+.
- **Comorbidades:** categóricas de 3 níveis (Sim / Não / Ausente) — D-07; "Ausente" = branco ou valor fora de 1/2 (§3.7). One-hot na logística; nativo/ordinal nos modelos de árvore.
- **Sintomas:** mesmo esquema de 3 níveis `[ASSUMPTION]` (consistência com D-07).
- **UF/região:** não é feature (D-21). Guardada no dataset só para dobras de validação e subgrupos.
- **Escalonamento:** só para logística/MLP (variáveis contínuas). Árvores não precisam.
- **Outliers:** idade fora de [0, 120] → check bloqueante (FR-03); atraso de notificação > 60 dias truncado em 60 `[ASSUMPTION]`.
- **Desbalanceamento (D-12, revisado em D-38):** **sem correção.** Os modelos treinam com a prevalência natural, sem pesos de classe, subamostragem ou SMOTE. O recall é controlado pelo limiar (F2, §3.12), e a calibração posterior (isotônica ou Platt) continua nas predições fora da dobra. Motivo: corrigir o desbalanceamento não melhora AUROC nem AUPRC e piora a calibração, às vezes de forma que a recalibração não conserta (van den Goorbergh et al., JAMIA 2022; Carriero et al., Stat Med 2024 — síntese em `research/consensus-boas-praticas.md` (cópia local, fora do repositório: termos do Consensus)). Exceção: a subamostra de negativos do Random Forest (§3.11), só por memória, com correção de probabilidade e verificada pela calibração.
- **Implementação:** um único `sklearn.Pipeline` / `ColumnTransformer` por modelo, salvo inteiro no artefato (FR-12). Nada de transformação ad hoc fora do pipeline.

## 3.10 Baselines

Todos obrigatórios (FR-04). Todos os modelos são julgados contra eles.

- **B0 — trivial:** prevê a prevalência do treino para todos. PR-AUC de B0 = prevalência (piso absoluto).
- **B1 — logística simples:** efeitos principais (idade em splines, sexo, gestação, 7 comorbidades, nº de comorbidades), sem interações.
- **B2 — regra do protocolo:** "alto risco" se o caso cumprir qualquer critério do grupo B do protocolo do MS (6ª ed., 2024; §3.2) que exista na ficha. Mapeamento `[ASSUMPTION]`, a revisar pelo grupo:
  - idade < 24 meses **ou** > 65 anos;
  - gestante (`CS_GESTANT` 1–4);
  - ≥ 1 das 7 comorbidades = 1;
  - `LACO` = 1 (sangramento induzido) **ou** `PETEQUIA_N` = 1 (sangramento de pele espontâneo).
  - Fora do mapeamento, por não existirem na ficha: DPOC, asma, obesidade, outras doenças cardiovasculares e risco social.
  - É uma regra binária: entra na comparação de recall/precisão no limiar, não de PR-AUC.

## 3.11 Modelagem

**Modelo explicativo (objetivo principal)**
- **E1 — logística com interações:** B1 + interações 2 a 2 entre as 7 comorbidades (21 termos) + interação comorbidade × idade (spline) para hipertensão e diabetes `[ASSUMPTION]`. A idade entra contínua também na interação; as faixas servem só para relatório e subgrupos (D-41), porque categorizar preditores contínuos piora o modelo ([Collins et al., Stat Med 2016](https://consensus.app/papers/details/2bfae82d18cf5de2b57622aed743abc3/)).
- **Interação aditiva (D-40):** para cada par de comorbidades, além do OR da interação (escala multiplicativa), reportar o **RERI** (excesso de risco relativo devido à interação) e o **AP** (proporção atribuível à interação), com IC 95% por método delta ou bootstrap.
  - Por quê: a escala aditiva responde à pergunta de saúde pública ("essa combinação acrescenta casos além da soma das duas condições?"), e uma interação pode ser significativa numa escala e não na outra. Síntese das referências (Knol & VanderWeele; Li & Chambless) em `research/consensus-boas-praticas.md` (cópia local, fora do repositório: termos do Consensus).
  - RERI e AP saem do mesmo modelo E1 (ajustado por idade e sexo), comparando "só A", "só B" e "A e B" contra "nenhuma das duas".
- Só se reportam interações com **≥ 10 eventos** (y = 1) na célula combinada `[ASSUMPTION]`.
- Correção para comparações múltiplas: Benjamini-Hochberg (FDR 5%) `[ASSUMPTION]`.
- Com milhões de linhas, quase tudo fica "estatisticamente significativo". O relatório interpreta **tamanho de efeito (OR) e IC**, não p-valor.

**Modelos preditivos (M1)**
| Modelo | Status | Motivo |
|---|---|---|
| Logística elastic net | Obrigatório | Pedido do professor. Mesmas features de B1 mais as interações de E1; a penalização L1 + L2 lida com muitas interações correlacionadas. **Só para predição:** coeficientes penalizados são viesados de propósito e não têm IC clássico, por isso E1 continua sem penalização. |
| XGBoost | Obrigatório | Estado da arte em dados tabulares; pedido do professor. Fecha Q-07. |
| Random Forest | Obrigatório | Comparação clássica (pré-projeto); pode exigir subamostra de negativos no Colab (com correção de probabilidade). |
| CatBoost | Obrigatório | Categóricas nativas; pedido do professor. |
| MLP | Obrigatório | Pedido do professor e do grupo. Raramente vence boosting em tabular; se não vencer, é resultado válido. Exige escalonamento (§3.9). |
| TabFM (Google Research) | Obrigatório | Modelo de fundação tabular zero-shot; pedido do professor. Restrições abaixo. |

**TabFM — restrições** (verificado em 2026-11-02 em fontes de lançamento: [blog do Google Research](https://research.google/blog/introducing-tabfm-a-zero-shot-foundation-model-for-tabular-data/), [Enterprise DNA](https://enterprisedna.co/resources/news/google-tabfm-zero-shot-tabular-data-enterprise-analytics-2026))
- Lançado em 30/06/2026. Não há treino: as linhas de treino entram como **contexto** na hora da predição (aprendizado em contexto), e a arquitetura alterna atenção entre linhas e colunas.
- Código sob Apache 2.0; pesos no Hugging Face com licença **não comercial**. `[VERIFY]` Confirmar no model card que uso acadêmico está coberto.
- `[VERIFY]` No model card: limite de linhas de contexto e de features (uma fonte secundária cita até 500 features e 10 classes) e velocidade de predição.
- Com milhões de linhas no desenvolvimento, o contexto será uma **subamostra estratificada** do treino de cada dobra, com tamanho definido pelo limite verificado. O relatório registra que o TabFM vê só essa subamostra.
- Precisa de GPU (Colab). Avaliado nas mesmas dobras leave-one-region-out e calibrado igual aos outros (FR-08, FR-17).
- Os resultados no TabArena são do próprio Google, ainda sem verificação independente; não citar como evidência de superioridade.

- **Busca de hiperparâmetros: Optuna (D-43)**, versão pinada no `uv.lock` quando a modelagem começar. Sampler TPE com semente fixa; poda com `MedianPruner`, reportando a PR-AUC acumulada a cada dobra `[ASSUMPTION]`; estado em SQLite no Drive (busca retomável); `timeout` igual ao orçamento do modelo. Até 50 tentativas por modelo **dentro do orçamento de tempo do modelo** (NFR-01, D-42), cada tentativa avaliada pela PR-AUC média das 5 dobras leave-one-region-out (§3.8). Se o orçamento não comportar, usar subamostra estratificada na busca antes de reduzir dobras ou modelos.
- **Espaço de busca:** `[OPEN QUESTION]` Q-08 — definido na implementação e registrado no config.
- **Early stopping e melhores pesos (FR-22):**
  - Em cada dobra leave-one-region-out, a região deixada de fora serve **só** para as predições fora da dobra. Ela não pode decidir onde parar o treino: se decidisse, a métrica fora da dobra ficaria otimista.
  - Por isso, o early stopping usa uma **validação interna**: 10% estratificado pelo alvo das linhas das 4 regiões de treino `[ASSUMPTION]`.
  - Métrica monitorada: PR-AUC (`aucpr` no XGBoost, `PRAUC` no CatBoost, cálculo próprio por época no MLP). Paciência: 50 rodadas no boosting e 10 épocas no MLP `[ASSUMPTION]`.
  - Retreino final: nº de árvores / épocas = mediana dos melhores pontos das 5 dobras (D-37).
- **Regra de seleção:** maior PR-AUC média nas dobras leave-one-region-out (§3.8). Empate (diferença < 0,005 ou ICs sobrepostos) → menor Brier; persistindo → o modelo mais simples (ordem: elastic net < Random Forest < XGBoost/CatBoost < MLP < TabFM `[ASSUMPTION]`).

## 3.12 Plano de avaliação

- **Métrica primária (D-09):** **PR-AUC** (average precision). Com positivos raros, a ROC-AUC fica alta mesmo quando o modelo erra muito na classe positiva; a PR-AUC mede o desempenho exatamente onde está o erro caro.
- **Secundárias:** Brier score, curva de calibração (calibration slope e intercept), ROC-AUC (para comparação com a literatura).
- **Métricas no limiar (D-24, D-33):** acurácia, precisão, recall e F1 no limiar escolhido, prometidas no pré-projeto, e **F2**.
  - **F2 em vez de F0.5 (D-33):** o professor sugeriu o F0.5 como "um F1 mais inclinado para o recall". Na Fβ, β < 1 dá mais peso à precisão e β > 1 dá mais peso ao recall: o F0.5 favorece a **precisão**. A intenção dele (priorizar recall) e o custo de erro do projeto (falso negativo mais caro, D-14) correspondem ao **F2**, que trata o recall como duas vezes mais importante que a precisão. O relatório explica a escolha.
  - Na tabela de resultados, sempre ao lado de **B0** e **B2**.
  - B0 no limiar prevê "ninguém agrava": acurácia ≈ 1 − prevalência, recall = 0. O relatório usa essa linha para mostrar por que a acurácia não serve como métrica de decisão com classe rara.
  - Não são critério de seleção de modelo (§3.11 usa PR-AUC).
- **Limiar:** escolhido nas predições calibradas fora da dobra (2022–23, FR-17), como o que **maximiza o F2** (D-33). Isso fecha Q-03: o recall resultante é reportado, em vez de fixado antes.
- **Utilidade clínica (D-39):** curva de decisão (*decision curve analysis*, net benefit) no teste para o melhor M1, B1 e a regra do protocolo (B2), contra "tratar todos" e "tratar ninguém", numa faixa de limiares de risco plausível para triagem `[ASSUMPTION]` (ex.: 1%–20%). O limiar F2 aparece como um ponto de operação marcado na curva, e não como a única justificativa do limiar. Síntese das referências (Vickers & Holland 2021; benchmark com F2 + DCA) em `research/consensus-boas-praticas.md` (cópia local, fora do repositório: termos do Consensus).
- **Calibração:** obrigatória, porque o produto é "qual o risco". Isotônica ou Platt, ajustada nas predições fora da dobra (FR-17). No teste, reportar a curva de calibração e o calibration slope: é a métrica que a literatura mostra degradar primeiro sob drift (§3.8).
- **Variação entre regiões no desenvolvimento:** reportar PR-AUC e calibration slope de cada dobra leave-one-region-out. É a medida de robustez geográfica do modelo.
- **Incerteza:** IC 95% por bootstrap no teste, para todas as métricas e para a **diferença** de PR-AUC entre o melhor modelo e B1. 1.000 reamostras para métricas escalares `[ASSUMPTION]`; **2.000** nas bandas da curva de calibração, como em [Austin et al., Stat Med 2014](https://consensus.app/papers/details/90973d5732005604963231ca27adbb22/) (D-41). Se o bootstrap ficar caro demais com milhões de linhas, o IC da AUC pode usar o método por função de influência ([LeDell et al., 2015](https://consensus.app/papers/details/d349620d7e9e5108a57864ddbb717245/)).
- **Subgrupos (D-13):** faixa etária; sexo e gestantes; região/UF. Reportar PR-AUC, recall no limiar e calibração por subgrupo, com IC.
- **Análise de erros:** inspecionar os 100 falsos negativos com maior risco não detectado `[ASSUMPTION]`, por perfil (idade, comorbidades, UF, atraso de notificação), e as células de comorbidade com pior calibração.
- **Privacidade nas tabelas:** células de perfil com < 10 casos não são publicadas `[ASSUMPTION]`.
- **Critérios de aceitação** `[ASSUMPTION]` — todos a confirmar pelo grupo:
  - O melhor modelo M1 supera B0 em PR-AUC (IC da diferença não inclui 0).
  - O melhor modelo é comparado a B1: superar B1 é desejável, mas **não** é condição de sucesso. Se não superar, conclui-se que a logística basta (resultado válido, §3.2).
  - No limiar escolhido, o recall do modelo é ≥ ao da regra B2, com precisão maior.
  - Calibration slope no teste entre 0,8 e 1,2.

## 3.13 Interpretabilidade e equidade

- **Coeficientes / OR da E1:** a principal ferramenta de explicação. São associações ajustadas por idade e sexo, **não efeitos causais**. Ex.: hipertensão é correlacionada com idade e com doença renal; parte do "efeito" pode ser confundimento residual.
- **Tabela de perfis:** traduz o modelo para a pergunta original ("qual o risco de um hipertenso de 65 anos?").
- **SHAP local na demo (D-35):** a aba Triagem mostra, para cada caso, os 5 fatores que mais mexeram no risco (§3.15). É explicação do **modelo** para aquele caso, não causa clínica.
- **SHAP (FR-13):** valores SHAP e SHAP interaction values do modelo de árvore, numa subamostra estratificada (ex.: 50 mil linhas `[ASSUMPTION]`), por custo computacional. Limitação: o SHAP explica o **modelo**, não o mundo; com features correlacionadas, a atribuição entre elas é instável.
- **Equidade:** comparar desempenho e calibração entre regiões e faixas etárias (§3.12). Um modelo pior calibrado no Norte/Nordeste, por exemplo, pode refletir diferenças de notificação, não de risco. Isso será discutido no relatório.

## 3.14 Reprodutibilidade e rastreio de experimentos

- **Ambiente (D-16):** `uv` + `pyproject.toml` + `uv.lock` versionado. No Colab: instalação a partir do lock.
- **Seeds:** seed global única no config, propagada para numpy, sklearn, XGBoost, CatBoost, MLP, sampler do Optuna, subamostra de contexto do TabFM, bootstrap e subamostras.
- **Dados:** snapshot Parquet por ano, com hash SHA-256 registrado em `data/manifest.json` e no MLflow. Data do download registrada (o DataSUS pode revisar os arquivos).
- **Configuração:** arquivos YAML (anos, filtros, features por momento, hiperparâmetros, limiar); nada hard-coded.
- **Tracking (D-15):** MLflow, com `mlruns/` persistido no Google Drive do grupo. Cada execução registra config, hash dos dados, commit do git, métricas e artefatos. Os melhores pesos de validação de cada modelo ficam no registro de modelos do MLflow com o alias `melhor-validacao` (FR-22).
- **Critério:** NFR-02.

## 3.15 Entregáveis e interfaces

**Entregáveis exigidos pelo professor (D-26):** um modelo, uma demo para testá-lo e um relatório explicando processo, decisões, resultados e passos seguidos.

| Exigido | O que o projeto entrega | IDs |
|---|---|---|
| Modelo | E1 (perfil) e M1 (triagem), serializados com metadados | FR-05, FR-07, FR-12 |
| Demo | App Streamlit público com duas abas | FR-11, D-17, D-27 |
| Relatório | Relatório TRIPOD+AI com apêndices de decisões, fluxograma e passos | FR-20, D-28 |

Apoio (não exigido, mas necessário para o relatório e a reprodutibilidade): pipeline em módulos Python, notebooks de profiling, explicação e avaliação, e MLflow. CLI só como extra (FR-10, MAY).

**Contrato da CLI** (extra, FR-10 MAY; só contrato, sem implementação). O mesmo schema de entrada vale para a aba Triagem da demo.

```
predict --model <caminho_artefato> --input casos.csv --output riscos.csv
```

Entrada (`casos.csv`), uma linha por caso:

| Coluna | Tipo | Domínio |
|---|---|---|
| `id_caso` | string | livre (devolvido na saída) |
| `idade_anos` | int | 0–120 |
| `sexo` | string | `M`, `F` |
| `gestante` | string | `sim`, `nao`, `ignorado` |
| `diabetes`, `hematologica`, `hepatopatia`, `renal_cronica`, `hipertensao`, `acido_peptica`, `autoimune` | string | `sim`, `nao`, `ignorado` |
| sintomas de §3.8 | string | `sim`, `nao`, `ignorado` |
| `dias_ate_atendimento` | int | 0–60 |

Saída (`riscos.csv`):

| Coluna | Tipo | Exemplo |
|---|---|---|
| `id_caso` | string | `abc-001` |
| `risco` | float | `0.042` (probabilidade calibrada) |
| `alto_risco` | bool | `true` (risco ≥ limiar) |
| `modelo_versao` | string | `m1-lgbm-2026-11-10-<hash>` |

**Tabela de perfis** (FR-06) — formato:

| Perfil | Faixa etária | Risco estimado | IC 95% | Razão vs. "saudável" mesma faixa |
|---|---|---|---|---|
| Sem comorbidades | 60–79 | … | … | 1,0 |
| Só hipertensão | 60–79 | … | … | … |
| Diabetes + renal crônica | 60–79 | … | … | … |
| 3+ comorbidades | 60–79 | … | … | … |

**Fonte da tabela de perfis e da aba Perfil (D-20):** o modelo explicativo **E1** (só perfil: idade, sexo, gestação, comorbidades). A pergunta original ("se um hipertenso pegar dengue, qual o risco?") é feita antes dos sintomas, e E1 responde exatamente isso. M1 é o modelo preditivo de triagem, exposto na aba Triagem (D-27).
- `[ASSUMPTION]` E1 é ajustado em 2022–23 e tem calibração checada em 2024, como os demais modelos. ICs dos perfis vêm da matriz de covariância da logística (método delta).

**Demo Streamlit (FR-11, D-27)**
- **Aba Perfil (E1)**
  - Entrada: idade, sexo, gestação, 7 comorbidades.
  - Saída: risco de E1 com IC 95%, comparação com o perfil "sem comorbidades" da mesma faixa etária, e os OR das comorbidades marcadas.
- **Aba Triagem (M1)**
  - Entrada: os campos do schema de entrada da CLI (perfil + sintomas iniciais + dias até o atendimento).
  - Saída: risco calibrado de M1 e "alto risco" sim/não no limiar escolhido (§3.12).
  - Explicação (D-35): os 5 fatores que mais aumentaram ou reduziram o risco do caso (SHAP local), com a frase "contribuição no modelo, não causa".
    - Modelos de árvore: TreeSHAP exato. Elastic net: contribuição linear (coeficiente × valor). MLP ou TabFM: SHAP aproximado com amostra de fundo `[ASSUMPTION]`, respeitando NFR-06.
  - `[ASSUMPTION]` SHOULD mostrar também se o caso cairia no grupo B pela regra do protocolo (B2, §3.10), para o usuário comparar modelo e regra.
  - Sem IC por predição: M1 é modelo de árvore, sem IC analítico. A incerteza do modelo fica no relatório (IC bootstrap das métricas).
- As duas abas explicam, em uma frase, a diferença entre elas: Perfil responde "qual o risco de quem tem estas condições"; Triagem responde "qual o risco deste paciente, com estes sintomas, agora".
- Aviso fixo nas duas abas: "Projeto acadêmico. Não é ferramenta clínica nem substitui avaliação médica." Na aba Triagem, o aviso fica em destaque, porque ela se parece mais com uma ferramenta clínica.
- Nenhum microdado embarcado; nenhuma entrada armazenada (NFR-03).

## 3.16 Registro de decisões

D-01 a D-21 registradas em 2026-10-19, na entrevista inicial (D-08, D-20 e D-21 após a pesquisa via Consensus). D-22 a D-25 registradas em 2026-11-01, na comparação com o pré-projeto enviado ao professor.

- **D-01 — Objetivo: explicação primeiro, predição depois.** Opções: ambos / só predição / só explicação. Decisão: ambos, com explicação como foco. Consequência: E1 (logística com interações) é entregável central; modelos de ML são comparados a ela.
- **D-02 — Alvo composto: dengue grave OU óbito pelo agravo.** Opções: composto / só óbito / hospitalização / multiclasse. Decisão: composto. Consequência: mais positivos que óbito sozinho; `GRAV_*` proibidos como features. Reconfirmado em D-22, frente ao alvo amplo do pré-projeto.
- **D-03 — Dois momentos de predição: M1 (primeiro atendimento) e M2 (pós-alarme).** Decisão: ambos, com M2 rebaixado a extra para conter o escopo. Consequência: features diferentes por momento (§3.8).
- **D-04 — Recorte: Brasil, 2022–2024.** Opções: Brasil 2022–24 / só 2024 / um estado / adiar. Decisão: Brasil 2022–24; 2017–24 só como sensibilidade extra (D-08).
- **D-05 — Acesso aos dados: FTP do DataSUS + `pyreaddbc`** (alterado em 2026-11-02; decisão original: PySUS). Opções originais: PySUS / CSV do OpenDataSUS / dados já fornecidos. Decisão original: PySUS (download por script, reprodutível).
  - **Motivo da alteração** (verificado em 2026-11-02 com PySUS 2.11.7): na versão 2.x, o PySUS não baixa do DataSUS. Até `source="origin"` consulta primeiro um catálogo próprio do projeto PySUS em S3, e os arquivos vêm desse espelho. Nesse catálogo, o SINAN aparece sem nenhum arquivo indexado: `sinan("DENG", 2022)` e `list_files("SINAN")` retornam vazio, sem erro. Além disso, o pacote instala ~200 dependências e fixa versões de pandas/numpy, o que arrisca quebrar o ambiente do Colab.
  - Opções na revisão: FTP + `pyreaddbc` / versão antiga do PySUS (sem manutenção) / CSV do OpenDataSUS (outra fonte e outro formato). Decisão: FTP + `pyreaddbc`, que é o mesmo leitor de `.dbc` que o PySUS usa por baixo.
  - Consequências: o download continua por script e reprodutível. A fonte passa a ser o arquivo oficial, e o manifesto registra o hash do `.dbc` e a data de revisão no FTP. PySUS sai das dependências.
- **D-06 — População: só casos confirmados com evolução conhecida.** Opções: confirmados / todos os notificados / só confirmados por laboratório. Consequência: rótulo mais limpo; risco é condicional a "notificado e confirmado" (viés de seleção, §3.7).
- **D-07 — "Ignorado"/branco como categoria própria.** Opções: categoria própria / tratar como "não" / excluir linhas. Consequência: exige o check de vazamento por completude (§3.8). Atualização 2026-11-01: os dicionários não têm o código 9 para comorbidades, então a categoria passa a se chamar "Ausente" (branco ou fora do domínio). A decisão não muda.
- **D-08 — Split: temporal (dev 2022–23, teste 2024) + validação interna-externa leave-one-region-out no desenvolvimento.** Contexto: o Pablo pediu revisão de literatura via Consensus antes de decidir. Opções: (A) dev 2022–23, teste 2024, com três variantes — interna-externa por região / temporal 2022→2023 com retreino / sem retreino; (B) 2017–2024; (C) 2022 / 2023 / 2024; (D) corte dentro de 2024; (E) aleatório estratificado. Decisão: A + interna-externa; B como sensibilidade extra (FR-16). Consequências: ~5× mais treinos no Colab; UF/região sai das features (D-21); calibrador e limiar ajustados em predições fora da dobra (FR-17), o que evita aplicar ao modelo retreinado um calibrador ajustado em outro modelo.
- **D-09 — Métrica primária: PR-AUC + calibração.** Opções: PR-AUC + calibração / recall com piso de precisão / ROC-AUC. Consequência: Brier e curva de calibração são secundárias obrigatórias.
- **D-10 — Análise de combinações: logística com interações + tabela de perfis + SHAP interactions.** "Taxas observadas por perfil" não foi selecionada.
- **D-11 — Modelos: boosting + RF obrigatórios; CatBoost e MLP extras.** Opções: boosting+RF obrigatórios / os 4 obrigatórios / só boosting. Motivo: escopo e compute no Colab. Atualizado por D-32: todos obrigatórios, mais elastic net e TabFM.
- **D-12 — Desbalanceamento: pesos de classe.** Opções: pesos / subamostrar negativos / SMOTE / nenhum. Consequência: calibração posterior obrigatória. **Revisado por D-38: sem correção de desbalanceamento.**
- **D-13 — Subgrupos: faixa etária; sexo e gestantes; região/UF.** Raça/cor não selecionada (ver Q-05).
- **D-14 — Custo de erro: falso negativo bem mais caro.** Consequência: limiar orientado a recall; valor mínimo em Q-03.
- **D-15 — Tracking: MLflow.** Opções: MLflow / CSV + YAML / W&B. Consequência: `mlruns/` no Drive.
- **D-16 — Ambiente: uv + pyproject + lock.** Opções: uv / requirements.txt / conda.
- **D-17 — App: Streamlit Community Cloud, público.** Opções: público / só local / adiar. Consequência: aviso de uso acadêmico e NFR-03 obrigatórios.
- **D-18 — Doenças respiratórias: não-objetivo documentado.** Opções: não-objetivo / extrair de texto livre / linkar SIH/SIM. Base: a ficha não tem o campo (verificado em 2026-10-19).
- **D-19 — Entregáveis: notebooks + relatório, pipeline + modelo salvo, app demo.**. Atualizado por D-26.
- **D-20 — Tabela de perfis e app usam E1 (só perfil).** Opções: E1 / M1 com sintomas fixos / M1 marginalizado sobre sintomas. Motivo: a pergunta original é anterior aos sintomas; E1 é explicável e tem IC analítico. Consequência: a aba Perfil não pede sintomas. Atualizado por D-27: M1 ganhou uma aba própria (Triagem).
- **D-21 — UF/região só como subgrupo, não como feature.** Opções: só subgrupo / features contínuas de nível regional / manter UF e trocar a CV. Motivo: compatibilidade com leave-one-region-out (D-08). Consequência: diferenças regionais aparecem como diferenças de calibração por região, discutidas no relatório.
- **D-22 — Alvo: mantido o estrito de D-02, divergindo do pré-projeto.** Contexto: o pré-projeto aprovado define agravamento como hospitalização, sinais de alarme, dengue grave ou óbito. Opções: (1) estrito como primário + amplo do pré-projeto como desfecho secundário em B1/E1; (2) só o estrito; (3) "casos graves" do MS (11/12 + óbito, sem hospitalização); (4) amplo do pré-projeto. Decisão: (2). Motivo: hospitalização é circular com comorbidade, e sinais de alarme são estado intermediário (§3.6). Consequências: `HOSPITALIZ` segue fora do alvo e das features. O relatório MUST justificar a mudança. Há menos eventos que no alvo amplo, então o risco de células raras (§3.17) continua.
- **D-23 — Análise descritiva (FR-18) e ranking de comorbidades (FR-19) viram requisitos.** Contexto: ambos são resultados esperados no pré-projeto e não tinham FR. Opções: os dois / só o ranking / nenhum. Decisão: os dois. Consequência: riscos brutos são só descritivos; a tabela de perfis continua vindo de E1 (D-10, D-20).
- **D-24 — Acurácia, precisão, recall e F1 no limiar como métricas reportadas.** Contexto: prometidas no pré-projeto; ausentes do spec. Opções: secundárias com B0 ao lado / só justificar a troca / F1 como primária. Decisão: secundárias com B0. Consequência: PR-AUC continua primária (D-09); a linha de B0 ilustra o paradoxo da acurácia.
- **D-25 — Diferencial reformulado e Rosa et al. (2026) registrado como trabalho relacionado.** Contexto: Rosa et al. já usam as 7 comorbidades e as destacam no SHAP, o que enfraquece o diferencial do pré-projeto. Opções: reformular / registrar sem reformular / não registrar. Decisão: reformular (§3.2). Consequência: a apresentação enfatiza combinações, risco calibrado, comparação com o protocolo e validação externa.
- **D-26 — Entrega acadêmica: modelo + demo + relatório.** Contexto: o Pablo informou o que o professor exige (2026-11-01): um modelo, uma demo para testá-lo e um relatório com processo, decisões, resultados e passos seguidos. Consequências: §3.15 reorganizado; CLI rebaixada de MUST para MAY (FR-10; opções: descontinuar / MAY / manter MUST); pipeline, notebooks e MLflow ficam como apoio ao relatório e à reprodutibilidade.
- **D-27 — Demo com duas abas: Perfil (E1) e Triagem (M1).** Opções: só E1 / só M1 / as duas em abas. Decisão: as duas. Consequências: dois modelos a calibrar, serializar e explicar na demo; a aba Triagem precisa do limiar de §3.12 e do mesmo schema de entrada da CLI; aviso de uso acadêmico em destaque na aba Triagem.
- **D-28 — Relatório estruturado pelo TRIPOD+AI, com apêndices.** Opções: TRIPOD+AI + apêndices / estrutura livre / aguardar template do professor. Decisão: TRIPOD+AI. Consequência: FR-20. O checklist também serve de autoavaliação antes da entrega. Se o professor fornecer um template, as seções do TRIPOD+AI são encaixadas nele.
- **D-29 — Cronograma fora do spec.** Contexto: o Pablo pediu (2026-11-01) que o spec trate só do trabalho acadêmico e do modelo. Consequências: §3.18 vira N/A; Q-09 (data de entrega) retirada; o risco "prazo estoura" sai de §3.17; justificativas de D-03 e D-11 que citavam prazo passam a citar escopo. Os extras (FR-14, FR-15, FR-16) continuam como MAY, fora do escopo base.
- **D-30 — Dúvidas de CEP e licença fora do spec.** Contexto: o Pablo decidiu (2026-11-01) não investigar a dispensa de CEP (Q-11) nem o alcance da cláusula "SemDerivações" (Q-12). Consequências: Q-11 e Q-12 retiradas; NFR-04 mantém só o fundamento da dispensa para o relatório; a licença fica registrada em §3.7 com a regra de citar a fonte e não redistribuir microdados.
- **D-31 — Marcos sem datas.** Contexto: o Pablo liberou (2026-11-01) marcos com objetivos, sem datas. Atualiza D-29: §3.18 deixa de ser N/A e passa a ter 7 marcos, cada um com objetivo, FRs e critérios de saída. Datas, prazos e o risco de prazo continuam fora do spec. Consequência: o item de §5 "marcos cabem no prazo, com folga" é avaliado como "marcos cobrem todos os FRs MUST, com critérios verificáveis".
- **D-32 — Seis candidatos obrigatórios em M1, a pedido do professor.** Contexto: no retorno do pré-projeto (2026-11-02), o professor pediu para testar XGBoost, MLP, TabFM, logística elastic net e CatBoost. Opções: todos, com TabFM extra / todos obrigatórios / só elastic net + XGBoost. Decisão: todos obrigatórios, incluindo o TabFM. Consequências: FR-07 reescrito; FR-15 absorvido; Q-07 fechada (XGBoost); mais custo de compute (5 modelos treináveis × 5 dobras); TabFM com contexto em subamostra e limites a verificar no model card. Nota: o agente tinha sugerido que "TabFM" fosse o TabPFN; o Pablo corrigiu, e a existência do TabFM (Google Research, 30/06/2026) foi confirmada.
- **D-33 — F2 no limiar, e não o F0.5 sugerido.** Contexto: o professor sugeriu F0.5 como métrica "inclinada para o recall", mas o F0.5 favorece a precisão. Opções: F2 explicando / F2 e F0.5 / F0.5 como pedido. Decisão: F2. Consequências: o limiar passa a ser o que maximiza o F2 nas predições fora da dobra; Q-03 fechada; PR-AUC continua primária (D-09); o relatório explica a diferença entre F0.5 e F2.
- **D-34 — Revisão por profissional de saúde só nos resultados.** Contexto: o professor sugeriu validar preditores e resultados com alguém da área. Opções: dois pontos (preditores e resultados) como SHOULD / dois pontos como MUST / só nos resultados. Decisão: só nos resultados. Consequências: FR-21 (SHOULD); a revisão acontece depois do teste, então sugestões que mudariam o modelo viram limitação, não retreino. Os preditores não passam por revisão clínica antes da modelagem; o relatório registra isso.
- **D-35 — Explicação por caso (SHAP local) na aba Triagem.** Contexto: o professor pediu ênfase em explicabilidade e um app útil para profissionais de saúde. Opções: SHAP local / só o risco. Decisão: SHAP local, com os 5 fatores de maior contribuição. Consequência: o método de SHAP depende do modelo escolhido (exato para árvores, linear para elastic net, aproximado para MLP/TabFM), dentro do limite de latência (NFR-06).
- **D-36 — Melhores pesos escolhidos só na validação.** Contexto: o Pablo pediu (2026-11-02) estratégias para guardar os melhores pesos e usá-los se testes posteriores piorarem. Opções: só validação (early stopping, melhor tentativa salva; o teste nunca escolhe) / 2024 como validação de seleção e o arquivo final de 2025 como teste congelado. Decisão: só validação. Motivo: escolher peso pelo teste de 2024 o transformaria em dado de seleção e deixaria o resultado final otimista. Consequências: FR-22; early stopping com validação interna em cada dobra, para não contaminar as predições fora da dobra; D-04 e D-08 não mudam.
- **D-37 — Retreino final usa a mediana dos melhores pontos das dobras.** Contexto: no retreino em 2022–23 completo não sobra validação para o early stopping. Opções: mediana das dobras / ensemble dos 5 modelos das dobras / fatia interna de validação no retreino. Decisão: mediana. Consequências: um modelo único, coerente com FR-17, com a demo e com o SHAP; o nº de árvores/épocas do modelo final é registrado com os 5 valores de origem.
- **D-38 — Revisão de D-12: sem correção de desbalanceamento.** Contexto: revisão de boas práticas via Consensus (2026-11-03). Estudos com centenas de milhares a milhões de pacientes mostram que pesos de classe, subamostragem e SMOTE não melhoram AUROC nem AUPRC e pioram a calibração. Opções: tirar os pesos / comparar com e sem / manter. Decisão: tirar. Consequências: §3.9 reescrito; o recall é controlado pelo limiar F2 (D-33); calibração posterior mantida.
- **D-39 — Curva de decisão (net benefit) como avaliação secundária.** Contexto: diretrizes e estudos recentes pedem medir utilidade clínica, não só discriminação e calibração. Opções: adicionar como secundária / não adicionar. Decisão: adicionar. Consequências: curva de decisão no teste para M1, B1 e B2; o limiar F2 vira um ponto de operação na curva; a PR-AUC continua primária (D-09).
- **D-40 — Interação multiplicativa e aditiva no E1.** Contexto: para "quais combinações de comorbidades são mais perigosas", a epidemiologia recomenda reportar também a escala aditiva. Opções: multiplicativa + aditiva / só multiplicativa. Decisão: as duas. Consequências: FR-05 reescrito; RERI e AP com IC para os 21 pares, com Benjamini-Hochberg; a tabela de perfis (FR-06) continua em risco absoluto.
- **D-41 — Ajustes menores pela revisão de evidências.** Aplicados: (1) a interação comorbidade × idade no E1 usa idade contínua (spline), e não faixa etária; (2) 2.000 reamostras de bootstrap nas bandas da curva de calibração e 1.000 nas demais métricas. Considerados e não adotados agora: medir o % de branco das comorbidades também por região; ranking de comorbidades proibido por SHAP e PDP como complemento (o ranking já vem dos OR de E1, FR-19).
- **D-42 — Orçamento de tempo por modelo (NFR-01).** Contexto: o limite antigo ("≤ 2 h para o treino completo") era de quando havia 2 modelos; com 6 candidatos × 5 dobras × até 50 tentativas, ele não cabia. O Pablo propôs um tempo fixo por modelo (2026-11-03). Opções consideradas: limite total para o pipeline / orçamento por modelo / reduzir o nº de modelos. Decisão: orçamento por modelo (60–90 min; total ≈ 8 h em sessões separadas). Motivo: cabe nos limites do Colab gratuito, isola falhas por modelo e dá a todos uma busca comparável; a literatura indica que, com muitos dados e poucas features, uma busca modesta já captura o ganho. Consequências: NFR-01 reescrita; busca com tempo-limite, poda e estado retomável; subamostra estratificada na busca se necessário; tempo e nº de tentativas registrados por modelo.
- **D-43 — Optuna para a busca de hiperparâmetros.** Contexto: a NFR-01 pede busca com tempo-limite, poda e estado retomável; o spec deixava "Optuna ou random search" em aberto. Decisão do Pablo (2026-11-03): Optuna. Consequências: nova dependência, pinada no `uv.lock` na fase de modelagem (não é necessária no profiling); sampler TPE com semente no config; estudo salvo em SQLite no Drive. A escolha do algoritmo de busca pesa pouco no resultado com muitos dados e poucas features ([Meaney et al. 2025](https://consensus.app/papers/details/404aec96444654a2bc7ee5a2e2d000aa/)); o ganho do Optuna está na infraestrutura (tempo, poda, retomada).
- **D-44 — Colab gratuito e Colab Pro, os dois suportados.** Contexto: o Pablo pretende usar o Colab Pro (plano de estudante). Opções: só o Pro / gratuito e Pro. Decisão (2026-11-03): os dois. Consequências: o Pro é o acelerador (GPU, High RAM, mais folga de tempo); o pipeline continua executável no gratuito, com subamostra na busca se precisar, para que qualquer pessoa reproduza sem assinatura; os orçamentos de tempo por modelo valem nos dois ambientes.
- **Revisão da tabela de vazamento (2026-11-03).** A tabela de §3.8 passou a cobrir as 121 colunas do arquivo de 2022, incluindo os campos da classificação antiga de FHD, os de investigação, os de unidade notificadora e os administrativos. Todos ficam fora do modelo. Não é decisão nova: a lista de features já era fechada; o registro documenta o motivo de cada exclusão.

## 3.17 Riscos

| Risco | Prob. | Impacto | Mitigação |
|---|---|---|---|
| Download do FTP do DataSUS lento ou instável | Média | Alto | Salvar Parquet no Drive; carregar só as colunas usadas. |
| Vazamento por completude da ficha (§3.8) | Média | Alto | Check obrigatório no profiling; análise de sensibilidade. |
| Poucos positivos em combinações raras de comorbidades | Alta | Médio | Mínimo de eventos por célula; considerar opção B de D-08 (mais anos). |
| Códigos de `CLASSI_FIN`/`EVOLUCAO` mudam entre anos | Média | Alto | Validar domínio por ano (FR-03); testes unitários da geração do alvo. |
| Mudança de distribuição em 2024 (epidemia, sorotipo) | Alta | Médio | É o que o teste temporal mede; reportar e discutir, não esconder. |
| Ruído no rótulo (encerramento clínico, variação por UF) | Média | Médio | Subgrupos por região; discutir no relatório. |
| RAM insuficiente no Colab (RF, SHAP) | Média | Médio | Tipos enxutos, subamostra estratificada para RF/SHAP. |
| Validação por região multiplica o tempo de treino (5 dobras × 5 modelos × trials) | Alta | Médio | Orçamento de tempo por modelo, poda e busca retomável (NFR-01); subamostra estratificada na busca; uma sessão do Colab por modelo. |
| Colab desconecta ou não oferece GPU | Alta | Médio | Busca retomável a partir do Drive; melhores pesos já salvos (FR-22); XGBoost e CatBoost rodam em CPU; Kaggle como alternativa. |
| TabFM não comporta o volume (limite de contexto, GPU, velocidade) | Média | Médio | Verificar limites no model card antes do Marco 4; subamostra estratificada como contexto; registrar a restrição. |
| Melhor M1 (ex.: TabFM ou MLP) pesado demais para a demo ou sem SHAP rápido | Média | Médio | SHAP aproximado; se não cumprir NFR-06, decidir antes do Marco 5 (Q-14). |
| Profissional de saúde sugere mudança depois do teste | Média | Baixo | Não retreinar (teste já usado); registrar como limitação (FR-21). |
| Região com poucos eventos numa dobra (ex.: Norte) | Média | Médio | Checar eventos por região no profiling; reportar dobra com aviso de IC largo. |
| ML não supera logística/regra | Média | Baixo | Resultado válido e reportável (§3.2). |
| Uso indevido do app público como ferramenta clínica | Baixa | Alto | Aviso fixo; sem recomendações de conduta. |
| Professor questiona o alvo diferente do pré-projeto (D-22) | Média | Médio | Parágrafo de justificativa no relatório (§3.6); se o professor exigir o alvo amplo, reabrir D-22. |

## 3.18 Marcos (milestones)

Marcos sem datas (D-31): cada um tem um objetivo, os FRs que completa e critérios de saída verificáveis. A ordem é a de dependência; datas e prazos continuam fora do spec (D-29). Composição e critérios `[ASSUMPTION]`, a revisar pelo grupo.

Os marcos se chamam **Marco 1…7** para não confundir com os momentos de predição M1/M2 (§3.6).

| Marco | Objetivo | FRs | Critérios de saída |
|---|---|---|---|
| **1 — Dados e profiling** | Ter os dados baixados, versionados e entendidos antes de qualquer modelo. | FR-01, FR-02, FR-03 | Roteiro de profiling ([profiling/ROTEIRO.md](profiling/ROTEIRO.md)) concluído e `RESULTADOS.md` preenchido. Passo 1 (`CLASSI_FIN`) resolvido. `[VERIFY]` de dados resolvidos ou listados como pendentes. Fluxograma de exclusão pronto. Eventos conhecidos por ano, região e subgrupo. Check de completude × alvo feito. Q-04, Q-05 e Q-06 respondidas. |
| **2 — Descrição, split e baselines** | Descrever a população e fixar o piso que todo modelo precisa superar. | FR-18, FR-04, FR-17 | Análise descritiva gerada. Dobras leave-one-region-out construídas. Métricas fora da dobra de B0, B1 e B2 registradas no MLflow. Recall mínimo definido (Q-03). Teste de 2024 ainda intocado. |
| **3 — Modelo explicativo (E1)** | Responder à pergunta central: quais comorbidades e combinações estão associadas a maior risco. | FR-05, FR-06, FR-19 | OR com IC 95% e correção de Benjamini-Hochberg. Interações reportadas só com ≥ 10 eventos. Ranking de comorbidades com empates marcados. Tabela de perfis com células < 10 suprimidas. |
| **4 — Modelos preditivos (M1)** | Treinar, comparar e escolher o modelo de triagem. | FR-07, FR-08, FR-12, FR-13 | Os seis candidatos de FR-07 avaliados nas mesmas dobras, com busca registrada no MLflow (Q-08 respondida; limites do TabFM verificados; Q-14 decidida). Melhores pesos por dobra e melhor tentativa de cada modelo salvos no MLflow (FR-22). Calibrador e limiar ajustados nas predições fora da dobra. Modelo final escolhido pela regra de §3.11 **antes** de tocar no teste. E1 e M1 serializados com metadados. |
| **5 — Avaliação final no teste** | Medir o desempenho real, uma única vez, em 2024. | FR-09 | Teste usado uma vez, com o modelo congelado do Marco 4. Todas as métricas de §3.12 com IC bootstrap. Subgrupos e análise de erros feitos. Calibração de E1 em 2024 checada. Resultado registrado mesmo se pior que B1/B2. |
| **6 — Demo** | Permitir testar os dois modelos. | FR-11 | Demo pública com as abas Perfil e Triagem, usando os artefatos serializados (Marcos 3 e 4). Aviso de uso acadêmico nas duas abas. Nenhum microdado embarcado (NFR-03). Resposta < 1 s por perfil (NFR-06). |
| **7 — Relatório** | Explicar processo, decisões, resultados e passos seguidos. | FR-20, FR-21 | Checklist TRIPOD+AI preenchido. Apêndices A–C presentes. Revisão do profissional de saúde registrada no apêndice D, se houver. Justificativa do alvo (D-22) incluída. Checklist de §5 passando. |

**Regras entre marcos**
- **Portão do Marco 1:** se o passo 1 do profiling mostrar `CLASSI_FIN` com códigos 1/2/8, D-02 é redecidido antes de começar o Marco 2.
- **O teste fica isolado até o Marco 5.** Nenhum marco anterior olha para 2024.
- **Extras que são modelos entram antes do Marco 5.** M2 (FR-14) precisa ser treinado e comparado até o Marco 4. Se entrarem depois, o teste passa a ser usado mais de uma vez, e isso deixa o resultado otimista. A análise de sensibilidade (FR-16) e a CLI (FR-10) podem vir depois.
- **Trabalho em paralelo:** o esqueleto da demo pode começar no Marco 2 com modelos fictícios, e o relatório pode ser escrito ao longo dos marcos. Os critérios de saída dos Marcos 6 e 7 dependem dos artefatos finais.

## 3.19 Mapeamento dos entregáveis acadêmicos

Exigências do professor, informadas pelo Pablo em 2026-11-01 (D-26).

| Exigência | Seção do spec |
|---|---|
| Um modelo | §3.11 (E1, M1), FR-05, FR-07, FR-12 |
| Uma demo para testá-lo | §3.15, FR-11, D-27 |
| Relatório: processo | FR-20; §3.6–§3.9 (formulação, dados, split, features) |
| Relatório: decisões | FR-20 apêndice A; §3.16 |
| Relatório: resultados | FR-20; §3.12 (avaliação), FR-06, FR-18, FR-19 |
| Relatório: passos seguidos | FR-20 apêndices B e C; FR-02, §3.14 (MLflow) |

**Pré-projeto enviado ao professor** (Grupo 1, "Dengue e Comorbidades") → onde o spec cobre cada compromisso:

| Compromisso do pré-projeto | Seção / ID | Situação |
|---|---|---|
| Fonte: SINAN/DataSUS | §3.7, FR-01 | Coberto (FTP oficial do DataSUS, D-05). |
| 7 comorbidades como preditores | §3.7, §3.8 | Coberto. |
| Alvo: hospitalização, alarme, grave ou óbito | §3.6, D-02, D-22 | **Divergente:** alvo estrito; justificativa obrigatória no relatório. |
| Logística vs Random Forest | §3.10 (B1), §3.11 (E1, RF) | Coberto; boosting é acréscimo. |
| Acurácia, precisão, recall, F1, foco no recall | §3.12, D-24, D-14 | Coberto como métricas no limiar; PR-AUC primária. |
| Desbalanceamento | §3.9, D-12 | Coberto. |
| Sem empecilho ético | NFR-04 | Fundamento reformulado (CNS 510, inciso II). |
| Risco a partir de idade, sexo e comorbidades | §3.15, E1, D-20 | Coberto. |
| Ranking de comorbidades | FR-19 | Coberto. |
| Análise descritiva com tabelas e gráficos | FR-18 | Coberto. |
| Diferencial: comorbidades como eixo central | §3.2, D-25 | Reformulado. |

**Retorno do professor sobre o pré-projeto** (recebido em 2026-11-02) → onde o spec cobre cada ponto:

| Comentário do professor | Seção / ID | Situação |
|---|---|---|
| Testar mais modelos (XGBoost, MLP, TabFM, logística elastic net, CatBoost) | §3.11, FR-07, D-32 | Coberto: os seis são obrigatórios em M1. |
| Cuidar com vazamento de dados | §3.8 (revisão campo a campo, vazamento por completude), profiling passo 4 | Coberto. |
| Validar preditores e resultados com alguém da área da saúde | FR-21, D-34 | Parcial, por decisão do grupo: só os resultados. |
| Trabalhar a explicabilidade do modelo | §3.13, FR-13, FR-19, D-35 | Coberto: OR, ranking, perfis, SHAP global e SHAP local na demo. |
| Usar F0.5 ("F1 mais inclinado para o recall") | §3.12, D-33 | Ajustado: F2, que é o que favorece o recall; o relatório explica. |
| Desenvolver um app legal para profissionais da saúde | §3.15, FR-11, D-27, D-35 | Coberto: demo com abas Perfil e Triagem, com explicação por caso. |

## 3.20 Perguntas em aberto e glossário

### Perguntas em aberto

- ~~**Q-01** `[OPEN QUESTION]` Entregáveis já conhecidos (D-26). Falta saber se há critérios de avaliação ou template de relatório. Quem responde: Pablo/professor.~~
- ~~**Q-02** `[OPEN QUESTION]` Haverá apresentação/defesa oral? Formato? Quem responde: professor.~~
- ~~**Q-03** Recall mínimo do limiar.~~ Respondida em D-33: o limiar maximiza o F2.
- **Q-04** `[OPEN QUESTION]` Duplicatas por chave composta: remover ou só reportar? Quem responde: profiling.
- **Q-05** `[OPEN QUESTION]` Raça/cor e escolaridade entram como features? Quem responde: profiling (taxa de ignorado) + decisão do grupo.
- **Q-06** `[OPEN QUESTION]` Análise de sensibilidade se a completude da ficha diferir por desfecho. Quem responde: profiling.
- ~~**Q-07** LightGBM ou XGBoost.~~ Respondida em D-32: XGBoost (pedido do professor).
- **Q-08** `[OPEN QUESTION]` Espaço de busca de hiperparâmetros. Quem responde: frente B, na implementação.
- ~~**Q-09** Data exata da entrega.~~ Retirada em D-29 (cronograma fora do spec).
- ~~**Q-10** `[OPEN QUESTION]` Papéis dos integrantes do grupo. Nomes (do pré-projeto): Gabriel Hanel, Mário Bernardo Balen, Mateus Lora, Pablo Henrique Strücker Sarturi, Ricardo Rigo Antunes. Quem responde: Pablo.~~
- ~~**Q-11** Dispensa de CEP para microdados do SINAN.~~ Retirada em D-30.
- ~~**Q-12** Alcance da licença CC BY-ND 3.0 sobre modelos e tabelas derivados.~~ Retirada em D-30.
- **Q-13** `[OPEN QUESTION]` Quem será o profissional de saúde da revisão (FR-21)? Quem responde: grupo.
- **Q-14** `[OPEN QUESTION]` Se o melhor M1 não couber na demo (velocidade, GPU, SHAP), a aba Triagem usa o melhor modelo que couber, com o motivo registrado? Quem responde: grupo, antes do Marco 5.

### Glossário

- **SINAN** — Sistema de Informação de Agravos de Notificação (Ministério da Saúde).
- **DataSUS** — Departamento de Informática do SUS; publica os microdados.
- **PySUS** — biblioteca Python para dados do DataSUS; considerada e abandonada em D-05.
- **`.dbc`** — formato do DataSUS: arquivo DBF (dBase) comprimido. Lido com `pyreaddbc`.
- **CLASSI_FIN / EVOLUCAO** — campos de classificação final e evolução do caso na ficha de dengue.
- **Sinais de alarme** — sinais clínicos que indicam risco de evolução para dengue grave (ex.: dor abdominal intensa, vômitos persistentes, sangramento de mucosa).
- **Dengue grave** — dengue com choque, sangramento grave ou comprometimento grave de órgãos.
- **PR-AUC** — área sob a curva precisão-recall; adequada para classe positiva rara.
- **Brier score** — erro quadrático médio das probabilidades; mede calibração e discriminação juntas.
- **Calibração** — se o risco previsto de 10% corresponde a ~10% de eventos observados.
- **OR (odds ratio)** — razão de chances; efeito de uma variável na logística.
- **SHAP** — método de atribuição de contribuição de cada feature à predição de um modelo.
- **Vazamento (leakage)** — uso, no treino, de informação indisponível no momento da predição ou derivada do rótulo.
- **Amostragem dependente do desfecho** — selecionar casos de forma diferente conforme a classe (ex.: negativos de um ano, positivos de outros). Distorce a prevalência e cria associações falsas com tudo que varia junto com o critério de seleção.
- **Paradoxo da acurácia** — com classe rara, um modelo que nunca prevê a classe positiva tem acurácia alta e recall zero.
- **Curva de decisão / net benefit** — mede, para cada limiar de risco, o benefício de agir segundo o modelo (verdadeiros positivos) descontado o custo dos falsos positivos, comparado com "tratar todos" e "ninguém".
- **RERI / AP** — medidas de interação aditiva: RERI = RR(A e B) − RR(só A) − RR(só B) + 1; AP = RERI / RR(A e B). RERI > 0 indica que a combinação acrescenta risco além da soma dos efeitos.
- **Early stopping** — parar o treino de um modelo iterativo quando a métrica de validação para de melhorar e restaurar o melhor ponto (checkpoint) visto até ali.
- **Fβ / F2** — média harmônica ponderada de precisão e recall; β > 1 favorece o recall (F2: recall 2× mais importante), β < 1 favorece a precisão (F0.5).
- **Elastic net** — regressão com penalização L1 (zera coeficientes) + L2 (encolhe coeficientes); melhora a predição com muitas variáveis correlacionadas, mas vicia os coeficientes.
- **TabFM** — modelo de fundação tabular zero-shot do Google Research (2026); prediz por aprendizado em contexto, sem treino.
- **TRIPOD+AI** — diretriz de relato para modelos de predição clínica com IA (Collins et al., BMJ 2024).
- **M1 / M2 / E1 / B0–B2** — modelos definidos em §3.6, §3.10 e §3.11.
