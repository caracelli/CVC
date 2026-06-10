# -*- coding: utf-8 -*-
"""RepositorioFuncionarioSqlite: merge INCREMENTAL do RH ativos (upsert, nao
delete+insert), roundtrip de entidade e buscas por matricula/CPF.
"""
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.repositorios.repositorio_funcionario_sqlite import RepositorioFuncionarioSqlite
from dominio.objetos_valor.cargo import Cargo
from dominio.entidades.funcionario_ativo import FuncionarioAtivo
from dominio.entidades.funcionario_desligado import FuncionarioDesligado


def _cargo(desc="ANALISTA", cc="100"):
    return Cargo(codigo="CG", descricao=desc, departamento="TI", centro_custo=cc)


def _ativo(mat, cpf="111", desc="ANALISTA", vinc="FUNCIONARIO", empresa=None):
    return FuncionarioAtivo(matricula=mat, nome=f"NOME {mat}", cpf=cpf,
                            cargo=_cargo(desc), email=f"{mat}@x.com",
                            data_admissao=date(2020, 1, 1), situacao="ATIVO",
                            tipo_vinculo=vinc, empresa=empresa)


def _desl(mat, cpf="999"):
    return FuncionarioDesligado(matricula=mat, nome=f"D{mat}", cpf=cpf,
                                cargo=_cargo(), data_desligamento=date(2026, 1, 1))


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_repofunc_")
        self.conexao = ConexaoBancoDados(os.path.join(self._tmp, "f.db"))
        self.conexao.inicializar()
        self.repo = RepositorioFuncionarioSqlite(self.conexao)


class TestMergeIncremental(_Base):

    def test_segundo_lote_nao_apaga_ausentes(self):
        self.repo.salvar_ativos([_ativo("M1", desc="ANALISTA"), _ativo("M2", desc="X")])
        # incremento: atualiza M2, adiciona M3 — M1 NAO vem no lote
        self.repo.salvar_ativos([_ativo("M2", desc="GERENTE"), _ativo("M3")])
        mats = {a.matricula for a in self.repo.obter_ativos()}
        self.assertEqual(mats, {"M1", "M2", "M3"})           # M1 preservado
        self.assertEqual(self.repo.buscar_por_matricula("M2").cargo.descricao, "GERENTE")
        self.assertEqual(self.repo.buscar_por_matricula("M1").cargo.descricao, "ANALISTA")

    def test_reimportar_mesma_matricula_atualiza_no_lugar(self):
        self.repo.salvar_ativos([_ativo("M1", desc="ANALISTA")])
        self.repo.salvar_ativos([_ativo("M1", desc="COORDENADOR")])
        ativos = self.repo.obter_ativos()
        self.assertEqual(len(ativos), 1)                     # nao duplica
        self.assertEqual(ativos[0].cargo.descricao, "COORDENADOR")


class TestRoundtrip(_Base):

    def test_ativo_roundtrip_campos(self):
        self.repo.salvar_ativos([_ativo("M1", cpf="12345678901", desc="ANALISTA")])
        a = self.repo.buscar_por_matricula("M1")
        self.assertEqual(a.nome, "NOME M1")
        self.assertEqual(a.cpf, "12345678901")
        self.assertEqual(a.cargo.centro_custo, "100")
        self.assertEqual(a.situacao, "ATIVO")
        self.assertEqual(a.data_admissao, date(2020, 1, 1))

    def test_terceiro_preserva_vinculo_e_empresa(self):
        self.repo.salvar_ativos([_ativo("TERC-1", vinc="TERCEIRO", empresa="FORNEC X")])
        a = self.repo.buscar_por_matricula("TERC-1")
        self.assertEqual(a.tipo_vinculo, "TERCEIRO")
        self.assertEqual(a.empresa, "FORNEC X")


class TestBuscas(_Base):

    def test_buscar_por_cpf(self):
        self.repo.salvar_ativos([_ativo("M1", cpf="11111111111")])
        self.assertEqual(self.repo.buscar_por_cpf("11111111111").matricula, "M1")
        self.assertIsNone(self.repo.buscar_por_cpf("00000000000"))

    def test_buscar_matricula_inexistente(self):
        self.assertIsNone(self.repo.buscar_por_matricula("ZZZ"))


class TestDesligados(_Base):

    def test_salvar_e_obter_e_buscar_por_cpf(self):
        self.repo.salvar_desligados([_desl("D1", cpf="33333333333")])
        self.assertEqual({d.matricula for d in self.repo.obter_desligados()}, {"D1"})
        d = self.repo.buscar_desligado_por_cpf("33333333333")
        self.assertEqual(d.matricula, "D1")
        self.assertEqual(d.data_desligamento, date(2026, 1, 1))

    def test_merge_desligados_nao_duplica(self):
        self.repo.salvar_desligados([_desl("D1")])
        self.repo.salvar_desligados([_desl("D1")])
        self.assertEqual(len(self.repo.obter_desligados()), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
