# Análise e Execução do Experimento 8: Controle de Motor CC

> **Contexto:** Relatório técnico analítico referente ao Experimento 8 (Laboratório de Engenharia Elétrica IV / TE059 / TE333 – UFPR), integrando os dados experimentais medidos no ano anterior (relatório de 2022 em PDF), a verificação de conformidade com o roteiro atual (DOCX), a injeção canônica dos dados no framework de automação `labscope`, a análise crítica de todas as formulações matemáticas e o dimensionamento eletrônico dos componentes para implementação física dos controladores.

> **Revisão de 2026-10-15.** As contas de regressão (somas, $K K_t$, $K$, $K_t$, $\bar\tau$, $K_1 K_t$) e a álgebra do PI foram refeitas e conferem com o `labscope`. O que foi corrigido ou ressalvado abaixo:
> 1. **O PD com $T_p = \tau$ (490 ms) pede 314 V ao amp-op** e o PID da mesma especificação, 429 V. O texto chamava os dois de "OK" e dimensionava o circuito do PID sobre esse projeto. Agora há um projeto viável por seção (§5.2 e §6.2), com $T_p$ mínimo que respeita $|V_a| \le 10\text{ V}$.
> 2. **Os ganhos de posição estão em V/°**, e o circuito trabalha em V/V: falta dividir pelo ganho do sensor de posição (§6.2). Ki e Kd estavam com unidades de velocidade ($\text{s}^{-1}$, s).
> 3. **A unidade de $i_g$ do PDF (µA) é suspeita** (10 a 87 µA para quedas de até 3,5 V no tacômetro). Se o original era mA, $K_1$ cai por 1000 **e $i_g$ sobe por 1000, então o produto $K_1 i_g$ (a queda de rpm) e todas as simulações ficam iguais**; mudam só os números exibidos de $K_1$ e $i_g$ e a carga que eles sugerem (§3.1, item iv).
> 4. **Os dados são de 2022, de outro grupo.** Servem de referência para o modelo e para ensaiar o código, mas não são medidas deste ano e não podem entrar no relatório como tal.
> 5. A fórmula do polinômio de posição na Falha 4 usa o ganho com a posição em volts; no código a posição está em graus (§3.2). A conclusão (2ª ordem sempre estável) não muda.
> 6. Links de arquivo `file:///c:/...` trocados por caminhos relativos.

---

## 1. Visão Geral e Resumo Executivo

O **Experimento 8** tem como finalidade a modelagem, identificação paramétrica em malha aberta e projeto de controle em malha fechada de um grupo motor-gerador CC com tacômetro acoplado (bancada didática servo-controlada, ex.: Feedback Instruments / CE110 Servo Trainer).

O sistema dinâmico linearizado de 1ª ordem do motor CC é regido por:
$$\omega(s) = \frac{K}{\tau s + 1} V_a(s) - \frac{K_1}{\tau s + 1} I_g(s) \quad [\text{rpm}]$$
$$V_t(s) = K_t \cdot \omega(s) \quad [\text{V}]$$

Onde:
- $V_a$: tensão de armadura aplicada ao motor ($\text{V}$);
- $\omega$: velocidade angular do eixo ($\text{rpm}$);
- $V_t$: tensão gerada nos terminais do tacômetro ($\text{V}$);
- $I_g$: corrente drenada pela carga resistiva conectada ao gerador ($\text{A}$);
- $K$: ganho estático de velocidade do motor ($\text{rpm/V}$);
- $K_t$: constante de sensibilidade do tacômetro ($\text{V/rpm}$);
- $K K_t$: ganho estático composto de tensão ($\text{V/V}$);
- $\tau$: constante de tempo mecânica do conjunto ($\text{s}$);
- $K_1$: constante de queda de velocidade sob torque de frenagem da carga ($\text{rpm/A}$).

Para controle de posição angular ($\theta$), a saída é integrada a partir da velocidade e passa por uma engrenagem redutora de $30:1$ ($N = 30$):
$$\frac{\theta(s)}{V_a(s)} = \frac{6 \cdot K / N}{s (\tau s + 1)} \quad [\text{graus/V}]$$
*(lembrando que $1\text{ rpm} = 360^\circ / 60\text{ s} = 6^\circ/\text{s}$)*.

---

## 2. Extração dos Dados Medidos (PDF 2022) e Comparação com o DOCX

### 2.1 Dados Extraídos do Relatório Anterior (PDF 2022)

Os alunos autores do relatório de 2022 mediram os dados em duas etapas:

#### Tabela 1: Motor CC Sem Carga ($I_g = 0$)
Na bancada, para cada ponto de ajuste da fonte ($V_{a,\text{nom}} = 1\dots 10\text{ V}$), registraram a tensão real medida na saída da fonte ($V_{in}$), a tensão do tacômetro em regime permanente ($V_t$), a velocidade no tacômetro digital ($\omega$) e a constante de tempo de partida no osciloscópio ($\tau$).

| Ponto | $V_a$ Nominal (V) | $V_{in}$ Medido (V) | $V_t$ Medido (V) | $\omega$ Medido (rpm) | Constante de Tempo $\tau$ (ms) |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 1.1 | 1 | 1,15 | 1,07 | 218 | 560 |
| 1.2 | 2 | 2,00 | 1,95 | 398 | 500 |
| 1.3 | 3 | 3,10 | 3,09 | 617 | 520 |
| 1.4 | 4 | 4,06 | 3,95 | 812 | 480 |
| 1.5 | 5 | 5,00 | 5,19 | 1031 | 460 |
| 1.6 | 6 | 6,09 | 6,23 | 1248 | 480 |
| 1.7 | 7 | 7,01 | 7,28 | 1455 | 480 |
| 1.8 | 8 | 8,05 | 8,32 | 1666 | 500 |
| 1.9 | 9 | 9,01 | 9,37 | 1881 | 480 |
| 1.10 | 10 | 9,50 | 9,85 | 1973 | 480 |

*Média aritmética das constantes de tempo:* $\bar{\tau} = 494\text{ ms} = 0,494\text{ s}$ (desvio padrão: $28\text{ ms}$).

#### Tabela 2: Motor CC Com Carga Resistiva no Gerador
Ao aplicar carga resistiva aos terminais do gerador acoplado, drenou-se uma corrente $i_g(t)$, o que provocou desaceleração do conjunto e queda da tensão de tacômetro para $V'_t(t)$. A queda observada é $V_{1t}(t) = V_t(t) - V'_t(t)$.

| Ponto | $V_a$ Medido (V) | $V_t$ Sem Carga (V) | $i_g$ Corrente Gerador ($\mu\text{A}$) | $V'_t$ Com Carga (V) | $V_{1t} = V_t - V'_t$ (V) |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 2.1 | 0,98 | 1,01 | 10 | 0,93 | 0,08 |
| 2.2 | 2,10 | 2,13 | 19 | 1,89 | 0,24 |
| 2.3 | 2,99 | 3,10 | 28 | 2,53 | 0,57 |
| 2.4 | 4,03 | 4,14 | 38 | 3,18 | 0,96 |
| 2.5 | 5,08 | 5,19 | 47 | 3,90 | 1,29 |
| 2.6 | 6,04 | 6,23 | 55 | 4,46 | 1,77 |
| 2.7 | 7,09 | 7,36 | 65 | 5,11 | 2,25 |
| 2.8 | 8,05 | 8,40 | 74 | 5,67 | 2,73 |
| 2.9 | 9,02 | 9,45 | 82 | 6,23 | 3,22 |
| 2.10 | 9,50 | 9,93 | 87 | 6,47 | 3,46 |

*(Nota de bancada: a corrente $i_g$ foi expressa em microamperes no PDF original, somando $505\,\mu\text{A}$).*

---

### 2.2 Análise Comparativa: PDF 2022 vs DOCX 2026

Ao inspecionar o arquivo DOCX correspondente à versão deste ano, observam-se aspectos fundamentais:

1. **Estrutura das Tabelas de Medição:**
   - O documento DOCX é a **folha de entrega / roteiro de laboratório em branco** distribuída aos grupos para preenchimento em aula.
   - Os pontos nominais de ensaio são **exatamente os mesmos**: 10 pontos de tensão para a Tabela 1 ($V_{a1}=1\text{ V}$ a $V_{a10}=10\text{ V}$) e 10 pontos para a Tabela 2.
   - As colunas solicitadas são idênticas ($V_a$, $V_t$, $\omega$, $\tau$ na Tabela 1; $V_a$, $V_t$, $i_g$, $V'_t$, $V_{1t}$ na Tabela 2).

2. **Divergência nas Especificações de Projeto:**
   - **Roteiro Anterior (PDF 2022):**
     * Controlador PI: projetar para velocidade de referência de **750 rpm**, com tempo de subida $T_r$ **30% menor** que em malha aberta.
     * Controlador PD/PID: projetar para posição de **55°**, com sobressinal $M_p \le \mathbf{25\%}$ e $T_p$ à escolha do aluno.
   - **Roteiro Atual (DOCX 2026):**
     * Controlador PI: projetar para velocidade de referência de **1000 rpm**, com tempo de subida $T_r$ **15% menor** que em malha aberta.
     * Controlador PD/PID: projetar para posição de **60°**, com sobressinal $M_p \le \mathbf{20\%}$ e $T_p$ à escolha do aluno.

3. **Conformidade do Código do Projeto (`labscope`):**
   - O código em [`labscope/roteiros/experimento8.py`](labscope/roteiros/experimento8.py) e [`labscope/motor/projeto.py`](labscope/motor/projeto.py) foi construído exatamente segundo os requisitos do **DOCX de 2026** (`referencia_rpm = 1000.0`, `referencia_graus = 60.0`, `fator = 0.85` e `mp = 0.20`), suportando parametrização flexível para qualquer conjunto de metas.

---

## 3. Análise Crítica das Fórmulas e Cálculos do PDF (2022)

Uma revisão minuciosa do memorial de cálculo do relatório de 2022 revelou acertos nas regressões por MMQ, mas também **graves inconsistências conceituais e algébricas** no projeto dos controladores.

### 3.1 Método dos Mínimos Quadrados (MMQ)

A fórmula de regressão linear padrão $y = a \cdot x + b$ utilizada foi:
$$a = \frac{n \sum_{i=1}^n x_i y_i - \left(\sum_{i=1}^n x_i\right)\left(\sum_{i=1}^n y_i\right)}{n \sum_{i=1}^n x_i^2 - \left(\sum_{i=1}^n x_i\right)^2}$$

#### (i) Ganho Composto $K K_t$ ($V_t \times V_a$)
- **Dados usados no PDF:** $x_i = V_{in}$ (tensões reais medidas da fonte, somando $54,97\text{ V}$), $y_i = V_t$ (soma $56,3\text{ V}$).
- $\sum x_i y_i = 390,6447$; $\sum x_i^2 = 378,8769$.
- $a = \frac{10 \cdot 390,6447 - 54,97 \cdot 56,3}{10 \cdot 378,8769 - (54,97)^2} = \mathbf{1,058\text{ V/V}}$.
- *No código `labscope`:* obtém-se $a = 1,0581\text{ V/V}$, com $b = -0,1864\text{ V}$ e $R^2 = 0,9995$. (Se usado $V_a$ nominal $1\dots 10\text{ V}$, $a = 1,0190\text{ V/V}$).

#### (ii) Ganho do Motor $K$ ($\omega \times V_a$)
- $x_i = V_{in}$; $y_i = \omega$ (soma $11299\text{ rpm}$).
- $\sum x_i y_i = 78313,6$; $\sum x_i^2 = 378,8769$.
- $a = \frac{10 \cdot 78313,6 - 54,97 \cdot 11299}{10 \cdot 378,8769 - (54,97)^2} = \mathbf{211,2328\text{ rpm/V}}$.
- *No código `labscope`:* $a = 211,23\text{ rpm/V}$, $b = -31,25\text{ rpm}$, $R^2 = 0,9998$.

#### (iii) Sensibilidade do Tacômetro $K_t$ ($V_t \times \omega$)
- $x_i = \omega$; $y_i = V_t$.
- $\sum x_i y_i = 80761,76$; $\sum x_i^2 = 16189897$.
- $a = \frac{10 \cdot 80761,76 - 56,3 \cdot 11299}{10 \cdot 16189897 - (11299)^2} = \mathbf{0,005001\text{ V/rpm}} \approx \mathbf{0,005\text{ V/rpm}}$.
- **Conferência solicitada pelo roteiro:**
  $$K_{t,\text{indireto}} = \frac{K K_t}{K} = \frac{1,058}{211,2328} = \mathbf{0,0050087\text{ V/rpm}}$$
  A discrepância entre o $K_t$ da reta $V_t \times \omega$ e a razão $K K_t / K$ é inferior a **0,0%** (concordância perfeita dos dados experimentais).

#### (iv) Constante com Carga $K_1 K_t$ e $K_1$
- $x_i = i_g$; $y_i = V_{1t}$.
- No PDF: $\sum x_i = 505\,\mu\text{A}$; $\sum y_i = 16,57\text{ V}$; $\sum x_i y_i = 1,13\text{ m}$; $\sum x_i^2 = 3,19 \times 10^{-8}$.
- $a = \frac{10 \cdot 1,13\times 10^{-3} - 505\times 10^{-6}\cdot 16,57}{10 \cdot 3,19\times 10^{-8} - (505\times 10^{-6})^2} = \mathbf{45043,38\text{ V/A}}$.
- $K_1 = \frac{K_1 K_t}{K_t} = \frac{45043,38}{0,005} = \mathbf{9\,008\,675\text{ rpm/A}}$.
- ⚠️ **Unidade de $i_g$ a confirmar, mas sem efeito nas simulações.** Com $i_g$ em µA, $K_1 \approx 9\times 10^6$ rpm/A: 87 µA derrubam 790 rpm, o que bate com a queda de 3,46 V no tacômetro. Mas 87 µA é uma corrente muito pequena para frear um gerador de bancada; se o PDF mediu mA, $K_1 \approx 9\times 10^3$ rpm/A. Como $K_1$ sai da reta $V_{1t} \times i_g$, trocar a unidade de $i_g$ divide $K_1$ pelo mesmo fator que multiplica $i_g$: o produto $K_1 i_g$ (rpm) é o mesmo, e verifiquei que as previsões do Exp. 9 saem idênticas nos dois casos. $K$, $K_t$ e $\tau$ também não mudam. O que muda é o valor impresso de $K_1$ e de $i_g$, e a carga implícita ($V_g/i_g$: ≈ 110 kΩ ou ≈ 110 Ω).
- *Nota analítica:* Os autores do PDF arredondaram a soma exata $\sum x_i y_i = 1,12911\text{ m}$ para $1,13\text{ m}$ e $\sum x_i^2 = 3,1917\times 10^{-8}$ para $3,19\times 10^{-8}$. A regressão sem arredondamento computada pelo `labscope` resulta em $K_1 K_t = 45572,5\text{ V/A}$ e $K_1 = 9,097 \times 10^6\text{ rpm/A}$.

---

### 3.2 Avaliação Crítica dos Controladores do PDF

#### ⚠️ Falha 1: Confusão entre Constante de Tempo $\tau$ e Tempo de Subida $T_r$
Na página 5 do PDF, os autores afirmam:
> *"Os parâmetros atuais, de tempo de subida, podem ser vistos abaixo: $T_r = 494\text{ ms}$. Um tempo de subida 30% menor seria um $T_r = 0,3458\text{ s}$."*

**Correção Teórica:**
Em um sistema de 1ª ordem puro, o tempo de subida de $10\%$ a $90\%$ é dado por:
$$T_r = \tau \cdot \ln\left(\frac{1 - 0,1}{1 - 0,9}\right) = \tau \cdot \ln(9) \approx 2,197 \cdot \tau \approx 2,2 \cdot \tau$$
Com $\bar{\tau} = 494\text{ ms}$, o tempo de subida em malha aberta real era **$T_{r,\text{MA}} \approx 1087\text{ ms}$**. Os autores tomaram $\tau$ como se fosse $T_r$, gerando uma meta artificial e distorcida.

#### ⚠️ Falha 2: Erro Algébrico na Função de Transferência de Malha Fechada
Ao fechar a malha com $C(s) = K_p + \frac{K_i}{s}$ e planta $\frac{1,058}{0,494 s + 1}$, tem-se:
$$G(s) = \frac{C(s) G_p(s)}{1 + C(s) G_p(s)} = \frac{1,058(K_p s + K_i)}{0,494 s^2 + (1 + \mathbf{1,058} K_p) s + \mathbf{1,058} K_i}$$
Na página 5, os alunos escreveram no denominador:
$$0,494 s^2 + (1 + K_p) s + K_i$$
Eles **esqueceram de multiplicar $K_p$ e $K_i$ pelo ganho da planta $1,058$** ao somar o numerador ao denominador!

#### ⚠️ Falha 3: Transferência Indevida de Requisitos entre Controladores
O roteiro previa:
- PI para velocidade: apenas especificação de tempo de subida ($T_r$).
- PD/PID para posição: especificação de sobressinal ($M_p \le 25\%$).

No PDF, os autores pegaram o sobressinal $M_p = 25\%$ destinado ao controle de posição e forçaram no PI de velocidade, deduzindo um fator de amortecimento $\xi = 0,404$ para um sistema de 2ª ordem que continha um zero em $-K_i/K_p$. Como consequência, o zero de malha fechada acelerou violentamente a resposta, produzindo um pico oscilatório enorme no MATLAB (pág. 7, Figura 4) em vez de uma resposta de velocidade suave.

#### ⚠️ Falha 4: Aplicação Equivocada de Ziegler-Nichols para Sistema de Grau 2
Na página 10 do PDF, para projetar o PID de posição, os alunos alegam:
> *"Como a função obtida possui grau maior que 2, nós utilizamos do método de Zieger-Nichols..."*

A malha direta de posição com ganho proporcional $K_p$ tem função de transferência:
$$L(s) = K_p \cdot \frac{1,058}{30 s (0,494 s + 1)}$$
A equação característica de malha fechada é:
$$0,494 s^2 + s + 0,03527 K_p = 0$$
*(Aqui $1,058/30 = 0,0353$ é o ganho com a posição lida em volts. No `labscope` a posição está em graus e o ganho da planta é $6K/N = 6 \cdot 211,2/30 = 42,2\ °/\text{V}$, de modo que o termo é $42,2\,K_p$ com $K_p$ em V/°; a conclusão abaixo vale igual.)*
**Este polinômio é estritamente de 2º grau e incondicionalmente estável para qualquer $K_p > 0$** (suas raízes sempre têm parte real negativa $\text{Re}(s) = -1/(2 \cdot 0,494) = -1,012$). Ele nunca cruza o eixo imaginário! O método de Ziegler-Nichols baseado no ganho crítico $K_u$ **não se aplica teoricamente**. Ao forçar o método, chegaram a ganhos absurdos ($K = 63,3$, $K_d = 23,7$), que na bancada exigiriam dezenas ou centenas de volts do amplificador operacional, levando o circuito imediatamente à saturação.

---

## 4. Arquitetura do Código Canônico (`labscope`)

O framework canônico adota as melhores práticas de Engenharia de Controle para bancadas reais:

### 4.1 Projeto PI com Cancelamento Polo-Zero (`ProjetoPI`)
Para a malha de velocidade com realimentação do tacômetro ($H(s) = K_t$), a malha aberta é:
$$L(s) = C(s) \cdot H(s) \cdot P(s) = \left(K_p + \frac{K_i}{s}\right) K_t \frac{K}{\tau s + 1} = K_p \left(\frac{s + K_i/K_p}{s}\right) \frac{K K_t}{\tau s + 1}$$

Fazendo a escolha ótima:
$$\frac{K_i}{K_p} = \frac{1}{\tau} \quad \implies \quad K_i = \frac{K_p}{\tau}$$
O zero do controlador PI cancela exatamente o polo da planta mecânica. A função de malha fechada resultante torna-se de **1ª ordem pura**:
$$G_{mf}(s) = \frac{1}{K_t} \cdot \frac{1}{\tau_{mf} s + 1}, \qquad \tau_{mf} = \frac{\tau}{K_p K K_t}$$

Para que o tempo de subida seja reduzido por uma fração $\alpha$ ($\alpha = 0,85$ no DOCX 2026, i.e., 15% menor; ou $\alpha = 0,70$ no PDF 2022, 30% menor):
$$\tau_{mf} = \alpha \cdot \tau \quad \implies \quad \mathbf{K_p = \frac{1}{\alpha \cdot K K_t}}, \qquad \mathbf{K_i = \frac{K_p}{\tau}}$$

*Vantagens:* **Sobressinal rigorosamente nulo ($M_p = 0\%$)**, eliminação completa do erro em regime permanente e comportamento monotonicamente estável.

Trecho canônico em [`labscope/motor/projeto.py`](labscope/motor/projeto.py#L178-L195):
```python
class ProjetoPI(Projeto):
    """PI de velocidade com o tacômetro na realimentação. O zero do PI cancela o
    polo do motor (Ki/Kp = 1/τ), e a malha fechada fica de 1ª ordem com
    τ_mf = τ/(Kp·K·Kt). Para T_r ser `fator` do de malha aberta (2,2·τ),
    τ_mf = fator·τ, logo Kp = 1/(fator·K·Kt) e Ki = Kp/τ."""
    nome = "PI de velocidade"
    grandeza = "velocidade"
    unidade = "rpm"

    def __init__(self, motor, referencia=1000.0, ig=0.0, fator=0.85, vmax=VMAX):
        super().__init__(motor, referencia, ig, vmax)
        self.fator = fator
        self.sensor = motor.Kt

    def ganhos(self):
        kp = 1 / (self.fator * self.motor.KKt)
        return dict(kp=kp, ki=kp / self.motor.tau, kd=0.0)
```

---

### 4.2 Projeto PD e PID com Supervisão de Saturação (`ProjetoPD`, `ProjetoPID`)
Para controle de posição, a planta é de 2ª ordem intrínseca ($\theta/V_a$). O código inicializa $K_p$ e $K_d$ com as fórmulas do sistema de 2ª ordem clássico e refina os ganhos via otimização não-linear (`least_squares`) para compensar o efeito acelerador do zero introduzido pelo termo derivativo ($s = -K_p/K_d$).

Além disso, o código monitora o esforço de controle para garantir que o sinal não ultrapasse a faixa linear dos amplificadores operacionais ($|V_a| \le 10\text{ V}$), calculando automaticamente `tp_minimo()` quando o instante de pico desejado satura a bancada.

Trecho canônico em [`labscope/motor/projeto.py`](labscope/motor/projeto.py#L228-L283):
```python
class ProjetoPD(Projeto):
    """PD de posição: θ/Va = 6K/(N·s(τs+1)) em graus/V, realimentação unitária,
    com N a redução até o eixo onde a posição é medida (30 no CE110, 1 no motor)."""
    nome = "PD de posição"
    ...
    def analitico(self):
        zeta = Mt.zeta_de_mp(self.mp_alvo)
        wn = math.pi / self.tp / math.sqrt(1 - zeta ** 2)
        k = 6.0 * self.motor.K / self.reducao
        return self.motor.tau * wn ** 2 / k, max(0.0, (2 * zeta * wn * self.motor.tau - 1) / k), wn
```

---

## 5. Resultados da Injeção dos Dados no Framework `labscope`

Ao injetar o conjunto integral das 20 leituras experimentais extraídas do relatório de 2022 na sessão de controle (`SessaoMotor`), o motor de cálculo gerou os resultados a seguir:

### 5.1 Identificação Paramétrica do Motor

```
  Mínimos quadrados, y = a·x + b (a é a constante; ao lado, a reta forçada pela origem)
  KKt  Vt × Va   a = 1,058 V/V       b = −0,1864 V   R² = 0,9995   (pela origem: 1,031 V/V)   10 pontos
  K    ω × Va    a = 211,2 rpm/V     b = −31,25 rpm  R² = 0,9998   (pela origem: 206,7 rpm/V)   10 pontos
  Kt   Vt × ω    a = 0,00501 V/rpm   b = −0,03026 V  R² = 0,9998   (pela origem: 0,004988 V/rpm) 10 pontos
       conferência: KKt/K = 0,005009 V/rpm   (Kt do gráfico Vt × ω difere +0,0 %)
  τ    média de 10 partidas sem carga: 494 ms ± 28 ms (desvio padrão)
  K1Kt V1t × ig  a = 4,557e+04 V/A   b = −0,6444 V   R² = 0,9863   (pela origem: 3,538e+04 V/A) 10 pontos
  K1   K1Kt/Kt = 9,097e+06 rpm/A

  Modelo Final:
  ω(s) = 211,2 / (0,494 s + 1) · Va(s) − 9,097e+06 / (0,494 s + 1) · Ig(s)   [rpm]
```

---

### 5.2 Desempenho dos Controladores Projetados

#### Caso A: Especificações do Roteiro Atual (DOCX 2026 – Canônico)
- **PI de Velocidade (Referência: 1000 rpm; $T_r$ 15% menor; sem carga):**
  - Ganhos: $K_p = \mathbf{1,112\text{ V/V}}$, $K_i = \mathbf{2,251\text{ s}^{-1}}$, $K_d = 0$.
  - Desempenho obtido: $T_r = 923\text{ ms} \le 924\text{ ms}$ (**OK**); $e_{ss} = 0,00\%$ (**OK**).
  - Tensão de controle máxima: $|V_a| = 5,6\text{ V} \le 10\text{ V}$ (**OK - não satura**).
- **PI de Velocidade (Com Carga):**
  - Ganhos idênticos; erro sob carga: $e_{ss} = 0,00\%$ (**OK**); tensão máxima $|V_a| = 6,6\text{ V} \le 10\text{ V}$ (**OK**).
- **PD de Posição (Referência: 60°; $M_p \le 20\%$; sem carga) — dois projetos:**

  | Projeto | $T_p$ | $K_p$ (V/°) | $K_d$ (V·s/°) | $M_p$ | pico de $\lvert V_a \rvert$ | Viável? |
  | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
  | $T_p = \tau$ (padrão do código) | 490 ms | 0,381 | 0,04848 | 19,0 % | **313,8 V** | **não** (amp-op satura em ±10 V) |
  | $T_p$ mínimo sem saturar | **1600 ms** | 0,05708 | 0,000479 | 19,0 % | 6,3 V | **sim** |

  O primeiro "atende" $M_p$ e $T_p$ só no modelo linear: na bancada o amp-op satura, a subida fica mais lenta e o sobressinal some. **O projeto a usar é o de $T_p = 1600\text{ ms}$** (`projeto tp 1600m`, ou o padrão do Exp. 9).
- **PD de Posição com carga ($i_g = 44\ \mu\text{A}$, o valor da Tabela 2 em 1000 rpm):** sem ação integral não elimina o erro: **−55 % em regime** com o projeto viável (−8,3 % no agressivo, que não funciona). A carga entra antes do integrador da planta, então só o termo $K_i$ a zera.
- **PID de Posição (Referência: 60°; com carga) — dois projetos:**
  - Agressivo, $T_p = 490\text{ ms}$: $K_p = 0,385$, $K_i = 0,2792$, $K_d = 0,06766$; $M_p = 19,0\%$, erro 0 %, mas **pico de 429 V — inviável**.
  - Viável, $T_p = 2500\text{ ms}$ (o menor que não satura): $K_p = \mathbf{0,03151}\text{ V/°}$, $K_i = \mathbf{0,004479}\text{ V/(°}\cdot\text{s)}$, $K_d = \mathbf{0,000616}\text{ V}\cdot\text{s/°}$; $M_p = 19,0\%$, erro com carga $0,00\%$, pico de $\lvert V_a \rvert$ = 5,6 V. Custo: o polo da ação integral ($\xi$ e $\omega_n$ lentos, zero de $K_i$ uma década abaixo de $\omega_n$) deixa $T_s \approx 12\text{ s}$ sem carga; para acomodar mais rápido seria preciso aumentar $K_i$ e aceitar mais sobressinal.

#### Caso B: Simulação com Parâmetros do PDF (750 rpm, $T_r$ 30% menor)
- Ganhos pelo método polo-zero: $K_p = \frac{1}{0,70 \cdot 1,0581} = \mathbf{1,350\text{ V/V}}$, $K_i = \frac{1,350}{0,494} = \mathbf{2,733\text{ s}^{-1}}$.
- $T_r = 760\text{ ms}$, $M_p = 0\%$, $|V_a| = 5,0\text{ V} \le 10\text{ V}$ (**Excelente margem**).

---

## 6. Dimensionamento dos Componentes do Circuito Controlador

O circuito analógico implementado na bancada didática utiliza estágios com amplificadores operacionais (conforme modelado em [`labscope/circuitos/controladores.py`](labscope/circuitos/controladores.py) e nas figuras dos roteiros 6 e 7):

```
                        Z_f
                 ┌───────▭───────┐
                 │               │
  V_in ───▭──────┴───(−)         │
         Z_in         │   >──────┴──── V_out
                 ┌───(+)
                GND
```

Como o detector de erro (somador) introduz inversão de fase, o ganho de malha efetivo é $G_c(s) = \frac{Z_f(s)}{Z_{in}(s)}$.

---

### 6.1 Circuito do Controlador PI

Na topologia canônica do controlador PI:
- Entrada: resistor simples $Z_{in}(s) = R$.
- Realimentação: resistor $R_2$ em série com capacitor $C_2$:
  $$Z_f(s) = R_2 + \frac{1}{s C_2}$$
- Função de transferência do estágio:
  $$G_c(s) = \frac{R_2 + \frac{1}{s C_2}}{R} = \frac{R_2}{R} + \frac{1}{s R C_2} = K_p + \frac{K_i}{s}$$

Portanto, as equações de dimensionamento são:
$$\mathbf{R = \frac{1}{K_i \cdot C_2}}$$
$$\mathbf{R_2 = K_p \cdot R}$$

#### Dimensionamento dos Componentes para o Controlador PI (Canônico – 1000 rpm, DOCX):
Ganhos requeridos: $K_p = 1,112$, $K_i = 2,251\text{ s}^{-1}$.

- **Opção 1: Adotando capacitor de filme/eletrolítico $C_2 = 10\ \mu\text{F}$:**
  $$R = \frac{1}{2,251 \cdot 10 \times 10^{-6}} = 44424,7\ \Omega \approx \mathbf{44,42\text{ k}\Omega}$$
  $$R_2 = 1,112 \cdot 44424,7\ \Omega = 49400,3\ \Omega \approx \mathbf{49,40\text{ k}\Omega}$$
  *Valores comerciais (E24) sugeridos:*
  - **$C_2 = 10\ \mu\text{F}$**
  - **$R = 47\text{ k}\Omega$** (ou resistor de $43\text{ k}\Omega + \text{trimpot}$ de $5\text{ k}\Omega$)
  - **$R_2 = 51\text{ k}\Omega$** (ou resistor de $47\text{ k}\Omega + \text{trimpot}$ de $5\text{ k}\Omega$)

- **Opção 2: Adotando capacitor de poliéster $C_2 = 1\ \mu\text{F}$:**
  $$R = \frac{1}{2,251 \cdot 1 \times 10^{-6}} \approx \mathbf{444,25\text{ k}\Omega}$$
  $$R_2 = 1,112 \cdot 444247\ \Omega \approx \mathbf{494,00\text{ k}\Omega}$$
  *Valores comerciais:* $C_2 = 1\ \mu\text{F}$, $R = 470\text{ k}\Omega$, $R_2 = 510\text{ k}\Omega$.

---

### 6.2 Circuito do Controlador PID

Para o controlador PID analógico, a topologia canônica ([`ControladorPID`](labscope/circuitos/controladores.py#L104-L117)) utiliza:
- Entrada: resistor $R$ em paralelo com capacitor derivativo $C_1$:
  $$Z_{in}(s) = R \parallel \frac{1}{s C_1} = \frac{R}{s R C_1 + 1}$$
- Realimentação: resistor $R_2$ em série com capacitor integral $C_2$:
  $$Z_f(s) = R_2 + \frac{1}{s C_2} = \frac{s R_2 C_2 + 1}{s C_2}$$
- Função de transferência do estágio:
  $$G_c(s) = \frac{Z_f(s)}{Z_{in}(s)} = \left(R_2 + \frac{1}{s C_2}\right)\left(\frac{1}{R} + s C_1\right) = \left(\frac{R_2}{R} + \frac{C_1}{C_2}\right) + \frac{1}{s R C_2} + s R_2 C_1$$

Identificando os termos com a forma ideal $G_c(s) = K_p + \frac{K_i}{s} + K_d s$:
1. $K_p = \frac{R_2}{R} + \frac{C_1}{C_2}$
2. $K_i = \frac{1}{R C_2}$
3. $K_d = R_2 C_1$

Multiplicando $K_i \cdot K_d$:
$$K_i \cdot K_d = \left(\frac{1}{R C_2}\right)(R_2 C_1) = \left(\frac{R_2}{R}\right)\left(\frac{C_1}{C_2}\right)$$
Definindo $u = \frac{R_2}{R}$ e $v = \frac{C_1}{C_2}$, temos o sistema clássico de soma e produto:
$$u + v = K_p, \qquad u \cdot v = K_i \cdot K_d$$
Portanto, $u$ e $v$ são as raízes da equação do 2º grau:
$$x^2 - K_p x + (K_i K_d) = 0$$
O discriminante é $\Delta = K_p^2 - 4 K_i K_d$.
Com as raízes $u = \frac{K_p + \sqrt{\Delta}}{2}$ e $v = \frac{K_p - \sqrt{\Delta}}{2}$, os componentes são determinados escolhendo $C_2$:
$$\mathbf{R = \frac{1}{K_i \cdot C_2}}, \qquad \mathbf{R_2 = u \cdot R}, \qquad \mathbf{C_1 = v \cdot C_2}$$

#### Dimensionamento dos Componentes para o Controlador PID (Posição, com Carga):

**Dois cuidados que o texto original não tinha.**

1. **Os ganhos de posição estão em V/°; o circuito trabalha em V/V.** O sinal que entra no somador é $V_{ref} - V_{sensor}$, e o sensor de posição dá $k_\theta$ V/°. Então $K_{p,circ} = K_p/k_\theta$, $K_{i,circ} = K_i/k_\theta$, $K_{d,circ} = K_d/k_\theta$. O ganho $k_\theta$ do potenciômetro/sensor do CE110 **não está no roteiro**; abaixo se supõe $k_\theta = 0,1\text{ V/°}$ (6 V para 60°). Com outro valor, só $R_2$ e $C_1$ mudam proporcionalmente.
2. **Os ganhos a usar são os do projeto viável** ($T_p = 2500\text{ ms}$), não os do projeto agressivo ($T_p = 490\text{ ms}$, 429 V no amp-op) que o texto anterior dimensionava ($R = 358\text{ k}\Omega$ etc.).

Ganhos do projeto viável (unidades de posição): $K_p = 0,03151\text{ V/°}$, $K_i = 0,004479\text{ V/(°}\cdot\text{s)}$, $K_d = 0,000616\text{ V}\cdot\text{s/°}$. No circuito, com $k_\theta = 0,1\text{ V/°}$:
$$K_{p,circ} = 0,3151,\qquad K_{i,circ} = 0,04479\text{ s}^{-1},\qquad K_{d,circ} = 0,006155\text{ s}$$

1. **Discriminante:** $K_i K_d = 0,04479 \cdot 0,006155 = 2,757\times 10^{-4}$; $\Delta = 0,3151^2 - 4 \cdot 2,757\times 10^{-4} = 0,09817 > 0$ (raízes reais).
2. **Razões:** $\sqrt\Delta = 0,3133$; $u = R_2/R = (0,3151 + 0,3133)/2 = \mathbf{0,3142}$; $v = C_1/C_2 = (0,3151 - 0,3133)/2 = \mathbf{0,00088}$.
3. **Componentes.** $K_i$ é muito pequeno, então $R = 1/(K_i C_2)$ só cabe em ≤ 1 MΩ com $C_2$ grande: $C_2 = 33\ \mu\text{F}$ dá $R = 676,5\text{ k}\Omega$; $R_2 = u R = 212,6\text{ k}\Omega$; $C_1 = v C_2 = 29\text{ nF}$.

*Valores comerciais:* $C_2 = 33\ \mu\text{F}$ (bipolar, ou dois de $68\ \mu\text{F}$ de eletrolítico em oposição), $R = 680\text{ k}\Omega$, $R_2 = 220\text{ k}\Omega$, $C_1 = 33\text{ nF}$. Com eles o circuito realiza $K_p = 0,325$, $K_i = 0,0446$, $K_d = 0,00726$: **$K_d$ sai 18 % acima** por causa de $C_1$ (28,95 → 33 nF). Use $R$ e $R_2$ com trimpot multivoltas e ajuste na bancada, ou $C_1 = 27\text{ nF}\parallel 1,8\text{ nF}$.

*Observação:* $v = 0,00088$ significa que a parte derivativa é quase só $K_d$: o PID é praticamente um PI com um pequeno $C_1$ em paralelo com $R$. É consequência de $K_d/K_p = 20\text{ ms}$ ser muito menor que $\tau = 494\text{ ms}$.

#### Dimensionamento do PD de posição (sem carga), $T_p = 1600\text{ ms}$:
Sem $C_2$: $Z_{in} = R \parallel C_1$, $Z_f = R_2$, logo $K_p = R_2/R$ e $K_d = R_2 C_1$. Com $K_{p,circ} = 0,5708$ e $K_{d,circ} = 0,004789\text{ s}$ e $R = 10\text{ k}\Omega$: $R_2 = 5,71\text{ k}\Omega$ e $C_1 = K_d/R_2 = 839\text{ nF}$. Comerciais: $R = 10\text{ k}\Omega$, $R_2 = 5,6\text{ k}\Omega$, $C_1 = 1\ \mu\text{F}$ ($K_d$ 17 % acima: use $0,68\ \mu\text{F} + 0,15\ \mu\text{F}$).

---

## 7. Conclusões e Recomendações Práticas para a Bancada

1. **Os dados de 2022 servem como referência, não como medida.** Permitiram verificar o código e ter um modelo para projetar ($K = 211,2\text{ rpm/V}$, $K_t = 0,00501\text{ V/rpm}$, $\tau = 494\text{ ms}$, $R^2 > 0,986$), mas são de outro grupo e de outro ano. No relatório deste ano, ou entram com a fonte declarada ("dados do relatório de 2022") ou saem; as tabelas medidas têm de ser as da bancada. $K_1$ depende da unidade de $i_g$ (§3.1, item iv) e deve ser conferido.
2. **O cancelamento polo-zero é a abordagem correta para o PI** e supera as formulações do relatório de 2022: sobressinal nulo, erro nulo, $|V_a|_{max} = 5,6\text{ V}$ sem carga e $6,6\text{ V}$ com carga. Com $R = 47\text{ k}\Omega$ e $R_2 = 51\text{ k}\Omega$ o zero cai em 1,96 s⁻¹ contra 2,02 s⁻¹ do polo (3 % de diferença): o cancelamento fica quase perfeito.
3. **Na posição, o limite é o amp-op, não o método.** $T_p$ = $\tau$ (490 ms) é inviável (314 V para o PD, 429 V para o PID). Com o $T_p$ mínimo que respeita 10 V (1,6 s para o PD, 2,5 s para o PID) as especificações de $M_p$ se cumprem; o preço é uma resposta lenta, com $T_s \approx 12\text{ s}$ no PID. Sem carga basta o PD; com carga só o PID zera o erro.
4. **Circuito:** as tabelas da §6 dão valores para montar o PI imediatamente. O PID e o PD dependem do ganho do sensor de posição $k_\theta$ (suposto 0,1 V/°), que precisa ser medido na bancada; os valores comerciais mudam $K_d$ em 17 % a 18 %, então use trimpots multivoltas.
