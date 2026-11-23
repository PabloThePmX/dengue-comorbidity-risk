# Análise de erros do M1 no teste (T-5.3)

Avaliação única em 2024 (R2). Este arquivo é o resultado do teste: não há nova avaliação com o mesmo lacre. Só agregados (R7); células de 1 a 9 aparecem como <10.

> Associação não é causa; diferenças de notificação não são diferenças de risco. Só agregados (R7): contagens de 1 a 9 aparecem como <10 e, nelas, a proporção também sai.

## Falsos negativos de maior risco previsto

Falsos negativos: eventos (y = 1) com risco calibrado do M1 abaixo do limiar principal congelado (D-92), do maior para o menor risco previsto. Ficam os 100 de maior risco previsto ([ASSUMPTION] do spec); empate de risco previsto: vence a linha que vem antes na ordem dos dados. Limiar principal do M1: 0,002155.

- Eventos: 11338; detectados (risco ≥ limiar): 7402; falsos negativos no total: 3936; no perfil: 100.
- Risco previsto dos 100 do perfil (quantis; nenhum valor individual): 1% = 0,002057; mediana = 0,002101; 99% = 0,002154 (o mínimo e o máximo são aproximados por esses quantis).

Perfil em agregados: cada coluna é a proporção do grupo na categoria. Compare os falsos negativos com todos os eventos e com os detectados para ver quem o modelo deixa passar. Células de 1 a 9 casos aparecem como <10, sem proporção.

| Dimensão | Categoria | Falsos negativos de maior risco | Todos os eventos | Eventos detectados |
|---|---|---|---|---|
| Faixa etária | 0–4 | <10 | 259 (2,3%) | 160 (2,2%) |
| Faixa etária | 5–14 | <10 | 536 (4,7%) | 217 (2,9%) |
| Faixa etária | 15–39 | 28 (28,0%) | 2647 (23,3%) | 956 (12,9%) |
| Faixa etária | 40–59 | 30 (30,0%) | 2380 (21,0%) | 1201 (16,2%) |
| Faixa etária | 60–79 | 31 (31,0%) | 3313 (29,2%) | 2681 (36,2%) |
| Faixa etária | 80+ | <10 | 2203 (19,4%) | 2187 (29,5%) |
| Sexo | F | 56 (56,0%) | 6046 (53,3%) | 3734 (50,4%) |
| Sexo | M | 44 (44,0%) | 5285 (46,6%) | 3662 (49,5%) |
| Sexo | I | 0 (0,0%) | <10 | <10 |
| Sexo | em branco | 0 (0,0%) | 0 (0,0%) | 0 (0,0%) |
| Gestante | gestante | <10 | 102 (0,9%) | 36 (0,5%) |
| Gestante | não gestante | 99 (99,0%) | 11236 (99,1%) | 7366 (99,5%) |
| Número de comorbidades | 0 | 76 (76,0%) | 6002 (52,9%) | 2535 (34,2%) |
| Número de comorbidades | 1 | 17 (17,0%) | 3040 (26,8%) | 2666 (36,0%) |
| Número de comorbidades | 2 | <10 | 1868 (16,5%) | 1778 (24,0%) |
| Número de comorbidades | 3+ | 0 (0,0%) | 428 (3,8%) | 423 (5,7%) |
| Comorbidade DIABETES | Sim | <10 | 2261 (19,9%) | 2107 (28,5%) |
| Comorbidade HEMATOLOG | Sim | <10 | 355 (3,1%) | 329 (4,4%) |
| Comorbidade HEPATOPAT | Sim | <10 | 258 (2,3%) | 242 (3,3%) |
| Comorbidade RENAL | Sim | 0 (0,0%) | 625 (5,5%) | 615 (8,3%) |
| Comorbidade HIPERTENSA | Sim | 16 (16,0%) | 4215 (37,2%) | 3887 (52,5%) |
| Comorbidade ACIDO_PEPT | Sim | 0 (0,0%) | 90 (0,8%) | 73 (1,0%) |
| Comorbidade AUTO_IMUNE | Sim | <10 | 350 (3,1%) | 320 (4,3%) |
| Região de residência | Sudeste | 51 (51,0%) | 6510 (57,4%) | 4398 (59,4%) |
| Região de residência | Sul | 19 (19,0%) | 2094 (18,5%) | 1357 (18,3%) |
| Região de residência | Centro-Oeste | 17 (17,0%) | 1682 (14,8%) | 1083 (14,6%) |
| Região de residência | Nordeste | 12 (12,0%) | 942 (8,3%) | 500 (6,8%) |
| Região de residência | Norte | <10 | 110 (1,0%) | 64 (0,9%) |
| Atraso até a notificação (dias) | 0–1 | 21 (21,0%) | 1898 (16,7%) | 918 (12,4%) |
| Atraso até a notificação (dias) | 2–3 | 19 (19,0%) | 2801 (24,7%) | 1464 (19,8%) |
| Atraso até a notificação (dias) | 4–6 | 35 (35,0%) | 3420 (30,2%) | 2374 (32,1%) |
| Atraso até a notificação (dias) | 7–14 | 17 (17,0%) | 2401 (21,2%) | 1942 (26,2%) |
| Atraso até a notificação (dias) | 15+ | <10 | 818 (7,2%) | 704 (9,5%) |
| Atraso até a notificação (dias) | sem data | 0 (0,0%) | 0 (0,0%) | 0 (0,0%) |

## Células de comorbidade com pior calibração

Observado/esperado e calibration-in-the-large (intercepto com offset logit(p)) por célula; IC 95% por bootstrap estratificado por alvo DENTRO da célula; as células se sobrepõem. Reamostra sem convergência do ajuste do slope: é descartada só para o slope e o intercepto; as demais métricas usam todas as reamostras. As descartadas são contadas e reportadas. Se mais de 5% das reamostras do subgrupo forem descartadas, o IC do slope e do intercepto sai como indisponível. Se o ajuste da amostra do subgrupo não convergir, o ponto estimado também sai como indisponível. (Decisão provisória, a confirmar.) Ordem: do maior desvio |ln(observado/esperado)| ao menor; sem métrica ao fim. Reamostras: 1000.

Referência: observado/esperado global do M1 = 1,301 (1,297; 1,305).

| Célula | Casos | Eventos | Observado/esperado (IC) | Intercepto (IC) | Slope (IC) | Reamostras descartadas | Leitura | Aviso |
|---|---|---|---|---|---|---|---|---|
| AUTO_IMUNE = Sim | 37794 | 350 | 1,527 (1,494; 1,559) | 0,443 (0,422; 0,465) | 0,935 (0,859; 1,005) | 0 | o modelo subestima o risco (observado > esperado) |  |
| 0 comorbidades | 4630761 | 6002 | 1,387 (1,385; 1,390) | 0,329 (0,327; 0,331) | 0,953 (0,932; 0,973) | 0 | o modelo subestima o risco (observado > esperado) |  |
| HEMATOLOG = Sim | 28894 | 355 | 1,311 (1,278; 1,342) | 0,288 (0,262; 0,312) | 0,834 (0,756; 0,903) | 0 | o modelo subestima o risco (observado > esperado) |  |
| 3 ou mais comorbidades | 21274 | 428 | 1,240 (1,203; 1,278) | 0,241 (0,208; 0,274) | 0,966 (0,903; 1,034) | 0 | o modelo subestima o risco (observado > esperado) |  |
| RENAL = Sim | 27077 | 625 | 1,228 (1,197; 1,260) | 0,232 (0,203; 0,261) | 0,946 (0,893; 1,000) | 0 | o modelo subestima o risco (observado > esperado) |  |
| 2 comorbidades | 161553 | 1868 | 1,224 (1,211; 1,235) | 0,213 (0,202; 0,222) | 0,909 (0,877; 0,941) | 0 | o modelo subestima o risco (observado > esperado) |  |
| DIABETES = Sim | 234904 | 2261 | 1,214 (1,203; 1,224) | 0,204 (0,195; 0,212) | 0,921 (0,892; 0,949) | 0 | o modelo subestima o risco (observado > esperado) |  |
| 1 comorbidade | 518157 | 3040 | 1,208 (1,201; 1,215) | 0,195 (0,189; 0,201) | 0,941 (0,916; 0,965) | 0 | o modelo subestima o risco (observado > esperado) |  |
| HEPATOPAT = Sim | 28314 | 258 | 1,199 (1,170; 1,233) | 0,192 (0,167; 0,220) | 0,954 (0,874; 1,044) | 0 | o modelo subestima o risco (observado > esperado) |  |
| HIPERTENSA = Sim | 544193 | 4215 | 1,184 (1,177; 1,191) | 0,176 (0,170; 0,182) | 0,956 (0,935; 0,976) | 0 | o modelo subestima o risco (observado > esperado) |  |
| ACIDO_PEPT = Sim | 28442 | 90 | 1,098 (1,069; 1,127) | 0,095 (0,068; 0,121) | 0,975 (0,847; 1,113) | 0 | o modelo subestima o risco (observado > esperado) | IC largo: poucos eventos; sem conclusões (menos de 100 eventos) |

## Espírito Santo à parte

Critério: UF de residência = Espírito Santo (código IBGE 32): município de residência e, na falta dele, a UF de residência (o mesmo critério da região). o ES usa o e-SUS Vigilância em Saúde desde 2020 e a origem do registro difere (data-model › Espírito Santo): diferença de preenchimento não é diferença de risco.
Casos sem UF conhecida (no resto do Brasil): 0.

| Grupo | Casos | Eventos | Taxa de eventos | PR-AUC (IC) | Recall (IC) | Precisão (IC) | Observado/esperado (IC) | Aviso |
|---|---|---|---|---|---|---|---|---|
| Espírito Santo | 117062 | 122 | 0,104% | 0,0242 (0,0135; 0,0519) | 0,615 (0,533; 0,705) | 0,0054 (0,0046; 0,0061) | 0,741 (0,727; 0,757) |  |
| Resto do Brasil | 5214683 | 11216 | 0,215% | 0,0348 (0,0325; 0,0374) | 0,653 (0,644; 0,663) | 0,0098 (0,0097; 0,0100) | 1,312 (1,308; 1,316) |  |


---
Só agregados; sem linhas individuais (R7).
