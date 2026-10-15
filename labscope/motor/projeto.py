"""Projeto dos controladores do Exp. 8 sobre o modelo identificado e a simulação
que confere as especificações (o papel do MATLAB/Simulink no roteiro).

  ProjetoPI    velocidade, 1000 rpm: tempo de subida 15 % menor que em malha aberta
  ProjetoPD    posição, 60°: sobressinal de no máximo 20 % e T_p escolhido
  ProjetoPID   o PD com ação integral, para eliminar o erro causado pela carga

A carga entra como a perturbação do modelo, −K1/(τs+1)·ig, aplicada em degrau
depois que a resposta à referência já acomodou.
"""
import math
from abc import ABC, abstractmethod

import numpy as np
from scipy.optimize import least_squares

from .. import metricas as Mt
from .. import modelo
from ..circuitos import FT

NAN = math.nan
N_DERIVATIVO = 100.0         # 1/s: filtro da ação derivativa, Kd·s·N/(s + N), o padrão do bloco PID do Simulink
VMAX = 10.0                  # V: o que o amp-op do controlador entrega antes de saturar


def _dois_significativos(x):
    return float(f"{x:.2g}")


class Projeto(ABC):
    """Malha com realimentação negativa: saída = G·Va − P·ig, Va = C·H·(ref − saída)."""
    nome = "?"
    grandeza = "?"
    unidade = "?"
    sensor = 1.0                 # H: o que converte a saída na tensão comparada com a referência

    def __init__(self, motor, referencia, ig=0.0, vmax=VMAX):
        self.motor = motor
        self.referencia = referencia
        self.ig = ig if motor.com_carga else 0.0
        self.vmax = vmax

    @abstractmethod
    def ganhos(self) -> dict:
        """kp, ki e kd."""

    @abstractmethod
    def planta(self) -> FT:
        """Va → saída."""

    @abstractmethod
    def perturbacao(self) -> FT:
        """ig → queda da saída."""

    @abstractmethod
    def especificacao(self) -> list:
        """[(o que, pedido, obtido, ok)]."""

    # ------------------------------------------------------------ malha
    def controlador(self):
        g = self.ganhos()
        if g["ki"]:
            return FT([g["kd"], g["kp"], g["ki"]], [1.0, 0.0])
        return FT([g["kd"], g["kp"]])

    def controlador_real(self):
        """C(s) com a ação derivativa filtrada (Kd·N·s/(s + N)), que é o que um
        circuito ou o Simulink realizam: com o derivativo ideal, Va teria um
        impulso na borda da referência."""
        g = self.ganhos()
        if not g["kd"]:
            return self.controlador()
        n = N_DERIVATIVO
        pd = FT([g["kp"] + g["kd"] * n, g["kp"] * n], [1.0, n])
        return pd + FT([g["ki"]], [1.0, 0.0]) if g["ki"] else pd

    def sinal_controle(self, s=None):
        """Va(t) que o controlador entrega na simulação `s` (padrão: `simular()`)."""
        s = s or self.simular()
        return modelo.simular(*(self.controlador_real() * self.sensor), s["ref"] - s["y"], s["t"][1] - s["t"][0])

    def pico_controle(self):
        """Maior |Va| pedido ao amp-op do controlador, com a carga se houver."""
        return float(np.max(np.abs(self.sinal_controle())))

    def _item_controle(self):
        pico = self.pico_controle()
        return ("sinal de controle |Va| máximo", f"≤ {self.vmax:g} V", f"{pico:.1f} V", pico <= self.vmax)

    def direto(self):
        return self.controlador() * self.sensor * self.planta()

    def fechada(self):
        """saída/referência."""
        return self.direto().malha()

    def sensibilidade(self):
        l = self.direto()
        return FT(l.den, np.polyadd(l.den, l.num))

    def polos(self):
        return self.fechada().polos()

    def estavel(self):
        return bool(np.all(np.real(self.polos()) < 0))

    # ------------------------------------------------------------ simulação
    def metricas(self):
        """tr (10–90 %), tp, mp e ts da resposta à referência, sem carga, e o erro em regime."""
        if not self.estavel():
            return dict(tr=NAN, tp=NAN, mp=NAN, ts=NAN, ess=NAN)
        m = modelo.metricas_degrau(*self.fechada(), "10-90")
        if m["mp"] < 0.005:
            m.update(tp=NAN, mp=0.0)
        return dict(tr=m["tr"], tp=m["tp"], mp=m["mp"], ts=m["ts"], ess=1 - m["dc"])

    def instante_carga(self):
        """Quando a carga entra na simulação: o dobro do assentamento, arredondado."""
        ts = self.metricas()["ts"]
        if math.isnan(ts):
            ts = 4 / min(abs(np.real(self.polos())))
        return _dois_significativos(2 * ts)

    def duracao(self):
        """(instante da carga, fim) da simulação: tempo para a malha se recuperar."""
        t_carga = self.instante_carga()
        lento = 5 / min(abs(np.real(self.polos())))
        return t_carga, (t_carga + max(t_carga, lento) if self.ig else 1.2 * t_carga)

    def simular(self, n=4000, t_carga=None, tfim=None):
        """t, ref, saída e (quando dá) Va: referência em degrau em t = 0 e a carga
        ig em degrau em `t_carga` (padrão: `duracao()`, como `tfim`)."""
        padrao = self.duracao()
        t_carga = padrao[0] if t_carga is None else t_carga
        t = np.linspace(0, padrao[1] if tfim is None else tfim, n)
        dt = t[1] - t[0]
        ref = np.full(n, float(self.referencia))
        y = modelo.simular(*self.fechada(), ref, dt)
        if self.ig:
            y = y - modelo.simular(*(self.perturbacao() * self.sensibilidade()), self.ig * (t >= t_carga), dt)
        return dict(t=t, ref=ref, y=y, t_carga=t_carga if self.ig else NAN)

    def erro_com_carga(self):
        """Erro em regime causado pela carga, relativo à referência, pelo teorema do
        valor final: −ig·[P·S](0)/ref. Zero quando a malha tem integrador antes do
        ponto em que a carga entra; NaN sem carga."""
        if not self.ig:
            return NAN
        f = self.perturbacao() * self.sensibilidade()
        num, den = np.array(f.num), np.array(f.den)
        while len(num) > 1 and len(den) > 1 and num[-1] == 0 and den[-1] == 0:   # cancela os s comuns
            num, den = num[:-1], den[:-1]
        if num[-1] == 0:
            return 0.0
        if den[-1] == 0:
            return -math.inf
        return float(-self.ig * num[-1] / den[-1] / self.referencia)

    def ganhos_texto(self):
        g, u = self.ganhos(), self.unidades_ganhos()
        partes = [f"Kp = {g['kp']:.4g} {u[0]}"]
        if g["ki"]:
            partes.append(f"Ki = {g['ki']:.4g} {u[1]}")
        if g["kd"]:
            partes.append(f"Kd = {g['kd']:.4g} {u[2]}")
        return "   ".join(partes).replace(".", ",")

    def unidades_ganhos(self):
        return ("V/V", "1/s", "s")

    def como_dict(self):
        return dict(nome=self.nome, referencia=self.referencia, ig=self.ig, ganhos=self.ganhos(),
                    metricas=self.metricas(), erro_com_carga=self.erro_com_carga(),
                    polos=[[float(p.real), float(p.imag)] for p in self.polos()],
                    especificacao=[dict(item=a, pedido=b, obtido=c, ok=d) for a, b, c, d in self.especificacao()])


class ProjetoPI(Projeto):
    """PI de velocidade com o tacômetro na realimentação. O zero do PI cancela o
    polo do motor (Ki/Kp = 1/τ), e a malha fechada fica de 1ª ordem com
    τ_mf = τ/(Kp·K·Kt). Para T_r ser `fator` do de malha aberta (2,2·τ),
    τ_mf = fator·τ, logo Kp = 1/(fator·K·Kt) e Ki = Kp/τ."""
    nome = "PI de velocidade"
    grandeza = "velocidade"
    unidade = "rpm"

    def __init__(self, motor, referencia=1000.0, ig=0.0, fator=0.85, vmax=VMAX):
        super().__init__(motor, referencia, ig, vmax)
        self.fator = fator
        self.sensor = motor.Kt

    def ganhos(self):
        kp = 1 / (self.fator * self.motor.KKt)
        return dict(kp=kp, ki=kp / self.motor.tau, kd=0.0)

    def planta(self):
        return self.motor.velocidade()

    def perturbacao(self):
        return self.motor.carga()

    @property
    def tr_malha_aberta(self):
        return 2.2 * self.motor.tau

    def malha_aberta(self, t, t_carga=NAN):
        """Sem controlador: Va fixa em ref/K, que dá a referência sem carga."""
        dt = t[1] - t[0]
        y = modelo.simular(*self.planta(), np.full(len(t), self.referencia / self.motor.K), dt)
        if self.ig and not math.isnan(t_carga):
            y = y - modelo.simular(*self.perturbacao(), self.ig * (t >= t_carga), dt)
        return y

    def especificacao(self):
        m = self.metricas()
        alvo = self.fator * self.tr_malha_aberta
        itens = [(f"T_r (10–90 %), {100 * (1 - self.fator):.0f} % menor que em malha aberta "
                  f"({self.tr_malha_aberta * 1e3:.0f} ms)", f"≤ {alvo * 1e3:.0f} ms", f"{m['tr'] * 1e3:.0f} ms",
                  m["tr"] <= alvo * 1.01),
                 ("erro em regime", "0", f"{m['ess'] * 100:.2f} %", abs(m["ess"]) < 1e-3)]
        if self.ig:
            e = self.erro_com_carga()
            itens.append(("erro com a carga", "0", f"{e * 100:.2f} %", abs(e) < 1e-3))
        itens.append(self._item_controle())
        return [(a, b, c.replace(".", ","), d) for a, b, c, d in itens]


class ProjetoPD(Projeto):
    """PD de posição: θ/Va = 6K/(N·s(τs+1)) em graus/V, realimentação unitária,
    com N a redução até o eixo onde a posição é medida (30 no CE110, 1 no motor).

    Começa pelo 2ª ordem padrão (ζ do sobressinal, ω_n de T_p) e corrige Kp e Kd
    numericamente, porque o zero do PD aumenta o sobressinal. O alvo é 1 ponto
    percentual abaixo do máximo pedido, para os ganhos arredondados não passarem."""
    nome = "PD de posição"
    grandeza = "posição"
    unidade = "°"

    def __init__(self, motor, referencia=60.0, tp=None, mp=0.20, ig=0.0, folga=0.01, vmax=VMAX, reducao=1.0):
        super().__init__(motor, referencia, ig, vmax)
        self.folga, self.reducao = folga, reducao
        self.tp = tp or _dois_significativos(motor.tau)
        self.mp_max, self.mp_alvo = mp, mp - folga
        self._ganhos = self._projetar()

    def planta(self):
        return self.motor.posicao(self.reducao)

    def perturbacao(self):
        return self.motor.carga_posicao(self.reducao)

    def unidades_ganhos(self):
        return ("V/°", "V/(°·s)", "V·s/°")

    def ganhos(self):
        return dict(self._ganhos)

    def analitico(self):
        """Kp, Kd e ω_n do 2ª ordem padrão: τs² + (1 + Kθ·Kd)s + Kθ·Kp = τ(s² + 2ζω_n s + ω_n²)."""
        zeta = Mt.zeta_de_mp(self.mp_alvo)
        wn = math.pi / self.tp / math.sqrt(1 - zeta ** 2)
        k = 6.0 * self.motor.K / self.reducao
        return self.motor.tau * wn ** 2 / k, max(0.0, (2 * zeta * wn * self.motor.tau - 1) / k), wn

    def _com(self, kp, kd):
        return dict(kp=kp, ki=0.0, kd=kd)

    def _projetar(self):
        kp0, kd0, self.wn = self.analitico()
        escala_kd = kd0 or self.motor.tau * self.reducao / (6.0 * self.motor.K)

        def residuo(x):
            self._ganhos = self._com(kp0 * x[0], escala_kd * x[1])
            if not self.estavel():
                return [10.0, 10.0]
            m = modelo.metricas_degrau(*self.fechada(), "0-100")
            return [m["mp"] - self.mp_alvo, m["tp"] / self.tp - 1]

        x = least_squares(residuo, [1.0, 1.0 if kd0 else 0.0], bounds=([1e-3, 0.0], [1e3, 1e3]),
                          diff_step=1e-2, xtol=1e-6).x
        return self._com(kp0 * x[0], escala_kd * x[1])

    def especificacao(self):
        m = self.metricas()
        itens = [("M_p (sobressinal)", f"≤ {self.mp_max * 100:.0f} %", f"{m['mp'] * 100:.1f} %", m["mp"] <= self.mp_max),
                 ("T_p (instante de pico, escolhido)", f"{self.tp * 1e3:.0f} ms", f"{m['tp'] * 1e3:.0f} ms",
                  abs(m["tp"] / self.tp - 1) < 0.05),
                 ("erro em regime", "0", f"{m['ess'] * 100:.2f} %", abs(m["ess"]) < 1e-3)]
        if self.ig:
            e = self.erro_com_carga()
            itens.append(("erro com a carga", "0", f"{e * 100:.2f} %", abs(e) < 1e-3))
        itens.append(self._item_controle())
        return [(a, b, c.replace(".", ","), d) for a, b, c, d in itens]


    def tp_minimo(self):
        """Menor T_p com que o sinal de controle fica dentro de `vmax` (busca
        por bisseção no logaritmo de T_p); None se o T_p atual já serve ou se
        nem 20 vezes mais lento serve."""
        if self.pico_controle() <= self.vmax:
            return None
        novo = lambda tp: type(self)(self.motor, self.referencia, tp, self.mp_max, self.ig, self.folga, self.vmax,
                                     self.reducao)
        a, b = self.tp, 20 * self.tp
        if novo(b).pico_controle() > self.vmax:
            return None
        for _ in range(8):
            meio = math.sqrt(a * b)
            a, b = (meio, b) if novo(meio).pico_controle() > self.vmax else (a, meio)
        return _dois_significativos(b * 1.05)


class ProjetoPID(ProjetoPD):
    """O PD com Ki = Kp·ω_n/10: o zero da ação integral fica uma década abaixo
    de ω_n, e Kp e Kd são corrigidos de novo para o sobressinal e T_p."""
    nome = "PID de posição"

    def _com(self, kp, kd):
        return dict(kp=kp, ki=kp * self.wn / 10, kd=kd)
