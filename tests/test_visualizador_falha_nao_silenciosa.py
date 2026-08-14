# -*- coding: utf-8 -*-
"""As leituras de tratativa nao podem falhar em silencio.

`_resolucoes_db`, `_tratamentos_desligado_db`, `_tratamentos_transferido_db` e
`_transferidos_depara` devolvem `{}` em qualquer excecao — e devolver `{}` NAO e'
neutro: a tela passa a mostrar como PENDENTE tudo o que ja' foi tratado, e o
analista refaz tratativa que existe. O erro nao pode derrubar o painel (por isso
o `{}` fica), mas tem de aparecer no log.

Este teste fixa esse contrato: em falha, devolve `{}` E imprime aviso. Sem ele,
uma simplificacao futura ("o except nao faz nada mesmo") reintroduz o silencio.
"""
import io
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
import visualizador.main as vm


class FalhaDeLeituraAvisa(unittest.TestCase):
    """Tabela existe mas esta ilegivel — o caso que o `{}` mascarava."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "iam.db")
        ConexaoBancoDados(self.db).inicializar()
        self._db_orig = vm.DB_PATH
        vm.DB_PATH = self.db

    def tearDown(self):
        vm.DB_PATH = self._db_orig

    def _corromper(self, tabela):
        """Deixa a tabela presente mas com as colunas erradas: a checagem de
        existencia passa, o SELECT estoura. E' o formato real da falha —
        banco de versao diferente da que o painel espera."""
        c = sqlite3.connect(self.db)
        try:
            c.execute(f"DROP TABLE IF EXISTS {tabela}")
            c.execute(f"CREATE TABLE {tabela} (registro_id TEXT)")
            c.commit()
        finally:
            c.close()

    def _rodar(self, fn):
        buf = io.StringIO()
        with redirect_stdout(buf):
            r = fn()
        return r, buf.getvalue()

    def test_resolucoes_avisa(self):
        self._corromper("resolucoes")
        r, saida = self._rodar(vm._resolucoes_db)
        self.assertEqual(r, {})
        self.assertIn("RESOL", saida)

    def test_tratamentos_desligado_avisa(self):
        self._corromper("tratamentos_desligado")
        r, saida = self._rodar(vm._tratamentos_desligado_db)
        self.assertEqual(r, {})
        self.assertIn("TRAT-DESL", saida)

    def test_tratamentos_transferido_avisa(self):
        self._corromper("tratamentos_transferido")
        r, saida = self._rodar(vm._tratamentos_transferido_db)
        self.assertEqual(r, {})
        self.assertIn("TRAT-TRANSF", saida)

    def test_transferidos_depara_avisa(self):
        self._corromper("transferidos")
        c = sqlite3.connect(self.db)
        c.row_factory = sqlite3.Row
        try:
            r, saida = self._rodar(lambda: vm._transferidos_depara(c, ["M1"]))
        finally:
            c.close()
        self.assertEqual(r, {})
        self.assertIn("transf", saida)


class AusenciaPrevistaNaoPoluiOLog(unittest.TestCase):
    """Banco de um Processador anterior NAO tem as tabelas — isso e' previsto e
    tem de seguir silencioso, senao o log vira ruido a cada request e o aviso
    de verdade se perde no meio."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "vazio.db")
        sqlite3.connect(self.db).close()      # banco sem tabela nenhuma
        self._db_orig = vm.DB_PATH
        vm.DB_PATH = self.db

    def tearDown(self):
        vm.DB_PATH = self._db_orig

    def test_sem_tabelas_nao_avisa(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(vm._resolucoes_db(), {})
            self.assertEqual(vm._tratamentos_desligado_db(), {})
            self.assertEqual(vm._tratamentos_transferido_db(), {})
        self.assertEqual(buf.getvalue().strip(), "",
                         "ausencia de tabela e' previsto — nao deve logar")


if __name__ == "__main__":
    unittest.main()
