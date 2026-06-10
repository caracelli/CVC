# -*- coding: utf-8 -*-
"""ImportarSistema (Card 6+) end-to-end com extrato IC sintetico:
substituicao (snapshot), move para PROCESSADOS do sistema, log com hash e
deteccao de reimportacao do mesmo conteudo.
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
from aplicacao.casos_de_uso.importar_sistema import ImportarSistema
from dominio.objetos_valor.sistema import Sistema

IC = "IC_INTEGRADOR_CONTABIL"
_HDR = ["CD_PESSOA", "CD_LOGIN", "NM_PESSOA", "CD_EMAIL", "NM_GRUPO", "ST_HABILITACAO", "CPF"]


def _xlsx(path, linhas):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(_HDR)
    for ln in linhas:
        ws.append(ln)
    wb.save(path)


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_imps_")
        self.entrada = os.path.join(self._tmp, "SISTEMAS", "IC")
        self.err = os.path.join(self._tmp, "ERR")
        os.makedirs(self.entrada)
        os.makedirs(self.err)
        self.db = os.path.join(self._tmp, "s.db")
        self.conexao = ConexaoBancoDados(self.db)
        self.conexao.inicializar()

    def _importar(self):
        return ImportarSistema(
            conexao=self.conexao, sistema=Sistema.IC_INTEGRADOR_CONTABIL,
            pasta_entrada=self.entrada, pasta_processados=None, pasta_erros=self.err,
        ).executar()

    def _acessos(self):
        c = sqlite3.connect(self.db)
        try:
            return {r[0] for r in c.execute(
                "SELECT usuario FROM acessos_sistemas WHERE sistema=?", [IC])}
        finally:
            c.close()

    def _log(self):
        c = sqlite3.connect(self.db)
        try:
            return c.execute(
                "SELECT arquivo,status,total_registros,hash_arquivo "
                "FROM log_importacoes ORDER BY id").fetchall()
        finally:
            c.close()


class TestImportarSistema(_Base):

    def test_importa_move_para_processados_e_loga(self):
        arq = os.path.join(self.entrada, "relatorio IC 30.04.xlsx")
        _xlsx(arq, [[1, "u1", "ANA", "a@x", "IC_CONSULTA", "A", "11111111111"],
                    [2, "u2", "BRUNO", "b@x", "IC_APROVADOR", "A", "22222222222"]])
        total = self._importar()
        self.assertEqual(total, 2)
        self.assertEqual(self._acessos(), {"u1", "u2"})
        # arquivo movido para PROCESSADOS do sistema
        self.assertFalse(Path(arq).exists())
        proc = Path(self.entrada) / "PROCESSADOS"
        self.assertEqual(len(list(proc.glob("*.xlsx"))), 1)
        # log SUCESSO com hash e total
        log = self._log()
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0][1], "SUCESSO")
        self.assertEqual(log[0][2], 2)
        self.assertTrue(log[0][3])   # hash preenchido

    def test_substituicao_snapshot_remove_anterior(self):
        a = os.path.join(self.entrada, "ic_A.xlsx")
        _xlsx(a, [[1, "a1", "A1", "", "IC_CONSULTA", "A", "11111111111"],
                  [2, "a2", "A2", "", "IC_CONSULTA", "A", "22222222222"]])
        self._importar()
        self.assertEqual(self._acessos(), {"a1", "a2"})
        # novo extrato (snapshot) com outro usuario -> substitui tudo
        b = os.path.join(self.entrada, "ic_B.xlsx")
        _xlsx(b, [[3, "b1", "B1", "", "IC_CONSULTA", "A", "33333333333"]])
        self._importar()
        self.assertEqual(self._acessos(), {"b1"})

    def test_reimportacao_mesmo_conteudo_reprocessa_sem_duplicar(self):
        linhas = [[1, "u1", "ANA", "", "IC_CONSULTA", "A", "11111111111"]]
        _xlsx(os.path.join(self.entrada, "ic1.xlsx"), linhas)
        self._importar()
        # re-stage do MESMO conteudo (outro nome) e importa de novo
        _xlsx(os.path.join(self.entrada, "ic1_copia.xlsx"), linhas)
        self._importar()
        self.assertEqual(self._acessos(), {"u1"})     # substituicao: nao duplica
        self.assertEqual(len(self._log()), 2)          # 2 importacoes logadas

    def test_pasta_vazia_retorna_zero(self):
        self.assertEqual(self._importar(), 0)
        self.assertEqual(self._acessos(), set())


if __name__ == "__main__":
    unittest.main(verbosity=2)
