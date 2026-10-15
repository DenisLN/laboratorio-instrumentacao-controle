# Experimento 9: Controle de Sistemas com Perturbações

> **O que é este documento.** Preparação do Experimento 9 (TE333, prof. Gideon Villar Leandro) sobre o `labscope`: o que a folha pede, o projeto de cada controlador sobre o motor identificado no Exp. 8, os circuitos, o que o modelo **prevê** para cada linha das tabelas e como medir na bancada. **Nenhum número de resposta aqui é medida.** São previsões do modelo; o motor vem dos dados de 2022 (outro grupo/ano; ver `analise_experimento8.md`). Quando houver medidas do Exp. 8 deste ano, `modelo <pasta da sessão>` refaz tudo.

---

## 1. O que a folha pede

Cada seção é um controlador montado e a resposta vista no osciloscópio, com as colunas $V_t(t)$, $\tau$, $T_r$, $T_p$, $M_p$ e $T_s$, o gráfico entrada × saída e a análise da posição dos polos no lugar das raízes (malha aberta e fechada).

| Tabela | Controlador | Especificação | Linhas |
| :---: | :--- | :--- | :--- |
| 1 | PI de velocidade, **sem carga** | elimina o erro, $T_r$ 15 % menor que em malha aberta, 1000 rpm | 1.1 |
| 2 | PD/PID de posição, **sem carga** | elimina o erro, $M_p \le 20\%$, $T_p$ à escolha, 60° | 2.1 |
| 3 | PI de velocidade, **com carga** | idem 1 | 3.1 ($V_g = 6\text{ V}$), 3.2 ($9\text{ V}$) |
| 4 | PD de posição, **com carga** | idem 2 | 4.1 ($V_g = 5\text{ V}$), 4.2 ($8\text{ V}$) |

Os valores de 1000 rpm, 60° e $M_p \le 20\%$ são os mesmos do Exp. 8, então o código do projeto serve sem alteração.

## 2. Hipóteses que a folha não fixa

Estas decisões foram tomadas no código como opções (`set ...`) e precisam ser confirmadas na bancada ou com o professor:

1. **O que é $V_g$.** Foi tratada como a tensão do gerador com a carga ligada, e a corrente como proporcional: $i_g = V_g \cdot i_{g,V}$, com $i_{g,V} = 9{,}17\ \mu\text{A/V}$ ajustado na Tabela 2 do Exp. 8 (`set igv`). Em 6 e 9 V isso dá 55 e 82,5 µA. Se $V_g$ for uma tensão aplicada ao gerador como segundo motor (freio), a perturbação é outra.
2. **Quando a carga entra.** Junto com o degrau de referência, com $i_g$ constante. Se na bancada a carga entrar depois de a resposta acomodar (como o `projeto` do Exp. 8 simula), os valores de $T_r$, $T_p$ e $M_p$ das Tabelas 3 e 4 ficam iguais aos das Tabelas 1 e 2, e o que muda é a queda e a recuperação depois da carga.
3. **Unidade de $i_g$.** O PDF de 2022 dá $i_g$ em µA; se for mA, $K_1$ cai por 1000 e todas as linhas com carga mudam (§3.1 de `analise_experimento8.md`).
4. **Sensor de posição.** Suposto $k_\theta = 0{,}1\text{ V/°}$ (60° = 6 V na tela). Só muda a escala da tela e os componentes de $K_p$, $K_i$, $K_d$ do circuito (`set vgrau`).
5. **PD ou PID com carga.** A folha diz "PD" na Tabela 4, mas o PD não elimina o erro de uma perturbação que entra antes do integrador da posição (§4.3). O padrão do código usa PID nessas linhas (`set tipo pd` para ver o PD).

## 3. Projeto

Modelo: $K = 211{,}2\text{ rpm/V}$, $K_t = 0{,}00501\text{ V/rpm}$, $\tau = 494\text{ ms}$, $K_1 = 9{,}1\times 10^6\text{ rpm/A}$, redução 30:1.

| Controlador | $T_p$ | Ganhos (posição em V/°) | Pico de $\lvert V_a \rvert$ | Polos de malha fechada |
| :--- | :---: | :--- | :---: | :--- |
| PI (1000 rpm) | – | $K_p = 1{,}112$, $K_i = 2{,}251\text{ s}^{-1}$ | 5,6 V (6,6–8,3 V com carga) | $-2{,}38$ e $-2{,}02$ |
| PD (60°) | 1,6 s | $K_p = 0{,}05708$, $K_d = 0{,}000479$ | 6,3 V | $-1{,}03 \pm j1{,}95$ |
| PID (60°, com carga) | 2,5 s | $K_p = 0{,}03151$, $K_i = 0{,}004479$, $K_d = 0{,}000616$ | 5,6 V | $-0{,}96 \pm j1{,}21$ e $-0{,}16$ |

**Por que $T_p$ não é pequeno.** Com $T_p = \tau$ (490 ms) o PD pede 314 V e o PID 429 V ao amp-op, que satura em ±10 V. O código escolhe o menor $T_p$ que cabe em 10 V, e **um só por tabela**: $V_g$ não altera os ganhos, então as linhas 4.1 e 4.2 usam o mesmo circuito. A escolha de $T_p$ é livre na folha; um valor menor exige mais tensão (`set tp 1.2`, `set vmax 12`).

**PI.** O zero do PI cancela o polo do motor ($K_i/K_p = 1/\tau$), a malha fechada fica de 1ª ordem com $\tau_{mf} = 0{,}85\,\tau$ e $T_r = 0{,}85 \cdot 2{,}2\,\tau = 924\text{ ms}$, sem sobressinal.

## 4. O que o modelo prevê para as tabelas

Previsão do modelo (`conectar sim` gera a mesma coisa com ruído). $T_r$ de 10 a 90 %, $T_s$ na faixa de ±2 %, $\tau$ = tempo até 63,2 % do valor final.

| Linha | $\tau$ (ms) | $T_r$ (ms) | $T_p$ (ms) | $M_p$ (%) | $T_s$ (ms) | erro final |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| 1.1 PI, sem carga | 420 | 923 | – | 0 | 1643 | 0 |
| 2.1 PD, sem carga | 677 | 713 | 1600 | 19,0 | 3742 | 0 |
| 3.1 PI, $V_g = 6$ V | 654 | 1331 | – | 0 | 2280 | 0 |
| 3.2 PI, $V_g = 9$ V | 783 | 1458 | – | 0 | 2458 | 0 |
| 4.1 PID, $V_g = 5$ V | 7349 | 13586 | – | 0 | 25497 | 0 |
| 4.2 PID, $V_g = 8$ V | 10547 | 13735 | – | 0 | 28695 | 0 |

### 4.1 Sem carga

O PI do cancelamento polo-zero dá resposta exponencial sem pico; $\tau = 420\text{ ms}$ é o da malha fechada, menor que os 494 ms do motor. O PD tem $\zeta \approx 0{,}47$ e $\omega_n \approx 2{,}2\text{ rad/s}$; o zero de $K_d$ (em $-119\text{ s}^{-1}$) fica bem longe e quase não distorce a resposta.

### 4.2 Com carga (velocidade)

O PI rejeita a carga: o erro final é nulo, mas a carga constante tira velocidade enquanto a integral acumula, e $T_r$ e $T_s$ crescem com $V_g$ (1331 e 1458 ms de $T_r$). O sinal de controle sobe com a carga (7,1 e 8,3 V), perto do limite de 10 V; acima de $V_g \approx 10\text{ V}$ o amp-op satura.

### 4.3 Com carga (posição)

A perturbação de velocidade $K_1 i_g/(\tau s + 1)$ entra **antes** do integrador de posição. Com PD, no equilíbrio a velocidade é nula e o motor precisa de $V_a = K_1 i_g/K$ constante, que só sai de um erro de posição $e = V_a/K_p$:

| Linha | $V_a$ necessário | erro com PD ($K_p = 0{,}057$ V/°) |
| :--- | :---: | :---: |
| 4.1 ($V_g = 5$ V) | 1,98 V | 58 % (≈ 35° dos 60°) |
| 4.2 ($V_g = 8$ V) | 3,17 V | 92 % (o eixo mal sai do lugar) |

Por isso a folha pede "elimina o erro" e o PD não consegue: **só o termo integral zera o erro**, e o PID do código reproduz o 0 % com tempos longos ($T_s \approx 25$–$29\text{ s}$, porque o zero de $K_i$ fica uma década abaixo de $\omega_n$). Se o relatório tiver de mostrar o PD com carga, vale mostrar esse erro como resultado, e o PID como solução.

### 4.4 Lugar das raízes

`lgr` desenha, por tabela, os polos de malha aberta (×), os zeros (○) e os de malha fechada (■) sobre o lugar da malha com ganho $k$ variando (o projeto é $k = 1$).

| Malha | Polos de malha aberta | Zeros | Polos de malha fechada |
| :--- | :--- | :--- | :--- |
| PI | $0$ e $-2{,}02$ | $-2{,}02$ (cancela) | $-2{,}38$ (dominante) e $-2{,}02$ (cancelado) |
| PD | $0$ e $-2{,}02$ | $-119$ | $-1{,}03 \pm j1{,}95$ |
| PID | $0$, $-2{,}02$ e $0$ | dois, perto da origem | $-0{,}96 \pm j1{,}21$ e $-0{,}16$ |

Com $K_p$ variando o PI desloca o polo em $0$ sobre o eixo real até $-2{,}02$; o projeto o coloca em $-2{,}38$, à esquerda do polo do motor, e é isso que encurta o $T_r$ em 15 %. No PD os polos saem de $0$ e $-2{,}02$, se encontram em $-1{,}01$ e vão para o plano complexo; o projeto fica em $\zeta = 0{,}47$. O PID acrescenta um polo real lento ($-0{,}16$) que domina o $T_s$.

## 5. Circuitos

`circuito` calcula $R$, $R_2$, $C_1$ e $C_2$ (série E24 para resistores, E6 para capacitores), com $G_c = Z_f/Z_{in}$; o detector de erro compensa a inversão do amp-op. Ganhos do circuito em V/V; na posição, divididos por $k_\theta$.

| Controlador | $K_{p,circ}$, $K_{i,circ}$, $K_{d,circ}$ | Calculado | Comercial | Ganhos reais |
| :--- | :--- | :--- | :--- | :--- |
| PI | 1,112; 2,251; – | $C_2 = 470\text{ nF}$, $R = 945\text{ k}\Omega$, $R_2 = 1{,}05\text{ M}\Omega$ | $910\text{ k}\Omega$, $1{,}1\text{ M}\Omega$, $470\text{ nF}$ | $K_p = 1{,}21$, $K_i = 2{,}33$ |
| PI, alternativa | | $C_2 = 10\ \mu\text{F}$: $R = 44{,}4\text{ k}\Omega$, $R_2 = 49{,}4\text{ k}\Omega$ | $47\text{ k}\Omega$, $51\text{ k}\Omega$ | $K_p = 1{,}085$, $K_i = 2{,}13$ |
| PD | 0,5708; –; 0,004789 s | $R = 10\text{ k}\Omega$, $R_2 = 5{,}71\text{ k}\Omega$, $C_1 = 839\text{ nF}$ | $5{,}6\text{ k}\Omega$, $1\ \mu\text{F}$ | $K_p = 0{,}56$, $K_d = 0{,}0056$ |
| PID | 0,3151; 0,04479; 0,006155 s | $C_2 = 33\ \mu\text{F}$, $R = 676{,}5\text{ k}\Omega$, $R_2 = 212{,}6\text{ k}\Omega$, $C_1 = 29\text{ nF}$ | $680\text{ k}\Omega$, $220\text{ k}\Omega$, $33\text{ nF}$ | $K_p = 0{,}325$, $K_i = 0{,}0446$, $K_d = 0{,}00726$ |

O PID do projeto precisa de $K_i$ muito pequeno: $R = 1/(K_i C_2)$ só cabe em 1 MΩ com um $C_2$ de dezenas de µF. `circuito c2 10u` troca o capacitor. Os componentes comerciais deslocam $K_d$ em 17–18 %; use trimpots multivoltas.

## 6. Como usar

```text
python -m labscope --exp 9 --sim --sem-abrir     # ensaio sem bancada (a captura é a previsão com ruído)
lab[e9 c1.1]> modelo ref2022                      # ou: modelo sessoes\sessao_..._Exp8
lab[e9 c1.1]> projeto todos                       # ganhos, polos e previsão de todas as linhas
lab[e9 c1.1]> circuito                            # componentes desta linha
lab[e9 c1.1]> preparar                            # trigger em CH1 subindo; aplique o degrau
lab[e9 c1.1]> a                                   # mede e compara com o previsto
lab[e9 c1.1]> n                                   # próxima linha
lab[e9 c4.2]> tabela / grafico 3 / lgr            # tabelas, respostas e lugar das raízes
```

Na bancada: **CH1 na referência, CH2 no sensor** (Vt no PI), terras juntos; a referência deve ser um degrau de 5,01 V (1000 rpm × $K_t$) no PI e de 6 V no PD/PID ($k_\theta = 0{,}1\text{ V/°}$). A sessão avisa se o degrau de CH1 não bate, se a janela é curta para $T_s$ (precisa de 5 τ ou mais) e se o amp-op deveria saturar. O relatório sai com `python -m labscope.sessao.latex <sessão> <destino>/09`.

## 7. Limites desta preparação

- Previsões, não medidas. Nada aqui substitui as tabelas medidas na bancada; ao entregar, as linhas "previsto" devem estar marcadas como tal.
- O modelo é linear de 1ª ordem; zona morta e atrito estático (que o Exp. 8 mostrou com Va baixa), saturação do amp-op e ondulação do comutador deixam a resposta real mais lenta que a prevista.
- $T_s$ longo no PID de posição (25–29 s) é consequência da regra $K_i = K_p \omega_n/10$ do código; é uma escolha de projeto que pode ser trocada por um $K_i$ maior, com mais sobressinal.
