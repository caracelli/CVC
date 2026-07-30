# -*- coding: utf-8 -*-
"""Outline de profundidade livre no .xlsx (pessoa > sistema > perfil).

As grids Desligados/Transferidos passaram a abrir os acessos POR SISTEMA
(colapsando os perfis). O Excel espelha isso com TRES niveis de outline, o que
exigiu generalizar `gerar_xlsx` (antes todo nivel > 0 virava outlineLevel="1").
Este teste trava a generalizacao e a retrocompatibilidade de 2 niveis, alem de
checar que os dois exports realmente agrupam por sistema.
"""
import re
import unittest
import zipfile
from io import BytesIO
from pathlib import Path

from src.visualizador.main import gerar_xlsx

INDEX = (Path(__file__).resolve().parent.parent
         / "CVC_IAM_ANALYTICS" / "EXECUTAVEIS" / "REPORT" / "index.html")


def _linhas_xml(xlsx_bytes):
    with zipfile.ZipFile(BytesIO(xlsx_bytes)) as z:
        sheet = z.read("xl/worksheets/sheet1.xml").decode("utf-8")
    return sheet, re.findall(r"<row [^>]*>", sheet)


class TestOutlineTresNiveis(unittest.TestCase):

    def setUp(self):
        self.cols = ["Matricula", "Sistema", "Perfil"]
        # pessoa > sistema(2 perfis) > perfil, perfil ; sistema(1) ; pessoa sem acesso
        self.linhas = [
            ["1", "", ""],          # 0 pessoa
            ["", "SIG", "2 perfis"],  # 1 sistema (abre grupo de perfis)
            ["", "", "P1"],        # 2 perfil
            ["", "", "P2"],        # 2 perfil
            ["", "SYSTUR", "A"],   # 1 sistema sem filhos
            ["2", "", ""],         # 0 pessoa sem acesso
        ]
        self.niveis = [0, 1, 2, 2, 1, 0]

    def test_outline_level_segue_o_nivel(self):
        sheet, rows = _linhas_xml(gerar_xlsx(self.cols, self.linhas, self.niveis))
        # rows[0] = cabecalho
        self.assertNotIn("outlineLevel", rows[1])            # pessoa
        self.assertIn('outlineLevel="1"', rows[2])           # sistema
        self.assertIn('outlineLevel="2"', rows[3])           # perfil
        self.assertIn('outlineLevel="2"', rows[4])           # perfil
        self.assertIn('outlineLevel="1"', rows[5])           # sistema sem filhos
        self.assertNotIn("outlineLevel", rows[6])            # pessoa
        self.assertIn('outlineLevelRow="2"', sheet)

    def test_detalhe_sai_recolhido_e_pai_collapsed(self):
        _, rows = _linhas_xml(gerar_xlsx(self.cols, self.linhas, self.niveis))
        self.assertIn('collapsed="1"', rows[1])   # pessoa abre grupo de sistemas
        self.assertIn('collapsed="1"', rows[2])   # sistema abre grupo de perfis
        self.assertNotIn('collapsed="1"', rows[5])  # sistema sem filhos
        for i in (2, 3, 4, 5):                    # todo detalhe nasce oculto
            self.assertIn('hidden="1"', rows[i])
        self.assertNotIn('hidden="1"', rows[1])

    def test_retrocompatibilidade_dois_niveis(self):
        """Exports antigos (0/1) devem sair exatamente como antes."""
        sheet, rows = _linhas_xml(
            gerar_xlsx(self.cols, [["1", "", ""], ["", "SIG", "P1"]], [0, 1]))
        self.assertIn('collapsed="1"', rows[1])
        self.assertIn('outlineLevel="1" hidden="1"', rows[2])
        self.assertIn('outlineLevelRow="1"', sheet)

    def test_sem_niveis_nao_gera_outline(self):
        sheet, rows = _linhas_xml(gerar_xlsx(self.cols, [["1", "SIG", "P1"]]))
        self.assertNotIn("outlineLevel", sheet)
        self.assertNotIn("outlinePr", sheet)
        self.assertNotIn("hidden", rows[1])


class TestExportsAgrupamPorSistema(unittest.TestCase):
    """A grid abre por sistema; o Excel tem de sair igual (regra: export reflete
    a grid). Varredura estrutural do index.html."""

    @classmethod
    def setUpClass(cls):
        cls.html = INDEX.read_text(encoding="utf-8")

    def _corpo(self, nome):
        m = re.search(r"\nfunction\s+" + re.escape(nome) + r"\s*\(", self.html)
        assert m, f"funcao {nome} nao encontrada"
        ini = m.start()
        prox = re.search(r"\nfunction\s+\w+\s*\(", self.html[ini + 1:])
        return self.html[ini:(ini + 1 + prox.start()) if prox else len(self.html)]

    def test_exports_usam_agrupamento_por_sistema(self):
        for fn in ("exportarDesligados", "exportarTransferidos"):
            corpo = self._corpo(fn)
            self.assertIn("_acessosPorSistema", corpo,
                          f"{fn} deve agrupar por sistema como a grid")
            self.assertIn("niveis.push(2)", corpo,
                          f"{fn} deve descer os perfis para o nivel 2 do outline")

    def test_grids_usam_agrupamento_por_sistema(self):
        for fn in ("pintarDesligados", "pintarTransferidos"):
            self.assertIn("_acessosPorSistema", self._corpo(fn),
                          f"{fn} deve abrir os acessos por sistema")


if __name__ == "__main__":
    unittest.main()
