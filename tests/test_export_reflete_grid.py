# -*- coding: utf-8 -*-
"""Tripwire: as exportacoes Excel devem REFLETIR a grid (mesmos campos, mesmo
formato). Bug recorrente: a coluna de login saindo com a MATRICULA (u.u) em vez
do login real (u.login), e datas CRUAS (ISO) no Excel em vez de dd/mm/aaaa.

Nao renderiza JS — faz uma varredura estrutural do index.html isolando o corpo
de cada funcao de export e checando o anti-padrao. Se alguem reintroduzir o bug,
este teste acende ANTES da entrega.
"""
import re
import unittest
from pathlib import Path

INDEX = (Path(__file__).resolve().parent.parent
         / "CVC_IAM_ANALYTICS" / "EXECUTAVEIS" / "REPORT" / "index.html")


def _corpo_funcao(html, nome):
    """Retorna o corpo textual de `function nome(...){ ... }` ate a proxima
    declaracao `function ` no topo do arquivo (suficiente p/ estas funcoes)."""
    m = re.search(r"\nfunction\s+" + re.escape(nome) + r"\s*\(", html)
    assert m, f"funcao {nome} nao encontrada no index.html"
    ini = m.start()
    prox = re.search(r"\nfunction\s+\w+\s*\(", html[ini + 1:])
    fim = (ini + 1 + prox.start()) if prox else len(html)
    return html[ini:fim]


class TestExportReflecteGrid(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.html = INDEX.read_text(encoding="utf-8")

    def test_inclusao_usa_login_real_nao_matricula(self):
        corpo = _corpo_funcao(self.html, "exportarInclusao")
        self.assertIn("u.login", corpo,
                      "export de Inclusao deve usar o login real (u.login) na coluna Usuario")
        # anti-padrao antigo: segunda posicao da linha era u.u (matricula)
        self.assertNotRegex(corpo, r"\[\s*d\.vinc[^,]*,\s*u\.u\b",
                            "Inclusao voltou a exportar u.u (matricula) na coluna Usuario")

    def test_consulta_usa_login_real_nao_matricula(self):
        corpo = _corpo_funcao(self.html, "csExportar")
        self.assertIn("u.login", corpo,
                      "export de Consulta deve usar o login real (u.login) na coluna Login")
        self.assertNotRegex(corpo, r"u\.n\s*,\s*u\.u\b",
                            "Consulta voltou a exportar u.u (matricula) na coluna Login")

    def test_aderentes_datas_formatadas_nao_cruas(self):
        corpo = _corpo_funcao(self.html, "exportarAderentes")
        # as datas do ciclo (dt_pend/dt_resol/dt) precisam passar por fmtDH
        self.assertIn("fmtDH(a.dt_pend)", corpo)
        self.assertIn("fmtDH(a.dt)", corpo)
        # anti-padrao antigo: data crua "a.dt_pend || ''"
        self.assertNotRegex(corpo, r"a\.dt_pend\s*\|\|\s*''",
                            "Aderentes voltou a exportar data crua (ISO) sem fmtDH")


if __name__ == "__main__":
    unittest.main(verbosity=2)
