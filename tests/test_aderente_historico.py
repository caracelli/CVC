# -*- coding: utf-8 -*-
"""RegistrarAderenteHistorico: projeta aderentes 'conforme direto' do
ciclo_vida_acesso na trilha `historico` (ACESSO_SISTEMA / ADERENTE).

Regra: so grava quem tem dt_aderente, NAO tem registro previo no historico e
NAO tem resolucao previa. Idempotente."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy import text

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from aplicacao.casos_de_uso.registrar_aderente_historico import RegistrarAderenteHistorico


def _ciclo(s, mat, sistema="SYSTUR", dt_ader="2026-06-10 10:00:00", perfil="P1"):
    s.execute(text(
        "INSERT INTO ciclo_vida_acesso "
        "(matricula,sistema,perfil,nome,login,cargo,dt_pendencia,dt_resolvido,"
        " ticket,dt_aderente,dt_atualizacao) "
        "VALUES (:m,:sis,:p,:n,'lg','CARGO',NULL,NULL,NULL,:da,:da)"
    ), {"m": mat, "sis": sistema, "p": perfil, "n": mat, "da": dt_ader})


class TestAderenteHistorico(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.mkdtemp(prefix="cvc_ader_")
        self.cx = ConexaoBancoDados(os.path.join(tmp, "d.db"))
        self.cx.inicializar()

    def _aderentes_hist(self):
        s = self.cx.sessao()
        rows = [r[0] for r in s.execute(text(
            "SELECT matricula FROM historico "
            "WHERE entidade='ACESSO_SISTEMA' AND tipo_mudanca='ADERENTE'"
        ))]
        s.close()
        return sorted(rows)

    def test_grava_aderente_conforme_direto(self):
        s = self.cx.sessao(); _ciclo(s, "M1"); s.commit(); s.close()
        n = RegistrarAderenteHistorico(self.cx).executar()
        self.assertEqual(n, 1)
        self.assertEqual(self._aderentes_hist(), ["M1"])

    def test_idempotente_nao_duplica(self):
        s = self.cx.sessao(); _ciclo(s, "M1"); s.commit(); s.close()
        RegistrarAderenteHistorico(self.cx).executar()
        n2 = RegistrarAderenteHistorico(self.cx).executar()
        self.assertEqual(n2, 0)
        self.assertEqual(self._aderentes_hist(), ["M1"])

    def test_exclui_quem_ja_tem_registro_no_historico(self):
        s = self.cx.sessao()
        _ciclo(s, "M1")
        s.execute(text(
            "INSERT INTO historico (data_snapshot,entidade,chave_entidade,"
            "tipo_mudanca,matricula) VALUES ('2026-06-01','RH_ATIVO','M1','NOVO','M1')"
        ))
        s.commit(); s.close()
        n = RegistrarAderenteHistorico(self.cx).executar()
        self.assertEqual(n, 0)
        self.assertEqual(self._aderentes_hist(), [])

    def test_exclui_quem_tem_resolucao(self):
        s = self.cx.sessao()
        _ciclo(s, "M1")
        s.execute(text("CREATE TABLE IF NOT EXISTS resolucoes (registro_id TEXT)"))
        s.execute(text("INSERT INTO resolucoes (registro_id) VALUES ('M1')"))
        s.commit(); s.close()
        n = RegistrarAderenteHistorico(self.cx).executar()
        self.assertEqual(n, 0)
        self.assertEqual(self._aderentes_hist(), [])

    def test_sem_dt_aderente_nao_grava(self):
        s = self.cx.sessao()
        s.execute(text(
            "INSERT INTO ciclo_vida_acesso (matricula,sistema,perfil,dt_pendencia,"
            "dt_aderente) VALUES ('M2','SYSTUR','P1','2026-06-01 09:00:00',NULL)"
        ))
        s.commit(); s.close()
        n = RegistrarAderenteHistorico(self.cx).executar()
        self.assertEqual(n, 0)

    def test_uma_linha_por_matricula(self):
        # mesma matricula aderente em 2 sistemas -> 1 linha (trilha por pessoa)
        s = self.cx.sessao()
        _ciclo(s, "M1", sistema="SYSTUR")
        _ciclo(s, "M1", sistema="SIGOT")
        s.commit(); s.close()
        n = RegistrarAderenteHistorico(self.cx).executar()
        self.assertEqual(n, 1)
        self.assertEqual(self._aderentes_hist(), ["M1"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
