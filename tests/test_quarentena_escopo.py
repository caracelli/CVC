# -*- coding: utf-8 -*-
"""Aba Quarentena com a chave composta (envio por SISTEMA e por ACESSO).

O envio ja gravava `usuario##sistema[##perfil]`, mas a LISTAGEM mostrava a chave
crua na coluna Usuario e o lookup de vinculo no RH nao casava (procurava a
matricula "M1##SYSTUR##P_A"). Agora a listagem devolve matricula, sistema,
perfil e o ESCOPO (Pessoa/Sistema/Acesso) separados, e o `id` (usado para
retirar) continua sendo a chave inteira.
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
    c.executescript("""
        INSERT INTO rh_ativos (matricula,nome,cpf,situacao,tipo_vinculo) VALUES
        ('M1','ANA','11122233344','ATIVO','TERCEIRO');
        INSERT INTO validacao_acessos (matricula,nome,sistema,perfil_esperado,
            perfil_atual,status,situacao_acao,origem_matriz,dt_processamento) VALUES
        ('M1','ANA','SYSTUR','P_OK_A','P_A','DIVERGENTE','PENDENTE','MATRIZ','2026-07-01 10:00:00'),
        ('M1','ANA','SYSTUR','P_OK_B','P_B','DIVERGENTE','PENDENTE','MATRIZ','2026-07-01 10:00:00');
    """)
    c.commit()
    c.close()


class TestQuarentenaEscopo(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_quaresc_")
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

    def _ativa(self):
        ativas = vm.listar_quarentena()["ativas"]
        self.assertEqual(len(ativas), 1, ativas)
        return ativas[0]

    def test_envio_por_acesso(self):
        vm.enviar_quarentena(["M1##SYSTUR##P_A"], dias=30, titulo="aguardando")
        q = self._ativa()
        self.assertEqual(q["id"], "M1##SYSTUR##P_A")      # chave inteira (p/ retirar)
        self.assertEqual(q["usuario"], "M1")              # coluna Usuario limpa
        self.assertEqual(q["sistema"], "SYSTUR")
        self.assertEqual(q["perfil"], "P_A")
        self.assertEqual(q["escopo"], "Acesso")
        self.assertEqual(q["vinc"], "Terceiro")           # lookup no RH voltou a casar

    def test_envio_por_sistema(self):
        vm.enviar_quarentena(["M1##SYSTUR"], dias=15, titulo="aguardando")
        q = self._ativa()
        self.assertEqual(q["usuario"], "M1")
        self.assertEqual(q["sistema"], "SYSTUR")
        self.assertEqual(q["perfil"], "")
        self.assertEqual(q["escopo"], "Sistema")

    def test_envio_da_pessoa_inteira(self):
        vm.enviar_quarentena(["M1"], dias=10, titulo="aguardando")
        q = self._ativa()
        self.assertEqual(q["usuario"], "M1")
        self.assertEqual(q["escopo"], "Pessoa")

    def test_grid_perde_so_o_acesso_quarentenado(self):
        vm.enviar_quarentena(["M1##SYSTUR##P_A"], dias=30, titulo="x")
        u = next(x for x in vm.construir_db()["users"] if x["u"] == "M1")
        self.assertEqual({d["pe"] for d in u["divs"]}, {"P_B"})

    def test_retirar_usa_a_chave_inteira_e_devolve_o_acesso(self):
        vm.enviar_quarentena(["M1##SYSTUR##P_A"], dias=30, titulo="x")
        self.assertEqual(vm.retirar_quarentena("M1##SYSTUR##P_A", "voltou"), 1)
        self.assertEqual(vm.listar_quarentena()["ativas"], [])
        u = next(x for x in vm.construir_db()["users"] if x["u"] == "M1")
        self.assertEqual({d["pe"] for d in u["divs"]}, {"P_A", "P_B"})   # devolvido

    def test_historico_tambem_separa_o_escopo(self):
        vm.enviar_quarentena(["M1##SYSTUR##P_A"], dias=30, titulo="x")
        vm.retirar_quarentena("M1##SYSTUR##P_A", "voltou")
        hist = vm.listar_quarentena()["historico"]
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist[0]["usuario"], "M1")
        self.assertEqual(hist[0]["escopo"], "Acesso")
        self.assertEqual(hist[0]["perfil"], "P_A")
        self.assertEqual(hist[0]["id"], "M1##SYSTUR##P_A")

    def test_dois_acessos_da_mesma_pessoa_convivem(self):
        vm.enviar_quarentena(["M1##SYSTUR##P_A"], dias=30, titulo="x")
        vm.enviar_quarentena(["M1##SYSTUR##P_B"], dias=10, titulo="y")
        ativas = vm.listar_quarentena()["ativas"]
        self.assertEqual(len(ativas), 2)
        self.assertEqual({q["perfil"] for q in ativas}, {"P_A", "P_B"})
        self.assertTrue(all(q["usuario"] == "M1" for q in ativas))
        # a pessoa sai da grid (todos os acessos quarentenados)
        self.assertFalse(any(x["u"] == "M1" for x in vm.construir_db()["users"]))

    def test_interacao_grava_o_perfil(self):
        vm.enviar_quarentena(["M1##SYSTUR##P_A"], dias=30, titulo="x")
        conteudo = ""
        for f in os.listdir(self.inter):
            with open(os.path.join(self.inter, f), encoding="utf-8") as fh:
                conteudo += fh.read()
        reg = json.loads([l for l in conteudo.splitlines() if l.strip()][-1])
        self.assertEqual(reg["registro_id"], "M1##SYSTUR##P_A")
        self.assertEqual(reg["sistema"], "SYSTUR")
        self.assertEqual(reg["perfil"], "P_A")


if __name__ == "__main__":
    unittest.main(verbosity=2)
