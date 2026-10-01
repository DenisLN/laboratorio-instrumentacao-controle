"""Preenche o roteiro do Experimento 6 (.docx) com as tabelas, os cálculos e as
figuras, a partir de tabelas.json e figs/*.png (gerados por experimento6.py).

Uso:  python preencher_roteiro.py modelo_em_branco.docx saida.docx
"""
import json
import math
import re
import struct
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from labscope import relatorio as Rl

AQUI = Path(__file__).parent
FONTE = '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>'
ALUNO = ("Denis Natã Henden Loyola", "GRR20231589")
NOTA = ("indutor medido de 68 mH (valor usado nos cálculos teóricos); capacitor usado de 1 µF que, na verdade, "
        "pela tolerância ou má construção, se comportou como ≈ 4,7 µF (ajuste: 4,6 µF).")


# ---------------------------------------------------------------- texto
def run(texto, sz=22, b=False, i=False, sub=False):
    rpr = FONTE + ("<w:b/>" if b else "") + ("<w:i/>" if i else "") + f'<w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/>'
    rpr += '<w:vertAlign w:val="subscript"/>' if sub else ""
    return f'<w:r><w:rPr>{rpr}</w:rPr><w:t xml:space="preserve">{escape(texto)}</w:t></w:r>'


def rico(texto, sz=22, b=False):
    """Runs a partir de texto com `_{...}` para subscrito e `**...**` para negrito."""
    out = []
    for k, trecho in enumerate(texto.split("**")):
        for j, parte in enumerate(re.split(r"_\{(.*?)\}", trecho)):
            if parte:
                out.append(run(parte, sz, b or k % 2 == 1, sub=j % 2 == 1))
    return "".join(out)


def par(conteudo, jc="both", antes=60, depois=60, manter=False):
    return (f'<w:p><w:pPr>{"<w:keepNext/>" if manter else ""}<w:spacing w:before="{antes}" w:after="{depois}"/>'
            f'<w:jc w:val="{jc}"/></w:pPr>{conteudo}</w:p>')


def texto(t, **kw):
    return par(rico(t), **kw)


def tabela(cabecalho, linhas, larguras, sz=20):
    def celula(t, w, b):
        return (f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/><w:vAlign w:val="center"/></w:tcPr>'
                + par(rico(t, sz, b), "center", 20, 20) + "</w:tc>")
    grade = "".join(f'<w:gridCol w:w="{w}"/>' for w in larguras)
    corpo = "".join("<w:tr>" + "".join(celula(t, w, k == 0) for t, w in zip(l, larguras)) + "</w:tr>"
                    for k, l in enumerate([cabecalho] + linhas))
    return ('<w:tbl><w:tblPr><w:tblStyle w:val="Tabelacomgrade"/><w:tblW w:w="0" w:type="auto"/><w:jc w:val="center"/>'
            f'<w:tblLayout w:type="fixed"/></w:tblPr><w:tblGrid>{grade}</w:tblGrid>{corpo}</w:tbl>' + par("", antes=0, depois=0))


# ---------------------------------------------------------------- equações (OMML)
def _mr(t, normal=False):
    estilo = '<m:rPr><m:sty m:val="p"/></m:rPr>' if normal else ""
    return (f'<m:r>{estilo}<w:rPr><w:rFonts w:ascii="Cambria Math" w:hAnsi="Cambria Math"/></w:rPr>'
            f'<m:t xml:space="preserve">{escape(t)}</m:t></m:r>')


def _grupo(s, i):
    """Conteúdo do grupo {...} que começa em s[i] e o índice logo depois dele."""
    nivel, j = 0, i
    while True:
        nivel += (s[j] == "{") - (s[j] == "}")
        j += 1
        if nivel == 0:
            return s[i + 1:j - 1], j


def tex(s):
    """Subconjunto de LaTeX para OMML: \\frac{}{}, \\sqrt{}, \\text{}, _{} e ^{}."""
    out, buf, i = [], "", 0

    def descarrega():
        nonlocal buf
        if buf:
            out.append(_mr(buf))
            buf = ""

    while i < len(s):
        if s.startswith("\\frac", i):
            descarrega()
            a, i = _grupo(s, i + 5)
            b, i = _grupo(s, i)
            out.append(f"<m:f><m:num>{tex(a)}</m:num><m:den>{tex(b)}</m:den></m:f>")
        elif s.startswith("\\sqrt", i):
            descarrega()
            a, i = _grupo(s, i + 5)
            out.append(f'<m:rad><m:radPr><m:degHide m:val="1"/></m:radPr><m:deg/><m:e>{tex(a)}</m:e></m:rad>')
        elif s.startswith("\\text", i):
            descarrega()
            a, i = _grupo(s, i + 5)
            out.append(_mr(a, normal=True))
        elif s[i] in "_^":
            marca, (a, j) = ("sSub", "sub") if s[i] == "_" else ("sSup", "sup"), _grupo(s, i + 1)
            if buf:                       # a base é o último caractere pendente
                base, buf = _mr(buf[-1]), buf[:-1]
                descarrega()
            else:                         # ou o elemento anterior (ex.: ω_{n}^{2})
                base = out.pop()
            out.append(f"<m:{marca[0]}><m:e>{base}</m:e><m:{marca[1]}>{tex(a)}</m:{marca[1]}></m:{marca[0]}>")
            i = j
        else:
            buf += s[i]
            i += 1
    descarrega()
    return "".join(out)


def eq(*formulas):
    """Parágrafo centrado com as fórmulas lado a lado."""
    sep = run("        ")
    return par(sep.join(f"<m:oMath>{tex(f)}</m:oMath>" for f in formulas), "center", 80, 80)


# ---------------------------------------------------------------- figuras
class Figuras:
    def __init__(self, primeiro_rid, primeiro_num):
        self.rid, self.num, self.itens = primeiro_rid, primeiro_num, []

    def bloco(self, arquivo, legenda, largura_pol):
        dados = Path(arquivo).read_bytes()
        w, h = struct.unpack(">II", dados[16:24])          # IHDR do PNG
        cx = int(largura_pol * 914400)
        cy = int(cx * h / w)
        rid, nome = f"rId{self.rid}", f"fig_exp6_{self.num}.png"
        self.itens.append((rid, nome, dados))
        desenho = (
            f'<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/>'
            f'<wp:docPr id="{100 + self.num}" name="Figura {self.num}"/>'
            '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
            '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            f'<pic:nvPicPr><pic:cNvPr id="{100 + self.num}" name="{nome}"/><pic:cNvPicPr/></pic:nvPicPr>'
            f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic>'
            '</wp:inline></w:drawing></w:r>')
        xml = par(desenho, "center", 120, 0, manter=True) + par(rico(f"Figura {self.num} – {legenda}", 20), "center", 0, 120)
        self.rid += 1
        self.num += 1
        return xml


# ---------------------------------------------------------------- conteúdo
def r2(c):
    return f"R_{{2}} = {c['R2'] / 1e3:g} kΩ"


def ts_exp(c):
    ts = c["exp"]["ts"]
    return f"> {c['exp']['semi'] * 1e3:.0f} ms" if math.isnan(ts) else Rl.ms(ts, 1)


def polos(c):
    def um(q):
        return Rl.num(q[0], 0) if abs(q[1]) < 1e-6 else f"{Rl.num(q[0], 0)} ± j{Rl.num(abs(q[1]), 0)}"
    return "; ".join(dict.fromkeys(um(q) for q in sorted(c["polos"], key=lambda q: q[0])))


def linha_tempo(c):
    """Linha das Tabelas 2, 4 e 6: Tr, Tp, Mp, Ts e Vc (experimental, teórico)."""
    e, t = c["exp"], c["teo"]
    return [Rl.ms(e["tr"]), Rl.ms(t["tr"]), Rl.ms(e["tp"]), Rl.ms(t["tp"]), Rl.pct(e["mp"]), Rl.pct(t["mp"]),
            ts_exp(c), Rl.ms(t["ts"], 1), Rl.num(e["vc"], 3, "V"), Rl.num(t["vc"], 3, "V")]


def linha_freq(c):
    """Linha das Tabelas 3, 5 e 7: ζ, ωn e ωd (experimental, teórico)."""
    e = c["exp"]
    return [Rl.num(e["zeta"], 3), Rl.num(c["zeta"], 3), Rl.num(e["wn"], 0, "rad/s"), Rl.num(c["wn"], 0, "rad/s"),
            Rl.num(e["wd"], 0, "rad/s"), Rl.num(c["wd"], 0, "rad/s")]


def linha_tab1(c):
    e, t = c["exp"], c["teo"]
    return [Rl.ms(e["tau"]), Rl.ms(t["tau"]), Rl.ms(e["tr"]), Rl.ms(t["tr"]), ts_exp(c), Rl.ms(t["ts"]),
            Rl.num(e["vc"], 3, "V"), Rl.num(t["vc"], 3, "V")]


def tabela_regime(casos):
    return tabela(["", "e_{ss} teórico", "e_{ss} experimental", "K_{p} teórico", "K_{p} experimental"],
                  [[r2(c), Rl.pct(c["teo"]["ess"]), Rl.pct(c["exp"]["ess"]), Rl.num(c["kp"]), Rl.num(c["exp"]["k_dc"])]
                   for c in casos], [1500, 1500, 1800, 1500, 1800])


def tabela_ganhos(casos):
    return tabela(["", "e_{ss} exp.", "K_{p} teórico", "K_{p} exp.", "K_{i} teórico", "K_{i} exp.", "Polos teóricos (s⁻¹)"],
                  [[r2(c), Rl.pct(c["exp"]["ess"]) + ("*" if math.isnan(c["exp"]["ts"]) else ""), Rl.num(c["kp"]),
                    Rl.num(c["exp"]["kp_id"]), "10 000 s⁻¹", Rl.num(c["exp"]["ki_id"], 0, "s⁻¹"), polos(c)]
                   for c in casos], [1300, 1000, 1100, 1000, 1200, 1200, 2700])


REGIME = [texto("**Erro estacionário e K_{p}** (A = 0,492 V é a amplitude medida da entrada):", manter=True),
          eq("e_{ss} = \\frac{1}{1 + K_{p}} \\text{ (teórico)}", "e_{ss} = \\frac{A − V_{c}}{A} \\text{ (experimental)}",
             "K_{p} = \\frac{V_{c}}{A − V_{c}} \\text{ (experimental)}")]
PI_GANHOS = [texto("**Erro estacionário, K_{p} e K_{i}** (e_{ss} = (A − V_{c})/A; K_{p} e K_{i} experimentais pelo "
                   "ajuste do modelo às formas de onda):", manter=True)]
OSCILANDO = texto("* Ainda oscilando no fim do semiperíodo.")
EXPERIMENTAL = eq("ζ = \\frac{−\\text{ln }M_{p}}{\\sqrt{π^{2} + \\text{ln}^{2}M_{p}}}", "ω_{d} = \\frac{π}{T_{p}}",
                  "ω_{n} = \\frac{ω_{d}}{\\sqrt{1 − ζ^{2}}}")


def calculos(parte, casos, figs):
    """Bloco de cálculos e figuras inserido depois do enunciado de cada parte."""
    b = [texto("**Cálculos**", antes=160, manter=True)]
    if parte == 3:
        b += [texto("**Função de transferência** (K_{p} = R_{2}/R, R = 10 kΩ, R_{1}C = 1 ms):", manter=True),
              eq("\\frac{V_{c}(s)}{E_{1}(s)} = \\frac{K_{p}}{R_{1}Cs + 1 + K_{p}} = \\frac{K_{p}/(1 + K_{p})}{τs + 1}",
                 "τ = \\frac{R_{1}C}{1 + K_{p}}"),
              eq("T_{r} = 2,2τ", "T_{s} = 4τ", "V_{c} = 0,5·\\frac{K_{p}}{1 + K_{p}}", "\\text{polo: }s = −\\frac{1 + K_{p}}{R_{1}C}"),
              texto("Exemplo (R_{2} = 5 kΩ, K_{p} = 0,5): τ = 1 ms/1,5 = 0,67 ms; T_{r} = 1,47 ms; T_{s} = 2,67 ms; "
                    "V_{c} = 0,5·0,5/1,5 = 0,167 V."),
              *REGIME, tabela_regime(casos),
              tabela(["", "Polo teórico", "Polo experimental (−1/τ)"],
                     [[r2(c), Rl.num(c["polos"][0][0], 0, "s⁻¹"), Rl.num(-1 / c["exp"]["tau"], 0, "s⁻¹")] for c in casos],
                     [1500, 2000, 2600])]
    elif parte == 4:
        b += [texto("**Função de transferência** (L = 68 mH):", manter=True),
              eq("\\frac{V_{c}(s)}{E_{1}(s)} = \\frac{K_{p}}{LCs^{2} + R_{1}Cs + 1 + K_{p}} = "
                 "\\frac{Kω_{n}^{2}}{s^{2} + 2ζω_{n}s + ω_{n}^{2}}"),
              eq("ω_{n} = \\sqrt{\\frac{1 + K_{p}}{LC}}", "ζ = \\frac{R_{1}}{2}\\sqrt{\\frac{C}{L(1 + K_{p})}}",
                 "ω_{d} = ω_{n}\\sqrt{1 − ζ^{2}}", "K = \\frac{K_{p}}{1 + K_{p}}"),
              eq("T_{r} = \\frac{π − \\text{arccos }ζ}{ω_{d}}", "T_{p} = \\frac{π}{ω_{d}}",
                 "M_{p} = e^{−ζπ/\\sqrt{1 − ζ^{2}}}", "T_{s} = \\frac{4}{ζω_{n}} = \\frac{8L}{R_{1}}"),
              texto("Exemplo (R_{2} = 5 kΩ): ω_{n} = √(1,5/(68·10⁻⁹)) = 4697 rad/s; ζ = 50·√(10⁻⁶/(0,068·1,5)) = 0,157; "
                    "ω_{d} = 4639 rad/s; T_{p} = 0,68 ms; M_{p} = 60,8 %; T_{s} = 8·0,068/100 = 5,4 ms."),
              texto("**Valores experimentais da Tabela 3**, a partir de M_{p} e T_{p} medidos:", manter=True), EXPERIMENTAL,
              *REGIME, tabela_regime(casos),
              texto("**Funções de transferência obtidas dos gráficos** (K = V_{c}/A, com ζ e ω_{n} da Tabela 3):", manter=True),
              tabela(["", "Experimental", "Teórica"],
                     [[r2(c),
                       f"{_e6(c['exp']['vc'] / c['amp'] * c['exp']['wn'] ** 2)} / (s² + "
                       f"{Rl.num(2 * c['exp']['zeta'] * c['exp']['wn'], 0)} s + {_e6(c['exp']['wn'] ** 2)})",
                       f"{_e6(c['num'][0] / c['den'][0])} / (s² + {Rl.num(c['den'][1] / c['den'][0], 0)} s + "
                       f"{_e6(c['den'][2] / c['den'][0])})"] for c in casos], [1300, 4000, 4000])]
    elif parte == 5:
        b += [texto("**Função de transferência** (controlador G_{c} = K_{p} + K_{i}/s, com K_{i} = 1/(R·C_{f}) = 10⁴ s⁻¹):",
                    manter=True),
              eq("\\frac{V_{c}(s)}{E_{1}(s)} = \\frac{K_{p}s + K_{i}}{R_{1}Cs^{2} + (1 + K_{p})s + K_{i}}"),
              eq("ω_{n} = \\sqrt{\\frac{K_{i}}{R_{1}C}} = 3162\\text{ rad/s}", "ζ = \\frac{1 + K_{p}}{2\\sqrt{K_{i}R_{1}C}}",
                 "\\text{zero: }s = −\\frac{K_{i}}{K_{p}}"),
              texto("Exemplo (R_{2} = 5 kΩ): ζ = 1,5/(2·3,162) = 0,237; ω_{d} = 3162·√(1 − 0,237²) = 3072 rad/s."),
              texto("Por causa do zero, T_{r}, T_{p}, M_{p} e T_{s} teóricos vêm da resposta ao degrau exata da função de "
                    "transferência. Os valores experimentais da Tabela 5 usam as mesmas fórmulas da Tabela 3."),
              texto("A terceira linha das Tabelas 4 e 5 foi medida com R_{2} = 20 kΩ (o roteiro pede 40 kΩ)."),
              *PI_GANHOS, tabela_ganhos(casos), OSCILANDO]
    else:
        b += [texto("**Função de transferência** (L = 68 mH):", manter=True),
              eq("\\frac{V_{c}(s)}{E_{1}(s)} = \\frac{K_{p}s + K_{i}}{LCs^{3} + R_{1}Cs^{2} + (1 + K_{p})s + K_{i}}"),
              texto("**Estabilidade (Routh):**", manter=True),
              eq("R_{1}C(1 + K_{p}) > LC·K_{i}", "1 + K_{p} > \\frac{L·K_{i}}{R_{1}} = 0,68",
                 "\\text{estável para todo }K_{p} ≥ 0"),
              texto("ζ, ω_{n} e ω_{d} são os do par de polos dominante. T_{r}, T_{p}, M_{p} e T_{s} teóricos vêm da resposta "
                    "ao degrau exata. R_{2} = 5 kΩ e 10 kΩ foram medidos em 20 Hz, porque em 50 Hz a resposta não acomodava."),
              *PI_GANHOS, tabela_ganhos(casos), OSCILANDO]
    nomes = {3: "RC com controlador P", 4: "RLC com controlador P", 5: "RC com controlador PI", 6: "RLC com controlador PI"}
    b += [figs.bloco(AQUI / f"figs/resposta_parte{parte}.png",
                     f"{nomes[parte]}: entrada e saídas. Acima, experimental e teórico; abaixo, experimental e modelo "
                     "com o capacitor efetivo.", 4.7),
          figs.bloco(AQUI / f"figs/lgr_parte{parte}.png", f"{nomes[parte]}: lugar das raízes.", 5.6)]
    return "".join(b)


def _e6(x):
    return Rl.num(x / 1e6, 2) + "·10⁶"


# ---------------------------------------------------------------- edição do docx
def preencher_tabela(tbl, linhas, sz):
    """Escreve `linhas` nas células vazias das três últimas linhas da tabela."""
    trs = list(re.finditer(r"<w:tr[ >].*?</w:tr>", tbl, flags=re.S))
    for tr, valores in reversed(list(zip(trs[-3:], linhas))):
        celulas = re.findall(r"<w:tc>.*?</w:tc>", tr.group(0), flags=re.S)
        novas = [celulas[0]]
        for cel, valor in zip(celulas[1:], valores, strict=True):
            cel = cel.replace('<w:jc w:val="both"/>', '<w:jc w:val="center"/>')
            if "<w:vAlign" not in cel:
                cel = cel.replace("</w:tcPr>", '<w:vAlign w:val="center"/></w:tcPr>', 1)
            novas.append(cel.replace("</w:p></w:tc>", run(valor, sz) + "</w:p></w:tc>"))
        linha = tr.group(0)[:tr.group(0).find("<w:tc>")] + "".join(novas) + "</w:tr>"
        tbl = tbl[:tr.start()] + linha + tbl[tr.end():]
    return tbl


def montar(modelo, saida, tab):
    with zipfile.ZipFile(modelo) as z:
        arquivos = {i.filename: z.read(i.filename) for i in z.infolist()}
    x = arquivos["word/document.xml"].decode("utf-8")
    rels = arquivos["word/_rels/document.xml.rels"].decode("utf-8")
    parte = lambda p: [c for c in tab["casos"] if c["parte"] == p]
    figs = Figuras(1 + max(int(n) for n in re.findall(r'Id="rId(\d+)"', rels)), 5)

    # tabelas do roteiro (a primeira é a de identificação dos alunos)
    conteudo = [(3, linha_tab1, 18), (4, linha_tempo, 16), (4, linha_freq, 20), (5, linha_tempo, 16),
                (5, linha_freq, 20), (6, linha_tempo, 16), (6, linha_freq, 20)]
    tabelas = list(re.finditer(r"<w:tbl>.*?</w:tbl>", x, flags=re.S))
    for t, (p, linha, sz) in reversed(list(zip(tabelas[1:], conteudo, strict=True))):
        nova = preencher_tabela(t.group(0), [linha(c) for c in parte(p)], sz)
        if p == 5:      # a 3ª linha foi medida com 20 kΩ
            antes = nova
            nova = nova.replace(" = 4</w:t>", " = 2</w:t>")
            assert nova != antes, "rótulo de 40 kΩ não encontrado"
        x = x[:t.start()] + nova + x[t.end():]

    # blocos de cálculo: depois de cada enunciado "Determine o erro estacionário..."
    enunciados = [m.start() for m in re.finditer("Determine o erro estacion", x)]
    blocos = [calculos(p, parte(p), figs) for p in (3, 4, 5, 6)]
    for pos, bloco in reversed(list(zip(enunciados, blocos, strict=True))):
        fim = x.find("</w:p>", pos) + len("</w:p>")
        x = x[:fim] + bloco + x[fim:]

    # identificação do aluno (1ª linha vazia da 1ª tabela) e nota no topo, antes dela
    t = tabelas[0]
    linha = list(re.finditer(r"<w:tr[ >].*?</w:tr>", t.group(0), flags=re.S))[1]
    nova = linha.group(0)
    for valor in ALUNO:
        arial = ('<w:r><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/><w:sz w:val="20"/>'
                 f'<w:szCs w:val="20"/></w:rPr><w:t>{escape(valor)}</w:t></w:r>')
        nova = nova.replace("</w:pPr></w:p>", "</w:pPr>" + arial + "</w:p>", 1)
    nota = par(run("Importante: ", 20, b=True) + run(NOTA, 20), antes=0, depois=120)
    x = (x[:t.start()] + nota + t.group(0)[:linha.start()] + nova + t.group(0)[linha.end():] + x[t.end():])

    novas_rels = "".join(
        f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
        f'Target="media/{nome}"/>' for rid, nome, _ in figs.itens)
    arquivos["word/document.xml"] = x.encode("utf-8")
    arquivos["word/_rels/document.xml.rels"] = rels.replace("</Relationships>", novas_rels + "</Relationships>").encode("utf-8")
    for _, nome, dados in figs.itens:
        arquivos[f"word/media/{nome}"] = dados
    with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as z:
        for nome, dados in arquivos.items():
            z.writestr(nome, dados)


if __name__ == "__main__":
    montar(sys.argv[1], sys.argv[2], json.load(open(AQUI / "tabelas.json")))
