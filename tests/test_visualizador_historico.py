# -*- coding: utf-8 -*-
"""Cronologia da trilha de pendencias no Visualizador (listar_historico_rh):
a "Pendencia identificada" NUNCA pode ser DEPOIS da "Pendencia resolvida".

Bug real (matricula 13922 / login AGEV0115): a pessoa resolveu a pendencia e
DEPOIS virou Aderente/OK. O bi_divergencias passou a guardar so a linha OK com a
data do REPROCESSO (data_identificacao > resolvido_em), invertendo a cronologia.
Fix: a identificada e' limitada pela propria data de resolucao.
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

LOGIN = "AGEV0115"
RESOLVIDO_EM = "2026-05-29T17:46:07"


def _criar_db(db, data_identificacao):
    """data_identificacao=None -> NAO cria linha no bi (pessoa saiu do bi)."""
    c = sqlite3.connect(db)
    c.executescript(
        "CREATE TABLE bi_divergencias (usuario TEXT, nome_usuario TEXT, "
        "data_identificacao TEXT);"
        "CREATE TABLE resolucoes (registro_id TEXT, ticket TEXT, ticket_url TEXT,"
        " descricao TEXT, pendencias TEXT, cargo TEXT, centro_custo TEXT,"
        " nome TEXT, resolvido_por TEXT, resolvido_em TEXT);"
    )
    if data_identificacao is not None:
        c.execute("INSERT INTO bi_divergencias VALUES (?,?,?)",
                  (LOGIN, "JOICE AQUINO VELLOSO", data_identificacao))
    c.execute("INSERT INTO resolucoes VALUES (?,?,?,?,?,?,?,?,?,?)",
              (LOGIN, "1231223", "", "", json.dumps([]), "ASSISTENTE",
               "05.02.07.08", "JOICE AQUINO VELLOSO", "user", RESOLVIDO_EM))
    c.commit()
    c.close()


class TestHistoricoCronologia(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_hist_")
        self._orig = (vm.DB_PATH, vm.PASTA_INTERACOES)
        vm.PASTA_INTERACOES = ""   # sem interacoes vivas: so o banco dobrado

    def tearDown(self):
        vm.DB_PATH, vm.PASTA_INTERACOES = self._orig

    def _par(self, data_identificacao):
        db = os.path.join(self._tmp, "h.db")
        _criar_db(db, data_identificacao)
        vm.DB_PATH = db
        recs = vm.listar_historico_rh()
        pend = next(r for r in recs
                    if r["tipo"] == "PENDENCIA" and r["matricula"] == LOGIN)
        resol = next(r for r in recs
                     if r["tipo"] == "RESOLUCAO" and r["matricula"] == LOGIN)
        return pend, resol

    def test_identificada_posterior_e_limitada_pela_resolvida(self):
        # bug 13922: data_identificacao (reprocesso de hoje) > resolvido_em
        pend, resol = self._par("2026-06-09 18:16:18")
        self.assertLessEqual(pend["data"], resol["data"])      # cronologia OK
        self.assertEqual(pend["data"], RESOLVIDO_EM)           # limitada pela resolucao

    def test_eventos_por_sistema_e_reabertura(self):
        # NOVO caminho: listar_historico_rh le ciclo_eventos_acesso e abre por
        # (matricula, sistema), com reabertura (ciclo 2). Caso 2084.
        db = os.path.join(self._tmp, "ev.db")
        c = sqlite3.connect(db)
        c.executescript(
            "CREATE TABLE bi_divergencias (usuario TEXT, nome_usuario TEXT, data_identificacao TEXT);"
            "CREATE TABLE resolucoes (registro_id TEXT, ticket TEXT, ticket_url TEXT,"
            " descricao TEXT, pendencias TEXT, cargo TEXT, centro_custo TEXT,"
            " nome TEXT, resolvido_por TEXT, resolvido_em TEXT);"
            "CREATE TABLE ciclo_eventos_acesso (id INTEGER PRIMARY KEY, matricula TEXT,"
            " sistema TEXT, ciclo INTEGER, tipo_evento TEXT, data_evento TEXT,"
            " perfil TEXT, nome TEXT, login TEXT, cargo TEXT, ticket TEXT, detalhe TEXT,"
            " dt_registro TEXT);"
        )
        c.executemany(
            "INSERT INTO ciclo_eventos_acesso (matricula,sistema,ciclo,tipo_evento,"
            "data_evento,nome) VALUES (?,?,?,?,?,?)",
            [("2084", "SICA_RA", 1, "ADERENTE", "2026-06-10 14:00:00", "Maria"),
             ("2084", "SYSTUR", 1, "PENDENCIA", "2026-06-01 09:00:00", "Maria"),
             ("2084", "SYSTUR", 1, "ADERENTE", "2026-06-05 09:00:00", "Maria"),
             ("2084", "SYSTUR", 2, "PENDENCIA", "2026-07-15 08:00:00", "Maria")])
        c.commit(); c.close()
        vm.DB_PATH = db
        recs = [r for r in vm.listar_historico_rh() if r["matricula"] == "2084"]
        # SICA_RA aderente e SYSTUR separados, cada um com seu sistema
        sica = [r for r in recs if r.get("sistema") == "SICA_RA"]
        systur = [r for r in recs if r.get("sistema") == "SYSTUR"]
        self.assertEqual([r["tipo"] for r in sica], ["ADERENTE"])
        self.assertEqual(len(systur), 3)  # pend c1, ader c1, reabertura c2
        # a reabertura (ciclo 2) vem marcada
        reab = [r for r in systur if r.get("reaberta")]
        self.assertEqual(len(reab), 1)
        self.assertEqual(reab[0]["movimentacao"], "Pendência reaberta")
        self.assertEqual(reab[0]["ciclo"], 2)

    def test_identificada_anterior_e_preservada(self):
        # caso normal: identificada ANTES da resolucao -> mantem a data original
        pend, resol = self._par("2026-05-20 09:00:00")
        self.assertLessEqual(pend["data"], resol["data"])
        self.assertEqual(pend["data"], "2026-05-20 09:00:00")  # nao mexe

    def test_resolucao_sempre_presente_no_par(self):
        # toda resolucao gera o par identificada+resolvida (rastreabilidade)
        pend, resol = self._par("2026-06-09 18:16:18")
        self.assertEqual(resol["data"], RESOLVIDO_EM)
        self.assertEqual(resol["campos"], "1231223")          # ticket na resolvida

    def test_resolucao_sem_linha_no_bi_usa_a_data_de_resolucao(self):
        # Pessoa saiu do bi (desligada / acesso mudou) mas a resolucao existe:
        # sem data_identificacao, a identificada cai na data de resolucao (nao
        # fica vazia nem depois da resolvida). Exercita o branch `not dt_pend`.
        pend, resol = self._par(None)                          # None = sem linha no bi
        self.assertEqual(pend["data"], RESOLVIDO_EM)
        self.assertLessEqual(pend["data"], resol["data"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
