"""Tabelas em Markdown com números no formato pt-BR."""
import math


def num(x, casas=2, unidade="", escala=1.0):
    """Número com vírgula decimal; NaN/None viram travessão."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "–"
    s = f"{x * escala:.{casas}f}".replace(".", ",").replace("-", "−")
    return f"{s} {unidade}" if unidade else s


def ms(x, casas=2):
    return num(x, casas, "ms", 1e3)


def pct(x, casas=1):
    return num(x, casas, "%", 100)


def tabela(cabecalho, linhas):
    """Tabela Markdown a partir do cabeçalho e de uma lista de linhas."""
    out = ["| " + " | ".join(cabecalho) + " |", "|" + "---|" * len(cabecalho)]
    out += ["| " + " | ".join(str(c) for c in l) + " |" for l in linhas]
    return "\n".join(out)
