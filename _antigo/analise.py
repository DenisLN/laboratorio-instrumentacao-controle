"""Experimento 6 – análise dos dados do osciloscópio (Tek TBS1052B, pasta ALLxxxx).

Malha: e1 -> [somador: e = e1 - Vc] -> Gc(s) -> planta G(s) -> Vc
  P : Gc = Kp,            Kp = R2/R
  PI: Gc = Kp + Ki/s,     Ki = 1/(R*Cf)
  RC : G = 1/(R1 C s + 1)
  RLC: G = 1/(L C s^2 + R1 C s + 1)
"""
import glob, json, math, sys
from pathlib import Path
import numpy as np

DADOS = Path(r"D:\NEW_FOLHHH")
R, C, L, CF = 10e3, 1e-6, 77e-3, 10e-9

# (parte, R2, R1, planta, controlador, [capturas])
CASOS = [
    (3, 5e3, 1e3, "RC", "P", [0, 1]),
    (3, 10e3, 1e3, "RC", "P", [2, 3]),
    (3, 20e3, 1e3, "RC", "P", [4, 5]),
    (4, 5e3, 100, "RLC", "P", [10, 11]),
    (4, 10e3, 100, "RLC", "P", [8, 9]),
    (4, 20e3, 100, "RLC", "P", [6, 7]),
    (5, 5e3, 1e3, "RC", "PI", [16, 17]),
    (5, 10e3, 1e3, "RC", "PI", [14, 15]),
    (5, 20e3, 1e3, "RC", "PI", [12, 13]),
    (6, 5e3, 1e3, "RLC", "PI", [18, 19]),
    (6, 10e3, 1e3, "RLC", "PI", [20, 21]),
    (6, 4e3, 1e3, "RLC", "PI", [22, 23]),
    (6, 40e3, 1e3, "RLC", "PI", [24, 25]),
]


# ---------------------------------------------------------------- leitura
def ler_canal(path):
    t, v = [], []
    for line in open(path, errors="replace"):
        d = [x.strip() for x in line.split(",") if x.strip()]
        try:
            t.append(float(d[-2])); v.append(float(d[-1]))
        except (ValueError, IndexError):
            pass
    return np.array(t), np.array(v)


def ler_captura(n):
    pasta = DADOS / f"ALL{n:04d}"
    t1, v1 = ler_canal(next(pasta.glob("*CH1.CSV")))
    t2, v2 = ler_canal(next(pasta.glob("*CH2.CSV")))
    comum, i1, i2 = np.intersect1d(np.round(t1, 12), np.round(t2, 12), return_indices=True)
    return comum, v1[i1], v2[i2]


# ---------------------------------------------------------------- modelo
def polys(caso):
    _, R2, R1, planta, ctrl, _ = caso
    kp, ki = R2 / R, 1 / (R * CF)
    gc_n = [kp] if ctrl == "P" else [kp, ki]
    gc_d = [1.0] if ctrl == "P" else [1.0, 0.0]
    g_n = [1.0]
    g_d = [R1 * C, 1.0] if planta == "RC" else [L * C, R1 * C, 1.0]
    num = np.polymul(gc_n, g_n)
    den = np.polyadd(np.polymul(gc_d, g_d), num)
    return num, den, kp, (ki if ctrl == "PI" else 0.0)


def expm(A):
    n = np.linalg.norm(A, 1)
    s = max(0, int(math.ceil(math.log2(n))) + 1) if n > 0 else 0
    A = A / 2 ** s
    X, term = np.eye(len(A)), np.eye(len(A))
    for k in range(1, 20):
        term = term @ A / k
        X = X + term
    for _ in range(s):
        X = X @ X
    return X


def simular(num, den, u, dt):
    """Simulação ZOH de num/den (forma canônica controlável)."""
    den = np.asarray(den, float); num = np.asarray(num, float)
    num = num / den[0]; den = den / den[0]
    n = len(den) - 1
    num = np.concatenate([np.zeros(n + 1 - len(num)), num])
    A = np.zeros((n, n)); A[:-1, 1:] = np.eye(n - 1); A[-1, :] = -den[1:][::-1]
    B = np.zeros(n); B[-1] = 1
    Cm = (num[1:] - num[0] * den[1:])[::-1]
    M = np.zeros((n + 1, n + 1)); M[:n, :n] = A * dt; M[:n, n] = B * dt
    E = expm(M); Ad, Bd = E[:n, :n], E[:n, n]
    x = np.zeros(n); y = np.empty(len(u))
    for k, uk in enumerate(u):
        y[k] = Cm @ x + num[0] * uk
        x = Ad @ x + Bd * uk
    return y


def quadrada_ideal(t, v_in):
    """Reconstrói a onda quadrada ideal (níveis, fase, período) a partir do CH1."""
    hi, lo = np.median(v_in[v_in > 0]), np.median(v_in[v_in < 0])
    s = v_in > 0
    bordas = np.where(s[1:] != s[:-1])[0] + 1
    subidas = t[bordas[s[bordas]]]
    periodo = np.median(np.diff(subidas)) if len(subidas) > 1 else 2 * np.median(np.diff(t[bordas]))
    return hi, lo, periodo, subidas[0] if len(subidas) else t[bordas[0]] - periodo / 2


def resposta_teorica(caso, t, v_in, n_aquec=20):
    num, den, *_ = polys(caso)
    hi, lo, P, t_sub = quadrada_ideal(t, v_in)
    dt = np.median(np.diff(t))
    tt = np.arange(t[0] - n_aquec * P, t[-1] + dt / 2, dt)
    fase = ((tt - t_sub) % P) < P / 2
    u = np.where(fase, hi, lo)
    y = simular(num, den, u, dt)
    return tt[-len(t):], u[-len(t):], y[-len(t):]


# ---------------------------------------------------------------- medidas
def medir(t, vin, y, ordem1):
    """Mede nas bordas de subida do CH1 que tenham meio período completo depois."""
    s = vin > 0
    b = np.where(s[1:] != s[:-1])[0] + 1
    res = []
    for i, j in zip(b[:-1], b[1:]):
        if not s[i]:
            continue  # só subidas
        seg, ts = y[i:j], t[i:j] - t[i]
        y0 = np.mean(y[max(0, i - 3):i + 1])
        yf = np.mean(seg[-max(3, len(seg) // 20):])
        d = yf - y0
        if d <= 0:
            continue
        frac = (seg - y0) / d
        def cruz(f):
            k = np.argmax(frac >= f)
            return ts[k] if frac[k] >= f else float("nan")
        kp = int(np.argmax(seg))
        fora = np.where(np.abs(seg - yf) > 0.02 * d)[0]
        m = dict(
            tau=cruz(0.632),
            tr=(cruz(0.9) - cruz(0.1)) if ordem1 else cruz(1.0),
            tp=ts[kp], mp=max(0.0, (seg[kp] - yf) / d),
            ts=ts[fora[-1] + 1] if len(fora) and fora[-1] + 1 < len(ts) else float("nan"),
            vc=yf, pico=seg[kp], y0=y0)
        res.append(m)
    if not res:
        return None
    return {k: float(np.nanmean([r[k] for r in res])) for k in res[0]}


def teoria_analitica(caso):
    num, den, kp, ki = polys(caso)
    raizes = np.roots(den)
    ganho_dc = num[-1] / den[-1]
    out = dict(kp=kp, ki=ki, polos=[complex(r) for r in raizes], ganho_dc=float(ganho_dc),
               num=list(map(float, num)), den=list(map(float, den)))
    # par dominante (menor |parte real| entre os complexos) para zeta/wn
    cplx = [r for r in raizes if abs(r.imag) > 1e-6]
    if cplx:
        p = max(cplx, key=lambda r: r.real)
        wn = abs(p); z = -p.real / wn
        out.update(zeta=z, wn=wn, wd=abs(p.imag))
    else:
        out.update(tau=float(-1 / max(raizes.real)))
    return out


def zeta_de_mp(mp):
    if mp <= 0:
        return float("nan")
    l = math.log(mp)
    return -l / math.sqrt(math.pi ** 2 + l ** 2)


def main():
    resultados = []
    for caso in CASOS:
        parte, R2, R1, planta, ctrl, caps = caso
        teo = teoria_analitica(caso)
        por_cap = []
        for n in caps:
            t, v1, v2 = ler_captura(n)
            ordem1 = planta == "RC" and ctrl == "P"
            _, u, yt = resposta_teorica(caso, t, v1)
            hi, lo, P, _ = quadrada_ideal(t, v1)
            por_cap.append(dict(cap=n, freq=1 / P, hi=hi, lo=lo, dt=float(np.median(np.diff(t))),
                                exp=medir(t, v1, v2, ordem1), sim=medir(t, u, yt, ordem1)))
        resultados.append(dict(parte=parte, R2=R2, R1=R1, planta=planta, ctrl=ctrl,
                               teoria=teo, capturas=por_cap))
    json.dump(resultados, open("resultados.json", "w"), indent=1, default=lambda c: [c.real, c.imag])
    for r in resultados:
        teo = r["teoria"]
        print(f"\nParte {r['parte']}  R2={r['R2']/1e3:g}k  Kp={teo['kp']:.2f}  DC={teo['ganho_dc']:.3f}  "
              + ("tau=%.3f ms" % (teo['tau'] * 1e3) if 'tau' in teo else
                 "zeta=%.3f wn=%.0f wd=%.0f" % (teo['zeta'], teo['wn'], teo['wd']))
              + "  polos=" + ", ".join(f"{p.real:.0f}{p.imag:+.0f}j" for p in teo["polos"]))
        for c in r["capturas"]:
            for k in ("exp", "sim"):
                m = c[k]
                if m is None:
                    print(f"  ALL{c['cap']:04d} {k}: sem borda completa"); continue
                print(f"  ALL{c['cap']:04d} {c['freq']:.1f}Hz dt={c['dt']*1e6:.0f}us {k}: "
                      f"tau={m['tau']*1e3:.3f} tr={m['tr']*1e3:.3f} tp={m['tp']*1e3:.3f} "
                      f"Mp={m['mp']*100:.1f}% ts={m['ts']*1e3:.2f} Vc={m['vc']:.3f} pico={m['pico']:.3f} y0={m['y0']:.3f}")


if __name__ == "__main__":
    main()
