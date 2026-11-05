"""Figuras do Experimento 10: a captura senoidal contra o previsto e o Bode com os pontos medidos."""
import textwrap

import numpy as np

from .. import graficos as G
from ..medidas import bode as _bode
from .painel import _MONO

plt = G.plt


def senoide(res, caminho, dpi=130):
    """CH1, CH2 e a saída prevista (na fase da entrada medida), com a tabela ao lado."""
    m = res.medida
    periodos = min(m.periodos, 3.0)
    fim = np.searchsorted(m.t, m.t[0] + periodos / m.frequencia)
    t = m.t[:fim]
    tt = (t - t[0]) * 1e3

    fig = plt.figure(figsize=(13.5, 6.4))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.45, 1], wspace=0.1)
    ax = fig.add_subplot(gs[0, 0])
    ax.plot(tt, m.captura[m.canal_entrada][:fim], color=G.CINZA, lw=1.2, label="entrada (CH1)")
    ax.plot(tt, m.captura[m.canal_saida][:fim], color=G.CORES[0], lw=0.8, alpha=0.45)
    ax.plot(tt, m.curva()[:fim], color=G.CORES[0], lw=1.6, label="saída medida (CH2, senoide ajustada)")
    fase_entrada = m._entrada[1]
    for prev, estilo, cor, rot in ((res.previsto, G.TRACEJADO, G.CORES[1], "teórico"),
                                   (res.previsto_carga, (0, (1, 1.5)), G.CORES[2], "modelo c/ carga")):
        ax.plot(tt, prev.curva(t, fase_entrada) * m.vpp_entrada / (2 * prev.amplitude),
                color=cor, lw=1.4, ls=estilo, label=f"{rot} (mesma entrada)")
    ax.set_xlim(tt[0], tt[-1])
    ax.set_xlabel("tempo (ms)")
    ax.set_ylabel("tensão (V)")
    ax.legend(fontsize=9, frameon=False, loc="lower right")
    G.limpar(ax)

    at = fig.add_subplot(gs[0, 1])
    at.axis("off")
    texto = "\n".join(res.linhas_texto() + ["", res.residuo_texto(), "=> " + res.veredito()]
                      + [f"! {x}" for x in res.avisos])
    at.text(0.0, 1.0, texto, transform=at.transAxes, va="top", ha="left", family=_MONO, fontsize=7.9,
            linespacing=1.5)
    fig.suptitle(f"#{res.numero:02d}  {res.titulo()}\n{res.componentes_texto()}", fontsize=11, x=0.01, ha="left")
    fig.text(0.01, 0.01, f"{res.quando}   {res.captura.origem}   {res.captura_texto()}", fontsize=7, color="#52514e")
    fig.subplots_adjust(left=0.06, right=0.985, top=0.88, bottom=0.1)
    G.salvar(fig, caminho, dpi)
    return caminho


def bode(tabela, casos, previsto, resultados, roteiro, caminho, dpi=160):
    """|G| (dB) e fase do circuito da tabela, com os pontos medidos.

    `previsto` é a lista [(ft, rótulo, estilo)] das curvas teóricas; `resultados`,
    os ResultadoSenoide medidos (pode ser vazia: só o teórico)."""
    fs = [c.frequencia for c in casos]
    f = np.logspace(np.log10(min(fs)) - 1, np.log10(max(fs)) + 1, 400)
    fig, (am, af) = plt.subplots(2, 1, figsize=(8.0, 6.4), sharex=True)
    curvas = []
    for k, (ft, rot, estilo) in enumerate(previsto):
        db, graus = _bode(ft, f)
        graus = graus - 360 * np.round(np.median(graus) / 360)     # o ramo mais perto de 0°
        curvas.append(graus)
        am.semilogx(f, db, color=G.CORES[1 + k], lw=1.5, ls=estilo, label=rot)
        af.semilogx(f, graus, color=G.CORES[1 + k], lw=1.5, ls=estilo)
    if resultados:
        fm = [r.caso.frequencia for r in resultados]
        am.semilogx(fm, [20 * np.log10(r.medida.ganho) for r in resultados], "s", color=G.CORES[0], label="medido")
        # a fase medida vem em (−180°, 180°]: leva cada ponto ao ramo da curva teórica
        perto = [np.interp(np.log(x), np.log(f), curvas[0]) for x in fm]
        af.semilogx(fm, [r.medida.fase + 360 * np.round((c - r.medida.fase) / 360) for r, c in zip(resultados, perto)],
                    "s", color=G.CORES[0])
    am.set_ylabel("|Vsaída/Ventrada| (dB)")
    af.set_ylabel("fase (graus)")
    af.set_xlabel("frequência (Hz)")
    am.legend(fontsize=9, frameon=False)
    for ax in (am, af):
        ax.grid(True, which="both", lw=0.3, alpha=0.5)
        G.limpar(ax)
    am.set_title(textwrap.fill(f"Exp. {roteiro.numero} · Tabela {tabela.numero} – {tabela.titulo}", 95),
                 fontsize=10, loc="left")
    G.salvar(fig, caminho, dpi)
    return caminho

