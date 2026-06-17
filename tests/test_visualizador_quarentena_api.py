# -*- coding: utf-8 -*-
"""Funcoes client-facing de quarentena do Visualizador: listar_quarentena
(tabela + overlay vivo) e os writes retirar_quarentena / resolver_pendencia
(gravam interacoes na rede). Monkeypatch dos globais, sem servidor.
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.interacoes import repositorio_interacoes as ri
import visualizador.main as vm

IC = "IC_INTEGRADOR_CONTABIL"


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_qapi_")
        self.db = os.path.join(self._tmp, "iam.db")
        self.inter = os.path.join(self._tmp, "INTERACOES")
        os.makedirs(self.inter)
        ConexaoBancoDados(self.db).inicializar()
        self._orig = (vm.DB_PATH, vm.PASTA_INTERACOES, vm.SISTEMA, vm._BASE)
        vm.DB_PATH = self.db
        vm.PASTA_INTERACOES = self.inter
        vm.SISTEMA = ""
        vm._BASE = None
        vm.garantir_estrutura(force=True)   # cria quarentena/historico/bi
        self.addCleanup(self._restore)

    def _restore(self):
        vm.DB_PATH, vm.PASTA_INTERACOES, vm.SISTEMA, vm._BASE = self._orig

    def _q_ins(self, usuario, data_fim="2099-12-31"):
        c = sqlite3.connect(self.db)
        c.execute(
            "INSERT INTO quarentena (usuario,nome_usuario,sistema,matricula,origem,"
            "data_inicio,data_fim,status,criado_por,criado_em) "
            "VALUES (?,?,?,?,?,?,?, 'Em quarentena', 'op', '2026-05-01')",
            [usuario, usuario, IC, usuario, "Inclusão", "2026-05-01", data_fim])
        c.commit(); c.close()

    def _h_ins(self, usuario):
        c = sqlite3.connect(self.db)
        c.execute(
            "INSERT INTO quarentena_historico (usuario,nome_usuario,sistema,matricula,"
            "origem,data_inicio,data_fim,data_saida,motivo,criado_por,criado_em,"
            "encerrado_por,movido_em) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [usuario, usuario, IC, usuario, "Inclusão", "2026-05-01", "2026-08-01",
             "2026-05-10", "Resolvido", "op", "2026-05-01", "op2", "2026-05-10 09:00:00"])
        c.commit(); c.close()


class TestListarQuarentena(_Base):

    def test_ativas_e_historico_da_tabela(self):
        self._q_ins("U1")
        self._h_ins("U2")
        out = vm.listar_quarentena()
        self.assertEqual([a["usuario"] for a in out["ativas"]], ["U1"])
        self.assertGreater(out["ativas"][0]["dias_restantes"], 0)
        self.assertEqual([h["usuario"] for h in out["historico"]], ["U2"])
        self.assertEqual(out["historico"][0]["periodo_dias"], 9)   # 01->10 maio

    def test_overlay_vivo_enviar_e_resolver(self):
        self._q_ins("U1")
        # ENVIAR vivo de um novo -> entra em ativas; RESOLVER vivo de U1 -> sai
        ri.gravar(self.inter, {"tipo_interacao": "QUARENTENA", "registro_id": "U9",
                               "acao": "ENVIAR", "nome": "U9", "sistema": IC,
                               "data_acao": "2026-06-01T10:00:00"}, "op")
        ri.gravar(self.inter, {"tipo_interacao": "QUARENTENA", "registro_id": "U1",
                               "acao": "RESOLVER", "data_acao": "2026-06-02T10:00:00"}, "op")
        out = vm.listar_quarentena()
        ativas = {a["usuario"] for a in out["ativas"]}
        self.assertEqual(ativas, {"U9"})                          # U1 saiu, U9 entrou
        self.assertIn("U1", {h["usuario"] for h in out["historico"]})


class TestWritesQuarentena(_Base):

    def _interacoes(self):
        return ri.ler_todas(self.inter)

    def test_retirar_quarentena_grava_resolver(self):
        n = vm.retirar_quarentena("R1", "saiu por teste")
        self.assertEqual(n, 1)
        its = [i for i in self._interacoes()
               if i.get("tipo_interacao") == "QUARENTENA" and i.get("acao") == "RESOLVER"]
        self.assertEqual([i["registro_id"] for i in its], ["R1"])
        self.assertEqual(its[0]["motivo"], "saiu por teste")

    def test_retirar_quarentena_id_vazio_nao_grava(self):
        self.assertEqual(vm.retirar_quarentena("", "m"), 0)
        self.assertEqual(self._interacoes(), [])

    def test_retirar_quarentena_sem_motivo_nao_grava(self):
        # motivo e' OBRIGATORIO na retirada
        self.assertEqual(vm.retirar_quarentena("R1", ""), 0)
        self.assertEqual(self._interacoes(), [])

    def test_resolver_pendencia_grava_resolucao(self):
        n = vm.resolver_pendencia("R1", ticket="IAM-123", descricao="ok")
        self.assertEqual(n, 1)
        res = [i for i in self._interacoes() if i.get("tipo_interacao") == "RESOLUCAO"]
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["registro_id"], "R1")
        self.assertEqual(res[0]["ticket"], "IAM-123")

    def test_resolver_pendencia_sem_ticket_nao_grava(self):
        self.assertEqual(vm.resolver_pendencia("R1", ticket=""), 0)
        self.assertEqual(self._interacoes(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
