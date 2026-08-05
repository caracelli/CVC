# -*- coding: utf-8 -*-
"""Deteccao de encoding: a amostra nao pode enganar em arquivo grande.

Caso real (processamento bruto de 05/08/2026): o extrato do SIG
`view_sig_15_07_2026_16-55.csv`, de 12 MB, so tem o primeiro acento no byte
78.344. A amostra antiga lia 50 KB do INICIO, via ASCII puro, devolvia 'ascii'
e a leitura do arquivo inteiro estourava no primeiro 'Ç'. O arquivo ia para
ERROS e o snapshot sumia — o motor nao quebrava, o dado e' que se perdia.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.leitores_arquivos.leitor_base import LeitorArquivoBase, ler_tabela


class TestDeteccaoEncoding(unittest.TestCase):

    def setUp(self):
        self.leitor = LeitorArquivoBase()
        self._tmp = Path(tempfile.mkdtemp(prefix="cvc_enc_"))

    def _arquivo(self, nome, conteudo: bytes) -> Path:
        p = self._tmp / nome
        p.write_bytes(conteudo)
        return p

    def test_acento_depois_da_amostra_nao_vira_ascii(self):
        # ASCII por 300 KB e um 'Ç' (utf-8) bem depois — o caso do SIG
        recheio = b"LOGIN;NOME;PERFIL\n" + (b"abc;DEF;GHI\n" * 25_000)
        p = self._arquivo("grande.csv", recheio + "CONCEIÇÃO;X;Y\n".encode("utf-8"))
        self.assertGreater(p.stat().st_size, 300_000)
        enc = self.leitor.detectar_encoding(p)
        # o teste real: o arquivo INTEIRO abre com o encoding devolvido
        p.read_text(encoding=enc)

    def test_nunca_devolve_ascii(self):
        p = self._arquivo("puro.csv", b"A;B;C\n1;2;3\n")
        self.assertNotIn(self.leitor.detectar_encoding(p).lower(), ("ascii", "us-ascii"))

    def test_arquivo_ascii_puro_continua_legivel(self):
        p = self._arquivo("puro2.csv", b"LOGIN;NOME\nabc;DEF\n")
        enc = self.leitor.detectar_encoding(p)
        self.assertEqual(p.read_text(encoding=enc), "LOGIN;NOME\nabc;DEF\n")

    def test_utf8_com_acento_no_inicio(self):
        p = self._arquivo("utf8.csv", "NOME\nCONCEIÇÃO\n".encode("utf-8"))
        enc = self.leitor.detectar_encoding(p)
        self.assertIn("CONCEIÇÃO", p.read_text(encoding=enc))

    def test_acento_so_no_FIM_de_arquivo_grande(self):
        recheio = b"col\n" + (b"valor\n" * 60_000)
        p = self._arquivo("fim.csv", recheio + "ÚLTIMO\n".encode("utf-8"))
        enc = self.leitor.detectar_encoding(p)
        p.read_text(encoding=enc)

    def test_arquivo_pequeno_nao_quebra(self):
        p = self._arquivo("mini.csv", b"a\n")
        self.leitor.detectar_encoding(p)

    def test_arquivo_vazio_nao_quebra(self):
        p = self._arquivo("vazio.csv", b"")
        self.assertTrue(self.leitor.detectar_encoding(p))


class TestLerTabela(unittest.TestCase):
    """`ler_tabela` faz a PROPRIA deteccao (janela de 64 KB) — foi ela que
    derrubou o extrato do SIG, mesmo com detectar_encoding ja corrigido.
    Duas funcoes detectando: as duas precisam do mesmo cuidado."""

    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="cvc_enc2_"))

    def test_le_csv_com_acento_depois_da_janela(self):
        p = self._tmp / "grande.csv"
        linhas = ["LOGIN;NOME;PERFIL"] + [f"u{i};FULANO;P{i%7}" for i in range(8000)]
        linhas.append("u9999;CONCEIÇÃO DA SILVA;P1")
        p.write_text("\n".join(linhas) + "\n", encoding="utf-8")
        self.assertGreater(p.stat().st_size, 65536)
        df = ler_tabela(p, dtype=str)
        self.assertEqual(len(df), 8001)
        self.assertIn("CONCEIÇÃO DA SILVA", df["NOME"].tolist())

    def test_encoding_explicito_continua_mandando(self):
        # config por sistema tem prioridade sobre a deteccao — nao pode mudar
        p = self._tmp / "cp1252.csv"
        p.write_bytes("NOME\nJOSÉ\n".encode("cp1252"))
        df = ler_tabela(p, dtype=str, encoding="cp1252")
        self.assertEqual(df["NOME"].tolist(), ["JOSÉ"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
