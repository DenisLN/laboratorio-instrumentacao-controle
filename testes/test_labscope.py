"""Testes da biblioteca com sinais sintéticos. Rodar da raiz: python -m pytest"""
import math

import numpy as np
import pytest

from labscope import ajuste, metricas, modelo, relatorio, sinais, tek


# ---------------------------------------------------------------- tek
def _csv_tek(caminho, t, v):
    meta = [("Record Length", f"{len(t):e}"), ("Sample Interval", "2.000000e-05"), ("Source", "CH1")]
    with open(caminho, "w") as fh:
        for k, (ti, vi) in enumerate(zip(t, v)):
            a, b = meta[k] if k < len(meta) else ("", "")
            fh.write(f"{a},{b},,{ti:17.12f},{vi:10.5f},\n")


def test_ler_csv_separa_metadados_e_amostras(tmp_path):
    t = np.arange(10) * 2e-5
    _csv_tek(tmp_path / "F0000CH1.CSV", t, np.sin(t))
    tl, vl, meta = tek.ler_csv(tmp_path / "F0000CH1.CSV")
    assert np.allclose(tl, t) and len(vl) == 10
    assert meta["Sample Interval"] == 2e-5 and meta["Source"] == "CH1"


def test_ler_captura_alinha_canais_de_tamanhos_diferentes(tmp_path):
    t = np.arange(100) * 2e-5
    _csv_tek(tmp_path / "F0003CH1.CSV", t, t * 0 + 1)
    _csv_tek(tmp_path / "F0003CH2.CSV", t[5:90], t[5:90] * 0 + 2)
    cap = tek.ler_captura(tmp_path)
    assert len(cap.t) == 85 and cap.t[0] == pytest.approx(t[5])
    assert set(cap.canais) == {"CH1", "CH2"} and cap["CH2"][0] == 2
    assert cap.dt == pytest.approx(2e-5)


def test_exportar_ngscope_gera_cabecalho_time(tmp_path):
    t = np.arange(20) * 2e-5
    _csv_tek(tmp_path / "F0000CH1.CSV", t, t)
    _csv_tek(tmp_path / "F0000CH2.CSV", t, -t)
    saida = tek.exportar_ngscope(tmp_path)
    linhas = (saida / "combinado.csv").read_text().splitlines()
    assert linhas[0] == "Time,CH1,CH2" and len(linhas) == 21


def test_capturas_lista_pastas_all(tmp_path):
    (tmp_path / "ALL0002").mkdir()
    (tmp_path / "ALL0010").mkdir()
    (tmp_path / "BMP").mkdir()
    assert list(tek.capturas(tmp_path)) == [2, 10]


# ---------------------------------------------------------------- sinais
def _quadrada(n=2500, dt=2e-5, f=50.0, t0=-0.0252):
    t = t0 + dt * np.arange(n)
    return t, np.where(((t - 0.001) % (1 / f)) < 0.5 / f, 0.5, -0.5)


def test_bordas_ignora_ruido_em_cima_do_nivel():
    t, v = _quadrada()
    limpo, sobe = sinais.bordas(v)
    ruidoso = v.copy()
    i = limpo[0]
    ruidoso[i:i + 6] = [0.02, -0.03, 0.04, -0.01, 0.03, 0.5]   # repique na transição
    idx, sobe2 = sinais.bordas(ruidoso)
    assert len(idx) == len(limpo) and list(sobe2) == list(sobe)
    assert np.sum(np.diff(np.sign(ruidoso[i - 1:i + 6])) != 0) > 1   # limiar simples contaria mais


def test_bordas_devolve_primeira_amostra_do_lado_novo():
    v = np.array([-1, -1, -1, 1, 1, 1, -1, -1.0])
    idx, sobe = sinais.bordas(v)
    assert list(idx) == [3, 6] and list(sobe) == [True, False]


def test_quadrada_recupera_periodo_e_patamares():
    t, v = _quadrada(f=20.0, dt=5e-5)
    q = sinais.quadrada(t, v)
    assert q.frequencia == pytest.approx(20.0, rel=1e-3)
    assert (q.baixo, q.alto) == (-0.5, 0.5) and q.amplitude == 0.5
    assert np.mean(q(t) == v) > 0.995


def test_media_movel_preserva_patamar():
    assert np.allclose(sinais.media_movel(np.ones(50), 2e-5, 6e-5)[5:-5], 1.0)


# ---------------------------------------------------------------- modelo
def test_malha_fechada_rc_com_p_tem_polo_em_1_mais_kp_sobre_rc():
    num, den = modelo.malha_fechada(*modelo.serie(modelo.p(2.0), modelo.rc(1e3, 1e-6)))
    assert modelo.polos(den)[0] == pytest.approx(-3000)
    assert modelo.ganho_dc(num, den) == pytest.approx(2 / 3)


def test_carga_em_paralelo_reduz_ganho_estatico():
    assert modelo.ganho_dc(*modelo.rc(1e3, 1e-6, carga=10e3)) == pytest.approx(10 / 11)
    assert modelo.ganho_dc(*modelo.rlc(100, 68e-3, 1e-6, carga=10e3)) == pytest.approx(100 / 101)


def test_esr_acrescenta_zero_e_soma_na_resistencia():
    num, den = modelo.rc(1e3, 1e-6, esr=10.0)
    assert np.allclose(num, [10e-6, 1.0]) and np.allclose(den, [1010e-6, 1.0])
    assert np.allclose(modelo.rlc(100, 68e-3, 1e-6)[1], [68e-9, 1e-4, 1.0])
    assert modelo.ganho_dc(*modelo.rlc(100, 68e-3, 1e-6, carga=10e3, esr=5.0)) == pytest.approx(100 / 101)


def test_simular_reproduz_degrau_analitico_de_segunda_ordem():
    z, wn = 0.2, 3000.0
    num, den = [wn ** 2], [1, 2 * z * wn, wn ** 2]
    t, y = modelo.resposta_degrau(num, den)
    wd = wn * math.sqrt(1 - z ** 2)
    exato = 1 - np.exp(-z * wn * t) * (np.cos(wd * t) + z * wn / wd * np.sin(wd * t))
    assert np.max(np.abs(y - exato)) < 1e-6


def test_metricas_degrau_batem_com_formulas_classicas():
    z, wn = 0.2, 3000.0
    m = modelo.metricas_degrau([wn ** 2], [1, 2 * z * wn, wn ** 2])
    f = metricas.segunda_ordem(z, wn)
    for k in ("tr", "tp", "mp"):
        assert m[k] == pytest.approx(f[k], rel=2e-3)
    assert metricas.zeta_de_mp(m["mp"]) == pytest.approx(z, rel=2e-3)


def test_dominante_e_routh():
    den = np.poly([-12000, -400 + 3000j, -400 - 3000j])
    d = modelo.dominante(np.roots(den))
    assert d["sigma"] == pytest.approx(400) and d["wd"] == pytest.approx(3000)
    assert np.all(modelo.routh(den) > 0)
    assert np.any(modelo.routh([1, 1, 2, 24]) < 0)        # s³+s²+2s+24 é instável
    assert "tau" in modelo.dominante(np.array([-100.0, -2000.0]))


# ---------------------------------------------------------------- metricas
def test_degrau_de_primeira_ordem():
    tau = 2e-3
    t = np.arange(0, 20e-3, 1e-6)
    m = metricas.degrau(t, 1 - np.exp(-t / tau), 0.0, 1.0)
    assert m["tau"] == pytest.approx(tau, rel=1e-3)
    assert m["tr"] == pytest.approx(math.log(9) * tau, rel=1e-3)
    assert m["ts"] == pytest.approx(math.log(50) * tau, rel=1e-3)
    assert m["mp"] == 0


def test_degrau_sem_acomodar_devolve_ts_nan():
    t = np.arange(0, 2e-3, 1e-6)
    assert math.isnan(metricas.degrau(t, 1 - np.exp(-t / 2e-3), 0.0, 1.0)["ts"])


def _malha_pi(kp=0.5, ki=1e4, R1=1e3, C=4e-6):
    return modelo.malha_fechada(*modelo.serie(modelo.pi(kp, ki), modelo.rc(R1, C)))


def test_medir_degraus_em_onda_quadrada_usa_subidas_e_descidas():
    t, ref = _quadrada()
    ft = modelo.malha_fechada(*modelo.serie(modelo.p(1.0), modelo.rc(1e3, 1e-6)))
    _, y = modelo.resposta_periodica(*ft, t, ref)
    m = metricas.medir_degraus(t, ref, y)
    assert m["n"] == 4
    assert m["yf"] == pytest.approx(0.25, rel=1e-2)
    assert m["tau"] == pytest.approx(0.5e-3, abs=2e-5)        # resolução de 1 amostra


def test_decremento_log_recupera_polos_mesmo_com_zero():
    num, den = _malha_pi()
    d = modelo.dominante(modelo.polos(den))
    t, y = modelo.resposta_degrau(num, den)
    m = metricas.decremento_log(t, y, 1.0, minimo=1e-3)
    assert m["zeta"] == pytest.approx(d["zeta"], rel=0.02)
    assert m["wd"] == pytest.approx(d["wd"], rel=0.01)
    # o zero do PI aumenta o sobressinal, então zeta = f(Mp) erra bem mais
    erro_mp = abs(metricas.zeta_de_mp(metricas.degrau(t, y, 0.0, 1.0)["mp"]) - d["zeta"])
    assert erro_mp > 3 * abs(m["zeta"] - d["zeta"])


# ---------------------------------------------------------------- ajuste
def test_ajuste_recupera_capacitor_de_formas_de_onda():
    t, ref = _quadrada()
    ft = lambda C: modelo.malha_fechada(*modelo.serie(modelo.p(1.0), modelo.rc(1e3, C)))
    _, y = modelo.resposta_periodica(*ft(4.2e-6), t, ref)
    (c_uF,), erro = ajuste.minimizar(lambda x: ajuste.erro_quadratico(ft(x[0] * 1e-6), [(t, ref, y)]),
                                     [1.0], [0.5])
    assert c_uF == pytest.approx(4.2, rel=5e-3) and erro < 1e-6


# ---------------------------------------------------------------- relatorio
def test_tabela_markdown_pt_br():
    assert relatorio.ms(1.234e-3) == "1,23 ms" and relatorio.pct(0.3114) == "31,1 %"
    assert relatorio.num(float("nan")) == "–"
    assert relatorio.tabela(["a", "b"], [[1, 2]]).splitlines() == ["| a | b |", "|---|---|", "| 1 | 2 |"]
