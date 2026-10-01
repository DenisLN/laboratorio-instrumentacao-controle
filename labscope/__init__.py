"""Ferramentas reutilizáveis para analisar capturas de osciloscópio em laboratório.

  tek       leitura das pastas ALLnnnn do Tektronix TBS/TDS e exportação para ngscopeclient
  sinais    níveis, bordas (trigger), onda quadrada de referência, suavização
  metricas  tau, Tr, Tp, Mp, Ts, decremento logarítmico e fórmulas de 1ª/2ª ordem
  modelo    funções de transferência, malha fechada, simulação, polos, lugar das raízes
  ajuste    ajuste de parâmetros do modelo às formas de onda medidas
  graficos  figuras de resposta no tempo e de lugar das raízes
  relatorio tabelas em Markdown com números no formato pt-BR

Por cima desse núcleo, em classes:

  circuitos     FT, estágios com amp-op, controladores P/PI/PID, plantas RC/RLC, MalhaFechada
  medidas       Metrica (medir × prever): Tr, Tp, Mp, Ts, Vc, e_ss, ζ, ω_n, ω_d, Kp/Ki/Kd
  instrumentos  Osciloscopio: Tektronix pela USB, pendrive ou simulado
  roteiros      casos e tabelas dos Experimentos 6 e 7
  sessao        o prompt interativo de bancada (python -m labscope)
"""
