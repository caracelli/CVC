# -*- coding: utf-8 -*-
"""Log de importacao por hash (md5): deteccao de reimportacao do mesmo conteudo."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from datetime import datetime

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.repositorios.repositorio_log_importacao import (
    RepositorioLogImportacao, md5_arquivo, loga_se_reimportacao,
    data_modificacao, mtimes_da_pasta,
)


class TestMd5(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="cvc_md5_")

    def _arq(self, nome, conteudo):
        p = Path(self.dir) / nome
        p.write_text(conteudo, encoding="utf-8")
        return p

    def test_mesmo_conteudo_mesmo_hash(self):
        a = self._arq("a.csv", "linha1\nlinha2\n")
        b = self._arq("b.csv", "linha1\nlinha2\n")   # nome diferente, conteudo igual
        self.assertEqual(md5_arquivo(a), md5_arquivo(b))

    def test_conteudo_diferente_hash_diferente(self):
        a = self._arq("a.csv", "X")
        b = self._arq("b.csv", "Y")
        self.assertNotEqual(md5_arquivo(a), md5_arquivo(b))


class TestRepositorioLog(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_logimp_")
        self.conexao = ConexaoBancoDados(os.path.join(self._tmp, "l.db"))
        self.conexao.inicializar()
        self.repo = RepositorioLogImportacao(self.conexao)

    def test_registrar_e_encontrar_por_hash(self):
        self.repo.registrar(arquivo="systur.csv", tipo="SYSTUR",
                            hash_arquivo="abc123", total_registros=10, status="SUCESSO")
        self.assertEqual(self.repo.hash_ja_importado("abc123"), "systur.csv")

    def test_hash_inexistente_e_vazio_retornam_none(self):
        self.assertIsNone(self.repo.hash_ja_importado("naoexiste"))
        self.assertIsNone(self.repo.hash_ja_importado(""))

    def test_status_erro_nao_conta_como_importado(self):
        self.repo.registrar(arquivo="ruim.csv", tipo="SYSTUR",
                            hash_arquivo="errohash", status="ERRO",
                            mensagem_erro="falhou")
        self.assertIsNone(self.repo.hash_ja_importado("errohash"))

    def test_loga_se_reimportacao_devolve_hash_e_nao_bloqueia(self):
        p = Path(self._tmp) / "systur_30_04.csv"
        p.write_text("a;b;c\n1;2;3\n", encoding="utf-8")
        h = loga_se_reimportacao(self.repo, caminho=p, tipo="SYSTUR")
        self.assertEqual(h, md5_arquivo(p))
        # registra sob OUTRO nome e roda de novo: deve detectar reimportacao sem erro
        self.repo.registrar(arquivo="outro_nome.csv", tipo="SYSTUR",
                            hash_arquivo=h, status="SUCESSO")
        h2 = loga_se_reimportacao(self.repo, caminho=p, tipo="SYSTUR")
        self.assertEqual(h2, h)   # nao bloqueia, devolve o mesmo hash


class TestDataArquivo(unittest.TestCase):
    """Data do PROPRIO arquivo (disponibilizacao) capturada na importacao."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_dtarq_")
        self.conexao = ConexaoBancoDados(os.path.join(self._tmp, "l.db"))
        self.conexao.inicializar()
        self.repo = RepositorioLogImportacao(self.conexao)

    def test_data_modificacao_le_mtime(self):
        p = Path(self._tmp) / "x.csv"
        p.write_text("a", encoding="utf-8")
        ref = datetime(2026, 4, 30, 14, 23, 11)
        os.utime(p, (ref.timestamp(), ref.timestamp()))
        self.assertEqual(data_modificacao(p), ref)

    def test_data_modificacao_inexistente_none(self):
        self.assertIsNone(data_modificacao(Path(self._tmp) / "naoexiste.csv"))

    def test_mtimes_da_pasta_recursivo(self):
        raiz = Path(self._tmp) / "entrada"      # pasta limpa (o l.db fica fora)
        sub = raiz / "sub"
        sub.mkdir(parents=True)
        (raiz / "a.csv").write_text("a", encoding="utf-8")
        (sub / "b.csv").write_text("b", encoding="utf-8")
        mt = mtimes_da_pasta(str(raiz))
        self.assertEqual(set(mt), {"a.csv", "b.csv"})
        self.assertTrue(all(isinstance(v, datetime) for v in mt.values()))

    def test_registrar_persiste_dt_arquivo(self):
        ref = datetime(2026, 4, 30, 9, 0, 0)
        self.repo.registrar(arquivo="systur.xlsx", tipo="SYSTUR", hash_arquivo="h",
                            total_registros=5, status="SUCESSO", dt_arquivo=ref)
        import sqlite3
        c = sqlite3.connect(os.path.join(self._tmp, "l.db"))
        row = c.execute("SELECT dt_arquivo FROM log_importacoes WHERE arquivo='systur.xlsx'").fetchone()
        c.close()
        # SQLAlchemy grava com microssegundos; o front (fmtDH) trunca na exibicao
        self.assertTrue(str(row[0]).startswith("2026-04-30 09:00:00"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
