"""Keysight (Agilent) InfiniiVision 2000/3000 X (DSO-X 2002A etc.) pela USB-B via VISA.

Lê a forma de onda com :WAVeform:DATA? em BYTE sem sinal e a converte com o
preâmbulo (:WAVeform:PREamble? = formato, tipo, pontos, contagem, XINC, XORIG,
XREF, YINC, YORIG, YREF):
    t = XORIG + XINC·(n − XREF)        v = YORIG + YINC·(bruto − YREF)
Referência: InfiniiVision 2000 X-Series Programmer's Guide.

A conexão VISA (abrir, *IDN?, transcrição) é a mesma do Tektronix; só mudam os
comandos.
"""
import numpy as np

from ..captura import Captura
from .base import ErroInstrumento
from .tektronix import TektronixTBS, recursos_visa

VID_KEYSIGHT = "0x0957"
PONTOS = 10000             # pontos pedidos por canal (o registro inteiro pode ter 50 mil)


def _canal(canal):
    """'CH1' → 'CHANnel1'."""
    return f"CHANnel{canal[-1]}"


class KeysightDSOX(TektronixTBS):
    nome = "Keysight InfiniiVision"
    VID = VID_KEYSIGHT
    MARCA = "KEYSIGHT"

    def conectar(self):
        try:
            return super().conectar()
        except ErroInstrumento:
            if self.MARCA != "KEYSIGHT":
                raise
            self.MARCA = "AGILENT"          # os mais antigos se identificam como Agilent
            try:
                return super().conectar()
            finally:
                self.MARCA = "KEYSIGHT"

    def _ao_conectar(self, idn):
        self.escrever("*CLS")

    def _numero(self, comando):
        resposta = self.perguntar(comando)
        try:
            return float(resposta.split(",")[0])
        except (ValueError, IndexError):
            raise ErroInstrumento(f"{comando} devolveu {resposta!r}") from None

    def erros(self):
        """Erros pendentes (:SYSTem:ERRor? até esvaziar a fila)."""
        try:
            erros = []
            for _ in range(10):
                resposta = self.perguntar(":SYSTem:ERRor?")
                if resposta.startswith(("+0", "0,")):
                    break
                erros.append(resposta)
            return "; ".join(erros) or "sem erros"
        except Exception as exc:
            return f"(não foi possível ler a fila de erros: {exc})"

    # ------------------------------------------------------------ aquisição
    def _rodando(self):
        return int(self._numero(":OPERegister:CONDition?")) & 8 != 0      # bit 3: Run

    def adquirir(self, canais=("CH1", "CH2")):
        """Para a aquisição, baixa os canais e devolve o osciloscópio ao RUN se
        ele estava rodando (depois de um :SINGle já disparado ele está parado)."""
        self._exigir_conexao()
        rodando = self._rodando()
        if rodando:
            self.escrever(":STOP")
        try:
            lidos = {c: self._ler_canal(c) for c in canais}
        finally:
            if rodando:
                self.escrever(":RUN")
        t = lidos[canais[0]][0]
        for c, (tc, _, _) in lidos.items():
            if len(tc) != len(t) or not np.allclose(tc, t, rtol=0, atol=abs(t[1] - t[0]) * 1e-3):
                raise ErroInstrumento(f"{c} veio com base de tempo diferente de {canais[0]}")
        meta = {c: m for c, (_, _, m) in lidos.items()}
        meta["geral"] = {"idn": self.idn, "recurso": self.recurso, "pontos": len(t), "congelado_para_ler": rodando}
        return Captura(t, {c: v for c, (_, v, _) in lidos.items()}, meta, f"USB {self.idn}")

    def _ler_canal(self, canal):
        ch = _canal(canal)
        if self.perguntar(f":{ch}:DISPlay?").strip() not in ("1", "ON"):
            raise ErroInstrumento(f"{canal} está desligado na tela: ligue o canal e tente de novo")
        for comando in (f":WAVeform:SOURce {ch}", ":WAVeform:FORMat BYTE", ":WAVeform:UNSigned ON",
                        ":WAVeform:POINts:MODE MAXimum", f":WAVeform:POINts {PONTOS}"):
            self.escrever(comando)
        pre = [float(x) for x in self.perguntar(":WAVeform:PREamble?").split(",")]
        xinc, xorig, xref, yinc, yorig, yref = pre[4:10]
        self.registrar(">>", ":WAVeform:DATA?")
        try:
            bruto = np.asarray(self.con.query_binary_values(":WAVeform:DATA?", datatype="B", container=np.array),
                               float)
        except Exception as exc:
            self.registrar("!!", f"{type(exc).__name__}: {exc}")
            raise ErroInstrumento(f"falha ao baixar {canal}: {exc}. Fila do instrumento: {self.erros()}") from exc
        if len(bruto) < 2:
            raise ErroInstrumento(f"{canal} devolveu {len(bruto)} pontos (o osciloscópio já adquiriu algo?)")
        self.registrar("<<", f"<bloco binário: {len(bruto)} pontos, de {bruto.min():.0f} a {bruto.max():.0f}>")
        t = xorig + xinc * (np.arange(len(bruto)) - xref)
        v = yorig + yinc * (bruto - yref)
        meta = {"Sample Interval": xinc, "Record Length": len(bruto), "Source": canal, "LSB": yinc,
                "cortado": bool(np.any(bruto >= 255) or np.any(bruto <= 1))}
        for chave, comando in (("Vertical Scale", f":{ch}:SCALe?"), ("Probe Atten", f":{ch}:PROBe?"),
                               ("Horizontal Scale", ":TIMebase:SCALe?")):
            try:
                meta[chave] = self._numero(comando)
            except Exception:  # metadado opcional
                break
        return t, v, meta

    # ------------------------------------------------------------ configuração
    def preparar(self, s_div, media=0, nivel=None, unico=False):
        """Trigger na subida de CH1 a 1 divisão da esquerda (:TIMebase:REFerence
        LEFT), `s_div` por divisão, média opcional; com `unico`, :SINGle."""
        self._exigir_conexao()
        comandos = [":TIMebase:MODE MAIN", f":TIMebase:SCALe {s_div:.6g}", ":TIMebase:REFerence LEFT",
                    ":TIMebase:POSition 0", ":TRIGger:MODE EDGE", ":TRIGger:EDGE:SOURce CHANnel1",
                    ":TRIGger:EDGE:SLOPe POSitive", ":TRIGger:SWEep NORMal"]
        if nivel is not None:
            comandos.append(f":TRIGger:EDGE:LEVel {nivel:.4g}")
        comandos += [":ACQuire:TYPE AVERage", f":ACQuire:COUNt {media}"] if media else [":ACQuire:TYPE NORMal"]
        for comando in comandos + [":SINGle" if unico else ":RUN"]:
            self.escrever(comando)
        return self.erros()

    def armar(self):
        self._exigir_conexao()
        self.escrever(":SINGle")


def osciloscopio_usb(recurso=None, rm=None):
    """O driver certo para o que está na USB: Keysight se o recurso (ou o único
    fabricante listado) for 0x0957, Tektronix nos demais casos."""
    if recurso:
        return KeysightDSOX(recurso, rm) if VID_KEYSIGHT in recurso.lower() else TektronixTBS(recurso, rm)
    try:
        todos = [r.lower() for r in recursos_visa(rm)]
    except Exception:          # sem VISA: o Tektronix dá a mensagem de erro de sempre
        return TektronixTBS(None, rm)
    if not any("0x0699" in r for r in todos) and any(VID_KEYSIGHT in r for r in todos):
        return KeysightDSOX(None, rm)
    return TektronixTBS(None, rm)
