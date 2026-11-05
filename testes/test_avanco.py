"""Experimento 10: compensador avanço de fase, medida senoidal e a sessão."""
import json
import math

import numpy as np
import pytest

from labscope.captura import Captura
from labscope.circuitos import CompensadorAvanco, Inversor, MalhaFechada, PlantaRC
from labscope.medidas import PrevisaoSenoidal, RespostaSenoidal
from labscope.medidas.senoide import diferenca_fase, fase
from labscope.roteiros import ROTEIROS, ComponentesAvanco, Experimento10
from labscope.sessao.avanco import SessaoAvanco
from labscope.sessao.cli import SessaoLab


# ---------------------------------------------------------------- roteiro
def test_roteiro_segue_a_folha():
    r = ROTEIROS[10]()
    assert isinstance(r, Experimento10) and r.familia == "avanco"
    assert [c.id for c in r.casos()] == ["1.1"] + [f"2.{k}" for k in range(1, 7)] + ["3.1", "4.1", "5.1", "7.1"]
    assert [c.frequencia for c in r.casos() if c.tabela == 2] == [20, 100, 300, 1e3, 3e3, 5e3]
    assert [t.numero for t in r.tabelas()] == [1, 2, 3, 4, 5, 6, 7]
    assert r.tabelas()[5].casos == ("5.1",) and r.tabelas()[5].metricas == ("zeta", "wn", "wd")
    assert [c.senoide for c in r.casos() if c.tabela in (3, 5)] == [False, False]
    assert r.caso("1.1").amplitude == 1.0 and r.caso("4.1").amplitude == 0.5


def test_nomes_da_folha():
    assert ComponentesAvanco.chave("rc") == "Rc" and ComponentesAvanco.chave("L") == "L1"
    assert ComponentesAvanco.chave("cc") == "Cc"
    with pytest.raises(KeyError):
        ComponentesAvanco.chave("RL")


# ---------------------------------------------------------------- modelo
def test_compensador_tem_zero_antes_do_polo():
    c = CompensadorAvanco(R1=15e3, C1=47e-9, R2=390e3, C2=1e-9)
    assert c.kp == pytest.approx(26)
    assert c.zero == pytest.approx(-1 / 705e-6) and c.polo == pytest.approx(-1 / 390e-6)
    assert c.fase_maxima == pytest.approx(16.7, abs=0.1)
    w = c.w_max
    assert math.degrees(np.angle(c.gc()(1j * w))) == pytest.approx(c.fase_maxima, abs=1e-6)
    assert c.gc().ganho_dc() == pytest.approx(26) and c.gc()(1e12j) == pytest.approx(47, rel=1e-6)   # C1/C2


def test_malha_com_inversor_no_caminho_direto_inverte_a_saida():
    gc, g = CompensadorAvanco(15e3, 47e-9, 390e3, 1e-9), PlantaRC(1e3, 1e-6)
    m = MalhaFechada(gc, g, 10e3, False, Inversor(10e3, 10e3))
    laco = gc.gc() * g.ft()
    s = 1j * np.logspace(1, 6, 30)
    assert m.ft()(s) == pytest.approx(-laco(s) / (1 + laco(s)), rel=1e-9)
    assert m.ganho_dc() == pytest.approx(-26 / 27) and m.estavel()
    # polos reais: a malha RC com este compensador não fica subamortecida
    assert np.all(np.abs(m.polos().imag) < 1e-6)


def test_tabela_2_e_a_cadeia_compensador_mais_inversor():
    caso = Experimento10().caso("2.1")
    ft = caso.malha().ft()
    c = caso.comp
    esperado = (c.R2 / c.R1) * (c.R4 / c.R3)
    assert ft.ganho_dc() == pytest.approx(esperado)
    p = PrevisaoSenoidal(ft, 20.0, 1.0)
    assert p.vpp == pytest.approx(0.598, abs=1e-3) and p.fase == pytest.approx(49.3, abs=0.1)
    assert PrevisaoSenoidal(Experimento10().caso("1.1").malha().ft(), 500.0, 1.0).fase == pytest.approx(180)


# ---------------------------------------------------------------- medida senoidal
def test_fase_pelo_menor_arco():
    assert fase(-180.0) == 180.0 and fase(190.0) == pytest.approx(-170.0)
    assert diferenca_fase(179.0, -179.0) == pytest.approx(-2.0)


def test_mede_vpp_e_fase_com_frequencia_fora_da_nominal():
    t = np.arange(4000) * 2e-6
    f, rng = 1030.0, np.random.default_rng(1)
    u = np.sin(2 * np.pi * f * t) + rng.normal(0, 5e-3, len(t))
    y = 0.4 * np.sin(2 * np.pi * f * t - np.radians(120)) + 0.05 + rng.normal(0, 5e-3, len(t))
    m = RespostaSenoidal(Captura(t, {"CH1": u, "CH2": y}, {}, "teste"), 1000.0)
    assert m.frequencia == pytest.approx(f, rel=2e-3)
    assert m.vpp == pytest.approx(0.8, rel=0.01) and m.fase == pytest.approx(-120, abs=0.5)
    assert m.ganho == pytest.approx(0.4, rel=0.01)


def test_sem_senoide_em_ch1_e_erro():
    t = np.arange(1000) * 1e-5
    cap = Captura(t, {"CH1": np.zeros_like(t), "CH2": np.zeros_like(t)}, {}, "teste")
    with pytest.raises(ValueError, match="não tem uma senoide"):
        RespostaSenoidal(cap, 100.0).vpp


# ---------------------------------------------------------------- sessão
def _sessao(tmp_path):
    s = SessaoLab(str(tmp_path), abrir_figuras=False, experimento=10)
    s.executar("conectar sim")
    return s


def test_sessao_mede_senoides_e_degraus_e_retoma(tmp_path, capsys):
    s = _sessao(tmp_path)
    assert isinstance(s, SessaoAvanco)
    for caso in ("1.1", "2.3", "3.1", "4.1", "5.1"):
        s.executar(f"caso {caso}")
        s.executar("adquirir")
    saida = capsys.readouterr().out
    assert "ERRO" not in saida
    assert all(not r.conferir for r in s.resultados.values())
    assert s.resultados[(10, "1.1")].linha("fase").exp == pytest.approx(180, abs=1)
    assert s.resultados[(10, "4.1")].linha("vpp").exp == pytest.approx(0.96, abs=0.02)
    # degrau com a saída invertida: as métricas saem do −CH2
    rlc = s.resultados[(10, "5.1")]
    assert rlc.linha("mp").exp == pytest.approx(0.394, abs=0.03) and rlc.linha("vc").exp > 0
    assert s.resultados[(10, "3.1")].linha("tau") is not None

    s.executar("tabela")
    s.executar("grafico 2")
    s.executar("grafico 5")
    s.executar("caso 3.1")
    s.executar("lgr")
    saida = capsys.readouterr().out
    assert "ERRO" not in saida and "**Tabela 2**" in saida and "Compensador" in saida
    assert (s.pasta.caminho / "bode_exp10_tabela2.png").exists()
    dados = json.loads(next(s.pasta.caminho.glob("02_e10_c2.3")).joinpath("metricas.json").read_text(encoding="utf-8"))
    assert dados["circuito"] == "avanco" and dados["frequencia_nominal"] == 300

    outra = SessaoLab(str(tmp_path / "outra"), abrir_figuras=False, experimento=7)
    outra.executar(f"retomar {s.pasta.caminho}")
    assert isinstance(outra, SessaoAvanco) and len(outra.resultados) == 5 and outra.numero == 5


def test_set_com_nomes_da_folha_e_ajustar_recusado(tmp_path, capsys):
    s = _sessao(tmp_path)
    s.executar("caso 3.1")
    s.executar("Rc=980")
    assert s.comp().Rc == 980
    s.executar("ajustar")
    s.executar("caso 2.1")
    s.executar("lgr")
    saida = capsys.readouterr().out
    assert "não se aplica" in saida and "malhas fechadas" in saida


def test_voltar_ao_exp7_tira_o_simulador_da_senoide(tmp_path, capsys):
    s = _sessao(tmp_path)
    s.executar("caso 2.1")
    s.executar("adquirir")
    s.executar("exp 7")
    s.executar("caso 1.2")
    s.executar("adquirir")
    assert "ERRO" not in capsys.readouterr().out
    assert not s.resultados[(7, "1.2")].conferir
