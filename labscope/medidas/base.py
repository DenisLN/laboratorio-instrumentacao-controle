"""Métrica: uma grandeza que se mede na captura e se prevê pelo modelo."""
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass

from .. import relatorio
from .resposta import RespostaMedida, RespostaTeorica


@dataclass(frozen=True)
class Comparacao:
    exp: float
    teo: float
    desvio: float      # (exp − teo)/teo; NaN se não dá para calcular
    ok: bool | None    # None quando falta um dos dois valores


class Metrica(ABC):
    """Cada métrica concreta diz como medir e como prever; o resto (formato,
    comparação com tolerância) é comum."""
    chave = "?"
    nome = "?"
    simbolo = "?"
    unidade = ""
    escala = 1.0            # multiplica o valor em SI para exibir (1e3 → ms)
    casas = 2
    tolerancia = 0.25       # desvio relativo aceito entre medida e modelo
    tolerancia_abs = 0.0    # folga absoluta, em SI (para valores perto de zero)

    @abstractmethod
    def medir(self, medida: RespostaMedida) -> float:
        ...

    @abstractmethod
    def prever(self, teoria: RespostaTeorica) -> float:
        ...

    def aplicavel(self, teoria: RespostaTeorica) -> bool:
        """Se a grandeza faz sentido para a malha (ex.: ζ exige polos complexos)."""
        return True

    def julgavel(self, teoria: RespostaTeorica) -> bool:
        """Se o desvio entre medida e modelo diz algo sobre a montagem. É False
        quando o próprio método de medida não vale para a malha."""
        return True

    def folga(self, medida: RespostaMedida) -> float:
        """Incerteza da própria medida, em SI (ex.: o passo de quantização do
        osciloscópio): um desvio menor que isso não acusa nada na montagem."""
        return 0.0

    def rotulo(self, medida=None):
        return self.simbolo

    def comparar(self, exp, teo, folga=0.0):
        if exp is None or teo is None or math.isnan(exp) or math.isnan(teo):
            return Comparacao(exp, teo, math.nan, None)
        desvio = (exp - teo) / teo if teo else math.nan
        limite = max(self.tolerancia * abs(teo), self.tolerancia_abs, folga)
        return Comparacao(exp, teo, desvio, abs(exp - teo) <= limite)

    def formatar(self, x, unidade=True):
        return relatorio.num(x, self.casas, self.unidade if unidade else "", self.escala)
