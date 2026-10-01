"""Figuras da sessão: o painel de uma captura, o gráfico de uma tabela e o lugar das raízes."""
import math
import os
import sys

import numpy as np

from .. import graficos as G
from ..medidas import RespostaTeorica

plt = G.plt
_MONO = "DejaVu Sans Mono"


def abrir(caminho):
    """Abre o arquivo no visualizador padrão do sistema, sem travar a sessão."""
    try:
        if sys.platform == "win32":
            os.startfile(caminho)  # noqa: S606 - arquivo que acabamos de gerar
        else:
            import subprocess
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(caminho)])
    except OSError as exc:
        print(f"(não consegui abrir {caminho}: {exc})")


def _trecho_para_mostrar(medida):
    """Índice do 1º trecho de subida medido (ou do 1º que houver)."""
    validos = [k for k, (i, j, s) in enumerate(medida.trechos)]
    subidas = [k for k in validos if medida.trechos[k][2] > 0]
    return (subidas or validos)[0]


def _janela(res, i, j):
    """(início, fim) em amostras: um pouco antes da borda até o transitório acabar."""
    m, t = res.medida, res.medida.t
    ts = [x for x in (m.degrau["ts"], res.teoria.degrau["ts"], res.teoria_carga.degrau["ts"]) if not math.isnan(x)]
    dur = t[j - 1] - t[i]
    if ts:
        dur = min(dur, max(1.8 * max(ts), 0.15 * dur))
    n = int(dur / res.captura.dt)
    antes = min(i, max(3, n // 12))
    return i - antes, min(i + n, len(t))


def painel(res, caminho, dpi=130):
    """Forma de onda com as curvas dos modelos, a tabela de métricas e os polos."""
    m, cap = res.medida, res.captura
    i, j, s = m.trechos[_trecho_para_mostrar(m)]
    a, b = _janela(res, i, j)
    tt = (m.t[a:b] - m.t[i]) * 1e3

    fig = plt.figure(figsize=(13.5, 7.2))
    gs = fig.add_gridspec(2, 2, width_ratios=[1.4, 1], height_ratios=[1.25, 1], hspace=0.28, wspace=0.12)
    ax = fig.add_subplot(gs[:, 0])
    ax.plot(tt, m.u[a:b], color=G.CINZA, lw=1.2, label="entrada e1 (CH1)")
    ax.plot(tt, cap[m.canal_saida][a:b], color=G.CORES[0], lw=0.7, alpha=0.35)
    ax.plot(tt, m.y[a:b], color=G.CORES[0], lw=1.6, label="Vc medido (CH2)")
    for teoria, estilo, rot in ((res.teoria, G.TRACEJADO, "teórico (roteiro)"),
                                (res.teoria_carga, (0, (1, 1.5)), "modelo c/ carga de 10 kΩ")):
        if teoria.estavel:
            ax.plot(tt, teoria.curva(m.t, m.entrada)[a:b], color=G.CORES[1] if rot[0] == "t" else G.CORES[2],
                    lw=1.5, ls=estilo, label=rot)

    # marcações das métricas medidas neste trecho (em tensão real, não espelhada)
    d = m.por_trecho[min(_trecho_para_mostrar(m), len(m.por_trecho) - 1)]
    y0, yf = s * d["y0"], s * d["yf"]
    ax.axhspan(yf - m.banda * (yf - y0), yf + m.banda * (yf - y0), color=G.CORES[0], alpha=0.10, lw=0)
    for chave, rot in (("tr", "Tr"), ("tp", "Tp"), ("ts", "Ts")):
        x = d[chave]
        if not math.isnan(x) and x * 1e3 <= tt[-1]:
            ax.axvline(x * 1e3, color="#52514e", lw=0.7, ls=":")
            ax.annotate(rot, (x * 1e3, 1.0), xycoords=("data", "axes fraction"), xytext=(2, -11),
                        textcoords="offset points", fontsize=9, color="#52514e")
    ax.set_xlim(tt[0], tt[-1])
    ax.set_xlabel("tempo após a borda (ms)")
    ax.set_ylabel("tensão (V)")
    ax.legend(fontsize=9, frameon=False, loc="lower right")
    G.limpar(ax)

    # tabela de métricas
    at = fig.add_subplot(gs[0, 1])
    at.axis("off")
    texto = "\n".join(res.linhas_texto() + ["", res.residuo_texto().replace(": teórico", ":\n  teórico"),
                                            "=> " + res.veredito().replace(" — ", "\n   ")]
                      + [f"! {x}" for x in res.avisos])
    at.text(0.0, 1.0, texto, transform=at.transAxes, va="top", ha="left", family=_MONO, fontsize=7.9,
            linespacing=1.5)

    # polos dominantes
    ap = fig.add_subplot(gs[1, 1])
    _polos(ap, res)

    fig.suptitle(f"#{res.numero:02d}  {res.titulo()}\n{res.componentes_texto()}     {res.ganhos_texto()}",
                 fontsize=11, x=0.01, ha="left")
    fig.text(0.01, 0.01, f"{res.quando}   {cap.origem}   {res.captura_texto()}", fontsize=7, color="#52514e")
    fig.subplots_adjust(left=0.06, right=0.985, top=0.9, bottom=0.085)
    fig.savefig(caminho, dpi=dpi)
    plt.close(fig)
    return caminho


def _proximos(polos):
    """Descarta polos reais muito mais rápidos que o dominante (achatariam o gráfico)."""
    polos = np.atleast_1d(polos)
    lento = max(abs(polos.real).min(), 1.0)
    return polos[abs(polos.real) <= 25 * lento]


def _experimentais(res):
    osc, d = res.medida.oscilacao, res.medida.degrau
    if osc:
        return np.array([complex(-osc["sigma"], osc["wd"]), complex(-osc["sigma"], -osc["wd"])])
    if res.teoria.ft.ordem == 1 and not math.isnan(d["tau"]):
        return np.array([-1 / d["tau"]])
    return None


def _polos(ax, res):
    marcas = [(_proximos(res.teoria.malha.polos()), "teórico", 1, "x"),
              (_proximos(res.teoria_carga.malha.polos()), "c/ carga", 2, "o")]
    exp = _experimentais(res)
    if exp is not None:
        marcas.append((exp, "experimental", 0, "s"))
    G.lugar_raizes(ax, [], marcas, "Polos dominantes")
    ax.legend(fontsize=8, frameon=False, loc="upper left")


def grafico_tabela(tabela, resultados, caminho, dpi=160):
    """Os casos já medidos de uma tabela no mesmo gráfico: entrada, saídas
    experimentais e saídas teóricas (o que o roteiro pede para esboçar)."""
    fig, ax = plt.subplots(figsize=(8.5, 5.0))
    curvas, entrada = [], None
    # todos até o fim do transitório mais longo (ou até onde a captura de cada um alcança)
    fim = 0.0
    for res in resultados:
        m = res.medida
        i, j, _ = m.trechos[_trecho_para_mostrar(m)]
        a, b = _janela(res, i, j)
        fim = max(fim, (m.t[b - 1] - m.t[i]) * 1e3)
    for res in resultados:
        m = res.medida
        i, j, s = m.trechos[_trecho_para_mostrar(m)]
        a, _ = _janela(res, i, j)
        b = min(j, i + int(fim * 1e-3 / res.captura.dt) + 1)
        tt = (m.t[a:b] - m.t[i]) * 1e3
        if entrada is None:
            entrada = (tt, m.u[a:b], "entrada e1 (CH1)")
        curvas.append((tt, m.y[a:b], res.teoria.curva(m.t, m.entrada)[a:b], res.caso.rotulo, "teórico"))
    G.respostas(ax, entrada, curvas, f"Exp. {resultados[0].roteiro.numero} · Tabela {tabela.numero} – {tabela.titulo}")
    ax.set_xlim(min(c[0][0] for c in curvas), fim)
    ax.set_xlabel("tempo após a borda (ms)")
    ax.legend(fontsize=8, ncol=2, frameon=False, loc="lower right")
    G.salvar(fig, caminho, dpi)
    return caminho


def lugar_das_raizes(res_ou_caso, roteiro, comp, caminho, variavel="R2", dpi=160):
    """Caminho dos polos quando `variavel` (R2 por padrão) varre de 1/20 a 20× o nominal."""
    res = None if hasattr(res_ou_caso, "malha") else res_ou_caso
    caso = res.caso if res else res_ou_caso
    nominal = getattr(comp, variavel)
    valores = nominal * np.logspace(-1.3, 1.3, 500)
    raizes = np.concatenate([_proximos(caso.malha(comp.trocar(**{variavel: v})).polos()) for v in valores])
    teoria, teoria_carga = (RespostaTeorica(caso.malha(comp, carga=c), roteiro.amplitude) for c in (False, True))
    marcas = [(_proximos(teoria.malha.polos()), f"{caso.rotulo} – teórico", 1, "x"),
              (_proximos(teoria_carga.malha.polos()), f"{caso.rotulo} – c/ carga", 2, "o")]
    if res is not None and _experimentais(res) is not None:
        marcas.append((_experimentais(res), f"{caso.rotulo} – experimental", 0, "s"))
    fig, ax = plt.subplots(figsize=(8.0, 4.6))
    G.lugar_raizes(ax, [(raizes, f"lugar das raízes variando {roteiro.nome(variavel)}", "#8a8984")], marcas,
                   f"Exp. {roteiro.numero} · caso {caso.id} ({caso.planta} + {caso.ctrl})")
    G.salvar(fig, caminho, dpi)
    return caminho
