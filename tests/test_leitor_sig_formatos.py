# -*- coding: utf-8 -*-
"""LeitorSig deve importar o extrato matricial tanto em XLSX (modelo antigo)
quanto em CSV (modelo novo), desde que as colunas/dados sejam os mesmos. As
colunas sao identificadas por NOME (case-insensitive), entao os dois formatos
caem no mesmo despivot."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import openpyxl

from infraestrutura.leitores_arquivos.leitor_sig import LeitorSig

CATALOGO = {"1": "PERFIL_A", "10": "PERFIL_B"}
HEADER = ["LOGIN", "NM_USER", "STATUS", "CPF", "EMAIL", "1", "10"]
LINHAS = [
    ["u1", "USER ONE", "ATIVO", "111", "e1@x", "X", ""],
    ["u2", "USER TWO", "ATIVO", "222", "e2@x", "", "X"],
]


class TestLeitorSigFormatos(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cvc_sigfmt_")

    def _xlsx(self):
        p = os.path.join(self.tmp, "sig.xlsx")
        wb = openpyxl.Workbook(); ws = wb.active
        ws.append(HEADER)
        for ln in LINHAS:
            ws.append(ln)
        wb.save(p)
        return Path(p)

    def _csv(self):
        p = os.path.join(self.tmp, "sig.csv")
        linhas = [",".join(HEADER)] + [",".join(ln) for ln in LINHAS]
        Path(p).write_text("\n".join(linhas), encoding="utf-8")
        return Path(p)

    def _acessos(self, arquivo):
        perfis = LeitorSig(catalogo=CATALOGO).ler_um(arquivo)
        return sorted((p.usuario, p.perfil) for p in perfis)

    def test_xlsx_e_csv_produzem_o_mesmo_despivot(self):
        esperado = [("u1", "PERFIL_A"), ("u2", "PERFIL_B")]
        self.assertEqual(self._acessos(self._xlsx()), esperado)
        self.assertEqual(self._acessos(self._csv()), esperado)

    def test_csv_com_ponto_e_virgula(self):
        # separador ';' tambem deve ser detectado
        p = os.path.join(self.tmp, "sig2.csv")
        linhas = [";".join(HEADER)] + [";".join(ln) for ln in LINHAS]
        Path(p).write_text("\n".join(linhas), encoding="utf-8")
        self.assertEqual(self._acessos(Path(p)),
                         [("u1", "PERFIL_A"), ("u2", "PERFIL_B")])


if __name__ == "__main__":
    unittest.main(verbosity=2)
