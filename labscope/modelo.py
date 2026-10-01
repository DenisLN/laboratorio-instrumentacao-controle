"""Funções de transferência como pares (num, den) de coeficientes em s, do
maior grau para o menor: blocos usuais, malha fechada, simulação e polos."""
import math

import numpy as np
from scipy.signal import cont2discrete, lfilter

from . import metricas, sinais


# ---------------------------------------------------------------- blocos
def p(kp):
    return [kp], [1.0]


def pi(kp, ki):
    return [kp, ki], [1.0, 0.0]


def _divisor(zs, C, carga, esr):
    """Vc/Vin da impedância série `zs` (polinômio em s) alimentando o ramo
    C + esr em paralelo com `carga`."""
    ramo = [esr * C, 1.0] if esr else [1.0]             # 1 + s·esr·C
    den = np.polyadd(np.polymul(ramo, np.polyadd(np.asarray(zs, float) / carga, [1.0])),
                     np.polymul(zs, [C, 0.0]))
    return np.asarray(ramo), den


divisor = _divisor


def rc(R, C, carga=np.inf, esr=0.0):
    """Passa-baixas RC com saída no capacitor. `carga` é uma resistência em
    paralelo com o capacitor (ex.: a entrada do estágio seguinte) e `esr` a
    resistência série dele."""
    return _divisor([R], C, carga, esr)


def rlc(R, L, C, carga=np.inf, esr=0.0):
    """RLC série com saída no capacitor; `carga` e `esr` como em `rc`."""
    return _divisor([L, R], C, carga, esr)


def serie(*fts):
    num, den = [1.0], [1.0]
    for n, d in fts:
        num, den = np.polymul(num, n), np.polymul(den, d)
    return num, den


def malha_fechada(num, den):
    """Realimentação unitária negativa em torno de num/den."""
    return np.asarray(num, float), np.polyadd(den, num)


# ---------------------------------------------------------------- análise
def ganho_dc(num, den):
    return float(num[-1] / den[-1])


def polos(den):
    return np.roots(den)


def dominante(raizes):
    """Par complexo mais próximo do eixo imaginário (zeta, wn, wd, sigma) ou,
    se todos os polos são reais, a constante de tempo do mais lento (tau)."""
    cplx = [r for r in raizes if abs(r.imag) > 1e-6]
    if not cplx:
        return dict(tau=float(-1 / max(np.real(raizes))))
    r = max(cplx, key=lambda r: r.real)
    return dict(zeta=float(-r.real / abs(r)), wn=float(abs(r)), wd=float(abs(r.imag)), sigma=float(-r.real))


def routh(den):
    """1ª coluna da tabela de Routh; o sistema é estável se todos os elementos
    têm o mesmo sinal."""
    den = np.asarray(den, float)
    n = len(den)
    cols = (n + 1) // 2
    tab = np.zeros((n, cols))
    tab[0, :len(den[0::2])] = den[0::2]
    tab[1, :len(den[1::2])] = den[1::2]
    for i in range(2, n):
        for j in range(cols - 1):
            tab[i, j] = (tab[i - 1, 0] * tab[i - 2, j + 1] - tab[i - 2, 0] * tab[i - 1, j + 1]) / tab[i - 1, 0]
    return tab[:, 0]


def lugar_raizes(den_de_k, ks):
    """Raízes de den_de_k(k) para cada k; uma linha por ganho."""
    return np.array([np.sort_complex(np.roots(den_de_k(k))) for k in ks])


# ---------------------------------------------------------------- simulação
def simular(num, den, u, dt):
    """Saída de num/den para a entrada amostrada `u`, mantida constante entre
    amostras (ZOH), partindo do repouso."""
    numd, dend, _ = cont2discrete((num, den), dt, method="zoh")
    return lfilter(numd.ravel(), dend, u)


def resposta_degrau(num, den, tfim=None, n=60000):
    """(t, y) da resposta ao degrau unitário; por padrão até 12 constantes de
    tempo do polo mais lento."""
    if tfim is None:
        tfim = 12 / min(abs(np.real(polos(den))))
    t = np.arange(n) * (tfim / n)
    return t, simular(num, den, np.ones(n), tfim / n)


def metricas_degrau(num, den, subida="0-100", banda=0.02):
    """Métricas da resposta ao degrau exata (vale com zeros e ordem > 2)."""
    t, y = resposta_degrau(num, den)
    m = metricas.degrau(t, y, 0.0, ganho_dc(num, den), subida, banda)
    m["dc"] = ganho_dc(num, den)
    return m


def resposta_periodica(num, den, t, ref, n_aquec=20, periodo=None):
    """Saída de num/den para a onda quadrada ideal reconstruída de `ref`, nos
    instantes `t`. Simula `n_aquec` períodos antes para já entrar em regime
    periódico, como na bancada. Devolve (entrada ideal, saída). `periodo` só é
    usado quando `ref` tem uma borda só (ver `sinais.quadrada`)."""
    return resposta_a_quadrada(num, den, t, sinais.quadrada(t, ref, periodo=periodo), n_aquec)


def resposta_a_quadrada(num, den, t, q, n_aquec=20):
    """Como `resposta_periodica`, com a onda quadrada `q` já reconstruída."""
    dt = float(np.median(np.diff(t)))
    antes = int(math.ceil(n_aquec * q.periodo / dt))
    tt = t[0] + dt * np.arange(-antes, len(t))
    u = q(tt)
    return u[antes:], simular(num, den, u, dt)[antes:]
