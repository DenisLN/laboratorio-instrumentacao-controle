"""Converte CSVs de osciloscópios Tektronix TBS/TDS (pasta ALLxxxx) para o formato
que o ngscopeclient importa: cabeçalho "Time,CH1,CH2,...", tempo em segundos na
1ª coluna, sem espaços e sem vírgula sobrando no fim da linha.

Uso:  python tek2ngscope.py D:\\NEW_FOLHHH\\ALL0000
Gera uma subpasta "ngscope" com um CSV por canal e um CSV combinado.
"""
import re
import sys
from pathlib import Path


def read_tek_csv(path):
    """Devolve lista de (tempo, valor). Aceita o formato original da Tek
    (metadados nas colunas A-C, dados nas D-E) ou só as duas colunas de dados."""
    samples = []
    for line in path.read_text(errors="replace").splitlines():
        fields = [f.strip() for f in line.split(",")]
        # Os dados são sempre os dois últimos campos não vazios da linha
        data = [f for f in fields if f != ""]
        if len(data) < 2:
            continue
        try:
            t, v = float(data[-2]), float(data[-1])
        except ValueError:
            continue
        samples.append((t, v))
    return samples


def main(folder):
    folder = Path(folder)
    files = sorted(p for p in folder.iterdir()
                   if re.fullmatch(r"F\d{4}CH\d\.CSV", p.name, re.IGNORECASE))
    if not files:
        sys.exit(f"Nenhum arquivo FxxxxCHn.CSV em {folder}")

    out = folder / "ngscope"
    out.mkdir(exist_ok=True)
    channels = {}
    for f in files:
        ch = re.search(r"CH\d", f.name, re.IGNORECASE).group(0).upper()
        samples = read_tek_csv(f)
        channels[ch] = dict(samples)
        dest = out / f"{ch}.csv"
        with dest.open("w", newline="\n") as fh:
            fh.write(f"Time,{ch}\n")
            for t, v in samples:
                fh.write(f"{t:.12g},{v:g}\n")
        print(f"{f.name}: {len(samples)} amostras -> {dest}")

    # Arquivo combinado só com os instantes presentes em todos os canais
    names = sorted(channels)
    common = sorted(set.intersection(*(set(c) for c in channels.values())))
    dest = out / "combinado.csv"
    with dest.open("w", newline="\n") as fh:
        fh.write("Time," + ",".join(names) + "\n")
        for t in common:
            fh.write(f"{t:.12g}," + ",".join(f"{channels[n][t]:g}" for n in names) + "\n")
    print(f"combinado: {len(common)} amostras comuns -> {dest}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
