# -*- coding: utf-8 -*-
"""ImportarMatrizes (Card 5) end-to-end: le perfis (filtrando por escopo) + CCO,
persiste e move processados; matriz de sistema fora de escopo e' ignorada
(sem mover).
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from aplicacao.casos_de_uso.importar_matrizes import ImportarMatrizes
from dominio.objetos_valor.sistema import Sistema

IC = "IC_INTEGRADOR_CONTABIL"


def _xlsx(path, header, linhas, titulo=False):
    wb = openpyxl.Workbook()
    ws = wb.active
    if titulo:
        ws.append(["TITULO FUNDIDO"])   # linha 0 (org tem cabecalho na linha 1)
    ws.append(header)
    for ln in linhas:
        ws.append(ln)
    wb.save(path)


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_mat_")
        self.perfis = os.path.join(self._tmp, "PERFIS")
        self.org = os.path.join(self._tmp, "ORG")
        self.proc = os.path.join(self._tmp, "PROC")
        self.err = os.path.join(self._tmp, "ERR")
        for d in (self.perfis, self.org, self.proc, self.err):
            os.makedirs(d)
        self.db = os.path.join(self._tmp, "m.db")
        self.conexao = ConexaoBancoDados(self.db)
        self.conexao.inicializar()

        # matriz de perfis IC (em escopo) + SIGOT (fora)
        self.arq_ic = os.path.join(self.perfis, "Matriz - IC Integrador Contabil.xlsx")
        _xlsx(self.arq_ic, ["ACESSO MANUAL", "CARGO", "CCUSTO", "PERFIL ACESSO"],
              [["NAO", "ANALISTA", "100", "IC CONSULTA"],
               ["SIM", "GERENTE", "200", "IC APROVADOR"]])
        self.arq_sigot = os.path.join(self.perfis, "Matriz - SIGOT.xlsx")
        _xlsx(self.arq_sigot, ["ACESSO MANUAL", "CARGO", "CCUSTO", "PERFIL ACESSO"],
              [["NAO", "OPERADOR", "300", "OP1"]])

        # CCO (cabecalho na linha 1)
        self.arq_cco = os.path.join(self.org, "Mapeamento CCO.xlsx")
        _xlsx(self.arq_cco,
              ["CÓDIGO DO CENTRO DE CUSTO", "NOME DO CENTRO DE CUSTO", "FUNÇÃO", "SISTEMAS", "PERFIS"],
              [["100", "FIN", "ANALISTA", "Systur", "P1"],
               ["200", "COM", "GERENTE", "Sigot", "P2"]],
              titulo=True)

    def _importar(self, escopo):
        return ImportarMatrizes(
            conexao=self.conexao, pasta_perfis=self.perfis, pasta_org=self.org,
            pasta_processados=self.proc, pasta_erros=self.err,
            sistemas_em_escopo=escopo,
        ).executar()

    def _q(self, sql):
        c = sqlite3.connect(self.db)
        try:
            return c.execute(sql).fetchall()
        finally:
            c.close()


class TestImportarMatrizes(_Base):

    def test_escopo_ic_so_importa_ic_e_nao_move_sigot(self):
        n_perfis, n_cco = self._importar({Sistema.IC_INTEGRADOR_CONTABIL})
        self.assertEqual(n_perfis, 2)
        sistemas = {r[0] for r in self._q("SELECT DISTINCT sistema FROM perfis_esperados")}
        self.assertEqual(sistemas, {IC})
        # IC foi movido; SIGOT (fora de escopo) permanece na pasta
        self.assertFalse(Path(self.arq_ic).exists())
        self.assertTrue(Path(self.arq_sigot).exists())

    def test_cco_importado(self):
        _, n_cco = self._importar({Sistema.IC_INTEGRADOR_CONTABIL})
        self.assertEqual(n_cco, 2)
        rows = self._q("SELECT cc, sistema, perfil FROM matriz_cco ORDER BY cc")
        self.assertEqual(rows, [("100", "Systur", "P1"), ("200", "Sigot", "P2")])

    def test_sem_escopo_processa_todas_as_matrizes(self):
        # None = compat: processa IC + SIGOT
        n_perfis, _ = self._importar(None)
        self.assertEqual(n_perfis, 3)   # 2 IC + 1 SIGOT
        sistemas = {r[0] for r in self._q("SELECT DISTINCT sistema FROM perfis_esperados")}
        self.assertEqual(sistemas, {IC, "SIGOT"})

    def test_acesso_manual_e_cargo_ccusto_persistidos(self):
        self._importar({Sistema.IC_INTEGRADOR_CONTABIL})
        rows = self._q("SELECT cargo_codigo, cargo_descricao, perfil, acesso_manual "
                       "FROM perfis_esperados ORDER BY perfil")
        # IC APROVADOR (manual=SIM->1), IC CONSULTA (manual=NAO->0)
        self.assertEqual(rows[0], ("200", "GERENTE", "IC APROVADOR", 1))
        self.assertEqual(rows[1], ("100", "ANALISTA", "IC CONSULTA", 0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
