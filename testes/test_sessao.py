"""A sessão interativa de ponta a ponta, com o osciloscópio simulado."""
import json

import numpy as np
import pytest

from labscope.captura import Captura
from labscope.instrumentos import Osciloscopio, OsciloscopioSimulado
from labscope.roteiros import Experimento6, Experimento7
from labscope.sessao import cli
from labscope.sessao.analise import analisar
from labscope.sessao.cli import SessaoLab, comando_terminal_diagnostico


@pytest.fixture
def sessao(tmp_path):
    s = SessaoLab(tmp_path / "sessoes", abrir_figuras=False)
    s.executar("conectar sim")
    return s


def _pastas(sessao):
    return sorted(p.name for p in sessao.pasta.caminho.iterdir() if p.is_dir())


# ---------------------------------------------------------------- análise
def test_analise_compara_medida_com_os_dois_modelos():
    roteiro = Experimento7()
    caso = roteiro.caso("4.2")
    cap = OsciloscopioSimulado(lambda: caso.malha(carga=True), s_div=10e-3, v_div=(0.2, 0.2)).adquirir()
    res = analisar(cap, roteiro, caso, numero=4)
    mp = res.linha("mp")
    # a "bancada" simulada tem a carga do inversor: bate com a coluna c/ carga e não com a do roteiro
    assert mp.exp == pytest.approx(mp.carga, abs=0.02) and abs(mp.exp - mp.teo) > 0.10 and mp.ok
    assert res.residuo["carga"] < 0.3 * res.residuo["teo"]
    assert not res.conferir and "dentro da tolerância" in res.veredito()
    assert res.linha("tau") is None                                  # só existe em 1ª ordem
    assert json.dumps(res.como_dict())                               # serializável
    assert res.texto().startswith("#04  Exp. 7 · Tabela 4 · caso 4.2 (R2 = 10 kΩ) · RLC + PID")


def test_analise_acusa_montagem_errada_e_tela_ruim():
    roteiro = Experimento7()
    montado, esperado = roteiro.caso("1.1"), roteiro.caso("1.2")       # R2 de 1 kΩ no lugar do de 10 kΩ
    cap = OsciloscopioSimulado(lambda: montado.malha(carga=True), s_div=1e-3).adquirir()
    res = analisar(cap, roteiro, esperado)
    assert "Mp" in [l.rotulo for l in res.conferir]
    for s_div, v_div, aviso in ((100e-6, 0.2, "aumente s/div"), (250e-6, 0.2, "aumente s/div"), (1e-3, 0.05, "saiu da tela")):
        cap = OsciloscopioSimulado(lambda: esperado.malha(carga=True), s_div=s_div, v_div=(0.2, v_div)).adquirir()
        assert aviso in " | ".join(analisar(cap, roteiro, esperado).avisos), aviso


def test_primeira_ordem_do_exp6_mede_tau_e_erro_de_regime():
    roteiro = Experimento6()
    caso = roteiro.caso("1.2")
    cap = OsciloscopioSimulado(lambda: caso.malha(carga=True), 50.0, s_div=500e-6, v_div=(0.2, 0.1)).adquirir()
    res = analisar(cap, roteiro, caso)
    assert res.linha("tau").exp == pytest.approx(1 / 2100, rel=0.08)
    assert res.linha("ess").exp == pytest.approx(1 - 10 / 21, abs=0.02) and res.linha("zeta") is None
    assert res.medida.subida == "10-90" and not res.conferir


# ---------------------------------------------------------------- sessão
def test_adquirir_grava_captura_metricas_e_painel(sessao, capsys):
    sessao.executar("caso 1.2")
    sessao.executar("adquirir")
    saida = capsys.readouterr().out
    assert "#01  Exp. 7 · Tabela 1 · caso 1.2" in saida and "ERRO" not in saida
    pasta = sessao.pasta.caminho / "01_e7_c1.2"
    assert {"captura.npz", "captura.csv", "metricas.json", "metricas.txt", "painel.png"} <= {p.name for p in pasta.iterdir()}
    dados = json.loads((pasta / "metricas.json").read_text(encoding="utf-8"))
    assert dados["caso"] == "1.2" and dados["ganhos"]["kp"] == pytest.approx(2.0)
    assert {m["chave"] for m in dados["metricas"]} >= {"tr", "tp", "mp", "ts", "vc", "ess"}
    assert (sessao.pasta.caminho / "scpi_transcricao.log").exists()
    assert sessao.resultados[(7, "1.2")].numero == 1


def test_fluxo_da_bancada_ate_a_tabela(sessao, capsys):
    for linha in ("a", "caso 1.2", "a", "ajustar", "caso 1.3", "a", "tabela", "grafico 1", "lgr", "status"):
        sessao.executar(linha)
    saida = capsys.readouterr().out
    assert "ERRO" not in saida and "| R2 = 10 kΩ |" in saida and "¹ sem sobressinal" in saida
    arquivos = {p.name for p in sessao.pasta.caminho.iterdir()}
    assert {"tabelas_exp7.md", "grafico_exp7_tabela1.png", "lgr_exp7_c1.3_R2.png"} <= arquivos
    assert sessao.resultados[(7, "1.2")].ganhos_id["kp"] == pytest.approx(2.0, rel=0.1)
    tabelas = (sessao.pasta.caminho / "tabelas_exp7.md").read_text(encoding="utf-8")
    assert "**Tabela 6**" in tabelas and "Regime e ganhos" in tabelas


def test_componente_real_vale_para_todo_caso_com_o_mesmo_nominal(sessao, capsys):
    sessao.executar("caso 4.1")
    sessao.executar("set L 68m")
    assert sessao.comp().L == 68e-3 and sessao.comp(sessao.roteiro.caso("5.2")).L == 68e-3
    sessao.executar("set R2 1.1k")
    assert sessao.comp().R2 == 1100.0 and sessao.comp(sessao.roteiro.caso("4.2")).R2 == 10e3
    sessao.executar("set RL 9.9k")                                    # apelido do roteiro para R1
    assert sessao.comp().R1 == 9900.0
    sessao.executar("reset")
    assert sessao.comp() == sessao.caso.comp
    sessao.executar("set R9 1k")
    assert "ERRO: 'componente desconhecido" in capsys.readouterr().out


def test_calcular_reanalisa_a_ultima_captura_como_outro_caso(sessao):
    sessao.executar("adquirir")                                       # caso 1.1 selecionado por engano
    assert _pastas(sessao) == ["01_e7_c1.1"]
    sessao.executar("caso 3.1")
    sessao.executar("calcular")
    assert _pastas(sessao) == ["01_e7_c3.1"] and sessao.numero == 1
    assert list(sessao.resultados) == [(7, "3.1")]


class _ScopeSemSinal(Osciloscopio):
    def conectar(self):
        return "sem sinal"

    def adquirir(self, canais=("CH1", "CH2")):
        t = np.arange(2500) * 2e-6
        return Captura(t, {"CH1": np.zeros(2500), "CH2": np.zeros(2500)}, origem="teste")


def test_erro_na_analise_nao_perde_a_captura_nem_derruba_a_sessao(sessao, capsys):
    bom, sessao.scope = sessao.scope, _ScopeSemSinal()
    assert sessao.executar("adquirir")
    saida = capsys.readouterr().out
    assert "ERRO: CH1 não tem uma onda quadrada" in saida and "gravada sem análise" in saida
    assert (sessao.pasta.caminho / "01_sem_analise" / "captura.npz").exists()
    assert "Traceback" not in saida and "Traceback" in sessao.ultimo_erro
    sessao.scope = bom
    sessao.executar("adquirir")
    assert _pastas(sessao) == ["01_sem_analise", "02_e7_c1.1"]


def test_comandos_invalidos_so_avisam(tmp_path, capsys):
    s = SessaoLab(tmp_path, abrir_figuras=False)
    for linha in ("adquirir", "xyz", "caso 9.9", "calcular", "exp 3", ""):
        assert s.executar(linha)
    saida = capsys.readouterr().out
    assert "nenhum osciloscópio conectado" in saida and "comando desconhecido" in saida
    assert not s.executar("quit") and not s.pasta.caminho.exists()     # nada gravado, nenhuma pasta criada


def test_troca_de_roteiro_e_teoria(tmp_path, capsys):
    s = SessaoLab(tmp_path, abrir_figuras=False)
    s.executar("exp 6")
    s.executar("caso 2.2")
    saida = capsys.readouterr().out
    assert "50 Hz" in saida and "RLC + P" in saida and "ζ" in saida and "Tela sugerida" in saida
    assert s.roteiro.numero == 6 and s.caso.id == "2.2"


def test_diagnostico_abre_e_fecha_a_janela_da_transcricao(sessao, monkeypatch, capsys):
    abertos = []

    class Janela:
        def __init__(self, comando, **kw):
            self.comando, self.encerrada = comando, False
            abertos.append(self)

        def poll(self):
            return 0 if self.encerrada else None

        def terminate(self):
            self.encerrada = True

    monkeypatch.setattr(cli.subprocess, "Popen", Janela)
    sessao.executar("set diagnostico on")
    assert sessao.diagnostico and len(abertos) == 1
    comando = abertos[0].comando
    assert comando[:3] == ["powershell.exe", "-NoExit", "-Command"]
    assert "Get-Content" in comando[3] and "-Wait" in comando[3] and "scpi_transcricao.log" in comando[3]
    sessao.scope = _ScopeSemSinal()
    sessao.executar("adquirir")
    assert "Traceback" in capsys.readouterr().out                     # com diagnóstico, o rastro aparece
    sessao.executar("set diagnostico off")
    assert abertos[0].encerrada and not sessao.diagnostico


def test_comando_do_terminal_de_diagnostico_e_puro(tmp_path):
    comando = comando_terminal_diagnostico(tmp_path / "sessao_x" / "scpi_transcricao.log")
    assert "sessao_x" in comando[3] and "-Tail 20" in comando[3] and "-Encoding UTF8" in comando[3]


def test_main_roda_comandos_e_sai(tmp_path, capsys):
    assert cli.main(["--sim", "--sem-abrir", "--pasta", str(tmp_path), "-c", "caso 2.1; a; status"]) == 0
    saida = capsys.readouterr().out
    assert "caso 2.1 (C2 = 1 nF)" in saida and "capturas: 1" in saida
