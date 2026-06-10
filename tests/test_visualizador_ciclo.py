# -*- coding: utf-8 -*-
"""Visualizador (listar_historico_rh): surfa a trilha do ciclo persistida em
`historico` (ACESSO_SISTEMA) e NAO duplica com as resolucoes ao vivo.

- Caso organico (sem resolucao): mostra PENDENCIA + ADERENTE persistidas.
- Caso com resolucao: as linhas ricas (read-time) cobrem Pendencia/Resolvida;
  as PENDENCIA/RESOLVIDO persistidas sao puladas; a ADERENTE persistida entra.
"""
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import visualizador.main as vm


def _dados(**kw):
    return json.dumps(kw, ensure_ascii=False)


class TestVisualizadorCiclo(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_vclh_")
        self._orig = (vm.DB_PATH, vm.PASTA_INTERACOES)
        vm.PASTA_INTERACOES = ""   # sem interacoes vivas

    def tearDown(self):
        vm.DB_PATH, vm.PASTA_INTERACOES = self._orig

    def _conn(self, com_historico=True):
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
            c.execute(
                "CREATE TABLE historico (id INTEGER PRIMARY KEY, data_snapshot TEXT,"
                " entidade TEXT, chave_entidade TEXT, tipo_mudanca TEXT,"
                " campos_alterados TEXT, dados_anterior TEXT, dados_novo TEXT,"
                " dt_registro TEXT, tipo TEXT, matricula TEXT)")
        vm.DB_PATH = db
        return c

    def _hist(self, c, mat, tipo, data, **dados):
        c.execute(
            "INSERT INTO historico (data_snapshot,entidade,chave_entidade,"
            "tipo_mudanca,dados_novo,matricula) VALUES (?,?,?,?,?,?)",
            (data[:10], "ACESSO_SISTEMA", mat, tipo,
             _dados(data=data, nome=dados.get("nome", mat), **{k: v for k, v in dados.items() if k != "nome"}),
             mat))

    def test_organico_pendencia_e_aderente(self):
        c = self._conn()
        self._hist(c, "M1", "PENDENCIA", "2026-06-01 09:00:00", nome="ANA")
        self._hist(c, "M1", "ADERENTE", "2026-06-10 10:00:00", nome="ANA")
        c.commit(); c.close()
        recs = [r for r in vm.listar_historico_rh() if r["matricula"] == "M1"]
        tipos = sorted(r["tipo"] for r in recs)
        self.assertEqual(tipos, ["ADERENTE", "PENDENCIA"])
        ader = next(r for r in recs if r["tipo"] == "ADERENTE")
        self.assertEqual(ader["movimentacao"], "Aderente")
        self.assertEqual(ader["nome"], "ANA")

    def test_dedup_com_resolucao_nao_duplica_pendencia(self):
        c = self._conn()
        # resolucao dobrada (read-time monta Pendencia + Resolvida ricas)
        c.execute("INSERT INTO bi_divergencias VALUES (?,?,?)",
                  ("RES1", "BIA", "2026-06-01 09:00:00"))
        c.execute("INSERT INTO resolucoes VALUES (?,?,?,?,?,?,?,?,?,?)",
                  ("RES1", "JIRA-1", "", "", json.dumps([]), "CARGO", "cc",
                   "BIA", "user", "2026-06-05 14:00:00"))
        # mesmas linhas persistidas pelo processador + a ADERENTE
        self._hist(c, "RES1", "PENDENCIA", "2026-06-01 09:00:00", nome="BIA")
        self._hist(c, "RES1", "RESOLVIDO", "2026-06-05 14:00:00", nome="BIA", ticket="JIRA-1")
        self._hist(c, "RES1", "ADERENTE", "2026-06-10 10:00:00", nome="BIA")
        c.commit(); c.close()
        recs = [r for r in vm.listar_historico_rh() if r["matricula"] == "RES1"]
        tipos = sorted(r["tipo"] for r in recs)
        # 1 pendencia (read-time), 1 resolucao (read-time), 1 aderente (persistida)
        self.assertEqual(tipos, ["ADERENTE", "PENDENCIA", "RESOLUCAO"])
        self.assertEqual(sum(1 for r in recs if r["tipo"] == "PENDENCIA"), 1)

    def test_sem_tabela_historico_nao_quebra(self):
        c = self._conn(com_historico=False)
        c.commit(); c.close()
        recs = vm.listar_historico_rh()  # nao pode lancar
        self.assertEqual([r for r in recs if r.get("tipo") in
                          ("ADERENTE", "PENDENCIA", "RESOLUCAO")], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
