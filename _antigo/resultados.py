"""Calcula as tabelas (experimental x teórico), identifica C efetivo e ganhos,
e gera as figuras do relatório. Saída: tabelas.json + figs/*.png"""
import json, math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import analise as A

CASOS = [c for c in A.CASOS if c[1] != 4e3]          # 22/23 ("4k") descartadas
COR = ["#2a78d6", "#eb6834", "#1baf7a"]               # slots 1-3 da paleta de referência
CINZA = "#8a8984"
plt.rcParams.update({"font.family": "Times New Roman", "font.size": 10,
                     "axes.edgecolor": "#b5b4ae", "axes.labelcolor": "#2b2a27",
                     "xtick.color": "#52514e", "ytick.color": "#52514e"})


def com(caso, **kw):
    """Cópia do caso com R2/R1 trocados; C é global em A."""
    p, R2, R1, pl, ct, caps = caso
    return (p, kw.get("R2", R2), kw.get("R1", R1), pl, ct, caps)


def suavizar(y, dt):
    k = max(1, int(round(60e-6 / dt)))
    return np.convolve(y, np.ones(k) / k, mode="same") if k > 1 else y


def medir_bordas(t, vin, y, ordem1):
    """Métricas em todas as bordas (descidas espelhadas) com meio período completo."""
    s = vin > 0
    b = np.where(s[1:] != s[:-1])[0] + 1
    res = []
    for i, j in zip(b[:-1], b[1:]):
        sinal = 1 if s[i] else -1
        seg, ts = sinal * y[i:j], t[i:j] - t[i]
        y0 = np.mean(sinal * y[max(0, i - 3):i + 1])
        yf = np.mean(seg[-max(3, len(seg) // 20):])
        d = yf - y0
        if d <= 0:
            continue
        fr = (seg - y0) / d
        def cruz(f):
            k = int(np.argmax(fr >= f))
            return ts[k] if fr[k] >= f else math.nan
        kp = int(np.argmax(seg))
        fora = np.where(np.abs(seg - yf) > 0.02 * d)[0]
        acomodou = len(fora) and fora[-1] < 0.9 * len(seg)
        res.append(dict(tau=cruz(0.632), tr=(cruz(0.9) - cruz(0.1)) if ordem1 else cruz(1.0),
                        tp=ts[kp], mp=max(0.0, (seg[kp] - yf) / d),
                        ts=ts[fora[-1] + 1] if acomodou else math.nan,
                        vc=yf, semi=ts[-1]))
    out = {k: float(np.nanmean([r[k] for r in res])) if not all(math.isnan(r[k]) for r in res) else math.nan
           for k in res[0]}
    out["n"] = len(res)
    return out


def degrau_teorico(caso, ordem1):
    """Métricas da resposta ao degrau unitário exata da FT de malha fechada."""
    num, den, *_ = A.polys(caso)
    polos = np.roots(den)
    tfim = 12 / min(abs(polos.real))
    dt = tfim / 60000
    t = np.arange(0, tfim, dt)
    y = A.simular(num, den, np.ones_like(t), dt)
    yf = num[-1] / den[-1]
    fr = y / yf
    cruz = lambda f: t[int(np.argmax(fr >= f))]
    fora = np.where(np.abs(y - yf) > 0.02 * yf)[0]
    kp = int(np.argmax(y))
    return dict(tau=cruz(0.632), tr=(cruz(0.9) - cruz(0.1)) if ordem1 else cruz(1.0),
                tp=t[kp], mp=max(0.0, (y[kp] - yf) / yf), ts=t[fora[-1] + 1], dc=yf)


def zeta_mp(mp):
    l = math.log(mp)
    return -l / math.sqrt(math.pi ** 2 + l ** 2)


def custo_modelo(caso, capturas, C=None, RL=0.0, kp=None, ki=None):
    """Erro quadrático médio entre CH2 e o modelo (C, resistência série extra, ganhos)."""
    C0, R0, CF0 = A.C, A.R, A.CF
    A.C = C or C0
    p, R2, R1, pl, ct, caps = caso
    R2m = kp * A.R if kp is not None else R2
    if ki is not None:
        A.CF = 1 / (A.R * ki)
    cm = (p, R2m, R1 + RL, pl, ct, caps)
    e = 0
    for t, v1, v2 in capturas:
        _, _, y = A.resposta_teorica(cm, t, v1, n_aquec=6)
        e += np.mean((y - v2) ** 2)
    A.C, A.CF = C0, CF0
    return e / len(capturas)


def minimizar(f, x0, passos, iters=40):
    """Busca por coordenadas simples (sem scipy)."""
    x = list(x0); fx = f(x); passos = list(passos)
    for _ in range(iters):
        melhorou = False
        for i in range(len(x)):
            for sgn in (1, -1):
                xn = list(x); xn[i] = x[i] + sgn * passos[i]
                if xn[i] <= 0:
                    continue
                fn = f(xn)
                if fn < fx:
                    x, fx, melhorou = xn, fn, True
                    break
        if not melhorou:
            passos = [p / 2 for p in passos]
            if max(p / abs(v) for p, v in zip(passos, x)) < 2e-3:
                break
    return x, fx


def main():
    dados = {n: A.ler_captura(n) for c in CASOS for n in c[5]}
    # ---------- identificação do C efetivo (parte 3: 1ª ordem, só depende de R1*C)
    caps3 = [dados[n] for c in CASOS if c[0] == 3 for n in c[5][:1]]
    f3 = lambda x: sum(custo_modelo(c, [dados[c[5][0]]], C=x[0] * 1e-6) for c in CASOS if c[0] == 3)
    (C_ef,), _ = minimizar(f3, [4.0], [0.5])
    C_ef *= 1e-6
    # resistência série da bobina (parte 4, com C_ef fixo)
    f4 = lambda x: sum(custo_modelo(c, [dados[c[5][0]]], C=C_ef, RL=x[0]) for c in CASOS if c[0] == 4)
    (RL_ef,), _ = minimizar(f4, [50.0], [25.0])
    print(f"C efetivo = {C_ef*1e6:.2f} uF ; R série extra (bobina) = {RL_ef:.0f} ohm")

    tabelas = dict(C_ef=C_ef, RL_ef=RL_ef, casos=[])
    for caso in CASOS:
        p, R2, R1, pl, ct, caps = caso
        ordem1 = pl == "RC" and ct == "P"
        teo = A.teoria_analitica(caso)
        exp = [medir_bordas(dados[n][0], dados[n][1],
                            suavizar(dados[n][2], np.median(np.diff(dados[n][0]))), ordem1)
               for n in caps]
        m = {k: float(np.nanmean([e[k] for e in exp])) if not all(math.isnan(e[k]) for e in exp) else math.nan
             for k in exp[0] if k != "n"}
        amp = float(np.mean([np.median(dados[n][1][dados[n][1] > 0]) for n in caps]))
        freq = float(np.mean([1 / A.quadrada_ideal(dados[n][0], dados[n][1])[2] for n in caps]))
        # teoria (nominal)
        if ordem1:
            tau = teo["tau"]
            th = dict(tau=tau, tr=2.2 * tau, ts=4 * tau)
        elif ct == "P":                          # 2ª ordem pura: fórmulas clássicas
            z, wn, wd = teo["zeta"], teo["wn"], teo["wd"]
            th = dict(tr=(math.pi - math.acos(z)) / wd, tp=math.pi / wd,
                      mp=math.exp(-z * math.pi / math.sqrt(1 - z * z)), ts=4 / (z * wn))
        else:                                    # PI: resposta exata da FT (zero / 3ª ordem)
            th = degrau_teorico(caso, False)
        th["vc"] = 0.5 * teo["ganho_dc"]
        # experimental: zeta, wn, wd a partir de Mp e Tp
        if not ordem1:
            z = zeta_mp(m["mp"]); wd = math.pi / m["tp"]; wn = wd / math.sqrt(1 - z * z)
            m.update(zeta=z, wn=wn, wd=wd)
        m["ess"] = (amp - m["vc"]) / amp
        th["ess"] = 1 - teo["ganho_dc"]
        # ganhos identificados
        if ct == "P":
            m["kp_dc"] = m["vc"] / (amp - m["vc"])
        (kp_id, *ki_id), _ = minimizar(
            (lambda x: custo_modelo(caso, [dados[n] for n in caps], C=C_ef, RL=RL_ef if pl == "RLC" else 0,
                                    kp=x[0], ki=x[1] * 1e4)) if ct == "PI" else
            (lambda x: custo_modelo(caso, [dados[n] for n in caps], C=C_ef, RL=RL_ef if pl == "RLC" else 0, kp=x[0])),
            [R2 / A.R, 1.0] if ct == "PI" else [R2 / A.R], [0.1, 0.1] if ct == "PI" else [0.1])
        m["kp_id"] = kp_id
        if ki_id:
            m["ki_id"] = ki_id[0] * 1e4
        # modelo com C efetivo (para a figura e para a comparação)
        A.C = C_ef
        casoC = com(caso, R1=R1 + (RL_ef if pl == "RLC" else 0))
        teoC = A.teoria_analitica(casoC)
        A.C = 1e-6
        tabelas["casos"].append(dict(parte=p, R2=R2, R1=R1, planta=pl, ctrl=ct, caps=caps, amp=amp, freq=freq,
                                     exp=m, teo=th, polos=[[z.real, z.imag] for z in teo["polos"]],
                                     polos_C=[[z.real, z.imag] for z in teoC["polos"]],
                                     kp=teo["kp"], ki=teo["ki"], zeta=teo.get("zeta"), wn=teo.get("wn"),
                                     wd=teo.get("wd"), tau=teo.get("tau"), num=teo["num"], den=teo["den"]))
        print(p, R2, {k: round(v, 5) for k, v in m.items()})
        print("   teo", {k: round(v, 5) for k, v in th.items()})
    json.dump(tabelas, open("tabelas.json", "w"), indent=1)
    figuras(tabelas, dados)


# ---------------------------------------------------------------- figuras
TITULO = {3: "Parte 3 – RC com controlador P", 4: "Parte 4 – RLC com controlador P",
          5: "Parte 5 – RC com controlador PI", 6: "Parte 6 – RLC com controlador PI"}


def figuras(tab, dados):
    import os
    os.makedirs("figs", exist_ok=True)
    for parte in (3, 4, 5, 6):
        casos = [c for c in CASOS if c[0] == parte]
        fig, axs = plt.subplots(2, 1, figsize=(7.0, 7.4), sharex=True)
        for ax, C, rot in ((axs[0], 1e-6, "teórico nominal (C = 1 µF)"),
                           (axs[1], tab["C_ef"], f"modelo com C efetivo = {tab['C_ef']*1e6:.1f} µF")):
            xmax = 0
            for k, caso in enumerate(casos):
                n = caso[5][0]
                t, v1, v2 = dados[n]
                s = v1 > 0
                b = np.where(s[1:] != s[:-1])[0] + 1
                i = next(i for i in b if s[i] and i > 20)
                j = next((jj for jj in b if jj > i), len(t) - 1)
                i0 = max(0, i - int(1e-3 / np.median(np.diff(t))))
                tt = (t[i0:j] - t[i]) * 1e3
                A.C = C
                cm = com(caso, R1=caso[2] + (tab["RL_ef"] if caso[3] == "RLC" and C != 1e-6 else 0))
                _, u, y = A.resposta_teorica(cm, t, v1)
                A.C = 1e-6
                lab = f"R2 = {caso[1]/1e3:g} kΩ"
                if k == 0:
                    ax.plot(tt, v1[i0:j], color=CINZA, lw=1.2, label="entrada e1(t) (CH1)")
                ax.plot(tt, v2[i0:j], color=COR[k], lw=1.4, label=f"{lab} – experimental")
                ax.plot(tt, y[i0:j], color=COR[k], lw=1.4, ls=(0, (4, 2)), label=f"{lab} – {'teórico' if C == 1e-6 else 'modelo'}")
                xmax = max(xmax, tt[-1])
            ax.set_title(rot, fontsize=10, loc="left", color="#2b2a27")
            ax.set_ylabel("tensão (V)")
            ax.grid(color="#e6e5e0", lw=0.6); ax.set_axisbelow(True)
            for sp in ("top", "right"):
                ax.spines[sp].set_visible(False)
            ax.set_xlim(-1, xmax)
        axs[1].set_xlabel("tempo após a borda de subida (ms)")
        axs[0].legend(fontsize=8, ncol=2, frameon=False, loc="lower right")
        fig.suptitle(TITULO[parte] + ": entrada, saídas experimentais e teóricas", fontsize=11, x=0.02, ha="left")
        fig.tight_layout()
        fig.savefig(f"figs/resposta_parte{parte}.png", dpi=200)
        plt.close(fig)
        lugar_raizes(parte, casos, tab)


def lugar_raizes(parte, casos, tab):
    c0 = casos[0]
    R1, pl, ct = c0[2], c0[3], c0[4]
    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    for C, estilo, rot in ((1e-6, "-", "nominal (C = 1 µF)"), (tab["C_ef"], ":", f"C efetivo {tab['C_ef']*1e6:.1f} µF")):
        A.C = C
        R1m = R1 + (tab["RL_ef"] if pl == "RLC" and C != 1e-6 else 0)
        kps = np.concatenate([np.linspace(0, 5, 400), np.linspace(5, 60, 200)])
        ramos = []
        for kp in kps:
            num, den, *_ = A.polys((parte, kp * A.R if kp > 0 else 1e-9, R1m, pl, ct, []))
            ramos.append(np.sort_complex(np.roots(den)))
        ramos = np.array(ramos)
        pts = ramos.ravel()
        ax.scatter(pts.real, pts.imag, s=1.2, color="#52514e" if C == 1e-6 else "#b5b4ae",
                   label=f"lugar das raízes – {rot}", zorder=1)
        A.C = 1e-6
    for k, caso in enumerate(casos):
        cc = next(c for c in tab["casos"] if c["parte"] == parte and c["R2"] == caso[1])
        pp = np.array(cc["polos"]); pc = np.array(cc["polos_C"])
        ax.plot(pp[:, 0], pp[:, 1], "x", color=COR[k], ms=9, mew=2, label=f"R2 = {caso[1]/1e3:g} kΩ – teórico")
        ax.plot(pc[:, 0], pc[:, 1], "o", mfc="none", color=COR[k], ms=8, mew=1.6, label=f"R2 = {caso[1]/1e3:g} kΩ – C efetivo")
        e = cc["exp"]
        if "zeta" in e:
            s = -e["zeta"] * e["wn"]
            ax.plot([s, s], [e["wd"], -e["wd"]], "s", color=COR[k], ms=6, label=f"R2 = {caso[1]/1e3:g} kΩ – experimental")
        else:
            ax.plot([-1 / e["tau"]], [0], "s", color=COR[k], ms=6, label=f"R2 = {caso[1]/1e3:g} kΩ – experimental")
    ax.axhline(0, color="#b5b4ae", lw=0.6); ax.axvline(0, color="#b5b4ae", lw=0.6)
    ax.set_xlabel("Re(s)  [1/s]"); ax.set_ylabel("Im(s)  [rad/s]")
    ax.grid(color="#e6e5e0", lw=0.6); ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    todos = np.array([p for c in tab["casos"] if c["parte"] == parte for p in c["polos"] + c["polos_C"]])
    xr = min(todos[:, 0].min() * 1.3, -500); yr = max(abs(todos[:, 1]).max() * 1.3, 500)
    ax.set_xlim(xr, -xr * 0.08); ax.set_ylim(-yr, yr)
    ax.legend(fontsize=7, frameon=False, loc="center left", bbox_to_anchor=(1.0, 0.5))
    ax.set_title(TITULO[parte] + ": lugar das raízes (variando Kp)", fontsize=11, loc="left")
    fig.tight_layout()
    fig.savefig(f"figs/lgr_parte{parte}.png", dpi=200)
    plt.close(fig)


if __name__ == "__main__":
    main()
