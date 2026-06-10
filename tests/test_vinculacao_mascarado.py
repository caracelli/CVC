# -*- coding: utf-8 -*-
"""Vinculacao integrada com CPF MASCARADO (cenario real do SICA_RA: '39328XXX').
Exercita o nivel 3 da cascata (CPF parcial + nome) via VincularAcessosRh, que
passa o cpf do acesso como cpf_mascarado.
"""
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import RhAtivo, AcessoSistema
from infraestrutura.repositorios.repositorio_acesso_sqlite import RepositorioAcessoSqlite
from aplicacao.casos_de_uso.vincular_acessos_rh import VincularAcessosRh
from dominio.objetos_valor.sistema import Sistema

SICA = "SICA_RA"


def _ativo(mat, cpf, nome):
    return RhAtivo(matricula=mat, nome=nome, cpf=cpf, cargo_codigo="CG",
                   cargo_descricao="ANALISTA", centro_custo_codigo="100",
                   departamento="TI", data_admissao=date(2020, 1, 1), situacao="ATIVO")


def _acesso(usuario, cpf_mascarado, nome):
    return AcessoSistema(sistema=SICA, usuario=usuario, perfil="P1",
                         nome_usuario=nome, cpf=cpf_mascarado, situacao="ATIVO")


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_mask_")
        self.conexao = ConexaoBancoDados(os.path.join(self._tmp, "m.db"))
        self.conexao.inicializar()

    def _seed(self, *orm):
        s = self.conexao.sessao()
        s.add_all(orm)
        s.commit()
        s.close()

    def _acessos(self):
        return {a.usuario: a for a in
                RepositorioAcessoSqlite(self.conexao).obter_por_sistema(Sistema.SICA_RA)}


class TestCpfMascarado(_Base):

    def test_cpf_parcial_mais_nome_nivel3(self):
        # M1 tem CPF completo iniciando por '39328'; acesso traz '39328XXX' + nome
        self._seed(
            _ativo("M1", "39328111111", "JOAO SILVA"),
            _acesso("u1", "39328XXX", "JOAO SILVA"),
        )
        VincularAcessosRh(self.conexao).executar()
        a = self._acessos()["u1"]
        self.assertEqual(a.matricula_vinculada, "M1")
        self.assertEqual(a.metodo_vinculacao, "CPF_PARCIAL_NOME")

    def test_parcial_ambiguo_grava_candidatos(self):
        # dois ativos com mesmo prefixo de CPF e mesmo nome -> ambiguo
        self._seed(
            _ativo("M1", "39328111111", "JOAO SILVA"),
            _ativo("M2", "39328222222", "JOAO SILVA"),
            _acesso("u1", "39328XXX", "JOAO SILVA"),
        )
        VincularAcessosRh(self.conexao).executar()
        a = self._acessos()["u1"]
        self.assertEqual(a.metodo_vinculacao, "CPF_PARCIAL_NOME")
        self.assertIsNotNone(a.candidatos_matricula)
        self.assertEqual(set(a.candidatos_matricula), {"M1", "M2"})

    def test_parcial_curto_demais_cai_para_nome(self):
        # '39XX' -> so 2 digitos contiguos (<5) -> nivel 3 nao aplica -> nivel 4 (nome)
        self._seed(
            _ativo("M1", "39328111111", "MARIA SOUZA"),
            _acesso("u1", "39XX", "MARIA SOUZA"),
        )
        VincularAcessosRh(self.conexao).executar()
        a = self._acessos()["u1"]
        self.assertEqual(a.matricula_vinculada, "M1")
        self.assertEqual(a.metodo_vinculacao, "NOME")


if __name__ == "__main__":
    unittest.main(verbosity=2)
