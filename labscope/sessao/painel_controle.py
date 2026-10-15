"""Figuras do Experimento 9: a resposta medida contra a prevista e o lugar das raízes."""
import math

import numpy as np

from .. import graficos as G
from .. import modelo
from ..motor.resposta import simular_degrau
from .painel import _MONO
from .painel_motor import _salvar

plt = G.plt


def curvas(res):
    """(t em ms depois do degrau, referência, medido, previsto) em volts, para o painel e o LaTeX."""
    m, p = res.medida, res.projeto
    t, y = m.curva()
    v = res.v_por_unidade
    previsto = v * simular_degrau(p, t)
    ref = np.full(len(t), p.referencia * v) if m.tem_entrada else None
    return t * 1e3, ref, y, previsto


def resposta(res, caminho, dpi=130):
    """Referência (CH1), saída medida (CH2) e a resposta prevista, com a tabela de métricas ao lado."""
    t, ref, y, prev = curvas(res)
    fig = plt.figure(figsize=(13.5, 6.4))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.45, 1], wspace=0.1)
    ax = fig.add_subplot(gs[0, 0])
    if ref is not None:
        ax.plot(t, ref, color=G.CINZA, lw=1.2, label="referência (CH1)")
    ax.plot(t, y, color=G.CORES[0], lw=1.6, label="saída medida (CH2)")
    ax.plot(t, prev, color=G.CORES[1], lw=1.4, ls=G.TRACEJADO, label="previsto pelo modelo")
    ax.set_xlabel("tempo após o degrau (ms)")
    ax.set_ylabel("tensão (V)")
    ax.legend(fontsize=9, frameon=False, loc="lower right")
    ts = res.medida.metricas["ts"]
    ax.set_xlim(t[0], min(t[-1], 2.2e3 * ts) if not math.isnan(ts) else t[-1])
    G.limpar(ax)
    at = fig.add_subplot(gs[0, 1])
    at.axis("off")
    texto = "\n".join(res.linhas_texto() + [""] + [f"! {x}" for x in res.avisos])
    at.text(0.0, 1.0, texto, transform=at.transAxes, va="top", ha="left", family=_MONO, fontsize=8.2, linespacing=1.5)
    fig.suptitle(f"#{res.numero:02d}  {res.titulo()}", fontsize=11, x=0.01, ha="left")
    fig.text(0.01, 0.01, f"{res.quando}   {res.captura.origem}   {res.captura_texto()}", fontsize=7, color="#52514e")
    return _salvar(fig, caminho, dpi)


def raizes(projeto, ganhos=None):
    """Raízes de 1 + k·L(s) = 0 para os ganhos k em `ganhos` (k = 1 é o projeto)."""
    num, den = projeto.direto()
    ks = np.logspace(-2, 1.4, 600) if ganhos is None else ganhos
    return np.array([np.sort_complex(np.roots(np.polyadd(den, k * num))) for k in ks])


def escala(projeto):
    """(xmax, ymax) da figura do lugar das raízes: os polos mandam, o zero do PD fica de fora se for longe."""
    ma = np.roots(projeto.direto().den)
    mf = np.asarray(projeto.polos())
    polos = np.concatenate([ma, mf])
    return max(1.0, 2.2 * float(np.max(np.abs(polos.real)))), max(1.0, 1.5 * float(np.max(np.abs(polos.imag))))


def lugar(projeto, caminho, dpi=150):
    """Polos de malha aberta (×) e de malha fechada (○) sobre o lugar das raízes da malha do projeto."""
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    rs = raizes(projeto)
    ax.scatter(rs.real.ravel(), rs.imag.ravel(), s=1.5, color=G.CINZA, zorder=1, label="lugar das raízes (ganho de malha k)")
    ma = np.roots(projeto.direto().den)
    zeros = np.roots(projeto.direto().num) if len(projeto.direto().num) > 1 else np.array([])
    mf = np.asarray(projeto.polos())
    ax.plot(ma.real, ma.imag, "x", color=G.CORES[1], ms=10, mew=2, label="polos de malha aberta")
    if len(zeros):
        ax.plot(zeros.real, zeros.imag, "o", color=G.CORES[1], mfc="none", ms=8, mew=1.5, label="zeros")
    ax.plot(mf.real, mf.imag, "s", color=G.CORES[0], ms=7, label="polos de malha fechada (projeto)")
    ax.axhline(0, color="#b5b4ae", lw=0.6)
    ax.axvline(0, color="#b5b4ae", lw=0.6)
    xr, yr = escala(projeto)
    for z in zeros[np.abs(zeros.real) > xr]:
        ax.annotate(f"zero em {z.real:.3g}".replace(".", ",") + " (fora da escala)", (0.02, 0.06), xycoords="axes fraction",
                    fontsize=8, color=G.CORES[1])
    ax.set_xlim(-xr, 0.15 * xr)
    ax.set_ylim(-yr, yr)
    ax.set_xlabel("Re(s)  [1/s]")
    ax.set_ylabel("Im(s)  [rad/s]")
    ax.set_title(f"{projeto.nome}: {projeto.ganhos_texto()}", fontsize=10, loc="left")
    ax.legend(fontsize=7.5, frameon=False, loc="best")
    G.limpar(ax)
    return _salvar(fig, caminho, dpi)


def respostas(resultados, caminho, dpi=140):
    """As respostas de uma tabela, uma por painel, medido contra previsto."""
    n = len(resultados)
    fig, axs = plt.subplots(1, n, figsize=(6.2 * n, 4.2), squeeze=False)
    for ax, res in zip(axs[0], resultados):
        t, ref, y, prev = curvas(res)
        if ref is not None:
            ax.plot(t, ref, color=G.CINZA, lw=1.1, label="referência")
        ax.plot(t, y, color=G.CORES[0], lw=1.5, label="medido")
        ax.plot(t, prev, color=G.CORES[1], lw=1.2, ls=G.TRACEJADO, label="previsto")
        ax.set_title(res.caso.rotulo, fontsize=10, loc="left")
        ax.set_xlabel("tempo (ms)")
        ax.set_ylabel("tensão (V)")
        ax.legend(fontsize=8, frameon=False, loc="lower right")
        G.limpar(ax)
    return _salvar(fig, caminho, dpi)
