"""Capturas já gravadas: pastas ALLnnnn do pendrive da Tektronix ou .npz de uma sessão."""
from pathlib import Path

from .. import tek
from ..captura import Captura
from .base import ErroInstrumento, Osciloscopio


def ler_arquivo(caminho):
    """Captura de uma pasta ALLnnnn, de uma pasta de sessão ou de um .npz."""
    caminho = Path(caminho)
    if caminho.is_file() and caminho.suffix.lower() == ".npz":
        return Captura.carregar(caminho)
    if caminho.is_dir() and (caminho / "captura.npz").exists():
        return Captura.carregar(caminho / "captura.npz")
    if caminho.is_dir():
        c = tek.ler_captura(caminho)
        return Captura(c.t, c.canais, c.meta, f"pendrive {caminho}")
    raise ErroInstrumento(f"não achei captura em {caminho}")


class OsciloscopioArquivo(Osciloscopio):
    """Lê as pastas ALLnnnn de `raiz`. Sem número, `adquirir` pega a mais nova —
    o mesmo gesto do USB: salvar no osciloscópio e pedir a aquisição aqui."""
    nome = "pendrive"

    def __init__(self, raiz):
        self.raiz = Path(raiz)
        self.proxima = None      # número da captura a ler no próximo adquirir()

    def conectar(self):
        if not self.raiz.is_dir():
            raise ErroInstrumento(f"pasta não encontrada: {self.raiz}")
        n = len(tek.capturas(self.raiz))
        return f"pasta {self.raiz} ({n} capturas ALLnnnn)"

    def adquirir(self, canais=("CH1", "CH2")):
        achadas = tek.capturas(self.raiz)
        if not achadas:
            raise ErroInstrumento(f"nenhuma pasta ALLnnnn em {self.raiz}")
        n = self.proxima if self.proxima is not None else max(achadas)
        self.proxima = None
        if n not in achadas:
            raise ErroInstrumento(f"ALL{n:04d} não existe em {self.raiz}")
        cap = ler_arquivo(achadas[n])
        faltam = [c for c in canais if c not in cap.canais]
        if faltam:
            raise ErroInstrumento(f"ALL{n:04d} não tem {', '.join(faltam)}")
        return cap
