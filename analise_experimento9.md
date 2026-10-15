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
3. **Unidade de $i_g$ (µA ou mA).** O PDF de 2022 dá $i_g$ em µA, o que é suspeito. **Não afeta as previsões:** $K_1$ sai da reta $V_{1t} 	imes i_g$, então se $i_g$ fosse mA, $K_1$ seria 1000 vezes menor e $i_g$ 1000 vezes maior, e o produto $K_1 i_g$ (a queda de rpm) é o mesmo (conferido: tabelas de previsão idênticas). O que muda é só o que a sessão imprime (`K1 = 9,1e6 rpm/A` e `ig = Vg × 9,2 µA/V` viram `9,1e3` e `9,2 mA/V`) e a carga implícita, $R_{carga} pprox V_g/i_g$: **≈ 110 kΩ** (µA) ou **≈ 110 Ω** (mA); o resistor ligado ao gerador diz qual dos dois é. **Cuidado só com misturar:** $K_1$ e `igv` têm de vir da mesma tabela e da mesma unidade (use `modelo <sua sessão do Exp. 8>`, que garante isso). Se digitar na mão, `set igv 9m` exige `K1=9,1e3` no `modelo`.
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

**O que são os componentes.** Todos são peças comuns, nenhuma precisa ser trimpot:

- $R$: resistor fixo na **entrada** do amp-op inversor (do detector de erro para a entrada −). No PD e no PID ele tem o capacitor $C_1$ **em paralelo**.
- $R_2$: resistor na **realimentação** (da saída para a entrada −). No PI e no PID ele fica **em série com $C_2$**; no PD está sozinho.
- $C_2$: capacitor da ação integral, em série com $R_2$ (não existe no PD). $C_1$: capacitor da ação derivativa, em paralelo com $R$ (não existe no PI).

**O que usar na bancada.** Use os valores comerciais, não os calculados. No PI, **use a linha "PI, alternativa"**: $C_2 = 10\ \mu\text{F}$, $R = 47\text{ k}\Omega$, $R_2 = 51\text{ k}\Omega$. A primeira linha (470 nF, 910 kΩ, 1,1 MΩ) só aparece porque o código escolhe o menor capacitor com $R \le 1\text{ M}\Omega$; valores de MΩ com amp-op comum sofrem com corrente de polarização, e 1 MΩ no lugar de 1,1 MΩ em $R_2$ derrubaria $K_p$ em 10 %. O capacitor de 10 µF tem de ser **bipolar** (ou dois eletrolíticos em oposição), porque a tensão sobre ele inverte. Para o ajuste fino, um trimpot de 5 kΩ em série com $R$ ou $R_2$ já basta; não precisa de trimpot de MΩ. Com `circuito c2 10u` o código dá os valores para outro capacitor.

| Controlador | $K_{p,circ}$, $K_{i,circ}$, $K_{d,circ}$ | Calculado | Comercial | Ganhos reais |
| :--- | :--- | :--- | :--- | :--- |
| PI | 1,112; 2,251; – | $C_2 = 470\text{ nF}$, $R = 945\text{ k}\Omega$, $R_2 = 1{,}05\text{ M}\Omega$ | $910\text{ k}\Omega$, $1{,}1\text{ M}\Omega$, $470\text{ nF}$ | $K_p = 1{,}21$, $K_i = 2{,}33$ |
| PI, alternativa | | $C_2 = 10\ \mu\text{F}$: $R = 44{,}4\text{ k}\Omega$, $R_2 = 49{,}4\text{ k}\Omega$ | $47\text{ k}\Omega$, $51\text{ k}\Omega$ | $K_p = 1{,}085$, $K_i = 2{,}13$ |
| PD | 0,5708; –; 0,004789 s | $R = 10\text{ k}\Omega$, $R_2 = 5{,}71\text{ k}\Omega$, $C_1 = 839\text{ nF}$ | $5{,}6\text{ k}\Omega$, $1\ \mu\text{F}$ | $K_p = 0{,}56$, $K_d = 0{,}0056$ |
| PID | 0,3151; 0,04479; 0,006155 s | $C_2 = 33\ \mu\text{F}$, $R = 676{,}5\text{ k}\Omega$, $R_2 = 212{,}6\text{ k}\Omega$, $C_1 = 29\text{ nF}$ | $680\text{ k}\Omega$, $220\text{ k}\Omega$, $33\text{ nF}$ | $K_p = 0{,}325$, $K_i = 0{,}0446$, $K_d = 0{,}00726$ |

O PID do projeto precisa de $K_i$ muito pequeno: $R = 1/(K_i C_2)$ só cabe em 1 MΩ com um $C_2$ de dezenas de µF. `circuito c2 10u` troca o capacitor. Os componentes comerciais deslocam $K_d$ em 17–18 %; use trimpots multivoltas.

## 6. Como usar

A sessão é um prompt (`lab[e9 c1.1]>`): você digita um comando por linha, e o que está entre `[ ]` no prompt é a linha da folha em que está (`c3.2` = Tabela 3, linha 2). Tudo o que ela grava vai para `sessoes\sessao_<data>_<hora>\`.

### 6.1 Ensaiar sem bancada

```text
python -m labscope --exp 9 --sim
```

`--sim` liga um osciloscópio de mentira: a "captura" é a previsão do modelo com ruído. Serve para aprender os comandos; **não é medida**. Dentro dela:

```text
lab[e9 c1.1]> modelo ref2022
lab[e9 c1.1]> caso 1.1
lab[e9 c1.1]> a
lab[e9 c1.1]> n
```

Repita `a` e `n` até a linha 4.2, e então `tabela`.

### 6.2 Passo 1: o modelo do motor (uma vez por sessão)

O Exp. 9 precisa de $K$, $K_t$, $\tau$, $K_1$ e da relação $i_g/V_g$. Três jeitos, do melhor para o pior:

| Comando | Quando |
| :--- | :--- |
| `modelo sessoes\sessao_2026-..._...` | **você mediu o Exp. 8 com a CLI**: aponte para a pasta da sessão dele. Pega as constantes das suas medidas |
| `modelo K=211,2 Kt=5,01m tau=0,494 K1=9,1e6 igv=9u` | você tem as constantes (do relatório do Exp. 8, p.ex.) mas não a sessão. `igv` é a corrente do gerador em A por volt de $V_g$ |
| `modelo ref2022` | **só para ensaio**: usa as 20 leituras do relatório de 2022, que são de outro grupo e não podem ser apresentadas como suas |

Depois do `modelo`, a sessão imprime o motor usado e a relação `ig = Vg × … µA/V`. Confira esses dois números antes de continuar (veja o §2, item 3: a unidade de ig não muda as previsões, desde que K1 e igv estejam na mesma unidade).

### 6.3 Passo 2: projetar e montar (por linha)

```text
lab[e9 c1.1]> caso 3.1        # escolhe a linha (n vai para a seguinte)
lab[e9 c3.1]> projeto         # ganhos, especificações, polos de malha aberta e fechada, previsão
lab[e9 c3.1]> circuito        # R, R2, C1, C2 (calculados e comerciais) e os ganhos que eles dão
```

- `projeto todos` faz isso para as seis linhas de uma vez.
- Se aparecer `!  o amp-op satura`, o $T_p$ pedido é rápido demais para ±10 V: `set tp 2` (segundos) ou `set tp auto` volta ao menor $T_p$ viável.
- `set tipo pd` mostra o PD nas linhas com carga (e o erro que ele deixa); `set tipo pid` força o PID também sem carga; `set tipo auto` é o padrão.
- `set vgrau 0.2` troca o ganho do sensor de posição (V/°) se o seu for outro; isso muda a tela e os componentes, não o projeto.

Monte o circuito com os valores **comerciais** do `circuito` e confira: CH1 (referência) e CH2 (sensor) no osciloscópio, terras juntos.

### 6.4 Passo 3: medir

```text
lab[e9 c3.1]> conectar          # osciloscópio real pela USB (ou: conectar <pasta ALLnnnn do pendrive>)
lab[e9 c3.1]> teoria            # o que montar, a previsão e a tela sugerida (s/div, V/div)
lab[e9 c3.1]> preparar          # trigger em CH1 subindo no meio do degrau, aquisição única
   (ajuste a referência da fonte para 5,01 V no PI, 6 V no PD/PID e aplique o degrau)
lab[e9 c3.1]> a                 # lê CH1 e CH2, mede, compara com a previsão e abre o painel
lab[e9 c3.1]> n                 # próxima linha
```

A tabela que `a` imprime tem, por linha, $\tau$, $T_r$, $T_p$, $M_p$, $T_s$ e o erro final, com a coluna **osciloscópio** (o que você mediu), **previsto** (o modelo), o desvio e `OK` ou `CONFERIR`. Um `CONFERIR` não é erro: é o motor real diferindo do modelo (zona morta, atrito, saturação). Os avisos com `!` dizem o que ajustar: degrau de CH1 diferente do esperado, janela curta para $T_s$ (precisa de 5 τ ou mais), CH2 ocupando poucos níveis do conversor, ou o amp-op que deveria saturar. Para repetir a medida da mesma linha, `a` de novo (a última vale); `descartar` tira a última captura das tabelas.

### 6.5 Passo 4: fechar

```text
lab[e9 c4.2]> tabela            # as 4 tabelas (linhas sem captura mostram "(previsto)"); salva tabelas_exp9.md
lab[e9 c4.2]> grafico 3         # as respostas medidas da Tabela 3, medido contra previsto
lab[e9 c4.2]> lgr               # lugar das raízes da linha atual (polos de malha aberta e fechada)
lab[e9 c4.2]> quit
```

O relatório em LaTeX sai fora do prompt:

```text
python -m labscope.sessao.latex sessoes\sessao_<data>_<hora> <destino>\09 --prefixo <pasta da atividade>\09
```

Para continuar uma sessão depois: `python -m labscope --exp 9`, `retomar` (a mais recente) ou `retomar <pasta>`; ele recarrega o modelo, as opções (`set ...`) e as capturas. `help` lista todos os comandos.

## 7. Limites desta preparação

- Previsões, não medidas. Nada aqui substitui as tabelas medidas na bancada; ao entregar, as linhas "previsto" devem estar marcadas como tal.
- O modelo é linear de 1ª ordem; zona morta e atrito estático (que o Exp. 8 mostrou com Va baixa), saturação do amp-op e ondulação do comutador deixam a resposta real mais lenta que a prevista.
- $T_s$ longo no PID de posição (25–29 s) é consequência da regra $K_i = K_p \omega_n/10$ do código; é uma escolha de projeto que pode ser trocada por um $K_i$ maior, com mais sobressinal.
