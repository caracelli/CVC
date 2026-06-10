# -*- coding: utf-8 -*-
"""RegistrarCicloHistorico: projeta os marcos do ciclo_vida_acesso na trilha
`historico` (entidade ACESSO_SISTEMA), uma linha por marco, idempotente.

Cobre os 4 casos combinados (manual + processador):
- pendente              -> so PENDENCIA
- pendente->resolvido->aderente -> as 3 linhas
- pendente->aderente (sem resolucao) -> PENDENCIA + ADERENTE
- lido aderente direto (sem dt_pendencia) -> so ADERENTE (NAO inventa pendencia)
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy import text

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from aplicacao.casos_de_uso.registrar_ciclo_historico import RegistrarCicloHistorico

D1, D2, D3 = "2026-06-01 09:00:00", "2026-06-05 14:00:00", "2026-06-10 10:00:00"


def _ciclo(s, mat, sistema="SYSTUR", dp=None, dr=None, da=None, ticket=None):
    s.execute(text(
        "INSERT INTO ciclo_vida_acesso "
        "(matricula,sistema,perfil,nome,login,cargo,dt_pendencia,dt_resolvido,"
        " ticket,dt_aderente,dt_atualizacao) "
        "VALUES (:m,:sis,'P1',:m,'lg','CARGO',:dp,:dr,:tk,:da,:upd)"
    ), {"m": mat, "sis": sistema, "dp": dp, "dr": dr, "tk": ticket, "da": da,
        "upd": da or dr or dp})


class TestCicloHistorico(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.mkdtemp(prefix="cvc_clh_")
        self.cx = ConexaoBancoDados(os.path.join(tmp, "d.db"))
        self.cx.inicializar()

    def _tipos(self, mat="M1"):
        s = self.cx.sessao()
        rows = sorted(r[0] for r in s.execute(text(
            "SELECT tipo_mudanca FROM historico WHERE entidade='ACESSO_SISTEMA' "
            "AND chave_entidade=:m"), {"m": mat}))
        s.close()
        return rows

    def test_pendente_so_gera_pendencia(self):
        s = self.cx.sessao(); _ciclo(s, "M1", dp=D1); s.commit(); s.close()
        n = RegistrarCicloHistorico(self.cx).executar()
        self.assertEqual(n, 1)
        self.assertEqual(self._tipos(), ["PENDENCIA"])

    def test_pendente_resolvido_aderente_gera_tres(self):
        s = self.cx.sessao(); _ciclo(s, "M1", dp=D1, dr=D2, da=D3, ticket="JIRA-1")
        s.commit(); s.close()
        n = RegistrarCicloHistorico(self.cx).executar()
        self.assertEqual(n, 3)
        self.assertEqual(self._tipos(), ["ADERENTE", "PENDENCIA", "RESOLVIDO"])

    def test_pendente_aderente_sem_resolucao_gera_duas(self):
        s = self.cx.sessao(); _ciclo(s, "M1", dp=D1, da=D3); s.commit(); s.close()
        n = RegistrarCicloHistorico(self.cx).executar()
        self.assertEqual(n, 2)
        self.assertEqual(self._tipos(), ["ADERENTE", "PENDENCIA"])

    def test_aderente_direto_so_aderente(self):
        # dt_pendencia NULL: lido aderente direto -> NAO inventa pendencia
        s = self.cx.sessao(); _ciclo(s, "M1", da=D3); s.commit(); s.close()
        n = RegistrarCicloHistorico(self.cx).executar()
        self.assertEqual(n, 1)
        self.assertEqual(self._tipos(), ["ADERENTE"])

    def test_idempotente_entre_rodadas(self):
        s = self.cx.sessao(); _ciclo(s, "M1", dp=D1, da=D3); s.commit(); s.close()
        RegistrarCicloHistorico(self.cx).executar()
        n2 = RegistrarCicloHistorico(self.cx).executar()
        self.assertEqual(n2, 0)
        self.assertEqual(self._tipos(), ["ADERENTE", "PENDENCIA"])

    def test_transicao_incremental_adiciona_so_o_novo(self):
        # rodada 1: pendente -> grava PENDENCIA
        s = self.cx.sessao(); _ciclo(s, "M1", dp=D1); s.commit(); s.close()
        self.assertEqual(RegistrarCicloHistorico(self.cx).executar(), 1)
        # rodada 2: virou aderente -> ciclo agora tem dt_aderente; so falta ADERENTE
        s = self.cx.sessao()
        s.execute(text("UPDATE ciclo_vida_acesso SET dt_aderente=:da WHERE matricula='M1'"),
                  {"da": D3})
        s.commit(); s.close()
        self.assertEqual(RegistrarCicloHistorico(self.cx).executar(), 1)
        self.assertEqual(self._tipos(), ["ADERENTE", "PENDENCIA"])

    def test_ticket_guardado_no_resolvido(self):
        s = self.cx.sessao(); _ciclo(s, "M1", dp=D1, dr=D2, ticket="JIRA-9")
        s.commit(); s.close()
        RegistrarCicloHistorico(self.cx).executar()
        s = self.cx.sessao()
        dn = s.execute(text("SELECT dados_novo FROM historico WHERE chave_entidade='M1' "
                            "AND tipo_mudanca='RESOLVIDO'")).fetchone()[0]
        s.close()
        self.assertEqual(json.loads(dn).get("ticket"), "JIRA-9")

    def test_uma_linha_por_matricula_multisistema(self):
        s = self.cx.sessao()
        _ciclo(s, "M1", sistema="SYSTUR", da=D3)
        _ciclo(s, "M1", sistema="SIGOT", da=D3)
        s.commit(); s.close()
        n = RegistrarCicloHistorico(self.cx).executar()
        self.assertEqual(n, 1)
        self.assertEqual(self._tipos(), ["ADERENTE"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
