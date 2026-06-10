# -*- coding: utf-8 -*-
"""PadronizarRh (Card 4): normaliza cpf/nome/matricula/situacao dos RH ja
gravados, in-place, idempotente.
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from aplicacao.casos_de_uso.padronizar_rh import PadronizarRh


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_padrh_")
        self.db = os.path.join(self._tmp, "p.db")
        self.conexao = ConexaoBancoDados(self.db)
        self.conexao.inicializar()

    def _exec(self, sql):
        c = sqlite3.connect(self.db)
        try:
            c.executescript(sql)
            c.commit()
        finally:
            c.close()

    def _row(self, sql):
        c = sqlite3.connect(self.db)
        try:
            return c.execute(sql).fetchone()
        finally:
            c.close()


class TestPadronizarAtivos(_Base):

    def setUp(self):
        super().setUp()
        self._exec(
            "INSERT INTO rh_ativos (matricula,nome,cpf,situacao) VALUES "
            "('00123','  joão   silva ','123.456.789-00','Atividade Normal');")
        PadronizarRh(self.conexao).executar()

    def test_cpf_normalizado(self):
        self.assertEqual(self._row("SELECT cpf FROM rh_ativos")[0], "12345678900")

    def test_nome_normalizado(self):
        self.assertEqual(self._row("SELECT nome FROM rh_ativos")[0], "JOÃO SILVA")

    def test_situacao_normalizada(self):
        self.assertEqual(self._row("SELECT situacao FROM rh_ativos")[0], "ATIVO")

    def test_matricula_normalizada_in_place(self):
        # matricula e' PK; normalizar remove zeros a esquerda ('00123' -> '123')
        self.assertEqual(self._row("SELECT matricula FROM rh_ativos")[0], "123")
        self.assertEqual(self._row("SELECT COUNT(*) FROM rh_ativos")[0], 1)


class TestPadronizarDesligados(_Base):

    def test_normaliza_cpf_nome_matricula(self):
        self._exec(
            "INSERT INTO rh_desligados (matricula,nome,cpf) VALUES "
            "('00900','  maria  souza ','987.654.321-00');")
        PadronizarRh(self.conexao).executar()
        row = self._row("SELECT matricula,nome,cpf FROM rh_desligados")
        self.assertEqual(row, ("900", "MARIA SOUZA", "98765432100"))


class TestColisaoMatricula(_Base):
    """Bug: '00100' e '100' normalizam ambos para '100' (a PK) -> antes
    quebrava com IntegrityError e derrubava a padronizacao inteira. Fix:
    renomeia so quem nao colide; o outro fica sem alterar."""

    def test_colisao_nao_crasha_e_preserva_ambos(self):
        self._exec(
            "INSERT INTO rh_ativos (matricula,nome,cpf,situacao) VALUES "
            "('00100','ANA','111','ATIVO'),('100','BRUNO','222','ATIVO');")
        PadronizarRh(self.conexao).executar()   # nao deve crashar
        c = sqlite3.connect(self.db)
        try:
            mats = {r[0] for r in c.execute("SELECT matricula FROM rh_ativos")}
            n = c.execute("SELECT COUNT(*) FROM rh_ativos").fetchone()[0]
        finally:
            c.close()
        self.assertEqual(n, 2)                  # nenhum registro perdido
        self.assertIn("100", mats)              # um normalizado/ja era
        self.assertEqual(len(mats), 2)          # sem colisao de PK

    def test_colisao_desligados_nao_crasha(self):
        self._exec(
            "INSERT INTO rh_desligados (matricula,nome,cpf) VALUES "
            "('0050','X','1'),('50','Y','2');")
        PadronizarRh(self.conexao).executar()
        c = sqlite3.connect(self.db)
        try:
            n = c.execute("SELECT COUNT(*) FROM rh_desligados").fetchone()[0]
        finally:
            c.close()
        self.assertEqual(n, 2)


class TestIdempotente(_Base):

    def test_rodar_duas_vezes_nao_muda(self):
        self._exec(
            "INSERT INTO rh_ativos (matricula,nome,cpf,situacao) VALUES "
            "('123','ANA SILVA','12345678900','ATIVO');")
        PadronizarRh(self.conexao).executar()
        PadronizarRh(self.conexao).executar()
        row = self._row("SELECT matricula,nome,cpf,situacao FROM rh_ativos")
        self.assertEqual(row, ("123", "ANA SILVA", "12345678900", "ATIVO"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
