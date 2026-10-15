"""Experimento 8: modelo do motor, mínimos quadrados, medida da partida, projeto e a sessão."""
import json
import math

import numpy as np
import pytest

from labscope.captura import Captura
from labscope.instrumentos import MotorSimulado
from labscope.motor import DegrauMotor, Identificacao, Leitura, MotorCC, ProjetoPD, ProjetoPI, ProjetoPID, Reta
from labscope.roteiros import Experimento8
from labscope.sessao import cli
from labscope.sessao.cli import SessaoLab
from labscope.sessao.latex import exportar
from labscope.sessao.motor import SessaoMotor

MOTOR = MotorCC(K=350.0, Kt=0.003, tau=0.35, K1=500.0)


def _leitura(**valores):
    l = Leitura()
    for k, v in valores.items():
        l.definir(k, v, "teste")
    return l


# ---------------------------------------------------------------- modelo e mínimos quadrados
def test_roteiro_tem_as_duas_tabelas_da_folha():
    r = Experimento8()
    assert [c.id for c in r.casos()][:2] == ["1.1", "1.2"] and len(r.casos()) == 20
    assert [t.numero for t in r.tabelas()] == [1, 2] and r.caso("2.4").carga and r.caso("2.4").va == 4.0
    assert r.par(r.caso("1.7")).id == "2.7" and r.familia == "motor"


def test_reta_de_minimos_quadrados():
    r = Reta.ajustar([1, 2, 3, 4], [2.9, 5.1, 7.0, 9.0])
    assert r.a == pytest.approx(2.02) and r.b == pytest.approx(0.95) and 0.99 < r.r2 < 1
    assert r.a0 == pytest.approx(np.dot([1, 2, 3, 4], [2.9, 5.1, 7.0, 9.0]) / 30)
    assert r(10) == pytest.approx(21.15)
    with pytest.raises(ValueError):
        Reta.ajustar([1, 1], [2, 3])


def test_identificacao_tira_o_ponto_do_motor_parado_e_confere_kt():
    sem = {f"1.{k}": _leitura(va=k, vt=0.0 if k == 1 else 1.05 * k - 0.6, w=0.0 if k == 1 else 350 * k - 200,
                              tau=0.35) for k in range(1, 6)}
    com = {f"2.{k}": _leitura(va=k, vt=1.05 * k - 0.6, vtc=1.05 * k - 0.6 - 1.5 * 0.1 * k, ig=0.1 * k)
           for k in range(2, 6)}
    ident = Identificacao.de(sem, com)
    assert ident.kkt.excluidos == ("1.1",) and ident.KKt == pytest.approx(1.05)
    assert ident.K == pytest.approx(350) and ident.Kt == pytest.approx(0.003, rel=1e-3)
    assert ident.Kt_indireto == pytest.approx(ident.Kt, rel=1e-3)
    assert ident.K1Kt == pytest.approx(1.5) and ident.K1 == pytest.approx(500, rel=1e-3)
    assert ident.tau == pytest.approx(0.35) and ident.motor() == pytest.approx(ident.motor())
    assert ident.prever("w", 6) == pytest.approx(1900) and ident.prever("vtc", ig=0.2, vt=3.0) == pytest.approx(2.7)
    with pytest.raises(ValueError, match="falta K"):
        Identificacao.de({}).motor()


def test_funcoes_de_transferencia_do_motor():
    assert MOTOR.tacometro().ganho_dc() == pytest.approx(1.05)
    assert MOTOR.velocidade().polos() == pytest.approx([-1 / 0.35])
    assert MOTOR.posicao().tipo == 1 and MOTOR.posicao()(1j * 1e-9) == pytest.approx(-1j * 2100e9, rel=1e-6)


# ---------------------------------------------------------------- medida da partida
def _partida(va=4.0, carga=False, **kw):
    scope = MotorSimulado(**kw)
    scope.va, scope.carga = va, carga
    scope.v_div = (2.0, 1.0)
    return scope, scope.adquirir()


def test_partida_mede_va_vt_e_tau():
    scope, cap = _partida()
    m = DegrauMotor(cap)
    w, _, tau = scope.regime()
    assert m.tem_entrada and m.va == pytest.approx(4.0, abs=0.05)
    assert m.vt == pytest.approx(scope.Kt * w, rel=0.02) and m.tau == pytest.approx(tau, rel=0.03)
    assert m.acomodou and m.residuo() < 0.06


def test_partida_sem_ch1_estima_o_inicio_pela_curva():
    scope, cap = _partida(va=3.0)
    so_ch2 = Captura(cap.t, {"CH2": cap["CH2"]}, {"CH2": cap.meta["CH2"]}, cap.origem)
    m = DegrauMotor(so_ch2)
    assert not m.tem_entrada and math.isnan(m.va)
    assert m.tau == pytest.approx(scope.tau, rel=0.06) and m.degrau["t0"] == pytest.approx(0.0, abs=0.02)


def test_partida_com_carga_e_mais_rapida_e_mais_baixa():
    scope, cap = _partida(carga=True)
    w, ig, tau = scope.regime()
    m = DegrauMotor(cap)
    assert tau < scope.tau and m.tau == pytest.approx(tau, rel=0.04) and m.vt == pytest.approx(scope.Kt * w, rel=0.02)


def test_captura_sem_partida_e_recusada():
    t = np.arange(2500) * 1e-3
    cap = Captura(t, {"CH1": np.zeros(2500), "CH2": np.zeros(2500)})
    with pytest.raises(ValueError, match="não tem uma partida"):
        DegrauMotor(cap).degrau


# ---------------------------------------------------------------- projeto
def test_pi_cancela_o_polo_e_sobe_15_por_cento_mais_rapido():
    p = ProjetoPI(MOTOR, 1000, ig=0.3)
    g = p.ganhos()
    assert g["ki"] / g["kp"] == pytest.approx(1 / MOTOR.tau) and g["kd"] == 0
    m = p.metricas()
    assert m["tr"] == pytest.approx(0.85 * 2.2 * MOTOR.tau, rel=0.01) and m["mp"] == 0 and abs(m["ess"]) < 1e-6
    assert p.erro_com_carga() == 0 and all(ok for *_, ok in p.especificacao())
    s = p.simular()
    assert s["y"][-1] == pytest.approx(1000, rel=0.005) and p.malha_aberta(s["t"], s["t_carga"])[-1] < 950


def test_pd_atende_sobressinal_e_tp_mas_nao_rejeita_a_carga():
    pd = ProjetoPD(MOTOR, 60, tp=0.3, ig=0.3)
    m = pd.metricas()
    assert m["mp"] == pytest.approx(0.19, abs=0.005) and m["tp"] == pytest.approx(0.3, rel=0.02)
    assert pd.ganhos()["kd"] > 0 and pd.erro_com_carga() < -0.05
    assert [ok for *_, ok in pd.especificacao()] == [True, True, True, False, True]     # o último: |Va| ≤ 10 V
    pid = ProjetoPID(MOTOR, 60, tp=0.3, ig=0.3)
    assert pid.ganhos()["ki"] > 0 and pid.erro_com_carga() == 0 and all(ok for *_, ok in pid.especificacao()[:4])


def test_tp_padrao_e_tau_e_tp_lento_dispensa_a_acao_derivativa():
    assert ProjetoPD(MOTOR).tp == 0.35
    lento = ProjetoPD(MOTOR, tp=3.0)
    assert lento.ganhos()["kd"] < 1e-6 and lento.metricas()["mp"] <= 0.20


# ---------------------------------------------------------------- sessão
@pytest.fixture
def sessao(tmp_path):
    s = SessaoLab(tmp_path / "sessoes", abrir_figuras=False, experimento=8)
    s.executar("conectar sim")
    return s


def _medir_linha(s, id, anotar=True):
    s.executar(f"caso {id}")
    s.executar("a")
    w, ig, _ = s.scope.regime()
    if anotar:
        s.executar(f"ig={ig * 1e3:.1f}m" if s.caso.carga else f"w={w:.0f}")


def test_exp8_e_o_padrao_e_troca_de_classe_com_exp(tmp_path, capsys):
    assert isinstance(SessaoLab(tmp_path, abrir_figuras=False, experimento=8), SessaoMotor)
    s = SessaoLab(tmp_path, abrir_figuras=False)
    assert type(s) is SessaoLab and s.roteiro.numero == 7
    s.executar("exp 8")
    assert isinstance(s, SessaoMotor) and s.caso.id == "1.1"
    s.executar("exp 6")
    assert type(s) is SessaoLab and s.caso.id == "1.1"
    assert "ERRO" not in capsys.readouterr().out
    assert cli.main(["--sim", "--sem-abrir", "--pasta", str(tmp_path), "-c", "caso 1.4; a; status"]) == 0
    assert "Experimento 8, caso 1.4" in capsys.readouterr().out


def test_fluxo_da_bancada_do_motor(sessao, capsys):
    for k in range(1, 6):
        _medir_linha(sessao, f"1.{k}")
    for k in range(2, 6):
        _medir_linha(sessao, f"2.{k}")
    for linha in ("ajustar", "tabela", "grafico 1", "grafico 2", "grafico partidas", "grafico partidas 2",
                  "projeto", "casos", "comp", "status"):
        sessao.executar(linha)
    saida = capsys.readouterr().out
    assert "ERRO" not in saida and "CONFERIR" not in saida
    assert "#01  Exp. 8 · Tabela 1 · caso 1.1 (Va = 1 V)" in saida and "KKt  Vt × Va" in saida
    assert "NÃO ATENDE" in saida                                 # o PD com carga, como esperado
    arquivos = {p.name for p in sessao.pasta.caminho.iterdir()}
    assert {"tabelas_exp8.md", "grafico_exp8_tabela1.png", "grafico_exp8_tabela2.png", "partidas_exp8_tabela1.png",
            "projeto_exp8.png", "projeto_exp8.json", "anotacoes_exp8.json", "01_e8_c1.1"} <= arquivos
    assert {"captura.npz", "metricas.json", "painel.png"} <= {p.name for p in (sessao.pasta.caminho / "01_e8_c1.1").iterdir()}
    ident = sessao.identificacao()
    assert ident.K == pytest.approx(350, rel=0.02) and ident.Kt == pytest.approx(0.003, rel=0.03)
    assert ident.K1 == pytest.approx(500, rel=0.1) and ident.tau == pytest.approx(0.35, rel=0.05)
    projeto = json.loads((sessao.pasta.caminho / "projeto_exp8.json").read_text(encoding="utf-8"))
    assert set(projeto["projetos"]) == {"pi", "pd", "pi_carga", "pd_carga", "pid_carga"}


def test_anotacao_vale_mais_que_o_osciloscopio_e_pode_ser_apagada(sessao, capsys):
    _medir_linha(sessao, "1.4", anotar=False)
    osc = sessao.leituras()["1.4"]["vt"]
    sessao.executar("vt=2,95")                                  # vírgula decimal sem espaço
    assert sessao.leituras()["1.4"]["vt"] == 2.95 and sessao.leituras()["1.4"].fontes["vt"] == "manual"
    sessao.executar("vt=-")
    assert sessao.leituras()["1.4"]["vt"] == osc
    sessao.executar("anotar 1.2 w 480")
    sessao.executar("vt' 2.5")                                  # anota no caso atual, que é da Tabela 1
    assert sessao.leituras()["1.2"]["w"] == 480 and sessao.leituras()["1.4"]["vtc"] == 2.5
    sessao.executar("ig=120")                                   # 120 A: unidade errada
    assert "o valor vai em A (120 mA = 120m)" in capsys.readouterr().out
    sessao.executar("caso 2.4")
    sessao.executar("ig 120m")
    l = sessao.leituras()["2.4"]
    assert l["ig"] == pytest.approx(0.12) and l["vt"] == osc and l.fontes["vt"] == "tab. 1, linha 1.4"


def test_ponto_fora_da_reta_aparece_na_hora(sessao, capsys):
    for k in (1, 2, 3):
        _medir_linha(sessao, f"1.{k}")
    capsys.readouterr()
    sessao.executar("caso 1.4")
    sessao.executar("w=2000")                                   # deveria dar ~1190
    assert "CONFERIR" in capsys.readouterr().out


def test_retomar_uma_sessao_do_motor_de_uma_sessao_do_exp7(sessao, tmp_path, capsys):
    for id in ("1.2", "1.3", "2.3"):
        _medir_linha(sessao, id)
    sessao.executar("projeto tp 250m")
    pasta = sessao.pasta.caminho
    nova = SessaoLab(tmp_path / "outra", abrir_figuras=False)  # abre no Exp. 7
    nova.executar(f"retomar {pasta}")
    assert isinstance(nova, SessaoMotor) and nova.numero == 3 and set(nova.capturas) == {"1.2", "1.3", "2.3"}
    assert nova.leituras()["1.3"].tem("w") and nova.opcoes_projeto == {"tp": 0.25} and nova.caso.id == "2.3"
    nova.executar("descartar 2")
    assert set(nova.capturas) == {"1.2", "2.3"} and nova.leituras()["1.3"].tem("w")
    assert "ERRO" not in capsys.readouterr().out


def test_exportar_sessao_do_motor_para_latex(sessao, tmp_path):
    for k in range(1, 5):
        _medir_linha(sessao, f"1.{k}")
    for k in range(2, 5):
        _medir_linha(sessao, f"2.{k}")
    destino = tmp_path / "te333" / "08"
    exportar(sessao.pasta.caminho, destino)
    tab = {p.name for p in (destino / "tab").iterdir()}
    tex = {p.name for p in (destino / "tex").iterdir()}
    assert tab == {"tabela1.tex", "tabela2.tex", "constantes.tex", "projeto.tex"}
    assert {"plot_vt_va.tex", "plot_w_va.tex", "plot_vt_w.tex", "plot_v1t_ig.tex", "plot_tau_va.tex",
            "plot_partidas1.tex", "plot_partidas2.tex", "plot_projeto_pi.tex", "plot_projeto_pd_carga.tex",
            "cod_motor.tex", "cod_pi.tex", "cod_pd.tex"} <= tex
    t1 = (destino / "tab" / "tabela1.tex").read_text(encoding="utf-8")
    assert r"\setcounter{table}{0}" in t1 and "08/csv" in (destino / "tex" / "plot_vt_va.tex").read_text(encoding="utf-8")
    codigo = (destino / "cod" / "motor_projeto.py").read_text(encoding="utf-8")
    assert all(ord(c) < 256 for c in codigo)                    # o listings só lida com Latin-1


def test_preparar_arma_a_aquisicao_unica_no_tektronix():
    from testes.test_instrumentos import _tek
    scope, con = _tek()
    scope.conectar()
    scope.preparar(0.25, nivel=2.0, unico=True)
    assert {"TRIGger:MAIn:LEVel 2", "ACQuire:STOPAfter SEQuence", "ACQuire:STATE RUN"} <= set(con.enviados)
    scope.preparar(1e-3)
    assert "ACQuire:STOPAfter RUNSTop" in con.enviados and "TRIGger:MAIn SETLevel" in con.enviados
    con.enviados.clear()
    scope.armar()
    assert con.enviados == ["ACQuire:STATE RUN"]


def test_sinal_de_controle_alem_do_amp_op_e_acusado_com_o_tp_que_resolve():
    rapido = ProjetoPD(MOTOR, 60, tp=0.1)
    item = rapido.especificacao()[-1]
    assert item[0].startswith("sinal de controle") and not item[3] and rapido.pico_controle() > 20
    tp = rapido.tp_minimo()
    assert 0.1 < tp < 0.5 and ProjetoPD(MOTOR, 60, tp=tp).pico_controle() <= 10
    pi = ProjetoPI(MOTOR, 1000)
    assert pi.pico_controle() == pytest.approx(1000 / (0.85 * MOTOR.K), rel=0.01)    # Kp·Kt·1000 rpm na borda
    assert ProjetoPI(MOTOR, 1000, vmax=3.0).especificacao()[-1][3] is False


def test_mau_contato_ao_ligar_a_fonte_nao_corta_a_partida():
    scope, cap = _partida()
    u = cap["CH1"].copy()
    i = int(np.argmax(u > 2))
    for a, b in ((i + 3, i + 5), (i + 9, i + 10)):           # dois repiques de poucos ms logo depois de encostar
        u[a:b] = 0.0
    m = DegrauMotor(Captura(cap.t, {"CH1": u, "CH2": cap["CH2"]}, cap.meta, cap.origem))
    assert m.borda[0] == i and m.borda[1] == len(u)
    assert m.tau == pytest.approx(scope.tau, rel=0.03) and m.va == pytest.approx(4.0, abs=0.05)
