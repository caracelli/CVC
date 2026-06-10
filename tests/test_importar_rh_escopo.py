# -*- coding: utf-8 -*-
"""ImportarRh respeitando o ESCOPO da Fase 1 (config-driven), end-to-end.

- processar_desligados=False: pasta de desligados NAO e' lida (nem movida),
  mesmo havendo arquivo (revogacao e' fluxo separado).
- processar_terceiros=False: arquivo de terceiros (QuickReport) na pasta de
  ATIVOS e' ignorado (nao importa nem move); o CLT segue normal.
Com os flags True, ambos entram — provando que o gating e' o flag, nao ausencia.
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from aplicacao.casos_de_uso.importar_rh import ImportarRh

_CLT = (
    "MATRICULA;NOME;CPF;CARGO_CODIGO;CARGO_DESCRICAO;CENTRO_CUSTO;DEPARTAMENTO;"
    "DATA_ADMISSAO;EMAIL;SITUACAO\n"
    "100;ANA SILVA;11111111111;CG1;ANALISTA;CC1;TI;01/02/2020;ana@x.com;Atividade Normal\n"
    "101;BRUNO LIMA;22222222222;CG2;GERENTE;CC2;COM;02/03/2019;bruno@x.com;Atividade Normal\n"
)
_DESLIGADOS = (
    "MATRICULA;NOME;CPF;CARGO_CODIGO;CARGO_DESCRICAO;CENTRO_CUSTO;DEPARTAMENTO;"
    "DATA_ADMISSAO;EMAIL;DATA_DESLIGAMENTO\n"
    "900;CARLOS DIAS;33333333333;CG3;ASSIST;CC3;OPS;01/01/2018;c@x.com;15/01/2026\n"
)
_TERCEIRO = (
    "EMPRESA FORNECEDORA;CNPJ;NOME DO SUPERVISOR;NOME;CODIGO;STATUS RH\n"
    "FORNEC X;00.000.000/0001-00;SUPER VISOR;TERCEIRO UM;12345678901;ATIVO\n"
)


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_rh_")
        self.ativos = os.path.join(self._tmp, "ATIVOS")
        self.deslig = os.path.join(self._tmp, "DESLIGADOS")
        self.proc = os.path.join(self._tmp, "PROC")
        self.err = os.path.join(self._tmp, "ERR")
        for d in (self.ativos, self.deslig, self.proc, self.err):
            os.makedirs(d)
        self.db = os.path.join(self._tmp, "rh.db")
        self.conexao = ConexaoBancoDados(self.db)
        self.conexao.inicializar()

    def _arq(self, pasta, nome, conteudo):
        p = Path(pasta) / nome
        p.write_text(conteudo, encoding="utf-8")
        return p

    def _importar(self, processar_desligados, processar_terceiros):
        return ImportarRh(
            conexao=self.conexao, pasta_ativos=self.ativos, pasta_desligados=self.deslig,
            pasta_processados=self.proc, pasta_erros=self.err,
            processar_desligados=processar_desligados,
            processar_terceiros=processar_terceiros,
        ).executar()

    def _conta(self, tabela):
        c = sqlite3.connect(self.db)
        try:
            return c.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
        finally:
            c.close()

    def _matriculas(self, tabela):
        c = sqlite3.connect(self.db)
        try:
            return {r[0] for r in c.execute(f"SELECT matricula FROM {tabela}")}
        finally:
            c.close()


class TestGatingDesligados(_Base):
    def test_desligados_off_nao_le_nem_move(self):
        self._arq(self.ativos, "clt.csv", _CLT)
        deslig_arq = self._arq(self.deslig, "desl.csv", _DESLIGADOS)
        n_at, n_de = self._importar(processar_desligados=False, processar_terceiros=True)
        self.assertEqual(n_de, 0)
        self.assertEqual(self._conta("rh_desligados"), 0)
        self.assertTrue(deslig_arq.exists(), "arquivo de desligados nao deve ser movido")
        self.assertEqual(n_at, 2)

    def test_desligados_on_le_e_importa(self):
        self._arq(self.ativos, "clt.csv", _CLT)
        self._arq(self.deslig, "desl.csv", _DESLIGADOS)
        _, n_de = self._importar(processar_desligados=True, processar_terceiros=True)
        self.assertEqual(n_de, 1)
        self.assertEqual(self._matriculas("rh_desligados"), {"900"})


class TestGatingTerceiros(_Base):
    def test_terceiros_off_ignora_arquivo_e_mantem_clt(self):
        self._arq(self.ativos, "clt.csv", _CLT)
        terc_arq = self._arq(self.ativos, "quickreport.csv", _TERCEIRO)
        n_at, _ = self._importar(processar_desligados=False, processar_terceiros=False)
        mats = self._matriculas("rh_ativos")
        self.assertEqual(mats, {"100", "101"})                 # so CLT
        self.assertFalse(any(m.startswith("TERC-") for m in mats))
        self.assertTrue(terc_arq.exists(), "terceiro fora de escopo nao deve ser movido")
        self.assertEqual(n_at, 2)

    def test_terceiros_on_importa_como_terceiro(self):
        self._arq(self.ativos, "clt.csv", _CLT)
        self._arq(self.ativos, "quickreport.csv", _TERCEIRO)
        self._importar(processar_desligados=False, processar_terceiros=True)
        mats = self._matriculas("rh_ativos")
        self.assertIn("TERC-12345678901", mats)
        c = sqlite3.connect(self.db)
        try:
            vinc = c.execute(
                "SELECT tipo_vinculo FROM rh_ativos WHERE matricula='TERC-12345678901'"
            ).fetchone()[0]
        finally:
            c.close()
        self.assertEqual(vinc, "TERCEIRO")


if __name__ == "__main__":
    unittest.main(verbosity=2)
