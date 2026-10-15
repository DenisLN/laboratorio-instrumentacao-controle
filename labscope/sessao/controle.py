"""Sessão do Experimento 9 (controle do motor CC com perturbações).

Parte do motor identificado no Exp. 8 (`modelo`), projeta o controlador de cada linha
da folha (PI de velocidade, PD/PID de posição, sem carga e com a carga Vg), mostra os
componentes do circuito analógico e compara a resposta ao degrau do osciloscópio
(CH1 = referência, CH2 = Vt ou o sensor de posição) com a que o modelo prevê:

    lab[e9 c1.1]> modelo ref2022          motor do Exp. 8 (ou: modelo <pasta da sessão do Exp. 8>)
    lab[e9 c1.1]> projeto                 ganhos, especificação, polos e resposta prevista
    lab[e9 c1.1]> circuito                R, R2, C1 e C2 do controlador analógico
    lab[e9 c1.1]> preparar -> (degrau) -> a    τ, T_r, T_p, M_p, T_s e erro de Vt(t)
    lab[e9 c1.1]> lgr                     polos de malha aberta e fechada no lugar das raízes
"""
import contextlib
import datetime as dt
import io
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .. import relatorio as Rl
from ..captura import Captura
from ..instrumentos import ControleSimulado, OsciloscopioArquivo, TektronixTBS, Transcricao, base_de_tempo
from ..motor import MotorCC, ProjetoPD, ProjetoPID, ProjetoPI, RespostaMalha, previsao
from ..motor import componentes as Cp
from ..motor.projeto import VMAX
from ..roteiros import Experimento9, texto_si, valor_si
from . import painel_controle
from .cli import SessaoLab
from .motor import SessaoMotor, _g, estado

NAN = math.nan
DADOS_2022 = Path(__file__).resolve().parent.parent / "dados" / "exp8_2022_anotacoes.json"
# (símbolo, unidade, escala SI → tela, casas, tolerância: relativa; absoluta, em fração, para M_p e e_ss)
METRICAS = {"tau": ("τ", "ms", 1e3, 0, 0.15), "tr": ("T_r", "ms", 1e3, 0, 0.15), "tp": ("T_p", "ms", 1e3, 0, 0.15),
            "mp": ("M_p", "%", 1e2, 1, 0.05), "ts": ("T_s", "ms", 1e3, 0, 0.20), "ess": ("e_ss", "%", 1e2, 2, 0.03)}

AJUDA_CONTROLE = """
Experimento 9 – controle do motor CC. Comandos (entre parênteses, o atalho):

  modelo [ref2022|<pasta Exp. 8>]  Motor (K, Kt, τ, K1) vindo do Exp. 8; ou digitado:
         [K=211 Kt=5m tau=0,494 K1=9e6 igv=8,7u]   (igv: A de ig por volt de Vg)
  conectar [recurso|sim|pasta]  Abre o osciloscópio (sim = malha simulada, só para ensaiar).
  casos / caso <id> / proximo (n)  As 4 tabelas da folha (1: PI sem carga, 2: PD/PID sem carga,
                                3: PI com Vg = 6 e 9 V, 4: PD/PID com Vg = 5 e 8 V).
  teoria (t)                    O que montar nesta linha, a resposta prevista e a tela sugerida.
  projeto [todos]               Ganhos, especificações, polos de malha aberta e fechada e a resposta
                                prevista (τ, T_r, T_p, M_p, T_s, e_ss) da linha (ou de todas).
  circuito [c2 <F>]             R, R2, C1 e C2 do PI/PD/PID analógico (calculados e da série E24/E6).
  preparar [s/div] / armar      Trigger em CH1 subindo, aquisição única; aplique o degrau.
  adquirir (a) [n]              Lê CH1 (referência) e CH2 (Vt): mede e compara com o previsto.
  calcular (c)                  Refaz as contas da última captura (depois de 'caso' ou 'set').
  lgr                           Lugar das raízes com os polos de malha aberta e fechada (figura).
  tabela [1..4]                 Tabelas da folha (medido; previsto onde ainda não há captura).
  grafico <1..4>                Respostas medidas da tabela.
  set tipo pd|pid|auto          Controlador de posição (auto: PD sem carga, PID com carga).
  set tp <s> | tp auto          T_p escolhido (padrão: o menor que não satura o amp-op em nenhuma linha).
  set vmax <V> | vgrau <V/°> | igv <A/V> | sonda <1|10|off> | diagnostico|abrir on|off
  descartar [n] / retomar       Como nos outros roteiros.   status, erro, exp <6|7|8|9>, help (?), quit (q)

Ligações: CH1 na referência (entrada do detector de erro), CH2 no sensor (tacômetro ou posição).
Ordem típica: modelo ref2022 -> caso 1.1 -> projeto -> circuito -> (monta) -> preparar -> (degrau) -> a -> n ...
""".strip("\n")


def formatar(chave, valor, unidade=True):
    _, un, escala, casas, _ = METRICAS[chave]
    if chave in ("mp", "ess") and abs(valor) < 0.5 * 10 ** -(casas + 2):
        valor = 0.0                 # sem o "−0,00 %"
    return Rl.num(valor, casas, un if unidade else "", escala)


@dataclass
class ResultadoControle:
    roteiro: object
    caso: object
    captura: object
    medida: RespostaMalha
    projeto: object
    v_por_unidade: float
    avisos: list
    numero: int = 0
    quando: str = field(default_factory=lambda: dt.datetime.now().isoformat(timespec="seconds"))
    previsto: dict = field(default_factory=dict)

    def valores(self):
        m = self.medida.metricas
        return {k: m[k] for k in METRICAS}

    def titulo(self):
        return f"Exp. {self.roteiro.numero} · Tabela {self.caso.tabela} · caso {self.caso.id} ({self.caso.rotulo})"

    def captura_texto(self):
        m = self.medida
        return (f"{len(m.t)} pontos, dt = {texto_si(self.captura.dt, 's')}, LSB = {m.lsb * 1e3:.3g} mV, "
                f"média móvel de {texto_si(m.suavizacao, 's')}")

    def comparacoes(self):
        """[(chave, medido, previsto, desvio, ok)]; para M_p e e_ss o desvio é absoluto (em fração)."""
        out = []
        for chave, exp in self.valores().items():
            teo = self.previsto.get(chave, NAN)
            if math.isnan(exp) or math.isnan(teo):
                out.append((chave, exp, teo, NAN, None))
            elif chave in ("mp", "ess"):
                out.append((chave, exp, teo, exp - teo, abs(exp - teo) <= METRICAS[chave][4]))
            else:
                d = (exp - teo) / teo if teo else NAN
                out.append((chave, exp, teo, d, None if math.isnan(d) else abs(d) <= METRICAS[chave][4]))
        return out

    def linhas_texto(self):
        out = [f"{'grandeza':<10}{'osciloscópio':>14}{'previsto':>12}{'desvio':>10}"]
        for chave, exp, teo, desvio, ok in self.comparacoes():
            if math.isnan(desvio):
                d = "–"
            elif chave in ("mp", "ess"):
                d = f"{desvio * 100:+.1f} pp".replace(".", ",")
            else:
                d = f"{desvio * 100:+.1f} %".replace(".", ",")
            out.append(f"{METRICAS[chave][0]:<10}{formatar(chave, exp):>14}{formatar(chave, teo):>12}{d:>10}   {estado(ok)}")
        return out

    def texto(self):
        cab = [f"#{self.numero:02d}  {self.titulo()}", f"     [{self.captura_texto()}]", ""]
        rodape = ["", "  (previsto: simulação do modelo do Exp. 8 com o controlador projetado; T_r de 10 a 90 %, "
                      "T_s na faixa de ±2 %, τ = tempo até 63,2 %)"]
        return "\n".join(cab + ["  " + l for l in self.linhas_texto()] + rodape + [f"  ! {a}" for a in self.avisos])

    def como_dict(self):
        num = lambda x: None if x is None or (isinstance(x, float) and math.isnan(x)) else float(x)
        m = self.medida.metricas
        return dict(numero=self.numero, quando=self.quando, experimento=self.roteiro.numero, caso=self.caso.id,
                    tabela=self.caso.tabela, rotulo=self.caso.rotulo, vg=self.caso.vg,
                    valores={k: num(v) for k, v in self.valores().items()},
                    previsto={k: num(v) for k, v in self.previsto.items()},
                    patamares={k: num(m[k]) for k in ("y0", "yf", "ref")}, dt=self.captura.dt,
                    lsb=self.medida.lsb, suavizacao=self.medida.suavizacao, avisos=self.avisos,
                    origem=self.captura.origem, v_por_unidade=self.v_por_unidade)


def analisar_controle(captura, roteiro, caso, projeto, v_por_unidade, numero=0):
    medida = RespostaMalha(captura)
    m = medida.metricas
    avisos = []
    for canal, meta in captura.meta.items():
        if isinstance(meta, dict) and meta.get("cortado"):
            avisos.append(f"{canal} saiu da tela (sinal cortado): aumente V/div")
    if not medida.tem_entrada:
        avisos.append("CH1 sem degrau de referência: o começo da resposta foi estimado só por CH2 e o erro não foi medido")
    else:
        alvo = projeto.referencia * v_por_unidade
        if abs(m["ref"] - alvo) > 0.1 * alvo:
            avisos.append(f"o degrau em CH1 é de {m['ref']:.2f} V; a referência de {projeto.referencia:g} {projeto.unidade} "
                          f"deveria dar {alvo:.2f} V (confira a fonte da referência, ou a sonda com 'set sonda')".replace(".", ","))
    if not medida.acomodou:
        avisos.append("a resposta não acomodou na janela (T_s indeterminado): aumente s/div")
    if m["banda"] > 0.0201:
        avisos.append(f"T_s medido na faixa de ±{m['banda'] * 100:.1f} % (não ±2 %): o degrau ocupa poucos níveis do "
                      "conversor, e a faixa de 2 % ficaria abaixo de 1,5 LSB".replace(".", ","))
    if medida.lsb and abs(m["yf"] - m["y0"]) / medida.lsb < 25:
        avisos.append(f"CH2 ocupa só {abs(m['yf'] - m['y0']) / medida.lsb:.0f} níveis do conversor: diminua V/div")
    pico = projeto.pico_controle()
    if pico > projeto.vmax:
        avisos.append(f"o modelo pede |Va| = {pico:.0f} V ao amp-op (limite {projeto.vmax:g} V): na bancada ele satura "
                      "e a resposta sai mais lenta que a prevista")
    return ResultadoControle(roteiro, caso, captura, medida, projeto, v_por_unidade, avisos, numero)


class SessaoControle(SessaoMotor):
    COMANDOS = {**SessaoMotor.COMANDOS}
    ATALHOS = dict(SessaoMotor.ATALHOS)

    def _ao_entrar(self):
        if not isinstance(self.roteiro, Experimento9):
            return
        if not hasattr(self, "capturas") or getattr(self, "_exp9", None) is None:
            self.capturas = {}
            self.anotacoes = []
            self.opcoes_projeto = {}
            self._unico = False
            self._exp9 = True
            self.motor, self.igv, self.origem_modelo = None, NAN, ""
            self.opcoes = {}               # tipo, tp, vmax, vgrau
            self._tp_cache = {}

    def _descricao_roteiro(self):
        return "CH1 na referência, CH2 no sensor (tacômetro ou posição)"

    # ------------------------------------------------------------ modelo
    def _definir_modelo(self, motor, igv, origem):
        self.motor, self.igv, self.origem_modelo, self._tp_cache = motor, igv, origem, {}
        self.pasta.escrever("modelo_exp9.json", json.dumps(
            dict(K=motor.K, Kt=motor.Kt, tau=motor.tau, K1=None if math.isnan(motor.K1) else motor.K1,
                 igv=None if math.isnan(igv) else igv, origem=origem, opcoes=self.opcoes), indent=1, ensure_ascii=False))

    def _exigir_motor(self):
        if self.motor is None:
            raise ValueError("sem modelo do motor: use 'modelo ref2022' (dados do Exp. 8 de 2022), 'modelo <pasta da "
                             "sessão do Exp. 8>' ou 'modelo K=... Kt=... tau=... K1=... igv=...'")
        return self.motor

    @staticmethod
    def _do_exp8(sessao8, origem):
        motor = sessao8.identificacao().motor()
        ls = sessao8.leituras()
        pts = [(ls[c.id]["va"], ls[c.id]["ig"]) for c in sessao8.roteiro.casos() if c.carga and ls[c.id].tem("ig")]
        igv = float(sum(v * i for v, i in pts) / sum(v * v for v, _ in pts)) if pts else NAN
        return motor, igv, origem

    def cmd_modelo(self, args):
        if not args:
            return self._mostrar_modelo()
        raiz = str(self.pasta.caminho.parent)
        if len(args) == 1 and args[0].lower() == "ref2022":
            s8 = SessaoLab(raiz, False, 8)
            s8.anotacoes = json.loads(DADOS_2022.read_text(encoding="utf-8"))
            self._definir_modelo(*self._do_exp8(s8, "dados do Exp. 8 de 2022 (outro grupo/ano; só para referência)"))
        elif len(args) == 1 and Path(args[0]).is_dir():
            s8 = SessaoLab(raiz, False, 8)
            with contextlib.redirect_stdout(io.StringIO()):
                s8.cmd_retomar([args[0]])
            self._definir_modelo(*self._do_exp8(s8, f"sessão do Exp. 8: {args[0]}"))
        else:
            v = {}
            for a in args:
                chave, _, valor = a.partition("=")
                if chave.lower() not in ("k", "kt", "tau", "k1", "igv") or not valor:
                    raise ValueError("uso: modelo ref2022 | modelo <pasta> | modelo K=211 Kt=5m tau=0,494 K1=9e6 igv=8,7u")
                v[chave.lower()] = valor_si(valor)
            if not all(k in v for k in ("k", "kt", "tau")):
                raise ValueError("faltam K, Kt e tau")
            self._definir_modelo(MotorCC(v["k"], v["kt"], v["tau"], v.get("k1", NAN)), v.get("igv", NAN), "digitado")
        self._mostrar_modelo()

    def _mostrar_modelo(self):
        m = self._exigir_motor()
        print(f"  modelo ({self.origem_modelo}): K = {_g(m.K, 'rpm/V')}, Kt = {_g(m.Kt, 'V/rpm')}, "
              f"τ = {_g(m.tau * 1e3, 'ms')}, K1 = {_g(m.K1, 'rpm/A')}")
        print((f"  carga: ig = Vg × {_g(self.igv * 1e6, 'µA/V')} (ig proporcional à tensão do gerador; "
               "ajuste com 'set igv <A/V>')") if not math.isnan(self.igv) else
              "  carga: sem igv — defina com 'set igv <A/V>' para simular as linhas com Vg")

    # ------------------------------------------------------------ projeto
    def _v_por_unidade(self, caso):
        return self._exigir_motor().Kt if caso.malha == "pi" else self.opcoes.get("vgrau", self.roteiro.v_por_grau)

    def _classe_posicao(self, caso):
        tipo = self.opcoes.get("tipo", "auto")
        return ProjetoPID if tipo == "pid" or (tipo == "auto" and caso.carga) else ProjetoPD

    def _ig(self, caso):
        if not caso.carga:
            return 0.0
        if math.isnan(self.igv):
            raise ValueError("falta a relação ig/Vg do gerador: 'set igv <A/V>' (ou 'modelo ... igv=...')")
        return caso.vg * self.igv

    def _projeto(self, caso):
        m = self._exigir_motor()
        r, vmax = self.roteiro, self.opcoes.get("vmax", VMAX)
        if caso.malha == "pi":
            return ProjetoPI(m, r.referencia_rpm, self._ig(caso), r.fator_tr, vmax)
        tp = self.opcoes.get("tp") or self._tp_padrao(caso.tabela)
        return self._classe_posicao(caso)(m, r.referencia_graus, tp, r.mp, self._ig(caso), vmax=vmax, reducao=r.reducao)

    def _tp_padrao(self, tabela):
        """O menor T_p com que nenhuma linha da tabela satura o amp-op. É um só por tabela, porque os ganhos do
        controlador não mudam com Vg: o circuito montado é o mesmo nas linhas de Vg = 5 e 8 V."""
        chave = (self.motor, tuple(sorted(self.opcoes.items())), self.igv, tabela)
        if self._tp_cache.get(chave):
            return self._tp_cache[chave]
        m, r = self.motor, self.roteiro
        tps = []
        for caso in r.casos():
            if caso.malha != "pd" or caso.tabela != tabela:
                continue
            p = self._classe_posicao(caso)(m, r.referencia_graus, None, r.mp, self._ig(caso),
                                           vmax=self.opcoes.get("vmax", VMAX), reducao=r.reducao)
            if p.pico_controle() > p.vmax:
                tps.append(p.tp_minimo())
        tp = max((x for x in tps if x), default=None) or float(f"{m.tau:.2g}")
        self._tp_cache[chave] = tp
        return tp

    def _linhas_projeto(self, caso):
        p = self._projeto(caso)
        v = self._v_por_unidade(caso)
        print(f"\n  {p.nome} – caso {caso.id} ({caso.descricao})" + (f", ig = {p.ig * 1e6:.1f} µA" if p.ig else ""))
        print(f"    {p.ganhos_texto()}" + (f"   (T_p = {p.tp * 1e3:.0f} ms)" if hasattr(p, "tp") else ""))
        for item, pedido, obtido, ok in p.especificacao():
            print(f"    {item:<52}{pedido:>12}{obtido:>12}   {'OK' if ok else 'NÃO ATENDE'}")
        polo = lambda x: (f"{x.real:.3g}" if abs(x.imag) < 1e-6 else f"{x.real:.3g} ± j{abs(x.imag):.3g}").replace(".", ",")
        ma = np.roots(p.direto().den)
        print("    polos de malha aberta:  " + "; ".join(dict.fromkeys(polo(x) for x in sorted(ma, key=lambda x: x.real))))
        print("    polos de malha fechada: " + "; ".join(dict.fromkeys(polo(x) for x in sorted(p.polos(), key=lambda x: x.real))))
        prev = previsao(p)
        print("    previsto na tela:  " + "   ".join(f"{METRICAS[k][0]} = {formatar(k, prev[k])}" for k in METRICAS)
              + f"   (CH1 = {p.referencia * v:.2f} V)".replace(".", ","))
        if p.ig and abs(prev["ess"]) > 0.005:
            print(f"    ! a carga deixa erro de {prev['ess'] * 100:.1f} % em regime: sem ação integral não se elimina"
                  .replace(".", ","))
        if p.pico_controle() > p.vmax:
            print(f"    ! o amp-op satura (|Va| = {p.pico_controle():.1f} V): 'set tp' maior, ou 'set vmax'".replace(".", ","))
        return p

    def cmd_projeto(self, args):
        self._exigir_motor()
        casos = self.roteiro.casos() if args[:1] == ["todos"] else [self.caso]
        dados = {}
        for caso in casos:
            dados[caso.id] = self._linhas_projeto(caso).como_dict()
        self.pasta.escrever("projeto_exp9.json", json.dumps(dados, indent=1, ensure_ascii=False, default=float))

    def cmd_circuito(self, args):
        caso = self.caso
        p, v = self._projeto(caso), self._v_por_unidade(caso)
        g = Cp.ganhos_eletricos(p, v)
        c2 = valor_si(args[1]) if len(args) == 2 and args[0].lower() == "c2" else Cp.escolher_c2(g["ki"])
        c = Cp.dimensionar(g["kp"], g["ki"], g["kd"], c2)
        real = Cp.comerciais(c)
        print(f"  caso {caso.id}: {c['tipo']} com Kp = {_g(g['kp'])}"
              + (f", Ki = {_g(g['ki'])} 1/s" if g["ki"] else "") + (f", Kd = {_g(g['kd'])} s" if g["kd"] else "")
              + (f"   (Kp em V/V = Kp em V/° ÷ {v:g} V/°)".replace(".", ",") if p.sensor == 1.0 else ""))
        print(f"  {'':<4}{'calculado':>14}{'comercial':>14}")
        for nome, un in (("R", "Ω"), ("R2", "Ω"), ("C1", "F"), ("C2", "F")):
            if c[nome] is not None:
                print(f"  {nome:<4}{texto_si(c[nome], un):>14}{texto_si(real[nome], un):>14}")
        gr = real["ganhos"]
        print(f"  com os valores comerciais: Kp = {_g(gr['kp'])}, Ki = {_g(gr['ki'])}, Kd = {_g(gr['kd'])}")
        print("  (o detector de erro compensa a inversão do amp-op; use trimpots multivoltas em R e R2 para acertar)")

    # ------------------------------------------------------------ roteiro
    def _prever(self, caso):
        try:
            return previsao(self._projeto(caso))
        except ValueError:
            return {}

    def _linha_caso(self, caso):
        res = self.capturas.get(caso.id)
        if res is None:
            return "–"
        v = res.valores()
        return "   ".join(f"{METRICAS[k][0]} = {formatar(k, v[k])}" for k in ("tau", "tr", "tp", "mp", "ts"))

    def cmd_casos(self, _args):
        for tabela in self.roteiro.tabelas():
            print(f"  Tabela {tabela.numero} – {tabela.titulo}")
            for id in tabela.casos:
                caso = self.roteiro.caso(id)
                marca = ">" if caso.id == self.caso.id else " "
                print(f"   {marca} {caso.id:<5} {caso.rotulo:<20} {self._linha_caso(caso)}")

    def cmd_caso(self, args):
        if not args:
            raise ValueError("uso: caso <id>  (veja os ids em 'casos')")
        self.caso = self.roteiro.caso(args[0])
        self.cmd_teoria([])

    def cmd_proximo(self, _args):
        ids = [c.id for c in self.roteiro.casos()]
        k = ids.index(self.caso.id)
        if k + 1 >= len(ids):
            raise ValueError(f"{self.caso.id} é a última linha")
        self.cmd_caso([ids[k + 1]])

    @staticmethod
    def _v_div_controle(degrau):
        """Menor V/div (1–2–5) em que o degrau com 20 % de sobressinal cabe em 4 divisões."""
        return next((v for v in (0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0) if 4.0 * v >= 1.2 * degrau), 10.0)

    def _s_div_sugerido(self):
        ts = self._prever(self.caso).get("ts", NAN)
        return base_de_tempo(2.5 * ts if not math.isnan(ts) else 2.0)

    def cmd_teoria(self, _args):
        caso = self.caso
        print(f"  Exp. 9 · Tabela {caso.tabela} · caso {caso.id} ({caso.rotulo}) · {caso.descricao}")
        if caso.carga:
            print(f"  Gerador a Vg = {texto_si(caso.vg, 'V')} com a carga ligada ao eixo desde antes do degrau.")
        if self.motor is None:
            print("  (sem modelo do motor ainda: 'modelo ref2022' ou 'modelo <pasta do Exp. 8>')")
            return
        p = self._linhas_projeto(caso)
        pico = self._v_por_unidade(caso) * p.referencia
        print(f"\n  Tela sugerida: {texto_si(self._s_div_sugerido(), 's')}/div com a borda de CH1 a 1 divisão da esquerda "
              f"('preparar'); CH1 e CH2 em {texto_si(self._v_div_controle(pico), 'V')}/div, centrados em 0 V "
              f"(degrau de {pico:.2f} V).".replace(".", ","))

    def cmd_comp(self, _args):
        self.cmd_circuito([])

    def cmd_set(self, args):
        if args and args[0].lower() in ("diagnostico", "abrir", "sonda", "suavizacao"):
            return SessaoLab.cmd_set(self, args)
        if len(args) != 2:
            raise ValueError("uso: set tipo pd|pid|auto | tp <s>|auto | vmax <V> | vgrau <V/°> | igv <A/V>")
        chave, valor = args[0].lower(), args[1].lower()
        if chave == "tipo":
            if valor not in ("pd", "pid", "auto"):
                raise ValueError("tipo: pd, pid ou auto")
            self.opcoes["tipo"] = valor
        elif chave in ("tp", "vmax", "vgrau"):
            if valor == "auto" and chave == "tp":
                self.opcoes.pop("tp", None)
            else:
                self.opcoes[chave] = valor_si(valor)
        elif chave == "igv":
            self.igv = valor_si(valor)
        else:
            raise ValueError(f"opção desconhecida: {chave}")
        self._tp_cache = {}
        if self.motor is not None:
            self._definir_modelo(self.motor, self.igv, self.origem_modelo)
        print(f"  {chave} = {valor}")

    def cmd_reset(self, _args):
        self.opcoes.clear()
        self._tp_cache = {}
        print("  opções de projeto de volta ao padrão")

    def cmd_ajustar(self, _args):
        self._mostrar_modelo()

    def cmd_anotar(self, _args):
        raise ValueError("o Exp. 9 não tem grandezas para anotar: tudo vem de CH1 e CH2")

    def cmd_lgr(self, _args):
        p = self._projeto(self.caso)
        self._mostrar(painel_controle.lugar(p, self.pasta.garantir() / f"lgr_exp9_c{self.caso.id}.png"))

    # ------------------------------------------------------------ medir
    def cmd_preparar(self, args):
        self._exigir_scope()
        s_div = valor_si(args[0]) if args else self._s_div_sugerido()
        nivel = self._projeto(self.caso).referencia * self._v_por_unidade(self.caso) / 2
        fila = self.scope.preparar(s_div, 0, nivel=nivel, unico=True)
        self._unico = True
        print(f"  {texto_si(s_div, 's')}/div, trigger em CH1 subindo a {texto_si(nivel, 'V')}, aquisição única: "
              "aplique o degrau de referência.")
        if fila:
            print(f"  fila do instrumento: {fila}")

    def cmd_conectar(self, args):
        if " ".join(args).lower() != "sim":
            return SessaoLab.cmd_conectar(self, args)
        if self.scope is not None:
            self.scope.fechar()
        scope = ControleSimulado()
        scope.transcricao = Transcricao(self.pasta.transcricao)
        print(f"  conectado: {scope.conectar()}")
        self.scope = scope

    def cmd_adquirir(self, args):
        self._exigir_scope()
        self._exigir_motor()
        if isinstance(self.scope, ControleSimulado):
            p = self._projeto(self.caso)
            v = self._v_por_unidade(self.caso)
            self.scope.projeto, self.scope.v_por_unidade = p, v
            self.scope.s_div = self._s_div_sugerido()
            self.scope.v_div = (self._v_div_controle(p.referencia * v),) * 2
        if isinstance(self.scope, OsciloscopioArquivo) and args:
            self.scope.proxima = int(args[0])
        captura = self.scope.adquirir()
        try:
            self._nova_captura(captura)
        finally:
            if isinstance(self.scope, TektronixTBS) and self._unico:
                self.scope.armar()
                print("  osciloscópio armado de novo para a próxima medida")
        if isinstance(self.scope, ControleSimulado):
            print("  (simulado: a captura é a previsão do modelo com ruído, não uma medida de bancada)")

    def _analisar(self, captura, numero):
        caso = self.caso
        if self.sonda:
            captura = captura.com_sonda(self.sonda)
        p, v = self._projeto(caso), self._v_por_unidade(caso)
        res = analisar_controle(captura, self.roteiro, caso, p, v, numero)
        res.previsto = previsao(p)
        self.capturas = {k: r for k, r in self.capturas.items() if r.numero != numero}
        self.capturas[caso.id] = res
        self.ultimo = res
        print(res.texto())
        pasta = self.pasta.salvar(res)
        print(f"  salvo em {pasta}")
        self._mostrar(self._figura(lambda caminho: painel_controle.resposta(res, caminho), pasta / "painel.png"))
        return res

    # ------------------------------------------------------------ relatório
    def _tabela_md(self, tabela):
        cab = ["linha"] + [f"{METRICAS[k][0]} ({METRICAS[k][1]})" for k in tabela.metricas]
        linhas = []
        for id in tabela.casos:
            caso, res = self.roteiro.caso(id), self.capturas.get(id)
            if res is not None:
                linhas.append([caso.rotulo] + [formatar(k, res.valores()[k], False) for k in tabela.metricas])
            else:
                prev = self._prever(caso)
                linhas.append([caso.rotulo + " (previsto)"] + [formatar(k, prev.get(k, NAN), False) for k in tabela.metricas])
        return f"**Tabela {tabela.numero}** – {tabela.titulo}\n\n" + Rl.tabela(cab, linhas)

    def cmd_tabela(self, args):
        tabelas = self.roteiro.tabelas()
        if args:
            tabelas = [t for t in tabelas if str(t.numero) == args[0]]
            if not tabelas:
                raise ValueError("o Experimento 9 tem as tabelas 1 a 4")
        texto = "\n\n".join([f"# Experimento 9 – {self.roteiro.titulo}"] + [self._tabela_md(t) for t in tabelas]) + "\n"
        print(texto)
        if not args:
            print(f"  salvo em {self.pasta.escrever('tabelas_exp9.md', texto)}")

    def cmd_grafico(self, args):
        tabela = next((t for t in self.roteiro.tabelas() if args and str(t.numero) == args[0]), None)
        if tabela is None:
            raise ValueError("uso: grafico <1..4>")
        resultados = [self.capturas[c] for c in tabela.casos if c in self.capturas]
        if not resultados:
            raise ValueError(f"nenhuma linha da Tabela {tabela.numero} foi adquirida ainda")
        self._mostrar(painel_controle.respostas(resultados,
                                                self.pasta.garantir() / f"respostas_exp9_tabela{tabela.numero}.png"))

    # ------------------------------------------------------------ sessão
    def cmd_retomar(self, args):
        pasta = self._pasta_para_retomar(args)
        if self._trocar_para_familia_gravada(pasta):
            return self.cmd_retomar([str(pasta)])
        arquivo = pasta / "modelo_exp9.json"
        if not arquivo.exists():
            raise ValueError(f"{pasta} não tem modelo_exp9.json (é uma sessão do Exp. 9?)")
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        self.pasta.caminho = pasta
        self.opcoes = dados.get("opcoes", {})
        nan = lambda x: NAN if x is None else x
        self._definir_modelo(MotorCC(dados["K"], dados["Kt"], dados["tau"], nan(dados["K1"])), nan(dados["igv"]),
                             dados["origem"])
        pastas = sorted((int(p.name[:2]), p) for p in pasta.glob("[0-9][0-9]_*") if p.is_dir())
        capturas, falhas, ultimo = {}, [], None
        for n, p in pastas:
            if not (p / "metricas.json").exists() or p.name.endswith("_descartada"):
                continue
            meta = json.loads((p / "metricas.json").read_text(encoding="utf-8"))
            if meta["experimento"] != 9:
                continue
            try:
                captura = Captura.carregar(p / "captura.npz")
                caso = self.roteiro.caso(meta["caso"])
                projeto = self._projeto(caso)
                res = analisar_controle(captura.com_sonda(self.sonda) if self.sonda else captura, self.roteiro, caso,
                                        projeto, self._v_por_unidade(caso), n)
                res.previsto = previsao(projeto)
            except Exception as exc:
                falhas.append(f"#{n:02d} ({exc})")
                continue
            res.quando = meta.get("quando", res.quando)
            capturas[caso.id] = ultimo = res
        self.capturas = capturas
        self.numero = pastas[-1][0] if pastas else 0
        if ultimo is not None:
            self.ultimo, self.ultima_captura, self.caso = ultimo, ultimo.captura, ultimo.caso
        print(f"  retomando {pasta}: {len(capturas)} linhas medidas; a próxima captura será a #{self.numero + 1:02d}")
        if falhas:
            print("  não reanalisadas: " + "; ".join(falhas))
        self.cmd_casos([])

    def cmd_status(self, _args):
        print(f"  Experimento 9, caso {self.caso.id} ({self.caso.rotulo})")
        scope = "não conectado" if self.scope is None else f"{self.scope.nome} {getattr(self.scope, 'idn', '')}".rstrip()
        print(f"  osciloscópio: {scope}")
        print(f"  modelo: {self.origem_modelo or 'não definido'}   opções: {self.opcoes or 'padrão'}")
        print(f"  capturas: {self.numero}   linhas medidas: {len(self.capturas)}   pasta: {self.pasta.caminho}")

    def cmd_help(self, _args):
        print(AJUDA_CONTROLE)

    def prompt(self):
        return f"lab[e9 c{self.caso.id}]> "

    @staticmethod
    def _separar(linha):
        return SessaoLab._separar(linha)


for _nome in ("modelo", "circuito"):
    SessaoControle.COMANDOS[_nome] = getattr(SessaoControle, f"cmd_{_nome}")
