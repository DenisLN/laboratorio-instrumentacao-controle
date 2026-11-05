"""Roteiros de laboratório: casos a montar e tabelas a preencher."""
from .base import Caso, Componentes, Roteiro, Tabela, texto_si, valor_si
from .experimento6 import Experimento6
from .experimento7 import Experimento7
from .experimento8 import ANOTAVEIS, APELIDOS, GRANDEZAS, Experimento8, Grandeza, PontoMotor, grandeza
from .experimento9 import CasoControle, Experimento9
from .experimento10 import CadeiaAberta, CasoAvanco, ComponentesAvanco, Experimento10

ROTEIROS = {6: Experimento6, 7: Experimento7, 8: Experimento8, 9: Experimento9, 10: Experimento10}

__all__ = ["Caso", "Componentes", "Roteiro", "Tabela", "Experimento6", "Experimento7", "Experimento8", "Experimento9", "CasoControle", "Experimento10", "CasoAvanco",
           "ComponentesAvanco", "CadeiaAberta", "ROTEIROS",
           "PontoMotor", "Grandeza", "GRANDEZAS", "APELIDOS", "ANOTAVEIS", "grandeza", "texto_si", "valor_si"]
