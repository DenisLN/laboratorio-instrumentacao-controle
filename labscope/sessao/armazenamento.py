"""Onde a sessão guarda o que mede: uma pasta por sessão, uma subpasta por captura."""
import datetime as dt
import json
from pathlib import Path


class PastaSessao:
    """sessoes/sessao_<data>_<hora>/NN_e<exp>_c<caso>/{captura.npz, captura.csv, metricas.json, painel.png}

    A pasta só é criada quando algo vai ser gravado nela."""

    def __init__(self, raiz="sessoes"):
        self.caminho = Path(raiz) / f"sessao_{dt.datetime.now():%Y-%m-%d_%H-%M-%S}"

    def garantir(self):
        self.caminho.mkdir(parents=True, exist_ok=True)
        return self.caminho

    @property
    def transcricao(self):
        return self.garantir() / "scpi_transcricao.log"

    def pasta_captura(self, res):
        """Pasta da captura `res.numero`. Se ela já existe com outro caso no nome
        (a captura foi reanalisada como outro caso), é renomeada."""
        nome = f"{res.numero:02d}_e{res.roteiro.numero}_c{res.caso.id}"
        destino = self.garantir() / nome
        for antiga in self.caminho.glob(f"{res.numero:02d}_e*"):
            if antiga != destino and antiga.is_dir():
                antiga.rename(destino)
        destino.mkdir(exist_ok=True)
        return destino

    def salvar(self, res):
        """Grava a captura e as métricas; devolve a pasta. Se a pasta da captura
        não aceitar escrita (aberta em outro programa, apagada no meio da sessão),
        grava numa pasta nova ao lado, com o horário no nome."""
        try:
            return self._gravar(self.pasta_captura(res), res)
        except OSError:
            alternativa = self.garantir() / f"{res.numero:02d}_e{res.roteiro.numero}_c{res.caso.id}_{dt.datetime.now():%H%M%S}"
            alternativa.mkdir()
            return self._gravar(alternativa, res)

    @staticmethod
    def _gravar(pasta, res):
        res.captura.salvar(pasta)
        (pasta / "metricas.json").write_text(json.dumps(res.como_dict(), indent=1, ensure_ascii=False),
                                             encoding="utf-8")
        (pasta / "metricas.txt").write_text(res.texto() + "\n", encoding="utf-8")
        return pasta

    def escrever(self, nome, texto):
        caminho = self.garantir() / nome
        caminho.write_text(texto, encoding="utf-8")
        return caminho
