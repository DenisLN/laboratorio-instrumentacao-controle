"""Métricas em classes: previsão pelo modelo e medida em capturas sintéticas."""
import math

import numpy as np
import pytest

from labscope import metricas
from labscope.captura import Captura
from labscope.instrumentos import OsciloscopioSimulado
from labscope.medidas import (METRICAS, PADRAO, FatorAmortecimento, FatorAmortecimentoDecremento, Metrica,
                              RespostaMedida, RespostaTeorica, TempoSubida, ganhos)
from labscope.roteiros import Experimento6, Experimento7

E6, E7 = Experimento6(), Experimento7()


def _captura(roteiro, id, s_div, ruido=0.0, quantizar=False, offset=0.0):
    """Captura sintética do caso; por padrão a resposta exata, sem ruído nem quantização."""
    caso = roteiro.caso(id)
    cap = OsciloscopioSimulado(lambda: caso.malha(carga=True), roteiro.frequencia, s_div=s_div, ruido=ruido,
                               quantizar=quantizar).adquirir()
    for canal in cap.canais:
        cap.canais[canal] = cap.canais[canal] + offset
    return caso, cap


def _medida(roteiro, id, s_div, **kw):
    caso, cap = _captura(roteiro, id, s_div, **kw)
    teoria = RespostaTeorica(caso.malha(carga=True), roteiro.amplitude)
    return teoria, RespostaMedida(cap, roteiro.frequencia, teoria.subida, caso.malha().controlador.integral,
                                  suavizacao=min(60e-6, teoria.degrau["tr"] / 8))


# ---------------------------------------------------------------- teoria
def test_primeira_ordem_usa_as_formulas_e_subida_10_90():
    t = RespostaTeorica(E6.caso("1.2").malha())
    assert t.degrau["tau"] == pytest.approx(0.5e-3) and t.degrau["tr"] == pytest.approx(1.1e-3)
    assert t.subida == "10-90" and math.isnan(t.degrau["tp"]) and t.ganho_dc == pytest.approx(0.5)


def test_segunda_ordem_padrao_usa_as_formulas():
    t = RespostaTeorica(E6.caso("2.2").malha())
    esperado = metricas.segunda_ordem(t.dominante["zeta"], t.dominante["wn"])
    assert t.subida == "0-100" and t.degrau["mp"] == pytest.approx(esperado["mp"])


def test_pid_sem_sobressinal_passa_para_10_90():
    t = RespostaTeorica(E7.caso("1.3").malha())
    assert t.subida == "10-90" and t.degrau["mp"] == 0 and math.isnan(t.degrau["tp"])
    assert RespostaTeorica(E7.caso("1.2").malha()).subida == "0-100"


def test_malha_instavel_nao_tem_previsao():
    caso = E6.caso("6.2")
    t = RespostaTeorica(caso.malha(caso.comp.trocar(R1=100.0)))
    assert not t.estavel and math.isnan(t.degrau["ts"])


# ---------------------------------------------------------------- medida
@pytest.mark.parametrize("roteiro,id,s_div", [(E7, "1.1", 1e-3), (E7, "1.2", 1e-3), (E7, "2.1", 250e-6),
                                              (E7, "4.2", 5e-3), (E6, "4.2", 1e-3), (E6, "4.3", 500e-6)])
def test_janela_com_uma_borda_so_recupera_o_modelo(roteiro, id, s_div):
    teoria, m = _medida(roteiro, id, s_div)
    assert m.bordas == 1 and m.degrau["n"] == 1 and math.isnan(m.frequencia)
    for k, tol in (("tr", 0.05), ("tp", 0.05), ("mp", 0.05), ("ts", 0.12)):
        assert m.degrau[k] == pytest.approx(teoria.degrau[k], rel=tol), k
    assert m.vc == pytest.approx(0.5, abs=0.01) and m.erro_regime == pytest.approx(0, abs=0.02)
    assert m.residuo(teoria) < 5e-3


def test_janela_com_varios_meios_periodos_da_o_mesmo_que_a_de_uma_borda():
    _, uma = _medida(E6, "4.2", 500e-6)
    _, varias = _medida(E6, "4.2", 5e-3)
    assert varias.bordas >= 4 and varias.degrau["n"] >= 3
    assert varias.frequencia == pytest.approx(50.0, rel=1e-3)
    assert varias.degrau["mp"] == pytest.approx(uma.degrau["mp"], abs=0.02)
    assert varias.degrau["tp"] == pytest.approx(uma.degrau["tp"], rel=0.05)


def test_salto_da_acao_derivativa_nao_contamina_o_regime_anterior():
    """Com K_d grande a saída salta na borda; V_c tem de sair da excursão inteira."""
    teoria, m = _medida(E7, "1.3", 250e-6)
    assert m.vc == pytest.approx(0.5, abs=0.01)
    assert m.degrau["tr"] == pytest.approx(teoria.degrau["tr"], rel=0.08)
    assert m.degrau["mp"] == 0 and math.isnan(m.degrau["tp"])


def test_vc_e_amplitude_nao_dependem_do_offset_do_gerador():
    _, m = _medida(E6, "1.2", 1e-3, offset=0.2)
    assert m.amplitude == pytest.approx(0.5, abs=0.005)
    assert m.vc == pytest.approx(0.5 * 10 / 21, abs=0.005)       # Kp·G(0)/(1 + Kp·G(0)) com a carga
    assert m.erro_regime == pytest.approx(1 - 10 / 21, abs=0.01)


def test_ruido_e_quantizacao_de_bancada_ficam_dentro_da_tolerancia():
    teoria, m = _medida(E7, "1.2", 500e-6, ruido=3e-3, quantizar=True)
    assert m.lsb == pytest.approx(8e-3)
    for chave in ("tr", "tp", "mp", "ts", "vc"):
        metrica = METRICAS[chave]
        assert metrica.comparar(metrica.medir(m), metrica.prever(teoria)).ok, chave


def test_ch1_sem_onda_quadrada_explica_o_problema():
    t = np.arange(2500) * 2e-6
    plano = Captura(t, {"CH1": np.full(2500, 0.5), "CH2": np.zeros(2500)})
    with pytest.raises(ValueError, match="onda quadrada"):
        RespostaMedida(plano, 10.0).degrau
    _, cap = _captura(E7, "1.2", 500e-6)
    trocados = Captura(cap.t, {"CH1": cap["CH1"], "CH2": -cap["CH2"]})
    with pytest.raises(ValueError, match="não acompanha"):
        RespostaMedida(trocados, 10.0).degrau


def test_janela_curta_demais_nao_inventa_tempo_de_assentamento():
    _, m = _medida(E7, "4.2", 500e-6)        # Ts previsto de 25 ms em uma janela de 4,5 ms
    assert not m.acomodou and math.isnan(m.degrau["ts"])


# ---------------------------------------------------------------- classes de métrica
def test_metrica_e_abstrata_e_as_concretas_tem_chave_unica():
    with pytest.raises(TypeError):
        Metrica()
    assert len(METRICAS) == len(PADRAO) and {"tr", "tp", "mp", "ts", "vc", "ess", "zeta", "wn", "wd"} <= set(METRICAS)


def test_comparacao_respeita_tolerancia_relativa_e_absoluta():
    tr = TempoSubida()
    assert tr.comparar(1.1e-3, 1.0e-3).ok and not tr.comparar(1.5e-3, 1.0e-3).ok
    assert tr.comparar(math.nan, 1.0e-3).ok is None
    ess = METRICAS["ess"]
    assert ess.comparar(0.02, 0.0).ok and not ess.comparar(0.10, 0.0).ok


def test_modais_so_se_aplicam_com_polos_complexos():
    primeira, segunda, pid = (RespostaTeorica(c.malha()) for c in (E6.caso("1.1"), E6.caso("2.1"), E7.caso("1.2")))
    zeta = FatorAmortecimento()
    assert not zeta.aplicavel(primeira) and zeta.aplicavel(segunda) and zeta.aplicavel(pid)
    assert zeta.prever(segunda) == pytest.approx(segunda.dominante["zeta"])
    # ζ = f(Mp) só vale sem zeros; o decremento logarítmico vale sempre
    assert zeta.julgavel(segunda) and not zeta.julgavel(pid)
    assert FatorAmortecimentoDecremento().julgavel(pid) and FatorAmortecimentoDecremento.chave == "zeta_dl"


def test_metodo_do_roteiro_e_decremento_medem_o_mesmo_no_segunda_ordem():
    teoria, m = _medida(E6, "2.2", 1e-3)
    assert FatorAmortecimento().medir(m) == pytest.approx(teoria.dominante["zeta"], rel=0.05)
    assert METRICAS["wd"].medir(m) == pytest.approx(teoria.dominante["wd"], rel=0.03)
    assert METRICAS["zeta_dl"].medir(m) == pytest.approx(teoria.dominante["zeta"], rel=0.12)
    assert METRICAS["wn_dl"].medir(m) == pytest.approx(teoria.dominante["wn"], rel=0.03)


def test_identificacao_recupera_os_ganhos_do_pid():
    caso, cap = _captura(E7, "1.2", 500e-6, ruido=2e-3, quantizar=True)
    malha = caso.malha(carga=True)
    m = RespostaMedida(cap, 10.0, integral=True)
    kp, ki, kd = ganhos(malha)
    teoria = RespostaTeorica(malha)
    assert kp.medir(m) == pytest.approx(2.0, rel=0.05) and ki.medir(m) == pytest.approx(1e4, rel=0.05)
    assert kd.medir(m) == pytest.approx(1e-4, rel=0.15) and kd.prever(teoria) == pytest.approx(1e-4)
    assert not ganhos(E6.caso("1.1").malha())[1].aplicavel(RespostaTeorica(E6.caso("1.1").malha()))   # P não tem Ki


@pytest.mark.parametrize("t0,entrada", [(-50, (-0.5, 0.5, 0.1, 0.0)),         # borda a 2 % do início do registro
                                        (-250, (-0.5, 0.5, 0.1, -0.05)),      # só uma borda de descida
                                        (-250, (-0.2, 0.8, 0.1, 0.0))])       # gerador com offset
def test_medida_aguenta_telas_fora_do_padrao(t0, entrada):
    from labscope import modelo, sinais
    malha = E7.caso("1.2").malha(carga=True)
    teoria = RespostaTeorica(malha)
    t = 4e-6 * (t0 + np.arange(2500))
    u, y = modelo.resposta_a_quadrada(*malha.ft(), t, sinais.Quadrada(*entrada), 3)
    m = RespostaMedida(Captura(t, {"CH1": u, "CH2": y}), 10.0, teoria.subida, integral=True)
    assert m.bordas == 1 and m.amplitude == pytest.approx(0.5) and m.vc == pytest.approx(0.5, abs=0.003)
    for k in ("tr", "tp", "mp", "ts"):
        assert m.degrau[k] == pytest.approx(teoria.degrau[k], rel=0.02), k
    assert m.oscilacao["wd"] == pytest.approx(teoria.dominante["wd"], rel=0.02)
