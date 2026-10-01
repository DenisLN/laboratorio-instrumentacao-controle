"""Tektronix TBS1000/TDS1000/TDS2000 pela porta USB-B (USBTMC) via VISA.

Lê a forma de onda da tela com CURVe? e a converte com o preâmbulo:
    t = XZEro + XINcr·(n − PT_Off)        v = YZEro + YMUlt·(bruto − YOFf)
Referência: TBS1000B/TDS2000C Programmer Manual (077-0444).
"""
import re

import numpy as np

from ..captura import Captura
from .base import ErroInstrumento, Osciloscopio

VID_TEKTRONIX = "0x0699"
# famílias que respondem ao preâmbulo em WFMPre; as mais novas usam WFMOutpre
_FAMILIA_WFMPRE = re.compile(r"T(BS\s*1|DS\s*[12]|PS\s*2)\d{3}", re.IGNORECASE)


def recursos_visa(rm=None):
    """Recursos VISA visíveis agora (strings como 'USB0::0x0699::0x0368::C012345::INSTR')."""
    import pyvisa
    return list((rm or pyvisa.ResourceManager()).list_resources())


class TektronixTBS(Osciloscopio):
    nome = "Tektronix TBS/TDS"

    def __init__(self, recurso=None, rm=None, timeout_ms=10000):
        self.recurso = recurso
        self._rm = rm
        self.timeout_ms = timeout_ms
        self.con = None
        self.idn = ""
        self._pre = "WFMPre"

    # ------------------------------------------------------------ conexão
    def conectar(self):
        import pyvisa
        self._rm = self._rm or pyvisa.ResourceManager()
        erros = []
        for recurso in ([self.recurso] if self.recurso else self._candidatos()):
            self.registrar("--", f"abrindo {recurso}")
            try:
                con = self._rm.open_resource(recurso)
                con.timeout = self.timeout_ms
                con.write_termination = "\n"
                self.registrar(">>", "*IDN?")
                idn = con.query("*IDN?").strip()
                self.registrar("<<", idn)
            except Exception as exc:  # recurso listado mas desligado, ocupado, etc.
                self.registrar("!!", f"{type(exc).__name__}: {exc}")
                erros.append(f"{recurso}: {exc}")
                continue
            if "TEKTRONIX" not in idn.upper():
                erros.append(f"{recurso}: não é um Tektronix ({idn})")
                con.close()
                continue
            self.con, self.recurso, self.idn = con, recurso, idn
            self._pre = "WFMPre" if _FAMILIA_WFMPRE.search(idn) else "WFMOutpre"
            self.escrever("HEADer OFF")
            self.escrever("*CLS")
            return idn
        raise ErroInstrumento("nenhum Tektronix respondeu. " + ("Tentativas: " + "; ".join(erros) + ". " if erros else
                              "Nenhum recurso VISA listado. ") + "Confira o cabo USB-B e o driver VISA "
                              "('recursos' lista o que o computador enxerga); o plano B é 'conectar <pasta do pendrive>'.")

    def _candidatos(self):
        todos = list(self._rm.list_resources())
        tek = [r for r in todos if VID_TEKTRONIX in r.lower()]
        return tek or [r for r in todos if r.upper().startswith("USB")]

    def fechar(self):
        if self.con is not None:
            try:
                self.con.close()
            finally:
                self.con = None

    # ------------------------------------------------------------ SCPI
    def _exigir_conexao(self):
        if self.con is None:
            raise ErroInstrumento("osciloscópio não conectado")

    def escrever(self, comando):
        self._exigir_conexao()
        self.registrar(">>", comando)
        self.con.write(comando)

    def perguntar(self, comando):
        self._exigir_conexao()
        self.registrar(">>", comando)
        try:
            resposta = self.con.query(comando).strip()
        except Exception as exc:
            self.registrar("!!", f"{type(exc).__name__}: {exc}")
            raise
        self.registrar("<<", resposta)
        return resposta

    def _numero(self, comando):
        resposta = self.perguntar(comando)
        try:
            # com HEADer ON a resposta vem como ":WFMPRE:XINCR 4.0E-6"
            return float(resposta.split()[-1])
        except (ValueError, IndexError):
            raise ErroInstrumento(f"{comando} devolveu {resposta!r}") from None

    def erros(self):
        """Eventos pendentes na fila do instrumento (texto do ALLEv?)."""
        try:
            self.perguntar("*ESR?")
            return self.perguntar("ALLEv?")
        except Exception as exc:
            return f"(não foi possível ler a fila de erros: {exc})"

    # ------------------------------------------------------------ aquisição
    def adquirir(self, canais=("CH1", "CH2")):
        """Congela a aquisição, baixa os canais e devolve o osciloscópio ao
        estado em que estava (RUN ou STOP)."""
        self._exigir_conexao()
        rodando = self._numero("ACQuire:STATE?") != 0
        if rodando:
            self.escrever("ACQuire:STATE STOP")
        try:
            lidos = {c: self._ler_canal(c) for c in canais}
        finally:
            if rodando:
                self.escrever("ACQuire:STATE RUN")
        t = lidos[canais[0]][0]
        for c, (tc, _, _) in lidos.items():
            if len(tc) != len(t) or not np.allclose(tc, t, rtol=0, atol=abs(t[1] - t[0]) * 1e-3):
                raise ErroInstrumento(f"{c} veio com base de tempo diferente de {canais[0]}")
        meta = {c: m for c, (_, _, m) in lidos.items()}
        meta["geral"] = {"idn": self.idn, "recurso": self.recurso, "pontos": len(t),
                         "congelado_para_ler": rodando}
        return Captura(t, {c: v for c, (_, v, _) in lidos.items()}, meta, f"USB {self.idn}")

    def _comprimento_do_registro(self):
        try:
            return int(self._numero("HORizontal:RECOrdlength?"))
        except Exception:      # os TBS1000/TDS2000 têm registro fixo de 2500 pontos
            return 2500

    def _ler_canal(self, canal):
        if self.perguntar(f"SELect:{canal}?").split()[-1] not in ("1", "ON"):
            raise ErroInstrumento(f"{canal} está desligado na tela: ligue o canal e tente de novo")
        for comando in (f"DATa:SOUrce {canal}", "DATa:ENCdg RIBinary", "DATa:WIDth 1", "DATa:STARt 1"):
            self.escrever(comando)
        self.escrever(f"DATa:STOP {self._comprimento_do_registro()}")
        pre = {k: self._numero(f"{self._pre}:{k}?") for k in ("XINcr", "XZEro", "PT_Off", "YMUlt", "YZEro", "YOFf")}
        self.registrar(">>", "CURVe?")
        try:
            bruto = np.asarray(self.con.query_binary_values("CURVe?", datatype="b", container=np.array), float)
        except Exception as exc:
            self.registrar("!!", f"{type(exc).__name__}: {exc}")
            raise ErroInstrumento(f"falha ao baixar {canal}: {exc}. Fila do instrumento: {self.erros()}") from exc
        if len(bruto) < 2:
            raise ErroInstrumento(f"{canal} devolveu {len(bruto)} pontos")
        self.registrar("<<", f"<bloco binário: {len(bruto)} pontos, de {bruto.min():.0f} a {bruto.max():.0f}>")
        t = pre["XZEro"] + pre["XINcr"] * (np.arange(len(bruto)) - pre["PT_Off"])
        v = pre["YZEro"] + pre["YMUlt"] * (bruto - pre["YOFf"])
        meta = {"Sample Interval": pre["XINcr"], "Record Length": len(bruto), "Source": canal,
                "LSB": pre["YMUlt"], "cortado": bool(np.any(bruto >= 127) or np.any(bruto <= -127))}
        for chave, comando in (("Vertical Scale", f"{canal}:SCAle?"), ("Probe Atten", f"{canal}:PRObe?"),
                               ("Horizontal Scale", "HORizontal:MAIn:SCAle?")):
            try:
                meta[chave] = self._numero(comando)
            except Exception:  # metadado opcional: modelos diferentes mudam o nome do comando
                break
        return t, v, meta

    # ------------------------------------------------------------ configuração
    def preparar(self, s_div, media=0):
        """Borda de subida de CH1 a 1 divisão da esquerda da tela, `s_div` por
        divisão e, se `media` > 0, média de `media` aquisições (4, 16, 64 ou 128)."""
        self._exigir_conexao()
        comandos = [f"HORizontal:MAIn:SCAle {s_div:.6g}",
                    f"HORizontal:MAIn:POSition {4 * s_div:.6g}",
                    "TRIGger:MAIn:MODe NORMal",
                    "TRIGger:MAIn:EDGE:SOUrce CH1",
                    "TRIGger:MAIn:EDGE:SLOpe RISe",
                    "TRIGger:MAIn SETLevel"]
        comandos += [f"ACQuire:NUMAVg {media}", "ACQuire:MODe AVErage"] if media else ["ACQuire:MODe SAMple"]
        for comando in comandos + ["ACQuire:STATE RUN"]:
            self.escrever(comando)
        return self.erros()
