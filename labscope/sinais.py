"""Operações sobre formas de onda amostradas: patamares, bordas (trigger), onda
quadrada de referência, recorte por meio período e suavização."""
from dataclasses import dataclass

import numpy as np


def niveis(v):
    """Patamares (baixo, alto) de um sinal de dois níveis."""
    v = np.asarray(v, float)
    meio = np.mean(np.percentile(v, [5, 95]))
    return float(np.median(v[v < meio])), float(np.median(v[v >= meio]))


def lsb(v):
    """Passo de quantização: menor diferença entre valores distintos de `v`."""
    return float(np.min(np.diff(np.unique(v))))


def bordas(v, nivel=None, histerese=None):
    """Índices das transições de `v` pelo `nivel` e, para cada uma, se é de subida.

    Funciona como o trigger do osciloscópio: a transição só vale quando o sinal
    sai da faixa nivel ± histerese, então ruído em cima do nível não gera bordas
    falsas. O índice devolvido é o da 1ª amostra já do lado novo do nível.
    Padrões: nível no meio dos patamares e histerese de 10 % da excursão.
    """
    v = np.asarray(v, float)
    baixo, alto = niveis(v)
    if nivel is None:
        nivel = (baixo + alto) / 2
    if histerese is None:
        histerese = 0.1 * (alto - baixo)
    marca = np.where(v > nivel + histerese, 1, np.where(v < nivel - histerese, -1, 0))
    definidos = np.flatnonzero(marca)
    if len(definidos) == 0:
        return np.array([], int), np.array([], bool)
    # dentro da faixa de histerese vale o último estado definido
    ultimo = np.maximum.accumulate(np.where(marca != 0, np.arange(len(v)), -1))
    ultimo[ultimo < 0] = definidos[0]
    estado = marca[ultimo]
    lado = v > nivel
    idx = []
    for k in np.flatnonzero(estado[1:] != estado[:-1]) + 1:
        while k > 0 and lado[k - 1] == lado[k]:
            k -= 1
        idx.append(k)
    idx = np.array(idx, int)
    return idx, lado[idx]


@dataclass
class Quadrada:
    """Onda quadrada ideal; chamar com um vetor de tempo devolve as amostras."""
    baixo: float
    alto: float
    periodo: float
    t_subida: float    # instante de uma borda de subida
    duty: float = 0.5

    @property
    def frequencia(self):
        return 1 / self.periodo

    @property
    def amplitude(self):
        return (self.alto - self.baixo) / 2

    def __call__(self, t):
        fase = (np.asarray(t, float) - self.t_subida) % self.periodo
        return np.where(fase < self.duty * self.periodo, self.alto, self.baixo)


def quadrada(t, v, duty=0.5, periodo=None, **kw):
    """Reconstrói a onda quadrada ideal (patamares, período e fase) de um canal.
    Com uma borda só no registro (janela curta em torno do trigger), o período
    não é observável e tem de vir em `periodo`. `kw` vai para `bordas`."""
    idx, sobe = bordas(v, **kw)
    if len(idx) < 2:
        if periodo is None or len(idx) == 0:
            raise ValueError("menos de duas bordas no sinal")
        tb = float(np.asarray(t, float)[idx[0]])
        baixo, alto = niveis(v)
        return Quadrada(baixo, alto, float(periodo), tb if sobe[0] else tb - duty * periodo, duty)
    tb = np.asarray(t, float)[idx]
    subidas, descidas = tb[sobe], tb[~sobe]
    if len(subidas) > 1:
        periodo = np.median(np.diff(subidas))
    elif len(descidas) > 1:
        periodo = np.median(np.diff(descidas))
    else:
        periodo = 2 * np.median(np.diff(tb))
    t_subida = subidas[0] if len(subidas) else descidas[0] - duty * periodo
    baixo, alto = niveis(v)
    return Quadrada(baixo, alto, float(periodo), float(t_subida), duty)


def meios_periodos(v, **kw):
    """(i, j, sinal) de cada meio período completo de `v`: da borda `i` até a
    borda seguinte `j`, com sinal +1 para subida e -1 para descida."""
    idx, sobe = bordas(v, **kw)
    return [(int(i), int(j), 1 if s else -1) for i, j, s in zip(idx[:-1], idx[1:], sobe[:-1])]


def trechos(v, **kw):
    """Trechos (i, j, sinal) em que dá para medir uma resposta ao degrau: os
    meios períodos completos ou, se o registro tem uma borda só, dela até o fim."""
    completos = meios_periodos(v, **kw)
    if completos:
        return completos
    idx, sobe = bordas(v, **kw)
    return [(int(idx[0]), len(v), 1 if sobe[0] else -1)] if len(idx) else []


def janela_subida(t, v, antes=1e-3, **kw):
    """(i0, i, j) da 1ª borda de subida com `antes` segundos de sinal à esquerda:
    início da janela, borda e borda seguinte (ou fim do registro)."""
    idx, sobe = bordas(v, **kw)
    n = int(round(antes / np.median(np.diff(t))))
    for k, (i, s) in enumerate(zip(idx, sobe)):
        if s and i >= n:
            j = idx[k + 1] if k + 1 < len(idx) else len(v) - 1
            return int(i - n), int(i), int(j)
    raise ValueError("nenhuma borda de subida com a folga pedida")


def media_movel(y, dt, janela):
    """Média móvel de `janela` segundos (reduz o ruído de quantização)."""
    k = max(1, int(round(janela / dt)))
    return np.convolve(y, np.ones(k) / k, mode="same") if k > 1 else np.asarray(y, float)
