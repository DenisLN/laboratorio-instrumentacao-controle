"""Circuitos como objetos e os roteiros que os montam."""
import numpy as np
import pytest

from labscope import modelo
from labscope.circuitos import (FT, Bloco, Controlador, ControladorIdeal, ControladorP, ControladorPI,
                                ControladorPID, EstagioAmpOp, InversorRealimentacao, MalhaFechada, Planta,
                                PlantaRC, PlantaRLC, Somador, capacitor, paralelo, resistor, serie)
from labscope.roteiros import ROTEIROS, Componentes, Experimento6, Experimento7, texto_si, valor_si

R, C, CF, L = 10e3, 1e-6, 10e-9, 68e-3      # valores da dedução (indutor medido)
S = 1j * 2000.0                              # ponto de teste no plano s


def _polos(malha):
    return np.sort_complex(malha.polos())


# ---------------------------------------------------------------- FT e impedâncias
def test_ft_desempacota_como_par_num_den():
    num, den = FT([2.0], [1e-3, 1.0])
    assert list(num) == [2.0] and list(den) == [1e-3, 1.0]


def test_serie_e_paralelo_de_impedancias():
    assert serie(resistor(1e3), capacitor(1e-6))(S) == pytest.approx(1e3 + 1 / (S * 1e-6))
    assert paralelo(resistor(1e3), capacitor(1e-6))(S) == pytest.approx(1 / (1 / 1e3 + S * 1e-6))


def test_malha_unitaria_soma_o_numerador_ao_denominador():
    t = FT([3.0], [1.0, 2.0]).malha()
    assert t.num == (3.0,) and t.den == (1.0, 5.0)
    assert FT([1.0], [1.0, 0.0, 0.0]).tipo == 2


# ---------------------------------------------------------------- classes abstratas
@pytest.mark.parametrize("abstrata", [Bloco, EstagioAmpOp, Controlador, Planta])
def test_classes_abstratas_nao_instanciam(abstrata):
    with pytest.raises(TypeError):
        abstrata()


def test_somador_e_inversor_tem_ganho_menos_um():
    assert Somador(R).ft().ganho_dc() == -1 and InversorRealimentacao(R).ft().ganho_dc() == -1
    assert InversorRealimentacao(R).carga == R


# ---------------------------------------------------------------- controladores
@pytest.mark.parametrize("ctrl", [ControladorP(R, 20e3), ControladorPI(R, 5e3, CF),
                                  ControladorPID(R, 10e3, 10e-9, 10e-9), ControladorPID(R, 100e3, 100e-9, 1e-9)])
def test_ganhos_em_formula_fechada_batem_com_as_impedancias(ctrl):
    """K_p + K_i/s + K_d·s tem de ser o mesmo Z_f/Z_in que sai do circuito."""
    esperado = ctrl.kp + ctrl.ki / S + ctrl.kd * S
    assert ctrl.gc()(S) == pytest.approx(esperado)
    assert ctrl.ft()(S) == pytest.approx(-esperado)        # o estágio é inversor
    assert Controlador.gc(ctrl)(S) == pytest.approx(esperado)


def test_ganhos_do_pid_do_roteiro():
    c = ControladorPID(R=10e3, R2=10e3, C2=10e-9, C1=10e-9)
    assert (c.kp, c.ki, c.kd) == pytest.approx((2.0, 1e4, 1e-4))
    assert isinstance(c, ControladorPI) and c.integral and not ControladorP(R, R).integral


def test_controlador_ideal_reproduz_o_de_amp_op():
    real = ControladorPID(R, 10e3, 10e-9, 10e-9)
    assert ControladorIdeal(**real.ganhos()).gc()(S) == pytest.approx(real.gc()(S))


# ---------------------------------------------------------------- malha fechada
@pytest.mark.parametrize("kp,esperado", [(0.5, -735 + 4639j), (1.0, -735 + 5373j), (2.0, -735 + 6601j)])
def test_rlc_com_p_tem_os_polos_da_deducao(kp, esperado):
    m = MalhaFechada(ControladorP(R, kp * R), PlantaRLC(100.0, L, C))
    assert _polos(m)[-1] == pytest.approx(esperado, abs=1.0)
    assert m.tipo == 0 and m.ganho_dc() == pytest.approx(kp / (1 + kp))


def test_rc_com_pi_e_rlc_com_pi_tem_os_polos_da_deducao():
    assert _polos(MalhaFechada(ControladorPI(R, R, CF), PlantaRC(1e3, C)))[-1] == pytest.approx(-1000 + 3000j, abs=1)
    p = _polos(MalhaFechada(ControladorPI(R, R, CF), PlantaRLC(1e3, L, C)))
    assert p[0] == pytest.approx(-13327, abs=1) and p[-1] == pytest.approx(-689 + 3250j, abs=1)


@pytest.mark.parametrize("ctrl,gc", [(ControladorP(R, 2 * R), modelo.p(2.0)),
                                     (ControladorPI(R, 4 * R, CF), modelo.pi(4.0, 1e4))])
@pytest.mark.parametrize("planta,g", [(PlantaRC(1e3, C), modelo.rc(1e3, C)),
                                      (PlantaRLC(1e3, L, C), modelo.rlc(1e3, L, C))])
def test_malha_em_classes_igual_a_das_funcoes(ctrl, gc, planta, g):
    num, den = modelo.malha_fechada(*modelo.serie(gc, g))
    assert MalhaFechada(ctrl, planta).ft()(S) == pytest.approx(np.polyval(num, S) / np.polyval(den, S))


def test_carga_do_inversor_muda_o_ganho_da_planta():
    m = MalhaFechada(ControladorP(R, R), PlantaRC(1e3, C))
    assert m.ganho_dc() == pytest.approx(0.5)
    assert m.com_carga().ft().den == pytest.approx((1.0, 2100.0))       # 1 + R1/R + Kp no lugar de 1 + Kp
    assert m.com_carga().planta_efetiva.ft().ganho_dc() == pytest.approx(10 / 11)


def test_pi_zera_o_erro_de_regime_e_p_nao():
    assert MalhaFechada(ControladorPI(R, R, CF), PlantaRC(1e3, C)).erro_regime() == pytest.approx(0)
    assert MalhaFechada(ControladorP(R, R), PlantaRC(1e3, C)).erro_regime() == pytest.approx(0.5)


def test_rlc_com_pi_e_r1_pequeno_e_instavel():
    """Routh: 1 + Kp > L·Ki/R1. Com R1 = 100 Ω é preciso Kp > 5,8."""
    assert not MalhaFechada(ControladorPI(R, R, CF), PlantaRLC(100.0, L, C)).estavel()
    assert MalhaFechada(ControladorPI(R, 70e3, CF), PlantaRLC(100.0, L, C)).estavel()
    assert np.any(MalhaFechada(ControladorPI(R, R, CF), PlantaRLC(100.0, L, C)).routh() < 0)


def test_pid_com_r2_de_100k_cancela_um_polo_com_um_zero():
    m = Experimento7().caso("1.3").malha()
    assert _polos(m) == pytest.approx([-5000, -1000]) and np.sort(m.zeros().real) == pytest.approx([-10000, -1000])


# ---------------------------------------------------------------- roteiros
def test_roteiros_tem_os_casos_das_tabelas():
    assert len(Experimento6().casos()) == 12 and len(Experimento7().casos()) == 14
    for roteiro in (r() for r in ROTEIROS.values()):
        ids = {c.id for c in roteiro.casos()}
        assert all(set(t.casos) <= ids for t in roteiro.tabelas())
        assert all(c.malha(carga=carga).estavel() for c in roteiro.casos() for carga in (False, True))


def test_caso_do_exp7_monta_o_circuito_certo():
    c = Experimento7().caso("5.2")
    assert (c.planta, c.ctrl, c.rotulo) == ("RLC", "PID", "C2 = 10 nF")
    assert (c.comp.R1, c.comp.L, c.comp.C1, c.comp.C2) == (10e3, 77e-3, 1e-9, 10e-9)
    assert c.malha().controlador.ganhos() == pytest.approx(dict(kp=1.1, ki=1e4, kd=1e-5))
    assert c.malha(c.comp.trocar(L=68e-3)).planta.L == 68e-3
    with pytest.raises(KeyError):
        Experimento7().caso("9.9")


def test_valores_si_e_apelidos():
    assert valor_si("10k") == 1e4 and valor_si("68m") == pytest.approx(0.068) and valor_si("4,7n") == pytest.approx(4.7e-9)
    assert texto_si(77e-3, "H") == "77 mH" and texto_si(100e-9, "F") == "100 nF"
    assert Componentes.chave("rl") == "R1" and Componentes.chave("Cf") == "C2" and Componentes.chave("CL") == "C"
    with pytest.raises(KeyError):
        Componentes.chave("R9")
