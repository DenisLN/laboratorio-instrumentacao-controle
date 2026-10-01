"""Blocos de um diagrama de controle e os estágios com amp-op que os realizam.

Todo estágio do roteiro é um amplificador inversor: a entrada (+) no terra, uma
impedância Z_in até a entrada (−) e uma Z_f na realimentação. A subclasse só
diz quais são as duas impedâncias; o ganho −Z_f/Z_in sai daqui.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass

from .ft import FT


# ---------------------------------------------------------------- impedâncias
def resistor(R):
    return FT([R])


def capacitor(C):
    return FT([1.0], [C, 0.0])


def indutor(L):
    return FT([L, 0.0])


def serie(*zs):
    total = zs[0]
    for z in zs[1:]:
        total = total + z
    return total


def paralelo(*zs):
    admitancia = zs[0].inversa()
    for z in zs[1:]:
        admitancia = admitancia + z.inversa()
    return admitancia.inversa()


# ---------------------------------------------------------------- blocos
class Bloco(ABC):
    """Qualquer coisa com uma função de transferência saída/entrada."""

    @abstractmethod
    def ft(self) -> FT:
        ...


class EstagioAmpOp(Bloco):
    """Amplificador inversor com amp-op ideal: V_out/V_in = −Z_f/Z_in."""

    @abstractmethod
    def z_entrada(self) -> FT:
        ...

    @abstractmethod
    def z_realimentacao(self) -> FT:
        ...

    def ft(self):
        return (-(self.z_realimentacao() / self.z_entrada())).normalizada()


@dataclass(frozen=True)
class Somador(EstagioAmpOp):
    """Amp-op 1: três resistores R no nó (−). Cada entrada sai com ganho −1,
    então V₁ = −(e₁ + V₃)."""
    R: float = 10e3

    def z_entrada(self):
        return resistor(self.R)

    def z_realimentacao(self):
        return resistor(self.R)


@dataclass(frozen=True)
class InversorRealimentacao(EstagioAmpOp):
    """Amp-op 3: devolve −V_c ao somador. O resistor de entrada termina em um
    terra virtual, então a planta o enxerga como uma carga R sobre o capacitor."""
    R: float = 10e3

    def z_entrada(self):
        return resistor(self.R)

    def z_realimentacao(self):
        return resistor(self.R)

    @property
    def carga(self):
        return self.R
