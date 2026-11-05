"""Exporta uma sessão do Experimento 10 para uma atividade do modelo-latex.

Chamado por `python -m labscope.sessao.latex <sessao> <destino>` quando a sessão é do
compensador avanço de fase. Gera csv/, tab/ e tex/ com:

  tab/tabela1.tex ... tabela7.tex   as tabelas da folha que têm captura: medido e previsto
  tab/componentes.tex               componentes das duas montagens
  tex/plot_senoide<n>.tex           entrada, saída medida e saída prevista (Tabelas 1, 2, 4 e 7)
  tex/plot_bode2.tex                |G| e fase do compensador, medido contra teórico (Tabela 2)
  tex/plot_degrau<n>.tex            resposta ao degrau, medido contra teórico (Tabelas 3 e 5)

Nas tabelas senoidais o Vpp previsto da saída usa o Vpp de entrada medido (|G| × Vpp de CH1),
porque o gerador nem sempre fica nos 2 Vpp da folha.
"""
import math
from pathlib import Path

import numpy as np

from ..medidas import bode as _bode
from ..roteiros import texto_si
from . import painel
from .latex import GRUPO, PONTOS, _cinza, _csv, _tabela, _tex

CORES = r"""% Cores validadas para daltonismo (Okabe-Ito); o traço também distingue as curvas na impressão P&B.
\definecolor{cor-medido}{HTML}{0072B2}
\definecolor{cor-teorico}{HTML}{D55E00}
\definecolor{cor-carga}{HTML}{009E73}"""

ESTILO_EIXOS = r"""grid=major, grid style={gray!20},
            title style={font=\small, at={(0,1)}, anchor=south west},
            scaled ticks=false,
            tick label style={font=\footnotesize, /pgf/number format/.cd, fixed, use comma, 1000 sep={\,}},
            legend columns=3, legend style={font=\footnotesize, draw=none, /tikz/every even column/.append style={column sep=0.6em}},
            unbounded coords=jump"""

TEMPO = {"tau": (r"$\tau$", 1), "tr": (r"$T_r$", 1), "tp": (r"$T_p$", 1), "ts": (r"$T_s$", 1)}
OUTRAS = {"mp": (r"$M_p$ (\%)", 100, 1), "vc": (r"$V_c$ (V)", 1, 3), "ess": (r"$e_{ss}$ (\%)", 100, 1),
          "zeta": (r"$\zeta$", 1, 3), "wn": (r"$\omega_n$ (rad/s)", 1, 0), "wd": (r"$\omega_d$ (rad/s)", 1, 0)}


def _v(x, casas, sinal=True):
    """Número com vírgula decimal; '--' para NaN."""
    if x is None or not np.isfinite(x):
        return "--"
    s = f"{x:.{casas}f}".replace(".", ",")
    return s.replace("-", "$-$") if sinal else s


def _hz(caso):
    return texto_si(caso.frequencia, "Hz").replace(" ", r"\,")


def _rot(caso):
    return _hz(caso) if caso.senoide and caso.circuito in ("inversor", "avanco") else caso.rotulo.replace("RC", "RC").replace(" Hz", r"\,Hz")


# ------------------------------------------------------------------ tabelas
def tabela_senoide(tabela, resultados, pasta):
    """Vpp da saída, |G| e fase: medido e teórico, uma linha por frequência."""
    linhas = []
    for r in resultados:
        m, p = r.medida, r.previsto
        linhas.append(" & ".join([
            _rot(r.caso), _v(m.vpp_entrada, 3), _v(m.vpp, 3), _cinza(_v(p.ganho * m.vpp_entrada, 3)),
            _v(m.ganho, 3), _v(p.ganho, 3), _v(m.fase, 1), _v(p.fase, 1)]) + r" \\")
    cab = (r"& & \multicolumn{2}{c}{$V_{pp}$ da saída (V)} & \multicolumn{2}{c}{$|G|$} & \multicolumn{2}{c}{fase ($^\circ$)} \\"
           "\n        \\cmidrule(lr){3-4} \\cmidrule(lr){5-6} \\cmidrule(lr){7-8}\n        "
           r"caso & $V_{pp}$ entrada (V) & exp. & " + _cinza("prev.") + r" & exp. & teór. & exp. & teór. \\")
    nota = (r"Previsto de $V_{pp}$ da saída: $|G|$ teórico $\times$ $V_{pp}$ de entrada medido em CH1. "
            r"Fase de CH2 em relação a CH1, pelo ajuste de senoide.")
    _tex(pasta / "tab" / f"tabela{tabela.numero}.tex", _tabela(
        None, f"tab:tabela{tabela.numero}", "l" + GRUPO + "r" + GRUPO + "rr" + GRUPO + "rr" + GRUPO + "rr", cab,
        "\n        ".join(linhas), f"{_titulo(tabela)}.", nota, tabela.numero))
    _csv(pasta / "csv" / f"tabela{tabela.numero}.csv",
         ("f", "vpp_in", "vpp_exp", "vpp_prev", "ganho_exp", "ganho_teo", "fase_exp", "fase_teo"),
         [[r.caso.frequencia for r in resultados], [r.medida.vpp_entrada for r in resultados],
          [r.medida.vpp for r in resultados], [r.previsto.ganho * r.medida.vpp_entrada for r in resultados],
          [r.medida.ganho for r in resultados], [r.previsto.ganho for r in resultados],
          [r.medida.fase for r in resultados], [r.previsto.fase for r in resultados]])


def tabela_degrau(tabela, resultados, pasta):
    """Métricas da tabela nas linhas; experimental, teórico, c/ carga e desvio."""
    res = resultados[0]
    ls = [res.linha(k) for k in tabela.metricas]
    ls = [l for l in ls if l is not None]
    if not ls:
        return False
    usa_us = max((l.teo for l in ls if l.metrica.chave in TEMPO and np.isfinite(l.teo)), default=1.0) < 1e-3
    escala_t, un = (1e6, r"$\mu$s") if usa_us else (1e3, "ms")
    linhas = []
    for l in ls:
        k = l.metrica.chave
        if k in TEMPO:
            nome, esc, casas = rf"{TEMPO[k][0]} ({un})", escala_t, 0 if usa_us else 2
        else:
            nome, esc, casas = OUTRAS[k]
        desvio = _v(100 * l.desvio, 1) + r"\,\%" if l.desvio is not None and np.isfinite(l.desvio) else "--"
        linhas.append(" & ".join([nome, _v(l.exp * esc, casas), _v(l.teo * esc, casas),
                                  _cinza(_v(l.carga * esc, casas)), desvio]) + r" \\")
    cab = r"métrica & exp. & teór. & " + _cinza("c/ carga") + r" & desvio \\"
    nota = (r"$T_r$ de 10\,\% a 90\,\%, $T_s$ na faixa de $\pm 2$\,\%, $\tau$ até 63,2\,\%; a saída medida foi "
            r"suavizada por média móvel de " + f"{_v(res.medida.suavizacao * 1e6, 1)}" + r"\,$\mu$s.")
    _tex(pasta / "tab" / f"tabela{tabela.numero}.tex", _tabela(
        None, f"tab:tabela{tabela.numero}", "l" + GRUPO + "rrr" + GRUPO + "r", cab, "\n        ".join(linhas),
        f"{_titulo(tabela)}.", nota, tabela.numero))
    return True


def _titulo(tabela):
    t = tabela.titulo
    for a, b in (("µ", r"$\mu$"), ("Ω", r"$\Omega$"), ("ζ", r"$\zeta$"), ("ω_n", r"$\omega_n$"), ("ω_d", r"$\omega_d$")):
        t = t.replace(a, b)
    for k in ("C1", "C2", "R1", "R2", "R3", "R4", "L1", "Cc", "Rc"):
        t = t.replace(f"{k} =", f"${k[0]}_{{{k[1:]}}}$ =")
    t = t.replace("R = R6 =", r"$R$ = $R_6$ =")
    return t.replace("Vpp", r"V$_{pp}$").replace(" 2 V$_{pp}$", r" 2\,V$_{pp}$")


def tabela_componentes(resultados, pasta):
    """Componentes nominais usados nos circuitos medidos."""
    por_circuito = {}
    for r in resultados:
        por_circuito.setdefault(r.caso.circuito, r)
    colunas = [("inversor", "inversor"), ("avanco", "avanço"), ("RC", "RC")]
    colunas = [(c, n) for c, n in colunas if c in por_circuito]
    nomes = ("R", "R1", "C1", "R2", "C2", "R3", "R4", "R5", "R6", "Rc", "Cc")
    unidade = por_circuito[colunas[0][0]].comp.UNIDADES
    linhas = []
    for nome in nomes:
        celulas = []
        for c, _ in colunas:
            r = por_circuito[c]
            celulas.append(texto_si(getattr(r.comp, nome), unidade[nome]).replace("µ", r"$\mu$").replace("Ω", r"$\Omega$")
                           if nome in r.caso.usados else "--")
        if all(x == "--" for x in celulas):
            continue
        linhas.append(f"${nome[0]}_{{{nome[1:]}}}$ & " .replace("_{}", "") + " & ".join(celulas) + r" \\")
    _tex(pasta / "tab" / "componentes.tex", _tabela(
        "C", "tab:componentes", "l" + GRUPO + "r" * len(colunas), " & " + " & ".join(n for _, n in colunas) + r" \\",
        "\n        ".join(linhas), "Componentes nominais de cada montagem (valores do roteiro)."))


# ------------------------------------------------------------------ gráficos
def _decimar(n, alvo=PONTOS):
    return slice(0, n, max(1, n // alvo))


def grafico_senoide(tabela, resultados, prefixo, pasta):
    """Um painel por frequência: CH1, CH2 e a saída prevista com a mesma entrada, em até 3 períodos."""
    paineis = []
    for k, r in enumerate(resultados):
        m = r.medida
        fim = np.searchsorted(m.t, m.t[0] + min(m.periodos, 3.0) / m.frequencia)
        t = m.t[:fim]
        s = _decimar(len(t))
        teo = r.previsto.curva(t, m._entrada[1]) * m.vpp_entrada / (2 * r.previsto.amplitude)
        nome = f"senoide_t{tabela.numero}_c{r.caso.id}.csv"
        _csv(pasta / "csv" / nome, ("t", "ch1", "ch2", "ajuste", "teo"),
             ((t[s] - t[0]) * 1e3, m.captura[m.canal_entrada][:fim][s], m.captura[m.canal_saida][:fim][s],
              m.curva()[:fim][s], teo[s]))
        arq = f"{prefixo}/csv/{nome}"
        opcoes = [rf"title={{{_rot(r.caso)} \quad (captura \#{r.numero:02d})}}",
                  f"xmin=0, xmax={(t[-1] - t[0]) * 1e3:.4g}"]
        if k == 0:
            opcoes.append(f"legend to name=leg-sen{tabela.numero}")
        leg = ([r" \addlegendentry{entrada (CH1)}", r" \addlegendentry{saída medida (CH2)}",
                r" \addlegendentry{saída teórica}"] if k == 0 else [""] * 3)
        paineis.append("\n            ".join([
            f"\\nextgroupplot[{', '.join(opcoes)}]",
            rf"\addplot[gray!80, thick] table[x=t, y=ch1, col sep=comma] {{{arq}}};{leg[0]}",
            rf"\addplot[cor-medido, line width=1pt] table[x=t, y=ch2, col sep=comma] {{{arq}}};{leg[1]}",
            rf"\addplot[cor-teorico, dashed, line width=0.9pt] table[x=t, y=teo, col sep=comma] {{{arq}}};{leg[2]}"]))
    colunas = 2 if len(paineis) > 1 else 1
    linhas = math.ceil(len(paineis) / colunas)
    largura = "0.4" if colunas == 2 else "0.7"
    _tex(pasta / "tex" / f"plot_senoide{tabela.numero}.tex", rf"""
{CORES}
\begin{{figure}}[htbp]
    \centering
    \pgfplotslegendfromname{{leg-sen{tabela.numero}}}\par\smallskip
    \begin{{tikzpicture}}
        \begin{{groupplot}}[
            group style={{group size={colunas} by {linhas}, horizontal sep=1.8cm, vertical sep=2.3cm}},
            scale only axis, width={largura}\textwidth, height=0.2\textwidth,
            xlabel={{tempo (ms)}}, ylabel={{tensão (V)}},
            {ESTILO_EIXOS},
        ]
            {chr(10).join('            ' + p for p in paineis).strip()}
        \end{{groupplot}}
    \end{{tikzpicture}}
    \caption{{Casos da Tabela~\ref{{tab:tabela{tabela.numero}}}: entrada (CH1), saída medida (CH2) e saída prevista
             pelo modelo para a mesma entrada.}}
    \label{{fig:senoide{tabela.numero}}}
\end{{figure}}""")


def grafico_bode(tabela, resultados, prefixo, pasta):
    """|G| (dB) e fase do circuito da tabela, curva teórica e pontos medidos."""
    casos = [r.caso for r in resultados]
    f = np.logspace(np.log10(min(c.frequencia for c in casos)) - 0.7, np.log10(max(c.frequencia for c in casos)) + 0.7, 200)
    db, graus = _bode(casos[0].malha(resultados[0].comp).ft(), f)
    graus = graus - 360 * np.round(np.median(graus) / 360)
    _csv(pasta / "csv" / f"bode_t{tabela.numero}_teo.csv", ("f", "db", "fase"), (f, db, graus))
    fm = np.array([r.medida.frequencia for r in resultados])
    fase = [r.medida.fase + 360 * np.round((np.interp(np.log(x), np.log(f), graus) - r.medida.fase) / 360)
            for r, x in zip(resultados, fm)]
    _csv(pasta / "csv" / f"bode_t{tabela.numero}_exp.csv", ("f", "db", "fase"),
         (fm, [20 * np.log10(r.medida.ganho) for r in resultados], fase))
    teo, exp = (f"{prefixo}/csv/bode_t{tabela.numero}_{x}.csv" for x in ("teo", "exp"))
    _tex(pasta / "tex" / f"plot_bode{tabela.numero}.tex", rf"""
{CORES}
\begin{{figure}}[htbp]
    \centering
    \pgfplotslegendfromname{{leg-bode{tabela.numero}}}\par\smallskip
    \begin{{tikzpicture}}
        \begin{{groupplot}}[
            group style={{group size=1 by 2, vertical sep=0.6cm, xlabels at=edge bottom, xticklabels at=edge bottom}},
            scale only axis, width=0.8\textwidth, height=0.22\textwidth, xmode=log,
            xlabel={{frequência (Hz)}},
            {ESTILO_EIXOS},
        ]
            \nextgroupplot[ylabel={{$|G|$ (dB)}}, legend to name=leg-bode{tabela.numero}]
            \addplot[cor-teorico, dashed, line width=0.9pt, mark=none] table[x=f, y=db, col sep=comma] {{{teo}}};
            \addlegendentry{{teórico}}
            \addplot[only marks, mark=square*, mark size=2.2pt, cor-medido] table[x=f, y=db, col sep=comma] {{{exp}}};
            \addlegendentry{{medido}}
            \nextgroupplot[ylabel={{fase ($^\circ$)}}]
            \addplot[cor-teorico, dashed, line width=0.9pt, mark=none] table[x=f, y=fase, col sep=comma] {{{teo}}};
            \addplot[only marks, mark=square*, mark size=2.2pt, cor-medido] table[x=f, y=fase, col sep=comma] {{{exp}}};
        \end{{groupplot}}
    \end{{tikzpicture}}
    \caption{{Resposta em frequência do compensador (Tabela~\ref{{tab:tabela{tabela.numero}}}): módulo e fase,
             modelo teórico e pontos medidos.}}
    \label{{fig:bode{tabela.numero}}}
\end{{figure}}""")


def grafico_degrau(tabela, resultados, prefixo, pasta):
    """Resposta ao degrau inteira e ampliada: entrada, medido, teórico e c/ carga."""
    from .latex import curvas
    paineis = []
    for res in resultados:
        t, u, y, teo, cg = curvas(res)
        teo, cg = -teo, -cg          # a medida já vem como -CH2 (segue a entrada); os modelos dão V_c, invertido
        nome = f"degrau_t{tabela.numero}_c{res.caso.id}.csv"
        _csv(pasta / "csv" / nome, ("t", "e1", "exp", "teo", "carga"), (t, u, y, teo, cg))
        arq = f"{prefixo}/csv/{nome}"
        ts = [l.exp for l in (res.linha("ts"),) if l is not None and np.isfinite(l.exp)]
        zoom = min(t[-1], 6 * ts[0] * 1e3) if ts else t[-1] / 5
        janelas = (t[-1],) if zoom >= 0.7 * t[-1] else (t[-1], zoom)      # sem ampliação se a janela já é curta
        for k, xmax in enumerate(janelas):
            opcoes = [f"xmin={t[0]:.4g}, xmax={xmax:.4g}"]
            if len(janelas) > 1:
                opcoes.insert(0, f"title={{{'resposta completa' if k == 0 else 'ampliação do transitório'}}}")
            if not paineis:
                opcoes.append(f"legend to name=leg-deg{tabela.numero}")
            leg = ([r" \addlegendentry{entrada $e_1$}", r" \addlegendentry{medido ($-V_c$)}",
                    r" \addlegendentry{teórico}", r" \addlegendentry{c/ carga do inversor}"] if not paineis else [""] * 4)
            paineis.append("\n            ".join([
                f"\\nextgroupplot[{', '.join(opcoes)}]",
                rf"\addplot[gray!70, thick, const plot] table[x=t, y=e1, col sep=comma] {{{arq}}};{leg[0]}",
                rf"\addplot[cor-medido, line width=1.1pt] table[x=t, y=exp, col sep=comma] {{{arq}}};{leg[1]}",
                rf"\addplot[cor-teorico, dashed, line width=0.9pt] table[x=t, y=teo, col sep=comma] {{{arq}}};{leg[2]}",
                rf"\addplot[cor-carga, densely dotted, line width=1.1pt] table[x=t, y=carga, col sep=comma] {{{arq}}};{leg[3]}"]))
    _tex(pasta / "tex" / f"plot_degrau{tabela.numero}.tex", rf"""
{CORES}
\begin{{figure}}[htbp]
    \centering
    \pgfplotslegendfromname{{leg-deg{tabela.numero}}}\par\smallskip
    \begin{{tikzpicture}}
        \begin{{groupplot}}[
            group style={{group size={2 if len(paineis) > 1 else 1} by {max(1, len(paineis) // 2)}, horizontal sep=1.8cm, vertical sep=1.6cm}},
            scale only axis, width={'0.36' if len(paineis) > 1 else '0.7'}\textwidth, height=0.24\textwidth,
            xlabel={{tempo após a borda de subida (ms)}}, ylabel={{tensão (V)}},
            {ESTILO_EIXOS}, legend columns=4,
        ]
            {chr(10).join('            ' + p for p in paineis).strip()}
        \end{{groupplot}}
    \end{{tikzpicture}}
    \caption{{Resposta ao degrau da Tabela~\ref{{tab:tabela{tabela.numero}}}: entrada, saída medida e saídas dos dois
             modelos, todas com o sinal trocado ($-V_c$), já que a malha inverte a saída em relação à entrada.}}
    \label{{fig:degrau{tabela.numero}}}
\end{{figure}}""")


# ------------------------------------------------------------------ tudo
def exportar(sessao, destino, prefixo):
    destino = Path(destino)
    for sub in ("csv", "tab", "tex"):
        (destino / sub).mkdir(parents=True, exist_ok=True)
    por_caso = {cid: res for (_, cid), res in sessao.resultados.items()}
    gerados = []
    for tabela in sessao.roteiro.tabelas():
        resultados = [por_caso[c] for c in tabela.casos if c in por_caso]
        if not resultados:
            continue
        if resultados[0].caso.senoide:
            tabela_senoide(tabela, resultados, destino)
            grafico_senoide(tabela, resultados, prefixo, destino)
            if len(resultados) > 2:
                grafico_bode(tabela, resultados, prefixo, destino)
        elif tabela_degrau(tabela, resultados, destino):
            if tabela.numero != 6:                    # a Tabela 6 usa a captura da 5
                grafico_degrau(tabela, resultados, prefixo, destino)
        else:
            continue
        gerados.append(tabela.numero)
    tabela_componentes(sorted(por_caso.values(), key=lambda r: [int(x) for x in r.caso.id.split(".")]), destino)
    return sorted(por_caso.values(), key=lambda r: r.numero)
