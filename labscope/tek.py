"""Capturas de osciloscópios Tektronix TBS/TDS salvas no pendrive ("Save All").

Cada captura é uma pasta ALLnnnn com um FnnnnCHk.CSV por canal. No CSV, os
metadados ficam nas colunas A-B das primeiras linhas e as amostras (tempo, valor)
nas colunas D-E de todas as linhas.

Uso como script:
  python -m labscope.tek info E:\\NEW_FOLHHH            resumo de cada captura
  python -m labscope.tek exportar E:\\NEW_FOLHHH\\ALL0000  CSVs para o ngscopeclient
"""
import argparse
import re
from dataclasses import dataclass
from functools import reduce
from pathlib import Path

import numpy as np

_CANAL = re.compile(r"F\d{4}(CH\d|MTH)\.CSV", re.IGNORECASE)
_PASTA = re.compile(r"ALL(\d{4})", re.IGNORECASE)


@dataclass
class Captura:
    pasta: Path
    t: np.ndarray      # instantes comuns a todos os canais [s]
    canais: dict       # "CH1" -> amostras
    meta: dict         # "CH1" -> metadados do CSV (Sample Interval, Vertical Scale, ...)

    def __getitem__(self, canal):
        return self.canais[canal]

    @property
    def dt(self):
        return float(np.median(np.diff(self.t)))


def ler_csv(caminho):
    """Devolve (t, v, meta). Aceita o formato original da Tek ou só as duas
    colunas de dados; linhas sem um par numérico no fim são ignoradas."""
    t, v, meta = [], [], {}
    for linha in Path(caminho).read_text(errors="replace").splitlines():
        campos = [c.strip() for c in linha.split(",")]
        if len(campos) >= 5 and campos[0]:
            try:
                meta[campos[0]] = float(campos[1])
            except ValueError:
                meta[campos[0]] = campos[1]
        # os dados são sempre os dois últimos campos não vazios da linha
        dados = [c for c in campos if c]
        try:
            ti, vi = float(dados[-2]), float(dados[-1])
        except (ValueError, IndexError):
            continue
        t.append(ti)
        v.append(vi)
    return np.array(t), np.array(v), meta


def ler_captura(pasta):
    """Lê todos os canais de uma pasta ALLnnnn, alinhados nos instantes comuns."""
    pasta = Path(pasta)
    arquivos = sorted(p for p in pasta.iterdir() if _CANAL.fullmatch(p.name))
    if not arquivos:
        raise FileNotFoundError(f"Nenhum FnnnnCHk.CSV em {pasta}")
    lidos = {_CANAL.fullmatch(p.name).group(1).upper(): ler_csv(p) for p in arquivos}
    comum = reduce(np.intersect1d, (np.round(t, 12) for t, _, _ in lidos.values()))
    canais = {n: v[np.isin(np.round(t, 12), comum)] for n, (t, v, _) in lidos.items()}
    return Captura(pasta, comum, canais, {n: m for n, (_, _, m) in lidos.items()})


def capturas(raiz):
    """{número: pasta} das capturas ALLnnnn dentro de `raiz`."""
    achadas = {}
    for p in sorted(Path(raiz).iterdir()):
        m = _PASTA.fullmatch(p.name)
        if m and p.is_dir():
            achadas[int(m.group(1))] = p
    return achadas


def ler(raiz, n):
    """Lê a captura número `n` (pasta ALLnnnn) de `raiz`."""
    return ler_captura(Path(raiz) / f"ALL{n:04d}")


def exportar_ngscope(pasta, destino=None):
    """Grava os CSVs no formato que o ngscopeclient importa (cabeçalho
    "Time,CH1,...", tempo em segundos na 1ª coluna): um por canal e um combinado.
    Devolve a pasta de saída."""
    pasta = Path(pasta)
    destino = Path(destino) if destino else pasta / "ngscope"
    destino.mkdir(exist_ok=True)
    for p in sorted(p for p in pasta.iterdir() if _CANAL.fullmatch(p.name)):
        nome = _CANAL.fullmatch(p.name).group(1).upper()
        t, v, _ = ler_csv(p)
        _gravar(destino / f"{nome}.csv", [nome], t, [v])
    cap = ler_captura(pasta)
    nomes = sorted(cap.canais)
    _gravar(destino / "combinado.csv", nomes, cap.t, [cap[n] for n in nomes])
    return destino


def _gravar(caminho, nomes, t, colunas):
    with caminho.open("w", newline="\n") as fh:
        fh.write("Time," + ",".join(nomes) + "\n")
        for linha in zip(t, *colunas):
            fh.write(f"{linha[0]:.12g}," + ",".join(f"{x:g}" for x in linha[1:]) + "\n")


def _info(raiz):
    from . import sinais
    for n, pasta in capturas(raiz).items():
        cap = ler_captura(pasta)
        partes = [f"ALL{n:04d}", f"{len(cap.t)} pts", f"dt={cap.dt * 1e6:g} us"]
        for nome in sorted(cap.canais):
            v = cap[nome]
            partes.append(f"{nome}: {v.min():+.3f}..{v.max():+.3f} V "
                          f"({cap.meta[nome].get('Vertical Scale', float('nan')):g} V/div)")
        try:
            q = sinais.quadrada(cap.t, cap[sorted(cap.canais)[0]])
            partes.append(f"{q.frequencia:.1f} Hz")
        except ValueError:
            pass
        print("  ".join(partes))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("comando", choices=["info", "exportar"])
    ap.add_argument("pasta")
    args = ap.parse_args()
    if args.comando == "info":
        _info(args.pasta)
    else:
        print(exportar_ngscope(args.pasta))
