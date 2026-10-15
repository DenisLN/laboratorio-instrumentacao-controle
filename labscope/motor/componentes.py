"""Valores de resistores e capacitores do controlador analógico a partir de Kp, Ki e Kd.

Todos os estágios têm o somador inversor do roteiro, G_c = Z_f/Z_in (o sinal
negativo do amp-op é compensado pelo detector de erro):

    PI   Z_in = R,         Z_f = R2 + 1/(sC2)    Kp = R2/R               Ki = 1/(R·C2)
    PD   Z_in = R ∥ C1,    Z_f = R2              Kp = R2/R               Kd = R2·C1
    PID  Z_in = R ∥ C1,    Z_f = R2 + 1/(sC2)    Kp = R2/R + C1/C2       Ki = 1/(R·C2)    Kd = R2·C1

No PID, u = R2/R e v = C1/C2 são as raízes de x² − Kp·x + Ki·Kd = 0; existem (reais)
quando Kp² ≥ 4·Ki·Kd.
"""
import math

SERIE_E24 = (1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0, 3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2,
             6.8, 7.5, 8.2, 9.1)
SERIE_CAPACITORES = (1.0, 1.5, 2.2, 3.3, 4.7, 6.8)        # E6, a série comum de capacitores


def comercial(x, serie=SERIE_E24):
    """O valor da série mais próximo de `x` (em escala logarítmica)."""
    if not x or x <= 0 or not math.isfinite(x):
        return math.nan
    dec = 10 ** math.floor(math.log10(x))
    candidatos = [v * dec * f for v in serie for f in (0.1, 1, 10)]
    return min(candidatos, key=lambda c: abs(math.log(c / x)))


def ganhos_eletricos(projeto, v_por_unidade=1.0):
    """Kp, Ki e Kd vistos pelo circuito, em V/V, 1/s e s. No PI o sensor (tacômetro)
    já está dentro de `projeto.ganhos()`; na posição os ganhos são em V/° e o
    sensor ganha `v_por_unidade` V/°, então se divide por ele."""
    g = projeto.ganhos()
    if projeto.sensor != 1.0:
        return dict(g)
    return {k: v / v_por_unidade for k, v in g.items()}


def escolher_c2(ki, r_max=1e6):
    """O menor capacitor de ação integral (E6, de 100 nF a 470 µF) com que R = 1/(Ki·C2) cabe em `r_max`;
    o maior da lista se nem ele chega (Ki muito pequeno)."""
    lista = [v * d for d in (1e-7, 1e-6, 1e-5, 1e-4) for v in SERIE_CAPACITORES if v * d <= 470e-6]
    return next((c for c in lista if 1 / (ki * c) <= r_max), lista[-1]) if ki else 1e-6


def dimensionar(kp, ki, kd, c2=1e-6, r_pd=10e3):
    """Componentes de `ganhos` com o capacitor integral C2 escolhido; PI, PD ou PID
    conforme Ki e Kd sejam nulos. `c2` escolhe a escala do PI/PID e `r_pd`, a do PD. Devolve {'tipo', 'R', 'R2', 'C1', 'C2', 'avisos'}; None
    nos que o tipo não usa."""
    avisos = []
    if ki and kd:
        d = kp * kp - 4 * ki * kd
        if d < 0:
            raise ValueError(f"Kp² < 4·Ki·Kd ({kp:.4g}² < {4 * ki * kd:.4g}): o PID não cabe nesta topologia; "
                             "aumente Kp ou diminua Ki")
        u = (kp + math.sqrt(d)) / 2
        v = (kp - math.sqrt(d)) / 2
        r = 1 / (ki * c2)
        return dict(tipo="PID", R=r, R2=u * r, C1=v * c2, C2=c2, avisos=avisos)
    if ki:
        r = 1 / (ki * c2)
        return dict(tipo="PI", R=r, R2=kp * r, C1=None, C2=c2, avisos=avisos)
    if kd:
        # PD: não há C2; R fixa a escala, R2 = Kp·R e C1 = Kd/R2
        r2 = kp * r_pd
        return dict(tipo="PD", R=r_pd, R2=r2, C1=kd / r2, C2=None, avisos=avisos)
    r = 10e3
    return dict(tipo="P", R=r, R2=kp * r, C1=None, C2=None, avisos=avisos)


def comerciais(c):
    """Os valores de `dimensionar` arredondados para as séries E24 (resistores) e E6 (capacitores), e
    os ganhos que o circuito realmente teria com eles."""
    out = dict(c, avisos=list(c["avisos"]))
    for k in ("R", "R2"):
        out[k] = comercial(c[k])
    for k in ("C1", "C2"):
        out[k] = comercial(c[k], SERIE_CAPACITORES) if c[k] else None
    r, r2, c1, c2 = out["R"], out["R2"], out["C1"], out["C2"]
    kp = r2 / r + (c1 / c2 if c1 and c2 else 0.0)
    ki = 1 / (r * c2) if c2 else 0.0
    kd = r2 * c1 if c1 else 0.0
    out["ganhos"] = dict(kp=kp, ki=ki, kd=kd)
    return out
