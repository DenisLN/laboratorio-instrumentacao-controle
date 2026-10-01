"""Sessão interativa de bancada: adquire do osciloscópio, mede e compara com o modelo.

    python -m labscope            abre o prompt
    python -m labscope --sim      já conectado ao osciloscópio simulado (ensaio sem hardware)
    python -m labscope -c "conectar sim; caso 1.2; adquirir; tabela"

Cada comando é independente e nenhum erro derruba a sessão: a captura é gravada
em disco antes da análise, então dá para refazer as contas depois.
"""
import argparse
import math
import subprocess
import sys
import traceback
from pathlib import Path

import numpy as np

from .. import medidas
from .. import relatorio as Rl
from ..instrumentos import (ErroInstrumento, OsciloscopioArquivo, OsciloscopioSimulado, TektronixTBS, Transcricao,
                            base_de_tempo, ler_arquivo, recursos_visa)
from ..medidas import METRICAS, PADRAO, RespostaTeorica
from ..roteiros import ROTEIROS, Componentes, texto_si, valor_si
from . import painel
from .analise import analisar
from .armazenamento import PastaSessao

AJUDA = """
Comandos (entre parênteses, o atalho):

  conectar [recurso|sim|pasta]  Abre o osciloscópio. Sem argumento, procura um Tektronix na USB.
                                "sim" usa um osciloscópio simulado; uma pasta (ex.: E:\\NEW_FOL)
                                lê as capturas ALLnnnn do pendrive.
  recursos                      Lista os recursos VISA que o computador enxerga agora.
  exp <6|7>                     Troca de roteiro.
  casos                         Lista os casos do roteiro e quais já foram medidos.
  caso <id>                     Escolhe o circuito montado (ex.: caso 1.2 = Tabela 1, 2ª linha).
  teoria (t)                    Ganhos, função de transferência, polos e métricas previstas.
  adquirir (a) [n]              Lê CH1/CH2, grava, calcula e abre o painel. Com pendrive, n é o
                                número da pasta ALLnnnn (padrão: a mais nova).
  calcular (c)                  Refaz as contas da última captura (depois de 'caso' ou 'set').
  ajustar                       Identifica Kp, Ki e Kd que melhor reproduzem a última captura.
  tabela [n]                    Tabelas do roteiro preenchidas com o que já foi medido.
  grafico <n>                   Casos medidos da tabela n no mesmo gráfico, com as curvas teóricas.
  lgr [componente]              Lugar das raízes variando R2 (ou outro componente).
  preparar [s/div] [media N]    Ajusta base de tempo, trigger em CH1 e média no osciloscópio.
  carregar <caminho>            Analisa uma captura gravada (pasta ALLnnnn, pasta da sessão ou .npz).
  set <componente> <valor>      Valor real de um componente (ex.: set L 68m, set R2 9.8k).
  set diagnostico on|off        Abre uma janela acompanhando a transcrição SCPI e mostra os
                                rastros de erro completos.
  set abrir on|off              Abrir ou não as figuras ao gerá-las.
  set suavizacao <tempo>        Janela da média móvel aplicada a CH2 (padrão 60u).
  reset                         Volta todos os componentes aos valores nominais.
  comp                          Componentes do caso: nominal e valor em uso.
  scpi <comando>                Envia um comando SCPI cru (com '?' no fim, mostra a resposta).
  status                        Resumo da sessão.
  erro                          Rastro completo do último erro.
  help (?)  /  quit (q)

Ordem típica:  conectar  ->  caso 1.1  ->  teoria  ->  (montar)  ->  adquirir  ->  caso 1.2  ->  ...  ->  tabela
""".strip("\n")


def comando_terminal_diagnostico(caminho_log):
    """Comando do PowerShell que acompanha a transcrição SCPI em tempo real (o
    equivalente a `tail -f`). Só monta a lista de argumentos; quem abre a janela
    é `SessaoLab._abrir_terminal_de_diagnostico`."""
    script = (f"$Host.UI.RawUI.WindowTitle = 'diagnostico SCPI - {caminho_log.parent.name}'; "
              f"Write-Host 'Acompanhando {caminho_log} (Ctrl+C fecha so esta janela)'; "
              f"Get-Content -Path '{caminho_log}' -Wait -Tail 20 -Encoding UTF8")
    return ["powershell.exe", "-NoExit", "-Command", script]


class SessaoLab:
    def __init__(self, raiz="sessoes", abrir_figuras=True, experimento=7):
        self.roteiro = ROTEIROS[experimento]()
        self.caso = self.roteiro.casos()[0]
        self.reais = {}             # (componente, valor nominal) -> valor real
        self.scope = None
        self.pasta = PastaSessao(raiz)
        self.resultados = {}        # (experimento, id do caso) -> Resultado mais recente
        self.ultimo = None          # Resultado da última análise que deu certo
        self.ultima_captura = None
        self.numero = 0             # contador de capturas da sessão
        self.abrir_figuras = abrir_figuras
        self.suavizacao = 60e-6
        self.diagnostico = False
        self.ultimo_erro = ""
        self._janela_diagnostico = None

    # ------------------------------------------------------------ estado
    def comp(self, caso=None):
        """Componentes em uso para o caso: os nominais com as trocas do 'set'."""
        caso = caso or self.caso
        trocas = {k: self.reais[(k, v)] for k, v in caso.comp.como_dict().items() if (k, v) in self.reais}
        return caso.comp.trocar(**trocas)

    def _teorias(self, caso=None):
        caso = caso or self.caso
        return tuple(RespostaTeorica(caso.malha(self.comp(caso), carga=c), self.roteiro.amplitude)
                     for c in (False, True))

    def _s_div_sugerido(self):
        """s/div em que cabem, nas 9 divisões depois da borda, duas vezes o tempo
        de assentamento previsto (sobra patamar para medir V_c) ou, se isso passar
        de meio período, o meio período inteiro."""
        semi = 0.5 / self.roteiro.frequencia
        ts = [t.degrau["ts"] for t in self._teorias() if not math.isnan(t.degrau["ts"])]
        return base_de_tempo(min(2.0 * max(ts), 1.1 * semi) if ts else 1.1 * semi)

    def _pico_previsto(self):
        """Maior |V_c| esperado, em volts: patamar mais o sobressinal do pior dos dois modelos."""
        mp = [t.degrau["mp"] for t in self._teorias() if not math.isnan(t.degrau["mp"])]
        return self.roteiro.amplitude * max(t.ganho_dc for t in self._teorias()) * (1 + 2 * max(mp, default=0.0))

    def _v_div_sugerido(self):
        """Menor V/div (sequência 1–2–5) em que o pico previsto fica dentro de 3,5 divisões."""
        return next((v for v in (0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0) if 3.5 * v >= self._pico_previsto()), 5.0)

    def _exigir_scope(self):
        if self.scope is None:
            raise ErroInstrumento("nenhum osciloscópio conectado: use 'conectar' (ou 'conectar sim')")

    def _mostrar(self, caminho):
        print(f"  figura: {caminho}")
        if self.abrir_figuras:
            painel.abrir(caminho)

    # ------------------------------------------------------------ conexão
    def cmd_recursos(self, _args):
        recursos = recursos_visa()
        print("\n".join(f"  {r}" for r in recursos) if recursos else "  nenhum recurso VISA visível")

    def cmd_conectar(self, args):
        if self.scope is not None:
            self.scope.fechar()
            self.scope = None
        alvo = " ".join(args)
        if alvo.lower() == "sim":
            scope = OsciloscopioSimulado(lambda: self.caso.malha(self.comp(), carga=True))
        elif alvo and Path(alvo).is_dir():
            scope = OsciloscopioArquivo(alvo)
        else:
            scope = TektronixTBS(alvo or None)
        scope.transcricao = Transcricao(self.pasta.transcricao)
        idn = scope.conectar()
        self.scope = scope
        print(f"  conectado: {idn}")

    def cmd_scpi(self, args):
        self._exigir_scope()
        if not isinstance(self.scope, TektronixTBS):
            raise ErroInstrumento("'scpi' só vale com o osciloscópio real conectado")
        comando = " ".join(args)
        if not comando:
            raise ValueError("uso: scpi <comando>")
        if comando.rstrip().endswith("?"):
            print("  " + self.scope.perguntar(comando))
        else:
            self.scope.escrever(comando)
            print("  fila do instrumento: " + self.scope.erros())

    def cmd_preparar(self, args):
        self._exigir_scope()
        media, s_div = 0, None
        args = [a.lower() for a in args]
        if "media" in args:
            k = args.index("media")
            media = int(args[k + 1])
            del args[k:k + 2]
        if args:
            s_div = valor_si(args[0])
        s_div = s_div or self._s_div_sugerido()
        fila = self.scope.preparar(s_div, media)
        print(f"  {texto_si(s_div, 's')}/div, trigger na subida de CH1 a 1 divisão da esquerda"
              + (f", média de {media} aquisições" if media else ", sem média"))
        if fila:
            print(f"  fila do instrumento: {fila}")
        print("  As escalas verticais continuam por sua conta (CH2 ocupando boa parte da tela).")

    # ------------------------------------------------------------ roteiro
    def cmd_exp(self, args):
        if not args or not args[0].isdigit() or int(args[0]) not in ROTEIROS:
            raise ValueError(f"uso: exp <{'|'.join(map(str, ROTEIROS))}>")
        self.roteiro = ROTEIROS[int(args[0])]()
        self.caso = self.roteiro.casos()[0]
        print(f"  Experimento {self.roteiro.numero} – {self.roteiro.titulo} "
              f"(onda quadrada de {self.roteiro.frequencia:g} Hz, {2 * self.roteiro.amplitude:g} Vpp)")
        self.cmd_casos([])

    def cmd_casos(self, _args):
        tabela = None
        for c in self.roteiro.casos():
            if c.tabela != tabela:
                tabela = c.tabela
                titulo = next(t.titulo for t in self.roteiro.tabelas() if t.numero == tabela)
                print(f"  Tabela {tabela} – {titulo}")
            g = c.malha(self.comp(c)).controlador.ganhos()
            res = self.resultados.get((self.roteiro.numero, c.id))
            estado = f"medido (#{res.numero:02d}, {len(res.conferir)} a conferir)" if res else "–"
            marca = ">" if c.id == self.caso.id else " "
            print(f"   {marca} {c.id:<4} {c.rotulo:<14} Kp = {Rl.num(g['kp'], 2):>5}  Ki = {Rl.num(g['ki'], 0):>7}"
                  f"  Kd = {Rl.num(g['kd'] * 1e3, 3):>6} ms   {estado}")

    def cmd_caso(self, args):
        if not args:
            raise ValueError("uso: caso <id>  (veja os ids em 'casos')")
        self.caso = self.roteiro.caso(args[0])
        self.cmd_teoria([])

    def cmd_comp(self, _args):
        efetivo = self.comp()
        for k in self.caso.usados:
            nominal, real = getattr(self.caso.comp, k), getattr(efetivo, k)
            u = Componentes.UNIDADES[k]
            troca = f"   <- em uso: {texto_si(real, u)}" if real != nominal else ""
            print(f"  {self.roteiro.nome(k):<3} = {texto_si(nominal, u)} (nominal){troca}")

    def cmd_teoria(self, _args):
        teo, carga = self._teorias()
        malha = teo.malha
        g = malha.controlador.ganhos()
        comp = self.comp()
        print(f"  Exp. {self.roteiro.numero} · Tabela {self.caso.tabela} · caso {self.caso.id} "
              f"({self.caso.rotulo}) · {malha.descricao()}")
        print("  " + "  ".join(f"{self.roteiro.nome(k)} = {texto_si(getattr(comp, k), comp.UNIDADES[k])}"
                               for k in self.caso.usados))
        print(f"  Kp = {Rl.num(g['kp'], 2)}   Ki = {Rl.num(g['ki'], 0)} 1/s   Kd = {Rl.num(g['kd'] * 1e3, 4)} ms"
              f"   (sistema tipo {malha.tipo}, ordem {malha.ordem})")
        print(f"  Vc/E1 = {teo.ft}")
        polo = lambda p: (Rl.num(p.real, 0) if abs(p.imag) < 1e-6 else
                          f"{Rl.num(p.real, 0)} ± j{Rl.num(abs(p.imag), 0)}")
        lista = lambda t: "; ".join(dict.fromkeys(polo(p) for p in sorted(t.malha.polos(), key=lambda p: p.real)))
        print(f"  polos (teórico):  {lista(teo)}")
        print(f"  polos (c/ carga): {lista(carga)}")
        if not teo.estavel:
            print("  ! pelo modelo do roteiro esta malha é INSTÁVEL")
        print(f"\n  {'métrica':<15}{'teórico':>14}{'c/ carga':>14}")
        for m in PADRAO:
            if m.chave == "amp" or m.chave.endswith("_dl") or not m.aplicavel(teo):
                continue
            rot = m.simbolo if m.chave != "tr" else f"Tr ({teo.subida.replace('-', '–')} %)"
            print(f"  {rot:<15}{m.formatar(m.prever(teo)):>14}{m.formatar(m.prever(carga)):>14}")
        print(f"\n  'c/ carga' inclui o resistor R do inversor ({texto_si(comp.R, 'Ω')}) em paralelo com o capacitor.")
        print(f"  Tela sugerida: {texto_si(self._s_div_sugerido(), 's')}/div com a borda de subida de CH1 a "
              "1 divisão da esquerda ('preparar' faz isso);")
        print(f"                 CH2 em {texto_si(self._v_div_sugerido(), 'V')}/div centrado em 0 V "
              f"(pico previsto de {Rl.num(self._pico_previsto(), 2)} V).")

    def cmd_set(self, args):
        if len(args) < 2:
            raise ValueError("uso: set <componente> <valor>  |  set diagnostico|abrir on|off  |  set suavizacao <tempo>")
        chave, valor = args[0].lower(), args[1]
        if chave in ("diagnostico", "abrir"):
            if valor.lower() not in ("on", "off"):
                raise ValueError(f"uso: set {chave} on|off")
            ligado = valor.lower() == "on"
            if chave == "abrir":
                self.abrir_figuras = ligado
            else:
                self.diagnostico = ligado
                (self._abrir_terminal_de_diagnostico if ligado else self._fechar_terminal_de_diagnostico)()
            print(f"  {chave}: {'ON' if ligado else 'OFF'}")
            return
        if chave == "suavizacao":
            self.suavizacao = valor_si(valor)
            print(f"  média móvel de {texto_si(self.suavizacao, 's')} em CH2 (vale a partir do próximo cálculo)")
            return
        k = Componentes.chave(chave)
        nominal, real = getattr(self.caso.comp, k), valor_si(valor)
        if real <= 0:
            raise ValueError("o valor tem de ser positivo")
        self.reais[(k, nominal)] = real
        u = Componentes.UNIDADES[k]
        print(f"  {self.roteiro.nome(k)}: nominal {texto_si(nominal, u)} -> em uso {texto_si(real, u)} "
              f"(vale para todo caso com esse nominal; 'calcular' refaz a última captura)")

    def cmd_reset(self, _args):
        self.reais.clear()
        print("  componentes de volta aos valores nominais")

    # ------------------------------------------------------------ diagnóstico
    def _abrir_terminal_de_diagnostico(self):
        """Janela de console nova fazendo `tail -f` da transcrição SCPI. É só uma
        conveniência: se não der para abrir, a sessão segue sem ela."""
        self._fechar_terminal_de_diagnostico()
        caminho = self.pasta.transcricao
        Transcricao(caminho)("--", "diagnóstico ligado")
        try:
            self._janela_diagnostico = subprocess.Popen(comando_terminal_diagnostico(caminho),
                                                        creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
        except Exception as exc:  # sem console gráfico, sem powershell.exe, etc.
            print(f"  (não consegui abrir a janela de diagnóstico: {exc}; a transcrição segue em {caminho})")

    def _fechar_terminal_de_diagnostico(self):
        janela, self._janela_diagnostico = self._janela_diagnostico, None
        if janela is not None and janela.poll() is None:
            try:
                janela.terminate()
            except Exception:  # só conveniência
                pass

    def cmd_erro(self, _args):
        print(self.ultimo_erro or "  nenhum erro nesta sessão")

    # ------------------------------------------------------------ medir
    def _analisar(self, captura, numero):
        """Analisa, grava, mostra a tabela e abre o painel."""
        res = analisar(captura, self.roteiro, self.caso, self.comp(), suavizacao=self.suavizacao, numero=numero)
        pasta = self.pasta.salvar(res)
        figura = painel.painel(res, pasta / "painel.png")
        self.resultados = {k: v for k, v in self.resultados.items() if v.numero != numero}
        self.resultados[(self.roteiro.numero, self.caso.id)] = res
        self.ultimo = res
        print(res.texto())
        print(f"  salvo em {pasta}")
        self._mostrar(figura)
        return res

    def _nova_captura(self, captura):
        self.numero += 1
        self.ultima_captura = captura
        try:
            return self._analisar(captura, self.numero)
        except Exception:
            # a captura não pode se perder por causa de uma conta que falhou
            bruta = self.pasta.garantir() / f"{self.numero:02d}_sem_analise"
            captura.salvar(bruta)
            print(f"  captura #{self.numero:02d} gravada sem análise em {bruta}; corrija e use 'calcular'")
            raise

    def cmd_adquirir(self, args):
        self._exigir_scope()
        if isinstance(self.scope, OsciloscopioSimulado):
            self.scope.frequencia, self.scope.amplitude = self.roteiro.frequencia, self.roteiro.amplitude
            self.scope.s_div = self._s_div_sugerido()
            self.scope.v_div = (0.2, self._v_div_sugerido())
        if isinstance(self.scope, OsciloscopioArquivo) and args:
            self.scope.proxima = int(args[0])
        captura = self.scope.adquirir()
        if self.diagnostico and isinstance(self.scope, TektronixTBS):
            print(f"  fila do instrumento: {self.scope.erros()}")
        self._nova_captura(captura)

    def cmd_carregar(self, args):
        if not args:
            raise ValueError("uso: carregar <pasta ALLnnnn | pasta da sessão | arquivo .npz>")
        self._nova_captura(ler_arquivo(" ".join(args)))

    def cmd_calcular(self, _args):
        if self.ultima_captura is None:
            raise ValueError("ainda não há captura nesta sessão: use 'adquirir'")
        sem_analise = self.pasta.caminho / f"{self.numero:02d}_sem_analise"
        self._analisar(self.ultima_captura, self.numero)
        if sem_analise.is_dir():
            for arquivo in sem_analise.iterdir():
                arquivo.unlink()
            sem_analise.rmdir()

    def cmd_ajustar(self, _args):
        if self.ultimo is None:
            raise ValueError("ainda não há captura analisada: use 'adquirir'")
        res = self.ultimo
        print(f"  ajustando os ganhos à captura #{res.numero:02d} (planta do modelo c/ carga)...")
        linhas = [(m, m.medir(res.medida), m.prever(res.teoria))
                  for m in medidas.ganhos(res.teoria_carga.malha) if m.aplicavel(res.teoria)]
        res.ganhos_id = {m.chave: float(exp) for m, exp, _ in linhas}
        print(f"  {'ganho':<8}{'ajustado':>14}{'teórico':>14}{'desvio':>10}")
        for m, exp, teo in linhas:
            c = m.comparar(exp, teo)
            print(f"  {m.simbolo:<8}{m.formatar(exp):>14}{m.formatar(teo):>14}"
                  f"{f'{c.desvio * 100:+.1f} %'.replace('.', ','):>10}   {'OK' if c.ok else 'CONFERIR'}")
        self.pasta.salvar(res)

    # ------------------------------------------------------------ relatório
    def _tabela_md(self, tabela):
        ms = [METRICAS[k] for k in tabela.metricas]
        cab = ["caso"] + [f"{m.simbolo} {lado}" for m in ms for lado in ("exp", "teo")]
        linhas, nota = [], False
        for id in tabela.casos:
            caso = self.roteiro.caso(id)
            teo = self._teorias(caso)[0]
            res = self.resultados.get((self.roteiro.numero, id))
            linha = [caso.rotulo]
            for m in ms:
                marca = "¹" if m.chave == "tr" and teo.subida == "10-90" else ""
                nota = nota or bool(marca)
                exp = res.linha(m.chave) if res else None
                linha += [m.formatar(exp.exp) + (marca if exp else "") if exp else "–",
                          m.formatar(m.prever(teo)) + marca]
            linhas.append(linha)
        partes = [f"**Tabela {tabela.numero}** – {tabela.titulo}", Rl.tabela(cab, linhas)]
        if nota:
            partes.append("¹ sem sobressinal: tempo de subida de 10 % a 90 %; nas demais linhas, de 0 a 100 %.")
        return "\n\n".join(partes)

    def _regime_md(self):
        cab = ["caso", "e_ss exp", "e_ss teo", "Kp teo", "Ki teo (1/s)", "Kd teo (ms)", "Kp ajuste", "Ki ajuste",
               "Kd ajuste (ms)"]
        linhas = []
        for caso in self.roteiro.casos():
            res = self.resultados.get((self.roteiro.numero, caso.id))
            teo = self._teorias(caso)[0]
            g, ess = teo.malha.controlador.ganhos(), METRICAS["ess"]
            aj = (res.ganhos_id if res else None) or {}
            linhas.append([f"{caso.id} ({caso.rotulo})", ess.formatar(res.linha("ess").exp) if res else "–",
                           ess.formatar(ess.prever(teo)), Rl.num(g["kp"], 2), Rl.num(g["ki"], 0),
                           Rl.num(g["kd"] * 1e3, 4), Rl.num(aj.get("kp"), 2), Rl.num(aj.get("ki"), 0),
                           Rl.num(aj["kd"] * 1e3, 4) if "kd" in aj else "–"])
        return "**Regime e ganhos** ('ajuste' aparece nos casos em que o comando `ajustar` foi usado)\n\n" + Rl.tabela(cab, linhas)

    def cmd_tabela(self, args):
        tabelas = self.roteiro.tabelas()
        if args:
            tabelas = [t for t in tabelas if str(t.numero) == args[0]]
            if not tabelas:
                raise ValueError(f"o Experimento {self.roteiro.numero} não tem tabela {args[0]}")
        texto = "\n\n".join([f"# Experimento {self.roteiro.numero} – {self.roteiro.titulo}"]
                            + [self._tabela_md(t) for t in tabelas] + ([] if args else [self._regime_md()])) + "\n"
        print(texto)
        if not args:
            print(f"  salvo em {self.pasta.escrever(f'tabelas_exp{self.roteiro.numero}.md', texto)}")

    def cmd_grafico(self, args):
        if not args:
            raise ValueError("uso: grafico <número da tabela>")
        tabela = next((t for t in self.roteiro.tabelas() if str(t.numero) == args[0]), None)
        if tabela is None:
            raise ValueError(f"o Experimento {self.roteiro.numero} não tem tabela {args[0]}")
        medidos = [self.resultados[(self.roteiro.numero, id)] for id in tabela.casos
                   if (self.roteiro.numero, id) in self.resultados]
        if not medidos:
            raise ValueError(f"nenhum caso da tabela {tabela.numero} foi medido ainda")
        nome = f"grafico_exp{self.roteiro.numero}_tabela{tabela.numero}.png"
        self._mostrar(painel.grafico_tabela(tabela, medidos, self.pasta.garantir() / nome))

    def cmd_lgr(self, args):
        variavel = Componentes.chave(args[0]) if args else "R2"
        res = self.resultados.get((self.roteiro.numero, self.caso.id))
        nome = f"lgr_exp{self.roteiro.numero}_c{self.caso.id}_{variavel}.png"
        self._mostrar(painel.lugar_das_raizes(res or self.caso, self.roteiro, self.comp(),
                                              self.pasta.garantir() / nome, variavel))

    def cmd_status(self, _args):
        print(f"  Experimento {self.roteiro.numero}, caso {self.caso.id} ({self.caso.rotulo}, "
              f"{self.caso.planta} + {self.caso.ctrl})")
        if self.scope is None:
            print("  osciloscópio: não conectado")
        else:
            print(f"  osciloscópio: {self.scope.nome} {getattr(self.scope, 'idn', '')}".rstrip())
        trocas = ", ".join(f"{k} {texto_si(n, Componentes.UNIDADES[k])} -> {texto_si(r, Componentes.UNIDADES[k])}"
                           for (k, n), r in self.reais.items())
        print(f"  componentes trocados: {trocas or 'nenhum'}")
        print(f"  capturas: {self.numero}   casos medidos: {len(self.resultados)}   pasta: {self.pasta.caminho}")
        print(f"  diagnostico: {'ON' if self.diagnostico else 'OFF'}   abrir figuras: "
              f"{'ON' if self.abrir_figuras else 'OFF'}   suavização: {texto_si(self.suavizacao, 's')}")

    def cmd_help(self, _args):
        print(AJUDA)

    # ------------------------------------------------------------ laço
    COMANDOS = {"conectar": cmd_conectar, "recursos": cmd_recursos, "scpi": cmd_scpi, "preparar": cmd_preparar,
                "exp": cmd_exp, "casos": cmd_casos, "caso": cmd_caso, "comp": cmd_comp, "teoria": cmd_teoria,
                "set": cmd_set, "reset": cmd_reset, "adquirir": cmd_adquirir, "carregar": cmd_carregar,
                "calcular": cmd_calcular, "ajustar": cmd_ajustar, "tabela": cmd_tabela, "grafico": cmd_grafico,
                "lgr": cmd_lgr, "status": cmd_status, "erro": cmd_erro, "help": cmd_help}
    ATALHOS = {"a": "adquirir", "c": "calcular", "t": "teoria", "?": "help", "ajuda": "help", "gráfico": "grafico"}

    def executar(self, linha):
        """Executa uma linha de comando. Devolve False para encerrar a sessão."""
        partes = linha.split()
        if not partes:
            return True
        comando, args = partes[0].lower(), partes[1:]
        comando = self.ATALHOS.get(comando, comando)
        if comando in ("quit", "exit", "q", "sair"):
            return False
        handler = self.COMANDOS.get(comando)
        if handler is None:
            print(f"  comando desconhecido: {comando!r} (digite 'help')")
            return True
        try:
            handler(self, args)
        except Exception as exc:  # nenhum erro de comando derruba a sessão
            self.ultimo_erro = traceback.format_exc()
            print(f"  ERRO: {exc}")
            if self.diagnostico:
                print(self.ultimo_erro)
        return True

    def prompt(self):
        return f"lab[e{self.roteiro.numero} c{self.caso.id}]> "

    def loop(self):
        print(f"labscope – Experimento {self.roteiro.numero}, caso {self.caso.id}. 'help' lista os comandos.")
        while True:
            try:
                linha = input(self.prompt())
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not self.executar(linha.strip()):
                break
        self.encerrar()

    def encerrar(self):
        if self.scope is not None:
            self.scope.fechar()
        self._fechar_terminal_de_diagnostico()


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m labscope", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exp", type=int, default=7, choices=sorted(ROTEIROS), help="roteiro inicial (padrão: 7)")
    ap.add_argument("--sim", action="store_true", help="começa conectado ao osciloscópio simulado")
    ap.add_argument("--sem-abrir", action="store_true", help="não abre as figuras no visualizador")
    ap.add_argument("--pasta", default="sessoes", help="onde gravar as sessões (padrão: ./sessoes)")
    ap.add_argument("-c", dest="comandos", help="roda os comandos separados por ';' e sai")
    args = ap.parse_args(argv)
    for fluxo in (sys.stdout, sys.stderr):
        # fora de um console (saída redirecionada) o padrão do Windows é cp1252, que não tem ζ nem ω
        fluxo.reconfigure(**({"errors": "replace"} if fluxo.isatty() else {"encoding": "utf-8"}))
    np.seterr(all="ignore")
    sessao = SessaoLab(args.pasta, not args.sem_abrir, args.exp)
    if args.sim:
        sessao.executar("conectar sim")
    if args.comandos:
        for linha in args.comandos.split(";"):
            if not sessao.executar(linha.strip()):
                break
        sessao.encerrar()
        return 0
    sessao.loop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
