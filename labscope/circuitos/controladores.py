"""Controladores P, PI e PID montados no amp-op 2 e o controlador ideal de ganhos dados.

No amp-op 2, G_c(s) = Z_f/Z_in (o sinal do estágio inversor se cancela com o do
somador). Cada controlador só declara as duas impedâncias e, em fórmula
fechada, os ganhos K_p, K_i e K_d que resultam delas.
"""
from abc import abstractmethod
from dataclasses import dataclass

from .blocos import Bloco, EstagioAmpOp, capacitor, paralelo, resistor, serie
from .ft import FT


class Controlador(Bloco):
    """G_c(s) = K_p + K_i/s + K_d·s."""
    nome = "?"

    @property
    @abstractmethod
    def kp(self) -> float:
        ...

    @property
    @abstractmethod
    def ki(self) -> float:
        ...

    @property
    @abstractmethod
    def kd(self) -> float:
        ...

    def gc(self) -> FT:
        if self.ki == 0:
            return FT([self.kd, self.kp])
        return FT([self.kd, self.kp, self.ki], [1.0, 0.0])

    def ft(self):
        """Ganho do estágio, com o sinal de um inversor: −G_c."""
        return -self.gc()

    def ganhos(self):
        return dict(kp=self.kp, ki=self.ki, kd=self.kd)

    @property
    def integral(self):
        return self.ki != 0


@dataclass(frozen=True)
class ControladorIdeal(Controlador):
    """Ganhos dados diretamente (para identificar K_p, K_i e K_d nas medidas)."""
    kp: float = 1.0
    ki: float = 0.0
    kd: float = 0.0
    nome = "ideal"


class ControladorAmpOp(EstagioAmpOp, Controlador):
    """Controlador realizado no amp-op 2, com R na entrada."""

    def gc(self):
        return (self.z_realimentacao() / self.z_entrada()).normalizada()


@dataclass(frozen=True)
class ControladorP(ControladorAmpOp):
    """Z_in = R, Z_f = R₂."""
    R: float
    R2: float
    nome = "P"

    def z_entrada(self):
        return resistor(self.R)

    def z_realimentacao(self):
        return resistor(self.R2)

    kp = property(lambda self: self.R2 / self.R)
    ki = property(lambda self: 0.0)
    kd = property(lambda self: 0.0)


@dataclass(frozen=True)
class ControladorPI(ControladorAmpOp):
    """Z_in = R, Z_f = R₂ em série com C₂ (o C_f do Experimento 6)."""
    R: float
    R2: float
    C2: float
    nome = "PI"

    def z_entrada(self):
        return resistor(self.R)

    def z_realimentacao(self):
        return serie(resistor(self.R2), capacitor(self.C2))

    kp = property(lambda self: self.R2 / self.R)
    ki = property(lambda self: 1 / (self.R * self.C2))
    kd = property(lambda self: 0.0)


@dataclass(frozen=True)
class ControladorPID(ControladorPI):
    """O PI com C₁ em paralelo com o R de entrada: Z_in = R ∥ C₁.

    G_c = (R₂ + 1/(sC₂))·(1/R + sC₁) = (R₂/R + C₁/C₂) + 1/(R·C₂·s) + R₂·C₁·s
    """
    C1: float = 0.0
    nome = "PID"

    def z_entrada(self):
        return paralelo(resistor(self.R), capacitor(self.C1))

    kp = property(lambda self: self.R2 / self.R + self.C1 / self.C2)
    kd = property(lambda self: self.R2 * self.C1)
