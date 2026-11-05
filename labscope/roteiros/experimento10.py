"""Experimento 10 (TE333): compensador avanço de fase.

O compensador usa um amp-op: R1 ∥ C1 na entrada e R2 ∥ C2 na realimentação,
G_c = (R2/R1)·(R1C1·s + 1)/(R2C2·s + 1). A folha tem dois tipos de tabela:

  senoide  1, 2, 4, 7   Vpp da saída e ângulo de fase em regime senoidal
  degrau   3, 5, 6      resposta à onda quadrada de 50 Hz, como nos Exps. 6 e 7

A malha das Figuras 2 e 3 não tem o inversor na realimentação: V_c volta direto
ao somador e o inversor R5/R6 fica entre o compensador e a planta, então
V_c/E₁ = −G_c·G/(1 + G_c·G) e a saída sai invertida em relação à entrada.

A Tabela 4 da folha troca R1 e R2 (390 kΩ e 15 kΩ); aqui vale o circuito das
Figuras 2 e 3 e das Tabelas 3, 5 e 7 (R1 = 15 kΩ, R2 = 390 kΩ).
"""
from dataclasses import asdict, dataclass, fields, replace

from ..circuitos import CompensadorAvanco, Inversor, MalhaFechada, PlantaRC, PlantaRLC
from .base import Roteiro, Tabela, texto_si

_TEMPO = ("tr", "tp", "mp", "ts", "vc")
_MODAL = ("zeta", "wn", "wd")
_SENOIDE = ("vpp", "fase")


@dataclass(frozen=True)
class ComponentesAvanco:
    """Componentes com os nomes da folha do Exp. 10. R é o resistor do somador
    (entrada, realimentação e retorno de V_c); R5/R6 o inversor antes da planta;
    R3/R4 o inversor na saída do compensador em malha aberta (Tabelas 1 e 2)."""
    R: float = 10e3
    R1: float = 15e3
    C1: float = 47e-9
    R2: float = 390e3
    C2: float = 1e-9
    R5: float = 10e3
    R6: float = 10e3
    Rc: float = 1e3
    Cc: float = 1e-6
    L1: float = 77e-3
    R3: float = 10e3
    R4: float = 10e3

    # sem anotação de tipo, de propósito: constantes da classe, não campos
    UNIDADES = {"R": "Ω", "R1": "Ω", "C1": "F", "R2": "Ω", "C2": "F", "R5": "Ω", "R6": "Ω", "Rc": "Ω", "Cc": "F",
                "L1": "H", "R3": "Ω", "R4": "Ω"}
    APELIDOS = {"L": "L1", "C": "Cc"}

    @classmethod
    def chave(cls, nome):
        """Nome do componente na folha, sem diferenciar maiúsculas ('rc' → 'Rc')."""
        nome = cls.APELIDOS.get(nome.strip().upper(), nome.strip())
        achado = next((k for k in cls.UNIDADES if k.upper() == nome.upper()), None)
        if achado is None:
            raise KeyError(f"componente desconhecido: {nome} (use {', '.join(cls.UNIDADES)})")
        return achado

    def trocar(self, **valores):
        return replace(self, **valores)

    def como_dict(self):
        return asdict(self)

    def compensador(self):
        return CompensadorAvanco(self.R1, self.C1, self.R2, self.C2)


assert set(ComponentesAvanco.UNIDADES) == {f.name for f in fields(ComponentesAvanco)}


@dataclass(frozen=True)
class CadeiaAberta:
    """Estágios em cascata, sem realimentação (Tabelas 1 e 2)."""
    estagios: tuple
    nome: str

    def ft(self):
        total = self.estagios[0].ft()
        for e in self.estagios[1:]:
            total = total * e.ft()
        return total.normalizada()

    def polos(self):
        return self.ft().polos()

    def descricao(self):
        return self.nome


_USADOS = {"inversor": ("R3", "R4"), "avanco": ("R1", "C1", "R2", "C2", "R3", "R4"),
           "RC": ("R", "R1", "C1", "R2", "C2", "R5", "R6", "Rc", "Cc"),
           "RLC": ("R", "R1", "C1", "R2", "C2", "R5", "R6", "Rc", "L1", "Cc")}


@dataclass(frozen=True)
class CasoAvanco:
    """Uma linha de tabela: o circuito montado e o sinal do gerador."""
    id: str
    tabela: int
    rotulo: str
    circuito: str           # "inversor", "avanco" (malha aberta), "RC" ou "RLC" (malha fechada)
    comp: ComponentesAvanco
    frequencia: float       # Hz
    amplitude: float        # V de pico
    senoide: bool

    @property
    def planta(self):
        return self.circuito if self.circuito in ("RC", "RLC") else "–"

    @property
    def ctrl(self):
        return "–" if self.circuito == "inversor" else "avanço"

    @property
    def usados(self):
        return _USADOS[self.circuito]

    def malha(self, comp=None, carga=False):
        """O circuito do caso: `MalhaFechada` nas Figuras 2 e 3, `CadeiaAberta` nas Tabelas 1 e 2.
        `carga` liga o R do somador sobre o capacitor da planta (só na malha fechada)."""
        c = comp or self.comp
        saida = Inversor(c.R3, c.R4)
        if self.circuito == "inversor":
            return CadeiaAberta((saida,), "inversor")
        if self.circuito == "avanco":
            return CadeiaAberta((c.compensador(), saida), "avanço + inversor")
        planta = PlantaRC(c.Rc, c.Cc) if self.circuito == "RC" else PlantaRLC(c.Rc, c.L1, c.Cc)
        return MalhaFechada(c.compensador(), planta, c.R, carga, Inversor(c.R5, c.R6))


class Experimento10(Roteiro):
    numero = 10
    titulo = "Compensador Avanço de Fase"
    familia = "avanco"
    frequencia = 50.0          # onda quadrada das Tabelas 3, 5 e 6
    amplitude = 0.5            # 1 Vpp
    frequencias_tabela2 = (20.0, 100.0, 300.0, 1e3, 3e3, 5e3)

    def casos(self):
        aberto = ComponentesAvanco(R1=12e3, C1=1e-6, R2=10e3, C2=100e-9, R3=50e3, R4=10e3)
        fechado = ComponentesAvanco()
        degrau = dict(frequencia=self.frequencia, amplitude=self.amplitude, senoide=False)
        seno_100 = dict(frequencia=100.0, amplitude=0.5, senoide=True)
        return ([CasoAvanco("1.1", 1, "500 Hz", "inversor", ComponentesAvanco(), 500.0, 1.0, True)]
                + [CasoAvanco(f"2.{k}", 2, texto_si(f, "Hz"), "avanco", aberto, f, 1.0, True)
                   for k, f in enumerate(self.frequencias_tabela2, 1)]
                + [CasoAvanco("3.1", 3, "RC, degrau", "RC", fechado, **degrau),
                   CasoAvanco("4.1", 4, "RC, 100 Hz", "RC", fechado, **seno_100),
                   CasoAvanco("5.1", 5, "RLC, degrau", "RLC", fechado, **degrau),
                   CasoAvanco("7.1", 7, "RLC, 100 Hz", "RLC", fechado, **seno_100)])

    def tabelas(self):
        rc = "Cc = 1 µF, Rc = 1 kΩ, C1 = 47 nF, C2 = 1 nF, R1 = 15 kΩ, R2 = 390 kΩ, R = R6 = 10 kΩ"
        rlc = rc.replace("Rc = 1 kΩ", "Rc = 1 kΩ, L1 = 77 mH")
        return [Tabela(1, "Circuito inversor (R3 = R4 = 10 kΩ, senoide de 500 Hz, 2 Vpp)", _SENOIDE, ("1.1",)),
                Tabela(2, "Compensador avanço de fase (C1 = 1 µF, C2 = 100 nF, R1 = 12 kΩ, R2 = 10 kΩ, "
                          "R3 = 50 kΩ, R4 = 10 kΩ, senoide de 2 Vpp)", _SENOIDE,
                       tuple(f"2.{k}" for k in range(1, 7))),
                Tabela(3, f"RC com compensador avanço de fase ({rc})", ("tau", "tr", "ts", "vc"), ("3.1",)),
                Tabela(4, "Avanço de fase, circuito RC (senoide de 100 Hz, 1 Vpp)", _SENOIDE, ("4.1",)),
                Tabela(5, f"RLC com compensador avanço de fase ({rlc})", _TEMPO, ("5.1",)),
                Tabela(6, "RLC com compensador avanço de fase: ζ, ω_n e ω_d", _MODAL, ("5.1",)),
                Tabela(7, "Avanço de fase, circuito RLC (senoide de 100 Hz, 1 Vpp)", _SENOIDE, ("7.1",))]
