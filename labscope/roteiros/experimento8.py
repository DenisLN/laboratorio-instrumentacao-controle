"""Experimento 8 (TE333): controle de motor CC.

Não há circuito para montar: cada linha das tabelas é uma tensão de armadura
Va aplicada ao grupo motor-gerador. Na Tabela 1 (sem carga) se medem Vt, ω e a
constante de tempo; na Tabela 2 (carga resistiva no gerador) se medem ig e V't.
As constantes K, Kt e K1 saem dessas medidas por mínimos quadrados
(`labscope.motor`), e é com elas que os controladores são projetados.
"""
from dataclasses import dataclass

from .base import Roteiro, Tabela, texto_si


@dataclass(frozen=True)
class PontoMotor:
    """Uma linha de tabela do roteiro: uma tensão de armadura, com ou sem carga."""
    id: str            # "tabela.linha", ex.: "1.4"
    tabela: int
    rotulo: str        # "Va = 4 V"
    va: float          # tensão de armadura pedida [V]
    carga: bool        # carga resistiva ligada ao gerador

    @property
    def descricao(self):
        return "motor com carga no gerador" if self.carga else "motor sem carga (ig = 0)"


@dataclass(frozen=True)
class Grandeza:
    """Algo que se lê na bancada (no osciloscópio ou no instrumento) e se anota."""
    chave: str
    simbolo: str
    unidade: str       # como aparece na tela
    escala: float      # SI → unidade da tela
    casas: int
    nome: str


GRANDEZAS = {g.chave: g for g in (
    Grandeza("va", "Va", "V", 1.0, 2, "tensão de armadura"),
    Grandeza("vt", "Vt", "V", 1.0, 3, "tensão do tacômetro sem carga"),
    Grandeza("w", "ω", "rpm", 1.0, 0, "velocidade (tacômetro)"),
    Grandeza("tau", "τ", "ms", 1e3, 1, "constante de tempo"),
    Grandeza("ig", "ig", "mA", 1e3, 1, "corrente do gerador"),
    Grandeza("vtc", "V't", "V", 1.0, 3, "tensão do tacômetro com carga"),
    Grandeza("v1t", "V1t", "V", 1.0, 3, "V1t = Vt − V't"),
)}
# como se pode digitar cada grandeza no prompt (w=1020, vt'=2.5, ig=120m, ...)
APELIDOS = {"va": "va", "vt": "vt", "w": "w", "rpm": "w", "tau": "tau", "τ": "tau", "ig": "ig",
            "vtc": "vtc", "vt'": "vtc", "v't": "vtc", "vtl": "vtc"}
ANOTAVEIS = ("va", "vt", "w", "tau", "ig", "vtc")


def grandeza(nome):
    chave = APELIDOS.get(nome.strip().lower())
    if chave is None:
        raise KeyError(f"grandeza desconhecida: {nome} (use {', '.join(sorted(APELIDOS))})")
    return GRANDEZAS[chave]


class Experimento8(Roteiro):
    numero = 8
    titulo = "Controle de Motor CC"
    familia = "motor"
    frequencia = 0.0               # não há onda quadrada: o degrau é a fonte ligando
    tensoes = tuple(float(v) for v in range(1, 11))
    referencia_rpm = 1000.0        # velocidade de referência do projeto PI
    referencia_graus = 60.0        # posição de referência do projeto PD/PID
    reducao = 30.0                 # CE110 Servo Trainer: o mostrador de posição fica depois da engrenagem 30:1

    def casos(self):
        return [PontoMotor(f"{t}.{k}", t, f"Va = {texto_si(v, 'V')}", v, t == 2)
                for t in (1, 2) for k, v in enumerate(self.tensoes, 1)]

    def tabelas(self):
        ids = lambda t: tuple(f"{t}.{k}" for k in range(1, len(self.tensoes) + 1))
        return [Tabela(1, "Motor CC sem carga (ig = 0)", ("va", "vt", "w", "tau"), ids(1)),
                Tabela(2, "Motor CC com carga no gerador", ("va", "vt", "ig", "vtc", "v1t"), ids(2))]

    def par(self, caso):
        """O caso da outra tabela com a mesma Va (1.4 ↔ 2.4)."""
        return self.caso(f"{3 - caso.tabela}.{caso.id.split('.')[1]}")
