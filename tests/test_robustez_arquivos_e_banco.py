# -*- coding: utf-8 -*-
"""Robustez contra travamentos do Processador:
- arquivos de tipo NAO suportado / lock do Office -> movidos para INVALIDOS/
  (nao chegam nos leitores, nao quebram o pandas);
- banco .db corrompido (nao e' SQLite) -> movido para .corrompido_<ts> e recriado
  (em vez de 'file is not a database').
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.leitores_arquivos.leitor_base import LeitorArquivoBase
from infraestrutura.banco_dados.conexao import ConexaoBancoDados


class TestArquivosInvalidos(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="cvc_inval_"))

    def _tocar(self, nome, conteudo=b"x"):
        p = self._tmp / nome
        p.write_bytes(conteudo)
        return p

    def test_move_invalidos_e_mantem_validos(self):
        self._tocar("dados.csv", b"a;b\n1;2\n")          # valido
        self._tocar("planilha.xlsx", b"PK\x03\x04lixo")  # extensao valida (fica; erro so na leitura)
        self._tocar("relatorio.pdf")                      # tipo nao suportado -> INVALIDOS
        self._tocar("notas.txt")                          # tipo nao suportado -> INVALIDOS
        self._tocar("~$aberto.xlsx")                      # lock do Office -> INVALIDOS
        self._tocar(".gitkeep", b"")                      # estrutural -> ignora (nao move)

        leitor = LeitorArquivoBase()
        validos = leitor.listar_arquivos(str(self._tmp))
        nomes = sorted(f.name for f in validos)
        self.assertEqual(nomes, ["dados.csv", "planilha.xlsx"])

        inval = self._tmp / "INVALIDOS"
        self.assertTrue(inval.exists())
        movidos = sorted(f.stem.split("_2")[0] for f in inval.iterdir())
        # pdf, txt e o lock ~$ foram movidos (nome tem sufixo de timestamp)
        self.assertTrue(any("relatorio" in f.name for f in inval.iterdir()))
        self.assertTrue(any("notas" in f.name for f in inval.iterdir()))
        self.assertTrue(any(f.name.startswith("~$") or "aberto" in f.name
                            for f in inval.iterdir()))
        # .gitkeep NAO foi movido (segue na pasta)
        self.assertTrue((self._tmp / ".gitkeep").exists())

    def test_ignora_subpasta_invalidos_na_revarredura(self):
        self._tocar("bom.csv", b"a;b\n1;2\n")
        self._tocar("ruim.pdf")
        leitor = LeitorArquivoBase()
        leitor.listar_arquivos(str(self._tmp))          # 1a passada move o pdf
        # 2a passada: nao reprocessa o que ja esta em INVALIDOS/
        validos = leitor.listar_arquivos(str(self._tmp))
        self.assertEqual([f.name for f in validos], ["bom.csv"])
        # nada duplicado em INVALIDOS
        self.assertEqual(len(list((self._tmp / "INVALIDOS").iterdir())), 1)


class TestBancoCorrompido(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="cvc_dbcorr_"))
        self.db = self._tmp / "iam.db"

    def test_db_nao_sqlite_e_movido_e_recriado(self):
        # simula banco corrompido / escrita parcial na rede (nao e' SQLite)
        self.db.write_bytes(b"isto nao e um banco sqlite valido\x00\x01")
        con = ConexaoBancoDados(str(self.db))
        con.inicializar()   # NAO deve levantar 'file is not a database'
        # o arquivo corrompido foi movido para .corrompido_*
        corrompidos = list(self._tmp.glob("iam.db.corrompido_*"))
        self.assertEqual(len(corrompidos), 1)
        # e um banco NOVO valido foi criado (tem as tabelas do schema)
        c = sqlite3.connect(str(self.db))
        try:
            tabs = {r[0] for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            c.close()
        self.assertIn("rh_ativos", tabs)

    def test_db_valido_nao_e_mexido(self):
        # banco valido existente nao pode ser movido
        ConexaoBancoDados(str(self.db)).inicializar()
        ConexaoBancoDados(str(self.db)).inicializar()   # 2a vez: nada de .corrompido
        self.assertEqual(list(self._tmp.glob("*.corrompido_*")), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
