"""Interface comum das fontes de captura e a transcrição do que trafega no cabo."""
import datetime as dt
from abc import ABC, abstractmethod
from pathlib import Path

from ..captura import Captura

# passos de s/div dos Tektronix TBS/TDS (sequência 1–2,5–5)
_PASSOS = [m * 10.0 ** e for e in range(-9, 2) for m in (1.0, 2.5, 5.0)]


def base_de_tempo(duracao, divisoes=9.0):
    """Menor s/div da sequência 1–2,5–5 em que `duracao` cabe em `divisoes`."""
    for passo in _PASSOS:
        if passo * divisoes >= duracao:
            return passo
    return _PASSOS[-1]


class ErroInstrumento(RuntimeError):
    pass


class Transcricao:
    """Arquivo de texto com tudo que foi enviado (>>) e recebido (<<), uma
    linha por mensagem e com horário. Grava a cada linha, para dar para
    acompanhar de outra janela enquanto a sessão roda."""

    def __init__(self, caminho):
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.caminho.touch()

    def __call__(self, sentido, texto):
        hora = dt.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        with self.caminho.open("a", encoding="utf-8") as fh:
            fh.write(f"{hora}  {sentido}  {texto}\n")


class Osciloscopio(ABC):
    """De onde vêm as capturas. A subclasse abre a conexão e devolve os canais
    já em volts e segundos; a análise não sabe (nem precisa saber) qual é."""
    nome = "osciloscópio"
    transcricao = None      # Transcricao, ou None para não registrar

    def registrar(self, sentido, texto):
        if self.transcricao is not None:
            self.transcricao(sentido, texto)

    @abstractmethod
    def conectar(self) -> str:
        """Abre a conexão e devolve a identificação do instrumento."""

    @abstractmethod
    def adquirir(self, canais=("CH1", "CH2")) -> Captura:
        """Lê o que está na tela, com todos os canais da mesma aquisição."""

    def preparar(self, s_div, media=0):
        """Ajusta base de tempo, trigger em CH1 e média de aquisições (opcional)."""
        raise ErroInstrumento(f"{self.nome} não aceita configuração remota")

    def fechar(self):
        pass

    def __enter__(self):
        self.conectar()
        return self

    def __exit__(self, *exc):
        self.fechar()
