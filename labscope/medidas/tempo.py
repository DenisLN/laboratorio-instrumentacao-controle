"""Métricas da resposta ao degrau no tempo e do regime permanente."""
import math

from .base import Metrica


class AmplitudeEntrada(Metrica):
    chave, nome, simbolo, unidade, casas = "amp", "Amplitude de e1 (pico)", "A (CH1)", "V", 3
    tolerancia = 0.10

    def medir(self, medida):
        return medida.amplitude

    def prever(self, teoria):
        return teoria.amplitude


class _DoDegrau(Metrica):
    """Lê um campo do dicionário de métricas do degrau, medido ou previsto."""
    campo = "?"

    def medir(self, medida):
        return medida.degrau[self.campo]

    def prever(self, teoria):
        return teoria.degrau[self.campo]


class ConstanteTempo(_DoDegrau):
    chave, nome, simbolo, unidade, escala, campo = "tau", "Constante de tempo", "τ", "ms", 1e3, "tau"

    def aplicavel(self, teoria):
        return teoria.ft.ordem == 1


class TempoSubida(_DoDegrau):
    chave, nome, simbolo, unidade, escala, campo = "tr", "Tempo de subida", "Tr", "ms", 1e3, "tr"

    def rotulo(self, medida=None):
        return f"Tr ({medida.subida.replace('-', '–')} %)" if medida else self.simbolo


class InstantePico(_DoDegrau):
    chave, nome, simbolo, unidade, escala, campo = "tp", "Instante de pico", "Tp", "ms", 1e3, "tp"


class Sobressinal(_DoDegrau):
    chave, nome, simbolo, unidade, escala, casas, campo = "mp", "Sobrevalor máximo", "Mp", "%", 100, 1, "mp"
    tolerancia_abs = 0.05


class TempoAssentamento(_DoDegrau):
    chave, nome, simbolo, unidade, escala, campo = "ts", "Tempo de assentamento (2 %)", "Ts", "ms", 1e3, "ts"
    tolerancia = 0.35


class ValorFinal(Metrica):
    chave, nome, simbolo, unidade, casas = "vc", "Vc em regime (pico)", "Vc", "V", 3
    tolerancia = 0.08

    def medir(self, medida):
        return medida.vc

    def prever(self, teoria):
        return teoria.amplitude * teoria.ganho_dc


class ErroEstacionario(Metrica):
    chave, nome, simbolo, unidade, escala, casas = "ess", "Erro estacionário", "e_ss", "%", 100, 1
    tolerancia_abs = 0.04

    def medir(self, medida):
        return medida.erro_regime

    def prever(self, teoria):
        return 1 - teoria.ganho_dc if teoria.estavel else math.nan
