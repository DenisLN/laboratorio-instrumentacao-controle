"""Figuras do Experimento 8: painel de uma partida, retas de mínimos quadrados,
partidas de uma tabela e as respostas simuladas dos controladores."""
import math

import numpy as np

from .. import graficos as G
from .painel import _MONO

plt = G.plt


def _salvar(fig, caminho, dpi):
    try:
        G.salvar(fig, caminho, dpi)
    finally:
        plt.close(fig)
    return caminho


def _janela(res):
    """(início, fim) em amostras: um pouco antes da partida até 6 τ depois (ou o fim)."""
    m = res.medida
    i, j = m.janela
    n = int(6 * m.tau / res.captura.dt) if m.tau > 0 else j - i
    return max(0, i - max(5, n // 12)), min(j, i + n)


def partida(res, caminho, dpi=130):
    """CH1, CH2 cru e suavizado, a exponencial medida e a tabela de valores."""
    m, cap = res.medida, res.captura
    d = m.degrau
    a, b = _janela(res)
    t0 = d["t0"]
    tt = (m.t[a:b] - t0) * 1e3
    fig = plt.figure(figsize=(13.5, 6.4))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.45, 1], wspace=0.1)
    ax = fig.add_subplot(gs[0, 0])
    if m.u is not None:
        ax.plot(tt, np.asarray(m.u)[a:b], color=G.CINZA, lw=1.2, label="Va (CH1)")
    ax.plot(tt, m.bruto[a:b], color=G.CORES[0], lw=0.6, alpha=0.3)
    ax.plot(tt, m.y[a:b], color=G.CORES[0], lw=1.6, label=f"{'V′t' if res.caso.carga else 'Vt'} medido (CH2)")
    ax.plot(tt, m.curva(m.t[a:b]), color=G.CORES[1], lw=1.4, ls=G.TRACEJADO, label="1ª ordem com τ e Vt medidos")
    y63 = d["y0"] + (1 - math.exp(-1)) * d["passo"]
    ax.axhline(y63, color="#52514e", lw=0.7, ls=":")
    ax.axvline(d["tau"] * 1e3, color="#52514e", lw=0.7, ls=":")
    ax.annotate(f"τ = {d['tau'] * 1e3:.0f} ms".replace(".", ","), (d["tau"] * 1e3, y63), xytext=(4, -14),
                textcoords="offset points", fontsize=9, color="#52514e")
    ax.set_xlim(tt[0], tt[-1])
    ax.set_xlabel("tempo após Va subir (ms)" if m.tem_entrada else "tempo após o início estimado da partida (ms)")
    ax.set_ylabel("tensão (V)")
    ax.legend(fontsize=9, frameon=False, loc="lower right")
    G.limpar(ax)
    at = fig.add_subplot(gs[0, 1])
    at.axis("off")
    texto = "\n".join(res.linhas_texto() + [""] + [f"! {x}" for x in res.avisos])
    at.text(0.0, 1.0, texto, transform=at.transAxes, va="top", ha="left", family=_MONO, fontsize=8.2, linespacing=1.5,
            wrap=True)
    fig.suptitle(f"#{res.numero:02d}  {res.titulo()}", fontsize=11, x=0.01, ha="left")
    fig.text(0.01, 0.01, f"{res.quando}   {cap.origem}   {res.captura_texto()}", fontsize=7, color="#52514e")
    fig.subplots_adjust(left=0.06, right=0.985, top=0.9, bottom=0.1)
    try:
        fig.savefig(caminho, dpi=dpi)
    finally:
        plt.close(fig)
    return caminho


def _reta(ax, reta, xlabel, ylabel, nome, unidade, escala_x=1.0, escala_y=1.0):
    if reta is None:
        ax.text(0.5, 0.5, "faltam pontos", transform=ax.transAxes, ha="center", color=G.CINZA)
    else:
        x, y = np.array(reta.x), np.array(reta.y)
        xs = np.linspace(0, x.max() * 1.05, 50)
        ax.plot(x * escala_x, y * escala_y, "o", color=G.CORES[0], ms=5, label="medido")
        rot = f"{nome} = {reta.a:.4g} {unidade}   (R² = {reta.r2:.4f})".replace(".", ",")
        ax.plot(xs * escala_x, reta(xs) * escala_y, color=G.CORES[1], lw=1.3, label=rot)
        for k, (xi, yi) in enumerate(zip(x, y)):
            ax.annotate(reta.ids[k], (xi * escala_x, yi * escala_y), xytext=(3, -9), textcoords="offset points",
                        fontsize=7, color=G.CINZA)
        ax.legend(fontsize=8, frameon=False, loc="upper left")
        ax.set_xlim(0, None)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    G.limpar(ax)


def retas(ident, caminho, dpi=150):
    """Os três gráficos da seção 3 (Vt × Va, ω × Va, Vt × ω) e τ de cada linha."""
    fig, axs = plt.subplots(2, 2, figsize=(11.5, 8.0))
    _reta(axs[0, 0], ident.kkt, "Va (V)", "Vt (V)", "KKt", "V/V")
    _reta(axs[0, 1], ident.k, "Va (V)", "ω (rpm)", "K", "rpm/V")
    _reta(axs[1, 0], ident.kt, "ω (rpm)", "Vt (V)", "Kt", "V/rpm")
    ax = axs[1, 1]
    if ident.taus:
        ids = sorted(ident.taus, key=lambda k: int(k.split(".")[1]))
        x = [int(k.split(".")[1]) for k in ids]
        ax.plot(x, [ident.taus[k] * 1e3 for k in ids], "o", color=G.CORES[0], ms=5, label="medido")
        ax.axhline(ident.tau * 1e3, color=G.CORES[1], lw=1.3,
                   label=f"média = {ident.tau * 1e3:.0f} ms".replace(".", ","))
        ax.legend(fontsize=8, frameon=False, loc="lower right")
        ax.set_ylim(0, 1.15 * max(ident.taus.values()) * 1e3)
    ax.set_xlabel("Va (V)")
    ax.set_ylabel("τ (ms)")
    G.limpar(ax)
    fig.suptitle("Exp. 8 · Tabela 1 – motor sem carga: retas de mínimos quadrados", fontsize=11, x=0.01, ha="left")
    return _salvar(fig, caminho, dpi)


def carga(ident, leituras, caminho, dpi=150):
    """V1t × ig (seção 4) e Vt, V't contra Va."""
    fig, axs = plt.subplots(1, 2, figsize=(11.5, 4.4))
    _reta(axs[0], ident.k1kt, "ig (mA)", "V1t = Vt − V′t (V)", "K1Kt", "V/A", escala_x=1e3)
    ax = axs[1]
    pts = sorted((l["va"], l["vt"], l["vtc"]) for k, l in leituras.items() if k.startswith("2.") and l.tem("vtc"))
    if pts:
        va, vt, vtc = map(np.array, zip(*pts))
        ax.plot(va, vt, "o-", color=G.CORES[0], ms=4, lw=1, label="Vt (sem carga)")
        ax.plot(va, vtc, "s-", color=G.CORES[2], ms=4, lw=1, label="V′t (com carga)")
        ax.legend(fontsize=8, frameon=False, loc="upper left")
    ax.set_xlabel("Va (V)")
    ax.set_ylabel("tensão do tacômetro (V)")
    G.limpar(ax)
    fig.suptitle("Exp. 8 · Tabela 2 – motor com carga", fontsize=11, x=0.01, ha="left")
    return _salvar(fig, caminho, dpi)


def partidas(resultados, caminho, dpi=140):
    """Uma partida por painel, cada uma com a própria escala de tempo."""
    n = len(resultados)
    col = 2 if n > 1 else 1
    lin = math.ceil(n / col)
    fig, axs = plt.subplots(lin, col, figsize=(11.5, 2.3 * lin + 0.6), squeeze=False)
    for ax, res in zip(axs.flat, resultados):
        m = res.medida
        a, b = _janela(res)
        tt = (m.t[a:b] - m.degrau["t0"]) * 1e3
        ax.plot(tt, m.y[a:b], color=G.CORES[0], lw=1.4)
        ax.plot(tt, m.curva(m.t[a:b]), color=G.CORES[1], lw=1.2, ls=G.TRACEJADO)
        ax.set_title(f"{res.caso.rotulo}  (#{res.numero:02d})   τ = {m.tau * 1e3:.0f} ms".replace(".", ","),
                     fontsize=9, loc="left")
        ax.set_xlim(tt[0], tt[-1])
        G.limpar(ax)
    for ax in list(axs.flat)[n:]:
        ax.axis("off")
    fig.supxlabel("tempo após a partida (ms)", fontsize=10)
    fig.supylabel("V′t (V)" if resultados[0].caso.carga else "Vt (V)", fontsize=10)
    fig.suptitle(f"Exp. 8 · Tabela {resultados[0].caso.tabela}: medido (cheio) e 1ª ordem com τ medido (tracejado)",
                 fontsize=11, x=0.01, ha="left")
    return _salvar(fig, caminho, dpi)


def projeto(projetos, caminho, dpi=150):
    """Velocidade e posição simuladas, sem carga e com a carga entrando no meio."""
    paineis = [("pi", "Velocidade sem carga"), ("pd", "Posição sem carga"), ("pi_carga", "Velocidade com carga"),
               ("pd_carga", "Posição com carga")]
    fig, axs = plt.subplots(2, 2, figsize=(12.0, 7.6))
    for ax, (chave, titulo) in zip(axs.flat, paineis):
        p = projetos.get(chave)
        if p is None:
            ax.text(0.5, 0.5, "falta K1 (Tabela 2)", transform=ax.transAxes, ha="center", color=G.CINZA)
            ax.axis("off")
            continue
        q = projetos.get("pid_carga") if chave == "pd_carga" else None
        if q is not None:       # PD e PID na mesma linha do tempo: a do PID, que demora mais a se recuperar
            t_carga, tfim = q.duracao()
            s, sq = p.simular(t_carga=t_carga, tfim=tfim), q.simular(t_carga=t_carga, tfim=tfim)
        else:
            s = p.simular()
        ax.plot(s["t"], s["ref"], color=G.CINZA, lw=1.0, ls=G.TRACEJADO, label="referência")
        ax.plot(s["t"], s["y"], color=G.CORES[0], lw=1.6, label=f"{p.nome.split()[0]}: {p.ganhos_texto()}")
        if chave.startswith("pi"):
            ax.plot(s["t"], p.malha_aberta(s["t"], s["t_carga"]), color=G.CINZA, lw=1.2,
                    label="malha aberta (Va = ref/K)")
        if q is not None:
            ax.plot(sq["t"], sq["y"], color=G.CORES[2], lw=1.6, label=f"PID: {q.ganhos_texto()}")
        if not math.isnan(s["t_carga"]):
            ax.axvline(s["t_carga"], color="#52514e", lw=0.7, ls=":")
            ax.annotate(f"carga: ig = {p.ig * 1e3:.0f} mA", (s["t_carga"], 1.0), xycoords=("data", "axes fraction"),
                        xytext=(3, -10), textcoords="offset points", fontsize=8, color="#52514e")
        # sinal de controle no eixo da direita, com o limite do amp-op
        av = ax.twinx()
        av.plot(s["t"], p.sinal_controle(s), color=G.CORES[3], lw=0.9, alpha=0.8)
        for lim in (p.vmax, -p.vmax):
            av.axhline(lim, color=G.CORES[3], lw=0.6, ls=":")
        av.set_ylabel("sinal de controle Va (V)", color=G.CORES[3], fontsize=9)
        av.tick_params(axis="y", colors=G.CORES[3], labelsize=8)
        for lado in ("top", "left"):
            av.spines[lado].set_visible(False)
        ax.set_title(titulo + f"   (pico de Va: {p.pico_controle():.1f} V)".replace(".", ","), fontsize=10, loc="left")
        ax.set_xlabel("tempo (s)")
        ax.set_ylabel(f"{p.grandeza} ({p.unidade})")
        ax.set_xlim(0, s["t"][-1])
        ax.legend(fontsize=7.5, frameon=False, loc="lower right")
        G.limpar(ax)
    fig.suptitle("Exp. 8 · controladores projetados sobre o modelo identificado (simulação)", fontsize=11, x=0.01,
                 ha="left")
    return _salvar(fig, caminho, dpi)
