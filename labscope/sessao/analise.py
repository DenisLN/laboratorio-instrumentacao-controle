"""Análise de uma captura contra um caso do roteiro: medida × modelo."""
import datetime as dt
import math
from dataclasses import dataclass, field

import numpy as np

from .. import relatorio as Rl
from ..medidas import PADRAO, RespostaMedida, RespostaTeorica
from ..roteiros import texto_si


def linhas_componentes(roteiro, caso, comp):
    """Um componente por linha, com o nominal ao lado quando o valor em uso é outro:
    'R2  = 9,87 kΩ   (nominal 10 kΩ)'."""
    linhas = []
    for k in caso.usados:
        u, real, nominal = comp.UNIDADES[k], getattr(comp, k), getattr(caso.comp, k)
        extra = f"   (nominal {texto_si(nominal, u)})" if real != nominal else ""
        linhas.append(f"{roteiro.nome(k):<3} = {texto_si(real, u)}{extra}")
    return linhas


@dataclass
class Linha:
    metrica: object
    rotulo: str
    exp: float
    teo: float          # modelo do roteiro (amp-ops ideais, sem carga)
    carga: float        # mesmo modelo com o R do inversor carregando o capacitor
    desvio: float       # (exp − teo)/teo
    ok: bool | None     # dentro da tolerância de um dos dois modelos; None se não dá para comparar


@dataclass
class Resultado:
    roteiro: object
    caso: object
    comp: object                    # componentes efetivos (nominais com as trocas do usuário)
    captura: object
    medida: RespostaMedida
    teoria: RespostaTeorica
    teoria_carga: RespostaTeorica
    linhas: list
    residuo: dict                   # RMS em volts entre CH2 e cada modelo: {"teo", "carga"}
    avisos: list
    numero: int = 0                 # ordem da captura na sessão
    quando: str = field(default_factory=lambda: dt.datetime.now().isoformat(timespec="seconds"))
    ganhos_id: dict | None = None   # Kp, Ki, Kd identificados pelo comando 'ajustar'

    def linha(self, chave):
        return next((l for l in self.linhas if l.metrica.chave == chave), None)

    @property
    def conferir(self):
        return [l for l in self.linhas if l.ok is False]

    # ------------------------------------------------------------ textos
    def titulo(self):
        return (f"Exp. {self.roteiro.numero} · Tabela {self.caso.tabela} · caso {self.caso.id} "
                f"({self.caso.rotulo}) · {self.teoria.malha.descricao()}")

    def ganhos_texto(self):
        g = self.teoria.malha.controlador.ganhos()
        partes = [f"Kp = {Rl.num(g['kp'], 2)}"]
        if g["ki"]:
            partes.append(f"Ki = {Rl.num(g['ki'], 0)} 1/s")
        if g["kd"]:
            partes.append(f"Kd = {Rl.num(g['kd'] * 1e3, 4)} ms")
        return "   ".join(partes)

    def componentes_texto(self):
        return "  ".join(f"{self.roteiro.nome(k)} = {texto_si(getattr(self.comp, k), self.comp.UNIDADES[k])}"
                         for k in self.caso.usados)

    def captura_texto(self):
        m = self.medida
        return (f"{m.degrau['n']} trecho(s) medido(s), {len(m.t)} pontos, dt = {texto_si(self.captura.dt, 's')}, "
                f"LSB = {m.lsb * 1e3:.3g} mV, média móvel de {texto_si(m.suavizacao, 's')}")

    def linhas_texto(self):
        """A tabela de métricas como lista de linhas de texto alinhadas."""
        out = [f"{'métrica':<15}{'experimental':>14}{'teórico':>14}{'c/ carga':>14}{'desvio':>10}   "]
        for l in self.linhas:
            desvio = "–" if math.isnan(l.desvio) else f"{l.desvio * 100:+.1f} %".replace(".", ",")
            estado = {True: "OK", False: "CONFERIR", None: ""}[l.ok]
            f = l.metrica.formatar
            out.append(f"{l.rotulo:<15}{f(l.exp):>14}{f(l.teo):>14}{f(l.carga):>14}{desvio:>10}   {estado}")
        return out

    def residuo_texto(self):
        return (f"resíduo RMS de CH2 contra o modelo: teórico {self.residuo['teo'] * 1e3:.1f} mV · "
                f"c/ carga {self.residuo['carga'] * 1e3:.1f} mV  (LSB {self.medida.lsb * 1e3:.3g} mV)").replace(".", ",")

    def veredito(self):
        comparadas = [l for l in self.linhas if l.ok is not None]
        if not self.conferir:
            return f"{len(comparadas)} de {len(comparadas)} métricas dentro da tolerância"
        return (f"{len(comparadas) - len(self.conferir)} de {len(comparadas)} dentro da tolerância — conferir: "
                + ", ".join(l.rotulo for l in self.conferir))

    def texto(self):
        cab = ([f"#{self.numero:02d}  {self.titulo()}"]
               + [f"     {l}" for l in linhas_componentes(self.roteiro, self.caso, self.comp)]
               + [f"     {self.ganhos_texto()}      [{self.captura_texto()}]", ""])
        corpo = ["  " + l for l in self.linhas_texto()]
        rodape = ["", "  " + self.residuo_texto()] + [f"  ! {a}" for a in self.avisos] + ["  => " + self.veredito()]
        return "\n".join(cab + corpo + rodape)

    def como_dict(self):
        num = lambda x: None if x is None or (isinstance(x, float) and math.isnan(x)) else float(x)
        par = lambda z: [[float(r.real), float(r.imag)] for r in z]
        return dict(
            numero=self.numero, quando=self.quando, experimento=self.roteiro.numero, caso=self.caso.id,
            tabela=self.caso.tabela, rotulo=self.caso.rotulo, planta=self.caso.planta, controlador=self.caso.ctrl,
            componentes=self.comp.como_dict(), ganhos=self.teoria.malha.controlador.ganhos(),
            ganhos_identificados=self.ganhos_id,
            ft=dict(num=list(self.teoria.ft.num), den=list(self.teoria.ft.den)),
            polos=par(self.teoria.malha.polos()), polos_carga=par(self.teoria_carga.malha.polos()),
            subida=self.medida.subida, trechos=self.medida.degrau["n"], dt=self.captura.dt, lsb=self.medida.lsb,
            oscilacao=self.medida.oscilacao,
            metricas=[dict(chave=l.metrica.chave, nome=l.metrica.nome, unidade_si=True, exp=num(l.exp),
                           teo=num(l.teo), carga=num(l.carga), desvio=num(l.desvio), ok=l.ok) for l in self.linhas],
            residuo_rms=self.residuo, avisos=self.avisos, origem=self.captura.origem)


def _avisos(captura, roteiro, medida, teoria, teoria_carga):
    avisos = []
    for canal, meta in captura.meta.items():
        if isinstance(meta, dict) and meta.get("cortado"):
            avisos.append(f"{canal} saiu da tela (sinal cortado): aumente V/div")
    pico = teoria_carga.saturacao()
    if pico:
        avisos.append(f"pelo modelo o amp-op do controlador teria de chegar a {pico:.0f} V para seguir esta resposta: "
                      "ele satura na alimentação, e a subida e o sobressinal medidos ficam menores que os teóricos "
                      "(a oscilação depois da saturação ainda segue o modelo — compare ω_d decr.)")
    razao = medida.amplitude / roteiro.amplitude
    sondas = {m.get("Probe Atten") for m in captura.meta.values() if isinstance(m, dict) and m.get("Probe Atten")}
    if (8 < razao < 12 or 1 / 12 < razao < 1 / 8) and sondas:
        avisos.append(f"CH1 com {razao:.3g}× a amplitude do roteiro e osciloscópio com sonda em "
                      f"{'/'.join(f'{s:g}X' for s in sorted(sondas))}: se a ponta ou o cabo for de outra atenuação, "
                      "acerte Probe no menu do canal ou use 'set sonda 1' (ou 10) e 'calcular'")
    if not teoria.estavel:
        avisos.append("pelo modelo do roteiro esta malha é INSTÁVEL: polos " + str(np.round(teoria.malha.polos(), 0)))
    semi = 0.5 / roteiro.frequencia
    ts = teoria_carga.degrau["ts"]
    if not math.isnan(ts) and ts > semi:
        avisos.append(f"pelo modelo a resposta não acomoda em meio período (Ts = {ts * 1e3:.0f} ms > {semi * 1e3:.0f} ms)")
    visto = medida.degrau["semi"]
    if not medida.acomodou:
        avisos.append("a resposta não acomodou dentro da janela: Ts sem valor e Vc pouco confiável — aumente s/div")
    elif not math.isnan(ts) and visto < min(1.2 * ts, 0.95 * semi):
        avisos.append(f"janela curta: só {visto * 1e3:.3g} ms depois da borda para um Ts previsto de "
                      f"{ts * 1e3:.3g} ms — Vc e Ts pouco confiáveis, aumente s/div")
    f = medida.frequencia
    if not math.isnan(f) and abs(f - roteiro.frequencia) > 0.05 * roteiro.frequencia:
        avisos.append(f"CH1 está em {f:.1f} Hz; o roteiro pede {roteiro.frequencia:g} Hz")
    tr = medida.degrau["tr"]
    if not math.isnan(tr) and tr < 8 * captura.dt:
        avisos.append(f"só {tr / captura.dt:.0f} amostras na subida: diminua s/div para medir Tr e Tp melhor")
    if medida.lsb and 2 * medida.vc / medida.lsb < 25:
        avisos.append(f"CH2 ocupa só {2 * medida.vc / medida.lsb:.0f} níveis do conversor: diminua V/div")
    return avisos


def analisar(captura, roteiro, caso, comp=None, metricas=PADRAO, suavizacao=60e-6, numero=0):
    """Mede `captura` e compara com os modelos do `caso` (do roteiro e com carga)."""
    comp = comp or caso.comp
    teoria = RespostaTeorica(caso.malha(comp), roteiro.amplitude)
    teoria_carga = RespostaTeorica(caso.malha(comp, carga=True), roteiro.amplitude)
    # a média móvel não pode ser longa a ponto de arredondar a própria subida
    tr = teoria_carga.degrau["tr"]
    if not math.isnan(tr):
        suavizacao = min(suavizacao, tr / 8)
    medida = RespostaMedida(captura, roteiro.frequencia, teoria.subida, teoria.malha.controlador.integral,
                            suavizacao=suavizacao)
    linhas = []
    for m in metricas:
        if not m.aplicavel(teoria):
            continue
        exp, teo, carga = m.medir(medida), m.prever(teoria), m.prever(teoria_carga)
        if m.chave.endswith("_dl") and math.isnan(exp):
            continue        # oscilação pequena demais para o decremento logarítmico
        folga = m.folga(medida)
        c1, c2 = m.comparar(exp, teo, folga), m.comparar(exp, carga, folga)
        ok = None if (c1.ok is None and c2.ok is None) or not m.julgavel(teoria) else bool(c1.ok or c2.ok)
        linhas.append(Linha(m, m.rotulo(medida), exp, teo, carga, c1.desvio, ok))
    residuo = dict(teo=medida.residuo(teoria) if teoria.estavel else math.nan,
                   carga=medida.residuo(teoria_carga) if teoria_carga.estavel else math.nan)
    return Resultado(roteiro, caso, comp, captura, medida, teoria, teoria_carga, linhas, residuo,
                     _avisos(captura, roteiro, medida, teoria, teoria_carga), numero)
