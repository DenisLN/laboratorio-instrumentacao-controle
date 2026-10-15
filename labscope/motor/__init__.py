"""Experimento 8: o grupo motor-gerador-tacômetro.

  modelo    MotorCC (1ª ordem), Reta (mínimos quadrados), Leitura, Identificacao
  medida    DegrauMotor: Va, Vt e τ de uma partida no osciloscópio
  resposta  RespostaMalha: a resposta em malha fechada do Exp. 9 numa captura, e a previsão do modelo
  componentes  resistores e capacitores do PI, PD e PID analógicos
  projeto   Projeto → ProjetoPI (velocidade), ProjetoPD e ProjetoPID (posição), com simulação
"""
from .medida import DegrauMotor
from .modelo import Identificacao, Leitura, MotorCC, Reta
from .resposta import RespostaMalha, previsao, simular_degrau
from .projeto import Projeto, ProjetoPD, ProjetoPI, ProjetoPID

__all__ = ["MotorCC", "Reta", "Leitura", "Identificacao", "DegrauMotor", "Projeto", "ProjetoPI", "ProjetoPD",
           "ProjetoPID",
           "RespostaMalha", "previsao", "simular_degrau"]
