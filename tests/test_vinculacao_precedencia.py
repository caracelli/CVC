# -*- coding: utf-8 -*-
"""Vinculacao integrada: precedencia ativo-vs-desligado, ambiguidade e
candidatos JSON. Roda VincularAcessosRh / vincular_multi_chave reais.
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import RhAtivo, RhDesligado, AcessoSistema
from infraestrutura.repositorios.repositorio_acesso_sqlite import RepositorioAcessoSqlite
from aplicacao.casos_de_uso.vincular_acessos_rh import VincularAcessosRh
from dominio.objetos_valor.sistema import Sistema

IC = Sistema.IC_INTEGRADOR_CONTABIL.value


def _ativo(mat, cpf="", email=None, nome="F", cc="100"):
    return RhAtivo(matricula=mat, nome=nome, cpf=cpf, email=email,
                   cargo_codigo="CG", cargo_descricao="ANALISTA",
                   centro_custo_codigo=cc, departamento="TI",
                   data_admissao=date(2020, 1, 1), situacao="ATIVO")


def _desligado(mat, cpf="", email=None, nome="F"):
    return RhDesligado(matricula=mat, nome=nome, cpf=cpf, email=email,
                       cargo_codigo="CG", cargo_descricao="ANALISTA",
                       centro_custo_codigo="100", departamento="TI",
                       data_admissao=date(2018, 1, 1), data_desligamento=date(2026, 1, 1))


def _ad(mat, login, cpf="", email=None, nome="F", tipo="PRESTADOR"):
    """Identidade vinda do diretorio (AD) — mora no rh_ativos com matricula
    namespaced (FRANQ-/PREST-) e tipo_vinculo proprio."""
    return RhAtivo(matricula=mat, nome=nome, cpf=cpf, email=email, login=login,
                   cargo_codigo="", cargo_descricao="", centro_custo_codigo="",
                   departamento="", data_admissao=None, situacao="ATIVO",
                   tipo_vinculo=tipo)


def _acesso(usuario, cpf=None, email=None, nome="F", perfil="P1"):
    return AcessoSistema(sistema=IC, usuario=usuario, perfil=perfil,
                         nome_usuario=nome, cpf=cpf, email=email, situacao="ATIVO")


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_vinc_")
        self.conexao = ConexaoBancoDados(os.path.join(self._tmp, "v.db"))
        self.conexao.inicializar()

    def _seed(self, *orm):
        s = self.conexao.sessao()
        s.add_all(orm)
        s.commit()
        s.close()

    def _acessos(self):
        return {a.usuario: a for a in RepositorioAcessoSqlite(self.conexao).obter_por_sistema(
            Sistema.IC_INTEGRADOR_CONTABIL)}


class TestPrecedenciaAtivoDesligado(_Base):

    def test_ativo_prevalece_sobre_desligado_no_mesmo_cpf(self):
        # mesmo CPF em ativo e desligado (re-contratacao): o acesso deve ligar
        # ao ATIVO (cargo atual), nao ao desligado.
        self._seed(
            _ativo("ATV", cpf="11111111111", nome="ANA"),
            _desligado("DESL", cpf="11111111111", nome="ANA"),
            _acesso("u1", cpf="11111111111", nome="ANA"),
        )
        contagem = VincularAcessosRh(self.conexao).executar()
        a = self._acessos()["u1"]
        self.assertEqual(a.matricula_vinculada, "ATV",
                         "o ativo deve prevalecer sobre o desligado no mesmo CPF")
        self.assertEqual(a.metodo_vinculacao, "CPF")

    def test_ativo_prevalece_por_email(self):
        # CPFs distintos (so o email colide) — Funcionario exige CPF nao-vazio
        self._seed(
            _ativo("ATV", cpf="00000000001", email="x@cvc.com", nome="ANA"),
            _desligado("DESL", cpf="00000000002", email="x@cvc.com", nome="ANA"),
            _acesso("u1", email="x@cvc.com", nome="ANA"),
        )
        VincularAcessosRh(self.conexao).executar()
        self.assertEqual(self._acessos()["u1"].matricula_vinculada, "ATV")


class TestPrecedenciaCltSobreDiretorioAd(_Base):
    """O AD e' importado ANTES do RH no pipeline (decisao da area: AD e' a base
    principal de identidade). A precedencia no matching NAO pode depender dessa
    ordem de insercao: quem tem vinculo empregaticio (CLT/terceiro) vence, e a
    identidade de diretorio so responde pelos orfaos."""

    def test_clt_vence_o_ad_no_mesmo_cpf_mesmo_inserido_depois(self):
        # AD semeado PRIMEIRO (ordem adversa, igual a do pipeline real)
        self._seed(
            _ad("PREST-corpp001", login="corpp001", cpf="11111111111", nome="ANA"),
            _ativo("TERC-11111111111", cpf="11111111111", nome="ANA"),
            _acesso("corpp001", cpf="11111111111", nome="ANA"),
        )
        VincularAcessosRh(self.conexao).executar()
        a = self._acessos()["corpp001"]
        self.assertEqual(a.matricula_vinculada, "TERC-11111111111",
                         "o vinculo do RH deve prevalecer sobre a identidade AD")
        self.assertEqual(a.metodo_vinculacao, "CPF")

    def test_orfao_so_com_login_liga_ao_ad(self):
        self._seed(
            _ad("FRANQ-corpp009", login="corpp009", nome="BIA", tipo="FRANQUEADO"),
            _ativo("M1", cpf="11111111111", nome="ANA"),
            _acesso("corpp009", nome=""),   # sem cpf, sem email, sem nome
        )
        contagem = VincularAcessosRh(self.conexao).executar()
        a = self._acessos()["corpp009"]
        self.assertEqual(a.matricula_vinculada, "FRANQ-corpp009")
        self.assertEqual(a.metodo_vinculacao, "LOGIN")
        self.assertEqual(contagem.get("LOGIN", 0), 1)


class TestAmbiguidadeCandidatos(_Base):

    def test_nome_ambiguo_grava_candidatos_json(self):
        # 2 ativos com o mesmo nome; acesso so com nome -> nivel NOME, ambiguo
        self._seed(
            _ativo("M1", cpf="00000000001", nome="JOAO SILVA"),
            _ativo("M2", cpf="00000000002", nome="JOAO SILVA"),
            _acesso("u1", nome="JOAO SILVA"),   # sem cpf/email -> cai no nivel NOME
        )
        VincularAcessosRh(self.conexao).executar()
        a = self._acessos()["u1"]
        self.assertEqual(a.metodo_vinculacao, "NOME")
        self.assertIsNotNone(a.candidatos_matricula)
        # obter_por_sistema ja desserializa candidatos_matricula para lista
        self.assertEqual(set(a.candidatos_matricula), {"M1", "M2"})

    def test_cpf_unico_nao_grava_candidatos(self):
        self._seed(_ativo("M1", cpf="11111111111", nome="ANA"),
                   _acesso("u1", cpf="11111111111", nome="ANA"))
        VincularAcessosRh(self.conexao).executar()
        a = self._acessos()["u1"]
        self.assertEqual(a.score_vinculacao, 1.0)
        self.assertIsNone(a.candidatos_matricula)


class TestNaoVinculado(_Base):

    def test_terceiro_sem_match_fica_nao_vinculado(self):
        self._seed(_ativo("M1", cpf="11111111111", nome="ANA"),
                   _acesso("u1", cpf="99999999999", nome="TERCEIRO ZZZ"))
        contagem = VincularAcessosRh(self.conexao).executar()
        a = self._acessos()["u1"]
        self.assertIsNone(a.matricula_vinculada)
        self.assertEqual(a.metodo_vinculacao, "NAO_VINCULADO")
        self.assertEqual(contagem.get("NAO_VINCULADO", 0), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
