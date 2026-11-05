# Experimento 10: Compensador Avanço de Fase

> **O que é este documento.** Preparação do Experimento 10 (TE333, prof. Gideon Villar Leandro) sobre o `labscope`: o que a folha pede, as funções de transferência, o que o modelo **prevê** para cada tabela e o que esperar na bancada. **Nenhum número aqui é medida.** São previsões do modelo com os valores nominais da folha (amp-ops ideais); `set <componente> <valor>` na sessão refaz tudo com os valores reais.

---

## 1. O que a folha pede

| Tabela | Circuito | Sinal do gerador | Colunas | Caso na sessão |
| :---: | :--- | :--- | :--- | :--- |
| 1 | inversor R3 = R4 = 10 kΩ | senoide, 500 Hz, 2 Vpp | Vpp da saída, fase | 1.1 |
| 2 | compensador + inversor R3 = 50 kΩ, R4 = 10 kΩ (Figura 1) | senoide, 2 Vpp, 20 Hz a 5 kHz | Vpp da saída, fase | 2.1 a 2.6 |
| 3 | malha com planta RC (Figura 2) | quadrada, 50 Hz, 1 Vpp | $\tau$, $T_r$, $T_s$, $V_c$ | 3.1 |
| 4 | idem 3 | senoide, 100 Hz, 1 Vpp | Vpp da saída, fase | 4.1 |
| 5 | malha com planta RLC (Figura 3) | quadrada, 50 Hz, 1 Vpp | $T_r$, $T_p$, $M_p$, $T_s$, $V_c$ | 5.1 |
| 6 | idem 5 | (da Tabela 5) | $\zeta$, $\omega_n$, $\omega_d$ | 5.1 |
| 7 | idem 5 | senoide, 100 Hz, 1 Vpp | Vpp da saída, fase | 7.1 |

Além das tabelas, a folha pede os gráficos de Bode com os pontos medidos (Tabelas 2, 4 e 7: `grafico 2`, `grafico 4`, `grafico 7`), entrada × saída medida × teórica (o painel de cada captura e `grafico 3`, `grafico 5`) e a análise do lugar das raízes (`lgr` nos casos 3.1 e 5.1).

## 2. Hipóteses e inconsistências da folha

1. **R1 e R2 trocados na Tabela 4.** As Figuras 2 e 3 e as Tabelas 3, 5 e 7 têm $R_1 = 15\text{ kΩ}$ (com $C_1 = 47\text{ nF}$, na entrada) e $R_2 = 390\text{ kΩ}$ (com $C_2 = 1\text{ nF}$, na realimentação). A Tabela 4 diz o contrário. O código usa o circuito das figuras. Com os valores trocados, o compensador seria $0{,}038 \cdot (18{,}3\text{ ms}\cdot s + 1)/(15\text{ µs}\cdot s + 1)$, outro circuito.
2. **"Ciclo de trabalho de 50 %" na senoide** não tem efeito; só vale para a onda quadrada.
3. **R5 = R6 = R = 10 kΩ.** A Figura 3 mostra R5 = 10 kΩ; a Figura 2 chama os três resistores do inversor e do somador só de R.
4. **Amp-ops ideais.** O modelo ignora saturação e slew rate. A §5 mostra onde isso pesa.

## 3. Funções de transferência

### 3.1 O compensador

O amp-op tem $Z_{in} = R_1 \parallel C_1$ e $Z_f = R_2 \parallel C_2$:

$$\frac{V_o}{V_i} = -\frac{Z_f}{Z_{in}} = -\frac{R_2}{R_1}\cdot\frac{R_1 C_1 s + 1}{R_2 C_2 s + 1} = -G_c(s)$$

com zero em $-1/(R_1C_1)$ e polo em $-1/(R_2C_2)$. É **avanço** quando o zero está mais perto da origem que o polo ($R_1C_1 > R_2C_2$). A fase máxima é $\phi_{max} = \arcsin\frac{1-a}{1+a}$, $a = \frac{R_2C_2}{R_1C_1}$, na média geométrica $\omega_{max} = \sqrt{\lvert z \rvert \lvert p \rvert}$. Em alta frequência o ganho tende a $C_1/C_2$.

| Circuito | $K = R_2/R_1$ | zero (rad/s) | polo (rad/s) | $\phi_{max}$ | em | ganho em AF ($C_1/C_2$) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| Tabela 2 | 0,833 | −83,3 | −1000 | 57,8° | 46 Hz | 10 |
| Figuras 2 e 3 | 26 | −1418 | −2564 | 16,7° | 304 Hz | 47 |

### 3.2 Tabelas 1 e 2 (malha aberta)

O inversor R3/R4 dá $-R_4/R_3$, então a Tabela 1 é $-1$ (2 Vpp, 180°) e a Tabela 2 é

$$\frac{V_{saída}}{V_{G1}} = \frac{R_4}{R_3}\, G_c(s) = 0{,}2 \cdot 0{,}833 \cdot \frac{12\text{ ms}\cdot s + 1}{1\text{ ms}\cdot s + 1}$$

positiva: os dois inversores se cancelam, e a fase medida é a do próprio compensador.

### 3.3 Figuras 2 e 3 (malha fechada)

O somador recebe $V_{G1}$ e $V_c$ (sem inversor na realimentação, ao contrário dos Exps. 6 e 7) e o inversor R5/R6 fica entre o compensador e a planta. Andando pela malha: $V_1 = -(V_{G1} + V_c)$, o compensador dá $G_c (V_{G1} + V_c)$, o inversor $-G_c (V_{G1} + V_c)$ e a planta $V_c = -G\,G_c\,(V_{G1} + V_c)$:

$$\frac{V_c}{V_{G1}} = -\frac{G_c G}{1 + G_c G}$$

É realimentação negativa com a **saída invertida**: em regime, $V_c \approx -0{,}96\,V_{G1}$, e a fase em baixa frequência fica perto de 180°. O erro estacionário ao degrau é $1/(1 + K) = 1/27 = 3{,}7\%$ (tipo 0).

Plantas: $G_{RC} = \frac{1}{R_cC_c s + 1}$ ($R_cC_c = 1\text{ ms}$) e $G_{RLC} = \frac{1}{L_1C_c s^2 + R_cC_c s + 1}$ ($\omega_n = 3604\text{ rad/s}$, $\zeta = 1{,}80$: a planta RLC sozinha é sobreamortecida). O modelo "c/ carga" acrescenta o R = 10 kΩ do somador em paralelo com $C_c$ (ele termina num terra virtual).

## 4. Previsões

### 4.1 Senoides (Tabelas 1, 2, 4 e 7)

| Caso | Frequência | Vpp da saída | Fase | Saída do compensador (pico) |
| :--- | :---: | :---: | :---: | :---: |
| 1.1 | 500 Hz | 2,000 V | 180,0° | – |
| 2.1 | 20 Hz | 0,598 V | 49,3° | 1,5 V |
| 2.2 | 100 Hz | 2,147 V | 50,3° | 5,4 V |
| 2.3 | 300 Hz | 3,537 V | 25,4° | 8,8 V |
| 2.4 | 1 kHz | 3,951 V | 8,3° | 9,9 V |
| 2.5 | 3 kHz | 3,994 V | 2,8° | 10,0 V |
| 2.6 | 5 kHz | 3,998 V | 1,7° | 10,0 V |
| 4.1 (RC) | 100 Hz | 0,962 V | 179,1° | 0,57 V |
| 7.1 (RLC) | 100 Hz | 0,963 V | 179,1° | 0,56 V |

O modelo com carga muda a terceira casa (0,958 V e 179,2° no caso 4.1). Em 100 Hz as duas malhas se comportam quase igual: o laço tem ganho ≈ 26 e quase nenhuma fase lá, então a fase fica a 1° de 180°.

### 4.2 Degrau (Tabelas 3, 5 e 6)

| Caso | Polos de malha fechada | $\tau$ | $T_r$ | $T_p$ | $M_p$ | $T_s$ (2 %) | $V_c$ (pico) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| 3.1 RC | −49 156 e −1408 | 20,6 µs | 46 µs (10–90 %) | – | 0 | 87 µs | 0,481 V |
| 5.1 RLC | −7070 ± j24 223 e −1412 | – | 77 µs | 130 µs | 39,4 % | 0,55 ms | 0,481 V |

Tabela 6 (caso 5.1): $\zeta = 0{,}280$, $\omega_n = 25\,233\text{ rad/s}$, $\omega_d = 24\,223\text{ rad/s}$ (c/ carga: 0,282, 25 261 e 24 237).

**Por que a malha RC não tem resposta subamortecida (pergunta da folha).** O laço $G_cG$ tem dois polos (−1000 da planta e −2564 do compensador) e um zero (−1418) **entre eles**. No eixo real, o lugar das raízes ocupa o trecho entre −1000 e −1418 e tudo à esquerda de −2564: um ramo vai do polo da planta ao zero e o outro do polo do compensador a −∞. Nenhum ramo sai do eixo real, então os polos de malha fechada são reais **para qualquer ganho**. Com $K = 26$ o polo lento (−1408) fica quase em cima do zero (−1418) e quase não aparece na resposta, que é a de 1ª ordem do polo rápido: $\tau \approx 1/49\,156 = 20\text{ µs}$. É por isso que a Tabela 3 tem $\tau$ e $T_r$ sem $T_p$ e $M_p$. O zero mais próximo da origem que o polo é justamente o que define o avanço de fase: o compensador puxa o lugar das raízes para a esquerda, mas não cria polos complexos sobre uma planta de 1ª ordem.

Na RLC, a planta acrescenta um polo e o lugar ganha um par complexo: $\zeta$ cai de 1,80 (planta) para 0,28.

## 5. O que esperar na bancada

1. **Saturação no degrau.** Na borda da onda quadrada, o erro salta 1 V e o compensador responde com o ganho de alta frequência $C_1/C_2 = 47$: o modelo pede **≈ 48 V** ao amp-op que alimenta a planta RLC (a sessão avisa, em `teoria`). Na RC o pico é da mesma ordem, só que dura menos de 100 µs. O amp-op satura na alimentação (±12 a ±15 V) e é limitado pelo slew rate (≈ 0,5 V/µs num 741). O resultado: **$\tau$, $T_r$, $T_p$ e $T_s$ medidos maiores e $M_p$ menor que os teóricos**, como no caso 5.1 do Exp. 7. A oscilação depois da saturação ainda tende a seguir $\omega_d$ (compare `ωd decr.` no painel). $V_c$ em regime não depende disso e deve bater (0,48 V de pico).
2. **Escala de tempo.** Pelo modelo, tudo acontece em menos de 1 ms, enquanto o meio período de 50 Hz é 10 ms. Use `preparar` (a sessão sugere 25 µs/div na RC e 250 µs/div na RLC); com a saturação, pode ser preciso aumentar s/div.
3. **Tabela 2 em alta frequência.** De 1 kHz em diante o primeiro amp-op entrega ≈ 10 V de pico (20 Vpp): perto da saturação com ±12 V. Se a senoide de CH2 achatar, o painel avisa ("resíduo alto") e o Vpp medido fica menor que o teórico. O slew rate pedido em 5 kHz é $10 \cdot 2\pi \cdot 5000 \approx 0{,}31\text{ V/µs}$, abaixo do limite de um 741, mas sem muita folga.
4. **Senoides em malha fechada (4 e 7)** têm sinais pequenos em todo lugar (0,57 V no compensador) e devem bater com o modelo dentro de poucos por cento. A fase medida perto de 180° pode aparecer como −179°; a sessão compara pelo menor arco.
5. **Fase.** Positiva quer dizer CH2 adiantada em relação a CH1. Nas Tabelas 1, 4 e 7, CH2 sai invertida.

## 6. Como medir

```bash
python -m labscope --exp 10
```

```
lab[e10 c1.1]> conectar             (ou 'conectar sim' para ensaiar)
lab[e10 c1.1]> caso 2.1             mostra G(jω), Vpp e fase previstos e a tela sugerida
lab[e10 c2.1]> preparar             base de tempo para 2,5 períodos na tela
lab[e10 c2.1]> a                    Vpp de CH1 e CH2, |G| e fase
lab[e10 c2.1]> caso 2.2 ... a       (até 2.6, depois 1.1, 4.1 e 7.1)
lab[e10 c7.1]> caso 3.1; preparar; a     degrau: τ, Tr, Ts, Vc
lab[e10 c3.1]> caso 5.1; preparar; a     degrau: Tr, Tp, Mp, Ts, Vc, ζ, ωn, ωd
lab[e10 c5.1]> grafico 2            Bode do compensador com os pontos medidos
lab[e10 c5.1]> lgr                  lugar das raízes variando R2
lab[e10 c5.1]> tabela               as sete tabelas (previsto onde ainda não há captura)
```

A medida senoidal ajusta $A\sin(2\pi f t + \phi) + c$ aos dois canais, na frequência medida em CH1 (subidas pela média, com interpolação), e dá Vpp, $\lvert G \rvert$ e a fase de CH2 em relação a CH1. Tolerâncias: 10 % no Vpp e em $\lvert G \rvert$, 10° na fase. No degrau, as contas são as dos Exps. 6 e 7 sobre −CH2. `conectar sim` gera a previsão do modelo com ruído e 8 bits: serve para ensaiar a sessão, não é medida.
