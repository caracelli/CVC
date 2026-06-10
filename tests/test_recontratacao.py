# -*- coding: utf-8 -*-
"""Recontratacao end-to-end (fix nº1 + regra de desligado juntos):
pessoa com vinculo ATIVO novo e DESLIGADO antigo (mesmo CPF). O acesso deve
vincular ao ATIVO e NAO ser marcado como ACESSO_DESLIGADO. Contraste: um
desligado puro (sem contraparte ativa) com acesso -> ACESSO_DESLIGADO.
"""
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
from infraestrutura.repositorios.repositorio_divergencia_sqlite import RepositorioDivergenciaSqlite
from aplicacao.casos_de_uso.vincular_acessos_rh import VincularAcessosRh
from aplicacao.casos_de_uso.analisar_divergencias import AnalisarDivergencias
from dominio.objetos_valor.sistema import Sistema
from dominio.objetos_valor.tipo_divergencia import TipoDivergencia

SYS = "SYSTUR"


class TestRecontratacao(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="cvc_recon_")
        cls.conexao = ConexaoBancoDados(os.path.join(cls._tmp, "r.db"))
        cls.conexao.inicializar()
        s = cls.conexao.sessao()
        s.add_all([
            # recontratada: ATIVO novo + DESLIGADO antigo, MESMO CPF
            RhAtivo(matricula="NEW", nome="ANA", cpf="11111111111", cargo_codigo="CG",
                    cargo_descricao="ANALISTA", centro_custo_codigo="100", situacao="ATIVO"),
            RhDesligado(matricula="OLD", nome="ANA", cpf="11111111111", cargo_codigo="CG",
                        cargo_descricao="ANALISTA", centro_custo_codigo="100",
                        data_desligamento=date(2024, 1, 1)),
            # desligado PURO (sem contraparte ativa)
            RhDesligado(matricula="DESL", nome="BRUNO", cpf="22222222222", cargo_codigo="CG",
                        cargo_descricao="X", centro_custo_codigo="200",
                        data_desligamento=date(2025, 1, 1)),
            # acessos sem vinculo previo
            AcessoSistema(sistema=SYS, usuario="uAna", perfil="P1",
                          nome_usuario="ANA", cpf="11111111111", situacao="ATIVO"),
            AcessoSistema(sistema=SYS, usuario="uBruno", perfil="P1",
                          nome_usuario="BRUNO", cpf="22222222222", situacao="ATIVO"),
        ])
        s.commit()
        s.close()
        VincularAcessosRh(cls.conexao).executar()
        AnalisarDivergencias(cls.conexao).executar()
        cls.acessos = {a.usuario: a for a in
                       RepositorioAcessoSqlite(cls.conexao).obter_por_sistema(Sistema.SYSTUR)}
        cls.divs = RepositorioDivergenciaSqlite(cls.conexao).obter_todas()

    def _desligado_divs(self):
        return {d.usuario for d in self.divs
                if d.tipo == TipoDivergencia.ACESSO_DESLIGADO}

    def test_recontratada_vincula_ao_ativo(self):
        self.assertEqual(self.acessos["uAna"].matricula_vinculada, "NEW")

    def test_recontratada_nao_e_acesso_desligado(self):
        # apesar de existir o vinculo OLD desligado com o mesmo CPF
        self.assertNotIn("uAna", self._desligado_divs())

    def test_desligado_puro_e_flagado(self):
        # contraste: BRUNO so existe como desligado -> acesso vira ACESSO_DESLIGADO
        self.assertEqual(self.acessos["uBruno"].matricula_vinculada, "DESL")
        self.assertIn("uBruno", self._desligado_divs())


if __name__ == "__main__":
    unittest.main(verbosity=2)
