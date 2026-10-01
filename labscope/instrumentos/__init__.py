"""Fontes de captura atrás de uma interface só.

  Osciloscopio          abstrato: conectar(), adquirir() → Captura, preparar(), fechar()
  TektronixTBS          TBS1000/TDS2000 pela USB-B (VISA)
  OsciloscopioArquivo   pastas ALLnnnn do pendrive
  OsciloscopioSimulado  gera a captura a partir de uma malha
"""
from .arquivo import OsciloscopioArquivo, ler_arquivo
from .base import ErroInstrumento, Osciloscopio, Transcricao, base_de_tempo
from .simulado import OsciloscopioSimulado
from .tektronix import TektronixTBS, recursos_visa

__all__ = ["Osciloscopio", "ErroInstrumento", "TektronixTBS", "OsciloscopioArquivo", "OsciloscopioSimulado",
           "ler_arquivo", "recursos_visa", "base_de_tempo", "Transcricao"]
