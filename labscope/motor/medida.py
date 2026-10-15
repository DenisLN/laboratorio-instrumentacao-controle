"""A partida do motor numa captura: CH1 = Va (a fonte ligando), CH2 = Vt (tacômetro).

A constante de tempo é medida como no cursor do osciloscópio: do instante em que
Va sobe até Vt chegar a 63,2 % do caminho. Sem CH1 (ou com CH1 sem degrau), o
início é estimado pela própria curva: numa exponencial, Vt passa por 10 % em
0,105·τ e por 63,2 % em τ, então τ = (t₆₃ − t₁₀)/0,895.
"""
import math
from functools import cached_property

import numpy as np

from .. import sinais

NAN = math.nan
_LN_10 = math.log(1 / 0.9)          # fração de τ até 10 % numa exponencial


class DegrauMotor:
    def __init__(self, captura, entrada="CH1", saida="CH2", suavizacao=None):
        """`suavizacao` (s): janela da média móvel em CH2; por padrão τ/20, para
        tirar a ondulação do comutador sem arredondar a subida."""
        self.captura = captura
        self.canal_entrada, self.canal_saida = entrada, saida
        self._suavizacao = suavizacao

    @property
    def t(self):
        return self.captura.t

    @property
    def bruto(self):
        return np.asarray(self.captura[self.canal_saida], float)

    @property
    def u(self):
        return self.captura.canais.get(self.canal_entrada)

    @cached_property
    def lsb(self):
        v = np.unique(self.bruto)
        return float(np.min(np.diff(v))) if len(v) > 1 else 0.0

    # ------------------------------------------------------------ onde começa
    @cached_property
    def borda(self):
        """(índice da subida de Va, índice onde Va volta a cair ou o fim) ou None
        quando CH1 não tem um degrau de subida."""
        u = self.u
        if u is None:
            return None
        baixo, alto = np.percentile(u, [0.5, 99.5])
        if alto - baixo < 0.2:
            return None
        idx, sobe = sinais.bordas(u, nivel=(baixo + alto) / 2, histerese=0.1 * (alto - baixo))
        # mau contato ao encostar o cabo da fonte: quedas mais curtas que isso não encerram a partida
        repique = max(20, len(u) // 50)
        bordas = list(zip(idx, sobe))
        for k, (i, s) in enumerate(bordas):
            if not s:
                continue
            fim = len(u)
            for m in range(k + 1, len(bordas)):
                f, desce = bordas[m]
                volta = bordas[m + 1][0] if m + 1 < len(bordas) else len(u)
                if not desce and volta - f >= repique:
                    fim = f
                    break
            return int(i), int(fim)
        return None

    @property
    def tem_entrada(self):
        return self.borda is not None

    @cached_property
    def janela(self):
        """(início, fim) em amostras do trecho medido. Sem CH1, do 1º ponto em
        que CH2 passa da metade da excursão, voltando até onde ele ainda estava
        parado, até o fim do registro."""
        if self.borda is not None:
            return self.borda
        y = sinais.media_movel(self.bruto, self.captura.dt, 20 * self.captura.dt)
        baixo, alto = np.percentile(y, [1, 99])
        if alto - baixo < max(4 * self.lsb, 0.02):
            raise ValueError(f"{self.canal_saida} não tem uma partida (excursão de {(alto - baixo) * 1e3:.0f} mV): "
                             "confira o tacômetro, a escala e o trigger")
        if abs(y[-len(y) // 10:].mean() - alto) > abs(y[-len(y) // 10:].mean() - baixo):
            raise ValueError(f"{self.canal_saida} termina embaixo: a janela pegou o motor desligando, ou o "
                             "tacômetro está invertido (troque as pontas ou o trigger para a subida)")
        meio = int(np.argmax(y >= (baixo + alto) / 2))
        parado = np.flatnonzero(y[:meio] <= baixo + 0.05 * (alto - baixo))
        return (int(parado[-1]) if len(parado) else 0), len(y)

    # ------------------------------------------------------------ medida
    @cached_property
    def suavizacao(self):
        if self._suavizacao is not None:
            return self._suavizacao
        rapido = self._medir(sinais.media_movel(self.bruto, self.captura.dt, 10 * self.captura.dt))
        tau = rapido["tau"] if not math.isnan(rapido["tau"]) else 0.0
        return max(tau / 20, 3 * self.captura.dt)

    @cached_property
    def y(self):
        """CH2 com média móvel centrada (não atrasa a curva)."""
        return sinais.media_movel(self.bruto, self.captura.dt, self.suavizacao)

    def _medir(self, y):
        i, j = self.janela
        t = self.t
        bruto = self.bruto
        antes = bruto[max(0, i - 50):max(1, i - 1)] if i > 1 else bruto[:1]
        y0 = float(np.mean(antes))
        seg = y[i:j]
        yf = float(np.mean(bruto[i:j][-max(5, (j - i) // 8):]))      # regime: o último oitavo, sem média móvel
        passo = yf - y0
        fr = (seg - y0) / passo if passo else np.zeros_like(seg)

        def cruza(f):
            n = int(np.argmax(fr >= f))
            return float(t[i + n]) if len(fr) and fr[n] >= f else NAN

        t10, t63 = cruza(0.1), cruza(1 - math.exp(-1))
        if self.borda is not None:
            t0 = float(t[i])
            tau = t63 - t0
        else:
            tau = (t63 - t10) / (1 - _LN_10)
            t0 = t10 - _LN_10 * tau
        return dict(y0=y0, yf=yf, passo=passo, t0=t0, t10=t10, t63=t63, tau=tau,
                    tau_1063=(t63 - t10) / (1 - _LN_10), duracao=float(t[j - 1] - t0))

    @cached_property
    def degrau(self):
        """y0, yf, passo (= Vt), t0, t10, t63, tau, tau_1063 e duracao (o que
        sobrou de janela depois da partida)."""
        return self._medir(self.y)

    # ------------------------------------------------------------ resultados
    @property
    def vt(self):
        """Tensão do tacômetro em regime, a partir do repouso (o passo de CH2)."""
        return abs(self.degrau["passo"])

    @property
    def tau(self):
        return self.degrau["tau"]

    @cached_property
    def va(self):
        """Degrau de Va em CH1 (NaN sem CH1)."""
        if self.borda is None:
            return NAN
        i, j = self.borda
        u = np.asarray(self.u, float)
        antes = u[max(0, i - 50):max(1, i - 1)] if i > 1 else u[:1]
        depois = u[i + (j - i) // 5:j]
        return float(np.median(depois) - np.median(antes))

    @property
    def acomodou(self):
        """Se sobrou janela para Vt chegar ao regime (pelo menos 4 τ)."""
        return not math.isnan(self.tau) and self.degrau["duracao"] >= 4 * self.tau

    def curva(self, t=None):
        """A exponencial de 1ª ordem com os valores medidos, nos instantes `t`."""
        t = self.t if t is None else np.asarray(t, float)
        d = self.degrau
        arg = np.clip((t - d["t0"]) / d["tau"], 0, None) if d["tau"] > 0 else np.zeros_like(t)
        return d["y0"] + d["passo"] * (1 - np.exp(-arg))

    def residuo(self):
        """RMS, em volts, entre CH2 e a exponencial medida, depois da partida."""
        i, j = self.janela
        return float(np.sqrt(np.mean((self.curva(self.t[i:j]) - self.bruto[i:j]) ** 2)))
