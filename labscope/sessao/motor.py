"""Sessão do Experimento 8 (motor CC): o mesmo prompt dos outros roteiros, com o
que muda num experimento sem circuito para montar.

Cada linha das tabelas é uma tensão de armadura. A partida do motor (a fonte
ligando) dá Va, Vt e τ pelo osciloscópio; a velocidade, a corrente do gerador e
qualquer valor lido no multímetro entram digitados:

    lab[e8 c1.4]> a              Va, Vt e τ da partida
    lab[e8 c1.4]> w=1020         velocidade lida no tacômetro (rpm)
    lab[e8 c2.4]> ig=120m        corrente do gerador (A, aceita prefixo)

O que é digitado vale mais que o que veio do osciloscópio. A cada valor novo a
sessão compara com o que as outras linhas já medidas preveem (as retas de
mínimos quadrados sem a linha em questão), para um ponto fora da reta aparecer
na hora.
"""
import datetime as dt
import json
import math
import re
from dataclasses import dataclass, field

import numpy as np

from .. import relatorio as Rl
from ..captura import Captura
from ..instrumentos import MotorSimulado, OsciloscopioArquivo, TektronixTBS, Transcricao, base_de_tempo
from ..motor import DegrauMotor, Identificacao, Leitura, ProjetoPD, ProjetoPI, ProjetoPID
from ..motor.projeto import VMAX
from ..roteiros import ANOTAVEIS, APELIDOS, GRANDEZAS, Experimento8, grandeza, texto_si, valor_si
from . import painel_motor
from .cli import SessaoLab

NAN = math.nan
# desvio aceito entre o valor lido e o previsto pelas outras linhas
TOLERANCIA = {"va": 0.08, "vt": 0.10, "vtc": 0.10, "w": 0.10, "tau": 0.25, "ig": 0.20}
# valores acima disso quase certamente foram digitados na unidade errada
LIMITE = {"va": 50.0, "vt": 100.0, "vtc": 100.0, "w": 20000.0, "tau": 30.0, "ig": 10.0}
_TAU_PADRAO = 0.3          # s, para sugerir a tela antes de medir o primeiro τ

AJUDA_MOTOR = """
Experimento 8 – motor CC. Comandos (entre parênteses, o atalho):

  conectar [recurso|sim|pasta]  Abre o osciloscópio (sim = motor simulado, para ensaiar).
  casos                         As duas tabelas com tudo que já foi medido.
  caso <id>                     Escolhe a linha (caso 1.4 = Tabela 1, Va = 4 V; 2.4 = com carga).
  proximo (n)                   Vai para a linha seguinte da mesma tabela.
  teoria (t)                    O que fazer nesta linha, o valor esperado e a tela sugerida.
  preparar [s/div]              Arma o osciloscópio para a partida: trigger em CH1 subindo
                                (meio Va) e aquisição única. Depois é só ligar a fonte.
  armar                         Arma de novo, sem mudar a tela (o 'adquirir' já rearma).
  adquirir (a) [n]              Lê CH1 (Va) e CH2 (Vt): Va, Vt (ou V't) e τ, grava e abre o painel.
  w=<rpm>  ig=<A>  vt=<V>       Anota um valor lido nos instrumentos (vale mais que o do
  vt'=<V>  va=<V>  tau=<s>      osciloscópio). 'w=-' apaga. Em outra linha: anotar 1.4 w 1020.
  calcular (c)                  Refaz as contas da última captura (depois de 'caso').
  ajustar                       Mínimos quadrados: KKt, K, Kt (e KKt/K), τ médio, K1Kt e K1.
  tabela [1|2]                  Tabelas do roteiro preenchidas, com as constantes.
  grafico <1|2|partidas [2]>    Retas de mínimos quadrados (1: Vt×Va, ω×Va, Vt×ω e τ; 2: V1t×ig)
                                ou as partidas medidas, uma por linha da tabela.
  projeto [tp <s>] [vmax <V>]   PI de velocidade (1000 rpm, Tr 15 % menor) e PD/PID de posição
          [ig <A>] [rpm <ω>]    (60°, Mp ≤ 20 %, Tp escolhido; padrão Tp = τ), simulados com e
          [graus <θ>]           sem carga, conferindo o sinal de controle (|Va| ≤ vmax, padrão 10 V,
          [reducao <N>]         o que o amp-op entrega). Posição no eixo de saída, após a redução
                                30:1 do CE110. 'projeto padrao' volta às opções iniciais.
  descartar [n] / retomar       Como nos outros roteiros.
  ver (v) / painel (p)          A última captura crua / o último painel.
  set diagnostico|abrir on|off, set sonda <1|10|off>, scpi <comando>, recursos, status, erro
  exp <6|7|8|9>   help (?)   quit (q)

Ligações: CH1 na armadura do motor (Va), CH2 no tacômetro (Vt), terras juntos.
Ordem típica:  conectar -> caso 1.1 -> preparar -> (liga a fonte) -> a -> w=... -> n -> ...
               ... -> caso 2.1 -> (liga a carga) -> preparar -> a -> ig=... -> ... -> ajustar -> projeto
""".strip("\n")


def formatar(chave, valor, unidade=True):
    g = GRANDEZAS[chave]
    return Rl.num(valor, g.casas, g.unidade if unidade else "", g.escala)


def _g(x, unidade=""):
    """4 algarismos significativos, com vírgula."""
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "–"
    return f"{x:.4g} {unidade}".strip().replace(".", ",").replace("-", "−")


@dataclass
class ResultadoMotor:
    roteiro: object
    caso: object
    captura: object
    medida: DegrauMotor
    avisos: list
    numero: int = 0
    quando: str = field(default_factory=lambda: dt.datetime.now().isoformat(timespec="seconds"))
    previsto: dict = field(default_factory=dict)    # grandeza -> valor esperado pelas outras linhas

    @property
    def saida(self):
        """Na Tabela 2 o patamar de CH2 é o V't (com carga)."""
        return "vtc" if self.caso.carga else "vt"

    def valores(self):
        return {"va": self.medida.va, self.saida: self.medida.vt, "tau": self.medida.tau}

    def titulo(self):
        return (f"Exp. {self.roteiro.numero} · Tabela {self.caso.tabela} · caso {self.caso.id} "
                f"({self.caso.rotulo}) · {self.caso.descricao}")

    def captura_texto(self):
        m = self.medida
        return (f"{len(m.t)} pontos, dt = {texto_si(self.captura.dt, 's')}, LSB = {m.lsb * 1e3:.3g} mV, "
                f"média móvel de {texto_si(m.suavizacao, 's')}"
                + ("" if m.tem_entrada else ", sem degrau em CH1"))

    def comparacoes(self):
        """[(chave, medido, previsto, desvio, ok)] do que a captura mediu."""
        out = []
        for chave, exp in self.valores().items():
            teo = self.previsto.get(chave, NAN)
            out.append((chave, exp) + comparar(chave, exp, teo))
        return out

    def linhas_texto(self):
        out = [f"{'grandeza':<12}{'osciloscópio':>14}{'previsto':>14}{'desvio':>10}"]
        for chave, exp, teo, desvio, ok in self.comparacoes():
            d = "–" if math.isnan(desvio) else f"{desvio * 100:+.1f} %".replace(".", ",")
            out.append(f"{GRANDEZAS[chave].simbolo:<12}{formatar(chave, exp):>14}{formatar(chave, teo):>14}{d:>10}"
                       f"   {estado(ok)}")
        return out

    def texto(self):
        cab = [f"#{self.numero:02d}  {self.titulo()}", f"     [{self.captura_texto()}]", ""]
        d = self.medida.degrau
        extra = (f"  τ só pela curva (10 % → 63 %): {formatar('tau', d['tau_1063'])};  "
                 f"resíduo RMS de CH2 contra a exponencial: {self.medida.residuo() * 1e3:.1f} mV").replace(".", ",")
        rodape = ["", extra, "  (previsto: retas de mínimos quadrados das outras linhas já medidas; Va: o pedido)"]
        return "\n".join(cab + ["  " + l for l in self.linhas_texto()] + rodape + [f"  ! {a}" for a in self.avisos])

    def como_dict(self):
        num = lambda x: None if x is None or (isinstance(x, float) and math.isnan(x)) else float(x)
        return dict(numero=self.numero, quando=self.quando, experimento=self.roteiro.numero, caso=self.caso.id,
                    tabela=self.caso.tabela, rotulo=self.caso.rotulo, va_pedido=self.caso.va, carga=self.caso.carga,
                    valores={k: num(v) for k, v in self.valores().items()},
                    previsto={k: num(v) for k, v in self.previsto.items()},
                    degrau={k: num(v) for k, v in self.medida.degrau.items()}, dt=self.captura.dt,
                    lsb=self.medida.lsb, suavizacao=self.medida.suavizacao, avisos=self.avisos,
                    origem=self.captura.origem)


def comparar(chave, exp, teo):
    """(previsto, desvio relativo, ok) — ok é None quando falta um dos lados."""
    if exp is None or teo is None or math.isnan(exp) or math.isnan(teo) or teo == 0:
        return teo, NAN, None
    desvio = (exp - teo) / teo
    return teo, desvio, abs(desvio) <= TOLERANCIA.get(chave, 0.1)


def estado(ok):
    return {True: "OK", False: "CONFERIR", None: ""}[ok]


def analisar_motor(captura, roteiro, caso, numero=0, suavizacao=None):
    """Mede a partida em `captura` para a linha `caso` e junta os avisos."""
    medida = DegrauMotor(captura, suavizacao=suavizacao)
    d = medida.degrau
    if math.isnan(d["tau"]) or d["tau"] <= 0:
        raise ValueError("CH2 não chega a 63 % do regime depois da partida: aumente s/div ou confira o trigger")
    avisos = []
    for canal, meta in captura.meta.items():
        if isinstance(meta, dict) and meta.get("cortado"):
            avisos.append(f"{canal} saiu da tela (sinal cortado): aumente V/div")
    if not medida.tem_entrada:
        avisos.append("CH1 sem degrau de Va: τ estimado só pela curva de CH2 (10 % e 63 %) e Va não medido")
    elif abs(medida.va - caso.va) > 0.1 * caso.va:
        avisos.append(f"Va medido em CH1 é {medida.va:.2f} V; a linha {caso.id} pede {caso.va:g} V "
                      "(confira a fonte, ou a sonda com 'set sonda')".replace(".", ","))
    if d["passo"] < 0:
        avisos.append("Vt desceu na partida: o tacômetro está com a polaridade invertida (o valor usado é o módulo)")
    if not medida.acomodou:
        avisos.append(f"janela curta: só {d['duracao'] * 1e3:.0f} ms depois da partida para τ = {d['tau'] * 1e3:.0f} ms "
                      "(precisa de 4 a 5 τ): Vt pode ainda não ter chegado ao regime, aumente s/div")
    if d["tau"] < 15 * captura.dt:
        avisos.append(f"só {d['tau'] / captura.dt:.0f} amostras até 63 %: diminua s/div para medir τ melhor")
    if medida.tem_entrada and abs(d["tau_1063"] - d["tau"]) > 0.2 * d["tau"]:
        avisos.append(f"a partida demora {(d['tau'] - d['tau_1063']) * 1e3:.0f} ms para começar depois de Va subir "
                      "(atrito estático?): o τ do cursor inclui esse atraso, o τ só pela curva não")
    if medida.lsb and medida.vt / medida.lsb < 25:
        avisos.append(f"CH2 ocupa só {medida.vt / medida.lsb:.0f} níveis do conversor: diminua V/div")
    return ResultadoMotor(roteiro, caso, captura, medida, avisos, numero)


class SessaoMotor(SessaoLab):
    COMANDOS = {**SessaoLab.COMANDOS, "anotar": None, "projeto": None, "armar": None, "proximo": None}
    ATALHOS = {**SessaoLab.ATALHOS, "n": "proximo", "próximo": "proximo", "prox": "proximo"}

    def _ao_entrar(self):
        if not hasattr(self, "capturas") or getattr(self, "_exp9", False):
            self._exp9 = False          # veio do Exp. 9: as capturas de lá não servem aqui
            self.capturas = {}          # id do caso -> ResultadoMotor mais recente
            self.anotacoes = []         # [{quando, caso, grandeza, valor}] na ordem em que foram digitadas
            self.opcoes_projeto = {}
            self._unico = False         # osciloscópio em aquisição única ('preparar')

    def _descricao_roteiro(self):
        return "CH1 na armadura (Va), CH2 no tacômetro (Vt)"

    # ------------------------------------------------------------ leituras
    def leituras(self, excluir=None):
        """{id: Leitura} de todas as linhas: osciloscópio, por cima o que foi
        digitado, e na Tabela 2 o Vt da Tabela 1 com a mesma Va quando ele não
        foi anotado. `excluir` deixa uma linha sem nada (para prevê-la)."""
        manuais = {}
        for a in self.anotacoes:
            manuais[(a["caso"], a["grandeza"])] = a["valor"]
        out = {}
        for caso in self.roteiro.casos():
            l = Leitura()
            out[caso.id] = l
            if caso.id == excluir:
                continue
            l.definir("va", caso.va, "nominal")
            res = self.capturas.get(caso.id)
            if res is not None:
                for chave, valor in res.valores().items():
                    l.definir(chave, valor, f"osc. #{res.numero:02d}")
            for chave in ANOTAVEIS:
                valor = manuais.get((caso.id, chave))
                if valor is not None:
                    l.definir(chave, valor, "manual")
        for caso in self.roteiro.casos():
            par = self.roteiro.par(caso)
            if caso.carga and caso.id != excluir and not out[caso.id].tem("vt") and out[par.id].tem("vt"):
                out[caso.id].definir("vt", out[par.id]["vt"], f"tab. 1, linha {par.id}")
        return out

    def identificacao(self, excluir=None):
        ls = self.leituras(excluir)
        tabela = lambda n: {k: l for k, l in ls.items() if self.roteiro.caso(k).tabela == n}
        return Identificacao.de(tabela(1), tabela(2))

    def previsao(self, caso):
        """O que as outras linhas já medidas dizem que esta linha deve dar."""
        ident = self.identificacao(excluir=caso.id)
        l = self.leituras()[caso.id]
        va = l["va"]
        out = {"va": caso.va, "vt": ident.prever("vt", va), "w": ident.prever("w", va), "tau": ident.prever("tau")}
        if caso.carga:
            out["vtc"] = ident.prever("vtc", ig=l["ig"], vt=l["vt"])
        return out

    def _faltam(self, caso):
        l = self.leituras()[caso.id]
        pedidas = ("vt", "w", "tau") if not caso.carga else ("vt", "ig", "vtc")
        dicas = {"vt": "a (osciloscópio) ou vt=<V>", "w": "w=<rpm> (tacômetro)", "tau": "a (osciloscópio)",
                 "ig": "ig=<A> (amperímetro)", "vtc": "a (osciloscópio) ou vt'=<V>"}
        return [f"{GRANDEZAS[k].simbolo}: {dicas[k]}" for k in pedidas if not l.tem(k)]

    def _salvar_anotacoes(self):
        self.pasta.escrever("anotacoes_exp8.json", json.dumps(self.anotacoes, indent=1, ensure_ascii=False))

    # ------------------------------------------------------------ conexão
    def cmd_conectar(self, args):
        if " ".join(args).lower() != "sim":
            return super().cmd_conectar(args)
        if self.scope is not None:
            self.scope.fechar()
        scope = MotorSimulado()
        scope.transcricao = Transcricao(self.pasta.transcricao)
        print(f"  conectado: {scope.conectar()}")
        self.scope = scope

    def _s_div_sugerido(self):
        """s/div em que cabem 6 τ nas 9 divisões depois do trigger."""
        res = self.capturas.get(self.caso.id)
        tau = res.medida.tau if res else self.identificacao().tau
        return base_de_tempo(6 * (tau if not math.isnan(tau) else _TAU_PADRAO))

    def _vt_previsto(self):
        p = self.previsao(self.caso)
        return p.get("vtc") if self.caso.carga and not math.isnan(p.get("vtc", NAN)) else p["vt"]

    @staticmethod
    def _v_div(pico):
        """Menor V/div (1–2–5) em que `pico` fica dentro de 3,5 divisões."""
        return next((v for v in (0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0) if 3.5 * v >= pico), 10.0)

    def cmd_preparar(self, args):
        self._exigir_scope()
        s_div = valor_si(args[0]) if args else self._s_div_sugerido()
        nivel = self.caso.va / 2
        fila = self.scope.preparar(s_div, 0, nivel=nivel, unico=True)
        self._unico = True
        print(f"  {texto_si(s_div, 's')}/div, trigger em CH1 subindo a {texto_si(nivel, 'V')}, aquisição única:")
        print(f"  com a fonte em {texto_si(self.caso.va, 'V')}, ligue a saída e depois 'a'.")
        if fila:
            print(f"  fila do instrumento: {fila}")

    def cmd_armar(self, _args):
        self._exigir_scope()
        if isinstance(self.scope, TektronixTBS):
            self.scope.armar()
        print("  armado: esperando a próxima partida (desligue e ligue a fonte)")

    # ------------------------------------------------------------ roteiro
    def _linha_caso(self, caso, leituras):
        l = leituras[caso.id]
        chaves = ("vt", "w", "tau") if not caso.carga else ("vt", "ig", "vtc", "v1t")
        partes = [f"{GRANDEZAS[k].simbolo} = {formatar(k, l[k])}" for k in chaves]
        if l.fontes.get("va") not in (None, "nominal") and abs(l["va"] - caso.va) > 0.02 * caso.va:
            partes.insert(0, f"(Va medido {formatar('va', l['va'])})")
        return "   ".join(partes)

    def cmd_casos(self, _args):
        ls = self.leituras()
        for tabela in self.roteiro.tabelas():
            print(f"  Tabela {tabela.numero} – {tabela.titulo}")
            for id in tabela.casos:
                caso = self.roteiro.caso(id)
                marca = ">" if caso.id == self.caso.id else " "
                medido = any(ls[id].fontes.get(k, "nominal") not in ("nominal",) and not
                             ls[id].fontes[k].startswith("tab.") for k in ls[id].fontes)
                texto = self._linha_caso(caso, ls) if medido else "–"
                print(f"   {marca} {caso.id:<5} {caso.rotulo:<10} {texto}")

    def cmd_caso(self, args):
        if not args:
            raise ValueError("uso: caso <id>  (veja os ids em 'casos'; 1.x sem carga, 2.x com carga)")
        self.caso = self.roteiro.caso(args[0])
        self.cmd_teoria([])

    def cmd_proximo(self, _args):
        ids = [c.id for c in self.roteiro.casos() if c.tabela == self.caso.tabela]
        k = ids.index(self.caso.id)
        if k + 1 >= len(ids):
            raise ValueError(f"{self.caso.id} é a última linha da Tabela {self.caso.tabela}")
        self.cmd_caso([ids[k + 1]])

    def cmd_teoria(self, _args):
        caso = self.caso
        print(f"  Exp. 8 · Tabela {caso.tabela} · caso {caso.id} ({caso.rotulo}) · {caso.descricao}")
        if caso.carga:
            par = self.roteiro.par(caso)
            vt = self.leituras()[caso.id]
            print(f"  Fonte em {texto_si(caso.va, 'V')}, carga ligada ao gerador. Leia ig no amperímetro (ig=<A>);")
            print("  a partida no osciloscópio dá V't. Vt sem carga: "
                  + (f"{formatar('vt', vt['vt'])} ({vt.fontes['vt']})" if vt.tem("vt") else
                     f"ainda não medido (meça {par.id} ou anote vt=<V>)"))
        else:
            print(f"  Fonte em {texto_si(caso.va, 'V')}, gerador sem carga. A partida no osciloscópio dá Va, Vt e τ;")
            print("  leia a velocidade no tacômetro e anote com w=<rpm>.")
        p = self.previsao(caso)
        esperado = [f"{GRANDEZAS[k].simbolo} ≈ {formatar(k, v)}" for k, v in p.items()
                    if k != "va" and not math.isnan(v)]
        print("  esperado pelas outras linhas: " + ("   ".join(esperado) if esperado else
                                                     "nada ainda (precisa de 2 linhas medidas)"))
        res = self.capturas.get(caso.id)
        if res or any(a["caso"] == caso.id for a in self.anotacoes):
            print(f"  já medido: {self._linha_caso(caso, self.leituras())}")
        vt = self._vt_previsto()
        print(f"  Tela sugerida: {texto_si(self._s_div_sugerido(), 's')}/div com o trigger a 1 divisão da esquerda "
              "('preparar' faz isso e arma a aquisição única);")
        print(f"                 CH1 em {texto_si(self._v_div(caso.va), 'V')}/div; CH2 em "
              + (f"{texto_si(self._v_div(vt), 'V')}/div (Vt previsto de {Rl.num(vt, 2)} V)" if not math.isnan(vt)
                 else "uma escala em que Vt caiba (ainda sem previsão)") + ", os dois centrados em 0 V.")

    def cmd_comp(self, _args):
        l = self.leituras()[self.caso.id]
        for chave in ("va", "vt", "w", "tau", "ig", "vtc"):
            if l.tem(chave):
                print(f"  {GRANDEZAS[chave].simbolo:<4} = {formatar(chave, l[chave]):>12}   ({l.fontes[chave]})")
        for falta in self._faltam(self.caso):
            print(f"  falta {falta}")

    def cmd_set(self, args):
        if args and args[0].lower() in ("diagnostico", "abrir", "sonda", "suavizacao"):
            return super().cmd_set(args)
        if args and args[0].lower() in APELIDOS:
            return self.cmd_anotar(args)
        raise ValueError("no Exp. 8: set diagnostico|abrir on|off, set sonda <1|10|off>, ou uma grandeza "
                         "(set w 1020, que é o mesmo que w=1020)")

    def cmd_reset(self, _args):
        print("  no Exp. 8 não há componentes; para apagar uma anotação: <grandeza>=-  (ex.: w=-)")

    def cmd_lgr(self, _args):
        raise ValueError("o Exp. 8 não tem lugar das raízes no roteiro: use 'projeto' (polos das malhas projetadas)")

    # ------------------------------------------------------------ anotar
    def cmd_anotar(self, args):
        caso = self.caso
        if args and re.fullmatch(r"\d+\.\d+", args[0]):
            caso, args = self.roteiro.caso(args[0]), args[1:]
        if len(args) != 2:
            raise ValueError("uso: <grandeza>=<valor> (w=1020, ig=120m, vt'=2.47, tau=350m; '-' apaga) "
                             "ou anotar [caso] <grandeza> <valor>")
        g = grandeza(args[0])
        if g.chave not in ANOTAVEIS:
            raise ValueError(f"{g.simbolo} é calculado, não se anota")
        valor = None if args[1] in ("-", "apagar") else valor_si(args[1])
        if valor is not None and not 0 <= valor <= LIMITE[g.chave]:
            si = {"ig": "A (120 mA = 120m)", "tau": "s (350 ms = 350m)"}.get(g.chave, g.unidade)
            raise ValueError(f"{g.simbolo} = {args[1]} fora do esperado: o valor vai em {si}")
        self.anotacoes.append(dict(quando=dt.datetime.now().isoformat(timespec="seconds"), caso=caso.id,
                                   grandeza=g.chave, valor=valor))
        self._salvar_anotacoes()
        if valor is None:
            print(f"  {caso.id}: anotação de {g.simbolo} apagada")
        else:
            teo, desvio, ok = comparar(g.chave, valor, self.previsao(caso).get(g.chave, NAN))
            extra = "" if ok is None else (f"   (previsto {formatar(g.chave, teo)}, "
                                           f"{f'{desvio * 100:+.1f} %'.replace('.', ',')}  {estado(ok)})")
            print(f"  {caso.id}: {g.simbolo} = {formatar(g.chave, valor)}{extra}")
        self._resumo_linha(caso)

    def _resumo_linha(self, caso):
        print(f"  {caso.id} ({caso.rotulo}): {self._linha_caso(caso, self.leituras())}")
        faltam = self._faltam(caso)
        if faltam:
            print("  falta " + ";  ".join(faltam))
        elif caso.id != f"{caso.tabela}.{len(self.roteiro.tensoes)}":
            print("  linha completa: 'n' vai para a próxima")

    # ------------------------------------------------------------ medir
    def cmd_adquirir(self, args):
        self._exigir_scope()
        if isinstance(self.scope, MotorSimulado):
            self.scope.va, self.scope.carga = self.caso.va, self.caso.carga
            self.scope.s_div = self._s_div_sugerido()
            vt = self._vt_previsto()
            w, ig, _ = self.scope.regime()
            self.scope.v_div = (self._v_div(self.caso.va), self._v_div(vt if not math.isnan(vt) else 1.2 * w * self.scope.Kt))
        if isinstance(self.scope, OsciloscopioArquivo) and args:
            self.scope.proxima = int(args[0])
        captura = self.scope.adquirir()
        if self.diagnostico and isinstance(self.scope, TektronixTBS):
            print(f"  fila do instrumento: {self.scope.erros()}")
        try:
            self._nova_captura(captura)
        finally:
            if isinstance(self.scope, TektronixTBS) and self._unico:
                self.scope.armar()
                print("  osciloscópio armado de novo para a próxima partida")
        if isinstance(self.scope, MotorSimulado):
            print(f"  (simulado: o tacômetro marcaria {w:.0f} rpm" +
                  (f" e o amperímetro {ig * 1e3:.0f} mA)" if self.caso.carga else ")"))

    def _analisar(self, captura, numero):
        if self.sonda:
            captura = captura.com_sonda(self.sonda)
        res = analisar_motor(captura, self.roteiro, self.caso, numero)
        self.capturas = {k: v for k, v in self.capturas.items() if v.numero != numero}
        self.capturas[self.caso.id] = res
        res.previsto = self.previsao(self.caso)
        self.ultimo = res
        print(res.texto())
        pasta = self.pasta.salvar(res)
        print(f"  salvo em {pasta}")
        self._resumo_linha(self.caso)
        self._mostrar(self._figura(lambda caminho: painel_motor.partida(res, caminho), pasta / "painel.png"))
        return res

    def cmd_ajustar(self, _args):
        ident = self.identificacao()
        print(self.ajuste_texto(ident))

    @staticmethod
    def ajuste_texto(ident):
        def reta(nome, rotulo, r, u, uy):
            if r is None:
                return f"  {nome:<5}{rotulo:<10}faltam pontos (pelo menos 2 com o motor girando)"
            fora = f"; fora: {', '.join(r.excluidos)} (motor parado)" if r.excluidos else ""
            return (f"  {nome:<5}{rotulo:<10}a = {_g(r.a, u):<16}b = {_g(r.b, uy):<12}R² = {r.r2:.4f}".replace(".", ",")
                    + f"   (pela origem: {_g(r.a0, u)})   {r.n} pontos{fora}")
        linhas = ["  Mínimos quadrados, y = a·x + b (a é a constante; ao lado, a reta forçada pela origem)",
                  reta("KKt", "Vt × Va", ident.kkt, "V/V", "V"),
                  reta("K", "ω × Va", ident.k, "rpm/V", "rpm"),
                  reta("Kt", "Vt × ω", ident.kt, "V/rpm", "V")]
        if not math.isnan(ident.Kt_indireto):
            d = (ident.Kt - ident.Kt_indireto) / ident.Kt_indireto if not math.isnan(ident.Kt) else NAN
            linhas.append(f"       conferência: KKt/K = {_g(ident.Kt_indireto, 'V/rpm')}"
                          + ("" if math.isnan(d) else f"   (Kt do gráfico Vt × ω difere {d * 100:+.1f} %)".replace(".", ",")))
        if ident.taus:
            dp = "" if math.isnan(ident.tau_desvio) else f" ± {ident.tau_desvio * 1e3:.0f} ms (desvio padrão)"
            linhas.append(f"  τ    média de {len(ident.taus)} partidas sem carga: {ident.tau * 1e3:.0f} ms{dp}".replace(".", ","))
        else:
            linhas.append("  τ    nenhuma partida sem carga medida ainda")
        linhas.append(reta("K1Kt", "V1t × ig", ident.k1kt, "V/A", "V"))
        if not math.isnan(ident.K1):
            linhas.append(f"  K1   K1Kt/Kt = {_g(ident.K1, 'rpm/A')}")
        if not any(math.isnan(x) for x in (ident.K, ident.tau)):
            k1 = "" if math.isnan(ident.K1) else f" − {_g(ident.K1)}/({_g(ident.tau)} s + 1)·Ig(s)"
            linhas.append(f"  modelo: ω(s) = {_g(ident.K)}/({_g(ident.tau)} s + 1)·Va(s){k1}   [rpm]")
        return "\n".join(linhas)

    # ------------------------------------------------------------ relatório
    def _tabela_md(self, tabela, ls):
        chaves = tabela.metricas
        cab = ["linha"] + [f"{GRANDEZAS[k].simbolo} ({GRANDEZAS[k].unidade})" for k in chaves]
        linhas = []
        for id in tabela.casos:
            caso, l = self.roteiro.caso(id), ls[id]
            celulas = [caso.rotulo]
            for k in chaves:
                if k == "va":
                    celulas.append(formatar("va", l["va"], False) if l.fontes.get("va") != "nominal"
                                   else Rl.num(caso.va, 0))
                else:
                    celulas.append(formatar(k, l[k], False))
            linhas.append(celulas)
        return f"**Tabela {tabela.numero}** – {tabela.titulo}\n\n" + Rl.tabela(cab, linhas)

    def cmd_tabela(self, args):
        tabelas = self.roteiro.tabelas()
        if args:
            tabelas = [t for t in tabelas if str(t.numero) == args[0]]
            if not tabelas:
                raise ValueError("o Experimento 8 tem as tabelas 1 (sem carga) e 2 (com carga)")
        ls = self.leituras()
        partes = [f"# Experimento 8 – {self.roteiro.titulo}"] + [self._tabela_md(t, ls) for t in tabelas]
        if not args:
            partes.append("**Constantes**\n\n```\n" + self.ajuste_texto(self.identificacao()) + "\n```")
        texto = "\n\n".join(partes) + "\n"
        print(texto)
        if not args:
            print(f"  salvo em {self.pasta.escrever('tabelas_exp8.md', texto)}")

    def cmd_grafico(self, args):
        if not args:
            raise ValueError("uso: grafico 1 (retas sem carga) | grafico 2 (V1t × ig) | grafico partidas [1|2]")
        destino = self.pasta.garantir()
        if args[0] == "1":
            caminho = painel_motor.retas(self.identificacao(), destino / "grafico_exp8_tabela1.png")
        elif args[0] == "2":
            caminho = painel_motor.carga(self.identificacao(), self.leituras(), destino / "grafico_exp8_tabela2.png")
        elif args[0].startswith("part"):
            n = int(args[1]) if len(args) > 1 else 1
            resultados = [self.capturas[c] for c in next(t for t in self.roteiro.tabelas() if t.numero == n).casos
                          if c in self.capturas]
            if not resultados:
                raise ValueError(f"nenhuma partida da Tabela {n} foi adquirida ainda")
            caminho = painel_motor.partidas(resultados, destino / f"partidas_exp8_tabela{n}.png")
        else:
            raise ValueError("uso: grafico 1 | grafico 2 | grafico partidas [1|2]")
        self._mostrar(caminho)

    # ------------------------------------------------------------ projeto
    def ig_de_operacao(self, motor, rpm):
        """ig da Tabela 2 interpolado na Va que dá `rpm` sem carga."""
        ls = self.leituras()
        pts = sorted((ls[c.id]["va"], ls[c.id]["ig"]) for c in self.roteiro.casos() if c.carga and ls[c.id].tem("ig"))
        if not pts:
            return 0.0
        va, ig = zip(*pts)
        return float(np.interp(rpm / motor.K, va, ig))

    def projetos(self):
        """Os controladores pedidos, com as opções de 'projeto'. Sem carga: PI e PD;
        com a carga (se já houver K1): PI, PD e PID."""
        motor = self.identificacao().motor()
        o = {"rpm": self.roteiro.referencia_rpm, "graus": self.roteiro.referencia_graus, **self.opcoes_projeto}
        tp, vmax, n = o.get("tp"), o.get("vmax", VMAX), o.get("reducao", self.roteiro.reducao)
        ig = o.get("ig", self.ig_de_operacao(motor, o["rpm"]) if motor.com_carga else 0.0)
        out = {"pi": ProjetoPI(motor, o["rpm"], vmax=vmax), "pd": ProjetoPD(motor, o["graus"], tp, vmax=vmax, reducao=n)}
        if motor.com_carga and ig:
            out.update(pi_carga=ProjetoPI(motor, o["rpm"], ig, vmax=vmax),
                       pd_carga=ProjetoPD(motor, o["graus"], tp, ig=ig, vmax=vmax, reducao=n),
                       pid_carga=ProjetoPID(motor, o["graus"], tp, ig=ig, vmax=vmax, reducao=n))
        return out

    def cmd_projeto(self, args):
        args = [a.lower() for a in args]
        if args[:1] in (["padrao"], ["padrão"]):
            self.opcoes_projeto = {}
            args = args[1:]
        if len(args) % 2:
            raise ValueError("uso: projeto [tp <s>] [vmax <V>] [reducao <N>] [ig <A>] [rpm <ω>] [graus <θ>]   "
                             "(ex.: projeto tp 300m)")
        for chave, valor in zip(args[::2], args[1::2]):
            if chave not in ("tp", "vmax", "reducao", "ig", "rpm", "graus"):
                raise ValueError(f"opção desconhecida: {chave} (tp, vmax, reducao, ig, rpm ou graus)")
            self.opcoes_projeto[chave] = valor_si(valor)
        projetos = self.projetos()
        motor = projetos["pi"].motor
        print(f"  modelo: K = {_g(motor.K, 'rpm/V')}, Kt = {_g(motor.Kt, 'V/rpm')}, τ = {_g(motor.tau * 1e3, 'ms')}"
              + ("" if not motor.com_carga else f", K1 = {_g(motor.K1, 'rpm/A')}"))
        print(f"  posição no eixo de saída, depois da redução {projetos['pd'].reducao:g}:1 ('projeto reducao 1' para o "
              f"eixo do motor); |Va| ≤ {projetos['pi'].vmax:g} V ('projeto vmax <V>')")
        titulos = {"pi": "sem carga", "pd": "sem carga", "pi_carga": "com carga", "pd_carga": "com carga",
                   "pid_carga": "com carga"}
        for chave, p in projetos.items():
            print(f"\n  {p.nome} – {titulos[chave]} (referência {_g(p.referencia, p.unidade)}"
                  + (f", ig = {p.ig * 1e3:.0f} mA" if p.ig else "") + ")")
            print(f"    {p.ganhos_texto()}")
            for item, pedido, obtido, ok in p.especificacao():
                print(f"    {item:<52}{pedido:>12}{obtido:>12}   {'OK' if ok else 'NÃO ATENDE'}")
            if isinstance(p, ProjetoPD) and p.pico_controle() > p.vmax:
                tp = p.tp_minimo()
                print("    ! o amp-op satura: " + (f"com Tp ≥ {tp * 1e3:.0f} ms o sinal fica dentro de {p.vmax:g} V "
                                                   f"('projeto tp {tp * 1e3:.0f}m')" if tp else
                                                   "nem com Tp 20 vezes maior; reveja a referência ou o limite (vmax)"))
            elif p.pico_controle() > p.vmax:
                print(f"    ! o amp-op satura: a referência pede mais que {p.vmax:g} V já no começo da subida")
        if "pi_carga" not in projetos:
            print("\n  (com carga: falta K1 — meça a Tabela 2 com ig — para simular a rejeição da carga)")
        dados = dict(opcoes=self.opcoes_projeto, motor=dict(K=motor.K, Kt=motor.Kt, tau=motor.tau, K1=motor.K1),
                     projetos={k: p.como_dict() for k, p in projetos.items()})
        self.pasta.escrever("projeto_exp8.json", json.dumps(dados, indent=1, ensure_ascii=False, default=float))
        self._mostrar(painel_motor.projeto(projetos, self.pasta.garantir() / "projeto_exp8.png"))

    # ------------------------------------------------------------ sessão
    def cmd_retomar(self, args):
        pasta = self._pasta_para_retomar(args)
        if self._trocar_para_familia_gravada(pasta):
            return self.cmd_retomar([str(pasta)])
        pastas = sorted((int(p.name[:2]), p) for p in pasta.glob("[0-9][0-9]_*") if p.is_dir())
        arquivo = pasta / "anotacoes_exp8.json"
        if not pastas and not arquivo.exists():
            raise ValueError(f"{pasta} não tem capturas nem anotações")
        roteiro, capturas, falhas, ultimo = Experimento8(), {}, [], None
        for n, p in pastas:
            if not (p / "metricas.json").exists() or p.name.endswith("_descartada"):
                continue
            dados = json.loads((p / "metricas.json").read_text(encoding="utf-8"))
            if dados["experimento"] != roteiro.numero:
                continue
            try:
                captura = Captura.carregar(p / "captura.npz")
                if self.sonda:
                    captura = captura.com_sonda(self.sonda)
                res = analisar_motor(captura, roteiro, roteiro.caso(dados["caso"]), n)
            except Exception as exc:
                falhas.append(f"#{n:02d} ({exc})")
                continue
            res.quando = dados.get("quando", res.quando)
            capturas[res.caso.id] = res
            ultimo = res
        self.pasta.caminho = pasta
        self.roteiro, self.capturas = roteiro, capturas
        self.anotacoes = json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.exists() else []
        projeto = pasta / "projeto_exp8.json"
        self.opcoes_projeto = json.loads(projeto.read_text(encoding="utf-8")).get("opcoes", {}) if projeto.exists() else {}
        self.numero = pastas[-1][0] if pastas else 0
        if ultimo is not None:
            self.ultimo, self.ultima_captura, self.caso = ultimo, ultimo.captura, ultimo.caso
        elif self.anotacoes:
            self.caso = roteiro.caso(self.anotacoes[-1]["caso"])
        for res in capturas.values():
            res.previsto = self.previsao(res.caso)
        print(f"  retomando {pasta}: {len(pastas)} capturas, {len(capturas)} partidas válidas, "
              f"{len(self.anotacoes)} anotações; a próxima captura será a #{self.numero + 1:02d}")
        if falhas:
            print("  não reanalisadas: " + "; ".join(falhas))
        self.cmd_casos([])

    def cmd_status(self, _args):
        print(f"  Experimento 8, caso {self.caso.id} ({self.caso.rotulo}, {self.caso.descricao})")
        scope = "não conectado" if self.scope is None else f"{self.scope.nome} {getattr(self.scope, 'idn', '')}".rstrip()
        print(f"  osciloscópio: {scope}" + (", aquisição única" if self._unico else ""))
        print(f"  capturas: {self.numero}   partidas válidas: {len(self.capturas)}   anotações: {len(self.anotacoes)}"
              f"   pasta: {self.pasta.caminho}")
        print(f"  diagnostico: {'ON' if self.diagnostico else 'OFF'}   abrir figuras: "
              f"{'ON' if self.abrir_figuras else 'OFF'}   opções do projeto: {self.opcoes_projeto or 'padrão'}")

    def cmd_help(self, _args):
        print(AJUDA_MOTOR)

    def _separar(self, linha):
        """Além do que os outros roteiros aceitam, uma grandeza no começo da linha
        é uma anotação: 'w=1020', 'w 1020', "vt'=2.47", 'ig=120m', 'vt=2,95'."""
        partes = linha.split()
        if len(partes) == 1:
            partes = [p for p in re.split(r"[,=]", linha) if p]
            if len(partes) == 3 and partes[1].isdigit() and partes[2].isdigit():
                partes = [partes[0], f"{partes[1]}.{partes[2]}"]        # vírgula decimal sem espaço
        elif len(partes) == 2 and partes[0].endswith("="):
            partes[0] = partes[0][:-1]
        if partes and partes[0].lower() in APELIDOS:
            return ["anotar"] + partes
        return SessaoLab._separar(linha)


for _nome in ("anotar", "projeto", "armar", "proximo"):
    SessaoMotor.COMANDOS[_nome] = getattr(SessaoMotor, f"cmd_{_nome}")
