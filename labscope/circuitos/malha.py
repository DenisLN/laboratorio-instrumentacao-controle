"""A malha do roteiro: somador, controlador, planta e inversor de realimentação."""
from dataclasses import dataclass, replace

import numpy as np

from .. import modelo
from .blocos import InversorRealimentacao, Somador
from .controladores import Controlador
from .ft import FT
from .plantas import Planta


@dataclass(frozen=True)
class MalhaFechada:
    """e₁ → somador → controlador → planta → V_c, com −V_c de volta ao somador.

    `carga_do_inversor` inclui o que o modelo do roteiro ignora: o resistor R
    de entrada do amp-op 3 em paralelo com o capacitor da planta.
    """
    controlador: Controlador
    planta: Planta
    R: float = 10e3
    carga_do_inversor: bool = False

    @property
    def somador(self):
        return Somador(self.R)

    @property
    def inversor(self):
        return InversorRealimentacao(self.R)

    @property
    def planta_efetiva(self):
        return self.planta.com_carga(self.inversor.carga) if self.carga_do_inversor else self.planta

    def direto(self) -> FT:
        """G_c·G: do erro até V_c (os dois estágios inversores se cancelam)."""
        return (self.somador.ft() * self.controlador.ft() * self.planta_efetiva.ft()).normalizada()

    def ft(self) -> FT:
        """V_c/E₁."""
        return self.direto().malha(self.inversor.ft()).normalizada()

    # ------------------------------------------------------------ análise
    def polos(self):
        return self.ft().polos()

    def zeros(self):
        return self.ft().zeros()

    def dominante(self):
        """Par complexo dominante (zeta, wn, wd, sigma) ou tau do polo mais lento."""
        return modelo.dominante(self.polos())

    def estavel(self):
        return bool(np.all(np.real(self.polos()) < 0))

    def routh(self):
        return modelo.routh(self.ft().den)

    def ganho_dc(self):
        return self.ft().ganho_dc()

    def erro_regime(self):
        """e_ss para degrau, como fração da amplitude do degrau."""
        return 1 - self.ganho_dc()

    @property
    def ordem(self):
        return self.ft().ordem

    @property
    def tipo(self):
        return self.direto().tipo

    # ------------------------------------------------------------ variações
    def com_carga(self, ligada=True):
        return replace(self, carga_do_inversor=ligada)

    def com_controlador(self, controlador):
        return replace(self, controlador=controlador)

    def descricao(self):
        return f"{self.planta.nome} + {self.controlador.nome}"
