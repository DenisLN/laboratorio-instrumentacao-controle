"""Roteiro de laboratório: os casos a montar e as tabelas a preencher."""
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, replace

from ..circuitos import (ControladorP, ControladorPI, ControladorPID, MalhaFechada, PlantaRC, PlantaRLC)

PREFIXOS = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "m": 1e-3, "k": 1e3, "M": 1e6}


def valor_si(texto):
    """'10k' → 10000.0, '68m' → 0.068, '4,7n' → 4.7e-9."""
    texto = texto.strip().replace(",", ".")
    if texto and texto[-1] in PREFIXOS:
        return float(texto[:-1]) * PREFIXOS[texto[-1]]
    return float(texto)


def texto_si(x, unidade=""):
    """10000.0 → '10 kΩ' (com unidade='Ω')."""
    for prefixo, fator in (("M", 1e6), ("k", 1e3), ("", 1.0), ("m", 1e-3), ("µ", 1e-6), ("n", 1e-9), ("p", 1e-12)):
        if abs(x) >= fator * 0.9999:
            return f"{x / fator:.4g} {prefixo}{unidade}".replace(".", ",")
    return f"{x:g} {unidade}"


@dataclass(frozen=True)
class Componentes:
    """Componentes da malha, com os nomes do Experimento 7 onde eles diferem:
    R1 e C são o resistor e o capacitor da planta (R_L e C_L no Exp. 7) e C2 é o
    capacitor da ação integral (C_f no Exp. 6)."""
    R: float = 10e3
    R2: float = 10e3
    R1: float = 1e3
    C: float = 1e-6
    L: float = 77e-3
    C1: float = 10e-9
    C2: float = 10e-9

    # sem anotação de tipo, de propósito: constantes da classe, não campos
    UNIDADES = {"R": "Ω", "R2": "Ω", "R1": "Ω", "C": "F", "L": "H", "C1": "F", "C2": "F"}
    APELIDOS = {"RL": "R1", "CL": "C", "CF": "C2"}

    @classmethod
    def chave(cls, nome):
        """Nome canônico de um componente, aceitando os apelidos dos roteiros."""
        nome = nome.strip().upper()
        nome = cls.APELIDOS.get(nome, nome)
        if nome not in cls.UNIDADES:
            raise KeyError(f"componente desconhecido: {nome} (use {', '.join(cls.UNIDADES)}, RL, CL ou Cf)")
        return nome

    def trocar(self, **valores):
        return replace(self, **valores)

    def como_dict(self):
        return asdict(self)


_CONTROLADORES = {
    "P": lambda c: ControladorP(c.R, c.R2),
    "PI": lambda c: ControladorPI(c.R, c.R2, c.C2),
    "PID": lambda c: ControladorPID(c.R, c.R2, c.C2, c.C1),
}
_PLANTAS = {
    "RC": lambda c: PlantaRC(c.R1, c.C),
    "RLC": lambda c: PlantaRLC(c.R1, c.L, c.C),
}
_USADOS = {"P": ("R", "R2"), "PI": ("R", "R2", "C2"), "PID": ("R", "R2", "C2", "C1"),
           "RC": ("R1", "C"), "RLC": ("R1", "L", "C")}


@dataclass(frozen=True)
class Caso:
    """Uma linha de tabela do roteiro: um circuito para montar e medir."""
    id: str            # "tabela.linha", ex.: "1.2"
    tabela: int
    rotulo: str        # "R2 = 10 kΩ"
    planta: str        # "RC" ou "RLC"
    ctrl: str          # "P", "PI" ou "PID"
    comp: Componentes

    def malha(self, comp=None, carga=False):
        """Malha fechada do caso; `comp` troca os componentes nominais."""
        comp = comp or self.comp
        return MalhaFechada(_CONTROLADORES[self.ctrl](comp), _PLANTAS[self.planta](comp), comp.R, carga)

    @property
    def usados(self):
        """Componentes que entram neste circuito."""
        return _USADOS[self.ctrl] + _USADOS[self.planta]


@dataclass(frozen=True)
class Tabela:
    numero: int
    titulo: str
    metricas: tuple    # chaves em labscope.medidas.METRICAS
    casos: tuple       # ids dos casos, na ordem das linhas


class Roteiro(ABC):
    """Um experimento: sinal de entrada, casos e tabelas."""
    numero: int
    titulo: str
    frequencia: float          # Hz da onda quadrada
    amplitude: float = 0.5     # V de pico (1 Vpp)
    nomes: dict = {}           # nome canônico -> como o roteiro chama o componente

    @abstractmethod
    def casos(self) -> list:
        ...

    @abstractmethod
    def tabelas(self) -> list:
        ...

    def caso(self, id):
        for c in self.casos():
            if c.id == id:
                return c
        raise KeyError(f"caso {id!r} não existe no Experimento {self.numero} (veja 'casos')")

    def nome(self, chave):
        return self.nomes.get(chave, chave)

    @staticmethod
    def _linhas(tabela, planta, ctrl, base, variavel, valores, unidade):
        """Casos de uma tabela em que só `variavel` muda de linha para linha."""
        return [Caso(f"{tabela}.{k}", tabela, f"{variavel} = {texto_si(v, unidade)}", planta, ctrl,
                     base.trocar(**{Componentes.chave(variavel): v}))
                for k, v in enumerate(valores, 1)]
