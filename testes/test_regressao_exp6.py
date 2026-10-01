"""Com L = 77 mH, as medidas e os valores teóricos do pipeline novo têm de
reproduzir _antigo/tabelas.json (a identificação mudou de propósito e fica de
fora). Precisa do pendrive com as capturas."""
import json
import math
from dataclasses import replace
from pathlib import Path

import pytest

import experimento6 as E
from labscope import modelo

ANTIGO = Path(__file__).parent.parent / "_antigo" / "tabelas.json"
pytestmark = pytest.mark.skipif(not (E.DADOS.exists() and ANTIGO.exists()), reason="sem capturas ou sem referência")
ROTEIRO = replace(E.Comp(), L=77e-3)


@pytest.fixture(scope="module")
def dados():
    return E.carregar(E.DADOS)


@pytest.fixture(scope="module")
def antigo():
    return json.load(open(ANTIGO))["casos"]


def _perto(a, b, rel):
    if a is None or b is None:
        return a is b
    if math.isnan(a) or math.isnan(b):
        return math.isnan(a) and math.isnan(b)
    return a == pytest.approx(b, rel=rel, abs=1e-9)


def test_medidas_iguais(dados, antigo):
    difs = []
    for caso, ref in zip(E.CASOS, antigo):
        assert (caso.parte, caso.R2) == (ref["parte"], ref["R2"])
        m = E.medir(dados, caso)
        for k in ("tau", "tr", "tp", "mp", "ts", "vc", "zeta", "wn", "wd"):
            if k in ref["exp"] and not _perto(m[k], ref["exp"][k], 1e-2):
                difs.append((caso.parte, caso.R2, k, m[k], ref["exp"][k]))
    assert not difs, difs


def test_teoricos_iguais(antigo):
    difs = []
    for caso, ref in zip(E.CASOS, antigo):
        th = E.teorico(caso, ROTEIRO)
        for k in ("tau", "tr", "tp", "mp", "ts", "vc", "ess"):
            if k == "tau" and caso.ctrl == "PI":
                continue        # campo auxiliar que o relatório não usa
            if k in ref["teo"] and not _perto(th[k], ref["teo"][k], 2e-3):
                difs.append((caso.parte, caso.R2, k, th[k], ref["teo"][k]))
    assert not difs, difs


def test_polos_iguais(antigo):
    for caso, ref in zip(E.CASOS, antigo):
        key = lambda p: (round(p[0], 3), round(p[1], 3))
        novos = sorted(([r.real, r.imag] for r in modelo.polos(E.ft(caso, ROTEIRO)[1])), key=key)
        for a, b in zip(novos, sorted(ref["polos"], key=key)):
            assert a == pytest.approx(b, rel=1e-6, abs=1e-6)


def test_identificacao_reproduz_as_formas_de_onda(dados):
    """O modelo identificado tem de ficar muito mais perto dos dados que o nominal."""
    tab = E.analisar(dados)
    for c in tab["casos"]:
        assert c["rms"]["final"] < 0.4 * c["rms"]["nominal"], (c["parte"], c["R2"], c["rms"])
