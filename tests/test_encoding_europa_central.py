# -*- coding: utf-8 -*-
"""O chardet le cp1252 (Brasil) como cp1250 (Europa Central).

Retorno de 28/09/2026 (ajustes_apl_28_09.docx, HERMES 90000639): o extrato
Oracle traz 'Criação' em cp1252 (byte E3 = 'ã'); lido como cp1250 virava
'Criaçăo' e nao casava com a matriz — o mesmo perfil aparecia em "Faltam" e em
"a mais". Na base de 15/09 o mesmo defeito atingia 110 nomes do SYSTUR e
departamento/cargo do RH ("CONCILIAÇĂO").
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from infraestrutura.leitores_arquivos.leitor_base import (
    ler_tabela, normalizar_encoding_detectado)


class Normalizar(unittest.TestCase):

    def test_europa_central_vira_cp1252(self):
        for e in ("windows-1250", "Windows-1250", "ISO-8859-2", "cp1250"):
            self.assertEqual(normalizar_encoding_detectado(e), "cp1252", e)

    def test_ascii_e_vazio_viram_utf8(self):
        self.assertEqual(normalizar_encoding_detectado("ascii"), "utf-8")
        self.assertEqual(normalizar_encoding_detectado(None), "utf-8")

    def test_demais_ficam_como_vieram(self):
        self.assertEqual(normalizar_encoding_detectado("utf-8"), "utf-8")
        self.assertEqual(normalizar_encoding_detectado("UTF-8-SIG"), "utf-8-sig")
        self.assertEqual(normalizar_encoding_detectado("Windows-1252"), "windows-1252")


class LerTabela(unittest.TestCase):

    def test_perfil_oracle_com_til_nao_vira_breve(self):
        linhas = ["USUÁRIO;PERFIL"] + [
            f"U{i};CVC INV BRASIL Criação Itens" if i % 3 == 0 else
            f"U{i};CVC GL SERVIÇOS Consulta Fiscal – Conciliação São Paulo"
            for i in range(300)]
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "view_ebs.csv"
            f.write_bytes("\n".join(linhas).encode("cp1252"))
            df = ler_tabela(f, separador=";")
        perfis = set(df["PERFIL"])
        self.assertIn("CVC INV BRASIL Criação Itens", perfis)
        self.assertFalse(any("ă" in p for p in perfis), perfis)


if __name__ == "__main__":
    unittest.main()
