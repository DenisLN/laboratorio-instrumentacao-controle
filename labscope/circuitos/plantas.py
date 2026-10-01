"""Plantas passivas do roteiro: divisor entre uma impedância série e o capacitor."""
import math
from abc import abstractmethod
from dataclasses import dataclass, replace

from .. import modelo
from .blocos import Bloco, indutor, resistor, serie
from .ft import FT


class Planta(Bloco):
    """Saída no capacitor C. `carga` é uma resistência em paralelo com ele e
    `esr` a resistência série dele; a subclasse define a impedância série."""
    nome = "?"
    C: float
    carga: float
    esr: float

    @abstractmethod
    def z_serie(self) -> FT:
        ...

    def ft(self):
        return FT(*modelo.divisor(self.z_serie().num, self.C, self.carga, self.esr))

    def com_carga(self, R):
        return replace(self, carga=R)


@dataclass(frozen=True)
class PlantaRC(Planta):
    """G = 1/(R₁C·s + 1)."""
    R1: float
    C: float
    carga: float = math.inf
    esr: float = 0.0
    nome = "RC"

    def z_serie(self):
        return resistor(self.R1)


@dataclass(frozen=True)
class PlantaRLC(Planta):
    """G = 1/(LC·s² + R₁C·s + 1). `r_bobina` soma a resistência do indutor a R₁."""
    R1: float
    L: float
    C: float
    carga: float = math.inf
    esr: float = 0.0
    r_bobina: float = 0.0
    nome = "RLC"

    def z_serie(self):
        return serie(indutor(self.L), resistor(self.R1 + self.r_bobina))
