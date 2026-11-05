"""Regime senoidal (Exp. 10): Vpp da saída e ângulo de fase entre CH2 e CH1.

A medida ajusta, por mínimos quadrados, a·sen + b·cos + c na frequência do
gerador aos dois canais. A frequência sai de CH1 (cruzamentos da média, com
interpolação); a previsão é G(jω) da função de transferência do circuito.
"""
import math
from dataclasses import dataclass
from functools import cached_property

import numpy as np

NAN = math.nan


def fase(graus):
    """Ângulo em (−180°, 180°]."""
    g = (graus + 180.0) % 360.0 - 180.0
    return 180.0 if g == -180.0 else g


def diferenca_fase(a, b):
    """a − b em graus, pelo menor arco (−180°, 180°]: 179° e −179° diferem de 2°."""
    return fase(a - b)


def frequencia_de(t, v):
    """Frequência pelas subidas pela média, com interpolação linear entre amostras;
    NaN se a janela tem menos de duas subidas."""
    v = np.asarray(v, float) - np.mean(v)
    histerese = 0.1 * (np.percentile(v, 99) - np.percentile(v, 1))
    subidas, armado = [], False
    for i in range(1, len(v)):
        if v[i] < -histerese:
            armado = True
        elif armado and v[i - 1] < 0 <= v[i]:
            subidas.append(t[i - 1] + (t[i] - t[i - 1]) * (-v[i - 1]) / (v[i] - v[i - 1]))
            armado = False
    if len(subidas) < 2:
        return NAN
    return (len(subidas) - 1) / (subidas[-1] - subidas[0])


def ajustar_senoide(t, v, f):
    """(amplitude de pico, fase em graus, offset) de v ≈ A·sen(2πft + φ) + c."""
    w = 2 * math.pi * f
    m = np.column_stack([np.sin(w * t), np.cos(w * t), np.ones_like(t)])
    (a, b, c), *_ = np.linalg.lstsq(m, np.asarray(v, float), rcond=None)
    return float(math.hypot(a, b)), math.degrees(math.atan2(b, a)), float(c)


class RespostaSenoidal:
    """Entrada em CH1 e saída em CH2, ambas senoides da mesma frequência."""

    def __init__(self, captura, frequencia, entrada="CH1", saida="CH2"):
        self.captura = captura
        self.frequencia_nominal = frequencia
        self.canal_entrada, self.canal_saida = entrada, saida

    @property
    def t(self):
        return self.captura.t

    @cached_property
    def lsb(self):
        v = np.unique(self.captura[self.canal_saida])
        return float(np.min(np.diff(v))) if len(v) > 1 else 0.0

    @cached_property
    def frequencia(self):
        """A de CH1 se a janela tem dois períodos; senão, a nominal."""
        f = frequencia_de(self.t, self.captura[self.canal_entrada])
        return self.frequencia_nominal if math.isnan(f) else f

    @property
    def periodos(self):
        return (self.t[-1] - self.t[0]) * self.frequencia

    @cached_property
    def _entrada(self):
        a, phi, c = ajustar_senoide(self.t, self.captura[self.canal_entrada], self.frequencia)
        if a < 0.02:
            raise ValueError(f"{self.canal_entrada} não tem uma senoide ({2e3 * a:.0f} mVpp na frequência do "
                             "gerador): confira o canal e o gerador")
        return a, phi, c

    @cached_property
    def _saida(self):
        self._entrada       # confere antes se CH1 é mesmo uma senoide
        return ajustar_senoide(self.t, self.captura[self.canal_saida], self.frequencia)

    @property
    def amplitude(self):
        """V de pico da entrada."""
        return self._entrada[0]

    @property
    def vpp_entrada(self):
        return 2 * self._entrada[0]

    @property
    def vpp(self):
        return 2 * self._saida[0]

    @property
    def ganho(self):
        return self._saida[0] / self._entrada[0]

    @property
    def fase(self):
        """Fase de CH2 em relação a CH1, em graus (positiva: CH2 adiantada)."""
        return fase(self._saida[1] - self._entrada[1])

    def curva(self, canal="CH2"):
        """Senoide ajustada ao canal, nos instantes da captura."""
        a, phi, c = self._entrada if canal == self.canal_entrada else self._saida
        return a * np.sin(2 * math.pi * self.frequencia * self.t + math.radians(phi)) + c

    @cached_property
    def residuo(self):
        """RMS, em volts, entre CH2 e a senoide ajustada (distorção, ruído, saturação)."""
        return float(np.sqrt(np.mean((self.captura[self.canal_saida] - self.curva()) ** 2)))


@dataclass(frozen=True)
class PrevisaoSenoidal:
    """Regime senoidal previsto por G(jω) para uma senoide de `amplitude` V de pico."""
    ft: object
    frequencia: float
    amplitude: float

    @property
    def g(self):
        return complex(self.ft(2j * math.pi * self.frequencia))

    @property
    def ganho(self):
        return abs(self.g)

    @property
    def vpp(self):
        return 2 * self.amplitude * self.ganho

    @property
    def fase(self):
        return fase(math.degrees(math.atan2(self.g.imag, self.g.real)))

    def curva(self, t, fase_entrada=0.0):
        """Saída prevista para a entrada A·sen(2πft + fase_entrada)."""
        w = 2 * math.pi * self.frequencia
        return self.amplitude * self.ganho * np.sin(w * np.asarray(t) + math.radians(fase_entrada + self.fase))


def bode(ft, f):
    """(|G| em dB, fase em graus) nas frequências `f` (Hz); a fase é contínua (sem saltos de 360°)."""
    g = ft(2j * np.pi * np.asarray(f, float))
    return 20 * np.log10(np.abs(g)), np.degrees(np.unwrap(np.angle(g)))
