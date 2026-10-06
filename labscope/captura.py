"""Uma aquisição de osciloscópio, venha ela do USB, do pendrive ou de uma simulação."""
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass
class Captura:
    t: np.ndarray                               # instantes comuns a todos os canais [s]
    canais: dict                                # "CH1" -> amostras [V]
    meta: dict = field(default_factory=dict)    # "CH1" -> metadados do canal; "geral" -> do instrumento
    origem: str = ""

    def __getitem__(self, canal):
        return self.canais[canal]

    @property
    def dt(self):
        return float(np.median(np.diff(self.t)))

    def com_sonda(self, sonda):
        """Mesma captura como se a atenuação de sonda configurada no osciloscópio
        fosse `sonda` (ex.: canal em 10X com ponta 1X → com_sonda(1) divide por 10).
        Canais sem 'Probe Atten' nos metadados ficam como estão."""
        canais, meta = {}, {k: dict(v) if isinstance(v, dict) else v for k, v in self.meta.items()}
        for canal, v in self.canais.items():
            configurada = meta.get(canal, {}).get("Probe Atten")
            fator = sonda / configurada if configurada else 1.0
            canais[canal] = v * fator
            if configurada:
                meta[canal].update({"Probe Atten": sonda, "Probe Atten no osciloscópio": configurada})
                if "LSB" in meta[canal]:
                    meta[canal]["LSB"] *= fator
        return Captura(self.t, canais, meta, self.origem)

    def salvar(self, pasta, nome="captura"):
        """Grava `nome`.npz (tudo) e `nome`.csv (Time,CH1,CH2 — abre no ngscopeclient e no Excel)."""
        pasta = Path(pasta)
        pasta.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(pasta / f"{nome}.npz", t=self.t, **self.canais,
                            meta=json.dumps(self.meta, default=str), origem=self.origem)
        nomes = sorted(self.canais)
        with (pasta / f"{nome}.csv").open("w", newline="\n") as fh:
            fh.write("Time," + ",".join(nomes) + "\n")
            for linha in zip(self.t, *(self.canais[n] for n in nomes)):
                fh.write(f"{linha[0]:.12g}," + ",".join(f"{x:g}" for x in linha[1:]) + "\n")
        return pasta / f"{nome}.npz"

    @classmethod
    def carregar(cls, caminho):
        with np.load(caminho, allow_pickle=False) as z:
            canais = {k: z[k] for k in z.files if k not in ("t", "meta", "origem")}
            return cls(z["t"], canais, json.loads(str(z["meta"])), str(z["origem"]))
