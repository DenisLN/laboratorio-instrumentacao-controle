# labscope

Ferramentas para medir e analisar respostas ao degrau em experimentos de controle com osciloscópio Tektronix TBS/TDS: ao vivo pela USB, ou depois, a partir das pastas `ALLnnnn` do pendrive.

Dependências: `numpy`, `scipy`, `matplotlib` e, para a USB, `pyvisa` com uma biblioteca VISA instalada (NI-VISA, Keysight IO Libraries ou TekVISA).

## Sessão interativa de bancada

```bash
python -m labscope
```

ou dois cliques em `LAB.cmd`. Com `--sim` a sessão já abre ligada a um osciloscópio simulado, para ensaiar sem hardware; `--exp 6` começa no roteiro do Experimento 6.

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
| `help` | todos os comandos |

A tabela que aparece a cada aquisição tem três colunas de valor: **experimental**, **teórico** (o modelo do roteiro) e **c/ carga** (o mesmo modelo com o resistor R do inversor de realimentação em paralelo com o capacitor da planta, que o roteiro ignora). Uma métrica só é marcada `CONFERIR` se ficar fora da tolerância dos dois modelos. O `resíduo RMS` compara a curva inteira de CH2 com cada modelo; perto do LSB, a montagem está reproduzindo o modelo.

Tudo vai para `sessoes/sessao_<data>_<hora>/`:

```
01_e7_c1.1/captura.npz   captura.csv   metricas.json   metricas.txt   painel.png
02_e7_c1.2/...
tabelas_exp7.md   grafico_exp7_tabela1.png   lgr_exp7_c1.2_R2.png   scpi_transcricao.log
```

A captura é gravada antes da análise. Se a conta falhar (canal trocado, sem borda na tela), ela fica em `NN_sem_analise/` e `calcular` a reaproveita depois de corrigir o caso ou os componentes.

### Se a USB não funcionar

Salve no osciloscópio como sempre ("Save All" no pendrive) e use a mesma sessão:

```
lab> conectar E:\NEW_FOL        (a pasta que contém as ALLnnnn)
lab> adquirir                   (lê a ALLnnnn mais nova; "adquirir 7" lê a ALL0007)
```

ou `carregar E:\NEW_FOL\ALL0007` para uma pasta avulsa.

### Como ajustar a tela

- Uma borda de subida de CH1 perto da esquerda e o transitório inteiro depois dela, com sobra de patamar (o comando `teoria` diz quantos s/div). Com várias bordas na tela a medida é a média de todos os meios períodos completos.
- CH2 ocupando boa parte da tela sem cortar o pico. Sinal cortado e janela curta geram avisos.
- A média de aquisições do osciloscópio (`preparar 1m media 16`) reduz bastante o ruído de quantização.

## Arquitetura

| Pacote | Classes |
|---|---|
| `circuitos` | `FT`; `Bloco` → `EstagioAmpOp` (`Somador`, `InversorRealimentacao`), `Controlador` (`ControladorP`, `ControladorPI`, `ControladorPID`, `ControladorIdeal`), `Planta` (`PlantaRC`, `PlantaRLC`); `MalhaFechada` |
| `medidas` | `RespostaMedida`, `RespostaTeorica`; `Metrica` → `TempoSubida`, `InstantePico`, `Sobressinal`, `TempoAssentamento`, `ConstanteTempo`, `ValorFinal`, `ErroEstacionario`, `FatorAmortecimento`, `FrequenciaNatural`, `FrequenciaAmortecida` (e as variantes por decremento logarítmico), `GanhoProporcional`, `GanhoIntegral`, `GanhoDerivativo` |
| `instrumentos` | `Osciloscopio` → `TektronixTBS`, `OsciloscopioArquivo`, `OsciloscopioSimulado`; `Transcricao` |
| `roteiros` | `Roteiro` → `Experimento6`, `Experimento7`; `Caso`, `Tabela`, `Componentes` |
| `sessao` | `SessaoLab` (prompt), `analisar` → `Resultado`, figuras e gravação |

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

As classes acima se apoiam nestes módulos, que continuam utilizáveis sozinhos (`experimento6.py`, na raiz, é um exemplo completo de análise a partir do pendrive):

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
