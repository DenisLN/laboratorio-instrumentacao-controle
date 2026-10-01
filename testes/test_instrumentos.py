"""Fontes de captura. O Tektronix é exercitado contra uma conexão VISA de
mentira que responde como o TBS1000B descrito no manual do programador."""
import numpy as np
import pytest

from labscope.captura import Captura
from labscope.instrumentos import (ErroInstrumento, Osciloscopio, OsciloscopioArquivo, OsciloscopioSimulado,
                                   TektronixTBS, Transcricao, base_de_tempo, ler_arquivo)
from labscope.roteiros import Experimento7

IDN_TBS = "TEKTRONIX,TBS 1052B,C012345,CF:91.1CT FV:v4.06"
PRE = {"XINCR": 4e-6, "XZERO": -1e-3, "PT_OFF": 0, "YMULT": 8e-3, "YZERO": 0.0, "YOFF": -20.0}


class ConexaoFalsa:
    """O mínimo de um recurso PyVISA: write, query, query_binary_values e close."""

    def __init__(self, idn=IDN_TBS, rodando=True, canais=None, prefixo="WFMPRE"):
        n = np.arange(2500)
        self.idn, self.rodando, self.prefixo = idn, rodando, prefixo
        self.canais = canais or {"CH1": np.where(n >= 250, 62, -62).astype(np.int8),
                                 "CH2": np.clip(n // 20 - 80, -100, 45).astype(np.int8)}
        self.fonte, self.enviados, self.fechada = "CH1", [], False

    def write(self, comando):
        self.enviados.append(comando)
        chave, _, valor = comando.partition(" ")
        if chave.upper() == "DATA:SOURCE":
            self.fonte = valor
        if chave.upper() == "ACQUIRE:STATE":
            self.rodando = valor.upper() in ("RUN", "ON", "1")

    def query(self, comando):
        self.enviados.append(comando)
        c = comando.upper().rstrip("?")
        if c == "*IDN":
            return self.idn + "\n"
        if c == "ACQUIRE:STATE":
            return f"{int(self.rodando)}\n"
        if c.startswith("SELECT:"):
            return f"{int(c.split(':')[1] in self.canais)}\n"
        if c == "HORIZONTAL:RECORDLENGTH":
            return "2500\n"
        if c.startswith(self.prefixo + ":"):
            return f"{PRE[c.split(':')[1]]:E}\n"
        if c in ("*ESR", "ALLEV"):
            return '0,"No events to report - queue empty"\n'
        if c.endswith(":SCALE"):
            return "2.0E-1\n"
        if c.endswith(":PROBE"):
            return "1.0E0\n"
        raise TimeoutError(f"sem resposta para {comando}")

    def query_binary_values(self, comando, datatype="b", container=list, **_):
        self.enviados.append(comando)
        assert comando == "CURVe?" and datatype == "b" and not self.rodando
        return container(self.canais[self.fonte])

    def close(self):
        self.fechada = True


class GerenteFalso:
    def __init__(self, recursos):
        self.recursos = recursos

    def list_resources(self):
        return tuple(self.recursos)

    def open_resource(self, nome):
        if isinstance(self.recursos[nome], Exception):
            raise self.recursos[nome]
        return self.recursos[nome]


def _tek(con=None, **outros):
    con = con or ConexaoFalsa()
    scope = TektronixTBS(rm=GerenteFalso({"USB0::0x0699::0x0368::C012345::INSTR": con, **outros}))
    return scope, con


# ---------------------------------------------------------------- Tektronix
def test_conecta_no_tektronix_e_ignora_recurso_que_nao_responde():
    morto = "USB0::0x0957::0x17A4::MY59240844::0::INSTR"      # listado pelo VISA, mas não está na mesa
    scope, con = _tek(**{morto: OSError("VI_ERROR_RSRC_NFOUND")})
    assert scope.conectar() == IDN_TBS and scope.recurso.startswith("USB0::0x0699")
    assert con.write_termination == "\n" and "HEADer OFF" in con.enviados
    scope.fechar()
    assert con.fechada and scope.con is None


def test_recusa_instrumento_que_nao_e_tektronix_ou_que_nao_existe():
    with pytest.raises(ErroInstrumento, match="não é um Tektronix"):
        TektronixTBS(rm=GerenteFalso({"USB0::0x0957::1::INSTR": ConexaoFalsa("KEYSIGHT,DSO-X 4034A,MY1,07.30")})).conectar()
    with pytest.raises(ErroInstrumento, match="cabo USB-B"):
        TektronixTBS(rm=GerenteFalso({})).conectar()
    with pytest.raises(ErroInstrumento, match="não conectado"):
        TektronixTBS(rm=GerenteFalso({})).adquirir()


def test_adquirir_converte_pelo_preambulo():
    scope, con = _tek()
    scope.conectar()
    cap = scope.adquirir()
    assert isinstance(cap, Captura) and len(cap.t) == 2500 and set(cap.canais) == {"CH1", "CH2"}
    assert cap.t[0] == pytest.approx(-1e-3) and cap.dt == pytest.approx(4e-6)
    # v = YZEro + YMUlt·(bruto − YOFf)
    assert cap["CH1"][0] == pytest.approx(8e-3 * (-62 + 20)) and cap["CH1"][-1] == pytest.approx(8e-3 * (62 + 20))
    assert cap.meta["CH2"]["LSB"] == 8e-3 and cap.meta["CH2"]["Vertical Scale"] == 0.2
    assert cap.meta["geral"]["idn"] == IDN_TBS and "TBS 1052B" in cap.origem
    assert "DATa:ENCdg RIBinary" in con.enviados and "DATa:STOP 2500" in con.enviados


def test_adquirir_congela_e_devolve_o_estado_de_aquisicao():
    scope, con = _tek()
    scope.conectar()
    scope.adquirir()
    assert con.rodando and con.enviados.index("ACQuire:STATE STOP") < con.enviados.index("CURVe?")
    parado = ConexaoFalsa(rodando=False)
    scope, _ = _tek(parado)
    scope.conectar()
    scope.adquirir()
    assert not parado.rodando and "ACQuire:STATE RUN" not in parado.enviados


def test_canal_desligado_e_sinal_cortado_sao_avisados():
    n = np.arange(2500)
    so_ch1 = ConexaoFalsa(canais={"CH1": np.where(n >= 250, 62, -62).astype(np.int8)})
    scope, _ = _tek(so_ch1)
    scope.conectar()
    with pytest.raises(ErroInstrumento, match="CH2 está desligado"):
        scope.adquirir()
    assert so_ch1.rodando                                     # mesmo com erro, volta a rodar
    cortado = ConexaoFalsa()
    cortado.canais["CH2"] = np.where(n >= 250, 127, -100).astype(np.int8)
    scope, _ = _tek(cortado)
    scope.conectar()
    meta = scope.adquirir().meta
    assert meta["CH2"]["cortado"] and not meta["CH1"]["cortado"]


def test_familias_novas_usam_wfmoutpre():
    con = ConexaoFalsa("TEKTRONIX,MSO2024B,C1,CF:91.1CT FV:v1.56", prefixo="WFMOUTPRE")
    scope, _ = _tek(con)
    scope.conectar()
    assert scope.adquirir().dt == pytest.approx(4e-6) and any(c.startswith("WFMOutpre:") for c in con.enviados)


def test_transcricao_registra_o_que_trafega(tmp_path):
    scope, _ = _tek()
    scope.transcricao = Transcricao(tmp_path / "scpi.log")
    scope.conectar()
    scope.adquirir(("CH1",))
    linhas = (tmp_path / "scpi.log").read_text(encoding="utf-8").splitlines()
    assert any(l.endswith(">>  *IDN?") for l in linhas) and any(f"<<  {IDN_TBS}" in l for l in linhas)
    assert any(">>  CURVe?" in l for l in linhas) and any("bloco binário: 2500 pontos" in l for l in linhas)
    assert linhas[0][2] == ":" and linhas[0][12:16] == "  --"       # HH:MM:SS.mmm  sentido  texto


def test_preparar_ajusta_base_de_tempo_trigger_e_media():
    scope, con = _tek()
    scope.conectar()
    scope.preparar(1e-3, media=16)
    assert {"HORizontal:MAIn:SCAle 0.001", "HORizontal:MAIn:POSition 0.004", "TRIGger:MAIn:EDGE:SOUrce CH1",
            "ACQuire:NUMAVg 16", "ACQuire:MODe AVErage"} <= set(con.enviados)


# ---------------------------------------------------------------- demais fontes
def test_osciloscopio_e_abstrato_e_base_de_tempo_segue_1_25_5():
    with pytest.raises(TypeError):
        Osciloscopio()
    assert base_de_tempo(4.4e-3) == pytest.approx(500e-6) and base_de_tempo(5e-3) == pytest.approx(1e-3)
    assert base_de_tempo(55e-3) == pytest.approx(10e-3) and base_de_tempo(2.0e-3) == pytest.approx(250e-6)


def test_simulado_imita_a_tela_do_tbs():
    caso = Experimento7().caso("1.2")
    cap = OsciloscopioSimulado(lambda: caso.malha(), s_div=1e-3).adquirir()
    assert len(cap.t) == 2500 and cap.dt == pytest.approx(4e-6) and cap.t[250] == pytest.approx(0)
    assert np.min(np.diff(np.unique(cap["CH2"]))) == pytest.approx(8e-3)
    assert not cap.meta["CH2"]["cortado"]
    assert OsciloscopioSimulado(lambda: caso.malha(), v_div=(0.2, 0.05)).adquirir().meta["CH2"]["cortado"]


def test_captura_salva_e_carrega(tmp_path):
    cap = OsciloscopioSimulado(lambda: Experimento7().caso("1.1").malha()).adquirir()
    cap.salvar(tmp_path / "x")
    lida = ler_arquivo(tmp_path / "x")
    assert np.array_equal(lida.t, cap.t) and np.array_equal(lida["CH2"], cap["CH2"])
    assert lida.meta["CH1"]["Vertical Scale"] == 0.2 and lida.origem == "simulação"
    assert (tmp_path / "x" / "captura.csv").read_text().splitlines()[0] == "Time,CH1,CH2"


def test_arquivo_le_a_pasta_all_mais_nova(tmp_path):
    def gravar(n, nivel):
        pasta = tmp_path / f"ALL{n:04d}"
        pasta.mkdir()
        for canal in ("CH1", "CH2"):
            with open(pasta / f"F{n:04d}{canal}.CSV", "w") as fh:
                for k in range(50):
                    fh.write(f",,,{k * 2e-5:17.12f},{nivel:10.5f},\n")
    gravar(3, 1.0)
    gravar(7, 2.0)
    scope = OsciloscopioArquivo(tmp_path)
    assert "2 capturas" in scope.conectar()
    assert scope.adquirir()["CH1"][0] == 2.0
    scope.proxima = 3
    assert scope.adquirir()["CH1"][0] == 1.0 and scope.adquirir()["CH1"][0] == 2.0
    scope.proxima = 5
    with pytest.raises(ErroInstrumento, match="ALL0005"):
        scope.adquirir()
