"""Função de transferência como objeto: razão de polinômios em s."""
from dataclasses import dataclass

import numpy as np


def _coef(p):
    p = np.trim_zeros(np.atleast_1d(np.asarray(p, float)), "f")
    return tuple(float(x) for x in p) if len(p) else (0.0,)


def _polinomio(c):
    termos = []
    for k, x in enumerate(c):
        grau = len(c) - 1 - k
        if x == 0 and len(c) > 1:
            continue
        s = "" if grau == 0 else "s" if grau == 1 else f"s^{grau}"
        termos.append(s if (x == 1 and s) else f"{x:.4g} {s}".strip())
    return " + ".join(termos).replace("+ -", "- ")


@dataclass(frozen=True)
class FT:
    """num(s)/den(s), coeficientes do maior grau para o menor. Desempacota como
    o par (num, den) que as funções de `labscope.modelo` esperam: `f(*ft)`.
    Serve também para impedâncias, que são razões de polinômios do mesmo jeito."""
    num: tuple
    den: tuple = (1.0,)

    def __post_init__(self):
        object.__setattr__(self, "num", _coef(self.num))
        object.__setattr__(self, "den", _coef(self.den))
        if self.den == (0.0,):
            raise ZeroDivisionError("denominador nulo")

    def __iter__(self):
        yield np.array(self.num)
        yield np.array(self.den)

    # ------------------------------------------------------------ álgebra
    @staticmethod
    def _de(x):
        return x if isinstance(x, FT) else FT([x])

    def __mul__(self, o):
        o = self._de(o)
        return FT(np.polymul(self.num, o.num), np.polymul(self.den, o.den))

    __rmul__ = __mul__

    def __truediv__(self, o):
        o = self._de(o)
        return FT(np.polymul(self.num, o.den), np.polymul(self.den, o.num))

    def __add__(self, o):
        o = self._de(o)
        if self.den == o.den:
            return FT(np.polyadd(self.num, o.num), self.den)
        return FT(np.polyadd(np.polymul(self.num, o.den), np.polymul(o.num, self.den)),
                  np.polymul(self.den, o.den))

    __radd__ = __add__

    def __neg__(self):
        return FT(-np.array(self.num), self.den)

    def __sub__(self, o):
        return self + (-self._de(o))

    def inversa(self):
        return FT(self.den, self.num)

    def normalizada(self):
        """Mesma FT com o denominador mônico."""
        return FT(np.array(self.num) / self.den[0], np.array(self.den) / self.den[0])

    def malha(self, h=-1.0):
        """Fecha a malha: saída = self·(entrada + h·saída). O padrão h = −1 é a
        realimentação unitária negativa."""
        h = self._de(h)
        return FT(np.polymul(self.num, h.den),
                  np.polysub(np.polymul(self.den, h.den), np.polymul(self.num, h.num)))

    # ------------------------------------------------------------ análise
    @property
    def ordem(self):
        return len(self.den) - 1

    @property
    def tipo(self):
        """Quantos polos na origem (integradores)."""
        return len(self.den) - len(np.trim_zeros(np.array(self.den), "b"))

    def polos(self):
        return np.roots(self.den)

    def zeros(self):
        return np.roots(self.num)

    def ganho_dc(self):
        if self.den[-1] == 0:
            return float(np.copysign(np.inf, self.num[-1] or 1.0))
        return float(self.num[-1] / self.den[-1])

    def __call__(self, s):
        return np.polyval(self.num, s) / np.polyval(self.den, s)

    def __str__(self):
        return f"({_polinomio(self.num)}) / ({_polinomio(self.den)})"
