"""A resposta em malha fechada do Exp. 9: o que o osciloscópio mostra (CH1 = referência,
CH2 = saída do sensor) e o que o modelo projetado prevê para a mesma tela.

A referência é um degrau; com carga, o gerador já está ligado quando o degrau
chega, e a corrente ig cresce junto com a velocidade. O modelo aplica a carga no
mesmo instante do degrau, como `Projeto.simular` faz depois que a resposta
acomodou.
"""
import math
from functools import cached_property

import numpy as np

from .. import metricas as Mt
from .. import modelo
from .medida import DegrauMotor

NAN = math.nan
CHAVES = ("tau", "tr", "tp", "mp", "ts", "ess")


def _fechar(m, ess):
    """Sobressinal abaixo de 0,5 % é monotônico: não há instante de pico."""
    if m["mp"] < 0.005:
        m = dict(m, mp=0.0, tp=NAN)
    return dict(tau=m["tau"], tr=m["tr"], tp=m["tp"], mp=m["mp"], ts=m["ts"], ess=ess)


def simular_degrau(projeto, t):
    """Saída do projeto (na unidade da grandeza controlada) nos instantes `t` ≥ 0:
    degrau de referência e, se o projeto tem carga, degrau de ig no mesmo instante."""
    dt = t[1] - t[0]
    y = modelo.simular(*projeto.fechada(), np.full(len(t), float(projeto.referencia)), dt)
    if projeto.ig:
        y = y - modelo.simular(*(projeto.perturbacao() * projeto.sensibilidade()), np.full(len(t), projeto.ig), dt)
    return y


def previsao(projeto, n=8000):
    """tau, tr (10–90 %), tp, mp, ts (2 %) e ess previstos para a tela do osciloscópio."""
    if not projeto.estavel():
        return {k: NAN for k in CHAVES}
    lento = min(abs(np.real(projeto.polos())))
    t = np.linspace(0, 12 / lento, n)
    y = simular_degrau(projeto, t)
    yf = float(np.mean(y[-n // 20:]))
    if abs(yf) < 1e-12:
        return {k: NAN for k in CHAVES}
    # métricas relativas ao valor final real (com o erro da carga, não à referência)
    m = Mt.degrau(t, y, 0.0, yf, "10-90")
    return _fechar(m, 1 - yf / projeto.referencia)


class RespostaMalha(DegrauMotor):
    """Mede a resposta ao degrau de uma malha fechada numa captura. O degrau de
    CH1 marca o começo; Vt(t) vem de CH2. O valor final é a média do último
    oitavo da janela, e o erro é a diferença entre ele e o degrau de CH1."""

    @cached_property
    def metricas(self):
        i, j = self.janela
        bruto = self.bruto
        y0 = float(np.mean(bruto[max(0, i - 50):max(1, i - 1)])) if i > 1 else float(bruto[0])
        yf = float(np.mean(bruto[i:j][-max(5, (j - i) // 8):]))
        if abs(yf - y0) < max(4 * self.lsb, 0.02):
            raise ValueError("CH2 não saiu do lugar depois do degrau: confira o sensor, a escala e o trigger")
        # com 8 bits, ±2 % de um degrau pequeno é menos que 2 LSB: a faixa de T_s cresce junto
        banda = max(0.02, 1.5 * self.lsb / abs(yf - y0))
        fim = j - max(1, int(self.suavizacao / self.captura.dt))      # a média móvel erra nas últimas amostras
        m = Mt.degrau(self.t[i:fim], self.y[i:fim], y0, yf, "10-90", banda)
        ref = self.va
        ess = (ref - (yf - y0)) / ref if not math.isnan(ref) and ref else NAN
        return dict(_fechar(m, ess), y0=y0, yf=yf, ref=ref, banda=banda, duracao=float(self.t[j - 1] - self.t[i]))

    def curva(self, t=None):
        """CH2 suavizado a partir do degrau, para o painel: (t − t0, y)."""
        i, j = self.janela
        fim = j - max(1, int(self.suavizacao / self.captura.dt))      # fora o fim, onde a média móvel erra
        return self.t[i:fim] - self.t[i], self.y[i:fim]

    @property
    def acomodou(self):
        ts = self.metricas["ts"]
        return not math.isnan(ts)
