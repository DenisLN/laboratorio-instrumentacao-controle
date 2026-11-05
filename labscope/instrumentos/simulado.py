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
        self.senoide = False        # True: o gerador em senoide (Exp. 10), saída em regime permanente
        self._rng = np.random.default_rng(semente)

    def conectar(self):
        return "SIMULADO,TBS 1052B,0,labscope"

    def preparar(self, s_div, media=0, nivel=None, unico=False):
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
        if self.senoide:
            g = self.fonte().ft()(2j * np.pi * self.frequencia)
            w = 2 * np.pi * self.frequencia
            u, y = self.amplitude * np.sin(w * t), self.amplitude * abs(g) * np.sin(w * t + np.angle(g))
        else:
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


class MotorSimulado(Osciloscopio):
    """Grupo motor-gerador de mentira visto pelo osciloscópio (Exp. 8): CH1 = Va,
    a fonte ligando a 1 divisão da esquerda; CH2 = Vt, a partida de 1ª ordem com
    a ondulação do comutador. O motor tem zona morta (atrito estático) e, com
    carga, o gerador alimenta `r_carga` e freia o eixo."""
    nome = "simulado (motor)"

    def __init__(self, K=350.0, Kt=0.003, tau=0.35, K1=500.0, zona_morta=0.6, kg=0.01, r_carga=47.0,
                 s_div=250e-3, pontos=2500, v_div=(2.0, 2.0), ruido=5e-3, ondulacao=0.02, semente=0):
        self.K, self.Kt, self.tau, self.K1 = K, Kt, tau, K1
        self.zona_morta, self.kg, self.r_carga = zona_morta, kg, r_carga
        self.s_div, self.pontos, self.v_div, self.ruido, self.ondulacao = s_div, pontos, v_div, ruido, ondulacao
        self.va, self.carga = 1.0, False
        self._rng = np.random.default_rng(semente)

    def conectar(self):
        return "SIMULADO,TBS 1052B,0,labscope-motor"

    def preparar(self, s_div, media=0, nivel=None, unico=False):
        self.s_div = s_div
        return ""

    def regime(self, va=None, carga=None):
        """(ω em rpm, ig em A, τ em s) em regime para a tensão `va`."""
        va = self.va if va is None else va
        carga = self.carga if carga is None else carga
        w = self.K * max(0.0, va - self.zona_morta)
        if not carga:
            return w, 0.0, self.tau
        freio = 1 + self.K1 * self.kg / self.r_carga      # ig = kg·ω/R realimenta a velocidade
        w = w / freio
        return w, self.kg * w / self.r_carga, self.tau / freio

    def adquirir(self, canais=("CH1", "CH2")):
        dt = self.s_div * 10 / self.pontos
        t = dt * (np.arange(self.pontos) - self.pontos // 10)
        w, ig, tau = self.regime()
        self.registrar("--", f"simulação: Va = {self.va:g} V, {'com' if self.carga else 'sem'} carga, "
                             f"ω = {w:.0f} rpm, ig = {ig * 1e3:.0f} mA")
        ligado = t >= 0
        rot = w * (1 - np.exp(-np.clip(t, 0, None) / tau)) * ligado
        fase = 2 * np.pi * np.cumsum(12 * rot / 60) * dt              # 12 lâminas no comutador
        sinal = {"CH1": self.va * ligado, "CH2": self.Kt * rot * (1 + self.ondulacao * np.sin(fase))}
        meta = {c: {"Sample Interval": dt, "Record Length": self.pontos, "Vertical Scale": vd, "Source": c,
                    "cortado": bool(np.max(np.abs(sinal[c])) > 4 * vd)}
                for c, vd in zip(("CH1", "CH2"), self.v_div)}
        meta["geral"] = {"idn": self.conectar(), "pontos": self.pontos}
        canais = {}
        for c, vd in zip(("CH1", "CH2"), self.v_div):
            lsb = vd * 10 / 250
            v = sinal[c] + self._rng.normal(0, self.ruido, len(t))
            canais[c] = np.clip(np.round(v / lsb), -127, 127) * lsb
        return Captura(t, canais, meta, "simulação (motor)")


class ControleSimulado(Osciloscopio):
    """A malha fechada do Exp. 9 vista pelo osciloscópio: CH1 = referência (degrau em
    t = 0, a 1 divisão da esquerda), CH2 = saída do sensor (Vt ou o potenciômetro de
    posição). `projeto` e `v_por_unidade` (V por rpm ou por grau) são trocados pela
    sessão a cada linha. É o que o modelo prevê com ruído e a quantização de 8 bits:
    serve para ensaiar a sessão, não para entregar como medida."""
    nome = "simulado (controle)"

    def __init__(self, projeto=None, v_por_unidade=1.0, s_div=0.25, pontos=2500, v_div=(2.0, 2.0), ruido=5e-3,
                 semente=0):
        self.projeto, self.v_por_unidade = projeto, v_por_unidade
        self.s_div, self.pontos, self.v_div, self.ruido = s_div, pontos, v_div, ruido
        self._rng = np.random.default_rng(semente)

    def conectar(self):
        return "SIMULADO,TBS 1052B,0,labscope-controle"

    def preparar(self, s_div, media=0, nivel=None, unico=False):
        self.s_div = s_div
        return ""

    def adquirir(self, canais=("CH1", "CH2")):
        from ..motor.resposta import simular_degrau
        if self.projeto is None:
            raise RuntimeError("ControleSimulado sem projeto")
        dt = self.s_div * 10 / self.pontos
        t = dt * (np.arange(self.pontos) - self.pontos // 10)
        depois = t >= 0
        y = np.zeros(self.pontos)
        y[depois] = simular_degrau(self.projeto, t[depois] - t[depois][0])
        self.registrar("--", f"simulação: {self.projeto.nome}, referência {self.projeto.referencia:g} "
                             f"{self.projeto.unidade}, ig = {self.projeto.ig * 1e6:.0f} µA")
        sinal = {"CH1": self.projeto.referencia * self.v_por_unidade * depois, "CH2": self.v_por_unidade * y}
        meta = {c: {"Sample Interval": dt, "Record Length": self.pontos, "Vertical Scale": vd, "Source": c,
                    "cortado": bool(np.max(np.abs(sinal[c])) > 4 * vd)}
                for c, vd in zip(("CH1", "CH2"), self.v_div)}
        meta["geral"] = {"idn": self.conectar(), "pontos": self.pontos}
        canais = {}
        for c, vd in zip(("CH1", "CH2"), self.v_div):
            lsb = vd * 10 / 250
            v = sinal[c] + self._rng.normal(0, self.ruido, len(t))
            canais[c] = np.clip(np.round(v / lsb), -127, 127) * lsb
        return Captura(t, canais, meta, "simulação (controle)")
