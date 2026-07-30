# -*- coding: utf-8 -*-
"""Granularidade por ACESSO (item 5 da Bruna, ultimo passo): tratar/quarentenar
UM perfil especifico, nao o sistema inteiro nem a pessoa.

Chave da interacao (sem mudar schema — o freeze de HML vale):
    usuario                      -> a pessoa inteira
    usuario##sistema             -> so aquele sistema
    usuario##sistema##perfil     -> so aquele acesso
"""
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
    # M1: no SYSTUR tem DOIS acessos divergentes (P_A e P_B); no SICA_RA, um.
    c.executescript("""
        INSERT INTO validacao_acessos (matricula,nome,sistema,perfil_esperado,
            perfil_atual,status,situacao_acao,origem_matriz,dt_processamento) VALUES
        ('M1','ANA','SYSTUR','P_OK_A','P_A','DIVERGENTE','PENDENTE','MATRIZ','2026-07-01 10:00:00'),
        ('M1','ANA','SYSTUR','P_OK_B','P_B','DIVERGENTE','PENDENTE','MATRIZ','2026-07-01 10:00:00'),
        ('M1','ANA','SICA_RA','P_OK_C','P_C','DIVERGENTE','PENDENTE','MATRIZ','2026-07-01 10:00:00');
    """)
    c.commit()
    c.close()


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_resperf_")
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

    def _divs(self):
        db = vm.construir_db()
        u = next((x for x in db["users"] if x["u"] == "M1"), None)
        return u, {(d["sis"], d["pe"]): d["s"] for d in (u["divs"] if u else [])}


class TestResolverPorPerfil(_Base):

    def test_resolve_so_o_acesso_alvo(self):
        n = vm.resolver_pendencia("M1", "IAM-1", motivo="Exceção",
                                  sistema="SYSTUR", perfil="P_A")
        self.assertEqual(n, 1)
        u, st = self._divs()
        self.assertEqual(st[("SYSTUR", "P_A")], "Resolvido")   # alvo
        self.assertEqual(st[("SYSTUR", "P_B")], "Pendente")    # mesmo sistema, intacto
        self.assertEqual(st[("SICA_RA", "P_C")], "Pendente")   # outro sistema, intacto
        self.assertFalse(u.get("resolvido"))                   # pessoa segue pendente

    def test_chave_composta_de_tres_partes(self):
        vm.resolver_pendencia("M1", "IAM-1", motivo="Exceção",
                              sistema="SYSTUR", perfil="P_A")
        conteudo = ""
        for f in os.listdir(self.inter):
            with open(os.path.join(self.inter, f), encoding="utf-8") as fh:
                conteudo += fh.read()
        self.assertIn('"registro_id": "M1##SYSTUR##P_A"', conteudo)
        self.assertIn('"perfil": "P_A"', conteudo)

    def test_snapshot_so_do_acesso_alvo(self):
        vm.resolver_pendencia("M1", "IAM-1", motivo="Exceção",
                              sistema="SYSTUR", perfil="P_A")
        reg = None
        for f in os.listdir(self.inter):
            with open(os.path.join(self.inter, f), encoding="utf-8") as fh:
                for linha in fh:
                    reg = json.loads(linha)
        pend = reg["pendencias"]
        self.assertEqual(len(pend), 1, f"snapshot deve ter so o acesso alvo: {pend}")
        self.assertEqual(pend[0]["pe"], "P_A")

    def test_resolver_o_sistema_continua_valendo(self):
        vm.resolver_pendencia("M1", "IAM-9", motivo="Exceção", sistema="SYSTUR")
        _, st = self._divs()
        self.assertEqual(st[("SYSTUR", "P_A")], "Resolvido")
        self.assertEqual(st[("SYSTUR", "P_B")], "Resolvido")
        self.assertEqual(st[("SICA_RA", "P_C")], "Pendente")

    def test_resolver_a_pessoa_continua_valendo(self):
        vm.resolver_pendencia("M1", "IAM-9", motivo="Exceção")
        u, st = self._divs()
        self.assertTrue(all(v == "Resolvido" for v in st.values()))
        self.assertTrue(u.get("resolvido"))

    def test_perfil_sem_sistema_e_ignorado(self):
        # perfil so faz sentido dentro de um sistema: sem sistema, resolve a pessoa
        vm.resolver_pendencia("M1", "IAM-1", motivo="Exceção", perfil="P_A")
        u, _ = self._divs()
        self.assertTrue(u.get("resolvido"))


class TestQuarentenaPorPerfil(_Base):

    def _quar(self, registro_id):
        with open(os.path.join(self.inter, "u.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "tipo_interacao": "QUARENTENA", "registro_id": registro_id,
                "acao": "ENVIAR", "usuario": "user", "data_acao": "2026-07-30T10:00:00",
                "dias": 30, "ticket": "", "titulo": "aguardando", "motivo": ""}) + "\n")

    def test_quarentena_tira_so_o_acesso(self):
        self._quar("M1##SYSTUR##P_A")
        u, st = self._divs()
        self.assertNotIn(("SYSTUR", "P_A"), st)          # saiu da grid
        self.assertEqual(st[("SYSTUR", "P_B")], "Pendente")
        self.assertEqual(st[("SICA_RA", "P_C")], "Pendente")

    def test_quarentena_por_sistema_continua_valendo(self):
        self._quar("M1##SYSTUR")
        _, st = self._divs()
        self.assertEqual({k[0] for k in st}, {"SICA_RA"})

    def test_quarentena_de_todos_os_acessos_some_com_a_pessoa(self):
        for k in ("M1##SYSTUR##P_A", "M1##SYSTUR##P_B", "M1##SICA_RA##P_C"):
            self._quar(k)
        db = vm.construir_db()
        self.assertFalse(any(x["u"] == "M1" for x in db["users"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
