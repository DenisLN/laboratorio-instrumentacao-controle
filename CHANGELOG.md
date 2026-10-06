# Changelog

## v1 — 2026-10-06

Primeira versão usada de verdade no laboratório. Tudo aqui saiu de algo que aconteceu na bancada, em duas aulas do Experimento 7 (PID).

### Validação em bancada

- **2026-10-01, Tektronix TDS 2022B** (firmware v22.01): o driver conectou e baixou CH1 e CH2 na primeira tentativa, em cerca de 3 s por aquisição, devolvendo o osciloscópio ao RUN. Antes disso, o `conectar` falhou porque a porta traseira estava em modo impressora (PictBridge).
- **2026-10-06, Tektronix TBS 1052B** (firmware v4.06): 27 capturas das Tabelas 1 a 5 do Exp. 7.
  - Com os valores medidos dos componentes, as curvas coincidem com o modelo "c/ carga" dentro do LSB do osciloscópio nos casos 1.2, 4.1 e 4.2 (resíduo RMS de 20 a 27 mV com LSB de 20 mV).
  - O modelo ideal do roteiro superestima o sobressinal nos casos RLC (R_L = 10 kΩ): o resistor de entrada do inversor carrega o capacitor da planta.
  - Caso 5.1: o controlador precisaria entregar cerca de 31 V e satura; a subida e o primeiro pico não seguem o modelo linear, mas a frequência da oscilação seguinte bate (+1,5 %).
  - Caso 5.2: patamar 9 % acima da entrada nos dois semiciclos. Um teste com as duas pontas no gerador mostrou os canais concordando em 0,9 %, então o desvio está no circuito (razão entre os resistores do somador e do inversor, ou contato).

### Conexão

- `conectar` e `recursos` reconhecem o osciloscópio em modo impressora (PictBridge) pelo Gerenciador de Dispositivos do Windows e dizem o que trocar no aparelho: Utility → Options → Rear USB Port → Computer.
- Mensagem de falha de conexão com o plano B (pendrive) e a dica de `recursos`.

### Medida e análise

- `set sonda <1|10|off>`: corrige as tensões quando a atenuação configurada no canal difere da ponta usada. A captura guarda os dois valores (`Probe Atten` e `Probe Atten no osciloscópio`).
- Aviso automático quando a amplitude de CH1 vem cerca de 10 vezes a do roteiro e o canal está em 10X ou 1X.
- Aviso automático, antes de montar (`teoria`) e depois de medir (`adquirir`), quando o amp-op do controlador teria de passar de 10 V por mais de 0,1 ms para seguir o modelo linear. Picos curtos da ação derivativa na borda não contam. Entre os 26 casos dos Exps. 6 e 7, só o 5.1 do Exp. 7 dispara (`RespostaTeorica.controlador` e `.saturacao()`).
- `Metrica.folga()`: a incerteza da própria medida entra na comparação. V_c aceita um LSB e e_ss aceita 2 LSB divididos pela amplitude, então uma diferença de quantização não vira mais `CONFERIR`.

### Sessão

- `retomar [pasta]`: continua a última sessão gravada. Recupera os valores reais dos componentes, a numeração das capturas e reanalisa as capturas já feitas, para `tabela` e `grafico` enxergarem tudo. Com 26 capturas leva cerca de 2 s.
- `descartar [n]`: tira uma captura das tabelas sem apagar nada; a pasta ganha `_descartada` no nome e o caso volta a usar a captura anterior.
- `ver` (`v`): desenha a última captura como veio do osciloscópio, sem análise. Quando a análise falha, esse desenho é gerado e aberto sozinho em `NN_sem_analise/bruto.png`.
- `painel` (`p`): reabre o painel da última captura analisada.
- Linha sem barra de espaço: `caso1.2`, `L=68m`, `R2=9.87k`, `set,sonda,1`, `tabela1`. Nesse modo o decimal é com ponto.
- Abreviações: um prefixo vale se só um comando começa com ele (`con`, `adq`, `stat`); se houver mais de um, a sessão lista as opções.
- `caso` e `teoria` mostram os componentes um por linha, com o nominal ao lado quando o valor em uso é outro, e não listam mais as métricas previstas (elas continuam na tabela de cada aquisição e no painel). O cabeçalho de cada aquisição também lista os componentes um por linha.

### Gravação

- A tabela de métricas é impressa antes de gravar qualquer arquivo; um erro de disco não esconde mais as contas.
- Se o Windows recusar gravar o painel (arquivo preso em outro programa, pasta apagada no meio da sessão), ele é gravado como `painel_<hora>.png`. Se a pasta da captura inteira recusar escrita, tudo vai para `NN_e7_cX.Y_<hora>/`.
- Figuras são fechadas mesmo quando a gravação falha.

### Testes

98 → 108 testes (mais 4 que dependem do pendrive do Lab 6). Novos casos: modo impressora, abreviação e linha sem espaço, desenho da captura sem análise, sonda trocada, pasta presa, folga de quantização, saturação do controlador, retomar e descartar.

## v0 — 2026-10-01 (`c2d7f76`)

Primeiro commit: a análise offline do Experimento 6 a partir das capturas do pendrive (`experimento6.py`) e a sessão interativa de bancada (`python -m labscope` / `LAB.cmd`) para os Experimentos 6 e 7.

- `circuitos`: `FT`, estágios com amp-op (`Somador`, `InversorRealimentacao`), controladores P, PI e PID (K_p = R₂/R + C₁/C₂, K_i = 1/(R·C₂), K_d = R₂·C₁), plantas RC e RLC e `MalhaFechada`, com a opção de incluir a carga do inversor sobre o capacitor.
- `medidas`: `Metrica` abstrata (medir × prever) e as métricas de tempo, modais (pelo método do roteiro e pelo decremento logarítmico) e de ganho (K_p, K_i, K_d por ajuste à forma de onda); medida com uma borda só na janela.
- `instrumentos`: `Osciloscopio` abstrato com Tektronix TBS/TDS pela USB (VISA), pendrive e simulado; transcrição SCPI com horário.
- `roteiros`: casos e tabelas dos Experimentos 6 e 7.
- `sessao`: o prompt, painel por captura, tabelas do roteiro, gráfico por tabela, lugar das raízes, `preparar` e `set diagnostico on` com a janela da transcrição SCPI ao vivo.
- O driver Tektronix tinha sido testado só contra uma conexão VISA falsa.
