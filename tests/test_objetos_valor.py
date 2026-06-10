# -*- coding: utf-8 -*-
"""Objetos de valor / enums (contrato de banco) + invariantes de entidade.

Os .value dos enums sao GRAVADOS no banco (status, tipo, sistema). Renomear
um valor quebraria dados em producao — estes testes pinam o contrato.
"""
import dataclasses
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dominio.objetos_valor.cargo import Cargo
from dominio.objetos_valor.nivel_acesso import NivelAcesso
from dominio.objetos_valor.tipo_divergencia import TipoDivergencia
from dominio.objetos_valor.status_validacao import StatusValidacao
from dominio.objetos_valor.sistema import Sistema
from dominio.entidades.funcionario import Funcionario
from dominio.entidades.funcionario_ativo import FuncionarioAtivo


def _cargo():
    return Cargo(codigo="CG", descricao="ANALISTA", departamento="TI", centro_custo="100")


class TestEnumsContrato(unittest.TestCase):
    def test_tipo_divergencia(self):
        self.assertEqual(
            {e.name: e.value for e in TipoDivergencia},
            {"ACESSO_DESLIGADO": "ACESSO_DESLIGADO",
             "ACESSO_TRANSFERIDO": "ACESSO_TRANSFERIDO",
             "PERFIL_INVALIDO": "PERFIL_INVALIDO",
             "PERFIL_EXCESSIVO": "PERFIL_EXCESSIVO",
             "ACESSO_SEM_VINCULO_RH": "ACESSO_SEM_VINCULO_RH"})

    def test_status_validacao(self):
        self.assertEqual(
            {e.name: e.value for e in StatusValidacao},
            {"ADERENTE": "ADERENTE", "DIVERGENTE": "DIVERGENTE",
             "EM_ANALISE": "EM_ANALISE", "NAO_MAPEADO": "NAO_MAPEADO",
             "SEM_ACESSO": "SEM_ACESSO", "SEM_DADOS": "SEM_DADOS", "OK": "OK"})

    def test_nivel_acesso(self):
        self.assertEqual(
            {e.name: e.value for e in NivelAcesso},
            {"SOMENTE_LEITURA": "SOMENTE_LEITURA", "OPERADOR": "OPERADOR",
             "SUPERVISOR": "SUPERVISOR", "ADMINISTRADOR": "ADMINISTRADOR"})

    def test_sistema(self):
        self.assertEqual(
            {e.name: e.value for e in Sistema},
            {"SIGOT": "SIGOT", "SICA_RA": "SICA_RA", "SICA_ESFERA": "SICA_ESFERA",
             "SYSTUR": "SYSTUR", "IC_INTEGRADOR_CONTABIL": "IC_INTEGRADOR_CONTABIL",
             "SIG": "SIG", "ORACLE_EBS": "ORACLE_EBS",
             "OPERA_OPERACIONAL": "OPERA_OPERACIONAL"})


class TestStatusValidacaoStrEnum(unittest.TestCase):
    def test_compara_como_string(self):
        # StatusValidacao herda de str: usado direto em comparacoes/SQL
        self.assertEqual(StatusValidacao.ADERENTE, "ADERENTE")
        self.assertEqual(StatusValidacao.DIVERGENTE.value, "DIVERGENTE")


class TestCargo(unittest.TestCase):
    def test_imutavel(self):
        c = _cargo()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            c.codigo = "X"

    def test_igualdade_por_valor(self):
        self.assertEqual(_cargo(), _cargo())

    def test_hashavel(self):
        # frozen -> hashavel: pode ir em set/dict (usado em chaves)
        self.assertEqual(len({_cargo(), _cargo()}), 1)


class TestFuncionarioInvariantes(unittest.TestCase):
    def test_exige_matricula(self):
        with self.assertRaises(ValueError):
            Funcionario(matricula="", nome="ANA", cpf="111", cargo=_cargo())

    def test_exige_nome(self):
        with self.assertRaises(ValueError):
            Funcionario(matricula="1", nome="", cpf="111", cargo=_cargo())

    def test_exige_cpf(self):
        with self.assertRaises(ValueError):
            Funcionario(matricula="1", nome="ANA", cpf="", cargo=_cargo())

    def test_ativo_defaults(self):
        f = FuncionarioAtivo(matricula="1", nome="ANA", cpf="111", cargo=_cargo())
        self.assertEqual(f.situacao, "ATIVO")
        self.assertEqual(f.tipo_vinculo, "FUNCIONARIO")
        self.assertIsNone(f.empresa)

    def test_ativo_valido_nao_quebra(self):
        f = FuncionarioAtivo(matricula="1", nome="ANA", cpf="111", cargo=_cargo(),
                             data_admissao=date(2020, 1, 1), situacao="ATIVO")
        self.assertEqual(f.matricula, "1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
