# -*- coding: utf-8 -*-
"""Resolução POR SISTEMA (retorno Bruna item 5): resolver um sistema marca só
aquele como Resolvido; os outros seguem Pendente. Usa a chave composta
`usuario##sistema` — sem mudar schema."""
import json
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import visualizador.main as vm
from infraestrutura.banco_dados.conexao import ConexaoBancoDados


def _seed(db):
    ConexaoBancoDados(db).inicializar()
    c = sqlite3.connect(db)
    # M1: pendência em SYSTUR (DIVERGENTE) e SICA_RA (DIVERGENTE)
    c.executescript("""
        INSERT INTO validacao_acessos (matricula,nome,sistema,perfil_esperado,
            perfil_atual,status,situacao_acao,origem_matriz,dt_processamento) VALUES
        ('M1','ANA','SYSTUR','P_OK','P_ERRADO','DIVERGENTE','PENDENTE','MATRIZ','2026-07-01 10:00:00'),
        ('M1','ANA','SICA_RA','P_OK','P_ERRADO','DIVERGENTE','PENDENTE','MATRIZ','2026-07-01 10:00:00');
    """)
    c.commit()
    c.close()


class TestResolverPorSistema(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_ressis_")
        self.db = os.path.join(self._tmp, "iam.db")
        self.inter = os.path.join(self._tmp, "INTERACOES")
        os.makedirs(self.inter)
        self._orig = (vm.DB_PATH, vm.SISTEMA, vm.PASTA_INTERACOES)
        _seed(self.db)
        vm.DB_PATH = self.db
        vm.SISTEMA = ""
        vm.PASTA_INTERACOES = self.inter
        vm.garantir_estrutura(force=True)

    def tearDown(self):
        vm.DB_PATH, vm.SISTEMA, vm.PASTA_INTERACOES = self._orig

    def _divs_por_sis(self):
        db = vm.construir_db()
        u = next(x for x in db["users"] if x["u"] == "M1")
        return {d["sis"]: d["s"] for d in u["divs"]}, u

    def test_resolver_um_sistema_nao_afeta_o_outro(self):
        # antes: ambos pendentes
        antes, _ = self._divs_por_sis()
        self.assertEqual(antes.get("SYSTUR"), "Pendente")
        self.assertEqual(antes.get("SICA_RA"), "Pendente")
        # resolve SÓ o SYSTUR
        n = vm.resolver_pendencia("M1", "IAM-1", descricao="Parecer do analista.", motivo="Exceção", sistema="SYSTUR")
        self.assertEqual(n, 1)
        depois, u = self._divs_por_sis()
        self.assertEqual(depois.get("SYSTUR"), "Resolvido")     # resolvido
        self.assertEqual(depois.get("SICA_RA"), "Pendente")     # intacto
        # pessoa NÃO está 100% resolvida (ainda tem SICA_RA pendente)
        self.assertFalse(u.get("resolvido"))

    def test_resolver_a_pessoa_inteira_marca_todos(self):
        n = vm.resolver_pendencia("M1", "IAM-9", descricao="Parecer do analista.", motivo="Exceção")   # sem sistema
        self.assertEqual(n, 1)
        depois, u = self._divs_por_sis()
        self.assertEqual(depois.get("SYSTUR"), "Resolvido")
        self.assertEqual(depois.get("SICA_RA"), "Resolvido")
        self.assertTrue(u.get("resolvido"))

    def test_interacao_gravada_com_chave_composta(self):
        vm.resolver_pendencia("M1", "IAM-1", descricao="Parecer do analista.", motivo="Exceção", sistema="SYSTUR")
        conteudo = ""
        for f in os.listdir(self.inter):
            with open(os.path.join(self.inter, f), encoding="utf-8") as fh:
                conteudo += fh.read()
        # registro_id composto + campo sistema
        self.assertIn('"registro_id": "M1##SYSTUR"', conteudo)
        self.assertIn('"sistema": "SYSTUR"', conteudo)


class TestQuarentenaPorSistema(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_quarsis_")
        self.db = os.path.join(self._tmp, "iam.db")
        self.inter = os.path.join(self._tmp, "INTERACOES")
        os.makedirs(self.inter)
        self._orig = (vm.DB_PATH, vm.SISTEMA, vm.PASTA_INTERACOES)
        _seed(self.db)
        vm.DB_PATH = self.db
        vm.SISTEMA = ""
        vm.PASTA_INTERACOES = self.inter
        vm.garantir_estrutura(force=True)

    def tearDown(self):
        vm.DB_PATH, vm.SISTEMA, vm.PASTA_INTERACOES = self._orig

    def _quar(self, registro_id):
        with open(os.path.join(self.inter, "u.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "tipo_interacao": "QUARENTENA", "registro_id": registro_id,
                "acao": "ENVIAR", "usuario": "user", "data_acao": "2026-07-29T10:00:00",
                "dias": 30, "ticket": "", "titulo": "aguardando", "motivo": ""}) + "\n")

    def test_quarentena_um_sistema_remove_so_ele(self):
        self._quar("M1##SYSTUR")   # quarentena SÓ o SYSTUR
        db = vm.construir_db()
        u = next(x for x in db["users"] if x["u"] == "M1")
        sistemas = {d["sis"] for d in u["divs"]}
        self.assertNotIn("SYSTUR", sistemas)   # em quarentena -> fora da grid
        self.assertIn("SICA_RA", sistemas)     # segue aparecendo

    def test_quarentena_pessoa_inteira_remove_todos(self):
        self._quar("M1")           # pessoa inteira
        db = vm.construir_db()
        self.assertFalse(any(x["u"] == "M1" for x in db["users"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
