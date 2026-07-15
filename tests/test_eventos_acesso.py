# -*- coding: utf-8 -*-
"""RegistrarEventosAcesso — log de eventos por (matricula, sistema) com ciclos.

Cobre: abertura (pendente/aderente-direto), pendente->resolvido->aderente,
multi-sistema separado (caso 2084), REABERTURA (aderente -> nova pendencia =
ciclo 2), idempotencia e o guard de que a resolucao do ciclo 1 nao vaza pro 2.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy import text

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from aplicacao.casos_de_uso.registrar_eventos_acesso import RegistrarEventosAcesso

AG = "2026-07-15 09:00:00"


class TestEventosAcesso(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.mkdtemp(prefix="cvc_evac_")
        self.cx = ConexaoBancoDados(os.path.join(tmp, "d.db"))
        self.cx.inicializar()

    # ---- helpers ----
    def _val(self, mat, sis, status, perfil="P1"):
        with self.cx.sessao() as s:
            s.execute(text(
                "INSERT INTO validacao_acessos (matricula,sistema,status,perfil_esperado) "
                "VALUES (:m,:s,:st,:p)"), {"m": mat, "s": sis, "st": status, "p": perfil})
            s.commit()

    def _cv(self, mat, sis, dt_resolvido=None, ticket=None):
        with self.cx.sessao() as s:
            s.execute(text(
                "INSERT INTO ciclo_vida_acesso (matricula,sistema,perfil,nome,login,cargo,"
                "dt_pendencia,dt_resolvido,ticket,dt_aderente,dt_atualizacao) "
                "VALUES (:m,:s,'P1','Nome','lg','CARGO',NULL,:dr,:tk,NULL,'x')"),
                {"m": mat, "s": sis, "dr": dt_resolvido, "tk": ticket})
            s.commit()

    def _ev(self, mat, sis, ciclo, tipo, data=AG):
        with self.cx.sessao() as s:
            s.execute(text(
                "INSERT INTO ciclo_eventos_acesso (matricula,sistema,ciclo,tipo_evento,data_evento) "
                "VALUES (:m,:s,:c,:t,:d)"), {"m": mat, "s": sis, "c": ciclo, "t": tipo, "d": data})
            s.commit()

    def _eventos(self, mat, sis):
        with self.cx.sessao() as s:
            rows = s.execute(text(
                "SELECT ciclo,tipo_evento FROM ciclo_eventos_acesso "
                "WHERE matricula=:m AND sistema=:s "
                "ORDER BY ciclo, CASE tipo_evento WHEN 'PENDENCIA' THEN 0 "
                "WHEN 'RESOLVIDO' THEN 1 ELSE 2 END"),
                {"m": mat, "s": sis}).fetchall()
        return [(r[0], r[1]) for r in rows]

    # ---- casos ----
    def test_abre_pendencia_ciclo1(self):
        self._val("M1", "SYSTUR", "DIVERGENTE")
        self.assertEqual(RegistrarEventosAcesso(self.cx).executar(AG), 1)
        self.assertEqual(self._eventos("M1", "SYSTUR"), [(1, "PENDENCIA")])

    def test_aderente_direto_ciclo1(self):
        self._val("M1", "SYSTUR", "OK")
        self.assertEqual(RegistrarEventosAcesso(self.cx).executar(AG), 1)
        self.assertEqual(self._eventos("M1", "SYSTUR"), [(1, "ADERENTE")])

    def test_pendente_resolvido_aderente(self):
        # pendente na 1a rodada
        self._ev("M1", "SYSTUR", 1, "PENDENCIA", "2026-06-01 09:00:00")
        # resolucao chega + acesso vira OK
        self._cv("M1", "SYSTUR", dt_resolvido="2026-06-05 10:00:00", ticket="INC-9")
        self._val("M1", "SYSTUR", "OK")
        self.assertEqual(RegistrarEventosAcesso(self.cx).executar(AG), 2)
        self.assertEqual(self._eventos("M1", "SYSTUR"),
                         [(1, "PENDENCIA"), (1, "RESOLVIDO"), (1, "ADERENTE")])

    def test_2084_multisistema_separado(self):
        self._val("2084", "SICA_RA", "OK")
        self._val("2084", "SYSTUR", "DIVERGENTE")
        RegistrarEventosAcesso(self.cx).executar(AG)
        self.assertEqual(self._eventos("2084", "SICA_RA"), [(1, "ADERENTE")])
        self.assertEqual(self._eventos("2084", "SYSTUR"), [(1, "PENDENCIA")])

    def test_reabertura_vira_ciclo2(self):
        # ja aderente (ciclo 1 fechado)
        self._ev("M1", "SYSTUR", 1, "ADERENTE", "2026-06-02 09:00:00")
        # agora a validacao volta a acusar pendencia
        self._val("M1", "SYSTUR", "DIVERGENTE")
        self.assertEqual(RegistrarEventosAcesso(self.cx).executar(AG), 1)
        self.assertEqual(self._eventos("M1", "SYSTUR"),
                         [(1, "ADERENTE"), (2, "PENDENCIA")])

    def test_idempotente(self):
        self._val("M1", "SYSTUR", "OK")
        RegistrarEventosAcesso(self.cx).executar(AG)
        self.assertEqual(RegistrarEventosAcesso(self.cx).executar(AG), 0)
        self.assertEqual(self._eventos("M1", "SYSTUR"), [(1, "ADERENTE")])

    def test_resolucao_do_ciclo1_nao_vaza_para_ciclo2(self):
        # ciclo 1 completo com resolucao antiga
        self._ev("M1", "SYSTUR", 1, "PENDENCIA", "2026-05-01 09:00:00")
        self._ev("M1", "SYSTUR", 1, "RESOLVIDO", "2026-05-05 09:00:00")
        self._ev("M1", "SYSTUR", 1, "ADERENTE", "2026-05-10 09:00:00")
        # ciclo_vida tem a resolucao ANTIGA (do ciclo 1)
        self._cv("M1", "SYSTUR", dt_resolvido="2026-05-05 09:00:00", ticket="INC-1")
        # reabre agora
        self._val("M1", "SYSTUR", "DIVERGENTE")
        RegistrarEventosAcesso(self.cx).executar(AG)
        eventos = self._eventos("M1", "SYSTUR")
        # ciclo 2 abre so a PENDENCIA; a resolucao velha NAO pode entrar no ciclo 2
        self.assertIn((2, "PENDENCIA"), eventos)
        self.assertNotIn((2, "RESOLVIDO"), eventos)


if __name__ == "__main__":
    unittest.main(verbosity=2)
