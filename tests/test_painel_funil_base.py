# -*- coding: utf-8 -*-
"""Tripwire do funil de coluna da aba Pendencias (retorno da usuaria: "por que
aparece '-' no filtro?").

Bug: `_pendMenu` montava a lista de valores a partir de `DB.users` com os divs
CRUS e lia `u.divs[0]` — o primeiro acesso da pessoa, que pode ser 'Aderente' ou
'Incluir Acesso' (fora da grid pela regra "sem acesso" da Bruna). Resultado: o
filtro oferecia valores que nao existem na tela ('Aderente' em Status, o sistema
do acesso errado, '-' de campo vazio). Fix: fonte unica `_usersPendBase()`.

Varredura estrutural do index.html (nao renderiza JS) — se alguem voltar a ler
divs crus no funil, este teste acende.
"""
import re
import unittest
from pathlib import Path

INDEX = (Path(__file__).resolve().parent.parent
         / "CVC_IAM_ANALYTICS" / "EXECUTAVEIS" / "REPORT" / "index.html")


class TestFunilPendenciasUsaBaseDaGrid(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.html = INDEX.read_text(encoding="utf-8")

    def test_existe_fonte_unica(self):
        self.assertEqual(len(re.findall(r"function _usersPendBase\(\)", self.html)), 1)

    def test_grid_e_funil_leem_da_mesma_base(self):
        self.assertIn("_usersFiltrados = _usersPendBase()", self.html,
                      "renderMatrix deve usar a fonte unica")
        self.assertIn("const base=_usersPendBase()", self.html,
                      "_pendMenu (funil) deve usar a MESMA base da grid")

    def test_nao_volta_a_ler_divs_crus_no_funil(self):
        self.assertNotIn("DB.users.filter(u=>u.divs.some(divPassa))", self.html,
                         "base do funil sem filtrar os divs = valores fantasma no filtro")

    def test_base_descarta_aderente_e_incluir_acesso(self):
        corpo = re.search(r"function _usersPendBase\(\)\{[\s\S]*?\n\}", self.html).group(0)
        self.assertIn("d.a !== 'Aderente'", corpo)
        self.assertIn("d.a !== 'Incluir Acesso'", corpo)
        self.assertIn("divPassa(d)", corpo)

    def test_funil_rotula_vazio_em_vez_de_traco(self):
        # o '-' na celula e' ausencia de valor; no filtro vira "(vazio)"
        self.assertIn("(vazio)</i>", self.html)

    def test_acoes_da_sublinha_sao_rotuladas(self):
        corpo = re.search(r"function _btnResSis\([^)]*\)\{[\s\S]*?\n\}", self.html).group(0)
        self.assertIn("tratar acesso", corpo, "acao por ACESSO precisa de rotulo")
        self.assertIn("quarentena", corpo, "acao de quarentena precisa de rotulo")
        self.assertIn("todo o ", corpo, "acao do SISTEMA inteiro (quando ha 2+ acessos)")
        self.assertIn("abrirResolver(", corpo)
        self.assertIn("quarentenar(", corpo)


if __name__ == "__main__":
    unittest.main()
