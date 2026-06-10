# -*- coding: utf-8 -*-
"""Visualizador: a aba Historico (listar_historico_rh) surfa as linhas ADERENTE
gravadas na tabela `historico` pelo Processador (entidade ACESSO_SISTEMA),
com movimentacao 'Aderente' e o nome lido do dados_novo."""
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import visualizador.main as vm


class TestVisualizadorAderente(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_vader_")
        self._orig = (vm.DB_PATH, vm.PASTA_INTERACOES)
        vm.PASTA_INTERACOES = ""   # sem interacoes vivas

    def tearDown(self):
        vm.DB_PATH, vm.PASTA_INTERACOES = self._orig

    def _db(self, com_historico=True):
        db = os.path.join(self._tmp, "h.db")
        c = sqlite3.connect(db)
        c.executescript(
            "CREATE TABLE bi_divergencias (usuario TEXT, nome_usuario TEXT, "
            "data_identificacao TEXT);"
            "CREATE TABLE resolucoes (registro_id TEXT, ticket TEXT, ticket_url TEXT,"
            " descricao TEXT, pendencias TEXT, cargo TEXT, centro_custo TEXT,"
            " nome TEXT, resolvido_por TEXT, resolvido_em TEXT);"
        )
        if com_historico:
            c.executescript(
                "CREATE TABLE historico (id INTEGER PRIMARY KEY, data_snapshot TEXT,"
                " entidade TEXT, chave_entidade TEXT, tipo_mudanca TEXT,"
                " campos_alterados TEXT, dados_anterior TEXT, dados_novo TEXT,"
                " dt_registro TEXT, tipo TEXT, matricula TEXT);"
            )
            c.execute(
                "INSERT INTO historico (data_snapshot,entidade,chave_entidade,"
                "tipo_mudanca,dados_novo,matricula) VALUES (?,?,?,?,?,?)",
                ("2026-06-10", "ACESSO_SISTEMA", "M1", "ADERENTE",
                 json.dumps({"nome": "FULANO", "sistema": "SYSTUR", "perfil": "P1"}),
                 "M1"))
        c.commit()
        c.close()
        vm.DB_PATH = db

    def test_aderente_aparece_na_trilha(self):
        self._db()
        ader = [r for r in vm.listar_historico_rh() if r.get("tipo") == "ADERENTE"]
        self.assertEqual(len(ader), 1)
        self.assertEqual(ader[0]["matricula"], "M1")
        self.assertEqual(ader[0]["nome"], "FULANO")
        self.assertEqual(ader[0]["movimentacao"], "Aderente")
        self.assertEqual(ader[0]["data"], "2026-06-10")

    def test_sem_tabela_historico_nao_quebra(self):
        # banco antigo sem a tabela historico: a aba so nao mostra aderentes
        self._db(com_historico=False)
        recs = vm.listar_historico_rh()  # nao pode lancar
        self.assertEqual([r for r in recs if r.get("tipo") == "ADERENTE"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
