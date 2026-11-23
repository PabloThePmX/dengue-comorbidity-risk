# Critérios de sucesso SC-01 a SC-04 (T-5.4)

Avaliação única em 2024 (R2). Este arquivo é o resultado do teste: não há nova avaliação com o mesmo lacre. Só agregados (R7); células de 1 a 9 aparecem como <10.

> Se o teste sair pior que a validação, reportar como resultado (drift); é proibido voltar e trocar modelo, peso, calibrador ou limiar.

## Resumo

| Critério | Valor medido (IC 95%) | Regra | Resultado |
|---|---|---|---|
| SC-01 | 0,032500 (0,030328; 0,035026) | IC da diferença M1 − B0 sem 0 e acima dele | **passou** |
| SC-02 | recall M1 − B2 = -0,0072 (-0,0151; 0,0005); precisão M1 − B2 = 0,00446 (0,00436; 0,00456) | recall do M1 ≥ B2 e precisão do M1 > B2 | **falhou** |
| SC-03 | 0,945 (0,933; 0,955) | slope entre 0,8 e 1,2 | **passou** |
| SC-04 | 0,018066 (0,016330; 0,020070) | diferença M1 − B1 reportada com IC | **passou** |

Passa/falha pela estimativa pontual, como o spec define. O IC é informado ao lado e as leituras abaixo dizem se ele sustenta o resultado. Reamostras: 1000.

## SC-01: M1 supera B0 em PR-AUC

- Diferença pareada (M1 − B0): 0,032500 (0,030328; 0,035026).
- O IC inclui 0: não. Resultado: **passou**.

## SC-02: recall e precisão do M1 contra a regra B2

- Limiar principal do M1 (congelado, D-92): 0,002155.
- Recall: M1 0,6528 (0,6444; 0,6618); B2 0,6601 (0,6510; 0,6687); diferença -0,0072 (-0,0151; 0,0005). Recall do M1 ≥ B2: não; o IC sustenta: não.
- Precisão: M1 0,00975 (0,00963; 0,00989); B2 0,00529 (0,00522; 0,00536); diferença 0,00446 (0,00436; 0,00456). Precisão do M1 > B2: sim; o IC sustenta: sim.
- Resultado: **falhou**. Recall igual com precisão igual falha: a precisão do M1 precisa ser maior.

## SC-03: calibration slope do M1

- Slope: 0,945 (0,933; 0,955).
- O IC inteiro cabe em [0,8; 1,2]: sim. Resultado: **passou**.

## SC-04: diferença de PR-AUC entre M1 e B1

- Diferença pareada (M1 − B1): 0,018066 (0,016330; 0,020070) (M1 acima do B1 (IC exclui 0)).
- Superar o B1 é desejável, não condição do critério. Reportado = passou: **passou**.

## Regra do teste

Se o teste sair pior que a validação, reportar como resultado (drift); é proibido voltar e trocar modelo, peso, calibrador ou limiar.

Nenhum modelo, peso, calibrador ou limiar foi alterado depois de ver o teste.


---
Só agregados; sem linhas individuais (R7).
