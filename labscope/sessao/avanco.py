"""Sessão do Experimento 10 (compensador avanço de fase).

As Tabelas 3, 5 e 6 (onda quadrada de 50 Hz) são medidas como nos Exps. 6 e 7,
com a saída invertida da malha das Figuras 2 e 3. As Tabelas 1, 2, 4 e 7 são em
regime senoidal: Vpp da saída e ângulo de fase entre CH2 e CH1, comparados com
G(jω) do circuito.

    lab[e10 c1.1]> conectar sim; caso 2.3; teoria; adquirir
    lab[e10 c2.3]> grafico 2           Bode do compensador com os pontos medidos
"""
import datetime as dt
import math
from dataclasses import dataclass, field

from .. import relatorio as Rl
from ..instrumentos import OsciloscopioArquivo, OsciloscopioSimulado, TektronixTBS, base_de_tempo
from ..medidas import PADRAO, ConstanteTempo, PrevisaoSenoidal, RespostaSenoidal
from ..medidas.senoide import diferenca_fase
from ..roteiros import CadeiaAberta, ComponentesAvanco, texto_si
from . import painel, painel_avanco
from .analise import analisar, ganhos_texto, linhas_componentes
from .cli import AJUDA, SessaoLab

NAN = math.nan

AJUDA_AVANCO = """
Experimento 10 – compensador avanço de fase. Além dos comandos de sempre:

  casos / caso <id>     1.1 inversor (500 Hz) · 2.1–2.6 compensador em malha aberta (20 Hz a 5 kHz)
                        3.1 RC e 5.1 RLC com onda quadrada de 50 Hz (Tabelas 3, 5 e 6)
                        4.1 RC e 7.1 RLC com senoide de 100 Hz (Tabelas 4 e 7)
  teoria (t)            Zero, polo e fase máxima do compensador, G(jω) ou a resposta ao degrau.
  adquirir (a)          Senoide: Vpp de CH2 e fase de CH2 em relação a CH1 (ajuste de senoide).
  grafico <n>           Tabelas 1, 2, 4 e 7: Bode teórico com os pontos medidos.
  lgr [componente]      Lugar das raízes das malhas fechadas (casos 3.1, 4.1, 5.1 e 7.1).
  set <componente> <v>  Nomes da folha: R, R1, C1, R2, C2, R3, R4, R5, R6, Rc, Cc, L1.

A saída das Figuras 2 e 3 sai invertida (V_c volta direto ao somador): a fase em
100 Hz fica perto de 180°, e no degrau as contas usam −CH2.
""".strip("\n")

# (símbolo, unidade, escala, casas, tolerância relativa ou, na fase, absoluta em graus)
_SENOIDE = {"vpp_in": ("Vpp entrada", "V", 1.0, 3, 0.10), "vpp": ("Vpp saída", "V", 1.0, 3, 0.10),
            "ganho": ("|G|", "", 1.0, 3, 0.10), "fase": ("fase", "°", 1.0, 1, 10.0)}


@dataclass
class LinhaSenoide:
    chave: str
    exp: float
    teo: float
    carga: float
    ok: bool | None

    @property
    def simbolo(self):
        return _SENOIDE[self.chave][0]

    def formatar(self, x):
        _, u, escala, casas, _ = _SENOIDE[self.chave]
        return Rl.num(x, casas, u, escala)

    @property
    def desvio_texto(self):
        if math.isnan(self.exp) or math.isnan(self.teo):
            return "–"
        if self.chave == "fase":
            return f"{diferenca_fase(self.exp, self.teo):+.1f}°".replace(".", ",")
        return f"{(self.exp - self.teo) / self.teo * 100:+.1f} %".replace(".", ",")


def _ok(chave, exp, teo, folga=0.0):
    if math.isnan(exp) or math.isnan(teo):
        return None
    tol = _SENOIDE[chave][4]
    if chave == "fase":
        return abs(diferenca_fase(exp, teo)) <= tol
    return abs(exp - teo) <= max(tol * abs(teo), folga)


@dataclass
class ResultadoSenoide:
    roteiro: object
    caso: object
    comp: object
    captura: object
    medida: RespostaSenoidal
    previsto: PrevisaoSenoidal
    previsto_carga: PrevisaoSenoidal
    linhas: list
    avisos: list
    numero: int = 0
    quando: str = field(default_factory=lambda: dt.datetime.now().isoformat(timespec="seconds"))

    def linha(self, chave):
        return next((l for l in self.linhas if l.chave == chave), None)

    @property
    def conferir(self):
        return [l for l in self.linhas if l.ok is False]

    def titulo(self):
        return (f"Exp. {self.roteiro.numero} · Tabela {self.caso.tabela} · caso {self.caso.id} "
                f"({self.caso.rotulo}) · senoide de {texto_si(self.caso.frequencia, 'Hz')}")

    def componentes_texto(self):
        return "  ".join(f"{k} = {texto_si(getattr(self.comp, k), self.comp.UNIDADES[k])}" for k in self.caso.usados)

    def captura_texto(self):
        m = self.medida
        return (f"{m.periodos:.1f} período(s) a {texto_si(m.frequencia, 'Hz')}, {len(m.t)} pontos, "
                f"dt = {texto_si(self.captura.dt, 's')}, LSB = {m.lsb * 1e3:.3g} mV").replace(".", ",")

    def linhas_texto(self):
        out = [f"{'grandeza':<13}{'experimental':>13}{'teórico':>12}{'c/ carga':>12}{'desvio':>9}   "]
        for l in self.linhas:
            estado = {True: "OK", False: "CONFERIR", None: ""}[l.ok]
            out.append(f"{l.simbolo:<13}{l.formatar(l.exp):>13}{l.formatar(l.teo):>12}{l.formatar(l.carga):>12}"
                       f"{l.desvio_texto:>9}   {estado}")
        return out

    def residuo_texto(self):
        return (f"resíduo RMS de CH2 contra a senoide ajustada: {self.medida.residuo * 1e3:.1f} mV "
                f"(LSB {self.medida.lsb * 1e3:.3g} mV)").replace(".", ",")

    def veredito(self):
        comparadas = [l for l in self.linhas if l.ok is not None]
        if not self.conferir:
            return f"{len(comparadas)} de {len(comparadas)} grandezas dentro da tolerância"
        return (f"{len(comparadas) - len(self.conferir)} de {len(comparadas)} dentro da tolerância — conferir: "
                + ", ".join(l.simbolo for l in self.conferir))

    def texto(self):
        cab = ([f"#{self.numero:02d}  {self.titulo()}"]
               + [f"     {l}" for l in linhas_componentes(self.roteiro, self.caso, self.comp)]
               + [f"     [{self.captura_texto()}]", ""])
        rodape = ["", "  " + self.residuo_texto()] + [f"  ! {a}" for a in self.avisos] + ["  => " + self.veredito()]
        return "\n".join(cab + ["  " + l for l in self.linhas_texto()] + rodape)

    def como_dict(self):
        num = lambda x: None if x is None or (isinstance(x, float) and math.isnan(x)) else float(x)
        ft = self.previsto.ft
        return dict(numero=self.numero, quando=self.quando, experimento=self.roteiro.numero, caso=self.caso.id,
                    tabela=self.caso.tabela, rotulo=self.caso.rotulo, circuito=self.caso.circuito,
                    frequencia_nominal=self.caso.frequencia, frequencia_medida=self.medida.frequencia,
                    componentes=self.comp.como_dict(), ft=dict(num=list(ft.num), den=list(ft.den)),
                    metricas=[dict(chave=l.chave, nome=l.simbolo, exp=num(l.exp), teo=num(l.teo), carga=num(l.carga),
                                   ok=l.ok) for l in self.linhas],
                    residuo_rms=self.medida.residuo, avisos=self.avisos, origem=self.captura.origem)


def previsoes(caso, comp, amplitude=None):
    """Regime senoidal previsto pelo modelo do roteiro e pelo modelo com a carga do somador."""
    a = caso.amplitude if amplitude is None else amplitude
    return tuple(PrevisaoSenoidal(caso.malha(comp, carga=c).ft(), caso.frequencia, a) for c in (False, True))


def analisar_senoide(captura, roteiro, caso, comp=None, numero=0):
    comp = comp or caso.comp
    medida = RespostaSenoidal(captura, caso.frequencia)
    teo, carga = previsoes(caso, comp)
    linhas = [LinhaSenoide("vpp_in", medida.vpp_entrada, teo.vpp / teo.ganho, NAN, None)]
    linhas[0].ok = _ok("vpp_in", medida.vpp_entrada, linhas[0].teo)
    for chave, exp, t, c in (("vpp", medida.vpp, teo.vpp, carga.vpp), ("ganho", medida.ganho, teo.ganho, carga.ganho),
                             ("fase", medida.fase, teo.fase, carga.fase)):
        folga = 2 * medida.lsb if chave == "vpp" else 0.0
        oks = [_ok(chave, exp, x, folga) for x in (t, c)]
        linhas.append(LinhaSenoide(chave, exp, t, c, None if oks == [None, None] else any(oks)))
    return ResultadoSenoide(roteiro, caso, comp, captura, medida, teo, carga, linhas,
                            _avisos(captura, caso, medida), numero)


def _avisos(captura, caso, medida):
    avisos = []
    for canal, meta in captura.meta.items():
        if isinstance(meta, dict) and meta.get("cortado"):
            avisos.append(f"{canal} saiu da tela (sinal cortado): aumente V/div")
    if abs(medida.frequencia - caso.frequencia) > 0.05 * caso.frequencia:
        avisos.append(f"CH1 está em {medida.frequencia:.4g} Hz; a folha pede {caso.frequencia:g} Hz")
    if medida.periodos < 1.0:
        avisos.append(f"só {medida.periodos:.2f} período na tela: aumente s/div (o ajuste fica pouco confiável)".replace(".", ","))
    if medida.residuo > max(0.05 * medida.vpp, 3 * medida.lsb):
        avisos.append("CH2 não parece uma senoide (resíduo alto): saturação do amp-op, ruído ou canal errado")
    if medida.lsb and medida.vpp / medida.lsb < 25:
        avisos.append(f"CH2 ocupa só {medida.vpp / medida.lsb:.0f} níveis do conversor: diminua V/div")
    return avisos


class ConstanteTempoSemSobressinal(ConstanteTempo):
    """A Tabela 3 pede τ, mas a malha RC com o compensador é de 2ª ordem: com o polo
    lento quase cancelado pelo zero, a resposta é a de um polo só e τ ainda faz sentido."""

    def aplicavel(self, teoria):
        return teoria.degrau["mp"] == 0


METRICAS_DEGRAU = [ConstanteTempoSemSobressinal() if isinstance(m, ConstanteTempo) else m for m in PADRAO]


class SessaoAvanco(SessaoLab):
    """'executar' chama o cmd_* desta classe quando ele existe aqui."""

    def _descricao_roteiro(self):
        return "senoides nas Tabelas 1, 2, 4 e 7; onda quadrada de 50 Hz, 1 Vpp nas Tabelas 3, 5 e 6"

    # ------------------------------------------------------------ análise
    def _analise(self, captura, roteiro, caso, comp, numero):
        if caso.senoide:
            return analisar_senoide(captura, roteiro, caso, comp, numero)
        return analisar(captura, roteiro, caso, comp, METRICAS_DEGRAU, self.suavizacao, numero)

    @staticmethod
    def _desenhar_painel(res, caminho):
        if isinstance(res, ResultadoSenoide):
            return painel_avanco.senoide(res, caminho)
        return painel.painel(res, caminho)

    def _s_div_sugerido(self):
        if self.caso.senoide:
            return base_de_tempo(2.5 / self.caso.frequencia, 10)      # dois períodos e meio na tela
        return super()._s_div_sugerido()

    def _v_div_sugerido(self):
        if self.caso.senoide:
            pico = previsoes(self.caso, self.comp())[1].vpp / 2
            return next((v for v in (0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0) if 3.5 * v >= pico), 5.0)
        return super()._v_div_sugerido()

    # ------------------------------------------------------------ roteiro
    def cmd_casos(self, _args):
        tabelas = {t.numero: t.titulo for t in self.roteiro.tabelas()}
        tabela = None
        for c in self.roteiro.casos():
            if c.tabela != tabela:
                tabela = c.tabela
                print(f"  Tabela {tabela} – {tabelas[tabela]}")
            res = self.resultados.get((self.roteiro.numero, c.id))
            estado = f"medido (#{res.numero:02d}, {len(res.conferir)} a conferir)" if res else "–"
            marca = ">" if c.id == self.caso.id else " "
            if c.senoide:
                p = previsoes(c, self.comp(c))[0]
                previsto = f"Vpp = {Rl.num(p.vpp, 3, 'V')}, fase = {Rl.num(p.fase, 1, '°')}"
            else:
                previsto = f"degrau de {texto_si(c.frequencia, 'Hz')}"
            print(f"   {marca} {c.id:<4} {c.rotulo:<12} {previsto:<32} {estado}")

    def cmd_teoria(self, args):
        caso, comp = self.caso, self.comp()
        if not caso.senoide:
            return super().cmd_teoria(args)
        bloco = caso.malha(comp)
        print(f"  Exp. {self.roteiro.numero} · Tabela {caso.tabela} · caso {caso.id} ({caso.rotulo}) · "
              f"{bloco.descricao()}")
        for linha in linhas_componentes(self.roteiro, caso, comp):
            print(f"    {linha}")
        if caso.circuito != "inversor":
            print(f"  compensador: {ganhos_texto(comp.compensador())}")
        print(f"  Vsaída/Ventrada = {bloco.ft()}")
        teo, carga = previsoes(caso, comp)
        print(f"  senoide de {texto_si(caso.frequencia, 'Hz')}, {Rl.num(2 * caso.amplitude, 2, 'V')}pp:")
        for rot, p in (("teórico", teo), ("c/ carga", carga)) if not isinstance(bloco, CadeiaAberta) else (("teórico", teo),):
            print(f"    {rot:<9} |G| = {Rl.num(p.ganho, 3)} ({Rl.num(20 * math.log10(p.ganho), 1, 'dB')})   "
                  f"Vpp saída = {Rl.num(p.vpp, 3, 'V')}   fase = {Rl.num(p.fase, 1, '°')}")
        print(f"  Tela sugerida: {texto_si(self._s_div_sugerido(), 's')}/div, trigger em CH1; "
              f"CH2 em {texto_si(self._v_div_sugerido(), 'V')}/div centrado em 0 V.")

    def cmd_adquirir(self, args):
        self._exigir_scope()
        if isinstance(self.scope, OsciloscopioSimulado):
            self.scope.frequencia, self.scope.amplitude = self.caso.frequencia, self.caso.amplitude
            self.scope.senoide = self.caso.senoide
            self.scope.s_div = self._s_div_sugerido()
            self.scope.v_div = (0.5 if self.caso.amplitude > 0.5 else 0.2, self._v_div_sugerido())
        if isinstance(self.scope, OsciloscopioArquivo) and args:
            self.scope.proxima = int(args[0])
        captura = self.scope.adquirir()
        if self.diagnostico and isinstance(self.scope, TektronixTBS):
            print(f"  fila do instrumento: {self.scope.erros()}")
        self._nova_captura(captura)

    def cmd_ajustar(self, _args):
        raise ValueError("'ajustar' identifica Kp, Ki e Kd de um PID e não se aplica ao compensador avanço de fase")

    def cmd_lgr(self, args):
        if self.caso.circuito not in ("RC", "RLC"):
            raise ValueError("o lugar das raízes é das malhas fechadas (casos 3.1, 4.1, 5.1 e 7.1); "
                             "nas Tabelas 1 e 2, 'teoria' mostra o zero e o polo do compensador")
        variavel = ComponentesAvanco.chave(args[0]) if args else "R2"
        res = self.resultados.get((self.roteiro.numero, self.caso.id))
        alvo = res if res is not None and not self.caso.senoide else self.caso
        nome = f"lgr_exp{self.roteiro.numero}_c{self.caso.id}_{variavel}.png"
        self._mostrar(painel.lugar_das_raizes(alvo, self.roteiro, self.comp(), self.pasta.garantir() / nome, variavel))

    # ------------------------------------------------------------ relatório
    def _tabela_md(self, tabela):
        if tabela.metricas != ("vpp", "fase"):
            return super()._tabela_md(tabela)
        cab = ["caso", "Vpp saída exp", "Vpp saída teo", "fase exp", "fase teo"]
        linhas = []
        for id in tabela.casos:
            caso = self.roteiro.caso(id)
            teo = previsoes(caso, self.comp(caso))[0]
            res = self.resultados.get((self.roteiro.numero, id))
            vpp, fase = (res.linha("vpp"), res.linha("fase")) if res else (None, None)
            linhas.append([caso.rotulo, vpp.formatar(vpp.exp) if vpp else "–", Rl.num(teo.vpp, 3, "V"),
                           fase.formatar(fase.exp) if fase else "–", Rl.num(teo.fase, 1, "°")])
        return f"**Tabela {tabela.numero}** – {tabela.titulo}\n\n" + Rl.tabela(cab, linhas)

    def _regime_md(self):
        linhas = []
        for rot, comp in (("Tabela 2 (malha aberta)", self.comp(self.roteiro.caso("2.1"))),
                          ("Figuras 2 e 3", self.comp(self.roteiro.caso("3.1")))):
            c = comp.compensador()
            linhas.append([rot, Rl.num(c.kp, 3), Rl.num(c.zero, 0), Rl.num(c.polo, 0), Rl.num(c.fase_maxima, 1),
                           Rl.num(c.w_max / (2 * math.pi), 0)])
        return ("**Compensador** G_c = (R2/R1)·(R1C1·s + 1)/(R2C2·s + 1)\n\n"
                + Rl.tabela(["circuito", "K = R2/R1", "zero (rad/s)", "polo (rad/s)", "fase máx. (°)", "em (Hz)"],
                            linhas))

    def cmd_grafico(self, args):
        tabela = next((t for t in self.roteiro.tabelas() if args and str(t.numero) == args[0]), None)
        if tabela is None or tabela.metricas != ("vpp", "fase"):
            return super().cmd_grafico(args)
        casos = [self.roteiro.caso(id) for id in tabela.casos]
        comp = self.comp(casos[0])
        curvas = [(casos[0].malha(comp).ft(), "teórico", "-")]
        if not isinstance(casos[0].malha(comp), CadeiaAberta):
            curvas.append((casos[0].malha(comp, carga=True).ft(), "modelo c/ carga", (0, (1, 1.5))))
        medidos = [self.resultados[(self.roteiro.numero, id)] for id in tabela.casos
                   if (self.roteiro.numero, id) in self.resultados]
        nome = f"bode_exp{self.roteiro.numero}_tabela{tabela.numero}.png"
        self._mostrar(painel_avanco.bode(tabela, casos, curvas, medidos, self.roteiro,
                                         self.pasta.garantir() / nome))

    def cmd_help(self, _args):
        print(AJUDA + "\n\n" + AJUDA_AVANCO)
