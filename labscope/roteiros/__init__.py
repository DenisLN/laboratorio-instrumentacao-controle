"""Roteiros de laboratório: casos a montar e tabelas a preencher."""
from .base import Caso, Componentes, Roteiro, Tabela, texto_si, valor_si
from .experimento6 import Experimento6
from .experimento7 import Experimento7

ROTEIROS = {6: Experimento6, 7: Experimento7}

__all__ = ["Caso", "Componentes", "Roteiro", "Tabela", "Experimento6", "Experimento7", "ROTEIROS",
           "texto_si", "valor_si"]
