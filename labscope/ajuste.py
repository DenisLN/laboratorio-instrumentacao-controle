"""Ajuste de parâmetros de um modelo às formas de onda medidas."""
import numpy as np

from . import modelo


def minimizar(f, x0, passos, iters=40, tol=2e-3):
    """Busca por coordenadas com passos que caem pela metade; parâmetros ficam
    positivos. Para quando o passo relativo cai abaixo de `tol`.
    Devolve (x, f(x))."""
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
            if max(p / abs(v) for p, v in zip(passos, x)) < tol:
                break
    return x, fx


def erro_quadratico(ft, capturas, n_aquec=6):
    """Erro quadrático médio entre a saída medida e a de `ft` = (num, den),
    em média sobre `capturas` = [(t, entrada, saída), ...]."""
    e = 0.0
    for t, ref, y in capturas:
        _, ym = modelo.resposta_periodica(*ft, t, ref, n_aquec)
        e += float(np.mean((ym - y) ** 2))
    return e / len(capturas)
