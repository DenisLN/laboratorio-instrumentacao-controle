"""Experimento 7 (TE333): controlador PID sobre plantas RC e RLC, 10 Hz.

O PID usa um amp-op só: C1 em paralelo com o R de entrada e R2 em série com C2
na realimentação, o que dá K_p = R2/R + C1/C2, K_i = 1/(R·C2) e K_d = R2·C1.
"""
from .base import Componentes, Roteiro, Tabela

_TEMPO = ("tr", "tp", "mp", "ts", "vc")


class Experimento7(Roteiro):
    numero = 7
    titulo = "Controlador Proporcional + Integral + Derivativo (PID)"
    frequencia = 10.0
    nomes = {"R1": "RL", "C": "CL"}

    def casos(self):
        rc = Componentes(R=10e3, R1=1e3, C=1e-6, R2=10e3, C1=10e-9, C2=10e-9)
        rlc = Componentes(R=10e3, R1=10e3, C=1e-6, L=77e-3, R2=10e3, C1=1e-9, C2=100e-9)
        return (self._linhas(1, "RC", "PID", rc, "R2", (1e3, 10e3, 100e3), "Ω")
                + self._linhas(2, "RC", "PID", rc, "C2", (1e-9, 100e-9), "F")
                + self._linhas(3, "RC", "PID", rc, "C1", (1e-9, 100e-9), "F")
                + self._linhas(4, "RLC", "PID", rlc, "R2", (1e3, 10e3, 100e3), "Ω")
                + self._linhas(5, "RLC", "PID", rlc, "C2", (1e-9, 10e-9), "F")
                + self._linhas(6, "RLC", "PID", rlc, "C1", (10e-9, 100e-9), "F"))

    def tabelas(self):
        ids = lambda t, n: tuple(f"{t}.{k}" for k in range(1, n + 1))
        rc, rlc = "RC com PID (CL = 1 µF, RL = 1 kΩ", "RLC com PID (CL = 1 µF, RL = 10 kΩ, L = 77 mH"
        return [Tabela(1, f"{rc}, C2 = 10 nF, C1 = 10 nF)", _TEMPO, ids(1, 3)),
                Tabela(2, f"{rc}, R2 = 10 kΩ, C1 = 10 nF)", _TEMPO, ids(2, 2)),
                Tabela(3, f"{rc}, R2 = 10 kΩ, C2 = 10 nF)", _TEMPO, ids(3, 2)),
                Tabela(4, f"{rlc}, C2 = 100 nF, C1 = 1 nF)", _TEMPO, ids(4, 3)),
                Tabela(5, f"{rlc}, R2 = 10 kΩ, C1 = 1 nF)", _TEMPO, ids(5, 2)),
                Tabela(6, f"{rlc}, R2 = 10 kΩ, C2 = 100 nF)", _TEMPO, ids(6, 2))]
