# Spec — Risco de desfecho grave em dengue por perfil de comorbidades

**Criado**: 2026-10-19 | **Atualizado**: 2026-11-15 | **Status**: rascunho v0.19
**Entrada**: pré-projeto enviado ao professor (Grupo 1, "Dengue e Comorbidades") e retorno do professor (2026-11-02).

> **O quê e por quê.** Objetivo em [goal.md](goal.md); como fazer em [plan.md](plan.md); dados em
> [data-model.md](data-model.md).
> Marco 1 (dados e profiling) concluído; próximo: Marco 2 ([tasks/02-fundacao.md](tasks/02-fundacao.md)).
> Números de dados, salvo indicação: 3ª execução do profiling (2026-11-03 04:21 UTC),
> [profiling/RESULTADOS.md](../profiling/RESULTADOS.md).

---

## Problema e contexto

- **Dor hoje:** em epidemias (ex.: 2024), serviços recebem volume muito acima da capacidade. Priorizar quem deve ser acompanhado de perto é crítico.
- **Como é feito hoje:** o protocolo do Ministério da Saúde classifica pacientes em grupos de manejo (A/B/C/D). Verificado em 2026-11-01 em *Dengue: diagnóstico e manejo clínico — adulto e criança*, 6ª ed., MS, 2024 (versão eletrônica preliminar), seção 6.2 e fluxograma:
  - **Grupo B** = dengue sem sinais de alarme, com sangramento de pele espontâneo ou induzido (prova do laço), **ou** com condição clínica especial / risco social / comorbidade.
  - Condições listadas: lactentes (< 24 meses), gestantes, adultos > 65 anos, hipertensão ou outras doenças cardiovasculares graves, diabetes, DPOC, asma, obesidade, doenças hematológicas crônicas, doença renal crônica, doença ácido-péptica, hepatopatias e doenças autoimunes.
  - Hemograma é **obrigatório** no grupo B e "a critério médico" no grupo A.
  - Observação para o relatório: o protocolo considera asma, DPOC e obesidade fatores de risco, mas a ficha do SINAN não registra nenhum deles (D-18).
- **Desafio ao próprio projeto:**
  - A pergunta "quais combinações são mais perigosas?" é de **inferência**. Ela é respondida por regressão logística com interações e taxas por perfil, não exige ML complexo.
  - A pergunta "qual o risco deste paciente?" é de **predição**. Aqui o ML só se justifica se superar a regra do protocolo (B2) e a logística simples (B1) ([Baselines](#baselines)).
  - Se o boosting não superar B1/B2, isso é um **resultado válido** e deve ser reportado como tal.

### Trabalhos relacionados e diferencial

Síntese da literatura (Rosa et al. 2026, Huang et al. 2020, Trindade et al. 2024 e as meta-análises sobre comorbidade): [research › Trabalhos relacionados](research.md#trabalhos-relacionados).

**Diferencial deste projeto** (D-25; reformula o do pré-projeto, que dizia que as comorbidades são "pouco exploradas como eixo central"; Rosa et al. já as usam e as destacam no SHAP):
1. **Combinações:** interações 2 a 2 entre comorbidades, com OR e IC 95% (E1, FR-05), e ranking com incerteza (FR-19). As meta-análises reportam comorbidades isoladas e, em geral, OR brutos.
2. **Risco absoluto calibrado por perfil** (FR-06), não só importância de feature.
3. **Comparação com a regra do protocolo do MS** (B2).
4. **Validação externa temporal (2024) e geográfica (leave-one-region-out)** (D-08), com prevalência natural e todas as classes vindas dos mesmos anos.

## Não-objetivos

Os objetivos estão em [goal.md](goal.md). Fica fora do escopo:

- **Doenças respiratórias** (asma, DPOC etc.): a ficha do SINAN não tem esse campo ([data-model › Comorbidades e sinais clínicos](data-model.md#comorbidades-e-sinais-clínicos)). Limitação documentada no relatório (D-18).
- Linkagem com SIH/SIM ou qualquer outra base.
- Inferência **causal** ("hipertensão causa piora"). Só associação ajustada.
- Ferramenta clínica real. O app é demonstração acadêmica, sem validação clínica.
- Previsão de surtos / número de casos (série temporal).
- Uso de resultados laboratoriais e sinais de gravidade como preditores ([Revisão de vazamento](#revisão-de-vazamento)).
- UF/região como **feature** (D-21). Região é usada só como subgrupo de avaliação e eixo da validação interna-externa.
- **Extras** (fora do escopo base): M2 pós-alarme (D-03) e análise de sensibilidade com 2017–2024 (D-08).

## Usuários e custo dos erros

`[ASSUMPTION]` Não há usuário clínico real; os usuários abaixo são hipotéticos, para guiar as escolhas de métrica.

| Usuário | Decisão que muda |
|---|---|
| Médico / enfermeiro na triagem | Quem recebe retorno precoce, reavaliação em 24–48 h ou observação. |
| Analista de vigilância / gestor | Quais perfis priorizar em campanhas e orientação (ex.: renais crônicos). |
| Banca / professor | Se o modelo acrescenta valor sobre a regra do protocolo. |

**Custo dos erros (D-14)**
- **Falso negativo** (diz "baixo risco" para quem evolui para grave/óbito): erro **muito mais caro**. Pode atrasar o reconhecimento de um paciente que vai piorar.
- **Falso positivo** (diz "alto risco" para quem não piora): custa monitoramento extra e ocupação do serviço.
- Consequência: o limiar prioriza recall alto. Ele é o de **precisão máxima entre os que dão recall ≥ ao da regra B2** nas predições calibradas fora da dobra (D-92, [Plano de avaliação](#plano-de-avaliação)); o ponto de F2 máximo (D-33) é reportado como ponto secundário.

## Cenários de usuário

Histórias em ordem de prioridade; cada uma pode ser testada sozinha. O relatório (FR-20) é
transversal e fecha no Marco 7 ([tasks/07-relatorio.md](tasks/07-relatorio.md)).

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

- **Por que P2:** é o objetivo secundário (D-01) e só se justifica se superar B1 e B2.
- **Teste independente:** com o M1 congelado, gerar predições fora da dobra (2022–23) e no teste
  (2024) e compará-las com B0, B1 e B2, sem a demo.
- **Cenários de aceitação:**
  1. **Dado** o desenvolvimento 2022–23, **quando** os seis candidatos são avaliados nas mesmas
     dobras, **então** cada um tem PR-AUC por dobra e média, e um é escolhido pela
     [regra de seleção](plan.md#regra-de-seleção) sem ler 2024 (FR-07, FR-17).
  2. **Dado** o M1 congelado, **quando** é avaliado em 2024 uma única vez, **então** todas as
     métricas do [Plano de avaliação](#plano-de-avaliação) saem com IC 95% e por subgrupo (FR-09).
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

- Óbito pelo agravo com classificação "dengue" (10) → `y = 1` ([Formulação](#formulação-do-problema)).
- Dengue grave (12) com evolução em branco → entra na população com `y = 1` (D-45).
- Código de idade inválido → idade por ano dos sintomas − `ANO_NASC`; sem `ANO_NASC` utilizável, o
  caso sai e é contado no fluxograma (D-49, D-50). O ES de 2022 grava idade em anos simples
  ([data-model › Espírito Santo](data-model.md#espírito-santo)).
- Comorbidade ou sintoma em branco ou fora de 1/2 → categoria "Ausente" (D-07).
- Combinação de comorbidades com < 10 casos → fora da tabela publicada; na demo, o risco sai do E1
  com a nota de que vem da soma dos efeitos (D-52).
- Subgrupo com < 100 eventos no teste (sexo "I" ou em branco, gestantes, Norte) → reportado com
  aviso de IC largo, sem conclusões ([Tamanho do teste](#tamanho-do-teste-e-das-dobras)).
- Notificações com a mesma chave composta → mantidas; a taxa é reportada (D-47).
- Entrada da demo fora do domínio de [contracts › Entrada de casos](contracts/interfaces.md#entrada-de-casos)
  (ex.: idade > 120, dias > 60) → recusada com mensagem `[ASSUMPTION]`.

## Requisitos

### Funcionais

- **FR-01** — O pipeline MUST baixar os microdados SINAN-Dengue (Brasil, 2022–2024; D-04) direto do FTP do DataSUS (D-05) e salvá-los em Parquet com hash SHA-256 registrado, junto com o hash do `.dbc` original e a data de revisão do arquivo no DataSUS.
- **FR-02** — O pipeline MUST aplicar os filtros de população ([Formulação](#formulação-do-problema)) e gerar o alvo, emitindo um **fluxograma de exclusão** com a contagem de linhas após cada filtro.
- **FR-03** — O pipeline MUST executar os [checks de qualidade](data-model.md#checks-de-qualidade) e falhar com mensagem clara se algum check bloqueante falhar.
- **FR-04** — O pipeline MUST treinar e avaliar os baselines B0, B1 e B2 ([Baselines](#baselines)).
- **FR-05** — O pipeline MUST ajustar a regressão logística com interações 2 a 2 entre comorbidades ([plan › Modelagem](plan.md#modelagem)) e reportar, para cada par, a interação **multiplicativa** (OR) e a **aditiva** (RERI e AP), com IC 95% e correção para comparações múltiplas (D-40).
- **FR-06** — O pipeline MUST gerar a [tabela de perfis](contracts/interfaces.md#tabela-de-perfis) com risco calibrado e IC 95% para cada perfil. Perfis (D-52): sem comorbidades, cada uma das 7 comorbidades sozinha, cada par que entrou no E1 e **todas** as combinações de 3+ com ≥ 10 casos em 2022–23.
- **FR-07** — O pipeline MUST treinar e comparar, para M1, os seis candidatos ([plan › Modelagem](plan.md#modelagem)) nas mesmas dobras (D-32): logística elastic net, XGBoost, Random Forest, CatBoost, MLP e TabFM. A busca de hiperparâmetros é registrada no MLflow; o TabFM é zero-shot e não tem busca.
- **FR-08** — O pipeline MUST calibrar as probabilidades e escolher o limiar de decisão usando **apenas** dados de validação.
- **FR-09** — O pipeline MUST avaliar o modelo final no conjunto de teste **uma única vez**, reportando as métricas do [Plano de avaliação](#plano-de-avaliação) com IC bootstrap e por subgrupo.
- **FR-10** — O projeto MAY expor uma CLI que recebe um CSV no schema de [contracts › Entrada de casos](contracts/interfaces.md#entrada-de-casos) e grava um CSV de predições. Rebaixado de MUST em D-26: a demo cumpre o papel de testar o modelo.
- **FR-11** — O projeto MUST publicar uma demo Streamlit (Streamlit Community Cloud), com aviso de uso acadêmico, em **duas abas** (D-27):
  - **Perfil:** risco de E1 para idade, sexo, gestação e comorbidades.
  - **Triagem:** risco calibrado de M1, com a classificação "alto risco" no limiar escolhido e os 5 fatores que mais aumentaram ou reduziram o risco daquele caso (SHAP local, D-35).
  - Detalhes em [contracts › Demo](contracts/interfaces.md#demo).
- **FR-12** — O modelo serializado MUST incluir metadados: versão do código, hash dos dados, config, data de treino e métricas de validação.
- **FR-13** — O pipeline SHOULD calcular SHAP interaction values para o modelo de árvore, em subamostra estratificada ([Interpretabilidade](#interpretabilidade-e-equidade)).
- **FR-14** — O pipeline MAY treinar o modelo M2 (pós-sinais de alarme) — extra.
- ~~**FR-15** — O pipeline MAY treinar CatBoost e MLP — extra.~~ Absorvido por FR-07 em D-32: CatBoost e MLP passaram a ser obrigatórios.
- **FR-16** — O pipeline MAY repetir o desenho de [Split e vazamento](#split-e-vazamento) com dados de 2017–2024 como análise de sensibilidade (D-08) — extra.
- **FR-17** — O pipeline MUST gerar as predições fora da dobra da validação leave-one-region-out ([Split](#estratégia-de-split)) e usá-las para tuning, calibração e escolha do limiar.
- **FR-18** — O pipeline MUST gerar a análise descritiva da população final (D-23), só com dados de desenvolvimento (2022–23), que são os usados no treino:
  - Tabela de características por desfecho (`y = 0` vs `y = 1`): idade, sexo, gestação, raça/cor, cada comorbidade, nº de comorbidades.
  - Risco bruto de `y = 1`, com IC 95%, por comorbidade, por nº de comorbidades (0, 1, 2, 3+) e por faixa etária.
  - Gráficos comparativos desses riscos.
  - Células com < 10 casos não são publicadas (R7).
  - Os riscos brutos são descritivos. Eles **não** substituem E1 nem alimentam a tabela de perfis (D-10, D-20).
- **FR-19** — O pipeline MUST gerar o **ranking de comorbidades** pelo OR ajustado de E1 (efeito principal, ajustado por idade e sexo), com IC 95% (D-23). Duas comorbidades cujos IC se sobrepõem são marcadas como **sem ordem definida** entre si.
- **FR-20** — O projeto MUST entregar um relatório estruturado pelo checklist **TRIPOD+AI** ([Collins et al., BMJ 2024](https://doi.org/10.1136/bmj-2023-074819)) (D-28), com:
  - processo, decisões e resultados de E1 e M1, incluindo baselines e a comparação logística vs Random Forest;
  - apêndice A: [registro de decisões](research.md#registro-de-decisões), com o que mudou desde o pré-projeto (D-22 a D-25);
  - apêndice B: fluxograma de exclusão (FR-02) e resultados do profiling;
  - apêndice C: "passos seguidos", uma cronologia das execuções exportada do MLflow (config, hash dos dados, métricas por execução);
  - apêndice D: revisão do profissional de saúde (FR-21), se houver.
- **FR-21** — O projeto SHOULD submeter os resultados a um profissional de saúde (médico, enfermeiro ou estudante da área) depois da avaliação no teste (Marco 5) (D-34). `[ASSUMPTION]` SHOULD, e não MUST, porque depende de conseguir alguém (Q-13).
  - O que é revisado: plausibilidade dos OR e do ranking de comorbidades (FR-19), tabela de perfis (FR-06), falsos negativos da análise de erros ([Plano de avaliação](#plano-de-avaliação)) e uso da demo (FR-11).
  - As observações entram no relatório (apêndice D), com quem revisou (função, sem dados pessoais) e quando.
  - **Regra:** sugestões que exigiriam mudar o modelo **não** são aplicadas, porque o teste de 2024 já foi usado (R2). Elas entram como limitação e trabalho futuro.
- **FR-22** — O pipeline MUST guardar os melhores pesos encontrados **na validação** (D-36, D-37), nunca no teste: o melhor ponto de cada modelo iterativo por dobra e a melhor tentativa de cada busca ficam salvos no MLflow. O teste de 2024 nunca escolhe peso; resultado pior no teste é reportado como resultado (drift). Como fazer: [plan › Early stopping e melhores pesos](plan.md#early-stopping-e-melhores-pesos).

### Não funcionais

- **NFR-01 (compute)** — Todo o pipeline MUST rodar tanto no Google Colab gratuito quanto no Colab Pro (D-44), com **orçamento de tempo por modelo** (D-42), e não um limite para o pipeline inteiro. Os 6 modelos rodam **numa sessão única**, com as mesmas dobras e a mesma semente, e são comparados no fim dela (D-53). Detalhes: [plan › Ambiente de execução e orçamento](plan.md#ambiente-de-execução-e-orçamento) (D-54).
- **NFR-02 (reprodutibilidade)** — Partindo de um checkout limpo + snapshot de dados com o hash registrado, a reexecução MUST reproduzir as métricas de teste com as mesmas 3 casas decimais.
- **NFR-03 (privacidade)** — Nenhum microdado (linha a linha) MUST ser versionado no repositório nem embarcado no app. O app MUST NOT armazenar as entradas do usuário.
- **NFR-04 (ética)** — Dados públicos e desidentificados (sem nome, CPF, endereço nem data de nascimento completa, mas com ano de nascimento, idade, sexo e município; [data-model › Dados pessoais](data-model.md#dados-pessoais)). Nenhum trâmite de ética é previsto (D-30).
  - No relatório, a dispensa se apoia na Resolução CNS 510/2016, art. 1º, parágrafo único, inciso II ("informações de acesso público", Lei 12.527/2011), e não em "não haver coleta direta", como no pré-projeto. Os dados são chamados de "desidentificados", não "anonimizados".
- **NFR-05 (manutenibilidade)** — Código em módulos Python (não só notebooks), com testes unitários (pytest) para geração do alvo, filtros de população e decodificação de idade; lint com ruff.
- **NFR-06 (latência)** — `[ASSUMPTION]` O app SHOULD responder em < 1 s por perfil.

Entidades (notificação, caso, perfil, dobra, modelo, predição): [data-model › Entidades](data-model.md#entidades).

## Critérios de sucesso

Resultados mensuráveis. SC-01 a SC-04 são os critérios de aceitação do teste; todos são
`[ASSUMPTION]` a confirmar pelo grupo.

- **SC-01** — O melhor M1 supera B0 em PR-AUC no teste, com IC 95% da diferença sem incluir 0.
- **SC-02** — No limiar escolhido, o recall do M1 é ≥ ao da regra B2, com precisão maior.
- **SC-03** — O calibration slope do M1 no teste fica entre 0,8 e 1,2.
- **SC-04** — A diferença de PR-AUC entre M1 e B1 é reportada com IC 95%, qualquer que seja o sinal.
  Superar B1 é desejável, mas não é condição de sucesso ([Problema e contexto](#problema-e-contexto)).
- **SC-05** — Toda comorbidade e todo par com ≥ 10 eventos têm OR e IC 95% no E1; nenhuma célula
  publicada tem < 10 casos (FR-05, NFR-03).
- **SC-06** — A demo responde em < 1 s por consulta (NFR-06).
- **SC-07** — A reexecução a partir de um checkout limpo reproduz as métricas de teste com 3 casas
  decimais (NFR-02).
- **SC-08** — O relatório cobre todos os itens do checklist TRIPOD+AI (FR-20).

## Premissas

Valores assumidos onde a entrada não decide. Cada um aparece também no ponto do texto em que se
aplica, marcado `[ASSUMPTION]`; esta lista serve para a revisão do Programador.

- Não há usuário clínico real; os [usuários](#usuários-e-custo-dos-erros) são hipotéticos e servem para guiar a métrica.
- "Gestante" = `CS_GESTANT` 1–4; faixas etárias 0–4, 5–14, 15–39, 40–59, 60–79 e 80+ ([data-model › Demografia e idade](data-model.md#demografia-e-idade)).
- `LEUCOPENIA`, `LACO` e os dias até a notificação estão disponíveis no primeiro atendimento ([Revisão de vazamento](#revisão-de-vazamento)).
- O mapeamento de B2 para o grupo B do protocolo usa só os critérios que existem na ficha ([Baselines](#baselines)).
- Interações e células só são reportadas com ≥ 10 eventos; correção por Benjamini-Hochberg (FDR 5%).
- A faixa de limiares da curva de decisão é 0,1%–5% ([Plano de avaliação](#plano-de-avaliação)).
- Os critérios de sucesso SC-01 a SC-04 e SC-06 são metas propostas, não exigências do professor.
- Parâmetros técnicos (validação interna de 10%, paciência, tetos de tempo, nº de tentativas) ficam
  no [plan.md](plan.md).

## Formulação do problema

- **Tipo:** classificação binária (com probabilidade calibrada como produto principal).
- **Unidade de predição:** uma notificação de caso confirmado de dengue (uma linha do SINAN).
  - **Duplicidade (D-47):** não há identificador pessoal, e a chave composta disponível marca de 17% a 42% da população como "duplicada", o que é implausível. Decisão: **não remover**; reportar a taxa como limitação e rodar uma análise de sensibilidade com chave mais estrita (+ unidade notificadora + data de notificação). Números e `NDUPLIC_N`: [data-model › Duplicidade](data-model.md#duplicidade).
- **População (D-06, revisada em D-45):** casos com `CLASSI_FIN` ∈ {10, 11, 12} **e** rótulo conhecido **e** idade válida:
  - `CLASSI_FIN` = 12 (dengue grave): entra com **qualquer** evolução, porque y = 1 já é conhecido pela classificação.
  - `CLASSI_FIN` = 10 ou 11: entra só com `EVOLUCAO` ∈ {1, 2} (cura ou óbito pelo agravo), porque sem evolução não se sabe se houve óbito.
  - Idade válida: `NU_IDADE_N` decodificado em [0, 120]; se o código for inválido ou a idade cair fora dessa faixa, ano dos sintomas − `ANO_NASC` (D-49, D-50).
  - Excluídos: inconclusivos (8), código 0 e branco em `CLASSI_FIN`; casos 10/11 com evolução ignorada (9), em branco, com código 0, em investigação ou óbito por outras causas; idade inválida. O fluxograma (FR-02) conta cada motivo.
- **Alvo (D-02):** `y = 1` se `CLASSI_FIN = dengue grave` **OU** `EVOLUCAO = óbito pelo agravo`; senão `y = 0`.
  - **Codificação verificada no profiling:** os arquivos usam 10 / 11 / 12 (dengue / com sinais de alarme / grave) e 8 = inconclusivo; os códigos 1 e 2 do dicionário de 2024 não aparecem, então a regra de D-02 vale. Dicionários, contagens e o código anômalo 0: [data-model › Codificação do alvo](data-model.md#codificação-do-alvo).
  - O MS chama de "casos graves" a soma de dengue com sinais de alarme e dengue grave. O alvo deste projeto é mais estrito; ao comparar com números oficiais, o relatório explicita a diferença.
  - **Divergência do pré-projeto (D-22):** o pré-projeto enviado ao professor define agravamento como hospitalização, sinais de alarme, dengue grave ou óbito (de `EVOLUCAO`, `CLASSI_FIN` e `HOSPITALIZ`). O spec mantém o alvo estrito. O relatório MUST ter um parágrafo explicando a mudança e os dois motivos:
    - **Hospitalização é circular:** a decisão de internar depende da conduta médica, que já usa comorbidade como critério ([Problema e contexto](#problema-e-contexto)), e da disponibilidade de leitos. Parte da associação "comorbidade → hospitalização" mediria a conduta, não a evolução do paciente.
    - **Sinais de alarme são um estado intermediário:** eles indicam risco de progressão, não um desfecho. Também são o ponto de partida do M2.
- **Momento da predição (D-03):**
  - **M1 — primeiro atendimento (base):** só informação disponível na notificação: perfil do paciente, comorbidades, sintomas iniciais. Sinais de alarme e gravidade ficam de fora.
  - **M2 — após sinais de alarme (extra):** M1 + campos `ALRM_*`. Responde "dado que já apareceram sinais de alarme, vai virar grave/óbito?".
    - **Restrição obrigatória:** pelo dicionário, os campos `ALRM_*` só são habilitados quando `CLASSI_FIN` = 11 ou 12. Nos dados, o preenchimento de `ALRM_*` continua revelando a classificação final ([data-model › Codificação do alvo](data-model.md#codificação-do-alvo)). Por isso a população de M2 é **só** `CLASSI_FIN` ∈ {11, 12}, com `y = 1` se 12 ou óbito pelo agravo.
  - Em **nenhum** dos dois entram sinais de gravidade (`GRAV_*`): eles definem "dengue grave" e seriam o próprio rótulo.
- **Fonte e qualidade do rótulo:** classificação feita pela vigilância no encerramento do caso.
  - Ruído conhecido: subnotificação de casos leves, encerramento por critério clínico-epidemiológico, variação de qualidade entre UFs.
  - Óbitos passam por investigação, o que pode deixar suas fichas **mais completas** que as de casos leves; ver vazamento por completude na [Revisão de vazamento](#revisão-de-vazamento).

## Split e vazamento

### Estratégia de split

D-08: temporal + validação interna-externa por região. Por que esse desenho:
[research › Evidência para o desenho de validação](research.md#evidência-para-o-desenho-de-validação).

| Etapa | Dados | Uso |
|---|---|---|
| **Desenvolvimento** | 2022–2023 (ano do arquivo, D-46), todas as regiões | Validação cruzada **leave-one-region-out** (5 dobras: Norte, Nordeste, Centro-Oeste, Sudeste, Sul). Em cada dobra, treina em 4 regiões e prediz a 5ª. |
| Tuning | Predições fora da dobra (2022–23) | Hiperparâmetros escolhidos pela PR-AUC média entre as 5 dobras ([plan › Modelagem](plan.md#modelagem)). |
| Calibração e limiar | Predições fora da dobra (2022–23), agrupadas | Calibrador (isotônica/Platt) e limiar ajustados nessas predições ([Plano de avaliação](#plano-de-avaliação)). |
| **Modelo final** | 2022–2023 completo | Retreino com os hiperparâmetros escolhidos; aplica o calibrador e o limiar da etapa anterior. |
| **Teste (congelado)** | 2024 (ano do arquivo, D-46) | Avaliado **uma única vez**, no fim (FR-09). Conta como validação externa temporal. |

- **Ano do split (D-46):** o ano é o **ano do arquivo**, que coincide com o da notificação em 99,98% dos casos ([data-model › Tamanho e prevalência](data-model.md#tamanho-e-prevalência)).
- Todo pré-processamento (imputação, encoding, calibração) é ajustado só nos dados de desenvolvimento, dentro de cada dobra.
- `[ASSUMPTION]` Ano e semana epidemiológica **não** entram como features: com split temporal, o modelo não pode extrapolar um ano que nunca viu.
- UF/região **não** entram como features (D-21): em leave-one-region-out, a região deixada de fora nunca apareceria no treino, e as predições fora da dobra não representariam o modelo final.
- Limitação conhecida: tuning e calibração usam as mesmas predições fora da dobra, o que pode deixar as métricas de desenvolvimento um pouco otimistas. Por isso o teste de 2024 continua intocado.

### Tamanho do teste e das dobras

O que importa é o número de **eventos**, não de linhas. A regra prática é ≥ 100 eventos e 100
não-eventos, com ~200/200 para avaliar calibração com precisão; o cálculo específico de
[Riley et al. (Stat Med 2021)](https://doi.org/10.1002/sim.9025) é preferível a regras fixas.
Contagens: [data-model › Eventos por região e subgrupo](data-model.md#eventos-por-região-e-subgrupo).

- **Dobras do desenvolvimento:** todas têm ≥ 100 eventos; o Norte (121) fica no limite, então sua calibração terá IC largo.
- **Teste de 2024:** 11.338 eventos. Ficam abaixo de 100 o sexo "I" (7 eventos) e o sexo em branco (nenhum evento); gestantes (102) e Norte (110) ficam no limite. **Esses quatro subgrupos vêm com aviso de IC largo, sem conclusões.**

### Revisão de vazamento

Por grupo de campos. Nomes conferidos nos dicionários em 2026-11-01 e no arquivo real em
2026-11-02: maiúsculas, sem acento (`PETEQUIA_N`). A lista final de features está no
[data-model › Dicionário de features](data-model.md#dicionário-de-features).

| Campo(s) | Disponível em M1? | Decisão | Motivo |
|---|---|---|---|
| Idade (`NU_IDADE_N`, decodificada), sexo (`CS_SEXO`), gestação (`CS_GESTANT`) | Sim | Entra | Perfil do paciente. |
| Raça/cor (`CS_RACA`), escolaridade (`CS_ESCOL_N`) | Sim | **Fora como feature** (D-48) | Escolaridade tem 50–54% de ignorado. Raça/cor (16–20% de ignorado) não entra como preditor clínico, mas é **subgrupo** de avaliação de equidade ([Plano de avaliação](#plano-de-avaliação)). |
| UF / região de residência (`SG_UF`, `ID_MN_RESI`) | Sim | **Fora como feature** (D-21) | Incompatível com leave-one-region-out; usada como subgrupo e eixo da validação. |
| 7 comorbidades do item 34 (`DIABETES`, `HEMATOLOG`, `HEPATOPAT`, `RENAL`, `HIPERTENSA`, `ACIDO_PEPT`, `AUTO_IMUNE`) + nº de comorbidades (derivada) | Sim | Entra | Objeto central do estudo. |
| Sintomas iniciais (`FEBRE`, `MIALGIA`, `CEFALEIA`, `EXANTEMA`, `VOMITO`, `NAUSEA`, `DOR_COSTAS`, `CONJUNTVIT`, `ARTRITE`, `ARTRALGIA`, `DOR_RETRO`, `PETEQUIA_N`) | Sim | Entra | Coletados na notificação. |
| `LEUCOPENIA`, `LACO` (prova do laço) | Sim | Entra `[ASSUMPTION]` | Ambos estão no item 33 da ficha ("sinais clínicos ou achados laboratoriais inespecíficos"), campo obrigatório 1/2. Ressalva: o hemograma só é obrigatório no grupo B do protocolo, então "não" em leucopenia pode significar "não foi feito". Documentar como limitação. |
| Dias entre início dos sintomas e notificação (`DT_NOTIFIC` − `DT_SIN_PRI`; as datas em si não entram) | Sim | Entra `[ASSUMPTION]` | Conhecido na notificação; proxy de busca por atendimento. |
| Resultados laboratoriais: sorologia (`DT_SORO`, `RESUL_SORO`), NS1 (`DT_NS1`, `RESUL_NS1`), isolamento viral (`DT_VIRAL`, `RESUL_VI_N`), PCR (`DT_PCR`, `RESUL_PCR_`), `SOROTIPO`, histopatologia (`HISTOPA_N`), imuno-histoquímica (`IMUNOH_N`) | **Não** | Fora | Chegam dias depois. |
| `CRITERIO` (laboratorial vs clínico-epidemiológico) | **Não** | Fora | Definido no encerramento. |
| `HOSPITALIZ`, data de internação (`DT_INTERNA`) | **Não** | Fora | Posterior à triagem e quase um desfecho. |
| Sinais de alarme (`ALRM_*`, `DT_ALRM`) | Não | Fora em M1; entra só em M2, com população restrita a `CLASSI_FIN` ∈ {11, 12} | Definem o momento M2. Só são habilitados para 11/12, então o preenchimento revela a classe ([Formulação](#formulação-do-problema)). |
| Sinais de gravidade (`GRAV_*`, `DT_GRAV`) | Não | **Fora sempre** | Definem o rótulo "dengue grave". |
| `CLASSI_FIN`, `EVOLUCAO`, `DT_OBITO`, `DT_ENCERRA` | Não | Fora | São o rótulo ou derivados dele. |
| Classificação antiga de febre hemorrágica (FHD): `MANI_HEMOR`, `EPISTAXE`, `GENGIVO`, `METRO`, `PETEQUIAS`, `HEMATURA`, `SANGRAM`, `LACO_N`, `PLASMATICO`, `EVIDENCIA`, `PLAQ_MENOR`, `CON_FHD`, `COMPLICA` | Não | **Fora sempre** | Manifestações hemorrágicas, extravasamento plasmático e plaquetopenia são critérios de gravidade: proxies do rótulo. Também tendem a ser preenchidos só em casos investigados (vazamento por completude). **Atenção:** `PETEQUIAS` e `LACO_N` são campos diferentes de `PETEQUIA_N` e `LACO` do item 33, que entram em M1. |
| Exames de chikungunya e PRNT: `DT_CHIK_S1`, `DT_CHIK_S2`, `RES_CHIKS1`, `RES_CHIKS2`, `DT_PRNT`, `RESUL_PRNT` | Não | Fora | Resultados laboratoriais; chegam depois da triagem (mesmo motivo da linha de exames). |
| Investigação e local de infecção: `DT_INVEST`, `TPAUTOCTO`, `COUFINF`, `COPAISINF`, `COMUNINF`, `DOENCA_TRA`, `CLINC_CHIK` | Não | Fora | Preenchidos na investigação ou no encerramento, depois da triagem. |
| Unidade e local de notificação: `ID_UNIDADE`, `ID_MUNICIP`, `SG_UF_NOT`, `ID_REGIONA`, `UF`, `MUNICIPIO` | Sim | Fora | A unidade notificadora é um proxy do tipo de serviço: casos notificados por hospital tendem a ser mais graves, então ela vazaria a gravidade. A geografia já está fora por D-21. |
| Administrativos e de sistema: `TP_NOT`, `ID_AGRAVO`, `NU_ANO`, `SEM_NOT`, `SEM_PRI`, `ID_PAIS`, `ID_RG_RESI`, `DT_DIGITA`, `TP_SISTEMA`, `NDUPLIC_N`, `CS_FLXRET`, `FLXRECEBI`, `MIGRADO_W` | — | Fora | Sem conteúdo clínico. `DT_DIGITA` é posterior à notificação; semana epidemiológica fora pela mesma razão do ano ([Estratégia de split](#estratégia-de-split)); `TP_SISTEMA` e `NDUPLIC_N` são usados só no profiling (cobertura do ES e duplicatas). |
| Ocupação (`ID_OCUPA_N`) | Sim | Fora `[ASSUMPTION]` | Alta ausência e códigos genéricos (Rosa et al. removeram pelo mesmo motivo). Reavaliar se o profiling mostrar preenchimento razoável. |
| Ano de nascimento (`ANO_NASC`) | Sim | Fora | Redundante com a idade decodificada; usado só para checar a decodificação e na chave de duplicatas. Os microdados não trazem `DT_NASC`. |

Cobertura da tabela: conferida em 2026-11-02 contra as **121 colunas** do arquivo `DENGBR22.dbc`. Toda coluna do arquivo aparece em alguma linha acima; as que não estão marcadas "Entra" ficam fora do modelo.

**Vazamento por completude da ficha** (casos graves são investigados e poderiam ter comorbidades mais preenchidas, fazendo de "Ausente" um marcador de "não grave"): checado no profiling e **não confirmado** — "Ausente" é ~0% nos dois desfechos na população final ([data-model › Ausência de dados](data-model.md#ausência-de-dados), D-49).

## Baselines

Todos obrigatórios (FR-04). Todos os modelos são julgados contra eles.

- **B0 — trivial:** prevê a prevalência do treino para todos. PR-AUC de B0 = prevalência (piso absoluto), entre **~0,0016 e ~0,0021** ([data-model › Tamanho e prevalência](data-model.md#tamanho-e-prevalência)).
- **B1 — logística simples:** efeitos principais (idade em splines, sexo, gestação, 7 comorbidades), sem interações. O nº de comorbidades fica de fora (D-62): é a soma das 7 comorbidades, e numa logística sem penalização a repetição deixa os coeficientes sem solução única, sem mudar as predições.
- **B2 — regra do protocolo:** "alto risco" se o caso cumprir qualquer critério do grupo B do protocolo do MS (6ª ed., 2024; [Problema e contexto](#problema-e-contexto)) que exista na ficha. Mapeamento `[ASSUMPTION]`, a revisar pelo grupo:
  - idade < 24 meses **ou** > 65 anos;
  - gestante (`CS_GESTANT` 1–4);
  - ≥ 1 das 7 comorbidades = 1;
  - `LACO` = 1 (sangramento induzido) **ou** `PETEQUIA_N` = 1 (sangramento de pele espontâneo).
  - Fora do mapeamento, por não existirem na ficha: DPOC, asma, obesidade, outras doenças cardiovasculares e risco social.
  - É uma regra binária: entra na comparação de recall/precisão no limiar, não de PR-AUC.

## Plano de avaliação

- **Métrica primária (D-09):** **PR-AUC** (average precision). Com positivos raros, a ROC-AUC fica alta mesmo quando o modelo erra muito na classe positiva; a PR-AUC mede o desempenho exatamente onde está o erro caro.
- **Secundárias:** Brier score, curva de calibração (calibration slope e intercept), ROC-AUC (para comparação com a literatura).
- **Métricas no limiar (D-24, D-33):** acurácia, precisão, recall e F1 no limiar escolhido, prometidas no pré-projeto, e **F2**.
  - **F2 em vez de F0.5 (D-33):** o F2 prioriza o recall, como pede o custo de erro (D-14); o F0.5 sugerido pelo professor favorece a precisão. O relatório explica a escolha.
  - Na tabela de resultados, sempre ao lado de **B0** e **B2**.
  - B0 no limiar prevê "ninguém agrava": acurácia ≈ 1 − prevalência, recall = 0. O relatório usa essa linha para mostrar por que a acurácia não serve como métrica de decisão com classe rara.
  - Não são critério de seleção de modelo (a [regra de seleção](plan.md#regra-de-seleção) usa PR-AUC).
- **Limiar (D-92, complementa D-33):** escolhido nas predições calibradas fora da dobra (2022–23, FR-17) como o de **precisão máxima entre os limiares com recall ≥ ao da regra B2 nas mesmas predições**; empate: o maior limiar; sem folga. É fixado antes do teste e congelado com o modelo. No teste, o recall resultante é reportado e o SC-02 o compara com o da B2 no teste. O limiar de **F2 máximo** (D-33) continua calculado nas mesmas predições e é reportado como ponto secundário, sem entrar no modelo congelado.
- **Utilidade clínica (D-39):** curva de decisão (*decision curve analysis*, net benefit) no teste para o melhor M1, B1 e a regra do protocolo (B2), contra "tratar todos" e "tratar ninguém", numa faixa de limiares de risco plausível para triagem `[ASSUMPTION]`, ajustada à prevalência observada de 0,16%–0,21%: **0,1%–5%**, ou seja, até ~30 vezes o risco médio. Os limiares principal (recall ≥ B2, D-92) e de F2 máximo (secundário, D-33) aparecem como pontos de operação marcados na curva, e nenhum deles é a única justificativa do limiar. Síntese das referências (Vickers & Holland 2021; benchmark com F2 + DCA) em `research/consensus-boas-praticas.md` (cópia local, fora do repositório: termos do Consensus).
- **Calibração:** obrigatória, porque o produto é "qual o risco". Isotônica ou Platt, ajustada nas predições fora da dobra (FR-17). No teste, reportar a curva de calibração e o calibration slope: é a métrica que a literatura mostra degradar primeiro sob drift ([research › Evidência para o desenho de validação](research.md#evidência-para-o-desenho-de-validação)).
- **Variação entre regiões no desenvolvimento:** reportar PR-AUC e calibration slope de cada dobra leave-one-region-out. É a medida de robustez geográfica do modelo.
- **Incerteza:** IC 95% por bootstrap no teste, para todas as métricas e para a **diferença** de PR-AUC entre o melhor modelo e B1. Número de reamostras e alternativas: [plan › Incerteza e comparação](plan.md#incerteza-e-comparação).
- **Subgrupos (D-13, D-48):** faixa etária; sexo e gestantes; região/UF; **raça/cor** (com "ignorado" como categoria). Reportar PR-AUC, recall no limiar e calibração por subgrupo, com IC. Os subgrupos com poucos eventos listados em [Tamanho do teste](#tamanho-do-teste-e-das-dobras) vêm com aviso de IC largo.
- **Análise de erros:** inspecionar os 100 falsos negativos com maior risco não detectado `[ASSUMPTION]`, por perfil (idade, comorbidades, UF, atraso de notificação), e as células de comorbidade com pior calibração.
- **Privacidade nas tabelas:** células de perfil com < 10 casos não são publicadas `[ASSUMPTION]` (R7).
- **Critérios de aceitação:** SC-01 a SC-04 ([Critérios de sucesso](#critérios-de-sucesso)).

## Interpretabilidade e equidade

- **Coeficientes / OR da E1:** a principal ferramenta de explicação. São associações ajustadas por idade e sexo, **não efeitos causais**. Ex.: hipertensão é correlacionada com idade e com doença renal; parte do "efeito" pode ser confundimento residual.
- **Tabela de perfis:** traduz o modelo para a pergunta original ("qual o risco de um hipertenso de 65 anos?").
- **SHAP local na demo (D-35):** a aba Triagem mostra, para cada caso, os 5 fatores que mais mexeram no risco ([contracts › Demo](contracts/interfaces.md#demo)). É explicação do **modelo** para aquele caso, não causa clínica.
- **SHAP (FR-13):** valores SHAP e SHAP interaction values do modelo de árvore, numa subamostra estratificada, por custo computacional (tamanho em [plan › Incerteza e comparação](plan.md#incerteza-e-comparação)). Limitação: o SHAP explica o **modelo**, não o mundo; com features correlacionadas, a atribuição entre elas é instável.
- **Equidade:** comparar desempenho e calibração entre regiões e faixas etárias ([Plano de avaliação](#plano-de-avaliação)). Um modelo pior calibrado no Norte/Nordeste, por exemplo, pode refletir diferenças de notificação, não de risco. Isso será discutido no relatório.

## Riscos

| Risco | Prob. | Impacto | Mitigação |
|---|---|---|---|
| Download do FTP do DataSUS lento ou instável | Média | Alto | Salvar Parquet no Drive; carregar só as colunas usadas. |
| Poucos positivos em combinações raras de comorbidades | **Confirmada** | Médio | Só 3.985 eventos no desenvolvimento (prevalência ~0,16%) e comorbidades raras (~0,5% cada). Mínimo de eventos por célula; `[VERIFY]` eventos por par de comorbidades no Marco 2; considerar opção B de D-08 (mais anos). |
| Diferença de sistema de origem no ES (`TP_SISTEMA`) | Média | Baixo | Registrar como limitação; olhar o ES na análise de erros. |
| Códigos de `CLASSI_FIN`/`EVOLUCAO` mudam entre anos | Baixa | Alto | 2022–24 usam a mesma codificação ([Formulação](#formulação-do-problema)); validar domínio por ano (FR-03) e testes unitários da geração do alvo. |
| Mudança de distribuição em 2024 (epidemia, sorotipo) | Alta | Médio | É o que o teste temporal mede; reportar e discutir, não esconder. |
| Ruído no rótulo (encerramento clínico, variação por UF) | Média | Médio | Subgrupos por região; discutir no relatório. |
| RAM insuficiente no Colab (RF, SHAP) | Média | Médio | Tipos enxutos, subamostra estratificada para RF/SHAP. |
| Validação por região multiplica o tempo de treino (5 dobras × 6 modelos × trials) | Alta | Médio | Orçamento de tempo por modelo ajustado pela cronometragem, poda e busca retomável (NFR-01); subamostra estratificada na busca; sessão única com marcador por modelo concluído (D-53). |
| Colab cai no meio da sessão única (~4 h) ou não oferece GPU | Alta | Médio | Marcador por modelo e estudo Optuna no Drive: a reexecução pula os concluídos e retoma o modelo em andamento (D-53); melhores pesos já salvos (FR-22); XGBoost e CatBoost também rodam em CPU; Kaggle como alternativa. |
| TabFM não comporta o volume (limite de contexto, GPU, velocidade) ou conflita com o torch do lock | Média | Médio | Subamostra estratificada como contexto; `tabfm` instalado só na sessão do Colab se o torch conflitar (D-69); registrar a restrição. |
| Melhor M1 (ex.: TabFM ou MLP) pesado demais para a demo, sem SHAP rápido ou impedido pela licença | Média | Médio | A demo usa o melhor modelo que couber, e o relatório explica (D-70). O TabFM nunca vai para a demo (D-69). |
| Profissional de saúde sugere mudança depois do teste | Média | Baixo | Não retreinar (teste já usado); registrar como limitação (FR-21). |
| Região com poucos eventos numa dobra | **Confirmada** | Médio | Norte com 121 eventos no desenvolvimento e 110 no teste ([Tamanho do teste](#tamanho-do-teste-e-das-dobras)): reportar com aviso de IC largo. |
| ML não supera logística/regra | Média | Baixo | Resultado válido e reportável ([Problema e contexto](#problema-e-contexto)). |
| Uso indevido do app público como ferramenta clínica | Baixa | Alto | Aviso fixo; sem recomendações de conduta. |
| Professor questiona o alvo diferente do pré-projeto (D-22) | Média | Médio | Parágrafo de justificativa no relatório ([Formulação](#formulação-do-problema)); se o professor exigir o alvo amplo, reabrir D-22. |

## Marcos

Marcos sem datas (D-31): cada um tem um objetivo, os FRs que completa e critérios de saída
verificáveis. A ordem é a de dependência; datas e prazos ficam fora do spec (D-29). Composição e
critérios `[ASSUMPTION]`, a revisar pelo grupo.

Os marcos se chamam **Marco 1…7** para não confundir com os modelos M1/M2. O Marco N é executado
pelas tarefas `T-N.x` do arquivo `tasks/0N-…md` (D-60).

| Marco | Objetivo | FRs | Critérios de saída |
|---|---|---|---|
| **1 — Dados e profiling** | Ter os dados baixados, versionados e entendidos antes de qualquer modelo. | FR-01, FR-02, FR-03 | **Concluído em 2026-11-03** (3 execuções do [roteiro](../profiling/ROTEIRO.md)). Pendências que não bloqueiam: significado de `NDUPLIC_N` e `TP_SISTEMA` no dicionário. |
| **2 — Descrição, split e baselines** | Descrever a população e fixar o piso que todo modelo precisa superar. | FR-18, FR-04, FR-17 | Análise descritiva gerada. Dobras leave-one-region-out construídas. Métricas fora da dobra de B0, B1 e B2 registradas no MLflow. Eventos por par de comorbidades contados (decide quais interações o E1 estima). Teste de 2024 ainda intocado. |
| **3 — Modelo explicativo (E1)** | Responder à pergunta central: quais comorbidades e combinações estão associadas a maior risco. | FR-05, FR-06, FR-19 | OR com IC 95% e correção de Benjamini-Hochberg. Interações reportadas só com ≥ 10 eventos. Ranking de comorbidades com empates marcados. Tabela de perfis com células < 10 suprimidas. |
| **4 — Modelos preditivos (M1)** | Treinar, comparar e escolher o modelo de triagem. | FR-07, FR-08, FR-12, FR-13 | Os seis candidatos de FR-07 avaliados nas mesmas dobras, com busca registrada no MLflow (espaço de busca definido na T-4.0, D-68; limites do TabFM verificados). Melhores pesos por dobra e melhor tentativa de cada modelo salvos no MLflow (FR-22). Calibrador e limiar ajustados nas predições fora da dobra. Modelo final escolhido pela [regra de seleção](plan.md#regra-de-seleção) **antes** de tocar no teste. E1 e M1 serializados com metadados. |
| **5 — Avaliação final no teste** | Medir o desempenho real, uma única vez, em 2024. | FR-09 | Teste usado uma vez, com o modelo congelado do Marco 4. Todas as métricas do [Plano de avaliação](#plano-de-avaliação) com IC bootstrap. Subgrupos e análise de erros feitos. Calibração de E1 em 2024 checada. Resultado registrado mesmo se pior que B1/B2. |
| **6 — Demo** | Permitir testar os dois modelos. | FR-11 | Demo pública com as abas Perfil e Triagem, usando os artefatos serializados (Marcos 3 e 4). Aviso de uso acadêmico nas duas abas. Nenhum microdado embarcado (NFR-03). Resposta < 1 s por perfil (NFR-06). |
| **7 — Relatório** | Explicar processo, decisões, resultados e passos seguidos. | FR-20, FR-21 | Checklist TRIPOD+AI preenchido. Apêndices A–C presentes. Revisão do profissional de saúde registrada no apêndice D, se houver. Justificativa do alvo (D-22) incluída. [checklists/requirements.md](checklists/requirements.md) passando. |

**Regras entre marcos**
- **O teste fica isolado até o Marco 5.** Nenhum marco anterior olha para 2024.
- **Extras que são modelos entram antes do Marco 5.** M2 (FR-14) precisa ser treinado e comparado até o Marco 4. Se entrarem depois, o teste passa a ser usado mais de uma vez, e isso deixa o resultado otimista. A análise de sensibilidade (FR-16) e a CLI (FR-10) podem vir depois.
- **Trabalho em paralelo:** o esqueleto da demo pode começar no Marco 2 com modelos fictícios, e o relatório pode ser escrito ao longo dos marcos. Os critérios de saída dos Marcos 6 e 7 dependem dos artefatos finais.

## Mapeamento acadêmico

**Exigências do professor**, informadas pelo Programador em 2026-11-01 (D-26):

| Exigência | O que o projeto entrega | Onde |
|---|---|---|
| Um modelo | E1 (perfil) e M1 (triagem), serializados com metadados | [plan › Modelagem](plan.md#modelagem), FR-05, FR-07, FR-12 |
| Uma demo para testá-lo | App Streamlit público com duas abas | [contracts › Demo](contracts/interfaces.md#demo), FR-11, D-17, D-27 |
| Relatório: processo | Relatório TRIPOD+AI (D-28) | FR-20; [Formulação](#formulação-do-problema), [data-model › Dados](data-model.md#dados), [Split e vazamento](#split-e-vazamento), [plan › Features](plan.md#features-e-pré-processamento) |
| Relatório: decisões | Apêndice A | FR-20; [research › Registro de decisões](research.md#registro-de-decisões) |
| Relatório: resultados | Seções de resultados | FR-20; [Plano de avaliação](#plano-de-avaliação), FR-06, FR-18, FR-19 |
| Relatório: passos seguidos | Apêndices B e C | FR-20; FR-02, [plan › Reprodutibilidade](plan.md#reprodutibilidade) (MLflow) |

Apoio (não exigido, mas necessário para o relatório e a reprodutibilidade): pipeline em módulos
Python, notebooks de profiling, explicação e avaliação, e MLflow. CLI só como extra (FR-10, MAY).

**Pré-projeto enviado ao professor** (Grupo 1, "Dengue e Comorbidades") → onde o spec cobre cada compromisso:

| Compromisso do pré-projeto | Onde | Situação |
|---|---|---|
| Fonte: SINAN/DataSUS | [data-model › Dados](data-model.md#dados), FR-01 | Coberto (FTP oficial do DataSUS, D-05). |
| 7 comorbidades como preditores | [data-model › Comorbidades](data-model.md#comorbidades-e-sinais-clínicos), [Revisão de vazamento](#revisão-de-vazamento) | Coberto. |
| Alvo: hospitalização, alarme, grave ou óbito | [Formulação](#formulação-do-problema), D-02, D-22 | **Divergente:** alvo estrito; justificativa obrigatória no relatório. |
| Logística vs Random Forest | [Baselines](#baselines) (B1), [plan › Modelagem](plan.md#modelagem) (E1, RF) | Coberto; boosting é acréscimo. |
| Acurácia, precisão, recall, F1, foco no recall | [Plano de avaliação](#plano-de-avaliação), D-24, D-14 | Coberto como métricas no limiar; PR-AUC primária. |
| Desbalanceamento | [plan › Features](plan.md#features-e-pré-processamento), D-38 | Coberto: sem correção de desbalanceamento, com justificativa (D-38 substitui D-12). |
| Sem empecilho ético | NFR-04 | Fundamento reformulado (CNS 510, inciso II). |
| Risco a partir de idade, sexo e comorbidades | [contracts › Tabela de perfis](contracts/interfaces.md#tabela-de-perfis), E1, D-20 | Coberto. |
| Ranking de comorbidades | FR-19 | Coberto. |
| Análise descritiva com tabelas e gráficos | FR-18 | Coberto. |
| Diferencial: comorbidades como eixo central | [Trabalhos relacionados e diferencial](#trabalhos-relacionados-e-diferencial), D-25 | Reformulado. |

**Retorno do professor sobre o pré-projeto** (recebido em 2026-11-02) → onde o spec cobre cada ponto:

| Comentário do professor | Onde | Situação |
|---|---|---|
| Testar mais modelos (XGBoost, MLP, TabFM, logística elastic net, CatBoost) | [plan › Modelagem](plan.md#modelagem), FR-07, D-32 | Coberto: os seis são obrigatórios em M1. |
| Cuidar com vazamento de dados | [Revisão de vazamento](#revisão-de-vazamento) (campo a campo, vazamento por completude), profiling passo 4 | Coberto. |
| Validar preditores e resultados com alguém da área da saúde | FR-21, D-34 | Parcial, por decisão do grupo: só os resultados. |
| Trabalhar a explicabilidade do modelo | [Interpretabilidade](#interpretabilidade-e-equidade), FR-13, FR-19, D-35 | Coberto: OR, ranking, perfis, SHAP global e SHAP local na demo. |
| Usar F0.5 ("F1 mais inclinado para o recall") | [Plano de avaliação](#plano-de-avaliação), D-33 | Ajustado: F2, que é o que favorece o recall, reportado como ponto secundário depois do D-92; o relatório explica. |
| Desenvolver um app legal para profissionais da saúde | [contracts › Demo](contracts/interfaces.md#demo), FR-11, D-27, D-35 | Coberto: demo com abas Perfil e Triagem, com explicação por caso. |

## Perguntas em aberto

- **Resolvidas ou retiradas:** Q-01 e Q-02 (entrega e apresentação; D-26), Q-03 (D-33), Q-04 (D-47), Q-05 (D-48), Q-06 (D-49), Q-07 (D-32), Q-09 (D-29), Q-10 (papéis do grupo, fora do spec), Q-11 e Q-12 (D-30).
- ~~**Q-08** Espaço de busca de hiperparâmetros.~~ Delegado ao agente na T-4.0 (D-68).
- **Q-13** `[OPEN QUESTION]` Quem será o profissional de saúde da revisão (FR-21)? Quem responde: grupo.
- ~~**Q-14** Modelo da demo se o melhor M1 não couber nela.~~ Resolvida no D-70: o melhor que couber, com o motivo no relatório.

## Glossário

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
- **M1 / M2** — momentos de predição e modelos correspondentes ([Formulação](#formulação-do-problema)). **E1** — modelo explicativo ([plan › Modelagem](plan.md#modelagem)). **B0–B2** — [Baselines](#baselines).
- **Marco** — etapa do projeto (1 a 7, [Marcos](#marcos)); não confundir com M1/M2.
