# -*- coding: utf-8 -*-
"""Banco da rede sem WAL (09/10/2026, "database disk image is malformed").

Na rede ficou um iam_analytics.db-wal ORFAO (gravacao das 10:18) ao lado de um
.db integro gravado depois em modo classico (11:00). Quem abria o banco
aplicava o -wal velho por cima e o painel copiava um banco corrompido.

- Processador: o -wal orfao vai para '.orfao_<data>'; WAL legitimo e'
  consolidado; o banco fica em journal_mode=DELETE.
- Painel: copia o ARQUIVO .db (ignora -wal ao lado), confere a copia com
  quick_check e nao copia durante o processamento (_processando.lock).
"""
import ast
import os
import shutil
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from infraestrutura.banco_dados.conexao import ConexaoBancoDados  # noqa: E402

VIS = RAIZ / "src" / "visualizador" / "main.py"


def _funcoes_do_painel():
    tree = ast.parse(VIS.read_text(encoding="utf-8-sig"))
    ns = {"os": os, "sqlite3": sqlite3, "time": time, "_LOCK_STALE_S": 1800}
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name in (
                "_banco_integro", "_copiar_banco_da_rede", "_processando_na_rede"):
            exec(compile(ast.Module([n], []), "vis", "exec"), ns)
    return ns


def _banco_com_wal_orfao(pasta: Path) -> Path:
    """Reproduz a rede: um -wal de uma versao ANTERIOR do banco ao lado de um
    .db mais novo, ja em modo classico."""
    db = pasta / "iam_analytics.db"
    c = sqlite3.connect(db)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA wal_autocheckpoint=0")
    c.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, v TEXT)")
    c.executemany("INSERT INTO t(v) VALUES (?)", [("x" * 200,)] * 3000)
    c.commit()
    c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    c.executemany("UPDATE t SET v=? WHERE id=?",
                  [("velho" * 40, i) for i in range(1, 3001, 3)])
    c.commit()
    shutil.copy(str(db) + "-wal", pasta / "wal_velho")   # o resto das 10:18
    c.close()
    c = sqlite3.connect(db)                               # a gravacao das 11:00
    c.execute("PRAGMA journal_mode=DELETE")
    c.execute("DELETE FROM t WHERE id % 2 = 0")
    c.commit()
    c.execute("VACUUM")
    c.close()
    shutil.move(str(pasta / "wal_velho"), str(db) + "-wal")
    return db


class TestBancoRedeSemWal(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_cenario_reproduz_o_malformed(self):
        db = _banco_com_wal_orfao(self.tmp)
        self.assertEqual(open(db, "rb").read(20)[18], 1)
        ns = _funcoes_do_painel()
        self.assertFalse(ns["_banco_integro"](str(db)),
                         "o -wal orfao aplicado tem de corromper (cenario da rede)")

    def test_processador_tira_o_wal_orfao_e_fica_em_delete(self):
        db = _banco_com_wal_orfao(self.tmp)
        ConexaoBancoDados(str(db))._garantir_journal_delete()
        nomes = os.listdir(self.tmp)
        self.assertNotIn("iam_analytics.db-wal", nomes)
        self.assertTrue(any(n.startswith("iam_analytics.db-wal.orfao_") for n in nomes),
                        "o -wal orfao e' guardado, nao apagado")
        c = sqlite3.connect(db)
        self.assertEqual(c.execute("PRAGMA journal_mode").fetchone()[0], "delete")
        self.assertEqual(c.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        self.assertEqual(c.execute("SELECT COUNT(*) FROM t").fetchone()[0], 1500)
        c.close()

    def test_processador_consolida_wal_legitimo_sem_perder_dado(self):
        db = self.tmp / "w.db"
        c = sqlite3.connect(db)
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA wal_autocheckpoint=0")
        c.execute("CREATE TABLE x(a)")
        c.executemany("INSERT INTO x VALUES (?)", [(i,) for i in range(5000)])
        c.commit()
        shutil.copy(db, self.tmp / "snap")
        shutil.copy(str(db) + "-wal", self.tmp / "snapwal")
        c.close()
        os.replace(self.tmp / "snap", db)
        os.replace(self.tmp / "snapwal", str(db) + "-wal")
        self.assertEqual(open(db, "rb").read(20)[18], 2)
        ConexaoBancoDados(str(db))._garantir_journal_delete()
        self.assertFalse(os.path.exists(str(db) + "-wal"))
        c = sqlite3.connect(db)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM x").fetchone()[0], 5000)
        self.assertEqual(c.execute("PRAGMA journal_mode").fetchone()[0], "delete")
        c.close()

    def test_painel_copia_integra_e_nao_mexe_na_rede(self):
        db = _banco_com_wal_orfao(self.tmp)
        antes = sorted(os.listdir(self.tmp))
        ns = _funcoes_do_painel()
        novo = self.tmp / "local.novo"
        ns["_copiar_banco_da_rede"](str(db), str(novo))
        self.assertTrue(ns["_banco_integro"](str(novo)))
        c = sqlite3.connect(novo)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM t").fetchone()[0], 1500)
        c.close()
        self.assertEqual(sorted(n for n in os.listdir(self.tmp)
                                if not n.startswith("local.novo")), antes)

    def test_painel_nao_copia_durante_o_processamento(self):
        db = _banco_com_wal_orfao(self.tmp)
        ns = _funcoes_do_painel()
        self.assertFalse(ns["_processando_na_rede"](str(db)))
        lock = self.tmp / "_processando.lock"
        lock.write_text("x")
        self.assertTrue(ns["_processando_na_rede"](str(db)))
        velho = time.time() - 3600
        os.utime(lock, (velho, velho))
        self.assertFalse(ns["_processando_na_rede"](str(db)), "trava morta nao bloqueia")

    def test_ninguem_mais_poe_o_banco_da_rede_em_wal(self):
        dobra = (RAIZ / "src" / "aplicacao" / "casos_de_uso"
                 / "dobrar_interacoes.py").read_text(encoding="utf-8")
        self.assertNotIn("journal_mode=WAL", dobra)
        self.assertIn("journal_mode=DELETE", dobra)


if __name__ == "__main__":
    unittest.main()
