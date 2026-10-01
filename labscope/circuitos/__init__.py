"""Os circuitos do roteiro como objetos.

  FT                    razão de polinômios em s (funções de transferência e impedâncias)
  Bloco                 abstrato: tem uma `ft()`
  EstagioAmpOp          abstrato: inversor com Z_in e Z_f  →  Somador, InversorRealimentacao
  Controlador           abstrato: K_p, K_i, K_d            →  ControladorP, PI, PID, Ideal
  Planta                abstrato: impedância série + C      →  PlantaRC, PlantaRLC
  MalhaFechada          junta tudo: V_c/E₁, polos, estabilidade, erro de regime
"""
from .blocos import (Bloco, EstagioAmpOp, InversorRealimentacao, Somador, capacitor, indutor, paralelo,
                     resistor, serie)
from .controladores import (Controlador, ControladorAmpOp, ControladorIdeal, ControladorP, ControladorPI,
                            ControladorPID)
from .ft import FT
from .malha import MalhaFechada
from .plantas import Planta, PlantaRC, PlantaRLC

__all__ = ["FT", "Bloco", "EstagioAmpOp", "Somador", "InversorRealimentacao", "resistor", "capacitor",
           "indutor", "serie", "paralelo", "Controlador", "ControladorAmpOp", "ControladorIdeal",
           "ControladorP", "ControladorPI", "ControladorPID", "Planta", "PlantaRC", "PlantaRLC",
           "MalhaFechada"]
