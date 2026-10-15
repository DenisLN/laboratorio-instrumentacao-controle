"""Experimento 9: roteiro, componentes do circuito, medida da resposta em malha fechada e a sessão."""
import math

import numpy as np
import pytest

from labscope.instrumentos import ControleSimulado
from labscope.motor import MotorCC, ProjetoPD, ProjetoPI, ProjetoPID, RespostaMalha, previsao
from labscope.motor import componentes as Cp
from labscope.roteiros import ROTEIROS, Experimento9
from labscope.sessao.cli import SessaoLab
from labscope.sessao.controle import SessaoControle
from labscope.sessao.latex import exportar

MOTOR = MotorCC(K=211.2, Kt=0.00501, tau=0.494, K1=9.1e6)


def _sessao(tmp_path):
    s = SessaoLab(str(tmp_path), abrir_figuras=False, experimento=9)
    s.executar("modelo ref2022")
    s.executar("conectar sim")
    return s


# ---------------------------------------------------------------- roteiro
def test_roteiro_segue_a_folha():
    r = ROTEIROS[9]()
    assert isinstance(r, Experimento9) and r.familia == "controle"
    assert [c.id for c in r.casos()] == ["1.1", "2.1", "3.1", "3.2", "4.1", "4.2"]
    assert [c.vg for c in r.casos()] == [0, 0, 6, 9, 5, 8]
    assert [c.malha for c in r.casos()] == ["pi", "pd", "pi", "pi", "pd", "pd"]
    assert [t.numero for t in r.tabelas()] == [1, 2, 3, 4] and r.tabelas()[0].metricas == ("tau", "tr", "tp", "mp", "ts")
    assert (r.referencia_rpm, r.referencia_graus, r.mp, r.fator_tr) == (1000.0, 60.0, 0.20, 0.85)


# ---------------------------------------------------------------- componentes
def test_pi_do_circuito_reproduz_os_ganhos():
    c = Cp.dimensionar(1.112, 2.251, 0.0, 10e-6)
    assert c["tipo"] == "PI" and c["R"] == pytest.approx(44.42e3, rel=1e-3) and c["R2"] == pytest.approx(49.4e3, rel=1e-3)
    real = Cp.comerciais(c)["ganhos"]
    assert real["kp"] == pytest.approx(1.112, rel=0.1) and real["ki"] == pytest.approx(2.251, rel=0.1)


def test_pid_do_circuito_reproduz_os_ganhos():
    kp, ki, kd = 0.385, 0.2792, 0.06766
    c = Cp.dimensionar(kp, ki, kd, 10e-6)
    assert c["tipo"] == "PID" and c["R"] == pytest.approx(358.2e3, rel=1e-3) and c["R2"] == pytest.approx(117.2e3, rel=1e-3)
    assert c["C1"] == pytest.approx(577e-9, rel=2e-3)
    assert c["R2"] / c["R"] + c["C1"] / c["C2"] == pytest.approx(kp) and 1 / (c["R"] * c["C2"]) == pytest.approx(ki)
    assert c["R2"] * c["C1"] == pytest.approx(kd)
    with pytest.raises(ValueError, match="não cabe"):
        Cp.dimensionar(0.1, 1.0, 1.0)


def test_pd_do_circuito_e_serie_comercial():
    c = Cp.dimensionar(0.57, 0.0, 0.0048)
    assert c["tipo"] == "PD" and c["R2"] / c["R"] == pytest.approx(0.57) and c["R2"] * c["C1"] == pytest.approx(0.0048)
    assert Cp.comercial(44.4e3) == pytest.approx(43e3) and Cp.comercial(0.577e-6, Cp.SERIE_CAPACITORES) == pytest.approx(0.68e-6)
    assert 1 / (0.0448 * Cp.escolher_c2(0.0448)) <= 1e6 and Cp.escolher_c2(2.25) == pytest.approx(0.47e-6)


def test_ganhos_eletricos_dividem_pelo_sensor_so_na_posicao():
    pi, pd = ProjetoPI(MOTOR), ProjetoPD(MOTOR, tp=1.6)
    assert Cp.ganhos_eletricos(pi, 0.1) == pi.ganhos()
    assert Cp.ganhos_eletricos(pd, 0.1)["kp"] == pytest.approx(pd.ganhos()["kp"] / 0.1)


# ---------------------------------------------------------------- previsão e medida
def test_previsao_do_pi_bate_com_o_projeto():
    p = ProjetoPI(MOTOR)
    prev = previsao(p)
    assert prev["tr"] == pytest.approx(0.85 * 2.2 * 0.494, rel=0.01) and prev["mp"] == 0.0 and math.isnan(prev["tp"])
    assert prev["ess"] == pytest.approx(0.0, abs=1e-3)


def test_pd_com_carga_deixa_erro_e_o_pid_elimina():
    pd = ProjetoPD(MOTOR, tp=1.6, ig=50e-6, reducao=30.0)
    pid = ProjetoPID(MOTOR, tp=1.6, ig=50e-6, reducao=30.0)
    assert previsao(pd)["ess"] == pytest.approx(pd.erro_com_carga() * -1, rel=0.02) and abs(previsao(pd)["ess"]) > 0.2
    assert abs(previsao(pid)["ess"]) < 0.01


def test_medida_na_captura_simulada_bate_com_a_previsao():
    p = ProjetoPD(MOTOR, tp=1.6)
    scope = ControleSimulado(p, v_por_unidade=0.1, s_div=0.5, ruido=0.0, v_div=(2.0, 2.0))
    m = RespostaMalha(scope.adquirir()).metricas
    prev = previsao(p)
    for k in ("tau", "tr", "tp", "ts"):
        assert m[k] == pytest.approx(prev[k], rel=0.1), k
    assert m["mp"] == pytest.approx(prev["mp"], abs=0.02) and m["ref"] == pytest.approx(6.0, rel=0.02)
    assert abs(m["ess"]) < 0.02


def test_captura_sem_resposta_nao_passa():
    p = ProjetoPI(MOTOR)
    cap = ControleSimulado(p, 0.005, 0.5, ruido=0.0).adquirir()
    cap.canais["CH2"] = np.zeros_like(cap.canais["CH2"])
    with pytest.raises(ValueError, match="não saiu do lugar"):
        RespostaMalha(cap).metricas


# ---------------------------------------------------------------- sessão
def test_sessao_do_exp9_mede_as_seis_linhas_e_retoma(tmp_path, capsys):
    s = _sessao(tmp_path)
    assert isinstance(s, SessaoControle)
    s.executar("caso 1.1")
    for _ in range(6):
        s.executar("a")
        s.executar("n") if s.caso.id != "4.2" else None
    saida = capsys.readouterr().out
    assert "ERRO" not in saida and set(s.capturas) == {c.id for c in s.roteiro.casos()}
    assert s.capturas["2.1"].valores()["mp"] == pytest.approx(0.19, abs=0.02)
    assert all(r.comparacoes() and all(ok in (True, None) for *_, ok in r.comparacoes()) for r in s.capturas.values())
    s.executar("tabela")
    assert (s.pasta.caminho / "tabelas_exp9.md").exists()
    pasta = s.pasta.caminho
    novo = SessaoLab(str(tmp_path / "outra"), abrir_figuras=False, experimento=9)
    novo.executar(f"retomar {pasta}")
    assert "ERRO" not in capsys.readouterr().out and set(novo.capturas) == set(s.capturas)
    assert novo.motor.K == pytest.approx(s.motor.K) and novo.igv == pytest.approx(s.igv)


def test_sessao_sem_modelo_pede_o_modelo(tmp_path, capsys):
    s = SessaoLab(str(tmp_path), abrir_figuras=False, experimento=9)
    s.executar("projeto")
    assert "sem modelo do motor" in capsys.readouterr().out


def test_modelo_digitado_e_tp_comum_as_linhas_de_carga(tmp_path, capsys):
    s = SessaoLab(str(tmp_path), abrir_figuras=False, experimento=9)
    s.executar("modelo K=211,2 Kt=5,01m tau=0,494 K1=9,1e6 igv=9u")
    s.executar("projeto todos")
    out = capsys.readouterr().out
    assert "ERRO" not in out and out.count("PID de posição") == 2
    g = [s._projeto(s.roteiro.caso(i)).ganhos() for i in ("4.1", "4.2")]
    assert g[0] == g[1]                        # o circuito montado é o mesmo; só Vg muda
    s.executar("set tipo pd")
    assert type(s._projeto(s.roteiro.caso("4.1"))) is ProjetoPD
    s.executar("set tp 3")
    assert s._projeto(s.roteiro.caso("2.1")).tp == 3.0


def test_trocar_de_exp9_para_exp8_zera_as_capturas(tmp_path, capsys):
    s = _sessao(tmp_path)
    s.executar("a")
    assert s.capturas
    s.executar("exp 8")
    assert s.roteiro.numero == 8 and not s.capturas and "ERRO" not in capsys.readouterr().out


def test_exportar_latex_do_exp9(tmp_path, capsys):
    s = _sessao(tmp_path)
    for _ in range(3):
        s.executar("a")
        s.executar("n")
    pasta = s.pasta.caminho
    exportar(pasta, tmp_path / "ativ", "ativ")
    for nome in ("tab/tabela1.tex", "tab/tabela3.tex", "tab/projeto.tex", "tex/plot_resposta1.tex", "tex/plot_lgr_2_1.tex",
                 "csv/tabela4.csv", "tex/cod9_componentes.tex"):
        assert (tmp_path / "ativ" / nome).exists(), nome
    assert r"\label{tab:tabela1}" in (tmp_path / "ativ/tab/tabela1.tex").read_text(encoding="utf-8")
