"""Métricas de resposta ao degrau medidas em formas de onda e as fórmulas
clássicas de 1ª e 2ª ordem."""
import math

import numpy as np

from . import sinais


def degrau(t, y, y0, yf, subida="10-90", banda=0.02, margem=0.1):
    """Métricas de uma resposta ao degrau que começa em t[0], de y0 para yf.

    tau  tempo até 63,2 %
    tr   tempo de subida: "10-90" ou "0-100" (1º cruzamento do valor final)
    tp   instante do pico;  mp  sobressinal relativo ao tamanho do degrau
    ts   entrada definitiva na faixa de ±banda; NaN se a última saída da faixa
         cai nos `margem` finais do trecho (não dá para dizer que acomodou)
    """
    t = np.asarray(t, float) - t[0]
    fr = (np.asarray(y, float) - y0) / (yf - y0)

    def cruza(f):
        k = int(np.argmax(fr >= f))
        return float(t[k]) if fr[k] >= f else math.nan

    kp = int(np.argmax(fr))
    fora = np.flatnonzero(np.abs(fr - 1) > banda)
    acomodou = len(fora) and fora[-1] < min((1 - margem) * len(fr), len(fr) - 1)
    return dict(tau=cruza(0.632),
                tr=cruza(0.9) - cruza(0.1) if subida == "10-90" else cruza(1.0),
                tp=float(t[kp]), mp=max(0.0, float(fr[kp] - 1)),
                ts=float(t[fora[-1] + 1]) if acomodou else math.nan)


def media(itens):
    """Média campo a campo de uma lista de dicts, ignorando NaN; NaN se todos forem NaN."""
    return {k: math.nan if all(math.isnan(r[k]) for r in itens)
            else float(np.nanmean([r[k] for r in itens])) for k in itens[0]}


def medir_degraus(t, ref, y, subida="10-90", banda=0.02, pre=3, cauda=0.05, **kw):
    """Média das métricas de `y` em todos os meios períodos completos da onda
    quadrada `ref` (as descidas entram espelhadas).

    Valor inicial: média das `pre` amostras antes da borda (e a da borda).
    Valor final `yf`: média da fração `cauda` final do meio período.
    Inclui `semi` (duração do meio período) e `n` (quantos entraram na média).
    """
    res = []
    for i, j, sinal in sinais.meios_periodos(ref, **kw):
        seg = sinal * y[i:j]
        y0 = float(np.mean(sinal * y[max(0, i - pre):i + 1]))
        yf = float(np.mean(seg[-max(3, len(seg) // int(round(1 / cauda))):]))
        if yf <= y0:
            continue
        m = degrau(t[i:j], seg, y0, yf, subida, banda)
        m.update(yf=yf, semi=float(t[j - 1] - t[i]))
        res.append(m)
    if not res:
        return None
    out = media(res)
    out["n"] = len(res)
    return out


def decremento_log(t, y, yf, minimo=0.0):
    """ζ, ω_d, ω_n e σ do modo oscilatório dominante, pelos extremos sucessivos
    de `y` em torno de `yf`.

    Extremos consecutivos de uma senoide amortecida ficam π/ω_d separados e caem
    por e^(-σπ/ω_d). Zeros e polos reais rápidos só alteram amplitude e fase da
    oscilação, então o método continua valendo onde ζ = f(Mp) não vale.
    Só entram extremos com amplitude acima de `minimo`; devolve None com menos de 2.
    """
    t, e = np.asarray(t, float), np.asarray(y, float) - yf
    cruz = np.flatnonzero(np.sign(e[1:]) * np.sign(e[:-1]) < 0) + 1
    tx, ax = [], []
    for a, b in zip(cruz[:-1], cruz[1:]):
        k = a + int(np.argmax(np.abs(e[a:b])))
        if abs(e[k]) <= minimo:
            break
        tx.append(t[k])
        ax.append(abs(e[k]))
    if len(tx) < 2:
        return None
    sigma = -float(np.polyfit(tx, np.log(ax), 1)[0])
    wd = math.pi * (len(tx) - 1) / (tx[-1] - tx[0])
    wn = math.hypot(sigma, wd)
    return dict(zeta=sigma / wn, wn=wn, wd=wd, sigma=sigma, extremos=len(tx))


def medir_oscilacao(t, ref, y, yf=None, minimo=0.0, trechos=None, **kw):
    """Média de `decremento_log` nos meios períodos de `ref`. `yf` é o valor
    final como fração do patamar de `ref` (ex.: 1.0 com ação integral); se
    omitido, usa a média do fim de cada meio período. `trechos` troca os meios
    períodos por uma lista própria de (i, j, sinal)."""
    baixo, alto = sinais.niveis(ref)
    centro, amp = (alto + baixo) / 2, (alto - baixo) / 2
    res = []
    for i, j, sinal in (trechos if trechos is not None else sinais.meios_periodos(ref, **kw)):
        seg = sinal * (y[i:j] - centro)
        alvo = yf * amp if yf is not None else float(np.mean(seg[-max(3, len(seg) // 20):]))
        m = decremento_log(t[i:j], seg, alvo, minimo)
        if m:
            res.append(m)
    if not res:
        return None
    out = media(res)
    out["n"] = len(res)
    return out


# ---------------------------------------------------------------- fórmulas
def zeta_de_mp(mp):
    """ζ de um 2ª ordem padrão (sem zeros) a partir do sobressinal."""
    if mp <= 0:
        return math.nan
    l = math.log(mp)
    return -l / math.sqrt(math.pi ** 2 + l ** 2)


def primeira_ordem(tau):
    return dict(tau=tau, tr=2.2 * tau, ts=4 * tau)


def segunda_ordem(zeta, wn):
    """Tr (0-100 %), Tp, Mp e Ts (2 %) do 2ª ordem padrão subamortecido."""
    wd = wn * math.sqrt(1 - zeta ** 2)
    return dict(tr=(math.pi - math.acos(zeta)) / wd, tp=math.pi / wd,
                mp=math.exp(-zeta * math.pi / math.sqrt(1 - zeta ** 2)), ts=4 / (zeta * wn))
