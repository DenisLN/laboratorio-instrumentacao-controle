"""Exporta uma sessão gravada para uma atividade do modelo-latex (pastas csv/ tab/ tex/ cod/).

    python -m labscope.sessao.latex sessoes/sessao_2026-10-06_13-42-01 saida/07 [--prefixo 07]

Cada caso do roteiro usa a última captura válida dele, como o 'retomar' faz.
Os trechos .tex usam caminhos a partir da raiz da disciplina (`07/csv/...`),
que é como o `doc c` compila.
"""
import argparse
import contextlib
import inspect
import io
import math
import re
import shutil
import warnings
from pathlib import Path

import numpy as np

from .. import medidas
from .. import relatorio as Rl
from ..roteiros import Componentes, texto_si
from . import painel
from .cli import SessaoLab

PONTOS = 350                     # pontos por curva nos CSVs (o pgfplots fica lento com 2500 x 10)

# chave, cabeçalho, casas, escala
METRICAS = (("tr", r"$T_r$ (ms)", 2, 1e3), ("tp", r"$T_p$ (ms)", 2, 1e3), ("mp", r"$M_p$ (\%)", 1, 100),
            ("ts", r"$T_s$ (ms)", 2, 1e3), ("vc", r"$V_c$ (V)", 3, 1.0))
ASCII_CODIGO = str.maketrans({**{chr(0x2080 + k): str(k) for k in range(10)},
                              "∥": "||", "→": "->", "−": "-", "·": "*", "×": "x", "²": "^2"})
VARIAVEL = {"R2": "R_2", "C1": "C_1", "C2": "C_2", "R1": "R_L", "C": "C_L", "L": "L", "R": "R"}


def carregar(pasta):
    """{caso.id: Resultado} da sessão, com a última captura válida de cada caso."""
    s = SessaoLab(abrir_figuras=False)
    with contextlib.redirect_stdout(io.StringIO()), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        s.cmd_retomar([str(pasta)])
    return {cid: res for (_, cid), res in s.resultados.items()}


def _n(x, casas, escala=1.0):
    return Rl.num(x, casas, escala=escala).replace("−", "$-$")


def _csv(caminho, cabecalho, colunas):
    linhas = [",".join(cabecalho)]
    linhas += [",".join("nan" if not np.isfinite(v) else f"{v:.6g}" for v in linha) for linha in zip(*colunas)]
    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def _tex(caminho, texto):
    caminho.write_text(texto.strip() + "\n", encoding="utf-8")


def _rotulo(caso):
    """'R2 = 1 kΩ' → '$R_2$ = 1 k$\\Omega$'."""
    nome, valor = caso.rotulo.split(" = ")
    nome = VARIAVEL.get(nome, nome)
    return f"${nome}$ = " + valor.replace("Ω", r"$\Omega$").replace("µ", r"$\mu$")


# ------------------------------------------------------------------ curvas
def curvas(res):
    """(t em ms após a borda, e1, Vc medido, Vc teórico, Vc c/ carga) de um trecho de subida."""
    m = res.medida
    i, j, _ = m.trechos[painel._trecho_para_mostrar(m)]
    a, b = painel._janela(res, i, j)
    teo = res.teoria.curva(m.t, m.entrada)
    carga = res.teoria_carga.curva(m.t, m.entrada)
    passo = max(1, (b - a) // PONTOS)
    s = slice(a, b, passo)
    return (m.t[s] - m.t[i]) * 1e3, m.u[s], m.y[s], teo[s], carga[s]


def _passo(faixa, divisoes=6):
    """Espaçamento 'redondo' (1, 2, 2,5 ou 5 × 10^k) para cerca de `divisoes` marcas."""
    bruto = faixa / divisoes
    ordem = 10 ** math.floor(math.log10(bruto))
    return next(m * ordem for m in (1, 2, 2.5, 5, 10) if m * ordem >= bruto)


def grafico(tabela, resultados, prefixo, pasta):
    """CSVs dos casos da tabela e tex/plot_tabelaN.tex: um painel por caso, empilhados,
    cada um com o tempo do próprio transitório e todos com a mesma escala de tensão.
    A cor é do modelo (medido, teórico, c/ carga), não do caso."""
    dados = []
    for res in resultados:
        t, u, y, teo, cg = curvas(res)
        nome = f"t{tabela.numero}_c{res.caso.id}.csv"
        _csv(pasta / "csv" / nome, ("t", "e1", "exp", "teo", "carga"), (t, u, y, teo, cg))
        dados.append((res, f"{prefixo}/csv/{nome}", t, np.concatenate([u, y, teo, cg])))
    v = np.concatenate([d[3] for d in dados])
    v = v[np.isfinite(v)]
    ymin, ymax = math.floor(v.min() * 10 - 0.5) / 10, math.ceil(v.max() * 10 + 0.5) / 10
    legenda = f"leg-tabela{tabela.numero}"
    paineis = []
    for k, (res, arq, t, _) in enumerate(dados):
        ultimo = k == len(dados) - 1
        opcoes = [f"title={{{_rotulo(res.caso)} \\quad (captura \\#{res.numero:02d})}}",
                  f"xmin={t[0]:.2f}, xmax={t[-1]:.2f}, xtick distance={_passo(t[-1] - t[0], 8):g}"]
        if ultimo:
            opcoes.append("xlabel={Tempo após a borda de subida (ms)}")
        if k == 0:
            opcoes.append(f"legend to name={legenda}")
        legendas = (["entrada $e_1$", "medido ($V_c$)", "teórico (roteiro)", "c/ carga do inversor"]
                    if k == 0 else [])
        curvas_tex = [rf"\addplot[entrada, const plot] table[x=t, y=e1, col sep=comma] {{{arq}}};",
                      rf"\addplot[medido] table[x=t, y=exp, col sep=comma] {{{arq}}};",
                      rf"\addplot[teorico] table[x=t, y=teo, col sep=comma] {{{arq}}};",
                      rf"\addplot[comcarga] table[x=t, y=carga, col sep=comma] {{{arq}}};"]
        linhas = [f"\\nextgroupplot[{', '.join(opcoes)}]"]
        for i, c in enumerate(curvas_tex):
            linhas.append(c + (f" \\addlegendentry{{{legendas[i]}}}" if legendas else ""))
        paineis.append("\n            ".join(linhas))
    corpo = "\n\n            ".join(paineis)
    _tex(pasta / "tex" / f"plot_tabela{tabela.numero}.tex", rf"""
% Cores validadas para daltonismo (Okabe-Ito); o traço também distingue as curvas na impressão P&B.
\definecolor{{cor-medido}}{{HTML}}{{0072B2}}
\definecolor{{cor-teorico}}{{HTML}}{{D55E00}}
\definecolor{{cor-carga}}{{HTML}}{{009E73}}
\begin{{figure}}[htbp]
    \centering
    \pgfplotsset{{
        entrada/.style={{gray!70, thick}},
        medido/.style={{cor-medido, line width=1.1pt}},
        teorico/.style={{cor-teorico, dashed, line width=0.9pt}},
        comcarga/.style={{cor-carga, densely dotted, line width=1.1pt}},
    }}
    \pgfplotslegendfromname{{{legenda}}}\par\smallskip
    \begin{{tikzpicture}}
        \begin{{groupplot}}[
            group style={{group size=1 by {len(dados)}, vertical sep=1.5cm}},
            scale only axis, width=0.86\textwidth, height=0.2\textwidth,
            ymin={ymin:g}, ymax={ymax:g}, ylabel={{Tensão (V)}},
            grid=major, grid style={{gray!20}},
            title style={{font=\small, at={{(0,1)}}, anchor=south west}},
            tick label style={{font=\footnotesize, /pgf/number format/.cd, use comma}},
            legend columns=4, legend style={{font=\footnotesize, draw=none, /tikz/every even column/.append style={{column sep=0.6em}}}},
            unbounded coords=jump,
        ]
            {corpo}
        \end{{groupplot}}
    \end{{tikzpicture}}
    \caption{{Casos da Tabela~\ref{{tab:tabela{tabela.numero}}}: entrada, saída medida e saídas dos dois modelos.}}
    \label{{fig:tabela{tabela.numero}}}
\end{{figure}}""")


# ------------------------------------------------------------------ lugar das raízes
def _faixa(resultados, variavel):
    valores = [getattr(r.comp, variavel) for r in resultados]
    return np.logspace(math.log10(min(valores) / 10), math.log10(max(valores) * 10), 250)


def lgr(tabela, resultados, prefixo, pasta):
    """Lugar das raízes variando o componente da tabela, com os polos de cada caso."""
    variavel = Componentes.chave(resultados[0].caso.rotulo.split(" = ")[0])
    base, caso = resultados[0].comp, resultados[0].caso
    ramos = {}
    for carga in (False, True):
        pts = [painel._proximos(caso.malha(base.trocar(**{variavel: v}), carga=carga).polos())
               for v in _faixa(resultados, variavel)]
        p = np.concatenate(pts)
        ramos[carga] = p
        _csv(pasta / "csv" / f"lgr_t{tabela.numero}_{'carga' if carga else 'teo'}.csv", ("re", "im"),
             (p.real, p.imag))
    marcas = {"teo": [], "carga": [], "exp": []}
    for res in resultados:
        rot = res.caso.id
        for chave, malha in (("teo", res.teoria.malha), ("carga", res.teoria_carga.malha)):
            marcas[chave] += [(z, rot) for z in painel._proximos(malha.polos()) if z.imag >= 0]
        exp = painel._experimentais(res)
        if exp is not None:
            marcas["exp"] += [(z, rot) for z in exp if z.imag >= 0]
    for chave, lista in marcas.items():
        linhas = ["re,im,caso"] + [f"{z.real:.6g},{z.imag:.6g},{r}" for z, r in lista]
        (pasta / "csv" / f"lgr_t{tabela.numero}_polos_{chave}.csv").write_text("\n".join(linhas) + "\n",
                                                                                encoding="utf-8")
    todos = np.concatenate([ramos[False], ramos[True]] + [np.array([z for z, _ in l]) for l in marcas.values() if l])
    polos = np.concatenate([np.array([z for z, _ in l]) for l in marcas.values() if l])
    xmin = max(1.3 * min(polos.real.min(), -1), todos.real.min())
    xmax = -0.05 * xmin
    ymax = 1.3 * max(abs(polos.imag).max(), 1)
    ymin = -0.08 * ymax
    arq = f"{prefixo}/csv/lgr_t{tabela.numero}"
    nome = VARIAVEL.get(variavel, variavel)
    medidos = (rf"""
            \addplot[only marks, mark=square*, mark size=2.2pt, cor-medido]
                table[x=re, y=im, col sep=comma] {{{arq}_polos_exp.csv}};
            \addlegendentry{{polos medidos}}""" if marcas["exp"] else "")
    _tex(pasta / "tex" / f"lgr_tabela{tabela.numero}.tex", rf"""
% Mesmas cores dos gráficos no tempo: teórico, c/ carga e medido.
\definecolor{{cor-medido}}{{HTML}}{{0072B2}}
\definecolor{{cor-teorico}}{{HTML}}{{D55E00}}
\definecolor{{cor-carga}}{{HTML}}{{009E73}}
\begin{{figure}}[htbp]
    \centering
    \begin{{tikzpicture}}
        \begin{{axis}}[
            scale only axis, width=0.86\textwidth, height=0.36\textwidth,
            grid=major, grid style={{gray!20}},
            xlabel={{$\sigma$ (1/s)}}, ylabel={{$j\omega$ (rad/s)}},
            xmin={xmin:.0f}, xmax={xmax:.0f}, ymin={ymin:.0f}, ymax={ymax:.0f},
            xtick distance={_passo(xmax - xmin, 7):g}, ytick distance={_passo(ymax - ymin, 5):g},
            scaled ticks=false,
            tick label style={{font=\footnotesize, /pgf/number format/.cd, use comma, 1000 sep={{.}}}},
            legend cell align=left, legend columns=3,
            legend style={{at={{(0.5,1.03)}}, anchor=south, font=\footnotesize, draw=none,
                          /tikz/every even column/.append style={{column sep=0.8em}}}},
            legend image post style={{mark size=2pt}},
            restrict x to domain={xmin:.0f}:{xmax:.0f},
        ]
            \addplot[only marks, mark=*, mark size=0.45pt, cor-teorico!45] table[x=re, y=im, col sep=comma] {{{arq}_teo.csv}};
            \addlegendentry{{variando ${nome}$ -- teórico}}
            \addplot[only marks, mark=*, mark size=0.45pt, cor-carga!45] table[x=re, y=im, col sep=comma] {{{arq}_carga.csv}};
            \addlegendentry{{variando ${nome}$ -- c/ carga}}
            \addplot[only marks, mark=x, mark size=3.2pt, line width=1pt, cor-teorico, nodes near coords,
                     point meta=explicit symbolic, every node near coord/.style={{font=\footnotesize, black, anchor=south west}}]
                table[x=re, y=im, meta=caso, col sep=comma] {{{arq}_polos_teo.csv}};
            \addlegendentry{{polos teóricos}}
            \addplot[only marks, mark=o, mark size=2.8pt, line width=1pt, cor-carga]
                table[x=re, y=im, col sep=comma] {{{arq}_polos_carga.csv}};
            \addlegendentry{{polos c/ carga}}{medidos}
        \end{{axis}}
    \end{{tikzpicture}}
    \caption{{Lugar das raízes variando ${nome}$ nos casos da Tabela~\ref{{tab:tabela{tabela.numero}}}
             (semiplano superior dos polos dominantes).}}
    \label{{fig:lgr{tabela.numero}}}
\end{{figure}}""")


# ------------------------------------------------------------------ tabelas
# Mais respiro entre linhas e entre os grupos de colunas; o que é secundário (modelo
# c/ carga, ganhos ajustados) vai em cinza para o olho ir direto ao medido x teórico.
ESPACO = r"\renewcommand{\arraystretch}{1.35}\setlength{\tabcolsep}{5pt}"
GRUPO = r"@{\hspace{1.6em}}"


def _cinza(x):
    return rf"\textcolor{{black!55}}{{{x}}}"


def _tabela(rotulo, label, colunas, cabecalho, corpo, legenda, nota="", numero=None):
    """Ambiente table com legenda no fim. `rotulo` ('C', 'E1') para as que não são do
    roteiro; `numero` para as do roteiro, que mantêm o número da folha."""
    if numero is not None:
        numeracao = rf"\setcounter{{table}}{{{numero - 1}}}% mesmo número da tabela do roteiro"
    else:
        numeracao = rf"\renewcommand{{\thetable}}{{{rotulo}}}\renewcommand{{\theHtable}}{{{rotulo}}}"
    nota = f"\n    \\par\\smallskip{{\\footnotesize {nota}}}" if nota else ""
    return rf"""
\begin{{table}}[htbp]
    \centering
    {numeracao}
    {ESPACO}
    \begin{{tabular}}{{{colunas}}}
        \toprule
        {cabecalho}
        \midrule
        {corpo}
        \bottomrule
    \end{{tabular}}{nota}
    \caption{{{legenda}}}
    \label{{{label}}}
\end{{table}}"""


def tabela_metricas(tabela, resultados, pasta):
    """Métricas nas linhas; para cada caso, experimental, teórico e c/ carga."""
    n = len(resultados)
    cab1 = " & ".join(rf"\multicolumn{{3}}{{c}}{{{_rotulo(r.caso)}}}" for r in resultados)
    regras = " ".join(rf"\cmidrule(lr){{{2 + 3 * k}-{4 + 3 * k}}}" for k in range(n))
    cab2 = " & ".join([f"exp. & teór. & {_cinza('c/ carga')}"] * n)
    linhas, nota = [], ""
    for chave, nome, casas, escala in METRICAS:
        cel = [nome]
        for r in resultados:
            l = r.linha(chave)
            marca = ""
            if chave == "tr" and r.teoria.subida == "10-90":
                marca = r"\textsuperscript{a}"
                nota = r"\textsuperscript{a} sem sobressinal: $T_r$ de 10\,\% a 90\,\%; nos demais casos, de 0 a 100\,\%."
            if l is None:
                cel += ["--", "--", _cinza("--")]
            else:
                cel += [_n(l.exp, casas, escala) + marca, _n(l.teo, casas, escala),
                        _cinza(_n(l.carga, casas, escala))]
        linhas.append(" & ".join(c.replace("–", "--") for c in cel) + r" \\")
    _tex(pasta / "tab" / f"tabela{tabela.numero}.tex", _tabela(
        None, f"tab:tabela{tabela.numero}", "l" + (GRUPO + "rrr") * n,
        f"& {cab1} \\\\\n        {regras}\n        & {cab2} \\\\", "\n        ".join(linhas),
        f"{_titulo(tabela)}. Componentes medidos na Tabela~\\ref{{tab:componentes}}.", nota, tabela.numero))


def _titulo(tabela):
    """'RC com PID (CL = 1 µF, RL = 1 kΩ, C2 = 10 nF, C1 = 10 nF)' em LaTeX."""
    t = re.sub(r"\b(CL|RL|C1|C2|R2|L)\b(?= =)", lambda m: f"${VARIAVEL[Componentes.chave(m.group(1))]}$", tabela.titulo)
    return t.replace("µ", r"$\mu$").replace("Ω", r"$\Omega$")


def tabela_regime(nome, tabelas, pasta, rotulo):
    """e_ss medido, ganhos pelos componentes medidos e ganhos ajustados à forma de onda,
    com os casos agrupados pela tabela do roteiro. `tabelas`: [(Tabela, [Resultado])]."""
    blocos = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for tabela, resultados in tabelas:
            linhas = [rf"\multicolumn{{8}}{{l}}{{\textit{{Tabela~\ref{{tab:tabela{tabela.numero}}}}}}} \\"]
            for r in resultados:
                g = r.teoria.malha.controlador.ganhos()
                aj = {m.chave: m.medir(r.medida) for m in medidas.ganhos(r.teoria_carga.malha)}
                kd_aj = r"$\approx 0$" if aj["kd"] < 1e-3 * g["kd"] else _n(aj["kd"], 1, 1e6)
                ess = r.linha("ess")
                linhas.append(" & ".join([r"\quad " + _rotulo(r.caso), _n(ess.exp, 1, 100) if ess else "--",
                                          _n(g["kp"], 2), _n(g["ki"], 0), _n(g["kd"], 1, 1e6),
                                          _cinza(_n(aj["kp"], 2)), _cinza(_n(aj["ki"], 0)), _cinza(kd_aj)])
                              + r" \\")
            blocos.append("\n        ".join(linhas))
    cab = (rf"& & \multicolumn{{3}}{{c}}{{teórico}} & \multicolumn{{3}}{{c}}{{{_cinza('ajuste')}}} \\"
           "\n        \\cmidrule(lr){3-5} \\cmidrule(lr){6-8}\n        "
           r"caso & $e_{ss}$ (\%) & $K_p$ & $K_i$ (1/s) & $K_d$ ($\mu$s) & "
           + " & ".join(_cinza(x) for x in (r"$K_p$", r"$K_i$ (1/s)", r"$K_d$ ($\mu$s)")) + r" \\")
    _tex(pasta / "tab" / f"regime_{nome}.tex", _tabela(
        rotulo, f"tab:regime-{nome}", "lr" + GRUPO + "rrr" + GRUPO + "rrr", cab,
        "\n        \\addlinespace\n        ".join(blocos),
        r"Erro estacionário medido e ganhos do PID: pelos componentes da Tabela~\ref{tab:componentes} (teórico) "
        r"e ajustados à forma de onda de $V_c$ com o modelo c/ carga (ajuste)."))


def tabela_componentes(resultados, pasta):
    """Valor do roteiro e valor medido de cada componente, nas duas montagens."""
    medidos = {}
    for r in resultados:
        for k in r.caso.usados:
            medidos.setdefault((k, getattr(r.caso.comp, k)), {}).setdefault(r.caso.planta, getattr(r.comp, k))
    ordem = ("R", "R2", "C2", "C1", "R1", "L", "C")
    linhas, anterior = [], None
    for (k, nominal), por_planta in sorted(medidos.items(), key=lambda kv: (ordem.index(kv[0][0]), kv[0][1])):
        u = resultados[0].comp.UNIDADES[k]
        f = lambda x: "--" if x is None else texto_si(x, u).replace("µ", r"$\mu$").replace("Ω", r"$\Omega$")
        if anterior is not None and k != anterior:
            linhas.append(r"\addlinespace[2pt]")
        nome = f"${VARIAVEL.get(k, k)}$" if k != anterior else ""
        linhas.append(f"{nome} & {f(nominal)} & {f(por_planta.get('RC'))} & {f(por_planta.get('RLC'))} \\\\")
        anterior = k
    _tex(pasta / "tab" / "componentes.tex", _tabela(
        "C", "tab:componentes", "l" + GRUPO + "r" + GRUPO + "rr", r"& nominal & medido (RC) & medido (RLC) \\",
        "\n        ".join(linhas), "Componentes: valor do roteiro e valor medido na bancada, usado em todos os cálculos."))


# ------------------------------------------------------------------ código
def codigo(prefixo, pasta):
    """Copia os módulos do modelo para cod/ e gera tex/cod_*.tex com o trecho de cada
    função de transferência (as linhas saem do código atual, via inspect)."""
    from ..circuitos import controladores, malha, plantas
    trechos = (("pid", controladores, (controladores.ControladorPI, controladores.ControladorPID)),
               ("planta_rc", plantas, (plantas.Planta, plantas.PlantaRC)),
               ("planta_rlc", plantas, (plantas.PlantaRLC,)),
               ("malha", malha, (malha.MalhaFechada.direto, malha.MalhaFechada.ft)))
    for nome, modulo, objetos in trechos:
        arquivo = Path(modulo.__file__)
        # o listings no LuaLaTeX desloca caracteres fora do Latin-1 (₁ sai antes da letra) e a
        # IBM Plex Mono não tem '∥': na cópia citada eles viram ASCII
        texto = arquivo.read_text(encoding="utf-8").translate(ASCII_CODIGO)
        (pasta / "cod" / arquivo.name).write_text(texto, encoding="utf-8", newline="\n")
        faixas = [(ini, ini + len(linhas) - 1) for linhas, ini in map(inspect.getsourcelines, objetos)]
        ini, fim = min(a for a, _ in faixas), max(b for _, b in faixas)
        nomes = " e ".join(o.__qualname__ for o in objetos)
        _tex(pasta / "tex" / f"cod_{nome}.tex", rf"""
\lstinputlisting[
    firstline={ini}, lastline={fim}, firstnumber={ini}, float=htbp,
    caption={{\texttt{{labscope/circuitos/{arquivo.name}}}: \texttt{{{nomes}}}}},
    label={{lst:{nome}}}
]{{{prefixo}/cod/{arquivo.name}}}""")


# ------------------------------------------------------------------ tudo
def exportar(sessao, destino, prefixo=None):
    destino = Path(destino)
    prefixo = prefixo or destino.name
    for sub in ("csv", "tab", "tex", "cod"):
        (destino / sub).mkdir(parents=True, exist_ok=True)
    por_caso = carregar(sessao)
    roteiro = next(iter(por_caso.values())).roteiro
    medidas_por_tabela = []
    for tabela in roteiro.tabelas():
        resultados = [por_caso[c] for c in tabela.casos if c in por_caso]
        if not resultados:
            continue
        medidas_por_tabela.append((tabela, resultados))
        tabela_metricas(tabela, resultados, destino)
        grafico(tabela, resultados, prefixo, destino)
        lgr(tabela, resultados, prefixo, destino)
    for k, planta in enumerate(("RC", "RLC"), 1):
        tabela_regime(planta.lower(), [(t, rs) for t, rs in medidas_por_tabela if rs[0].caso.planta == planta],
                      destino, f"E{k}")
    ordem = sorted(por_caso.values(), key=lambda r: [int(x) for x in r.caso.id.split(".")])
    tabela_componentes(ordem, destino)
    codigo(prefixo, destino)
    return ordem


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("sessao")
    ap.add_argument("destino")
    ap.add_argument("--prefixo", help="pasta da atividade a partir da raiz da disciplina (padrão: nome do destino)")
    a = ap.parse_args(argv)
    for r in exportar(a.sessao, a.destino, a.prefixo):
        print(f"caso {r.caso.id}: captura #{r.numero:02d}")


if __name__ == "__main__":
    main()
