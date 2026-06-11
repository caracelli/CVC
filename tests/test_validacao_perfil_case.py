# -*- coding: utf-8 -*-
"""Regressao: o casamento de perfil e' case-insensitive (+ acento/trim) para
TODOS os sistemas. A matriz pode vir 'Analista_M_C' e o extrato 'ANALISTA_M_C'
— e' o mesmo perfil, deve dar OK/Aderente, nao DIVERGENTE.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import (
    RhAtivo, PerfilEsperadoModel, AcessoSistema, ValidacaoAcessoModel)
from aplicacao.casos_de_uso.validar_acessos_sistema import ValidarAcessosSistema

SYS = "SYSTUR"


class TestPerfilCaseInsensitive(unittest.TestCase):

    def _run(self, esperado, atual):
        tmp = tempfile.mkdtemp(prefix="cvc_case_")
        cx = ConexaoBancoDados(os.path.join(tmp, "d.db"))
        cx.inicializar()
        s = cx.sessao()
        s.add(RhAtivo(matricula="M1", nome="M1", cpf="11111111111", cargo_codigo="CG",
                      cargo_descricao="ANALISTA", centro_custo_codigo="100", situacao="ATIVO"))
        s.add(PerfilEsperadoModel(cargo_codigo="100", cargo_descricao="ANALISTA",
                                  sistema=SYS, perfil=esperado))
        # garante SYSTUR com dados + o acesso do funcionario
        s.add(AcessoSistema(sistema=SYS, usuario="z", perfil="ZZ", matricula_vinculada="ZZ"))
        s.add(AcessoSistema(sistema=SYS, usuario="u1", perfil=atual, matricula_vinculada="M1"))
        s.commit(); s.close()
        ValidarAcessosSistema(cx).executar()
        s = cx.sessao()
        rows = [(r.status, r.perfil_esperado, r.perfil_atual)
                for r in s.query(ValidacaoAcessoModel).filter_by(matricula="M1").all()]
        s.close()
        return rows

    def test_so_difere_a_caixa_vira_OK(self):
        rows = self._run("Analista_M_C", "ANALISTA_M_C")
        self.assertEqual([r[0] for r in rows], ["OK"])

    def test_caixa_e_acento_vira_OK(self):
        rows = self._run("Operações", "OPERACOES")
        self.assertEqual([r[0] for r in rows], ["OK"])

    def test_perfil_realmente_diferente_continua_divergente(self):
        rows = self._run("Analista_M_C", "GERENTE_X")
        self.assertTrue(any(r[0] == "DIVERGENTE" for r in rows),
                        f"esperava DIVERGENTE, veio {rows}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
