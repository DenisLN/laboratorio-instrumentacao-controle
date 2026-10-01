"""Ganhos do controlador: previstos pelos componentes e identificados na medida.

A identificação ajusta um controlador ideal à forma de onda (custa alguns
segundos), então o resultado fica guardado na própria métrica de K_p e as de
K_i e K_d o reaproveitam.
"""
from .base import Metrica


class Identificacao:
    """Ajuste dos ganhos de uma malha a uma medida, feito uma vez e compartilhado."""

    def __init__(self, malha):
        self.malha = malha
        self._feito = {}

    def ganhos(self, medida):
        if id(medida) not in self._feito:
            self._feito[id(medida)] = medida.identificar_ganhos(self.malha)
        return self._feito[id(medida)]


class _Ganho(Metrica):
    campo = "?"
    tolerancia = 0.20

    def __init__(self, identificacao):
        self.identificacao = identificacao

    def aplicavel(self, teoria):
        return teoria.malha.controlador.ganhos()[self.campo] > 0

    def medir(self, medida):
        return self.identificacao.ganhos(medida)[self.campo]

    def prever(self, teoria):
        return teoria.malha.controlador.ganhos()[self.campo]


class GanhoProporcional(_Ganho):
    chave, nome, simbolo, casas, campo = "kp", "Ganho proporcional", "Kp", 2, "kp"


class GanhoIntegral(_Ganho):
    chave, nome, simbolo, unidade, casas, campo = "ki", "Ganho integral", "Ki", "1/s", 0, "ki"


class GanhoDerivativo(_Ganho):
    chave, nome, simbolo, unidade, escala, casas, campo = "kd", "Ganho derivativo", "Kd", "ms", 1e3, 4, "kd"


def ganhos(malha):
    """As três métricas de ganho de uma malha, compartilhando um único ajuste."""
    ident = Identificacao(malha)
    return [GanhoProporcional(ident), GanhoIntegral(ident), GanhoDerivativo(ident)]
