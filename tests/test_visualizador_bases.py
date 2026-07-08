# -*- coding: utf-8 -*-
"""Painel "Bases" do Visualizador: listar_bases agrupa RH/Matrizes/Sistemas e
mostra SO a ULTIMA importacao por tipo (nome do arquivo + data do proprio
arquivo). Monkeypatch dos globais, sem servidor.
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
import visualizador.main as vm


class TestListarBases(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_bases_")
        self.db = os.path.join(self._tmp, "iam.db")
        ConexaoBancoDados(self.db).inicializar()
        self._orig = vm.DB_PATH
        vm.DB_PATH = self.db
        self.addCleanup(lambda: setattr(vm, "DB_PATH", self._orig))

    def _log(self, tipo, arquivo, dt_arquivo, dt_importacao, status="SUCESSO"):
        c = sqlite3.connect(self.db)
        c.execute(
            "INSERT INTO log_importacoes (arquivo,tipo,total_registros,status,"
            "hash_arquivo,dt_importacao,dt_arquivo) VALUES (?,?,?,?,?,?,?)",
            [arquivo, tipo, 1, status, "", dt_importacao, dt_arquivo])
        c.commit(); c.close()

    def test_agrupa_e_pega_ultima_importacao(self):
        # duas importacoes do MESMO tipo -> so a mais recente aparece
        self._log("SYSTUR", "systur_velho.xlsx", "2026-03-01 10:00:00", "2026-03-01 12:00:00")
        self._log("SYSTUR", "systur_novo.xlsx", "2026-04-30 10:00:00", "2026-05-15 12:00:00")
        self._log("RH_ATIVOS", "PROJETOIAM.CSV", "2026-04-30 08:00:00", "2026-05-15 12:00:00")
        self._log("MATRIZ_PERFIS", "MATRIZ SYSTUR.xlsx", "2026-04-29 08:00:00", "2026-05-15 12:00:00")

        out = vm.listar_bases()
        grupos = {g["grupo"]: g["itens"] for g in out}
        self.assertEqual([g["grupo"] for g in out], ["RH", "Matrizes", "Extratos dos Sistemas"])

        systur = next(i for i in grupos["Extratos dos Sistemas"] if i["base"] == "SYSTUR")
        self.assertEqual(systur["arquivo"], "systur_novo.xlsx")     # a mais recente
        self.assertEqual(systur["dt_arquivo"], "2026-04-30 10:00:00")
        self.assertEqual(grupos["RH"][0]["base"], "Funcionários Ativos")
        self.assertEqual(grupos["Matrizes"][0]["base"], "Matriz de Perfis de Acesso")

    def test_status_erro_nao_aparece(self):
        self._log("SIGOT", "sigot_ruim.csv", "2026-04-30 10:00:00", "2026-05-15 12:00:00",
                  status="ERRO")
        out = vm.listar_bases()
        self.assertEqual(out, [])

    def test_sem_importacoes_lista_vazia(self):
        self.assertEqual(vm.listar_bases(), [])

    def test_base_sem_coluna_dt_arquivo_nao_quebra(self):
        # Visualizador apontado p/ base ainda nao migrada (sem dt_arquivo):
        # mostra o arquivo, data vazia, sem erro.
        c = sqlite3.connect(self.db)
        c.execute("ALTER TABLE log_importacoes RENAME TO _li")
        c.execute("CREATE TABLE log_importacoes (id INTEGER PRIMARY KEY, arquivo TEXT, "
                  "tipo TEXT, total_registros INT, status TEXT, mensagem_erro TEXT, "
                  "hash_arquivo TEXT, dt_importacao DATETIME)")  # sem dt_arquivo
        c.execute("INSERT INTO log_importacoes (arquivo,tipo,total_registros,status,"
                  "hash_arquivo,dt_importacao) VALUES "
                  "('systur.xlsx','SYSTUR',1,'SUCESSO','','2026-05-15 12:00:00')")
        c.commit(); c.close()
        out = vm.listar_bases()
        item = out[0]["itens"][0]
        self.assertEqual(item["base"], "SYSTUR")
        self.assertEqual(item["arquivo"], "systur.xlsx")
        self.assertEqual(item["dt_arquivo"], "")

    def test_dt_arquivo_nulo_vira_string_vazia(self):
        self._log("IC_INTEGRADOR_CONTABIL", "ic.xlsx", None, "2026-05-15 12:00:00")
        out = vm.listar_bases()
        item = out[0]["itens"][0]
        self.assertEqual(item["dt_arquivo"], "")
        self.assertEqual(item["base"], "IC — Integrador Contábil")


if __name__ == "__main__":
    unittest.main(verbosity=2)
