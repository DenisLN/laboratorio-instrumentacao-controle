# labscope

Ferramentas para medir e analisar respostas ao degrau em experimentos de controle com osciloscópio Tektronix TBS/TDS: ao vivo pela USB, ou depois, a partir das pastas `ALLnnnn` do pendrive.

Dependências: `numpy`, `scipy`, `matplotlib` e, para a USB, `pyvisa` com uma biblioteca VISA instalada (NI-VISA, Keysight IO Libraries ou TekVISA).

## Sessão interativa de bancada

```bash
python -m labscope
```

ou dois cliques em `LAB.cmd`. Abre no Experimento 8 (motor CC, seção abaixo); `--exp 9` abre o controle do motor, `--exp 10` o compensador avanço de fase, `--exp 7` ou `--exp 6` começa nos roteiros com amp-op, e `exp <n>` troca no meio da sessão. Com `--sim` a sessão já abre ligada a um osciloscópio simulado (no Exp. 8, um motor simulado), para ensaiar sem hardware.

Ligações: **CH1 = e₁** (saída do gerador), **CH2 = V_c**, cabo USB-B na traseira do osciloscópio.

| No prompt | O que acontece |
|---|---|
| `conectar` | acha o Tektronix na USB e mostra o `*IDN?` |
| `caso 1.2` | escolhe o circuito (Tabela 1, 2ª linha) e mostra a teoria: ganhos, polos, métricas previstas e a tela sugerida |
| `preparar` | põe a base de tempo e o trigger do osciloscópio na tela sugerida (opcional; a escala vertical é manual) |
| `adquirir` ou `a` | lê CH1 e CH2, grava, mede, compara com o modelo e abre o painel |
| `set L 68m` | troca um componente pelo valor medido; `calcular` refaz a última captura |
| `ajustar` | identifica K_p, K_i e K_d na forma de onda |
| `tabela` | tabelas do roteiro preenchidas com tudo que já foi medido |
| `grafico 1` | os casos da Tabela 1 no mesmo gráfico, com as curvas teóricas |
| `lgr` | lugar das raízes do caso, com os polos teóricos e medidos |
| `set diagnostico on` | abre uma janela acompanhando a transcrição SCPI e mostra rastros de erro |
| `ver` / `painel` | a última captura como veio do osciloscópio / reabre o último painel |
| `set sonda 1` | ponta 1X com o canal do osciloscópio em 10X: corrige as tensões nas contas |
| `retomar` | continua a última sessão gravada: componentes, numeração e capturas já medidas |
| `descartar 27` | tira a captura #27 das tabelas (a pasta fica, com `_descartada` no nome) |
| `help` | todos os comandos |

Comandos podem ser abreviados quando não há ambiguidade (`con`, `adq`), e funcionam sem barra de espaço: `caso1.2`, `L=68m`, `set,sonda,1`, `tabela1`. Nesse modo o decimal é com ponto.

A tabela que aparece a cada aquisição tem três colunas de valor: **experimental**, **teórico** (o modelo do roteiro) e **c/ carga** (o mesmo modelo com o resistor R do inversor de realimentação em paralelo com o capacitor da planta, que o roteiro ignora). Uma métrica só é marcada `CONFERIR` se ficar fora da tolerância dos dois modelos. O `resíduo RMS` compara a curva inteira de CH2 com cada modelo; perto do LSB, a montagem está reproduzindo o modelo.

Tudo vai para `sessoes/sessao_<data>_<hora>/`:

```
01_e7_c1.1/captura.npz   captura.csv   metricas.json   metricas.txt   painel.png
02_e7_c1.2/...
tabelas_exp7.md   grafico_exp7_tabela1.png   lgr_exp7_c1.2_R2.png   scpi_transcricao.log
```

Avisos que a sessão dá sozinha: sinal cortado, janela curta para o T_s previsto, resposta que não acomoda em meio período, amplitude de CH1 dez vezes a do roteiro (sonda 10X/1X trocada) e amp-op do controlador que precisaria passar de 10 V para seguir o modelo linear (satura). V_c e e_ss levam o passo de quantização em conta antes de acusar `CONFERIR`.

A captura é gravada antes da análise. Se a conta falhar (canal trocado, sem borda na tela), ela fica em `NN_sem_analise/` e `calcular` a reaproveita depois de corrigir o caso ou os componentes.

### Se a USB não funcionar

- `recursos` não lista nenhum `0x0699`: o osciloscópio pode estar com a porta traseira em modo impressora (o Windows mostra "Tektronix PictBridge Device"). No osciloscópio: Utility → Options → Rear USB Port → Computer. O `conectar` detecta isso e avisa.
- Plano B, o pendrive: salve no osciloscópio como sempre ("Save All") e use a mesma sessão:

```
lab> conectar E:\NEW_FOL        (a pasta que contém as ALLnnnn)
lab> adquirir                   (lê a ALLnnnn mais nova; "adquirir 7" lê a ALL0007)
```

ou `carregar E:\NEW_FOL\ALL0007` para uma pasta avulsa.

### Como ajustar a tela

- Uma borda de subida de CH1 perto da esquerda e o transitório inteiro depois dela, com sobra de patamar (o comando `teoria` diz quantos s/div). Com várias bordas na tela a medida é a média de todos os meios períodos completos.
- CH2 ocupando boa parte da tela sem cortar o pico. Sinal cortado e janela curta geram avisos.
- A média de aquisições do osciloscópio (`preparar 1m media 16`) reduz bastante o ruído de quantização.

## Experimento 8 – motor CC

Não há circuito para montar: cada linha é uma tensão de armadura (`caso 1.4` = Tabela 1, Va = 4 V; `caso 2.4` = a mesma Va com carga no gerador). Ligações: **CH1 na armadura (Va)**, **CH2 no tacômetro (Vt)**.

| No prompt | O que acontece |
|---|---|
| `caso 1.4` / `n` | escolhe a linha (ou vai para a próxima) e diz o que medir, o valor esperado pelas linhas já medidas e a tela sugerida |
| `preparar` | trigger em CH1 subindo a Va/2 e aquisição única (Single Seq): é só ligar a fonte |
| `a` | lê a partida: Va, Vt (V't na Tabela 2) e τ (63,2 % a partir da subida de Va), compara com as outras linhas e rearma o osciloscópio |
| `w=1020` | velocidade lida no tacômetro (rpm). Também `ig=120m` (A), `vt=2.95`, `vt'=2.47`, `va=4.02`, `tau=350m`; `w=-` apaga; `anotar 1.4 w 1020` anota em outra linha |
| `ajustar` | mínimos quadrados: KKt (Vt × Va), K (ω × Va), Kt (Vt × ω, conferido com KKt/K), τ médio, K1Kt (V1t × ig) e K1 = K1Kt/Kt |
| `tabela` | as duas tabelas da folha e as constantes, em `tabelas_exp8.md` |
| `grafico 1` / `grafico 2` / `grafico partidas` | as retas da seção 3 e τ por linha / V1t × ig / uma partida por painel |
| `projeto` | PI de velocidade (1000 rpm, T_r 15 % menor que em malha aberta) e PD/PID de posição (60°, M_p ≤ 20 %, T_p = τ por padrão: `projeto tp 300m`), simulados sem carga e com a carga entrando em degrau |

O que é digitado vale mais que o que veio do osciloscópio. Na Tabela 2, Vt sem carga é o da Tabela 1 com a mesma Va, a não ser que seja anotado de novo. Pontos com o motor parado (zona morta) ficam fora das retas. A cada valor novo a sessão compara com a previsão das retas das outras linhas e marca `CONFERIR` se o ponto sair da reta.

Projeto: o PI cancela o polo do motor (Ki/Kp = 1/τ), e Kp = 1/(0,85·K·Kt) deixa a malha fechada com τ_mf = 0,85·τ. O PD parte do 2ª ordem padrão (ζ do sobressinal, ω_n de T_p) e corrige Kp e Kd numericamente, porque o zero do PD aumenta o sobressinal; o alvo é 19 %, um ponto de folga. O PID é o PD com Ki = Kp·ω_n/10, para a carga não deixar erro em regime (o erro com carga sai do teorema do valor final).

`python -m labscope.sessao.latex <sessão> <destino>/08` exporta as tabelas (1, 2, K de constantes e P de projeto), um gráfico por reta, as partidas, as simulações e os trechos de código.

## Experimento 9 – controle do motor CC com perturbações

Usa o motor identificado no Exp. 8. Cada linha é um controlador montado e a resposta ao degrau de referência: **CH1 na referência**, **CH2 no sensor** (tacômetro no PI, sensor de posição no PD/PID). Tabelas da folha: 1 PI sem carga (1000 rpm, T_r 15 % menor), 2 PD/PID sem carga (60°, M_p ≤ 20 %), 3 PI com Vg = 6 e 9 V, 4 PD/PID com Vg = 5 e 8 V; colunas τ, T_r, T_p, M_p e T_s.

| No prompt | O que acontece |
|---|---|
| `modelo ref2022` | motor do Exp. 8 de 2022 (`labscope/dados`, outro grupo/ano: só referência); `modelo <pasta da sessão do Exp. 8>` usa a sua; `modelo K=211 Kt=5m tau=0,494 K1=9e6 igv=9u` digita |
| `caso 3.1` / `n` | escolhe a linha e mostra ganhos, especificações, polos de malha aberta e fechada, a resposta prevista (τ, T_r, T_p, M_p, T_s, e_ss) e a tela sugerida |
| `circuito` | R, R2, C1 e C2 do PI, PD ou PID analógico (calculados e das séries E24/E6) e os ganhos que os valores comerciais dão |
| `preparar`, `a` | trigger em CH1 subindo no meio do degrau, aquisição única; `a` mede a resposta e compara com a prevista |
| `lgr` | lugar das raízes com os polos de malha aberta (×) e de malha fechada (■) |
| `tabela`, `grafico <1..4>` | as quatro tabelas (previsto onde falta captura) e as respostas medidas |
| `set tipo pd\|pid\|auto`, `set tp`, `set vmax`, `set vgrau`, `set igv` | opções de projeto; por padrão T_p é o menor que não satura o amp-op (|Va| ≤ 10 V) e o PID entra nas linhas com carga |

Hipóteses que a folha não fixa e que ficam como opção: a carga entra no mesmo instante do degrau, com `ig = Vg·igv` constante (`igv` sai da Tabela 2 do Exp. 8: ig por volt de Va), e o sensor de posição dá 0,1 V/° (só muda a escala da tela e os ganhos do circuito). `conectar sim` gera a previsão do modelo com ruído e 8 bits: serve para ensaiar a sessão, não é medida. `python -m labscope.sessao.latex <sessão> <destino>/09` exporta as quatro tabelas (medido e previsto), a tabela de projeto, as respostas, o lugar das raízes e o código.

## Experimento 10 – compensador avanço de fase

O compensador é um amp-op com R1 ∥ C1 na entrada e R2 ∥ C2 na realimentação: G_c = (R2/R1)·(R1C1·s + 1)/(R2C2·s + 1). A folha tem dois tipos de tabela, e a sessão mede os dois com **CH1 no gerador** e **CH2 na saída**:

- **Senoide** (Tabelas 1, 2, 4 e 7): Vpp da saída e ângulo de fase de CH2 em relação a CH1, por ajuste de senoide na frequência medida em CH1, comparados com G(jω). Casos 1.1 (inversor, 500 Hz), 2.1–2.6 (compensador em malha aberta, 20 Hz a 5 kHz), 4.1 (RC) e 7.1 (RLC), estes em 100 Hz.
- **Degrau** (Tabelas 3, 5 e 6): onda quadrada de 50 Hz, como nos Exps. 6 e 7. Casos 3.1 (RC: τ, T_r, T_s, V_c) e 5.1 (RLC: T_r, T_p, M_p, T_s, V_c e ζ, ω_n, ω_d).

| No prompt | O que acontece |
|---|---|
| `caso 2.3`, `t` | zero, polo e fase máxima do compensador; G(jω), Vpp e fase previstos, ou a resposta ao degrau |
| `a` | senoide: Vpp de entrada e saída, \|G\| e fase; degrau: as métricas de sempre |
| `grafico 2` (ou 1, 4, 7) | Bode teórico com os pontos medidos; nas Tabelas 3 e 5, as respostas |
| `lgr [componente]` | lugar das raízes das malhas fechadas (3.1, 4.1, 5.1, 7.1), variando R2 por padrão |
| `set Rc 980`, `L1=75m` | valores reais, com os nomes da folha (R, R1, C1, R2, C2, R3, R4, R5, R6, Rc, Cc, L1) |

Nas Figuras 2 e 3, V_c volta direto ao somador e o inversor R5/R6 fica entre o compensador e a planta: a saída sai **invertida** (fase perto de 180° em 100 Hz) e as métricas do degrau são tiradas de −CH2. `ajustar` (K_p, K_i, K_d) não se aplica, e a exportação LaTeX ainda não cobre o Exp. 10. Previsões e o que esperar na bancada: `analise_experimento10.md`.

## Arquitetura

| Pacote | Classes |
|---|---|
| `circuitos` | `FT`; `Bloco` → `EstagioAmpOp` (`Somador`, `Inversor`, `InversorRealimentacao`), `Controlador` (`ControladorP`, `ControladorPI`, `ControladorPID`, `ControladorIdeal`, `CompensadorAvanco`), `Planta` (`PlantaRC`, `PlantaRLC`); `MalhaFechada` |
| `medidas` | `RespostaMedida`, `RespostaTeorica`; `Metrica` → `TempoSubida`, `InstantePico`, `Sobressinal`, `TempoAssentamento`, `ConstanteTempo`, `ValorFinal`, `ErroEstacionario`, `FatorAmortecimento`, `FrequenciaNatural`, `FrequenciaAmortecida` (e as variantes por decremento logarítmico), `GanhoProporcional`, `GanhoIntegral`, `GanhoDerivativo`; `RespostaSenoidal`, `PrevisaoSenoidal` (Exp. 10) |
| `instrumentos` | `Osciloscopio` → `TektronixTBS`, `OsciloscopioArquivo`, `OsciloscopioSimulado`, `MotorSimulado`, `ControleSimulado`; `Transcricao` |
| `roteiros` | `Roteiro` → `Experimento6`, `Experimento7`, `Experimento8`, `Experimento9`, `Experimento10`; `Caso`, `PontoMotor`, `CasoControle`, `CasoAvanco`, `Tabela`, `Componentes`, `ComponentesAvanco` |
| `motor` | `MotorCC`, `Reta`, `Leitura`, `Identificacao`; `DegrauMotor`, `RespostaMalha` (Exp. 9), `previsao`; `componentes` (resistores e capacitores); `Projeto` → `ProjetoPI`, `ProjetoPD` → `ProjetoPID` |
| `sessao` | `SessaoLab` (prompt) → `SessaoMotor` (Exp. 8) → `SessaoControle` (Exp. 9), `SessaoLab` → `SessaoAvanco` (Exp. 10; a classe segue o `exp`), `analisar` → `Resultado`, `analisar_motor` → `ResultadoMotor`, figuras, gravação e exportação LaTeX |

As classes abstratas definem o contrato e as concretas só preenchem o que muda:

- Um estágio com amp-op declara `z_entrada()` e `z_realimentacao()`; o ganho −Z_f/Z_in é herdado. O PID é o PI com `z_entrada()` trocada por R ∥ C₁.
- Uma métrica declara `medir(medida)` e `prever(teoria)`; formato, tolerância e comparação são herdados.
- Um osciloscópio declara `conectar()` e `adquirir()`; a análise recebe uma `Captura` e não sabe de onde ela veio.

```python
from labscope.circuitos import ControladorPID, MalhaFechada, PlantaRC
from labscope.instrumentos import TektronixTBS
from labscope.medidas import METRICAS, RespostaMedida, RespostaTeorica

malha = MalhaFechada(ControladorPID(R=10e3, R2=10e3, C2=10e-9, C1=10e-9), PlantaRC(R1=1e3, C=1e-6))
malha.controlador.ganhos()        # {'kp': 2.0, 'ki': 10000.0, 'kd': 0.0001}
malha.polos(), malha.estavel(), malha.com_carga().ft()

teoria = RespostaTeorica(malha)
with TektronixTBS() as scope:
    medida = RespostaMedida(scope.adquirir(), frequencia=10.0, subida=teoria.subida, integral=True)
mp = METRICAS["mp"]
mp.medir(medida), mp.prever(teoria), mp.comparar(mp.medir(medida), mp.prever(teoria)).ok
```

Um experimento novo é uma subclasse de `Roteiro` com `casos()` e `tabelas()`; um controlador novo, uma subclasse de `ControladorAmpOp` com as duas impedâncias e os três ganhos.

## Núcleo numérico (funções)

As classes acima se apoiam nestes módulos, que continuam utilizáveis sozinhos:

| Módulo | O que faz |
|---|---|
| `tek` | lê `FnnnnCHk.CSV` com metadados, alinha os canais de uma pasta `ALLnnnn`, exporta para o ngscopeclient |
| `sinais` | patamares, bordas com histerese (trigger), onda quadrada de referência, recorte por meio período, média móvel, LSB |
| `metricas` | τ, T_r, T_p, M_p, T_s de um degrau; média sobre todas as bordas; decremento logarítmico; fórmulas de 1ª e 2ª ordem |
| `modelo` | blocos P, PI, RC, RLC (com carga e ESR), malha fechada, simulação, polos, Routh, lugar das raízes |
| `ajuste` | erro quadrático entre modelo e medida; busca de parâmetros |
| `graficos` | figuras de resposta no tempo e de lugar das raízes |
| `relatorio` | tabelas Markdown com números em pt-BR |

```bash
python -m labscope.tek info E:\NEW_FOLHHH              # resumo de cada captura do pendrive
python -m labscope.tek exportar E:\NEW_FOLHHH\ALL0000  # CSVs para o ngscopeclient
python -m pytest                                        # testes (rodar da raiz)
```

Funções de transferência no núcleo são pares `(num, den)` de coeficientes em s, do maior grau para o menor; um objeto `FT` desempacota nesse par (`modelo.simular(*ft, u, dt)`).
