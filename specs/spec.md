# Spec — Risco de desfecho grave em dengue por perfil de comorbidades (SINAN/DataSUS)

**Feature**: `dengue-comorbidity-risk` (feature única; branch `main`)
**Criado**: 2026-10-19 | **Atualizado**: 2026-11-04 | **Status**: rascunho v0.18
**Entrada**: pré-projeto enviado ao professor (Grupo 1, "Dengue e Comorbidades") e retorno do professor (2026-11-02).

> Marco 1 (dados e profiling) concluído; próximo passo: Marco 2 ([tasks/01-setup-fundacao.md](tasks/01-setup-fundacao.md)). Pendências: `[OPEN QUESTION]` em §3.20 e `[VERIFY]` ao longo do texto; qualidade do spec em [checklists/requirements.md](checklists/requirements.md). O histórico de versões fica no git e no Registro de decisões ([research.md](research.md), §3.16).
> Números de dados, salvo indicação: 3ª execução do profiling (2026-11-03 04:21 UTC), [profiling/RESULTADOS.md](../profiling/RESULTADOS.md).
> Idioma: pt-BR (entregável acadêmico).
>
> **Mapa dos artefatos** (convenções do GitHub Spec Kit, D-55). Os números §3.x e os IDs (US, FR, NFR, SC, D, Q) valem em todos os arquivos de `specs/`:
>
> | Arquivo | Conteúdo |
> |---|---|
> | [goal.md](goal.md) | Objetivo geral e objetivos específicos (fonte única, D-59) |
> | [constitution.md](constitution.md) | Princípios, regras R1–R10, decisões reservadas ao Programador, governança |
> | [spec.md](spec.md) | O quê e por quê: §3.2–§3.6, cenários (US1–US3), requisitos e entidades-chave, critérios de sucesso (SC), premissas, §3.8, §3.10, §3.12, §3.13, §3.17–§3.20 |
> | [plan.md](plan.md) | Como: resumo, contexto técnico, Constitution Check, §A arquitetura, §B ambiente e orçamento, §3.9, §3.11, §3.14, complexidade |
> | [research.md](research.md) | R.1–R.3 (literatura e evidência) e §3.16 Registro de decisões |
> | [data-model.md](data-model.md) | §C entidades, §3.7 dados, §D dicionário de features |
> | [contracts/interfaces.md](contracts/interfaces.md) | §3.15 entregáveis e interfaces (CLI, tabela de perfis, demo) |
> | [quickstart.md](quickstart.md) | Como rodar e validar |
> | [tasks/](tasks/00-como-usar.md) | Tarefas: `00-como-usar.md` (regras, referência rápida, registros) e um arquivo por fase, `01` a `06` (Setup/Fundação, US1, US2, teste, US3, relatório) |
> | [checklists/requirements.md](checklists/requirements.md) | Checklist de qualidade do spec |
>
> Em caso de conflito: constitution > spec > plan, research, data-model, contracts > tasks.

---

## 3.1 Resumo

O objetivo geral e os objetivos específicos estão em [goal.md](goal.md) (D-59). Este spec detalha o que é preciso para alcançá-los.

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
- **Objetivo declarado:** explicação primeiro, predição depois (D-01; [goal.md](goal.md)).

### Trabalhos relacionados e diferencial (D-25)

Síntese da literatura (Rosa et al. 2026, Huang et al. 2020, Trindade et al. 2024 e as meta-análises sobre comorbidade): [research.md](research.md), R.1.

**Diferencial deste projeto** (reformula o do pré-projeto, que dizia que as comorbidades são "pouco exploradas como eixo central"; Rosa et al. já as usam e as destacam no SHAP):
1. **Combinações:** interações 2 a 2 entre comorbidades, com OR e IC 95% (E1, FR-05), e ranking com incerteza (FR-19). As meta-análises (research R.1) reportam comorbidades isoladas e, em geral, OR brutos.
2. **Risco absoluto calibrado por perfil** (FR-06), não só importância de feature.
3. **Comparação com a regra do protocolo do MS** (B2, §3.10).
4. **Validação externa temporal (2024) e geográfica (leave-one-region-out)** (D-08), com prevalência natural e todas as classes vindas dos mesmos anos.

## 3.3 Objetivos e não-objetivos

**Objetivos:** em [goal.md](goal.md) (objetivo geral e objetivos específicos).

**Não-objetivos**
- **Doenças respiratórias** (asma, DPOC etc.): a ficha do SINAN não tem esse campo (verificado, §3.7). Limitação documentada no relatório (D-18).
- Linkagem com SIH/SIM ou qualquer outra base.
- Inferência **causal** ("hipertensão causa piora"). Só associação ajustada.
- Ferramenta clínica real. O app é demonstração acadêmica, sem validação clínica.
- Previsão de surtos / número de casos (série temporal).
- Uso de resultados laboratoriais e sinais de gravidade como preditores (§3.8).
- UF/região como **feature** (D-21). Região é usada só como subgrupo de avaliação e eixo da validação interna-externa.
- **Extras** (fora do escopo base): M2 pós-alarme (D-03) e análise de sensibilidade com 2017–2024 (D-08).

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
- Consequência: o limiar prioriza recall alto. Ele é o que maximiza o F2 nas predições fora da dobra (D-33, §3.12).

## Cenários de usuário e testes

Histórias em ordem de prioridade. Cada uma pode ser testada sozinha (Spec Kit). O relatório
(FR-20) é transversal e fica na fase de polimento ([tasks/06-relatorio.md](tasks/06-relatorio.md)).

### US1 — Perfil de risco por comorbidades (Prioridade: P1)

Um analista de vigilância (ou a banca) quer saber quais comorbidades e combinações estão associadas
a maior risco de dengue grave ou óbito, ajustando por idade e sexo, e qual o risco absoluto de
pacientes-tipo.

- **Por que P1:** é o objetivo principal (D-01) e a pergunta original do pré-projeto.
- **Teste independente:** com o E1 ajustado em 2022–23, gerar OR com IC, ranking, RERI/AP e a
  tabela de perfis, sem depender de M1 nem da demo.
- **Cenários de aceitação:**
  1. **Dado** o E1 ajustado em 2022–23, **quando** se pede a tabela de associações, **então** cada
     comorbidade e cada par com ≥ 10 eventos têm OR e IC 95%, com correção de Benjamini-Hochberg,
     além de RERI e AP para os pares (FR-05).
  2. **Dado** o E1, **quando** se pede o ranking, **então** as comorbidades vêm ordenadas pelo OR
     ajustado, e as que têm IC sobrepostos ficam marcadas "sem ordem definida" (FR-19).
  3. **Dado** um perfil (ex.: 60–79 anos, hipertensão + diabetes), **quando** se consulta a tabela
     de perfis, **então** aparecem o risco absoluto, o IC 95% e a razão contra "sem comorbidades"
     na mesma faixa; células com < 10 casos não aparecem (FR-06, NFR-03).

### US2 — Risco individual na triagem (Prioridade: P2)

Um médico ou enfermeiro, no primeiro atendimento, quer o risco calibrado de um paciente a partir
do perfil e dos sintomas iniciais, e saber se ele passa do limiar de alto risco.

- **Por que P2:** é o objetivo secundário (D-01) e só se justifica se superar B1 e B2 (§3.2).
- **Teste independente:** com o M1 congelado, gerar predições fora da dobra (2022–23) e no teste
  (2024) e compará-las com B0, B1 e B2, sem a demo.
- **Cenários de aceitação:**
  1. **Dado** o desenvolvimento 2022–23, **quando** os seis candidatos são avaliados nas mesmas
     dobras, **então** cada um tem PR-AUC por dobra e média, e um é escolhido pela regra de §3.11
     sem ler 2024 (FR-07, FR-17).
  2. **Dado** o M1 congelado, **quando** é avaliado em 2024 uma única vez, **então** todas as
     métricas de §3.12 saem com IC 95% e por subgrupo (FR-09).
  3. **Dado** um caso com risco ≥ limiar, **quando** é previsto, **então** é classificado como
     "alto risco"; o limiar foi escolhido só nas predições fora da dobra (FR-08).

### US3 — Demo para testar os modelos (Prioridade: P3)

O professor ou um profissional de saúde quer testar os dois modelos pelo navegador, sem instalar
nada.

- **Por que P3:** é entregável exigido (D-26), mas depende dos artefatos de US1 e US2.
- **Teste independente:** com os artefatos serializados de E1 e M1, abrir a demo e consultar um
  perfil e um caso.
- **Cenários de aceitação:**
  1. **Dado** um perfil na aba Perfil, **quando** é enviado, **então** aparecem o risco de E1 com
     IC 95% e os OR das comorbidades marcadas, em < 1 s (FR-11, NFR-06).
  2. **Dado** um caso na aba Triagem, **quando** é enviado, **então** aparecem o risco calibrado,
     "alto risco" sim/não e os 5 fatores de maior contribuição (D-35).
  3. **Dado** qualquer uso, **então** o aviso de projeto acadêmico aparece e nenhuma entrada é
     armazenada (NFR-03).

### Casos-limite

- Óbito pelo agravo com classificação "dengue" (10) → `y = 1` (§3.6).
- Dengue grave (12) com evolução em branco → entra na população com `y = 1` (D-45).
- Código de idade inválido → idade por ano dos sintomas − `ANO_NASC`; sem `ANO_NASC` utilizável, o
  caso sai e é contado no fluxograma (D-49, D-50). O ES de 2022 grava idade em anos simples (§3.7).
- Comorbidade ou sintoma em branco ou fora de 1/2 → categoria "Ausente" (D-07).
- Combinação de comorbidades com < 10 casos → fora da tabela publicada; na demo, o risco sai do E1
  com a nota de que vem da soma dos efeitos (D-52).
- Subgrupo com < 100 eventos no teste (sexo "I" ou em branco, gestantes, Norte) → reportado com aviso de IC
  largo, sem conclusões (§3.12).
- Notificações com a mesma chave composta → mantidas; a taxa é reportada (D-47).
- Entrada da demo fora do domínio de [contracts/interfaces.md](contracts/interfaces.md) (ex.: idade
  > 120, dias > 60) → recusada com mensagem `[ASSUMPTION]`.

## 3.5 Requisitos

### Funcionais

- **FR-01** — O pipeline MUST baixar os microdados SINAN-Dengue (Brasil, 2022–2024; D-04) direto do FTP do DataSUS (D-05) e salvá-los em Parquet com hash SHA-256 registrado, junto com o hash do `.dbc` original e a data de revisão do arquivo no DataSUS.
- **FR-02** — O pipeline MUST aplicar os filtros de população (§3.6) e gerar o alvo, emitindo um **fluxograma de exclusão** com a contagem de linhas após cada filtro.
- **FR-03** — O pipeline MUST executar os checks de qualidade de §3.7 e falhar com mensagem clara se algum check bloqueante falhar.
- **FR-04** — O pipeline MUST treinar e avaliar os baselines B0, B1 e B2 (§3.10).
- **FR-05** — O pipeline MUST ajustar a regressão logística com interações 2 a 2 entre comorbidades (§3.11) e reportar, para cada par, a interação **multiplicativa** (OR) e a **aditiva** (RERI e AP), com IC 95% e correção para comparações múltiplas (D-40).
- **FR-06** — O pipeline MUST gerar a tabela de perfis (§3.15) com risco calibrado e IC 95% para cada perfil. Perfis (D-52): sem comorbidades, cada uma das 7 comorbidades sozinha, cada par que entrou no E1 e **todas** as combinações de 3+ com ≥ 10 casos em 2022–23.
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
- **FR-22** — O pipeline MUST guardar os melhores pesos encontrados **na validação** (D-36, D-37), nunca no teste: o melhor ponto de cada modelo iterativo por dobra e a melhor tentativa de cada busca ficam salvos no MLflow. O teste de 2024 nunca escolhe peso; resultado pior no teste é reportado como resultado (drift, §3.8). Como fazer: §3.11, "Early stopping e melhores pesos".

### Não funcionais

- **NFR-01 (compute)** — Todo o pipeline MUST rodar tanto no Google Colab gratuito quanto no Colab Pro (D-44), com **orçamento de tempo por modelo** (D-42), e não um limite para o pipeline inteiro. Os 6 modelos rodam **numa sessão única**, com as mesmas dobras e a mesma semente, e são comparados no fim dela (D-53).
  - Ambiente (Colab gratuito e Pro), orçamento por modelo, cronometragem, sessão única e regras da busca: [plan.md §B](plan.md#b-ambiente-de-execução-e-orçamento-nfr-01) (D-54).
- **NFR-02 (reprodutibilidade)** — Partindo de um checkout limpo + snapshot de dados com o hash registrado, a reexecução MUST reproduzir as métricas de teste com as mesmas 3 casas decimais.
- **NFR-03 (privacidade)** — Nenhum microdado (linha a linha) MUST ser versionado no repositório nem embarcado no app. O app MUST NOT armazenar as entradas do usuário.
- **NFR-04 (ética)** — Dados públicos e desidentificados (sem nome, CPF, endereço nem data de nascimento completa, mas com ano de nascimento, idade, sexo e município; §3.7). Nenhum trâmite de ética é previsto (D-30).
  - No relatório, a dispensa se apoia na Resolução CNS 510/2016, art. 1º, parágrafo único, inciso II ("informações de acesso público", Lei 12.527/2011), e não em "não haver coleta direta", como no pré-projeto. Os dados são chamados de "desidentificados", não "anonimizados".
- **NFR-05 (manutenibilidade)** — Código em módulos Python (não só notebooks), com testes unitários (pytest) para geração do alvo, filtros de população e decodificação de idade; lint com ruff.
- **NFR-06 (latência)** — `[ASSUMPTION]` O app SHOULD responder em < 1 s por perfil.

### Entidades-chave

- **Notificação:** uma linha do SINAN-Dengue de um ano.
- **Caso da população:** notificação que passa nos filtros de §3.6, com o alvo `y`.
- **Perfil:** faixa etária, sexo, gestação e comorbidades, sem sintomas (unidade da tabela de perfis).
- **Dobra:** região deixada de fora na validação leave-one-region-out (§3.8).
- **Modelo:** E1 (explicativo), M1 (triagem) ou baseline B0–B2, com metadados (FR-12).
- **Predição:** risco calibrado e classificação no limiar.

Campos, regras e relações: [data-model.md](data-model.md), §C.

## Critérios de sucesso

Resultados mensuráveis. SC-01 a SC-04 são os critérios de aceitação do teste (§3.12); todos são
`[ASSUMPTION]` a confirmar pelo grupo.

- **SC-01** — O melhor M1 supera B0 em PR-AUC no teste, com IC 95% da diferença sem incluir 0.
- **SC-02** — No limiar escolhido, o recall do M1 é ≥ ao da regra B2, com precisão maior.
- **SC-03** — O calibration slope do M1 no teste fica entre 0,8 e 1,2.
- **SC-04** — A diferença de PR-AUC entre M1 e B1 é reportada com IC 95%, qualquer que seja o sinal.
  Superar B1 é desejável, mas não é condição de sucesso (§3.2).
- **SC-05** — Toda comorbidade e todo par com ≥ 10 eventos têm OR e IC 95% no E1; nenhuma célula
  publicada tem < 10 casos (FR-05, NFR-03).
- **SC-06** — A demo responde em < 1 s por consulta (NFR-06).
- **SC-07** — A reexecução a partir de um checkout limpo reproduz as métricas de teste com 3 casas
  decimais (NFR-02).
- **SC-08** — O relatório cobre todos os itens do checklist TRIPOD+AI (FR-20).

## Premissas

Valores assumidos onde a entrada não decide. Cada um aparece também no ponto do texto em que se
aplica, marcado `[ASSUMPTION]`.

- Não há usuário clínico real; os usuários de §3.4 são hipotéticos e servem para guiar a métrica.
- "Gestante" = `CS_GESTANT` 1–4; faixas etárias 0–4, 5–14, 15–39, 40–59, 60–79 e 80+ (data-model).
- `LEUCOPENIA`, `LACO` e os dias até a notificação estão disponíveis no primeiro atendimento (§3.8).
- O mapeamento de B2 para o grupo B do protocolo usa só os critérios que existem na ficha (§3.10).
- Interações e células só são reportadas com ≥ 10 eventos; correção por Benjamini-Hochberg (FDR 5%).
- A faixa de limiares da curva de decisão é 0,1%–5% (§3.12).
- Os critérios de sucesso SC-01 a SC-04 e SC-06 são metas propostas, não exigências do professor.
- Parâmetros técnicos (validação interna de 10%, paciência, tetos de tempo, nº de tentativas) ficam
  no [plan.md](plan.md).

## 3.6 Formulação do problema de ML

- **Tipo:** classificação binária (com probabilidade calibrada como produto principal).
- **Unidade de predição:** uma notificação de caso confirmado de dengue (uma linha do SINAN).
  - **Duplicidade (D-47):** não há identificador pessoal, e a chave composta disponível marca de 17% a 42% da população como "duplicada", o que é implausível. Decisão: **não remover**; reportar a taxa como limitação e rodar uma análise de sensibilidade com chave mais estrita (+ unidade notificadora + data de notificação). Números e `NDUPLIC_N`: [data-model.md](data-model.md), §3.7.
- **População (D-06, revisada em D-45):** casos com `CLASSI_FIN` ∈ {10, 11, 12} **e** rótulo conhecido **e** idade válida:
  - `CLASSI_FIN` = 12 (dengue grave): entra com **qualquer** evolução, porque y = 1 já é conhecido pela classificação.
  - `CLASSI_FIN` = 10 ou 11: entra só com `EVOLUCAO` ∈ {1, 2} (cura ou óbito pelo agravo), porque sem evolução não se sabe se houve óbito.
  - Idade válida: `NU_IDADE_N` decodificado em [0, 120]; se o código for inválido ou a idade cair fora dessa faixa, ano dos sintomas − `ANO_NASC` (D-49, D-50).
  - Excluídos: inconclusivos (8), código 0 e branco em `CLASSI_FIN`; casos 10/11 com evolução ignorada (9), em branco, com código 0, em investigação ou óbito por outras causas; idade inválida. O fluxograma (FR-02) conta cada motivo.
- **Alvo (D-02):** `y = 1` se `CLASSI_FIN = dengue grave` **OU** `EVOLUCAO = óbito pelo agravo`; senão `y = 0`.
  - **Codificação verificada no profiling:** os arquivos usam 10 / 11 / 12 (dengue / com sinais de alarme / grave) e 8 = inconclusivo; os códigos 1 e 2 do dicionário de 2024 não aparecem, então a regra de D-02 vale. Dicionários, contagens e o código anômalo 0: [data-model.md](data-model.md), §3.7.
  - O MS chama de "casos graves" a soma de dengue com sinais de alarme e dengue grave. O alvo deste projeto é mais estrito; ao comparar com números oficiais, o relatório explicita a diferença.
  - **Divergência do pré-projeto (D-22):** o pré-projeto enviado ao professor define agravamento como hospitalização, sinais de alarme, dengue grave ou óbito (de `EVOLUCAO`, `CLASSI_FIN` e `HOSPITALIZ`). O spec mantém o alvo estrito. O relatório MUST ter um parágrafo explicando a mudança e os dois motivos:
    - **Hospitalização é circular:** a decisão de internar depende da conduta médica, que já usa comorbidade como critério (§3.2), e da disponibilidade de leitos. Parte da associação "comorbidade → hospitalização" mediria a conduta, não a evolução do paciente.
    - **Sinais de alarme são um estado intermediário:** eles indicam risco de progressão, não um desfecho. Também são o ponto de partida do M2.
- **Momento da predição (D-03):**
  - **M1 — primeiro atendimento (base):** só informação disponível na notificação: perfil do paciente, comorbidades, sintomas iniciais. Sinais de alarme e gravidade ficam de fora.
  - **M2 — após sinais de alarme (extra):** M1 + campos `ALRM_*`. Responde "dado que já apareceram sinais de alarme, vai virar grave/óbito?".
    - **Restrição obrigatória:** pelo dicionário, os campos `ALRM_*` só são habilitados quando `CLASSI_FIN` = 11 ou 12. Nos dados, o preenchimento de `ALRM_*` continua revelando a classificação final (números no [data-model.md](data-model.md), §3.7). Por isso a população de M2 é **só** `CLASSI_FIN` ∈ {11, 12}, com `y = 1` se 12 ou óbito pelo agravo.
  - Em **nenhum** dos dois entram sinais de gravidade (`GRAV_*`): eles definem "dengue grave" e seriam o próprio rótulo.
- **Fonte e qualidade do rótulo:** classificação feita pela vigilância no encerramento do caso.
  - Ruído conhecido: subnotificação de casos leves, encerramento por critério clínico-epidemiológico, variação de qualidade entre UFs.
  - Óbitos passam por investigação, o que pode deixar suas fichas **mais completas** que as de casos leves — ver risco de vazamento em §3.8.

## 3.7 Dados

No [data-model.md](data-model.md) (D-55): fonte, licença, tamanho, dicionários, codificação, missingness, vieses e checks de qualidade.

## 3.8 Split e vazamento

### Estratégia de split — D-08: temporal + validação interna-externa por região

| Etapa | Dados | Uso |
|---|---|---|
| **Desenvolvimento** | 2022–2023 (ano do arquivo, D-46), todas as regiões | Validação cruzada **leave-one-region-out** (5 dobras: Norte, Nordeste, Centro-Oeste, Sudeste, Sul). Em cada dobra, treina em 4 regiões e prediz a 5ª. |
| Tuning | Predições fora da dobra (2022–23) | Hiperparâmetros escolhidos pela PR-AUC média entre as 5 dobras (§3.11). |
| Calibração e limiar | Predições fora da dobra (2022–23), agrupadas | Calibrador (isotônica/Platt) e limiar ajustados nessas predições (§3.12). |
| **Modelo final** | 2022–2023 completo | Retreino com os hiperparâmetros escolhidos; aplica o calibrador e o limiar da etapa anterior. |
| **Teste (congelado)** | 2024 (ano do arquivo, D-46) | Avaliado **uma única vez**, no fim (FR-09). Conta como validação externa temporal. |

Por que esse desenho: evidência em [research.md](research.md), R.2.


**Tamanho do teste.** Teste grande é vantagem: o que importa é o número de **eventos**. A regra prática é ≥ 100 eventos e 100 não-eventos, com ~200/200 para avaliar calibração com precisão; o cálculo específico de [Riley et al. (Stat Med 2021)](https://doi.org/10.1002/sim.9025) é preferível a regras fixas.
- **Eventos no teste de 2024**: 11.338 no total. Por subgrupo: 0–4 anos 259; 5–14 anos 536; 15–39 anos 2.647; 40–59 anos 2.380; 60–79 anos 3.313; 80+ anos 2.203; sexo F 6.046 e M 5.285; gestantes **102**; regiões Centro-Oeste 1.682, Nordeste 942, **Norte 110**, Sudeste 6.510, Sul 2.094. Ficam abaixo de 100 o sexo "I" (7 eventos) e o sexo em branco (8 casos, nenhum evento); gestantes e Norte ficam no limite. Esses quatro vêm com aviso de IC largo, sem conclusões.
- **Eventos por região no desenvolvimento (dobras leave-one-region-out)**: Centro-Oeste 736, Nordeste 582, **Norte 121**, Sudeste 1.736, Sul 810. Todas as dobras têm ≥ 100 eventos; o Norte fica no limite, então sua calibração terá IC largo.
- **Ano do split (D-46):** o ano é o **ano do arquivo**, que coincide com o ano da notificação em 99,98% dos casos (exceções: 680 casos de 2024 no arquivo de 2023; 284 de 2023 e 477 de 2025 no de 2024). O arquivo de 2024 tem 5.238 casos com sintomas em 2023, que ficam no teste.

Regras gerais:
- Todo pré-processamento (imputação, encoding, calibração) é ajustado só nos dados de desenvolvimento, dentro de cada dobra.
- `[ASSUMPTION]` Ano e semana epidemiológica **não** entram como features: com split temporal, o modelo não pode extrapolar um ano que nunca viu.
- UF/região **não** entram como features (D-21): em leave-one-region-out, a região deixada de fora nunca apareceria no treino, e as predições fora da dobra não representariam o modelo final.
- Limitação conhecida: tuning e calibração usam as mesmas predições fora da dobra, o que pode deixar as métricas de desenvolvimento um pouco otimistas. Por isso o teste de 2024 continua intocado.

### Revisão de vazamento (por grupo de campos)

Nomes de campo conferidos nos dicionários em 2026-11-01 e no arquivo real em 2026-11-02: maiúsculas, sem acento (`PETEQUIA_N`).

| Campo(s) | Disponível em M1? | Decisão | Motivo |
|---|---|---|---|
| Idade (`NU_IDADE_N`, decodificada), sexo (`CS_SEXO`), gestação (`CS_GESTANT`) | Sim | Entra | Perfil do paciente. |
| Raça/cor (`CS_RACA`), escolaridade (`CS_ESCOL_N`) | Sim | **Fora como feature** (D-48) | Escolaridade tem 50–54% de ignorado. Raça/cor (16–20% de ignorado) não entra como preditor clínico, mas é **subgrupo** de avaliação de equidade (§3.12). |
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

**Vazamento por completude da ficha** (casos graves são investigados e poderiam ter comorbidades mais preenchidas, fazendo de "Ausente" um marcador de "não grave"): checado no profiling e **não confirmado** — "Ausente" é ~0% nos dois desfechos na população final (§3.7, D-49).

## 3.9 Features e pré-processamento

No [plan.md](plan.md#39-features-e-pré-processamento) (D-54). Dicionário de features no [data-model.md](data-model.md), §D; revisão de vazamento aqui, em §3.8.

## 3.10 Baselines

Todos obrigatórios (FR-04). Todos os modelos são julgados contra eles.

- **B0 — trivial:** prevê a prevalência do treino para todos. PR-AUC de B0 = prevalência (piso absoluto), entre **~0,0016 e ~0,0021** (§3.7).
- **B1 — logística simples:** efeitos principais (idade em splines, sexo, gestação, 7 comorbidades, nº de comorbidades), sem interações.
- **B2 — regra do protocolo:** "alto risco" se o caso cumprir qualquer critério do grupo B do protocolo do MS (6ª ed., 2024; §3.2) que exista na ficha. Mapeamento `[ASSUMPTION]`, a revisar pelo grupo:
  - idade < 24 meses **ou** > 65 anos;
  - gestante (`CS_GESTANT` 1–4);
  - ≥ 1 das 7 comorbidades = 1;
  - `LACO` = 1 (sangramento induzido) **ou** `PETEQUIA_N` = 1 (sangramento de pele espontâneo).
  - Fora do mapeamento, por não existirem na ficha: DPOC, asma, obesidade, outras doenças cardiovasculares e risco social.
  - É uma regra binária: entra na comparação de recall/precisão no limiar, não de PR-AUC.

## 3.11 Modelagem

No [plan.md](plan.md#311-modelagem) (D-54): E1, candidatos de M1, busca de hiperparâmetros, early stopping, comparação e regra de seleção.

## 3.12 Plano de avaliação

- **Métrica primária (D-09):** **PR-AUC** (average precision). Com positivos raros, a ROC-AUC fica alta mesmo quando o modelo erra muito na classe positiva; a PR-AUC mede o desempenho exatamente onde está o erro caro.
- **Secundárias:** Brier score, curva de calibração (calibration slope e intercept), ROC-AUC (para comparação com a literatura).
- **Métricas no limiar (D-24, D-33):** acurácia, precisão, recall e F1 no limiar escolhido, prometidas no pré-projeto, e **F2**.
  - **F2 em vez de F0.5 (D-33):** o F2 prioriza o recall, como pede o custo de erro (D-14); o F0.5 sugerido pelo professor favorece a precisão. O relatório explica a escolha.
  - Na tabela de resultados, sempre ao lado de **B0** e **B2**.
  - B0 no limiar prevê "ninguém agrava": acurácia ≈ 1 − prevalência, recall = 0. O relatório usa essa linha para mostrar por que a acurácia não serve como métrica de decisão com classe rara.
  - Não são critério de seleção de modelo (§3.11 usa PR-AUC).
- **Limiar:** escolhido nas predições calibradas fora da dobra (2022–23, FR-17), como o que **maximiza o F2** (D-33). O recall resultante é reportado, em vez de fixado antes.
- **Utilidade clínica (D-39):** curva de decisão (*decision curve analysis*, net benefit) no teste para o melhor M1, B1 e a regra do protocolo (B2), contra "tratar todos" e "tratar ninguém", numa faixa de limiares de risco plausível para triagem `[ASSUMPTION]`, ajustada à prevalência observada de 0,16%–0,21% (§3.7): **0,1%–5%**, ou seja, até ~30 vezes o risco médio. O limiar F2 aparece como um ponto de operação marcado na curva, e não como a única justificativa do limiar. Síntese das referências (Vickers & Holland 2021; benchmark com F2 + DCA) em `research/consensus-boas-praticas.md` (cópia local, fora do repositório: termos do Consensus).
- **Calibração:** obrigatória, porque o produto é "qual o risco". Isotônica ou Platt, ajustada nas predições fora da dobra (FR-17). No teste, reportar a curva de calibração e o calibration slope: é a métrica que a literatura mostra degradar primeiro sob drift (§3.8).
- **Variação entre regiões no desenvolvimento:** reportar PR-AUC e calibration slope de cada dobra leave-one-region-out. É a medida de robustez geográfica do modelo.
- **Incerteza:** IC 95% por bootstrap no teste, para todas as métricas e para a **diferença** de PR-AUC entre o melhor modelo e B1. Número de reamostras e alternativas: [plan.md](plan.md), §3.11.
- **Subgrupos (D-13, D-48):** faixa etária; sexo e gestantes; região/UF; **raça/cor** (com "ignorado" como categoria). Reportar PR-AUC, recall no limiar e calibração por subgrupo, com IC. Subgrupos com < 100 eventos no teste, ou no limite (sexo "I" com 7; sexo em branco com 0; gestantes com 102; Norte com 110), vêm com aviso de IC largo (§3.8).
- **Análise de erros:** inspecionar os 100 falsos negativos com maior risco não detectado `[ASSUMPTION]`, por perfil (idade, comorbidades, UF, atraso de notificação), e as células de comorbidade com pior calibração.
- **Privacidade nas tabelas:** células de perfil com < 10 casos não são publicadas `[ASSUMPTION]`.
- **Critérios de aceitação:** SC-01 a SC-04 (Critérios de sucesso).

## 3.13 Interpretabilidade e equidade

- **Coeficientes / OR da E1:** a principal ferramenta de explicação. São associações ajustadas por idade e sexo, **não efeitos causais**. Ex.: hipertensão é correlacionada com idade e com doença renal; parte do "efeito" pode ser confundimento residual.
- **Tabela de perfis:** traduz o modelo para a pergunta original ("qual o risco de um hipertenso de 65 anos?").
- **SHAP local na demo (D-35):** a aba Triagem mostra, para cada caso, os 5 fatores que mais mexeram no risco (§3.15). É explicação do **modelo** para aquele caso, não causa clínica.
- **SHAP (FR-13):** valores SHAP e SHAP interaction values do modelo de árvore, numa subamostra estratificada, por custo computacional (tamanho no [plan.md](plan.md), §3.11). Limitação: o SHAP explica o **modelo**, não o mundo; com features correlacionadas, a atribuição entre elas é instável.
- **Equidade:** comparar desempenho e calibração entre regiões e faixas etárias (§3.12). Um modelo pior calibrado no Norte/Nordeste, por exemplo, pode refletir diferenças de notificação, não de risco. Isso será discutido no relatório.

## 3.14 Reprodutibilidade e rastreio de experimentos

No [plan.md](plan.md#314-reprodutibilidade-e-rastreio-de-experimentos) (D-54). O critério é NFR-02 (§3.5).

## 3.15 Entregáveis e interfaces

No [contracts/interfaces.md](contracts/interfaces.md) (D-55): contrato da CLI, formato da tabela de perfis e demo. O mapeamento para o que o professor exige está em §3.19.

## 3.16 Registro de decisões

No [research.md](research.md) (D-55), com contexto, opções, decisão e consequências de D-01 em diante.

## 3.17 Riscos

| Risco | Prob. | Impacto | Mitigação |
|---|---|---|---|
| Download do FTP do DataSUS lento ou instável | Média | Alto | Salvar Parquet no Drive; carregar só as colunas usadas. |
| Poucos positivos em combinações raras de comorbidades | **Confirmada** | Médio | Só 3.985 eventos no desenvolvimento (prevalência ~0,16%) e comorbidades raras (~0,5% cada). Mínimo de eventos por célula; `[VERIFY]` eventos por par de comorbidades no Marco 2; considerar opção B de D-08 (mais anos). |
| Diferença de sistema de origem no ES (`TP_SISTEMA`) | Média | Baixo | Registrar como limitação; olhar o ES na análise de erros. |
| Códigos de `CLASSI_FIN`/`EVOLUCAO` mudam entre anos | Baixa | Alto | 2022–24 usam a mesma codificação (§3.6); validar domínio por ano (FR-03) e testes unitários da geração do alvo. |
| Mudança de distribuição em 2024 (epidemia, sorotipo) | Alta | Médio | É o que o teste temporal mede; reportar e discutir, não esconder. |
| Ruído no rótulo (encerramento clínico, variação por UF) | Média | Médio | Subgrupos por região; discutir no relatório. |
| RAM insuficiente no Colab (RF, SHAP) | Média | Médio | Tipos enxutos, subamostra estratificada para RF/SHAP. |
| Validação por região multiplica o tempo de treino (5 dobras × 6 modelos × trials) | Alta | Médio | Orçamento de tempo por modelo ajustado pela cronometragem, poda e busca retomável (NFR-01); subamostra estratificada na busca; sessão única com marcador por modelo concluído (D-53). |
| Colab cai no meio da sessão única (~4 h) ou não oferece GPU | Alta | Médio | Marcador por modelo e estudo Optuna no Drive: a reexecução pula os concluídos e retoma o modelo em andamento (D-53); melhores pesos já salvos (FR-22); XGBoost e CatBoost também rodam em CPU; Kaggle como alternativa. |
| TabFM não comporta o volume (limite de contexto, GPU, velocidade) | Média | Médio | Verificar limites no model card antes do Marco 4; subamostra estratificada como contexto; registrar a restrição. |
| Melhor M1 (ex.: TabFM ou MLP) pesado demais para a demo ou sem SHAP rápido | Média | Médio | SHAP aproximado; se não cumprir NFR-06, decidir antes do Marco 5 (Q-14). |
| Profissional de saúde sugere mudança depois do teste | Média | Baixo | Não retreinar (teste já usado); registrar como limitação (FR-21). |
| Região com poucos eventos numa dobra | **Confirmada** | Médio | Norte com 121 eventos no desenvolvimento e 110 no teste (§3.8): reportar com aviso de IC largo. |
| ML não supera logística/regra | Média | Baixo | Resultado válido e reportável (§3.2). |
| Uso indevido do app público como ferramenta clínica | Baixa | Alto | Aviso fixo; sem recomendações de conduta. |
| Professor questiona o alvo diferente do pré-projeto (D-22) | Média | Médio | Parágrafo de justificativa no relatório (§3.6); se o professor exigir o alvo amplo, reabrir D-22. |

## 3.18 Marcos (milestones)

Marcos sem datas (D-31): cada um tem um objetivo, os FRs que completa e critérios de saída verificáveis. A ordem é a de dependência; datas e prazos continuam fora do spec (D-29). Composição e critérios `[ASSUMPTION]`, a revisar pelo grupo.

Os marcos se chamam **Marco 1…7** para não confundir com os momentos de predição M1/M2 (§3.6).

| Marco | Objetivo | FRs | Critérios de saída |
|---|---|---|---|
| **1 — Dados e profiling** | Ter os dados baixados, versionados e entendidos antes de qualquer modelo. | FR-01, FR-02, FR-03 | **Concluído em 2026-11-03** (3 execuções do [roteiro](../profiling/ROTEIRO.md)). Pendências que não bloqueiam: significado de `NDUPLIC_N` e `TP_SISTEMA` no dicionário. |
| **2 — Descrição, split e baselines** | Descrever a população e fixar o piso que todo modelo precisa superar. | FR-18, FR-04, FR-17 | Análise descritiva gerada. Dobras leave-one-region-out construídas. Métricas fora da dobra de B0, B1 e B2 registradas no MLflow. Eventos por par de comorbidades contados (decide quais interações o E1 estima). Teste de 2024 ainda intocado. |
| **3 — Modelo explicativo (E1)** | Responder à pergunta central: quais comorbidades e combinações estão associadas a maior risco. | FR-05, FR-06, FR-19 | OR com IC 95% e correção de Benjamini-Hochberg. Interações reportadas só com ≥ 10 eventos. Ranking de comorbidades com empates marcados. Tabela de perfis com células < 10 suprimidas. |
| **4 — Modelos preditivos (M1)** | Treinar, comparar e escolher o modelo de triagem. | FR-07, FR-08, FR-12, FR-13 | Os seis candidatos de FR-07 avaliados nas mesmas dobras, com busca registrada no MLflow (Q-08 respondida; limites do TabFM verificados; Q-14 decidida). Melhores pesos por dobra e melhor tentativa de cada modelo salvos no MLflow (FR-22). Calibrador e limiar ajustados nas predições fora da dobra. Modelo final escolhido pela regra de §3.11 **antes** de tocar no teste. E1 e M1 serializados com metadados. |
| **5 — Avaliação final no teste** | Medir o desempenho real, uma única vez, em 2024. | FR-09 | Teste usado uma vez, com o modelo congelado do Marco 4. Todas as métricas de §3.12 com IC bootstrap. Subgrupos e análise de erros feitos. Calibração de E1 em 2024 checada. Resultado registrado mesmo se pior que B1/B2. |
| **6 — Demo** | Permitir testar os dois modelos. | FR-11 | Demo pública com as abas Perfil e Triagem, usando os artefatos serializados (Marcos 3 e 4). Aviso de uso acadêmico nas duas abas. Nenhum microdado embarcado (NFR-03). Resposta < 1 s por perfil (NFR-06). |
| **7 — Relatório** | Explicar processo, decisões, resultados e passos seguidos. | FR-20, FR-21 | Checklist TRIPOD+AI preenchido. Apêndices A–C presentes. Revisão do profissional de saúde registrada no apêndice D, se houver. Justificativa do alvo (D-22) incluída. [checklists/requirements.md](checklists/requirements.md) passando. |

**Regras entre marcos**
- **O teste fica isolado até o Marco 5.** Nenhum marco anterior olha para 2024.
- **Extras que são modelos entram antes do Marco 5.** M2 (FR-14) precisa ser treinado e comparado até o Marco 4. Se entrarem depois, o teste passa a ser usado mais de uma vez, e isso deixa o resultado otimista. A análise de sensibilidade (FR-16) e a CLI (FR-10) podem vir depois.
- **Trabalho em paralelo:** o esqueleto da demo pode começar no Marco 2 com modelos fictícios, e o relatório pode ser escrito ao longo dos marcos. Os critérios de saída dos Marcos 6 e 7 dependem dos artefatos finais.

## 3.19 Mapeamento dos entregáveis acadêmicos

Exigências do professor, informadas pelo Programador em 2026-11-01 (D-26).

| Exigência | Seção |
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
| Desbalanceamento | §3.9, D-38 | Coberto: sem correção de desbalanceamento, com justificativa (D-38 substitui D-12). |
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

- **Resolvidas ou retiradas:** Q-01 e Q-02 (entrega e apresentação; D-26), Q-03 (D-33), Q-04 (D-47), Q-05 (D-48), Q-06 (D-49), Q-07 (D-32), Q-09 (D-29), Q-10 (papéis do grupo, fora do spec), Q-11 e Q-12 (D-30).
- **Q-08** `[OPEN QUESTION]` Espaço de busca de hiperparâmetros. Quem responde: Programador, a partir da proposta da T-4.0.
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
