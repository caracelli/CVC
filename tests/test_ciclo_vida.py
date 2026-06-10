# -*- coding: utf-8 -*-
"""Ciclo de vida do acesso: Pendencia -> Resolvido (ticket) -> Aderente, com
timestamps FIRST-WINS. Valida o ciclo completo, a idempotencia (datas nao mudam
ao reprocessar) e o colapso do Em Analise (N opcoes -> 1 linha por sistema).
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from aplicacao.casos_de_uso.registrar_ciclo_vida import RegistrarCicloVida


def _set_validacao(db, status, perfil="P1"):
    c = sqlite3.connect(db)
    c.execute("DELETE FROM validacao_acessos")
    c.execute(
        """INSERT INTO validacao_acessos
           (matricula,nome,sistema,perfil_esperado,perfil_atual,status,situacao_acao,dt_processamento)
           VALUES ('M1','NOME','SYSTUR',?, '', ?, ?, '2026-01-01')""",
        (perfil, status, "OK" if status == "OK" else "PENDENTE"))
    c.commit(); c.close()


def _add_resolucao(db, ticket, resolvido_em):
    c = sqlite3.connect(db)
    c.execute("INSERT OR REPLACE INTO resolucoes (registro_id,ticket,resolvido_em) VALUES ('M1',?,?)",
              (ticket, resolvido_em))
    c.commit(); c.close()


def _row(db):
    c = sqlite3.connect(db); c.row_factory = sqlite3.Row
    r = c.execute("SELECT * FROM ciclo_vida_acesso WHERE matricula='M1'").fetchone()
    c.close()
    return dict(r) if r else None


class TestCicloVida(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cvc_ciclo_")
        self.db = os.path.join(self.tmp, "c.db")
        self.cx = ConexaoBancoDados(self.db)
        self.cx.inicializar()
        # resolucoes normalmente e' criada pela dobra de interacoes
        c = sqlite3.connect(self.db)
        c.execute("CREATE TABLE IF NOT EXISTS resolucoes "
                  "(registro_id TEXT PRIMARY KEY, ticket TEXT, resolvido_em TEXT)")
        c.commit(); c.close()

    def test_ciclo_completo_e_idempotente(self):
        # 1) Pendencia em t1
        _set_validacao(self.db, "SEM_ACESSO")
        RegistrarCicloVida(self.cx).executar(agora="2026-01-01 09:00:00")
        r = _row(self.db)
        self.assertEqual(r["dt_pendencia"], "2026-01-01 09:00:00")
        self.assertIsNone(r["dt_aderente"])
        self.assertIsNone(r["dt_resolvido"])

        # 2) Resolvido (ticket Jira)
        _add_resolucao(self.db, "JIRA-1", "2026-01-03 10:00:00")
        RegistrarCicloVida(self.cx).executar(agora="2026-01-03 12:00:00")
        r = _row(self.db)
        self.assertEqual(r["dt_resolvido"], "2026-01-03 10:00:00")
        self.assertEqual(r["ticket"], "JIRA-1")

        # 3) Aderente em t3 (acesso OK)
        _set_validacao(self.db, "OK")
        RegistrarCicloVida(self.cx).executar(agora="2026-01-05 08:00:00")
        r = _row(self.db)
        self.assertEqual(r["dt_aderente"], "2026-01-05 08:00:00")
        self.assertEqual(r["dt_pendencia"], "2026-01-01 09:00:00")  # preservada

        # 4) Idempotencia: reprocessa com nova data -> datas NAO mudam
        RegistrarCicloVida(self.cx).executar(agora="2026-01-09 23:00:00")
        r2 = _row(self.db)
        self.assertEqual(r2["dt_pendencia"], "2026-01-01 09:00:00")
        self.assertEqual(r2["dt_resolvido"], "2026-01-03 10:00:00")
        self.assertEqual(r2["dt_aderente"], "2026-01-05 08:00:00")

    def test_em_analise_colapsa_por_sistema(self):
        # 3 opcoes EM_ANALISE no mesmo sistema -> 1 unica linha de ciclo
        c = sqlite3.connect(self.db)
        c.execute("DELETE FROM validacao_acessos")
        for p in ("A", "B", "C"):
            c.execute(
                """INSERT INTO validacao_acessos
                   (matricula,nome,sistema,perfil_esperado,perfil_atual,status,situacao_acao,dt_processamento)
                   VALUES ('M1','N','SYSTUR',?, '', 'EM_ANALISE','PENDENTE','2026-01-01')""", (p,))
        c.commit(); c.close()
        RegistrarCicloVida(self.cx).executar(agora="2026-01-01 09:00:00")
        c = sqlite3.connect(self.db)
        n = c.execute("SELECT COUNT(*) FROM ciclo_vida_acesso WHERE matricula='M1'").fetchone()[0]
        c.close()
        self.assertEqual(n, 1)

    def test_vg_tempos_medios_formatados(self):
        # 2 ciclos completos -> medias formatadas d/h/min na Visao Geral
        import visualizador.main as vm
        c = sqlite3.connect(self.db)
        c.execute(
            """INSERT INTO ciclo_vida_acesso (matricula,sistema,perfil,dt_pendencia,dt_resolvido,dt_aderente)
               VALUES ('A','SYSTUR','P','2026-01-01 00:00:00','2026-01-03 00:00:00','2026-01-05 00:00:00'),
                      ('B','SYSTUR','P','2026-01-01 00:00:00','2026-01-03 00:00:00','2026-01-07 00:00:00')""")
        c.commit()
        vg = vm._calcular_visao_geral(c, "")
        c.close()
        t = vg["tempos"]
        self.assertEqual(t["total"], "5d")          # seg_pr(2d) + seg_ra(3d)
        self.assertEqual(t["n"], 2)
        self.assertEqual(t["resolv_ader"], "3d")     # (2d + 4d) / 2
        self.assertEqual(t["pend_resolv"], "2d")     # (2d + 2d) / 2

    def test_vg_ignora_ciclos_incompletos(self):
        # So ciclos COMPLETOS (3 datas) entram na media. O caso EMERSON
        # (pendencia + aderente, SEM resolvido) NAO pode distorcer nem contar.
        import visualizador.main as vm
        c = sqlite3.connect(self.db)
        c.execute(
            """INSERT INTO ciclo_vida_acesso (matricula,sistema,perfil,dt_pendencia,dt_resolvido,dt_aderente)
               VALUES ('C','SYSTUR','P','2026-01-01 00:00:00','2026-01-03 00:00:00','2026-01-05 00:00:00'),
                      ('D','SYSTUR','P','2026-01-01 00:00:00','2026-01-03 00:00:00','2026-01-05 00:00:00'),
                      ('E','SYSTUR','P','2026-01-01 00:00:00',NULL,'2026-01-09 00:00:00')""")
        c.commit()
        vg = vm._calcular_visao_geral(c, "")
        c.close()
        t = vg["tempos"]
        self.assertEqual(t["n"], 2)                 # so C e D; E (incompleto) fora
        self.assertEqual(t["pend_resolv"], "2d")     # jan1 -> jan3
        self.assertEqual(t["resolv_ader"], "2d")     # jan3 -> jan5
        self.assertEqual(t["total"], "4d")

    def test_fmt_duracao(self):
        from visualizador.main import _fmt_duracao
        self.assertEqual(_fmt_duracao(5 * 86400), "5d")
        self.assertEqual(_fmt_duracao(86400 + 3 * 3600 + 15 * 60), "1d 3h 15min")
        self.assertEqual(_fmt_duracao(45 * 60), "45min")
        self.assertEqual(_fmt_duracao(0), "0min")
        self.assertEqual(_fmt_duracao(None), "—")

    def test_aderente_puro_nao_tem_pendencia(self):
        # quem ja nasce OK (nunca foi pendencia) -> sem dt_pendencia (sem tempo)
        _set_validacao(self.db, "OK")
        RegistrarCicloVida(self.cx).executar(agora="2026-01-01 09:00:00")
        r = _row(self.db)
        self.assertEqual(r["dt_aderente"], "2026-01-01 09:00:00")
        self.assertIsNone(r["dt_pendencia"])


class TestAderentesLista(unittest.TestCase):
    """Lista da aba Aderentes (construir_db): so quem tem dt_aderente, ordenado
    por dt_aderente DESC, filtravel por sistema, carregando a trilha de datas."""

    def setUp(self):
        import visualizador.main as vm
        self.vm = vm
        self.tmp = tempfile.mkdtemp(prefix="cvc_ader_")
        self.db = os.path.join(self.tmp, "a.db")
        self.inter = os.path.join(self.tmp, "INTERACOES")
        os.makedirs(self.inter)
        ConexaoBancoDados(self.db).inicializar()
        c = sqlite3.connect(self.db)
        c.execute(
            "INSERT INTO ciclo_vida_acesso (matricula,sistema,perfil,nome,login,"
            "cargo,dt_pendencia,dt_resolvido,ticket,dt_aderente) VALUES "
            # A1: ciclo completo (pendencia->resolvido->aderente em jan)
            "('A1','SYSTUR','P_A','NOME A1','LA1','CARGO','2026-01-01 09:00:00',"
            "'2026-01-03 10:00:00','JIRA-1','2026-01-05 08:00:00'),"
            # A2: aderente PURO (sem trilha) em fev
            "('A2','SYSTUR','P_B','NOME A2','LA2','CARGO',NULL,NULL,NULL,'2026-02-10 12:00:00'),"
            # A3: aderente PURO no IC em mar
            "('A3','IC_INTEGRADOR_CONTABIL','P_C','NOME A3','LA3','CARGO',NULL,NULL,NULL,'2026-03-01 07:00:00'),"
            # A4: ainda pendencia (dt_aderente NULL) -> NAO entra na lista
            "('A4','SYSTUR','P_D','NOME A4','LA4','CARGO','2026-01-01 09:00:00',NULL,NULL,NULL)")
        c.commit()
        c.close()
        self._orig = (vm.DB_PATH, vm.SISTEMA, vm.PASTA_INTERACOES, vm._BASE)
        vm.DB_PATH = self.db
        vm.SISTEMA = ""
        vm.PASTA_INTERACOES = self.inter
        vm._BASE = None
        vm.garantir_estrutura(force=True)
        self.addCleanup(self._restore)

    def _restore(self):
        (self.vm.DB_PATH, self.vm.SISTEMA,
         self.vm.PASTA_INTERACOES, self.vm._BASE) = self._orig

    def _aderentes(self, sistema=""):
        self.vm.SISTEMA = sistema
        self.vm._BASE = None
        return self.vm.construir_db()["aderentes"]

    def test_so_quem_tem_dt_aderente_ordenado_desc(self):
        # A4 (dt_aderente NULL) fora; ordem DESC: A3(mar) > A2(fev) > A1(jan)
        self.assertEqual([a["m"] for a in self._aderentes("")], ["A3", "A2", "A1"])

    def test_carrega_a_trilha_de_datas_do_ciclo(self):
        ad = {a["m"]: a for a in self._aderentes("")}
        a1 = ad["A1"]
        self.assertEqual(a1["dt_pend"], "2026-01-01 09:00:00")
        self.assertEqual(a1["dt_resol"], "2026-01-03 10:00:00")
        self.assertEqual(a1["ticket"], "JIRA-1")
        self.assertEqual(a1["dt"], "2026-01-05 08:00:00")
        self.assertEqual(ad["A2"]["dt_pend"], "")   # aderente puro: sem trilha

    def test_filtro_por_sistema(self):
        self.assertEqual([a["m"] for a in self._aderentes("IC_INTEGRADOR_CONTABIL")],
                         ["A3"])                      # so o aderente do IC


if __name__ == "__main__":
    unittest.main(verbosity=2)
