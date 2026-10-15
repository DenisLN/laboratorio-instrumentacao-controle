"""Modelo de 1ª ordem do grupo motor-gerador-tacômetro (eq. 2 e 3 da teoria do
Exp. 8) e a identificação das constantes por mínimos quadrados.

    ω(s)  = K/(τs + 1) · Va(s) − K1/(τs + 1) · Ig(s)      [rpm]
    Vt(s) = Kt · ω(s)

Unidades: K em rpm/V, Kt em V/rpm, K1 em rpm/A, τ em s.
"""
import math
from dataclasses import dataclass, field

import numpy as np

from ..circuitos import FT

GRAUS_POR_S_POR_RPM = 6.0      # 1 rpm = 360° / 60 s
NAN = math.nan


@dataclass(frozen=True)
class MotorCC:
    K: float               # rpm/V
    Kt: float              # V/rpm
    tau: float             # s
    K1: float = NAN        # rpm/A (precisa da Tabela 2)

    @property
    def KKt(self):
        return self.K * self.Kt

    def velocidade(self):
        """ω/Va em rpm/V."""
        return FT([self.K], [self.tau, 1.0])

    def tacometro(self):
        """Vt/Va em V/V."""
        return FT([self.KKt], [self.tau, 1.0])

    def carga(self):
        """−ω/Ig em rpm/A (a corrente do gerador freia o motor)."""
        return FT([self.K1], [self.tau, 1.0])

    def posicao(self, reducao=1.0):
        """θ/Va em graus/V: a posição é a integral da velocidade; com `reducao`
        (30 no CE110), a posição do eixo de saída, depois da engrenagem."""
        return FT([GRAUS_POR_S_POR_RPM * self.K / reducao], [self.tau, 1.0, 0.0])

    def carga_posicao(self, reducao=1.0):
        """−θ/Ig em graus/A."""
        return FT([GRAUS_POR_S_POR_RPM * self.K1 / reducao], [self.tau, 1.0, 0.0])

    @property
    def com_carga(self):
        return not math.isnan(self.K1)


@dataclass(frozen=True)
class Reta:
    """y = a·x + b por mínimos quadrados, com a reta pela origem (y = a0·x) ao lado.
    `ids` diz de que caso veio cada ponto; `excluidos`, os casos deixados de fora."""
    a: float
    b: float
    a0: float
    r2: float
    x: tuple
    y: tuple
    ids: tuple = ()
    excluidos: tuple = ()

    @classmethod
    def ajustar(cls, x, y, ids=(), excluidos=()):
        x, y = np.asarray(x, float), np.asarray(y, float)
        if len(x) < 2 or np.ptp(x) == 0:
            raise ValueError("são precisos pelo menos 2 pontos com x diferentes")
        a, b = np.polyfit(x, y, 1)
        a0 = float(x @ y / (x @ x))
        residuo = y - (a * x + b)
        total = y - y.mean()
        r2 = 1 - float(residuo @ residuo) / float(total @ total) if total @ total > 0 else 1.0
        return cls(float(a), float(b), a0, r2, tuple(map(float, x)), tuple(map(float, y)), tuple(ids),
                   tuple(excluidos))

    @property
    def n(self):
        return len(self.x)

    def __call__(self, x):
        return self.a * np.asarray(x, float) + self.b


@dataclass
class Leitura:
    """O que se sabe de uma linha da tabela: cada grandeza com a fonte de onde veio
    ('osc', 'manual', 'nominal' ou 'tab. 1')."""
    valores: dict = field(default_factory=dict)
    fontes: dict = field(default_factory=dict)

    def __getitem__(self, chave):
        if chave == "v1t":
            return self["vt"] - self["vtc"]
        return self.valores.get(chave, NAN)

    def definir(self, chave, valor, fonte):
        if valor is not None and not math.isnan(valor):
            self.valores[chave], self.fontes[chave] = float(valor), fonte

    def tem(self, chave):
        return not math.isnan(self[chave])


def _parou(valores, fracao=0.03):
    """Índices dos pontos em que o motor não girou: |y| abaixo de `fracao` do maior."""
    v = np.abs(np.asarray(valores, float))
    return set(np.flatnonzero(v <= fracao * v.max())) if len(v) and v.max() > 0 else set()


def _reta(pontos, x, y, parados=("x", "y")):
    """Reta de y contra x nas leituras `pontos` ({id: Leitura}) que têm os dois.
    Pontos com o motor parado (x ou y quase zero, conforme `parados`) ficam de fora."""
    ids = [k for k, l in pontos.items() if l.tem(x) and l.tem(y)]
    xs, ys = [pontos[k][x] for k in ids], [pontos[k][y] for k in ids]
    fora = set()
    if "x" in parados:
        fora |= _parou(xs)
    if "y" in parados:
        fora |= _parou(ys)
    usados = [k for k in range(len(ids)) if k not in fora]
    if len(usados) < 2:
        return None
    return Reta.ajustar([xs[k] for k in usados], [ys[k] for k in usados], [ids[k] for k in usados],
                        tuple(ids[k] for k in sorted(fora)))


@dataclass
class Identificacao:
    """As constantes pedidas pelo roteiro, cada uma da reta do gráfico indicado:

      KKt   Vt × Va           (item i da seção 3)
      K     ω × Va            (item ii)
      Kt    Vt × ω            (item iii), conferido com KKt/K
      K1Kt  V1t × ig          (item i da seção 4)
      K1    K1Kt / Kt         (item ii da seção 4)
      τ     média das constantes de tempo medidas sem carga
    """
    kkt: Reta | None
    k: Reta | None
    kt: Reta | None
    k1kt: Reta | None
    taus: dict              # id do caso -> τ medido (Tabela 1)

    @classmethod
    def de(cls, sem_carga, com_carga=None):
        """`sem_carga` e `com_carga`: {id: Leitura} das Tabelas 1 e 2."""
        com_carga = com_carga or {}
        taus = {k: l["tau"] for k, l in sem_carga.items() if l.tem("tau")}
        return cls(kkt=_reta(sem_carga, "va", "vt", ("y",)), k=_reta(sem_carga, "va", "w", ("y",)),
                   kt=_reta(sem_carga, "w", "vt"), k1kt=_reta(com_carga, "ig", "v1t", ()), taus=taus)

    @property
    def tau(self):
        return float(np.mean(list(self.taus.values()))) if self.taus else NAN

    @property
    def tau_desvio(self):
        return float(np.std(list(self.taus.values()), ddof=1)) if len(self.taus) > 1 else NAN

    @staticmethod
    def _a(reta):
        return reta.a if reta is not None else NAN

    @property
    def KKt(self):
        return self._a(self.kkt)

    @property
    def K(self):
        return self._a(self.k)

    @property
    def Kt(self):
        """Kt do gráfico Vt × ω; sem ω medido, KKt/K não existe e fica NaN."""
        return self._a(self.kt)

    @property
    def Kt_indireto(self):
        """Kt = KKt/K, a conferência pedida no item iii."""
        return self.KKt / self.K if self.K else NAN

    @property
    def K1Kt(self):
        return self._a(self.k1kt)

    @property
    def K1(self):
        return self.K1Kt / self.Kt if self.Kt else NAN

    def motor(self):
        """O modelo para o projeto. Exige K, Kt e τ."""
        faltam = [n for n, v in (("K (ω × Va)", self.K), ("Kt (Vt × ω)", self.Kt), ("τ", self.tau))
                  if math.isnan(v)]
        if faltam:
            raise ValueError("ainda não dá para montar o modelo, falta " + ", ".join(faltam)
                             + ": meça mais linhas da Tabela 1")
        return MotorCC(self.K, self.Kt, self.tau, self.K1)

    def prever(self, chave, va=NAN, ig=NAN, vt=NAN):
        """Valor esperado de uma grandeza numa linha, pelas retas já ajustadas."""
        if chave == "vt":
            return float(self.kkt(va)) if self.kkt else NAN
        if chave == "w":
            return float(self.k(va)) if self.k else NAN
        if chave == "tau":
            return self.tau
        if chave == "vtc":
            return vt - float(self.k1kt(ig)) if self.k1kt and not math.isnan(ig) else NAN
        return NAN
