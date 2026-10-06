"""Os dois lados de uma comparação: a resposta medida em uma captura e a
resposta teórica de uma malha. As métricas consultam um ou o outro."""
import math
from dataclasses import replace
from functools import cached_property

import numpy as np

from .. import ajuste, metricas, modelo, sinais
from ..circuitos import ControladorIdeal

NAN = math.nan
_SEM_SOBRESSINAL = 0.005     # abaixo disso o pico não é um sobressinal de verdade


class RespostaTeorica:
    """Resposta ao degrau prevista para uma malha fechada."""

    def __init__(self, malha, amplitude=0.5):
        self.malha = malha
        self.amplitude = amplitude       # V de pico da onda quadrada de entrada

    @cached_property
    def ft(self):
        return self.malha.ft()

    @cached_property
    def estavel(self):
        return self.malha.estavel()

    @cached_property
    def dominante(self):
        return self.malha.dominante()

    @cached_property
    def degrau(self):
        """tau, tr, tp, mp, ts e a definição de subida usada ("10-90" ou "0-100").

        Onde valem, usa as fórmulas de 1ª ordem e de 2ª ordem padrão; com zeros,
        ordem maior ou polos reais, mede a resposta ao degrau exata. Sem
        sobressinal não existe cruzamento do valor final, e T_r passa a 10–90 %.
        """
        if not self.estavel:
            return dict(tau=NAN, tr=NAN, tp=NAN, mp=NAN, ts=NAN, subida="0-100")
        num, den = self.ft
        dom = self.dominante
        if self.ft.ordem == 1 and len(num) == 1:
            return dict(metricas.primeira_ordem(dom["tau"]), tp=NAN, mp=0.0, subida="10-90")
        if self.ft.ordem == 2 and len(num) == 1 and "zeta" in dom:
            return dict(metricas.segunda_ordem(dom["zeta"], dom["wn"]), tau=NAN, subida="0-100")
        m = modelo.metricas_degrau(num, den, "0-100")
        if m["mp"] >= _SEM_SOBRESSINAL:
            return dict(m, subida="0-100")
        return dict(modelo.metricas_degrau(num, den, "10-90"), tp=NAN, mp=0.0, subida="10-90")

    @property
    def subida(self):
        return self.degrau["subida"]

    @property
    def ganho_dc(self):
        return self.malha.ganho_dc()

    def curva(self, t, entrada, n_aquec=3):
        """Saída prevista nos instantes `t` para a onda quadrada `entrada`."""
        return modelo.resposta_a_quadrada(*self.ft, t, entrada, n_aquec)[1]

    @cached_property
    def controlador(self):
        """Tensão que o amp-op do controlador teria de entregar à planta numa
        borda da onda quadrada (de −A para +A), pelo modelo linear: (t, v2).

        Sai de V_c: como V_c = G·V₂ e G = 1/den(s) (sem ESR), V₂ = den(d/dt)·V_c.
        Devolve None se a planta tiver numerador (ESR) ou a malha for instável."""
        g = self.malha.planta_efetiva.ft()
        if len(g.num) != 1 or not self.estavel:
            return None
        t, y = modelo.resposta_degrau(*self.ft, n=200000)
        y = 2 * self.amplitude * y - self.amplitude
        v2, derivada = np.zeros_like(y), y
        for c in reversed(g.den):                 # termo de grau 0, depois 1, 2...
            v2 += c * derivada
            derivada = np.gradient(derivada, t)
        return t, v2 / g.num[0]

    def saturacao(self, limite=10.0, duracao=100e-6):
        """Maior |V₂| previsto, se ele passar de `limite` volts por mais de
        `duracao` (picos curtos, como o da ação derivativa na borda, não contam)."""
        if self.controlador is None:
            return None
        t, v2 = self.controlador
        if np.sum(np.abs(v2) > limite) * (t[1] - t[0]) <= duracao:
            return None
        return float(np.max(np.abs(v2)))


class RespostaMedida:
    """Resposta ao degrau extraída de uma captura (entrada em CH1, saída em CH2).

    Mede em todos os meios períodos completos da onda quadrada (descidas
    espelhadas) e tira a média; se a janela só tem uma borda, mede dela até o
    fim do registro, e aí a frequência da onda tem de vir em `frequencia`.
    """

    def __init__(self, captura, frequencia=None, subida="0-100", integral=False, entrada="CH1",
                 saida="CH2", suavizacao=60e-6, banda=0.02):
        self.captura = captura
        self.frequencia_nominal = frequencia
        self.subida = subida
        self.integral = integral         # com ação integral o valor final é o patamar da entrada
        self.canal_entrada, self.canal_saida = entrada, saida
        self.suavizacao = suavizacao
        self.banda = banda

    # ------------------------------------------------------------ sinais
    @property
    def t(self):
        return self.captura.t

    @property
    def u(self):
        return self.captura[self.canal_entrada]

    @cached_property
    def y(self):
        """Saída com média móvel (reduz o ruído de quantização)."""
        return sinais.media_movel(self.captura[self.canal_saida], self.captura.dt, self.suavizacao)

    @cached_property
    def lsb(self):
        v = np.unique(self.captura[self.canal_saida])
        return float(np.min(np.diff(v))) if len(v) > 1 else 0.0

    @cached_property
    def _gatilho(self):
        """Nível e histerese para achar as bordas de CH1. Sai dos extremos do
        sinal, e não dos percentis 5/95 que `sinais.niveis` usa: em uma janela com
        a borda perto do começo, um dos patamares ocupa menos de 5 % do registro."""
        baixo, alto = np.percentile(self.u, [0.5, 99.5])
        if alto - baixo < 0.05:
            raise ValueError(f"{self.canal_entrada} não tem uma onda quadrada (excursão de "
                             f"{(alto - baixo) * 1e3:.0f} mV): confira o canal e o gerador")
        return dict(nivel=float(baixo + alto) / 2, histerese=0.1 * float(alto - baixo))

    @cached_property
    def entrada(self):
        """Onda quadrada ideal reconstruída de CH1."""
        periodo = 1 / self.frequencia_nominal if self.frequencia_nominal else None
        gatilho = self._gatilho
        try:
            q = sinais.quadrada(self.t, self.u, periodo=periodo, **gatilho)
        except ValueError:
            raise ValueError(f"nenhuma borda de {self.canal_entrada} na janela: ajuste a base de tempo "
                             "ou o trigger para a borda aparecer na tela") from None
        nivel = self._gatilho["nivel"]
        return replace(q, baixo=float(np.median(self.u[self.u < nivel])), alto=float(np.median(self.u[self.u >= nivel])))

    @cached_property
    def trechos(self):
        """(i, j, sinal) de cada trecho medido, sem as amostras finais que a
        média móvel distorce na borda do registro."""
        self.entrada        # confere antes se CH1 é mesmo uma onda quadrada
        k = max(1, int(round(self.suavizacao / self.captura.dt)))
        fim = len(self.t) - k
        return [(i, min(j, fim), s) for i, j, s in sinais.trechos(self.u, **self._gatilho) if min(j, fim) - i > 20]

    @property
    def bordas(self):
        return len(sinais.bordas(self.u, **self._gatilho)[0])

    @property
    def amplitude(self):
        return self.entrada.amplitude

    @property
    def frequencia(self):
        """Frequência medida de CH1; NaN se a janela tem menos de duas bordas."""
        return self.entrada.frequencia if self.bordas >= 2 else NAN

    # ------------------------------------------------------------ degrau
    @cached_property
    def por_trecho(self):
        res = []
        bruto = self.captura[self.canal_saida]
        k = max(3, int(round(self.suavizacao / self.captura.dt)))
        for i, j, s in self.trechos:
            seg = s * self.y[i:j]
            # regime anterior: sinal bruto logo antes da borda. A média móvel não
            # serve aqui, porque com ação derivativa a saída salta na própria borda.
            antes = bruto[max(0, i - 2 - k):max(1, i - 2)]
            y0 = float(np.mean(s * antes))
            yf = float(np.mean(seg[-max(3, len(seg) // 20):]))
            if yf <= y0:
                continue
            m = metricas.degrau(self.t[i:j], seg, y0, yf, self.subida, self.banda)
            if m["mp"] < _SEM_SOBRESSINAL:      # sem sobressinal não há pico, e o cruzamento de 100 % é só ruído
                m.update(tp=NAN, mp=0.0)
                if self.subida == "0-100":
                    m.update(tr=NAN)
            m.update(y0=y0, yf=yf, semi=float(self.t[j - 1] - self.t[i]))
            res.append(m)
        if not res:
            raise ValueError(f"{self.canal_saida} não acompanha {self.canal_entrada}: canais trocados, "
                             "saída invertida ou janela sem nenhuma borda completa")
        return res

    @cached_property
    def degrau(self):
        """Média dos trechos: tau, tr, tp, mp, ts, y0, yf, semi e n (quantos trechos)."""
        out = metricas.media(self.por_trecho)
        out["n"] = len(self.por_trecho)
        return out

    @property
    def vc(self):
        """Patamar de V_c em volts de pico: metade da excursão entre o regime
        anterior e o novo (não depende de offset do gerador)."""
        return (self.degrau["yf"] - self.degrau["y0"]) / 2

    @property
    def erro_regime(self):
        return (self.amplitude - self.vc) / self.amplitude

    @property
    def acomodou(self):
        return not math.isnan(self.degrau["ts"])

    @cached_property
    def oscilacao(self):
        """ζ, ω_n, ω_d e σ pelo decremento logarítmico; None se não há dois extremos."""
        if not self.integral:
            return metricas.medir_oscilacao(self.t, self.u, self.y, minimo=2 * self.lsb, trechos=self.trechos)
        # com ação integral o valor final é o próprio patamar da entrada
        q = self.entrada
        res = [m for i, j, s in self.trechos
               if (m := metricas.decremento_log(self.t[i:j], s * (self.y[i:j] - (q.alto + q.baixo) / 2), q.amplitude,
                                                2 * self.lsb))]
        return dict(metricas.media(res), n=len(res)) if res else None

    # ------------------------------------------------------------ modelo x medida
    def residuo(self, teoria):
        """RMS, em volts, entre CH2 e a curva de `teoria` para a mesma entrada."""
        ym = teoria.curva(self.t, self.entrada)
        return float(np.sqrt(np.mean((ym - self.captura[self.canal_saida]) ** 2)))

    def identificar_ganhos(self, malha):
        """K_p, K_i e K_d de um controlador ideal que, com a planta de `malha`,
        melhor reproduzem CH2. Só ajusta os ganhos que o controlador de `malha`
        tem. Devolve dict(kp, ki, kd, rms)."""
        nominal = malha.controlador.ganhos()
        livres = [k for k in ("kp", "ki", "kd") if nominal[k] > 0]
        y = self.captura[self.canal_saida]

        def custo(x):
            ganhos = dict(nominal, **{k: v * nominal[k] for k, v in zip(livres, x)})
            ft = malha.com_controlador(ControladorIdeal(**ganhos)).ft()
            if np.any(np.real(ft.polos()) >= 0):
                return 1e9
            return float(np.mean((modelo.resposta_a_quadrada(*ft, self.t, self.entrada, 3)[1] - y) ** 2))

        x, erro = ajuste.minimizar(custo, [1.0] * len(livres), [0.2] * len(livres))
        return dict(nominal, **{k: v * nominal[k] for k, v in zip(livres, x)}, rms=math.sqrt(erro))
