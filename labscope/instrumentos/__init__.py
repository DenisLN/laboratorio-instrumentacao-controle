"""Fontes de captura atrás de uma interface só.

  Osciloscopio          abstrato: conectar(), adquirir() → Captura, preparar(), fechar()
  TektronixTBS          TBS1000/TDS2000 pela USB-B (VISA)
  KeysightDSOX          InfiniiVision 2000/3000 X (DSO-X 2002A) pela USB-B; osciloscopio_usb escolhe
  OsciloscopioArquivo   pastas ALLnnnn do pendrive
  OsciloscopioSimulado  gera a captura a partir de uma malha
  MotorSimulado         a partida do grupo motor-gerador do Exp. 8
  ControleSimulado      a resposta em malha fechada do Exp. 9
"""
from .arquivo import OsciloscopioArquivo, ler_arquivo
from .base import ErroInstrumento, Osciloscopio, Transcricao, base_de_tempo
from .keysight import KeysightDSOX, osciloscopio_usb
from .simulado import ControleSimulado, MotorSimulado, OsciloscopioSimulado
from .tektronix import TektronixTBS, dica_de_usb, dispositivos_usb_tektronix, recursos_visa

__all__ = ["Osciloscopio", "ErroInstrumento", "TektronixTBS", "KeysightDSOX", "osciloscopio_usb", "OsciloscopioArquivo", "OsciloscopioSimulado", "MotorSimulado", "ControleSimulado",
           "ler_arquivo", "recursos_visa", "base_de_tempo", "Transcricao", "dica_de_usb",
           "dispositivos_usb_tektronix"]
