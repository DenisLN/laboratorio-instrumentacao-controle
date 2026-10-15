"""Exporta uma sessão do Experimento 8 para uma atividade do modelo-latex.

Chamado por `python -m labscope.sessao.latex <sessao> <destino>` quando a sessão
é do motor. Gera, além de csv/ e cod/:

  tab/tabela1.tex, tabela2.tex   as tabelas da folha (mesmo número)
  tab/constantes.tex             as retas de mínimos quadrados e as constantes (Tabela K)
  tab/projeto.tex                ganhos e especificações dos controladores (Tabela P)
  tex/plot_<y>_<x>.tex           um gráfico por reta: vt_va, w_va, vt_w, v1t_ig, e tau_va
  tex/plot_partidas<n>.tex       as partidas medidas da tabela n, um painel por linha
  tex/plot_projeto_<chave>.tex   uma figura por controlador simulado
  tex/cod_*.tex                  trechos do modelo e do projeto (motor, reta, malha_motor, pi, pd, pid)
"""
import inspect
import math
import re
from pathlib import Path

import numpy as np

from ..motor import modelo as modelo_motor
from ..motor import projeto as projeto_motor
from .latex import ASCII_CODIGO, GRUPO, PONTOS, _cinza, _csv, _n, _passo, _tabela, _tex

CORES = r"""\definecolor{cor-medido}{HTML}{0072B2}
\definecolor{cor-teorico}{HTML}{D55E00}
\definecolor{cor-carga}{HTML}{009E73}"""
GRANDEZA_TEX = {"va": r"$V_a$ (V)", "vt": r"$V_t$ (V)", "w": r"$\omega$ (rpm)", "tau": r"$\tau$ (ms)",
                "ig": r"$i_g$ (mA)", "vtc": r"$V'_t$ (V)", "v1t": r"$V_{1t}$ (V)"}
CASAS = {"va": (2, 1.0), "vt": (3, 1.0), "w": (0, 1.0), "tau": (1, 1e3), "ig": (1, 1e3), "vtc": (3, 1.0),
         "v1t": (3, 1.0)}


def _g(x, casas=4):
    """Número com `casas` algarismos significativos e vírgula, para o texto."""
    if x is None or not math.isfinite(x):
        return "--"
    return f"{x:.{casas}g}".replace(".", "{,}").replace("-", "$-$").replace("e{,}", "e")


def _texto(t):
    """Texto da sessão (unidades, especificações) em LaTeX: a fonte do modelo não tem °, ·, ≤ e –."""
    for a, b in (("%", r"\%"), ("°", r"\textdegree{}"), ("·", r"$\cdot$"), ("≤", r"$\le$"), ("–", "--"),
                 ("−", "$-$")):
        t = t.replace(a, b)
    return t


def _num(x):
    """Número para o pgfmath (ponto decimal, sem notação estranha)."""
    return f"{x:.6g}"


# ------------------------------------------------------------------ tabelas
def tabelas_roteiro(sessao, pasta):
    ls = sessao.leituras()
    for tabela in sessao.roteiro.tabelas():
        chaves = [k for k in tabela.metricas if k != "va"]
        linhas = []
        medido_va = False
        for id in tabela.casos:
            caso, l = sessao.roteiro.caso(id), ls[id]
            va_medido = l["va"] if l.fontes.get("va") not in (None, "nominal") else math.nan
            medido_va |= math.isfinite(va_medido)
            cel = [_n(caso.va, 0)] + [_n(l[k], *CASAS[k]) for k in chaves] + [_cinza(_n(va_medido, 2))]
            linhas.append(" & ".join(c.replace("–", "--") for c in cel) + r" \\")
        cab = " & ".join([r"$V_a$ (V)"] + [GRANDEZA_TEX[k] for k in chaves] + [_cinza(r"$V_a$ medido (V)")]) + r" \\"
        colunas = "r" + GRUPO + "r" * len(chaves) + GRUPO + "r"
        nota = (r"$V_t$ sem carga repetido da Tabela~\ref{tab:tabela1} (mesma $V_a$) onde não foi medido de novo."
                if tabela.numero == 2 else "")
        _tex(pasta / "tab" / f"tabela{tabela.numero}.tex", _tabela(
            None, f"tab:tabela{tabela.numero}", colunas, cab, "\n        ".join(linhas),
            tabela.titulo.replace("ig = 0", "$i_g = 0$") + ".", nota, tabela.numero))
        _csv(pasta / "csv" / f"tabela{tabela.numero}.csv", ["va_pedido"] + list(tabela.metricas),
             [[sessao.roteiro.caso(id).va for id in tabela.casos]]
             + [[ls[id][k] for id in tabela.casos] for k in tabela.metricas])


def tabela_constantes(ident, pasta):
    def linha(simbolo, grafico, r, unidade, casas_b=3):
        if r is None:
            return f"{simbolo} & {grafico} & \\multicolumn{{5}}{{c}}{{faltam pontos}} \\\\"
        fora = f" ({', '.join(r.excluidos)} fora)" if r.excluidos else ""
        return (f"{simbolo} & {grafico} & {_g(r.a)} {unidade} & {_cinza(_g(r.b, casas_b))} & "
                f"{_cinza(_g(r.a0))} & {r.r2:.4f}".replace(".", "{,}") + f" & {r.n}{fora} \\\\")
    linhas = [linha("$KK_t$", r"$V_t \times V_a$", ident.kkt, "V/V"),
              linha("$K$", r"$\omega \times V_a$", ident.k, "rpm/V"),
              linha("$K_t$", r"$V_t \times \omega$", ident.kt, "V/rpm"),
              f"$K_t$ & $KK_t/K$ & {_g(ident.Kt_indireto)} V/rpm & & & & \\\\",
              r"\addlinespace",
              linha("$K_1K_t$", r"$V_{1t} \times i_g$", ident.k1kt, "V/A"),
              f"$K_1$ & $K_1K_t/K_t$ & {_g(ident.K1)} rpm/A & & & & \\\\",
              r"\addlinespace",
              f"$\\tau$ & média sem carga & {_g(ident.tau * 1e3, 3)} ms & {_cinza(r'$\pm$ ' + _g(ident.tau_desvio * 1e3, 2))}"
              f" & & & {len(ident.taus)} \\\\"]
    cab = (r"constante & gráfico & inclinação $a$ & " + _cinza("$b$") + " & " + _cinza("pela origem")
           + r" & $R^2$ & pontos \\")
    _tex(pasta / "tab" / "constantes.tex", _tabela(
        "K", "tab:constantes", "ll" + GRUPO + "r" + GRUPO + "rr" + GRUPO + "rr", cab, "\n        ".join(linhas),
        r"Constantes do grupo motor-gerador por mínimos quadrados ($y = a x + b$); em cinza, o coeficiente linear "
        r"e a inclinação da reta forçada pela origem. Pontos com o motor parado ficam fora das retas."))


def tabela_projeto(projetos, pasta):
    titulos = {"pi": "sem carga", "pd": "sem carga", "pi_carga": "com carga", "pd_carga": "com carga",
               "pid_carga": "com carga"}
    blocos = []
    for chave, p in projetos.items():
        g, u = p.ganhos(), [_texto(x) for x in p.unidades_ganhos()]
        ganhos = [f"$K_p = {_g(g['kp'])}$ {u[0]}"]
        if g["ki"]:
            ganhos.append(f"$K_i = {_g(g['ki'])}$ {u[1]}")
        if g["kd"]:
            ganhos.append(f"$K_d = {_g(g['kd'])}$ {u[2]}")
        carga = rf", $i_g = {_g(p.ig * 1e3, 3)}$ mA" if p.ig else ""
        espec = p.especificacao()
        linhas = []
        for k, (item, pedido, obtido, ok) in enumerate(espec):
            cab = (rf"\multirow{{{len(espec)}}}{{*}}{{\shortstack[l]{{{p.nome.split()[0]} ({titulos[chave]}{carga})\\ "
                   + r"\\ ".join(ganhos) + "}}") if k == 0 else ""
            item_tex = re.sub(r"\b([TM])_([rp])\b", r"$\1_\2$", _texto(item))
            linhas.append(f"{cab} & {item_tex} & {_texto(pedido)} & {_texto(obtido).replace('-', '$-$')} & "
                          f"{'sim' if ok else _cinza('não')} \\\\")
        blocos.append("\n        ".join(linhas))
    _tex(pasta / "tab" / "projeto.tex", _tabela(
        "P", "tab:projeto", "l" + GRUPO + "p{5.4cm}rrc", r"controlador & especificação & pedido & simulado & atende \\",
        "\n        \\midrule\n        ".join(blocos),
        r"Controladores projetados sobre o modelo da Tabela~\ref{tab:constantes} e o resultado da simulação."))


# ------------------------------------------------------------------ gráficos
def _figura(nome, corpo, legenda, label, pasta, largura=r"0.86\textwidth", altura=r"0.42\textwidth"):
    _tex(pasta / "tex" / f"{nome}.tex", rf"""
% Cores validadas para daltonismo (Okabe-Ito), as mesmas dos outros experimentos.
{CORES}
\begin{{figure}}[htbp]
    \centering
    \begin{{tikzpicture}}
        \begin{{axis}}[
            scale only axis, width={largura}, height={altura},
            grid=major, grid style={{gray!20}},
            tick label style={{font=\footnotesize, /pgf/number format/.cd, use comma, 1000 sep={{.}}}},
            scaled ticks=false,
            legend cell align=left, legend pos=north west,
            legend style={{font=\footnotesize, draw=none, fill=none}},
            {corpo}
        \end{{axis}}
    \end{{tikzpicture}}
    \caption{{{legenda}}}
    \label{{{label}}}
\end{{figure}}""")


def grafico_reta(nome, reta, xlabel, ylabel, simbolo, unidade, prefixo, pasta, escala_x=1.0):
    """Pontos medidos e a reta de mínimos quadrados."""
    if reta is None:
        return
    xs, ys = np.array(reta.x) * escala_x, np.array(reta.y)
    _csv(pasta / "csv" / f"{nome}.csv", ("x", "y"), (xs, ys))
    (pasta / "csv" / f"{nome}_casos.csv").write_text(
        "x,y,caso\n" + "".join(f"{a:.6g},{b:.6g},{c}\n" for a, b, c in zip(xs, ys, reta.ids)), encoding="utf-8")
    xmax = 1.08 * xs.max()
    a, b = reta.a / escala_x, reta.b
    sinal = "+" if b >= 0 else "-"
    corpo = rf"""xlabel={{{xlabel}}}, ylabel={{{ylabel}}},
            xmin=0, xmax={_num(xmax)}, xtick distance={_num(_passo(xmax, 8))},
        ]
            \addplot[cor-teorico, line width=1pt, domain=0:{_num(xmax)}, samples=2] {{{_num(a)}*x {sinal} {_num(abs(b))}}};
            \addlegendentry{{${simbolo} = {_g(reta.a)}$ {unidade} \quad ($R^2 = {f'{reta.r2:.4f}'.replace('.', '{,}')}$)}}
            \addplot[only marks, mark=*, mark size=1.8pt, cor-medido, nodes near coords, point meta=explicit symbolic,
                     every node near coord/.style={{font=\scriptsize, gray, anchor=north west}}]
                table[x=x, y=y, meta=caso, col sep=comma] {{{prefixo}/csv/{nome}_casos.csv}};
            \addlegendentry{{medido}}"""
    _figura(f"plot_{nome}", corpo, f"{ylabel.split(' (')[0]} em função de {xlabel.split(' (')[0]}, com a reta de "
            "mínimos quadrados.", f"fig:{nome}", pasta)


def grafico_tau(ident, prefixo, pasta):
    if not ident.taus:
        return
    ids = sorted(ident.taus, key=lambda k: int(k.split(".")[1]))
    x = [int(k.split(".")[1]) for k in ids]
    y = [ident.taus[k] * 1e3 for k in ids]
    _csv(pasta / "csv" / "tau_va.csv", ("va", "tau"), (x, y))
    corpo = rf"""xlabel={{$V_a$ (V)}}, ylabel={{$\tau$ (ms)}}, xmin=0, xmax=11, xtick distance=1,
            ymin=0, ymax={_num(1.2 * max(y))}, legend pos=south east,
        ]
            \addplot[cor-teorico, line width=1pt, domain=0:11, samples=2] {{{_num(ident.tau * 1e3)}}};
            \addlegendentry{{média: $\tau = {_g(ident.tau * 1e3, 3)}$ ms}}
            \addplot[only marks, mark=*, mark size=1.8pt, cor-medido] table[x=va, y=tau, col sep=comma] {{{prefixo}/csv/tau_va.csv}};
            \addlegendentry{{medido}}"""
    _figura("plot_tau_va", corpo, r"Constante de tempo medida em cada partida sem carga.", "fig:tau_va", pasta,
            altura=r"0.3\textwidth")


def grafico_partidas(tabela, resultados, prefixo, pasta):
    """Um painel por linha medida da tabela: Vt medido e a 1ª ordem com τ medido."""
    if not resultados:
        return
    paineis = []
    for k, res in enumerate(resultados):
        m = res.medida
        i, j = m.janela
        fim = min(j, i + int(6 * m.tau / res.captura.dt))
        a = max(0, i - max(5, (fim - i) // 12))
        passo = max(1, (fim - a) // PONTOS)
        s = slice(a, fim, passo)
        t = (m.t[s] - m.degrau["t0"]) * 1e3
        nome = f"partida_t{tabela.numero}_c{res.caso.id}.csv"
        _csv(pasta / "csv" / nome, ("t", "exp", "modelo"), (t, m.y[s], m.curva(m.t[s])))
        arq = f"{prefixo}/csv/{nome}"
        opcoes = [rf"title={{$V_a$ = {_n(res.caso.va, 0)} V \quad $\tau$ = {_n(m.tau, 0, 1e3)} ms}}",
                  f"xmin={t[0]:.1f}, xmax={t[-1]:.1f}"]
        if k == 0:
            opcoes.append("legend to name=leg-partidas" + str(tabela.numero))
        leg = (r" \addlegendentry{medido}", r" \addlegendentry{modelo de primeira ordem}") if k == 0 else ("", "")
        paineis.append("\n            ".join([
            f"\\nextgroupplot[{', '.join(opcoes)}]",
            rf"\addplot[cor-medido, line width=1pt] table[x=t, y=exp, col sep=comma] {{{arq}}};{leg[0]}",
            rf"\addplot[cor-teorico, dashed, line width=0.8pt] table[x=t, y=modelo, col sep=comma] {{{arq}}};{leg[1]}"]))
    linhas = math.ceil(len(paineis) / 2)
    simbolo = "V'_t" if tabela.numero == 2 else "V_t"
    _tex(pasta / "tex" / f"plot_partidas{tabela.numero}.tex", rf"""
{CORES}
\begin{{figure}}[htbp]
    \centering
    \pgfplotslegendfromname{{leg-partidas{tabela.numero}}}\par\smallskip
    \begin{{tikzpicture}}
        \begin{{groupplot}}[
            group style={{group size=2 by {linhas}, horizontal sep=1.6cm, vertical sep=1.3cm,
                          xlabels at=edge bottom, ylabels at=edge left}},
            scale only axis, width=0.4\textwidth, height=0.13\textwidth,
            xlabel={{tempo (ms)}}, ylabel={{${simbolo}$ (V)}},
            grid=major, grid style={{gray!20}},
            title style={{font=\footnotesize, at={{(0,1)}}, anchor=south west}},
            tick label style={{font=\scriptsize, /pgf/number format/.cd, use comma, 1000 sep={{.}}}},
            legend columns=2, legend style={{font=\footnotesize, draw=none, /tikz/every even column/.append style={{column sep=0.8em}}}},
        ]
            {chr(10).join('            ' + p for p in paineis).strip()}
        \end{{groupplot}}
    \end{{tikzpicture}}
    \caption{{Partidas medidas na Tabela~\ref{{tab:tabela{tabela.numero}}}: tensão do tacômetro e a resposta de
             primeira ordem com o $\tau$ medido, a partir do instante em que $V_a$ sobe.}}
    \label{{fig:partidas{tabela.numero}}}
\end{{figure}}""")


def grafico_projeto(chave, p, prefixo, pasta, outro=None):
    """Resposta simulada de um controlador; `outro` (o PID) entra no mesmo gráfico."""
    if outro is not None:
        t_carga, tfim = outro.duracao()
        s, so = p.simular(800, t_carga, tfim), outro.simular(800, t_carga, tfim)
    else:
        s, so = p.simular(800), None
    colunas, cab = [s["t"], s["ref"], s["y"]], ["t", "ref", "y"]
    if chave.startswith("pi"):
        colunas.append(p.malha_aberta(s["t"], s["t_carga"]))
        cab.append("ma")
    if so is not None:
        colunas.append(so["y"])
        cab.append("y2")
    _csv(pasta / "csv" / f"projeto_{chave}.csv", cab, colunas)
    arq = f"{prefixo}/csv/projeto_{chave}.csv"
    curvas = [rf"\addplot[gray, dashed] table[x=t, y=ref, col sep=comma] {{{arq}}}; \addlegendentry{{referência}}",
              rf"\addplot[cor-medido, line width=1.1pt] table[x=t, y=y, col sep=comma] {{{arq}}}; "
              rf"\addlegendentry{{{p.nome.split()[0]}}}"]
    if "ma" in cab:
        curvas.append(rf"\addplot[gray, line width=0.9pt] table[x=t, y=ma, col sep=comma] {{{arq}}}; "
                      r"\addlegendentry{malha aberta ($V_a = \omega_{ref}/K$)}")
    if "y2" in cab:
        curvas.append(rf"\addplot[cor-carga, line width=1.1pt] table[x=t, y=y2, col sep=comma] {{{arq}}}; "
                      rf"\addlegendentry{{{outro.nome.split()[0]}}}")
    if math.isfinite(s["t_carga"]):
        curvas.append(rf"\draw[gray, densely dotted] (axis cs:{_num(s['t_carga'])},\pgfkeysvalueof{{/pgfplots/ymin}}) -- "
                      rf"(axis cs:{_num(s['t_carga'])},\pgfkeysvalueof{{/pgfplots/ymax}});")
    ylabel = r"$\omega$ (rpm)" if p.unidade == "rpm" else r"$\theta$ (graus)"
    corpo = (rf"""xlabel={{tempo (s)}}, ylabel={{{ylabel}}}, xmin=0, xmax={_num(s['t'][-1])},
            ymin=0, ymax={_num(1.15 * max(np.nanmax(s['y']), p.referencia))}, legend pos=south east,
        ]
            """ + "\n            ".join(curvas))
    carga = (rf" A carga ($i_g = {_g(p.ig * 1e3, 3)}$ mA) entra em $t = {_g(s['t_carga'], 3)}$ s." if p.ig else "")
    nomes = p.nome + (f" e {outro.nome}" if outro is not None else "")
    _figura(f"plot_projeto_{chave}", corpo, f"Simulação: {nomes}, referência de {_g(p.referencia, 4)} "
            f"{'rpm' if p.unidade == 'rpm' else 'graus'}.{carga}", f"fig:projeto-{chave.replace('_', '-')}", pasta,
            altura=r"0.32\textwidth")


# ------------------------------------------------------------------ código
# o listings no LuaLaTeX só lida bem com Latin-1 (ver latex.codigo): o resto vira ASCII
ASCII_MOTOR = {**ASCII_CODIGO, **str.maketrans({"ω": "w", "τ": "tau", "θ": "theta", "ζ": "zeta", "≤": "<=",
                                                 "–": "-", "′": "'", "→": "->", "×": "x", "≈": "~"})}


def _ascii(texto):
    texto = texto.translate(ASCII_MOTOR)
    return "".join(c if ord(c) < 256 else "?" for c in texto)


def codigo(prefixo, pasta):
    """Trechos do modelo e do projeto: (nome, módulo, do começo de `de` ao fim de `ate`)."""
    P = projeto_motor
    trechos = (("motor", modelo_motor, modelo_motor.MotorCC, modelo_motor.MotorCC),
               ("reta", modelo_motor, modelo_motor.Reta.ajustar, modelo_motor.Reta.ajustar),
               ("malha_motor", P, P.Projeto.controlador, P.Projeto.sensibilidade),
               ("pi", P, P.ProjetoPI, P.ProjetoPI.ganhos),
               ("pd", P, P.ProjetoPD.analitico, P.ProjetoPD._projetar),
               ("pid", P, P.ProjetoPID, P.ProjetoPID))
    for nome, modulo, de, ate in trechos:
        arquivo = Path(modulo.__file__)
        destino = pasta / "cod" / ("motor_" + arquivo.name)
        destino.write_text(_ascii(arquivo.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
        ini = inspect.getsourcelines(de)[1]
        linhas, comeco = inspect.getsourcelines(ate)
        fim = comeco + len(linhas) - 1
        nomes = de.__qualname__ if de == ate else f"{de.__qualname__} a {ate.__qualname__}"
        _tex(pasta / "tex" / f"cod_{nome}.tex", rf"""
\lstinputlisting[
    firstline={ini}, lastline={fim}, firstnumber={ini}, float=htbp,
    caption={{\texttt{{labscope/motor/{arquivo.name}}}: \texttt{{{nomes.replace("_", chr(92) + "_")}}}}},
    label={{lst:{nome}}}
]{{{prefixo}/cod/{destino.name}}}""")


# ------------------------------------------------------------------ tudo
def exportar(sessao, destino, prefixo):
    destino = Path(destino)
    for sub in ("csv", "tab", "tex", "cod"):
        (destino / sub).mkdir(parents=True, exist_ok=True)
    tabelas_roteiro(sessao, destino)
    ident = sessao.identificacao()
    tabela_constantes(ident, destino)
    for nome, reta, xl, yl, simb, u, esc in (
            ("vt_va", ident.kkt, r"$V_a$ (V)", r"$V_t$ (V)", "KK_t", "V/V", 1.0),
            ("w_va", ident.k, r"$V_a$ (V)", r"$\omega$ (rpm)", "K", "rpm/V", 1.0),
            ("vt_w", ident.kt, r"$\omega$ (rpm)", r"$V_t$ (V)", "K_t", "V/rpm", 1.0),
            ("v1t_ig", ident.k1kt, r"$i_g$ (mA)", r"$V_{1t}$ (V)", "K_1K_t", "V/A", 1e3)):
        grafico_reta(nome, reta, xl, yl, simb, u, prefixo, destino, esc)
    grafico_tau(ident, prefixo, destino)
    for tabela in sessao.roteiro.tabelas():
        grafico_partidas(tabela, [sessao.capturas[c] for c in tabela.casos if c in sessao.capturas], prefixo, destino)
    try:
        projetos = sessao.projetos()
    except ValueError as exc:
        print(f"sem projeto: {exc}")
        projetos = {}
    if projetos:
        tabela_projeto(projetos, destino)
        for chave, p in projetos.items():
            if chave == "pid_carga":
                continue                     # vai junto com o PD com carga
            grafico_projeto(chave, p, prefixo, destino, projetos.get("pid_carga") if chave == "pd_carga" else None)
    codigo(prefixo, destino)
    return sorted(sessao.capturas.values(), key=lambda r: r.numero)
