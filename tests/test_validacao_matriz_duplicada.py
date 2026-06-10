# -*- coding: utf-8 -*-
"""Regressao: linha duplicada na matriz (mesmo cargo+sistema+perfil) NAO deve
virar EM_ANALISE. EM_ANALISE so quando ha 2+ perfis DISTINTOS para o cargo.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import RhAtivo, PerfilEsperadoModel, AcessoSistema, ValidacaoAcessoModel
from aplicacao.casos_de_uso.validar_acessos_sistema import ValidarAcessosSistema

SYS = "SYSTUR"


def _rh(mat, cc="100", cargo="ANALISTA"):
    return RhAtivo(matricula=mat, nome=mat, cpf=mat.rjust(11, "0"), cargo_codigo="CG",
                   cargo_descricao=cargo, centro_custo_codigo=cc, situacao="ATIVO")


def _pe(perfil, manual=False, cc="100", cargo="ANALISTA"):
    return PerfilEsperadoModel(cargo_codigo=cc, cargo_descricao=cargo, sistema=SYS,
                               perfil=perfil, acesso_manual=manual)


class TestMatrizDuplicada(unittest.TestCase):

    def _run(self, perfis, acesso_perfil=None, mat="M1"):
        tmp = tempfile.mkdtemp(prefix="cvc_dup_")
        cx = ConexaoBancoDados(os.path.join(tmp, "d.db"))
        cx.inicializar()
        s = cx.sessao()
        s.add(_rh(mat))
        for pe in perfis:
            s.add(pe)
        # garante SYSTUR com dados
        s.add(AcessoSistema(sistema=SYS, usuario="z", perfil="ZZ", matricula_vinculada="ZZ"))
        if acesso_perfil:
            s.add(AcessoSistema(sistema=SYS, usuario="u", perfil=acesso_perfil, matricula_vinculada=mat))
        s.commit()
        s.close()
        ValidarAcessosSistema(cx).executar()
        s = cx.sessao()
        rows = [(r.status, r.perfil_esperado) for r in
                s.query(ValidacaoAcessoModel).filter_by(matricula=mat).all()]
        s.close()
        return rows

    def test_duplicata_exata_com_acesso_e_ok(self):
        # 2x a mesma linha 'P1' + funcionario tem P1 -> OK/Aderente (1 linha)
        rows = self._run([_pe("P1"), _pe("P1")], acesso_perfil="P1")
        self.assertEqual(rows, [("OK", "P1")])

    def test_duplicata_exata_sem_acesso_e_sem_acesso(self):
        # 2x 'P1' + sem acesso -> SEM_ACESSO (1 linha, nao EM_ANALISE)
        rows = self._run([_pe("P1"), _pe("P1")])
        self.assertEqual(rows, [("SEM_ACESSO", "P1")])

    def test_dois_perfis_distintos_continuam_em_analise(self):
        # 2 perfis DISTINTOS -> EM_ANALISE (fix nao quebra esse caso)
        rows = self._run([_pe("P1"), _pe("P2")])
        self.assertEqual({s for s, _ in rows}, {"EM_ANALISE"})
        self.assertEqual({p for _, p in rows}, {"P1", "P2"})

    def test_mesmo_perfil_manual_diferente_dedup_para_um(self):
        # mesma 'P1' com manual True/False -> 1 perfil distinto -> nao EM_ANALISE
        rows = self._run([_pe("P1", manual=False), _pe("P1", manual=True)])
        self.assertEqual(rows, [("SEM_ACESSO", "P1")])


if __name__ == "__main__":
    unittest.main(verbosity=2)
