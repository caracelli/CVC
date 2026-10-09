# -*- coding: utf-8 -*-
"""Os exes nao rodam da pasta de REDE (09/10/2026).

Alguem abriu o launcher direto da rede: a pasta ficou presa (ninguem consegue
atualizar) e o painel usa <rede>\\EXECUTAVEIS\\DADOS\\BANCO como "copia local"
— um arquivo so', na rede, para todos — o que corrompe o banco.

A mesma funcao `_executando_da_rede` esta nos tres pontos de entrada
(principal, painel e Processador); este teste garante que sao identicas e
que cada um chama a trava antes de qualquer outra coisa.
"""
import ast
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQS = {
    "principal": RAIZ / "src" / "launcher" / "principal.py",
    "visualizador": RAIZ / "src" / "visualizador" / "main.py",
    "processador": RAIZ / "src" / "processador" / "main.py",
}


def _fonte(arq: Path, nome: str) -> str:
    src = arq.read_text(encoding="utf-8-sig")
    for n in ast.parse(src).body:
        if isinstance(n, ast.FunctionDef) and n.name == nome:
            return ast.get_source_segment(src, n)
    raise AssertionError(f"{nome} ausente em {arq}")


def _funcao():
    ns = {"sys": sys}
    exec(_fonte(ARQS["principal"], "_executando_da_rede"), ns)
    return ns["_executando_da_rede"]


class TestNaoRodaDaRede(unittest.TestCase):

    def test_mesma_funcao_nos_tres_exes(self):
        for nome in ("_executando_da_rede", "_avisar_rede"):
            fontes = {k: _fonte(a, nome) for k, a in ARQS.items()}
            self.assertEqual(len(set(fontes.values())), 1, f"{nome} divergiu: {list(fontes)}")

    def test_caminho_unc_e_rede(self):
        f = _funcao()
        self.assertTrue(f(r"\\intra.cvc\fscvc\Processos_Antlia\CVC\CVC_IAM_ANALYTICS\EXECUTAVEIS"))
        self.assertTrue(f(r"\\intra.cvc\fscvc\Processos_Antlia\CVC\CVC_IAM_ANALYTICS\EXECUTAVEIS\launcher"))

    def test_pasta_local_nao_e_rede(self):
        f = _funcao()
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(f(d, r"\\intra.cvc\fscvc\Processos_Antlia\CVC\CVC_IAM_ANALYTICS"))
            self.assertFalse(f(d, ""))

    def test_dentro_da_raiz_de_rede_configurada(self):
        """Unidade mapeada que o Windows nao marque como remota: vale a raiz."""
        f = _funcao()
        with tempfile.TemporaryDirectory() as d:
            raiz = Path(d) / "CVC_IAM_ANALYTICS"
            (raiz / "EXECUTAVEIS" / "launcher").mkdir(parents=True)
            self.assertTrue(f(raiz / "EXECUTAVEIS", str(raiz)))
            self.assertTrue(f(raiz / "EXECUTAVEIS" / "launcher", str(raiz) + "\\"))
            vizinha = Path(d) / "CVC_IAM_ANALYTICS_LOCAL" / "EXECUTAVEIS"
            vizinha.mkdir(parents=True)
            self.assertFalse(f(vizinha, str(raiz)), "prefixo do nome nao e' a mesma pasta")

    def test_cada_exe_chama_a_trava_no_inicio(self):
        principal = _fonte(ARQS["principal"], "main")
        self.assertLess(principal.index("_executando_da_rede"),
                        principal.index("_matar_processos_anteriores"))
        proc = _fonte(ARQS["processador"], "main")
        self.assertLess(proc.index("_executando_da_rede"), proc.index("ui.iniciar"))
        vis = ARQS["visualizador"].read_text(encoding="utf-8-sig")
        chamada = vis.index("if _executando_da_rede(BASE_APP")
        self.assertLess(chamada, vis.index("os.makedirs(_p, exist_ok=True)"))
        self.assertLess(chamada, vis.index("DB_PATH = sincronizar_banco()"))


if __name__ == "__main__":
    unittest.main()
