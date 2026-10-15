"""Exporta uma sessão do Experimento 9 para uma atividade do modelo-latex.

Chamado por `python -m labscope.sessao.latex <sessao> <destino>` quando a sessão é do
controle do motor. Gera, além de csv/ e cod/:

  tab/tabela1.tex ... tabela4.tex   as tabelas da folha: medido e previsto, uma coluna de cada por linha
  tab/projeto.tex                   ganhos, polos e circuito (R, R2, C1, C2) de cada linha (Tabela P)
  tex/plot_resposta<n>.tex          referência, saída medida e prevista da tabela n
  tex/plot_lgr_<caso>.tex           polos de malha aberta e fechada sobre o lugar das raízes
  tex/cod_*.tex                     trechos do projeto e do dimensionamento dos componentes
"""
import inspect
import math
from pathlib import Path

import numpy as np

from ..motor import componentes as componentes_motor
from ..motor import projeto as projeto_motor
from ..motor import resposta as resposta_motor
from . import painel_controle
from .controle import METRICAS, formatar
from .latex import GRUPO, PONTOS, _cinza, _csv, _tabela, _tex
from .latex_motor import CORES, _ascii, _figura, _g, _num, _texto


def _fmt(chave, x):
    return formatar(chave, x, False).replace("−", "$-$").replace("–", "--")


# ------------------------------------------------------------------ tabelas
def tabelas_roteiro(sessao, pasta):
    """Por linha da folha, as métricas medidas e (em cinza) as previstas pelo modelo."""
    metricas = ("tau", "tr", "tp", "mp", "ts")
    for tabela in sessao.roteiro.tabelas():
        linhas = []
        for id in tabela.casos:
            caso, res = sessao.roteiro.caso(id), sessao.capturas.get(id)
            prev = res.previsto if res is not None else sessao._prever(caso)
            medido = res.valores() if res is not None else {}
            rot = _texto(caso.rotulo)
            linhas.append(" & ".join([rot] + [_fmt(k, medido.get(k, math.nan)) for k in metricas]) + r" \\")
            linhas.append(" & ".join([_cinza("previsto")] + [_cinza(_fmt(k, prev.get(k, math.nan))) for k in metricas]) + r" \\")
        cab = " & ".join(["linha"] + [rf"${METRICAS[k][0]}$ ({METRICAS[k][1].replace('%', chr(92) + '%')})".replace(
            "$τ$", r"$\tau$") for k in metricas]) + r" \\"
        _tex(pasta / "tab" / f"tabela{tabela.numero}.tex", _tabela(
            None, f"tab:tabela{tabela.numero}", "l" + GRUPO + "r" * len(metricas), cab,
            "\n        ".join(linhas), _texto(tabela.titulo) + ".",
            r"Em cinza, a resposta prevista pelo modelo do Experimento~8 com o controlador projetado. "
            r"$T_r$ de 10\,\% a 90\,\%, $T_s$ na faixa de $\pm 2$\,\%, $\tau$ é o tempo até 63,2\,\%; "
            r"``--'' onde não há pico (resposta sem sobressinal) ou a resposta não acomodou na janela.", tabela.numero))
        _csv(pasta / "csv" / f"tabela{tabela.numero}.csv", ["caso"] + [f"{k}_{lado}" for k in metricas for lado in ("exp", "prev")],
             [[float(i.split(".")[1]) for i in tabela.casos]]
             + [[(sessao.capturas[i].valores() if i in sessao.capturas else {}).get(k, math.nan) if lado == "exp"
                 else (sessao.capturas[i].previsto if i in sessao.capturas else sessao._prever(sessao.roteiro.caso(i))).get(k, math.nan)
                 for i in tabela.casos] for k in metricas for lado in ("exp", "prev")])


def tabela_projeto(sessao, pasta):
    """Ganhos, polos e componentes de cada linha."""
    linhas = []
    for caso in sessao.roteiro.casos():
        p, v = sessao._projeto(caso), sessao._v_por_unidade(caso)
        g = componentes_motor.ganhos_eletricos(p, v)
        c = componentes_motor.dimensionar(g["kp"], g["ki"], g["kd"], componentes_motor.escolher_c2(g["ki"]))
        real = componentes_motor.comerciais(c)
        ganhos = [f"$K_p = {_g(g['kp'])}$"] + ([f"$K_i = {_g(g['ki'])}$"] if g["ki"] else []) + \
                 ([f"$K_d = {_g(g['kd'])}$"] if g["kd"] else [])
        comp = [rf"{nome} = {_g(real[nome] * esc, 3)} {un}" for nome, esc, un in
                (("R", 1e-3, r"k$\Omega$"), ("R2", 1e-3, r"k$\Omega$"), ("C1", 1e6, r"\textmu F"), ("C2", 1e6, r"\textmu F"))
                if real[nome] is not None]
        comp = [x.replace("R2 =", "$R_2$ =").replace("C1 =", "$C_1$ =").replace("C2 =", "$C_2$ =").replace("R =", "$R$ =")
                for x in comp]
        polos = "; ".join(dict.fromkeys(
            (_g(x.real, 3) if abs(x.imag) < 1e-6 else f"{_g(x.real, 3)} $\\pm$ j{_g(abs(x.imag), 3)}")
            for x in sorted(p.polos(), key=lambda x: x.real)))
        linhas.append(f"{_texto(caso.rotulo)} & {c['tipo']} & {', '.join(ganhos)} & {polos} & {', '.join(comp)} \\\\")
    _tex(pasta / "tab" / "projeto.tex", _tabela(
        "P", "tab:projeto", "ll" + GRUPO + "p{3.2cm}p{2.6cm}p{4.2cm}", r"linha & tipo & ganhos & polos de malha fechada ($1/$s) & componentes \\",
        "\n        ".join(linhas),
        r"Controladores projetados sobre o modelo identificado no Experimento~8. Ganhos do circuito, em V/V, 1/s e s "
        r"(na posição, divididos pelo ganho do sensor); componentes da série E24 (resistores) e E6 (capacitores)."))


# ------------------------------------------------------------------ gráficos
def grafico_respostas(tabela, resultados, prefixo, pasta):
    """Um painel por linha medida: referência, saída medida e saída prevista."""
    if not resultados:
        return
    paineis = []
    for k, res in enumerate(resultados):
        t, ref, y, prev = painel_controle.curvas(res)
        passo = max(1, len(t) // PONTOS)
        s = slice(0, len(t), passo)
        nome = f"resposta_t{tabela.numero}_c{res.caso.id}.csv"
        _csv(pasta / "csv" / nome, ("t", "ref", "exp", "prev"),
             (t[s] / 1e3, ref[s] if ref is not None else np.full(len(t[s]), math.nan), y[s], prev[s]))
        arq = f"{prefixo}/csv/{nome}"
        opcoes = [rf"title={{{_texto(res.caso.rotulo)}}}", f"xmin=0, xmax={t[-1] / 1e3:.3f}"]
        if k == 0:
            opcoes.append(f"legend to name=leg-resp{tabela.numero}")
        leg = (r" \addlegendentry{referência}", r" \addlegendentry{medido}", r" \addlegendentry{previsto}") if k == 0 else ("",) * 3
        paineis.append("\n            ".join([
            f"\\nextgroupplot[{', '.join(opcoes)}]",
            rf"\addplot[gray, dashed, line width=0.8pt] table[x=t, y=ref, col sep=comma] {{{arq}}};{leg[0]}",
            rf"\addplot[cor-medido, line width=1pt] table[x=t, y=exp, col sep=comma] {{{arq}}};{leg[1]}",
            rf"\addplot[cor-teorico, dashed, line width=0.8pt] table[x=t, y=prev, col sep=comma] {{{arq}}};{leg[2]}"]))
    linhas = math.ceil(len(paineis) / 2)
    colunas = 2 if len(paineis) > 1 else 1
    _tex(pasta / "tex" / f"plot_resposta{tabela.numero}.tex", rf"""
{CORES}
\begin{{figure}}[htbp]
    \centering
    \pgfplotslegendfromname{{leg-resp{tabela.numero}}}\par\smallskip
    \begin{{tikzpicture}}
        \begin{{groupplot}}[
            group style={{group size={colunas} by {linhas}, horizontal sep=1.6cm, vertical sep=1.5cm,
                          xlabels at=edge bottom, ylabels at=edge left}},
            scale only axis, width={'0.4' if colunas == 2 else '0.7'}\textwidth, height=0.2\textwidth,
            xlabel={{tempo (s)}}, ylabel={{tensão (V)}},
            grid=major, grid style={{gray!20}},
            title style={{font=\footnotesize, at={{(0,1)}}, anchor=south west}},
            tick label style={{font=\scriptsize, /pgf/number format/.cd, use comma, 1000 sep={{.}}}},
            legend columns=3, legend style={{font=\footnotesize, draw=none}},
        ]
            {chr(10).join('            ' + p for p in paineis).strip()}
        \end{{groupplot}}
    \end{{tikzpicture}}
    \caption{{Resposta ao degrau da Tabela~\ref{{tab:tabela{tabela.numero}}}: referência (CH1), saída medida (CH2) e a
             saída prevista pelo modelo, a partir do instante do degrau.}}
    \label{{fig:resposta{tabela.numero}}}
\end{{figure}}""")


def grafico_lgr(caso, p, prefixo, pasta):
    """Polos de malha aberta e de malha fechada sobre o lugar das raízes da malha."""
    rs = painel_controle.raizes(p)
    nome = f"lgr_c{caso.id}.csv"
    _csv(pasta / "csv" / nome, ("re", "im"), (rs.real.ravel(), rs.imag.ravel()))
    arq = f"{prefixo}/csv/{nome}"
    ma = np.roots(p.direto().den)
    zeros = np.roots(p.direto().num) if len(p.direto().num) > 1 else np.array([])
    mf = np.asarray(p.polos())
    xmax, ymax = painel_controle.escala(p)
    fora = zeros[np.abs(zeros.real) > xmax]
    zeros = zeros[np.abs(zeros.real) <= xmax]
    pontos = lambda z: "\n                ".join(f"({_num(x.real)}, {_num(x.imag)})" for x in z)
    curvas = [rf"\addplot[only marks, mark=*, mark size=0.4pt, gray] table[x=re, y=im, col sep=comma] {{{arq}}}; "
              r"\addlegendentry{lugar das raízes}",
              rf"\addplot[only marks, mark=x, mark size=3.5pt, very thick, cor-teorico] coordinates {{{pontos(ma)}}}; "
              r"\addlegendentry{polos de malha aberta}"]
    if len(zeros):
        curvas.append(rf"\addplot[only marks, mark=o, mark size=3pt, thick, cor-teorico] coordinates {{{pontos(zeros)}}}; "
                      r"\addlegendentry{zeros}")
    curvas.append(rf"\addplot[only marks, mark=square*, mark size=2.5pt, cor-medido] coordinates {{{pontos(mf)}}}; "
                  r"\addlegendentry{polos de malha fechada}")
    corpo = (rf"""xlabel={{$\mathrm{{Re}}(s)$ (1/s)}}, ylabel={{$\mathrm{{Im}}(s)$ (rad/s)}},
            xmin={_num(-xmax)}, xmax={_num(0.15 * xmax)}, ymin={_num(-ymax)}, ymax={_num(ymax)}, legend pos=north west,
        ]
            """ + "\n            ".join(curvas))
    nota = "".join(f" O zero em $s = {_g(z.real, 3)}$ fica fora da escala." for z in fora)
    _figura(f"plot_lgr_{caso.id.replace('.', '_')}", corpo,
            f"Lugar das raízes de {_texto(caso.rotulo)} ({p.nome}) com os polos de malha aberta e de malha fechada.{nota}",
            f"fig:lgr-{caso.id.replace('.', '-')}", pasta, altura=r"0.32\textwidth")


# ------------------------------------------------------------------ código
def codigo(prefixo, pasta):
    """Trechos do projeto e do dimensionamento: (nome, módulo, do começo de `de` ao fim de `ate`)."""
    P, C, R = projeto_motor, componentes_motor, resposta_motor
    trechos = (("pi", P, P.ProjetoPI, P.ProjetoPI.ganhos), ("pd", P, P.ProjetoPD.analitico, P.ProjetoPD._projetar),
               ("pid", P, P.ProjetoPID, P.ProjetoPID), ("componentes", C, C.dimensionar, C.dimensionar),
               ("resposta", R, R.previsao, R.previsao))
    for nome, modulo, de, ate in trechos:
        arquivo = Path(modulo.__file__)
        destino = pasta / "cod" / ("motor_" + arquivo.name)
        destino.write_text(_ascii(arquivo.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
        ini = inspect.getsourcelines(de)[1]
        linhas, comeco = inspect.getsourcelines(ate)
        fim = comeco + len(linhas) - 1
        nomes = de.__qualname__ if de == ate else f"{de.__qualname__} a {ate.__qualname__}"
        _tex(pasta / "tex" / f"cod9_{nome}.tex", rf"""
\lstinputlisting[
    firstline={ini}, lastline={fim}, firstnumber={ini}, float=htbp,
    caption={{\texttt{{labscope/motor/{arquivo.name}}}: \texttt{{{nomes.replace("_", chr(92) + "_")}}}}},
    label={{lst:e9-{nome}}}
]{{{prefixo}/cod/{destino.name}}}""")


# ------------------------------------------------------------------ tudo
def exportar(sessao, destino, prefixo):
    destino = Path(destino)
    for sub in ("csv", "tab", "tex", "cod"):
        (destino / sub).mkdir(parents=True, exist_ok=True)
    sessao._exigir_motor()
    tabelas_roteiro(sessao, destino)
    tabela_projeto(sessao, destino)
    for tabela in sessao.roteiro.tabelas():
        grafico_respostas(tabela, [sessao.capturas[c] for c in tabela.casos if c in sessao.capturas], prefixo, destino)
    for caso in sessao.roteiro.casos():
        if caso.id.endswith(".1"):           # as linhas de uma tabela só mudam Vg: os polos são os mesmos
            grafico_lgr(caso, sessao._projeto(caso), prefixo, destino)
    codigo(prefixo, destino)
    return sorted(sessao.capturas.values(), key=lambda r: r.numero)
