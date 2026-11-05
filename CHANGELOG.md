# Changelog

## v4 – 2026-10-29

Experimento 10 (compensador avanço de fase). Ainda não usado em bancada.

### Experimento 10

- `Experimento10`: as sete tabelas da folha. Senoide nas Tabelas 1 (inversor, 500 Hz), 2 (compensador em malha aberta, 20 Hz a 5 kHz), 4 e 7 (malha RC e RLC, 100 Hz), com Vpp da saída e ângulo de fase; onda quadrada de 50 Hz nas Tabelas 3 (RC), 5 e 6 (RLC). `ComponentesAvanco` usa os nomes da folha (R1, C1, R2, C2, R3–R6, Rc, Cc, L1).
- `CompensadorAvanco`: R1 ∥ C1 na entrada e R2 ∥ C2 na realimentação, com zero, polo, fase máxima e a frequência dela. `Inversor` de ganho −R_f/R_in.
- `MalhaFechada(inversor_serie=...)`: a malha das Figuras 2 e 3, com o inversor no caminho direto e V_c voltando direto ao somador (saída invertida).
- `RespostaMedida(invertida=True)` mede o degrau em −CH2; `RespostaTeorica` mede a forma do degrau previsto sem o sinal, e V_c e e_ss usam |ganho DC|.
- `labscope.medidas.senoide`: `RespostaSenoidal` (frequência pelas subidas de CH1, ajuste de senoide nos dois canais: Vpp, |G| e fase), `PrevisaoSenoidal` (G(jω)) e `bode`.
- `SessaoAvanco` (`exp 10`, `--exp 10`): `casos`, `teoria`, `adquirir` e `tabela` para os dois tipos de caso, `grafico` com o Bode e os pontos medidos, `lgr` nas malhas fechadas; `ajustar` recusado. O simulador (`conectar sim`) gera senoides em regime nos casos senoidais.
- `analise_experimento10.md`: o que a folha pede, a função de transferência, as previsões de cada tabela e o que esperar na bancada.

### Outros

- `SessaoLab`: ganchos `_analise` e `_desenhar_painel`; `retomar` reanalisa só as capturas da mesma família; `set`, `comp` e `status` usam os componentes do caso (nomes do Exp. 10 também no atalho `Rc=980`).
- O simulador volta à onda quadrada ao sair do Exp. 10.
- A exportação LaTeX avisa que ainda não cobre o Exp. 10.
- 144 → 155 testes.

## v3 — 2026-10-15

Experimento 9 (controle do motor CC com perturbações) e revisão da análise do Exp. 8. Ainda não usado em bancada.

### Experimento 9

- `Experimento9`: quatro tabelas da folha (PI e PD/PID, sem carga e com Vg = 6/9 V e 5/8 V), colunas τ, T_r, T_p, M_p e T_s.
- `labscope.motor.resposta`: `RespostaMalha` mede a resposta ao degrau em malha fechada (CH1 = referência, CH2 = sensor) com a faixa de T_s ampliada quando 2 % passa a ser menos que 1,5 LSB; `previsao` simula o projeto com a carga entrando junto com o degrau.
- `labscope.motor.componentes`: R, R2, C1 e C2 do PI, PD e PID analógicos, com a série E24/E6 e os ganhos que os valores comerciais realmente dão.
- `SessaoControle` (`exp 9`, `--exp 9`): `modelo` (dados do Exp. 8 ou digitados), `projeto`, `circuito`, `lgr`, `tabela`, `grafico`, `set tipo|tp|vmax|vgrau|igv`, `retomar`. O T_p padrão é o menor que não satura o amp-op e vale para a tabela inteira, já que Vg não muda os ganhos.
- `ControleSimulado`: a previsão do modelo com ruído e 8 bits, para ensaiar com `conectar sim`.
- Exportação LaTeX (`latex_controle`): tabelas com medido e previsto, ganhos e componentes, respostas e lugar das raízes.
- `labscope/dados/exp8_2022_anotacoes.json`: as 20 leituras do relatório de 2022, só como referência para ensaiar (não são medidas deste ano).

### Revisão do Exp. 8

- `analise_experimento8.md` revisado: PD no T_p = τ pede 314 V (o amp-op satura) e os componentes do PID eram dimensionados sobre esse projeto; unidades de Ki e Kd, ganho da planta de posição e referências a linhas do código corrigidos.

### Outros

- `retomar` e `exp` reconhecem as três famílias (circuitos, motor, controle).
- 130 → 144 testes.

## v2 — 2026-10-08

Experimento 8 (controle de motor CC) no mesmo fluxo dos outros roteiros, e como roteiro padrão do `LAB.cmd`. Ainda não usado em bancada.

### Experimento 8

- `Experimento8`: Tabela 1 (sem carga) e Tabela 2 (carga no gerador), uma linha por Va de 1 a 10 V.
- `labscope.motor`: modelo de 1ª ordem (`MotorCC`, eq. 2 e 3 da teoria), mínimos quadrados (`Reta`, `Identificacao`: KKt, K, Kt e a conferência KKt/K, τ médio, K1Kt e K1), medida da partida no osciloscópio (`DegrauMotor`: Va, Vt e τ a 63,2 % da subida de Va, ou pela própria curva quando não há CH1) e projeto com simulação (`ProjetoPI`, `ProjetoPD`, `ProjetoPID`).
- `SessaoMotor`: herda o prompt da sessão; `exp 8` troca a classe. Novos comandos: anotações (`w=1020`, `ig=120m`, `vt'=2.47`, `anotar 1.4 w 1020`), `proximo` (`n`), `armar` e `projeto`; `ajustar`, `tabela`, `grafico`, `teoria`, `casos`, `retomar` e `descartar` com o sentido do Exp. 8. Cada valor novo é comparado com as retas das outras linhas.
- `MotorSimulado`: partida de 1ª ordem com zona morta, ondulação do comutador e carga resistiva no gerador, para ensaiar com `conectar sim`.
- Exportação LaTeX do Exp. 8 (`latex_motor`), chamada pelo mesmo `python -m labscope.sessao.latex`.

### Outros

- `TektronixTBS.preparar(nivel=, unico=)` e `armar()`: nível de trigger fixo e aquisição única (Single Seq). O `preparar` de sempre agora também manda `ACQuire:STOPAfter RUNSTop`, para não ficar preso em aquisição única depois do Exp. 8.
- `retomar` reconhece se a sessão gravada é do motor ou dos circuitos e troca a classe da sessão.
- `python -m labscope` abre no Exp. 8; `--exp 7` para os anteriores.
- 108 → 126 testes.

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
