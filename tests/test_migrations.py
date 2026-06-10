# -*- coding: utf-8 -*-
"""Migrations incrementais e idempotentes (ConexaoBancoDados._migrar).

Cria bancos com schema LEGADO via sqlite puro e confere que inicializar()
migra preservando os dados, e que rodar de novo e' no-op (idempotente).
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.banco_dados.conexao import ConexaoBancoDados


def _cols(db, tabela):
    c = sqlite3.connect(db)
    try:
        return {r[1] for r in c.execute(f"PRAGMA table_info({tabela})")}
    finally:
        c.close()


def _pk(db, tabela):
    c = sqlite3.connect(db)
    try:
        rows = list(c.execute(f"PRAGMA table_info({tabela})"))
        pks = sorted([(r[5], r[1]) for r in rows if r[5] > 0])
        return [n for _, n in pks]
    finally:
        c.close()


def _scalar(db, sql, *p):
    c = sqlite3.connect(db)
    try:
        return c.execute(sql, p).fetchone()
    finally:
        c.close()


class TestMigracaoAcessosPK(unittest.TestCase):
    """acessos_sistemas legado (PK sistema,usuario, sem perfil/matching/email)
    -> PK (sistema,usuario,perfil) + colunas de matching, dados preservados."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_mig_pk_")
        self.db = os.path.join(self._tmp, "legado.db")
        c = sqlite3.connect(self.db)
        c.executescript("""
            CREATE TABLE acessos_sistemas (
              sistema TEXT NOT NULL, usuario TEXT NOT NULL, perfil TEXT,
              nome_usuario TEXT, cpf TEXT, situacao TEXT,
              matricula_vinculada TEXT, arquivo_origem TEXT, dt_importacao DATETIME,
              PRIMARY KEY (sistema, usuario)
            );
            INSERT INTO acessos_sistemas (sistema,usuario,perfil,cpf,matricula_vinculada)
            VALUES ('SYSTUR','log1','P1','12345678901','M1');
        """)
        c.commit()
        c.close()

    def test_migra_pk_colunas_e_preserva_dados(self):
        ConexaoBancoDados(self.db).inicializar()
        self.assertEqual(_pk(self.db, "acessos_sistemas"), ["sistema", "usuario", "perfil"])
        cols = _cols(self.db, "acessos_sistemas")
        for c in ("metodo_vinculacao", "score_vinculacao", "candidatos_matricula", "email"):
            self.assertIn(c, cols)
        row = _scalar(self.db,
                      "SELECT perfil,cpf,matricula_vinculada FROM acessos_sistemas "
                      "WHERE sistema='SYSTUR' AND usuario='log1'")
        self.assertEqual(row, ("P1", "12345678901", "M1"))

    def test_migracao_idempotente(self):
        ConexaoBancoDados(self.db).inicializar()
        n1 = _scalar(self.db, "SELECT COUNT(*) FROM acessos_sistemas")[0]
        ConexaoBancoDados(self.db).inicializar()   # 2a vez: nao deve mexer
        n2 = _scalar(self.db, "SELECT COUNT(*) FROM acessos_sistemas")[0]
        self.assertEqual((n1, n2), (1, 1))
        self.assertEqual(_pk(self.db, "acessos_sistemas"), ["sistema", "usuario", "perfil"])


class TestMigracaoColunasNovas(unittest.TestCase):

    def _db_legado(self, ddl):
        tmp = tempfile.mkdtemp(prefix="cvc_mig_col_")
        db = os.path.join(tmp, "legado.db")
        c = sqlite3.connect(db)
        c.executescript(ddl)
        c.commit()
        c.close()
        return db

    def test_perfis_esperados_ganha_cargo_descricao_e_acesso_manual(self):
        db = self._db_legado("""
            CREATE TABLE perfis_esperados (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              cargo_codigo TEXT, sistema TEXT, perfil TEXT);
            INSERT INTO perfis_esperados (cargo_codigo,sistema,perfil)
            VALUES ('100','SYSTUR','P1');
        """)
        ConexaoBancoDados(db).inicializar()
        cols = _cols(db, "perfis_esperados")
        self.assertIn("cargo_descricao", cols)
        self.assertIn("acesso_manual", cols)
        self.assertEqual(_scalar(db, "SELECT COUNT(*) FROM perfis_esperados")[0], 1)

    def test_validacao_acessos_ganha_situacao_acao(self):
        db = self._db_legado("""
            CREATE TABLE validacao_acessos (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              matricula TEXT, sistema TEXT NOT NULL, status TEXT NOT NULL);
            INSERT INTO validacao_acessos (matricula,sistema,status)
            VALUES ('M1','SYSTUR','DIVERGENTE');
        """)
        ConexaoBancoDados(db).inicializar()
        self.assertIn("situacao_acao", _cols(db, "validacao_acessos"))
        self.assertEqual(_scalar(db, "SELECT COUNT(*) FROM validacao_acessos")[0], 1)


class TestInicializarIdempotente(unittest.TestCase):

    def test_inicializar_duas_vezes_em_banco_novo(self):
        tmp = tempfile.mkdtemp(prefix="cvc_mig_new_")
        db = os.path.join(tmp, "novo.db")
        ConexaoBancoDados(db).inicializar()
        ConexaoBancoDados(db).inicializar()   # nao deve falhar
        tabelas = {r[0] for r in sqlite3.connect(db).execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        for t in ("rh_ativos", "acessos_sistemas", "perfis_esperados",
                  "validacao_acessos", "historico"):
            self.assertIn(t, tabelas)


if __name__ == "__main__":
    unittest.main(verbosity=2)
