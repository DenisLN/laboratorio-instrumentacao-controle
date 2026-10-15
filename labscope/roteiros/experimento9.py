"""Experimento 9 (TE333): controle de sistemas com perturbações.

Usa o motor identificado no Experimento 8 (K, Kt, τ, K1). Cada linha é um
controlador montado na bancada e a resposta ao degrau de referência vista no
osciloscópio: Vt(t), com τ, T_r, T_p, M_p e T_s. Os controladores são os de
`labscope.motor.projeto`: PI de velocidade e PD (ou PID) de posição, sem carga e
com a carga resistiva no gerador a Vg = 6 V e 9 V (velocidade) ou 5 V e 8 V (posição).
"""
from dataclasses import dataclass

from .base import Roteiro, Tabela, texto_si


@dataclass(frozen=True)
class CasoControle:
    id: str            # "tabela.linha", ex.: "3.2"
    tabela: int
    rotulo: str        # "PI, Vg = 9 V"
    malha: str         # "pi" (velocidade) ou "pd" (posição)
    vg: float          # tensão do gerador com a carga ligada [V]; 0 sem carga

    @property
    def carga(self):
        return self.vg > 0

    @property
    def descricao(self):
        grandeza = "velocidade (1000 rpm)" if self.malha == "pi" else "posição (60°)"
        return f"{grandeza}, " + (f"com carga, Vg = {texto_si(self.vg, 'V')}" if self.carga else "sem carga")


class Experimento9(Roteiro):
    numero = 9
    titulo = "Controle de Sistemas com Perturbações"
    familia = "controle"
    frequencia = 0.0               # o degrau de referência é manual (fonte ou gerador de funções)
    referencia_rpm = 1000.0
    fator_tr = 0.85                # T_r 15 % menor que em malha aberta
    referencia_graus = 60.0
    mp = 0.20
    reducao = 30.0                 # CE110: mostrador de posição depois da engrenagem 30:1
    v_por_grau = 0.1               # V/°: ganho do sensor de posição (só muda a escala da tela)
    # linhas: (tabela, malha, [Vg das linhas])
    _LINHAS = ((1, "pi", (0.0,)), (2, "pd", (0.0,)), (3, "pi", (6.0, 9.0)), (4, "pd", (5.0, 8.0)))
    _TITULOS = {1: "Motor CC sem carga: PI de velocidade (1000 rpm)",
                2: "Motor CC sem carga: PD/PID de posição (60°)",
                3: "Motor CC com carga: PI de velocidade (1000 rpm)",
                4: "Motor CC com carga: PD/PID de posição (60°)"}

    def casos(self):
        out = []
        for tabela, malha, vgs in self._LINHAS:
            for k, vg in enumerate(vgs, 1):
                nome = {"pi": "PI", "pd": "PD/PID"}[malha]
                rotulo = f"{nome}, Vg = {texto_si(vg, 'V')}" if vg else f"{nome}, sem carga"
                out.append(CasoControle(f"{tabela}.{k}", tabela, rotulo, malha, vg))
        return out

    def tabelas(self):
        return [Tabela(t, self._TITULOS[t], ("tau", "tr", "tp", "mp", "ts"),
                       tuple(f"{t}.{k}" for k in range(1, len(vgs) + 1))) for t, _, vgs in self._LINHAS]
