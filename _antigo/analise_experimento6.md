# Experimento 6: análise dos dados (Controlador P e PI)

Osciloscópio Tektronix TBS1052B, CSVs de `D:\NEW_FOLHHH\ALL0000` … `ALL0025`. CH1 = entrada e₁(t) (onda quadrada de 1 Vpp, ±0,5 V) e CH2 = tensão no capacitor V_c(t).

## Mapeamento das capturas

| Parte | R₂ = 5 kΩ | R₂ = 10 kΩ | R₂ = 20 kΩ / 40 kΩ | Obs. |
|---|---|---|---|---|
| 3 – RC, P | 0, 1 | 2, 3 | 20k: 4, 5 | 50 Hz |
| 4 – RLC, P | 10, 11 | 8, 9 | 20k: 6, 7 | 50 Hz |
| 5 – RC, PI | 16, 17 | 14, 15 | **20k**: 12, 13 | 50 Hz. O roteiro pede 40k, mas foi medido com 20k (os dados confirmam: K_p identificado ≈ 2,2) |
| 6 – RLC, PI | 18, 19 | 20, 21 | 40k: 24, 25 | 5k e 10k em **20 Hz**; 40k em 50 Hz |

As capturas 22/23 (anotadas como "4k") foram **descartadas**: CH2 fica em ≈ 0 V no semiciclo negativo e tem picos de ±4 V nas bordas, o que é incompatível com o circuito (provável saturação ou erro de ligação). Elas não fazem parte das tabelas.

**Método.** Cada valor experimental é a média de todas as bordas completas (subida e descida espelhada) das duas capturas do caso, com um filtro de média móvel de 60 µs para reduzir o ruído de quantização. Critérios:
- T_r de 10–90 % na 1ª ordem e de 0–100 % nos sistemas subamortecidos;
- T_s pelo critério de 2 %;
- ζ experimental a partir de M_p: ζ = −ln M_p / √(π² + ln² M_p);
- ω_d = π/T_p e ω_n = ω_d/√(1−ζ²).

## Modelo comum aos quatro circuitos

O 1º amp-op soma e₁ com −V_c (o 3º amp-op é um inversor de ganho 1), formando o erro. O 2º amp-op aplica G_c(s) = Z₂(s)/R e desfaz a inversão. O resultado é uma **realimentação unitária negativa**:

$$\frac{V_c(s)}{E_1(s)} = \frac{G_c(s)\,G(s)}{1 + G_c(s)\,G(s)}$$

- P: G_c = K_p = R₂/R, com R = 10 kΩ
- PI: G_c = K_p + K_i/s, com K_i = 1/(R·C_f) = 1/(10 kΩ · 10 nF) = **10⁴ s⁻¹**
- RC: G = 1/(R₁Cs + 1). RLC: G = 1/(LCs² + R₁Cs + 1)

---

## ⚠️ Achado principal: o capacitor efetivo é ≈ 4,2 µF, e não 1 µF

Os **valores de regime batem com a teoria em todos os casos**, mas **toda a dinâmica é mais lenta** do que o previsto:
- Parte 3: τ fica 3,8× a 4,2× maior que o teórico.
- Partes 4 a 6: ω_n fica ≈ metade da teórica.

A razão é a mesma para os três valores de K_p. Portanto o desvio está na planta, e não no controlador.

Ajustando o modelo às formas de onda da Parte 3, obtém-se **C_ef ≈ 4,17 µF**. Um capacitor de 4,7 µF (ou um eletrolítico com tolerância grande) explicaria isso. **Vale conferir qual capacitor foi usado.** Com esse valor:

- o modelo se sobrepõe às curvas medidas (painéis inferiores das figuras);
- o K_p identificado pelo ajuste fica **0,50 / 0,97 / 1,94** (Parte 3) e **0,54 / 1,03 / 2,07** (Parte 4), praticamente iguais a R₂/R = 0,5 / 1 / 2;
- na Parte 4, sobra só uma resistência série extra de ≈ 23 Ω (o enrolamento da bobina).

Assim, os "valores teóricos" das tabelas abaixo usam os **valores nominais do roteiro (C = 1 µF)**, e a discrepância é explicada pelo C efetivo.

---

## Parte 3: RC com controlador P

**Função de transferência**

$$\frac{V_c}{E_1} = \frac{K_p}{R_1C\,s + 1 + K_p} = \frac{K_p/(1+K_p)}{\tau s + 1}, \qquad \tau = \frac{R_1C}{1+K_p}, \qquad p = -\frac{1+K_p}{R_1C}$$

Com R₁C = 1 ms: T_r = 2,2τ, T_s = 4τ e V_c = 0,5·K_p/(1+K_p).

**Tabela 1**

| C = 1 µF, R₁ = 1 kΩ | τ exp | τ teo | T_r exp | T_r teo | T_s exp | T_s teo | V_c exp | V_c teo |
|---|---|---|---|---|---|---|---|---|
| R₂ = 5 kΩ | 2,53 ms | 0,67 ms | 5,31 ms | 1,47 ms | 8,5 ms | 2,67 ms | 0,152 V | 0,167 V |
| R₂ = 10 kΩ | 2,01 ms | 0,50 ms | 4,39 ms | 1,10 ms | 7,5 ms | 2,00 ms | 0,234 V | 0,250 V |
| R₂ = 20 kΩ | 1,40 ms | 0,33 ms | 3,11 ms | 0,73 ms | 5,6 ms | 1,33 ms | 0,325 V | 0,333 V |

**Erro estacionário e K_p.** O sistema é do tipo 0, então e_ss = 1/(1+K_p). Experimentalmente, e_ss = (A − V_c)/A e K_p = V_c/(A − V_c), com A = 0,496 V.

| R₂ | e_ss teo | e_ss exp | K_p teo | K_p exp (de V_c) |
|---|---|---|---|---|
| 5 kΩ | 66,7 % | 69,3 % | 0,50 | 0,44 |
| 10 kΩ | 50,0 % | 52,8 % | 1,00 | 0,89 |
| 20 kΩ | 33,3 % | 34,6 % | 2,00 | 1,89 |

![Parte 3 – respostas](figs/resposta_parte3.png)
![Parte 3 – lugar das raízes](figs/lgr_parte3.png)

**Análise**
- O regime concorda com a teoria (diferença de 2 a 9 %). Aumentar K_p reduz o erro, mas **ele nunca zera**, porque a malha é do tipo 0.
- A resposta é de 1ª ordem pura, sem sobressinal, como previsto. Ela é só ≈ 4× mais lenta, por causa do C_ef.
- **Lugar das raízes:** o polo é único e real, em s = −(1+K_p)/(R₁C). Ele anda para a esquerda com K_p, deixando a resposta mais rápida e com menos erro. O sistema é estável para qualquer K_p > −1 e nunca oscila.
- Polos teóricos: −1500, −2000 e −3000 s⁻¹. Polos experimentais (−1/τ): −395, −498 e −714 s⁻¹. Com C_ef, o modelo dá −360, −479 e −719 s⁻¹.

---

## Parte 4: RLC com controlador P

**Função de transferência**

$$\frac{V_c}{E_1} = \frac{K_p}{LC\,s^2 + R_1C\,s + 1 + K_p} = \frac{K\,\omega_n^2}{s^2 + 2\zeta\omega_n s + \omega_n^2}$$

$$\omega_n = \sqrt{\frac{1+K_p}{LC}}, \qquad \zeta = \frac{R_1}{2}\sqrt{\frac{C}{L(1+K_p)}}, \qquad K = \frac{K_p}{1+K_p}$$

A parte real dos polos é σ = ζω_n = R₁/(2L) = **649 s⁻¹**, independente de K_p. Logo T_s ≈ 4/σ = 6,16 ms nos três casos. As demais métricas: T_r = (π − arccos ζ)/ω_d, T_p = π/ω_d e M_p = e^(−ζπ/√(1−ζ²)).

**Tabela 2** (L = 77 mH, C = 1 µF, R₁ = 100 Ω)

| | T_r exp | T_r teo | T_p exp | T_p teo | M_p exp | M_p teo | T_s exp | T_s teo | V_c exp | V_c teo |
|---|---|---|---|---|---|---|---|---|---|---|
| R₂ = 5 kΩ | 0,93 ms | 0,39 ms | 1,48 ms | 0,72 ms | 31,1 % | 62,7 % | 5,5 ms | 6,2 ms | 0,171 V | 0,167 V |
| R₂ = 10 kΩ | 0,80 ms | 0,34 ms | 1,28 ms | 0,62 ms | 31,7 % | 66,8 % | 4,8 ms | 6,2 ms | 0,253 V | 0,250 V |
| R₂ = 20 kΩ | 0,62 ms | 0,27 ms | 1,09 ms | 0,51 ms | 42,4 % | 72,0 % | 5,4 ms | 6,2 ms | 0,334 V | 0,333 V |

**Tabela 3** (ω em rad/s)

| | ζ exp | ζ teo | ω_n exp | ω_n teo | ω_d exp | ω_d teo |
|---|---|---|---|---|---|---|
| R₂ = 5 kΩ | 0,348 | 0,147 | 2268 | 4414 | 2126 | 4366 |
| R₂ = 10 kΩ | 0,343 | 0,127 | 2613 | 5096 | 2454 | 5055 |
| R₂ = 20 kΩ | 0,263 | 0,104 | 2994 | 6242 | 2889 | 6208 |

**Erro estacionário e K_p**

| R₂ | e_ss teo | e_ss exp | K_p teo | K_p exp |
|---|---|---|---|---|
| 5 kΩ | 66,7 % | 65,5 % | 0,50 | 0,53 |
| 10 kΩ | 50,0 % | 48,9 % | 1,00 | 1,04 |
| 20 kΩ | 33,3 % | 32,6 % | 2,00 | 2,07 |

**Funções de transferência obtidas dos gráficos** (K = V_c/A, com ζ e ω_n medidos), comparadas com as teóricas:

| R₂ | T_exp(s) | T_teo(s) |
|---|---|---|
| 5 kΩ | 1,77·10⁶ / (s² + 1579 s + 5,14·10⁶) | 6,49·10⁶ / (s² + 1299 s + 19,5·10⁶) |
| 10 kΩ | 3,49·10⁶ / (s² + 1794 s + 6,83·10⁶) | 13,0·10⁶ / (s² + 1299 s + 26,0·10⁶) |
| 20 kΩ | 6,05·10⁶ / (s² + 1576 s + 8,97·10⁶) | 26,0·10⁶ / (s² + 1299 s + 39,0·10⁶) |

![Parte 4 – respostas](figs/resposta_parte4.png)
![Parte 4 – lugar das raízes](figs/lgr_parte4.png)

**Análise**
- O regime (V_c, e_ss e K_p) bate com a teoria. O erro diminui com K_p, mas não zera (tipo 0).
- **A tendência dinâmica é a prevista:** com K_p maior, ω_n sobe, ζ cai e M_p cresce.
- Os números divergem de forma coerente com C_ef ≈ 4 µF:
  - ω_n ∝ 1/√C, e a ω_n medida é ≈ 0,5× a teórica;
  - ζ ∝ √C, e o ζ medido é ≈ 2,5× o teórico;
  - por isso há menos sobressinal e a oscilação é mais lenta.
- σ = ζω_n **não depende de C**. A medida dá 790–900 s⁻¹, contra 649 s⁻¹ teórico. Isso indica ≈ 23 Ω de resistência série extra, da bobina. Coerentemente, T_s experimental quase não varia com K_p (4,8–5,5 ms).
- **Lugar das raízes:** os polos complexos sobem verticalmente sobre Re(s) = −R₁/(2L) conforme K_p aumenta. O sistema é sempre estável, mas fica menos amortecido e não acomoda mais rápido. Há um compromisso: K_p alto reduz o erro, e K_p baixo reduz o sobressinal.

---

## Parte 5: RC com controlador PI

**Função de transferência**

$$\frac{V_c}{E_1} = \frac{K_p s + K_i}{R_1C\,s^2 + (1+K_p)\,s + K_i}, \qquad \omega_n = \sqrt{\frac{K_i}{R_1C}} = 3162\ \text{rad/s (fixo)}, \qquad \zeta = \frac{1+K_p}{2\sqrt{K_i R_1 C}}$$

Há também um zero em s = −K_i/K_p. Por causa desse zero, as métricas teóricas da Tabela 4 vêm da **resposta ao degrau exata da FT**, e não das fórmulas do 2ª ordem padrão.

**Tabela 4** (C = 1 µF, R₁ = 1 kΩ, C_f = 10 nF)

| | T_r exp | T_r teo | T_p exp | T_p teo | M_p exp | M_p teo | T_s exp | T_s teo | V_c exp | V_c teo |
|---|---|---|---|---|---|---|---|---|---|---|
| R₂ = 5 kΩ | 1,18 ms | 0,54 ms | 2,21 ms | 0,97 ms | 69,4 % | 47,0 % | > 10 ms | 5,2 ms | 0,466 V* | 0,500 V |
| R₂ = 10 kΩ | 1,14 ms | 0,52 ms | 2,11 ms | 0,94 ms | 60,2 % | 37,1 % | > 10 ms | 3,4 ms | 0,485 V* | 0,500 V |
| R₂ = 20 kΩ | 1,08 ms | 0,50 ms | 2,04 ms | 0,89 ms | 46,5 % | 23,6 % | 8,9 ms | 2,4 ms | 0,500 V | 0,500 V |

\* A oscilação ainda não tinha se extinguido no fim do semiperíodo (10 ms), então o "valor final" medido é aproximado.

**Tabela 5**

| | ζ exp | ζ teo | ω_n exp | ω_n teo | ω_d exp | ω_d teo |
|---|---|---|---|---|---|---|
| R₂ = 5 kΩ | 0,116 | 0,237 | 1428 | 3162 | 1418 | 3072 |
| R₂ = 10 kΩ | 0,159 | 0,316 | 1512 | 3162 | 1492 | 3000 |
| R₂ = 20 kΩ | 0,237 | 0,474 | 1583 | 3162 | 1538 | 2784 |

**Erro estacionário, K_p e K_i.** A malha agora é do tipo 1, então **e_ss = 0**. Os valores experimentais de K_p e K_i vêm do ajuste do modelo às formas de onda, com C_ef = 4,17 µF.

| R₂ | e_ss exp | K_p teo → exp | K_i teo → exp |
|---|---|---|---|
| 5 kΩ | 6,1 %* | 0,50 → 0,78 | 10 000 → 8 590 s⁻¹ |
| 10 kΩ | 2,2 %* | 1,00 → 1,24 | 10 000 → 8 560 s⁻¹ |
| 20 kΩ | −0,8 % ≈ 0 | 2,00 → 2,18 | 10 000 → 8 500 s⁻¹ |

![Parte 5 – respostas](figs/resposta_parte5.png)
![Parte 5 – lugar das raízes](figs/lgr_parte5.png)

**Análise**
- **A ação integral eliminou o erro estacionário.** No caso que chegou a acomodar (20k), V_c = 0,500 V. O custo é que o sistema passou de 1ª para 2ª ordem e agora oscila.
- Como ω_n é fixo, **aumentar K_p só aumenta ζ**, e o sobressinal cai: 69 % → 60 % → 47 % medido, contra 47 % → 37 % → 24 % teórico. A tendência é a mesma.
- A oscilação medida é mais lenta e maior pela mesma causa, o C_ef: ω_n ∝ 1/√C e ζ ∝ 1/√C, então os dois caem pela metade.
- O K_i identificado fica ≈ 15 % abaixo do nominal. Isso corresponde a C_f ≈ 11,6 nF, dentro da tolerância.
- **Lugar das raízes:** com K_i fixo, os polos percorrem uma **circunferência de raio ω_n** em direção ao eixo real conforme K_p cresce, e ficam reais a partir de ζ = 1. O sistema é estável para qualquer K_p ≥ 0. O zero em −K_i/K_p se aproxima da origem com K_p baixo, o que aumenta ainda mais o sobressinal.

---

## Parte 6: RLC com controlador PI

**Função de transferência** (3ª ordem)

$$\frac{V_c}{E_1} = \frac{K_p s + K_i}{LC\,s^3 + R_1C\,s^2 + (1+K_p)\,s + K_i}$$

**Routh.** A malha é estável se R₁C(1+K_p) > LC·K_i, ou seja, 10⁻³(1+K_p) > 7,7·10⁻⁴. Isso vale para qualquer K_p ≥ 0. As métricas teóricas vêm da resposta ao degrau exata, e ζ, ω_n e ω_d são os do **par dominante**.

| R₂ | K_p | Polos teóricos |
|---|---|---|
| 5 kΩ | 0,5 | −12262; −362 ± j3234 |
| 10 kΩ | 1,0 | −11716; −635 ± j3268 |
| 40 kΩ | 4,0 | −5437; −3775 ± j3104 |

**Tabela 6** (C = 1 µF, L = 77 mH, R₁ = 1 kΩ, C_f = 10 nF)

| | T_r exp | T_r teo | T_p exp | T_p teo | M_p exp | M_p teo | T_s exp | T_s teo | V_c exp | V_c teo |
|---|---|---|---|---|---|---|---|---|---|---|
| R₂ = 5 kΩ (20 Hz) | 1,19 ms | 0,55 ms | 2,12 ms | 1,00 ms | 68,4 % | 68,8 % | > 25 ms | 10,8 ms | 0,529 V* | 0,500 V |
| R₂ = 10 kΩ (20 Hz) | 1,12 ms | 0,52 ms | 2,07 ms | 0,95 ms | 65,4 % | 55,1 % | 21,2 ms | 6,0 ms | 0,497 V | 0,500 V |
| R₂ = 40 kΩ (50 Hz) | 0,97 ms | 0,39 ms | 1,86 ms | 0,64 ms | 36,4 % | 18,7 % | 7,3 ms | 1,3 ms | 0,495 V | 0,500 V |

\* Ainda oscilando no fim do semiperíodo.

**Tabela 7**

| | ζ exp | ζ teo | ω_n exp | ω_n teo | ω_d exp | ω_d teo |
|---|---|---|---|---|---|---|
| R₂ = 5 kΩ | 0,120 | 0,111 | 1490 | 3254 | 1480 | 3234 |
| R₂ = 10 kΩ | 0,134 | 0,191 | 1531 | 3329 | 1518 | 3268 |
| R₂ = 40 kΩ | 0,306 | 0,772 | 1774 | 4887 | 1689 | 3104 |

**Erro estacionário, K_p e K_i** (valores experimentais por ajuste, com C_ef e R_bobina)

| R₂ | e_ss exp | K_p teo → exp | K_i teo → exp |
|---|---|---|---|
| 5 kΩ | ≈ 0 (−6,6 %*) | 0,50 → 0,85 | 10 000 → 8 630 s⁻¹ |
| 10 kΩ | −0,1 % ≈ 0 | 1,00 → 1,40 | 10 000 → 9 030 s⁻¹ |
| 40 kΩ | 0,3 % ≈ 0 | 4,00 → 4,33 | 10 000 → 8 840 s⁻¹ |

![Parte 6 – respostas](figs/resposta_parte6.png)
![Parte 6 – lugar das raízes](figs/lgr_parte6.png)

**Análise**
- O erro estacionário foi eliminado de novo (tipo 1).
- Com K_p baixo (5k e 10k), o par dominante fica colado no eixo imaginário. O resultado é sobressinal de 65–68 % e oscilação ainda visível após 20 ms. Por isso foi preciso baixar a frequência para 20 Hz.
- Com K_p = 4 (40k), o par se afasta do eixo e a resposta fica bem mais amortecida: M_p cai para 36 % e T_s para 7 ms.
- A ω_n medida (≈ 1500 rad/s) é ≈ metade da teórica, pela mesma causa das partes anteriores (C_ef).
- **Lugar das raízes:** com K_p pequeno, o polo real é rápido (≈ −12000 s⁻¹) e desprezível, e o par complexo domina. Com o aumento de K_p, o par se afasta do eixo imaginário e o polo real se aproxima da origem. Em K_p = 4, os três polos já têm influência comparável e o modelo de 2ª ordem dominante deixa de ser bom. O sistema é estável para qualquer K_p ≥ 0.

---

## Conclusões

1. **Controlador P** (Partes 3 e 4): o erro estacionário cai com K_p [e_ss = 1/(1+K_p)], mas nunca zera. Na planta de 1ª ordem, K_p só acelera a resposta. Na de 2ª ordem, K_p aumenta o sobressinal sem melhorar T_s.
2. **Controlador PI** (Partes 5 e 6): a ação integral zera o erro estacionário, mas aumenta a ordem do sistema e introduz oscilação. Nesse caso, aumentar K_p **melhora o amortecimento**.
3. **Os valores de regime concordaram muito bem com a teoria**, validando o modelo de realimentação unitária.
4. A dinâmica ficou sistematicamente mais lenta que a nominal. Isso é explicado de forma consistente, nas quatro partes, por um **capacitor efetivo ≈ 4,2 µF** (provavelmente 4,7 µF), mais ≈ 23 Ω de resistência da bobina e C_f ≈ 11,6 nF. Com esses valores, o modelo reproduz as formas de onda medidas e os ganhos identificados ficam próximos de R₂/R e 1/(RC_f).
