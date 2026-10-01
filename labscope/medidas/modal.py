"""ζ, ω_n e ω_d do par de polos dominante.

Previsto: direto dos polos da malha. Medido: pelo método do roteiro (ζ de M_p e
ω_d de T_p, exato só para o 2ª ordem sem zeros) ou, nas variantes "decr.", pelo
decremento logarítmico, que continua valendo com zeros e polos extras.
"""
import math

from .. import metricas
from .base import Metrica


class _Modal(Metrica):
    campo = "?"

    def aplicavel(self, teoria):
        return teoria.estavel and "zeta" in teoria.dominante

    def prever(self, teoria):
        return teoria.dominante.get(self.campo, math.nan)

    def julgavel(self, teoria):
        """ζ = f(M_p) e ω_d = π/T_p só valem para o 2ª ordem sem zeros."""
        return teoria.ft.ordem == 2 and len(teoria.ft.num) == 1

    @staticmethod
    def _zeta(medida):
        return metricas.zeta_de_mp(medida.degrau["mp"])

    @staticmethod
    def _wd(medida):
        tp = medida.degrau["tp"]
        return math.pi / tp if tp and not math.isnan(tp) else math.nan


class FatorAmortecimento(_Modal):
    chave, nome, simbolo, casas, campo = "zeta", "Coeficiente de amortecimento", "ζ", 3, "zeta"
    tolerancia = 0.30

    def medir(self, medida):
        return self._zeta(medida)


class FrequenciaAmortecida(_Modal):
    chave, nome, simbolo, unidade, casas, campo = "wd", "Frequência natural amortecida", "ωd", "rad/s", 0, "wd"

    def medir(self, medida):
        return self._wd(medida)


class FrequenciaNatural(_Modal):
    chave, nome, simbolo, unidade, casas, campo = "wn", "Frequência natural", "ωn", "rad/s", 0, "wn"

    def medir(self, medida):
        z, wd = self._zeta(medida), self._wd(medida)
        return wd / math.sqrt(1 - z * z) if 0 < z < 1 else math.nan


def _por_decremento(base):
    """Variante de uma métrica modal que mede pelo decremento logarítmico."""

    class PorDecremento(base):
        chave = base.chave + "_dl"
        nome = base.nome + " (decremento logarítmico)"
        simbolo = base.simbolo + " decr."

        def medir(self, medida):
            return medida.oscilacao[self.campo] if medida.oscilacao else math.nan

        def julgavel(self, teoria):
            return True

    PorDecremento.__name__ = base.__name__ + "Decremento"
    return PorDecremento


FatorAmortecimentoDecremento = _por_decremento(FatorAmortecimento)
FrequenciaNaturalDecremento = _por_decremento(FrequenciaNatural)
FrequenciaAmortecidaDecremento = _por_decremento(FrequenciaAmortecida)
