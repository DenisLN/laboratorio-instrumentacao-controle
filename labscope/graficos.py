"""Figuras de relatório: respostas no tempo e lugar das raízes."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

CORES = ["#2a78d6", "#eb6834", "#1baf7a", "#8e5bd0"]
CINZA = "#8a8984"
TRACEJADO = (0, (4, 2))

plt.rcParams.update({"font.family": "Times New Roman", "font.size": 10,
                     "axes.edgecolor": "#b5b4ae", "axes.labelcolor": "#2b2a27",
                     "xtick.color": "#52514e", "ytick.color": "#52514e"})


def limpar(ax):
    """Grade clara atrás dos dados e sem as bordas de cima e da direita."""
    ax.grid(color="#e6e5e0", lw=0.6)
    ax.set_axisbelow(True)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)


def respostas(ax, entrada, curvas, titulo=""):
    """Entrada em cinza e, por caso, medido (cheio) e modelo (tracejado).

    entrada: (t_ms, v, rótulo)
    curvas:  [(t_ms, medido, modelo, rótulo, rótulo do modelo), ...]
    """
    t, v, rot = entrada
    ax.plot(t, v, color=CINZA, lw=1.2, label=rot)
    for k, (t, medido, mod, rot, rot_mod) in enumerate(curvas):
        cor = CORES[k % len(CORES)]
        ax.plot(t, medido, color=cor, lw=1.4, label=f"{rot} – experimental")
        ax.plot(t, mod, color=cor, lw=1.4, ls=TRACEJADO, label=f"{rot} – {rot_mod}")
    ax.set_title(titulo, fontsize=10, loc="left", color="#2b2a27")
    ax.set_ylabel("tensão (V)")
    limpar(ax)


def lugar_raizes(ax, ramos, marcas, titulo=""):
    """ramos:  [(raízes para vários ganhos, rótulo, cor), ...]
    marcas: [(polos, rótulo, índice da cor, marcador), ...] com marcador
            "x" (teórico), "o" (modelo) ou "s" (experimental)."""
    for raizes, rot, cor in ramos:
        pts = np.ravel(raizes)
        ax.scatter(pts.real, pts.imag, s=1.2, color=cor, label=rot, zorder=1)
    estilo = {"x": dict(ms=9, mew=2), "o": dict(ms=8, mew=1.6, mfc="none"), "s": dict(ms=6)}
    todos = []
    for pol, rot, k, marcador in marcas:
        pol = np.atleast_1d(pol)
        ax.plot(pol.real, pol.imag, marcador, color=CORES[k % len(CORES)], label=rot, **estilo[marcador])
        todos.extend(pol)
    ax.axhline(0, color="#b5b4ae", lw=0.6)
    ax.axvline(0, color="#b5b4ae", lw=0.6)
    ax.set_xlabel("Re(s)  [1/s]")
    ax.set_ylabel("Im(s)  [rad/s]")
    limpar(ax)
    todos = np.array(todos)
    xr = min(todos.real.min() * 1.3, -500)
    yr = max(abs(todos.imag).max() * 1.3, 500)
    ax.set_xlim(xr, -xr * 0.08)
    ax.set_ylim(-yr, yr)
    ax.legend(fontsize=7, frameon=False, loc="center left", bbox_to_anchor=(1.0, 0.5))
    ax.set_title(titulo, fontsize=11, loc="left")


def salvar(fig, caminho, dpi=200):
    fig.tight_layout()
    fig.savefig(caminho, dpi=dpi)
    plt.close(fig)
