"""Experimento 6 (TE333): controladores P e PI sobre plantas RC e RLC, 50 Hz."""
from .base import Componentes, Roteiro, Tabela

_TEMPO = ("tr", "tp", "mp", "ts", "vc")
_MODAL = ("zeta", "wn", "wd")


class Experimento6(Roteiro):
    numero = 6
    titulo = "Controlador Proporcional e Proporcional + Integral"
    frequencia = 50.0
    nomes = {"C2": "Cf"}

    def casos(self):
        base = Componentes(R=10e3, C=1e-6, L=77e-3, C2=10e-9)
        r1k, r100 = base.trocar(R1=1e3), base.trocar(R1=100.0)
        return (self._linhas(1, "RC", "P", r1k, "R2", (5e3, 10e3, 20e3), "Ω")
                + self._linhas(2, "RLC", "P", r100, "R2", (5e3, 10e3, 20e3), "Ω")
                + self._linhas(4, "RC", "PI", r1k, "R2", (5e3, 10e3, 40e3), "Ω")
                + self._linhas(6, "RLC", "PI", r1k, "R2", (5e3, 10e3, 40e3), "Ω"))

    def tabelas(self):
        ids = lambda t: tuple(f"{t}.{k}" for k in (1, 2, 3))
        return [Tabela(1, "RC com controlador P (C = 1 µF, R1 = 1 kΩ)", ("tau", "tr", "ts", "vc"), ids(1)),
                Tabela(2, "RLC com controlador P (C = 1 µF, L = 77 mH, R1 = 100 Ω)", _TEMPO, ids(2)),
                Tabela(3, "RLC com controlador P: ζ, ω_n e ω_d", _MODAL, ids(2)),
                Tabela(4, "RC com controlador PI (C = 1 µF, R1 = 1 kΩ, Cf = 10 nF)", _TEMPO, ids(4)),
                Tabela(5, "RC com controlador PI: ζ, ω_n e ω_d", _MODAL, ids(4)),
                Tabela(6, "RLC com controlador PI (C = 1 µF, L = 77 mH, R1 = 1 kΩ, Cf = 10 nF)", _TEMPO, ids(6)),
                Tabela(7, "RLC com controlador PI: ζ, ω_n e ω_d", _MODAL, ids(6))]
