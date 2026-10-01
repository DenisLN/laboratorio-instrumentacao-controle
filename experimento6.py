"""Experimento 6 (TE333) – controladores P e PI sobre plantas RC e RLC.

Malha: e1 -> [somador: e = e1 - Vc] -> Gc(s) -> planta G(s) -> Vc
  P : Gc = Kp,            Kp = R2/R
  PI: Gc = Kp + Ki/s,     Ki = 1/(R*Cf)
  RC : G = 1/(R1 C s + 1)
  RLC: G = 1/(L C s^2 + R1 C s + 1)
CH1 = e1 (onda quadrada de 1 Vpp), CH2 = Vc.

Uso:  python experimento6.py [pasta das capturas]
Saída: tabelas.json, tabelas.md e figs/*.png
"""
import argparse
import json
import math
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import numpy as np

from labscope import ajuste, metricas, modelo, sinais, tek
from labscope import graficos as G
from labscope import relatorio as Rl

DADOS = Path(r"E:\NEW_FOLHHH")


@dataclass(frozen=True)
class Comp:
    R: float = 10e3
    C: float = 1e-6
    L: float = 68e-3          # medido na bancada; o roteiro indica 77 mH
    CF: float = 10e-9
    R1k: float = 1e3          # valor efetivo do resistor R1 de 1 kΩ (Partes 3, 5 e 6)
    RL: float = 0.0           # resistência série extra no ramo da bobina
    esr: float = 0.0          # resistência série do capacitor
    carga: float = math.inf   # resistência em paralelo com C


@dataclass(frozen=True)
class Caso:
    parte: int
    R2: float
    R1: float
    planta: str     # "RC" ou "RLC"
    ctrl: str       # "P" ou "PI"
    caps: tuple     # números das capturas ALLnnnn

    @property
    def ordem1(self):
        return self.planta == "RC" and self.ctrl == "P"


# As capturas 22/23 (R2 anotado como "4k") foram descartadas: CH2 fica em ~0 V no
# semiciclo negativo e tem picos de ±4 V nas bordas.
CASOS = [
    Caso(3, 5e3, 1e3, "RC", "P", (0, 1)),
    Caso(3, 10e3, 1e3, "RC", "P", (2, 3)),
    Caso(3, 20e3, 1e3, "RC", "P", (4, 5)),
    Caso(4, 5e3, 100, "RLC", "P", (10, 11)),
    Caso(4, 10e3, 100, "RLC", "P", (8, 9)),
    Caso(4, 20e3, 100, "RLC", "P", (6, 7)),
    Caso(5, 5e3, 1e3, "RC", "PI", (16, 17)),
    Caso(5, 10e3, 1e3, "RC", "PI", (14, 15)),
    Caso(5, 20e3, 1e3, "RC", "PI", (12, 13)),     # o roteiro pede 40k; foi medido com 20k
    Caso(6, 5e3, 1e3, "RLC", "PI", (18, 19)),
    Caso(6, 10e3, 1e3, "RLC", "PI", (20, 21)),
    Caso(6, 40e3, 1e3, "RLC", "PI", (24, 25)),
]
TITULO = {3: "Parte 3 – RC com controlador P", 4: "Parte 4 – RLC com controlador P",
          5: "Parte 5 – RC com controlador PI", 6: "Parte 6 – RLC com controlador PI"}


# ---------------------------------------------------------------- modelo
def planta(caso, comp):
    r1 = comp.R1k if caso.R1 == 1e3 else caso.R1
    if caso.planta == "RC":
        return modelo.rc(r1, comp.C, comp.carga, comp.esr)
    return modelo.rlc(r1 + comp.RL, comp.L, comp.C, comp.carga, comp.esr)


def ft(caso, comp, kp=None, ki=None):
    """FT de malha fechada Vc/E1 do caso; kp e ki sobrepõem os dos componentes."""
    kp = caso.R2 / comp.R if kp is None else kp
    ki = 1 / (comp.R * comp.CF) if ki is None else ki
    gc = modelo.pi(kp, ki) if caso.ctrl == "PI" else modelo.p(kp)
    return modelo.malha_fechada(*modelo.serie(gc, planta(caso, comp)))


def teorico(caso, comp):
    """Métricas previstas: fórmulas de 1ª ordem e de 2ª ordem padrão onde valem;
    com PI (zero e/ou 3ª ordem), a resposta ao degrau exata."""
    num, den = ft(caso, comp)
    dom = modelo.dominante(modelo.polos(den))
    if caso.ordem1:
        th = metricas.primeira_ordem(dom["tau"])
    elif caso.ctrl == "P":
        th = metricas.segunda_ordem(dom["zeta"], dom["wn"])
    else:
        th = modelo.metricas_degrau(num, den)
    dc = modelo.ganho_dc(num, den)
    th.update(vc=0.5 * dc, ess=1 - dc)
    return th


# ---------------------------------------------------------------- medidas
def formas(dados, caps):
    return [(dados[n].t, dados[n]["CH1"], dados[n]["CH2"]) for n in caps]


def medir(dados, caso):
    """Métricas experimentais: média das bordas das capturas do caso, com média
    móvel de 60 µs no CH2. Nos casos oscilatórios traz ζ, ω_n e ω_d pelo método
    do roteiro (de Mp e Tp) e, em `dl`, pelo decremento logarítmico."""
    por_cap, osc = [], []
    for n in caso.caps:
        cap = dados[n]
        y = sinais.media_movel(cap["CH2"], cap.dt, 60e-6)
        por_cap.append(metricas.medir_degraus(cap.t, cap["CH1"], y, "10-90" if caso.ordem1 else "0-100"))
        if not caso.ordem1:
            # com ação integral o valor final é o próprio patamar da entrada
            osc.append(metricas.medir_oscilacao(cap.t, cap["CH1"], y, 1.0 if caso.ctrl == "PI" else None,
                                                minimo=2 * sinais.lsb(cap["CH2"])))
    m = metricas.media(por_cap)
    m["vc"] = m.pop("yf")
    del m["n"]
    if not caso.ordem1:
        z = metricas.zeta_de_mp(m["mp"])
        wd = math.pi / m["tp"]
        m.update(zeta=z, wn=wd / math.sqrt(1 - z * z), wd=wd)
        osc = [o for o in osc if o]
        m["dl"] = metricas.media(osc) if osc else None
    return m


def _erro(dados, casos, parte, comp):
    return sum(ajuste.erro_quadratico(ft(c, comp), formas(dados, c.caps)) for c in casos if c.parte == parte)


def identificar(dados, casos, comp):
    """Componentes que as formas de onda fixam, ancorados no L medido. Cada
    parte acrescenta um bloco e a Parte 6 fica de fora, como validação.

    Devolve (base, final): `base` tem a carga de R sobre o capacitor, C e a
    resistência série extra (Parte 4) e o resistor de 1 kΩ efetivo (Parte 3);
    `final` soma o Ki comum e a ESR do capacitor (Parte 5).
    """
    comp = replace(comp, carga=comp.R)      # o inversor da realimentação carrega Vc com R
    (c_uF, rl), _ = ajuste.minimizar(lambda x: _erro(dados, casos, 4, replace(comp, C=x[0] * 1e-6, RL=x[1])),
                                     [4.0, 20.0], [0.5, 10.0])
    comp = replace(comp, C=c_uF * 1e-6, RL=rl)
    (r1k,), _ = ajuste.minimizar(lambda x: _erro(dados, casos, 3, replace(comp, R1k=x[0] * 1e3)), [1.0], [0.1])
    base = replace(comp, R1k=r1k * 1e3)
    (ki, esr), _ = ajuste.minimizar(
        lambda x: _erro(dados, casos, 5, replace(base, CF=1 / (comp.R * x[0] * 1e4), esr=x[1])),
        [1.0, 3.0], [0.1, 1.0])
    # no ramo RLC a ESR já estava contada dentro da resistência série extra
    return base, replace(base, CF=1 / (comp.R * ki * 1e4), esr=esr, RL=max(rl - esr, 0.0))


def identificar_com_r1_nominal(dados, casos, comp):
    """Leitura alternativa dos mesmos dados: R1 = 1 kΩ exato, C pela Parte 3 e
    L (com a resistência série) pela Parte 4."""
    comp = replace(comp, carga=comp.R)
    (c_uF,), _ = ajuste.minimizar(lambda x: _erro(dados, casos, 3, replace(comp, C=x[0] * 1e-6)), [4.0], [0.5])
    comp = replace(comp, C=c_uF * 1e-6)
    (l_mH, rl), _ = ajuste.minimizar(lambda x: _erro(dados, casos, 4, replace(comp, L=x[0] * 1e-3, RL=x[1])),
                                     [70.0, 20.0], [5.0, 10.0])
    return replace(comp, L=l_mH * 1e-3, RL=rl)


def ganhos(dados, caso, comp):
    """Kp (e Ki no PI) que melhor reproduzem as formas de onda do caso."""
    f = formas(dados, caso.caps)
    if caso.ctrl == "PI":
        (kp, ki), _ = ajuste.minimizar(lambda x: ajuste.erro_quadratico(ft(caso, comp, x[0], x[1] * 1e4), f),
                                       [caso.R2 / comp.R, 1.0], [0.1, 0.1])
        return kp, ki * 1e4
    (kp,), _ = ajuste.minimizar(lambda x: ajuste.erro_quadratico(ft(caso, comp, x[0]), f),
                                [caso.R2 / comp.R], [0.1])
    return kp, None


def analisar(dados, casos=CASOS, nominal=Comp()):
    base, final = identificar(dados, casos, nominal)
    par = lambda z: [[float(r.real), float(r.imag)] for r in z]
    rms = lambda caso, *a: 1e3 * math.sqrt(ajuste.erro_quadratico(ft(caso, *a), formas(dados, caso.caps)))
    tab = dict(nominal=asdict(nominal), planta=asdict(base), final=asdict(final),
               r1_nominal=asdict(identificar_com_r1_nominal(dados, casos, nominal)), casos=[])
    for caso in casos:
        num, den = ft(caso, nominal)
        dom = modelo.dominante(modelo.polos(den))
        m, th = medir(dados, caso), teorico(caso, nominal)
        q = [sinais.quadrada(dados[n].t, dados[n]["CH1"]) for n in caso.caps]
        amp = float(np.mean([x.amplitude for x in q]))
        m["ess"] = (amp - m["vc"]) / amp
        if caso.ctrl == "P":
            m["k_dc"] = m["vc"] / (amp - m["vc"])       # Kp·G(0) visto pelo regime
        m["kp_id"], ki = ganhos(dados, caso, base)
        if ki is not None:
            m["ki_id"] = ki
        tab["casos"].append(dict(
            parte=caso.parte, R2=caso.R2, R1=caso.R1, planta=caso.planta, ctrl=caso.ctrl, caps=list(caso.caps),
            amp=amp, freq=float(np.mean([x.frequencia for x in q])),
            lsb=float(np.mean([sinais.lsb(dados[n]["CH2"]) for n in caso.caps])), exp=m, teo=th,
            polos=par(modelo.polos(den)), polos_id=par(modelo.polos(ft(caso, final)[1])),
            g0=modelo.ganho_dc(*planta(caso, final)),
            kp=caso.R2 / nominal.R, ki=1 / (nominal.R * nominal.CF) if caso.ctrl == "PI" else 0.0,
            zeta=dom.get("zeta"), wn=dom.get("wn"), wd=dom.get("wd"), tau=dom.get("tau"),
            num=list(map(float, num)), den=list(map(float, den)),
            rms=dict(nominal=rms(caso, nominal), planta=rms(caso, base), final=rms(caso, final),
                     ganhos=rms(caso, base, m["kp_id"], ki))))
    return tab


def carregar(raiz, casos=CASOS):
    return {n: tek.ler(raiz, n) for c in casos for n in c.caps}


# ---------------------------------------------------------------- tabelas
def _r2(c):
    return f"R₂ = {c['R2'] / 1e3:g} kΩ"


def _ts(c):
    ts = c["exp"]["ts"]
    return f"> {c['exp']['semi'] * 1e3:.0f} ms" if math.isnan(ts) else Rl.ms(ts, 1)


def _e6(x):
    return Rl.num(x / 1e6, 2) + "·10⁶"


def tabelas_md(tab):
    nom, pl, fim, alt = tab["nominal"], tab["planta"], tab["final"], tab["r1_nominal"]
    parte = lambda p: [c for c in tab["casos"] if c["parte"] == p]
    b = ["## Identificação (âncora: L medido)", Rl.tabela(
        ["Componente", "Nominal", "Identificado", "Origem"],
        [["C", "1 µF", Rl.num(pl["C"] * 1e6, 2, "µF"), "Parte 4 (ω_n), com L = 68 mH"],
         ["R série extra no ramo RLC", "0", Rl.num(pl["RL"], 1, "Ω"), "Parte 4 (σ); inclui bobina e ESR"],
         ["R₁ de 1 kΩ", "1,00 kΩ", Rl.num(pl["R1k"] / 1e3, 3, "kΩ"), "Parte 3 (τ); só R₁·C é observável"],
         ["K_i = 1/(R·C_f)", "10 000 s⁻¹", Rl.num(1 / (fim["R"] * fim["CF"]), 0, "s⁻¹"), "Parte 5"],
         ["ESR do capacitor", "0", Rl.num(fim["esr"], 1, "Ω"), "Parte 5 (amortecimento a mais)"],
         ["Carga sobre C", "∞", "10 kΩ", "esquema (resistor R do inversor)"]]),
         "## Duas leituras dos mesmos dados", Rl.tabela(
        ["Âncora", "C", "L", "R₁ (1 kΩ)", "R série extra", "R₁·C", "L·C"],
        [["L = 68 mH (medido)", Rl.num(pl["C"] * 1e6, 2, "µF"), "68 mH", Rl.num(pl["R1k"] / 1e3, 2, "kΩ"),
          Rl.num(pl["RL"], 1, "Ω"), Rl.ms(pl["R1k"] * pl["C"]), Rl.num(pl["L"] * pl["C"] * 1e7, 2) + "·10⁻⁷ s²"],
         ["R₁ = 1,00 kΩ (nominal)", Rl.num(alt["C"] * 1e6, 2, "µF"), Rl.num(alt["L"] * 1e3, 1, "mH"), "1,00 kΩ",
          Rl.num(alt["RL"], 1, "Ω"), Rl.ms(alt["R1k"] * alt["C"]), Rl.num(alt["L"] * alt["C"] * 1e7, 2) + "·10⁻⁷ s²"]]),
         "## Resíduo RMS entre CH2 e cada modelo (mV)", Rl.tabela(
        ["Caso", "LSB", "Teórico nominal", "Planta identificada", "+ K_i comum e ESR", "Ganhos ajustados por caso"],
        [[f"Parte {c['parte']}, {_r2(c)}", Rl.num(c["lsb"] * 1e3, 0)] +
         [Rl.num(c["rms"][k], 1) for k in ("nominal", "planta", "final", "ganhos")] for c in tab["casos"]])]

    b += ["## Parte 3", "Tabela 1", Rl.tabela(
        ["C = 1 µF, R₁ = 1 kΩ", "τ exp", "τ teo", "T_r exp", "T_r teo", "T_s exp", "T_s teo", "V_c exp", "V_c teo"],
        [[_r2(c), Rl.ms(c["exp"]["tau"]), Rl.ms(c["teo"]["tau"]), Rl.ms(c["exp"]["tr"]), Rl.ms(c["teo"]["tr"]),
          _ts(c), Rl.ms(c["teo"]["ts"]), Rl.num(c["exp"]["vc"], 3, "V"), Rl.num(c["teo"]["vc"], 3, "V")]
         for c in parte(3)])]
    for p in (3, 4):
        b += [f"Regime, Parte {p}", Rl.tabela(
            ["R₂", "e_ss teo", "e_ss exp", "K_p teo", "K = V_c/(A − V_c)", "G(0) do modelo", "K_p = K/G(0)", "K_p do ajuste"],
            [[f"{c['R2'] / 1e3:g} kΩ", Rl.pct(c["teo"]["ess"]), Rl.pct(c["exp"]["ess"]), Rl.num(c["kp"]),
              Rl.num(c["exp"]["k_dc"], 3), Rl.num(c["g0"], 3),
              Rl.num(c["exp"]["k_dc"] / c["g0"], 2), Rl.num(c["exp"]["kp_id"], 2)] for c in parte(p)])]
    b += ["Polos, Parte 3", Rl.tabela(
        ["R₂", "teórico", "experimental (−1/τ)", "modelo identificado"],
        [[f"{c['R2'] / 1e3:g} kΩ", Rl.num(c["polos"][0][0], 0), Rl.num(-1 / c["exp"]["tau"], 0),
          Rl.num(max(q[0] for q in c["polos_id"]), 0)] for c in parte(3)])]

    for p, nome in ((4, "Tabela 2"), (5, "Tabela 4"), (6, "Tabela 6")):
        b += [f"## Parte {p}", nome, Rl.tabela(
            ["", "T_r exp", "T_r teo", "T_p exp", "T_p teo", "M_p exp", "M_p teo", "T_s exp", "T_s teo", "V_c exp", "V_c teo"],
            [[_r2(c) + (f" ({c['freq']:.0f} Hz)" if p == 6 else ""),
              Rl.ms(c["exp"]["tr"]), Rl.ms(c["teo"]["tr"]), Rl.ms(c["exp"]["tp"]), Rl.ms(c["teo"]["tp"]),
              Rl.pct(c["exp"]["mp"]), Rl.pct(c["teo"]["mp"]), _ts(c), Rl.ms(c["teo"]["ts"], 1),
              Rl.num(c["exp"]["vc"], 3, "V"), Rl.num(c["teo"]["vc"], 3, "V")] for c in parte(p)])]
        dl = lambda c, k, casas: Rl.num(c["exp"]["dl"][k], casas) if c["exp"]["dl"] else "–"
        b += [f"Tabela {p - 1 if p == 4 else p}" if p != 6 else "Tabela 7", Rl.tabela(
            ["", "ζ exp", "ζ decr.", "ζ teo", "ω_n exp", "ω_n decr.", "ω_n teo", "ω_d exp", "ω_d decr.", "ω_d teo",
             "σ decr.", "σ teo"],
            [[_r2(c), Rl.num(c["exp"]["zeta"], 3), dl(c, "zeta", 3), Rl.num(c["zeta"], 3),
              Rl.num(c["exp"]["wn"], 0), dl(c, "wn", 0), Rl.num(c["wn"], 0),
              Rl.num(c["exp"]["wd"], 0), dl(c, "wd", 0), Rl.num(c["wd"], 0),
              dl(c, "sigma", 0), Rl.num(c["zeta"] * c["wn"], 0)] for c in parte(p)])]
        if p == 4:
            b += ["FTs, Parte 4", Rl.tabela(
                ["R₂", "T_exp(s)", "T_teo(s)"],
                [[f"{c['R2'] / 1e3:g} kΩ",
                  f"{_e6(c['exp']['vc'] / c['amp'] * c['exp']['wn'] ** 2)} / (s² + "
                  f"{Rl.num(2 * c['exp']['zeta'] * c['exp']['wn'], 0)} s + {_e6(c['exp']['wn'] ** 2)})",
                  f"{_e6(c['num'][0] / c['den'][0])} / (s² + {Rl.num(c['den'][1] / c['den'][0], 0)} s + "
                  f"{_e6(c['den'][2] / c['den'][0])})"] for c in parte(4)])]
        else:
            b += [f"Ganhos, Parte {p}", Rl.tabela(
                ["R₂", "e_ss exp", "K_p teo", "K_p ajuste", "K_i teo", "K_i ajuste"],
                [[f"{c['R2'] / 1e3:g} kΩ", Rl.pct(c["exp"]["ess"]), Rl.num(c["kp"]), Rl.num(c["exp"]["kp_id"]),
                  "10 000", Rl.num(c["exp"]["ki_id"], 0)] for c in parte(p)])]
        polo = lambda q: (Rl.num(q[0], 0) if abs(q[1]) < 1e-6 else
                          f"{Rl.num(q[0], 0)} ± j{Rl.num(abs(q[1]), 0)}")
        lista = lambda pol: "; ".join(dict.fromkeys(polo(q) for q in sorted(pol, key=lambda q: q[0])))
        b += [f"Polos, Parte {p}", Rl.tabela(
            ["R₂", "K_p", "teóricos", "modelo identificado"],
            [[f"{c['R2'] / 1e3:g} kΩ", Rl.num(c["kp"], 1), lista(c["polos"]), lista(c["polos_id"])] for c in parte(p)])]
    return "\n\n".join(b) + "\n"


# ---------------------------------------------------------------- figuras
def figuras(tab, dados, pasta="figs"):
    Path(pasta).mkdir(exist_ok=True)
    nom, fim = Comp(**tab["nominal"]), Comp(**tab["final"])
    paineis = ((nom, "teórico", f"teórico nominal (C = 1 µF, L = {nom.L * 1e3:g} mH)"),
               (fim, "modelo", f"modelo identificado (C = {Rl.num(fim.C * 1e6, 1)} µF, carga de 10 kΩ, ESR)"))
    for parte in (3, 4, 5, 6):
        casos = [c for c in CASOS if c.parte == parte]
        fig, axs = G.plt.subplots(2, 1, figsize=(7.0, 7.4), sharex=True)
        for ax, comp, rot_mod, titulo in ((axs[0], *paineis[0]), (axs[1], *paineis[1])):
            curvas = []
            for caso in casos:
                cap = dados[caso.caps[0]]
                i0, i, j = sinais.janela_subida(cap.t, cap["CH1"])
                _, y = modelo.resposta_periodica(*ft(caso, comp), cap.t, cap["CH1"])
                tt = (cap.t[i0:j] - cap.t[i]) * 1e3
                if not curvas:
                    entrada = (tt, cap["CH1"][i0:j], "entrada e1(t) (CH1)")
                curvas.append((tt, cap["CH2"][i0:j], y[i0:j], f"R2 = {caso.R2 / 1e3:g} kΩ", rot_mod))
            G.respostas(ax, entrada, curvas, titulo)
            ax.set_xlim(-1, max(c[0][-1] for c in curvas))
        axs[1].set_xlabel("tempo após a borda de subida (ms)")
        axs[0].legend(fontsize=8, ncol=2, frameon=False, loc="lower right")
        fig.suptitle(TITULO[parte] + ": entrada, saídas experimentais e teóricas", fontsize=11, x=0.02, ha="left")
        G.salvar(fig, f"{pasta}/resposta_parte{parte}.png")

        kps = np.concatenate([np.linspace(0, 5, 400), np.linspace(5, 60, 200)])
        ramos = [(modelo.lugar_raizes(lambda k: ft(casos[0], comp, kp=k)[1], kps), "lugar das raízes – " + rot, cor)
                 for comp, rot, cor in ((nom, "nominal", "#52514e"), (fim, "modelo identificado", "#b5b4ae"))]
        marcas = []
        for k, caso in enumerate(casos):
            c = next(c for c in tab["casos"] if c["parte"] == parte and c["R2"] == caso.R2)
            rot = f"R2 = {caso.R2 / 1e3:g} kΩ"
            cplx = lambda pol: np.array([complex(*q) for q in pol])
            marcas.append((cplx(c["polos"]), rot + " – teórico", k, "x"))
            marcas.append((cplx(c["polos_id"]), rot + " – modelo", k, "o"))
            e = c["exp"]
            if caso.ordem1:
                exp = [-1 / e["tau"]]
            else:
                d = e["dl"] or dict(sigma=e["zeta"] * e["wn"], wd=e["wd"])
                exp = [complex(-d["sigma"], d["wd"]), complex(-d["sigma"], -d["wd"])]
            marcas.append((np.array(exp), rot + " – experimental", k, "s"))
        fig, ax = G.plt.subplots(figsize=(7.0, 4.0))
        G.lugar_raizes(ax, ramos, marcas, TITULO[parte] + ": lugar das raízes (variando Kp)")
        G.salvar(fig, f"{pasta}/lgr_parte{parte}.png")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pasta", nargs="?", default=DADOS, type=Path)
    args = ap.parse_args()
    dados = carregar(args.pasta)
    tab = analisar(dados)
    json.dump(tab, open("tabelas.json", "w"), indent=1)
    Path("tabelas.md").write_text(tabelas_md(tab), encoding="utf-8")
    figuras(tab, dados)
    print(tabelas_md(tab))


if __name__ == "__main__":
    main()
