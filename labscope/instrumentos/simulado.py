"""Osciloscópio de mentira: gera o que a bancada mostraria para uma malha.

Serve para ensaiar a sessão e para os testes. Imita um TBS1000: 2500 pontos,
8 bits em 10 divisões verticais e ruído de fundo.
"""
import numpy as np

from .. import modelo, sinais
from ..captura import Captura
from .base import Osciloscopio


class OsciloscopioSimulado(Osciloscopio):
    nome = "simulado"

    def __init__(self, fonte, frequencia=10.0, amplitude=0.5, s_div=2.5e-3, pontos=2500,
                 v_div=(0.2, 0.2), ruido=2e-3, semente=0, quantizar=True):
        """`fonte` devolve a MalhaFechada "montada na bancada" a cada aquisição.
        Com `quantizar=False` e `ruido=0` a captura é a resposta exata do modelo."""
        self.fonte = fonte
        self.frequencia, self.amplitude = frequencia, amplitude
        self.s_div, self.pontos, self.v_div, self.ruido = s_div, pontos, v_div, ruido
        self.quantizar = quantizar
        self._rng = np.random.default_rng(semente)

    def conectar(self):
        return "SIMULADO,TBS 1052B,0,labscope"

    def preparar(self, s_div, media=0):
        self.s_div = s_div
        return ""

    def _digitalizar(self, v, v_div):
        lsb = v_div * 10 / 250       # 25 níveis por divisão, como no TBS1000
        v = v + self._rng.normal(0, self.ruido, len(v))
        if not self.quantizar:
            return v
        return np.clip(np.round(v / lsb), -127, 127) * lsb

    def adquirir(self, canais=("CH1", "CH2")):
        dt = self.s_div * 10 / self.pontos
        self.registrar("--", f"simulação: {self.pontos} pontos a {self.s_div:g} s/div, {self.frequencia:g} Hz")
        t = dt * (np.arange(self.pontos) - self.pontos // 10)      # borda de subida a 1 divisão da esquerda
        entrada = sinais.Quadrada(-self.amplitude, self.amplitude, 1 / self.frequencia, 0.0)
        u, y = modelo.resposta_a_quadrada(*self.fonte().ft(), t, entrada, 3)
        sinal = {"CH1": u, "CH2": y}
        # 4 divisões para cada lado do zero: o que passar disso sai cortado, como na tela
        meta = {c: {"Sample Interval": dt, "Record Length": self.pontos, "Vertical Scale": vd, "Source": c,
                    "cortado": bool(self.quantizar and np.max(np.abs(sinal[c])) > 4 * vd)}
                for c, vd in zip(("CH1", "CH2"), self.v_div)}
        meta["geral"] = {"idn": self.conectar(), "pontos": self.pontos}
        return Captura(t, {c: self._digitalizar(sinal[c], vd) for c, vd in zip(("CH1", "CH2"), self.v_div)},
                       meta, "simulação")
