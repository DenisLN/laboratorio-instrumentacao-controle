"""Métricas como objetos: cada uma sabe medir na captura e prever pelo modelo.

  RespostaMedida / RespostaTeorica   os dois lados da comparação
  Metrica                            abstrata: medir(), prever(), aplicavel()
  tempo   Tr, Tp, Mp, Ts, τ, Vc, e_ss e a amplitude da entrada
  modal   ζ, ω_n, ω_d (pelo método do roteiro e pelo decremento logarítmico)
  ganhos  K_p, K_i, K_d identificados por ajuste à forma de onda
"""
from .base import Comparacao, Metrica
from .ganhos import GanhoDerivativo, GanhoIntegral, GanhoProporcional, Identificacao, ganhos
from .modal import (FatorAmortecimento, FatorAmortecimentoDecremento, FrequenciaAmortecida,
                    FrequenciaAmortecidaDecremento, FrequenciaNatural, FrequenciaNaturalDecremento)
from .resposta import RespostaMedida, RespostaTeorica
from .tempo import (AmplitudeEntrada, ConstanteTempo, ErroEstacionario, InstantePico, Sobressinal,
                    TempoAssentamento, TempoSubida, ValorFinal)

# na ordem em que aparecem na tela
PADRAO = [AmplitudeEntrada(), ConstanteTempo(), TempoSubida(), InstantePico(), Sobressinal(),
          TempoAssentamento(), ValorFinal(), ErroEstacionario(), FatorAmortecimento(), FrequenciaNatural(),
          FrequenciaAmortecida(), FatorAmortecimentoDecremento(), FrequenciaNaturalDecremento(),
          FrequenciaAmortecidaDecremento()]
METRICAS = {m.chave: m for m in PADRAO}

__all__ = ["Metrica", "Comparacao", "RespostaMedida", "RespostaTeorica", "PADRAO", "METRICAS", "ganhos",
           "Identificacao", "AmplitudeEntrada", "ConstanteTempo", "TempoSubida", "InstantePico",
           "Sobressinal", "TempoAssentamento", "ValorFinal", "ErroEstacionario", "FatorAmortecimento",
           "FrequenciaNatural", "FrequenciaAmortecida", "FatorAmortecimentoDecremento",
           "FrequenciaNaturalDecremento", "FrequenciaAmortecidaDecremento", "GanhoProporcional",
           "GanhoIntegral", "GanhoDerivativo"]
