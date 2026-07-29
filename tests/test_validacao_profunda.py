# -*- coding: utf-8 -*-
"""Cenarios PROFUNDOS da validacao de acesso (ValidarAcessosSistema.executar()).

Vai alem do happy-path: caminho CCO (origem_matriz=CCO), flag acesso_manual,
agregacao de perfil_atual com multiplos acessos, aproximacao do IC combinada
com multi-acesso, e funcionario multi-sistema avaliado de forma independente.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import (
    RhAtivo, PerfilEsperadoModel, AcessoSistema, MatrizCcoModel, ValidacaoAcessoModel,
)
from aplicacao.casos_de_uso.validar_acessos_sistema import ValidarAcessosSistema

IC = "IC_INTEGRADOR_CONTABIL"
SYSTUR = "SYSTUR"


def _rh(mat, cc, cargo):
    return RhAtivo(matricula=mat, nome=f"F{mat}", cpf=mat.rjust(11, "0"),
                   cargo_codigo="CG", cargo_descricao=cargo,
                   centro_custo_codigo=cc, centro_custo_nome="CC", situacao="ATIVO")


def _pe(cc, cargo, sistema, perfil, manual=False):
    return PerfilEsperadoModel(cargo_codigo=cc, cargo_descricao=cargo,
                               sistema=sistema, perfil=perfil, acesso_manual=manual)


def _ac(sistema, usuario, perfil, matricula):
    return AcessoSistema(sistema=sistema, usuario=usuario, perfil=perfil,
                         nome_usuario="N", situacao="ATIVO", matricula_vinculada=matricula)


class TestValidacaoProfunda(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="cvc_prof_")
        cls.conexao = ConexaoBancoDados(os.path.join(cls._tmp, "p.db"))
        cls.conexao.inicializar()

        s = cls.conexao.sessao()
        s.add_all([
            # c1: caminho CCO (sem matriz de perfis; mapeado so na CCO)
            _rh("c1", "400", "OPERADOR"),
            # c2: acesso_manual=True na matriz, sem acesso -> SEM_ACESSO manual
            _rh("c2", "500", "DIRETOR"),
            # c3: 1 perfil esperado, 2 acessos atuais -> DIVERGENTE com perfil_atual agregado
            _rh("c3", "600", "ZX"),
            # c4: IC aproximacao + multi-acesso (um deles casa) -> ADERENTE
            _rh("c4", "700", "WY"),
            # c5: multi-sistema (IC ok + SYSTUR faltando)
            _rh("c5", "800", "Q"),

            # matriz de perfis (MATRIZ)
            _pe("500", "DIRETOR", IC, "IC CONSULTA", manual=True),
            _pe("600", "ZX", SYSTUR, "P1"),
            _pe("700", "WY", IC, "IC CONSULTA"),
            _pe("800", "Q", IC, "IC TAL"),
            _pe("800", "Q", SYSTUR, "S1"),

            # matriz CCO (origem CCO) — "Systur" como texto livre
            MatrizCcoModel(cc="400", cc_nome="X", funcao="OPERADOR",
                           sistema="Systur", perfil="OP1"),

            # acessos (ja vinculados)
            _ac(SYSTUR, "c3u", "P2", "c3"),
            _ac(SYSTUR, "c3u", "P3", "c3"),
            _ac(IC, "c4u", "IC_APROVADOR", "c4"),
            _ac(IC, "c4u", "IC_CONSULTA", "c4"),
            _ac(IC, "c5u", "IC_TAL", "c5"),   # casa "IC TAL" por aproximacao
            # (garante IC e SYSTUR com dados; SYSTUR ja tem via c3)
        ])
        s.commit()
        s.close()

        ValidarAcessosSistema(cls.conexao).executar()

        s = cls.conexao.sessao()
        cls._by_mat = {}
        for r in s.query(ValidacaoAcessoModel).all():
            cls._by_mat.setdefault(r.matricula, []).append(r)
        s.close()

    def regs(self, mat):
        return self._by_mat.get(mat, [])

    def test_caminho_cco_gera_sem_acesso_com_origem_cco(self):
        r = self.regs("c1")
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0].status, "SEM_ACESSO")
        self.assertEqual(r[0].origem_matriz, "CCO")
        self.assertEqual(r[0].sistema, SYSTUR)
        self.assertEqual(r[0].perfil_esperado, "OP1")

    def test_acesso_manual_propagado_na_validacao(self):
        r = self.regs("c2")
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0].status, "SEM_ACESSO")
        self.assertTrue(bool(r[0].acesso_manual))
        self.assertEqual(r[0].origem_matriz, "MATRIZ")

    def test_multi_acesso_sem_aderente_vira_em_analise(self):
        # 2+ perfis encontrados (P2,P3) e NENHUM aderente -> Em Análise (regra)
        r = self.regs("c3")
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0].status, "EM_ANALISE")
        self.assertEqual(r[0].perfil_atual, "P2, P3")

    def test_aproximacao_ic_com_multi_acesso_um_casa_ok(self):
        # tem IC_APROVADOR e IC_CONSULTA; esperado "IC CONSULTA" -> casa -> OK
        r = self.regs("c4")
        self.assertEqual([x.status for x in r], ["OK"])

    def test_multi_sistema_avaliado_independente(self):
        # IC casa (OK/Aderente, gravado); SYSTUR falta (SEM_ACESSO, gravado)
        r = self.regs("c5")
        por_sis = {x.sistema: x.status for x in r}
        self.assertEqual(por_sis.get(IC), "OK")
        self.assertEqual(por_sis.get(SYSTUR), "SEM_ACESSO")

    def test_situacao_acao_pendente_ou_ok(self):
        # PENDENTE so p/ pendencia (DIVERGENTE/EM_ANALISE); OK e SEM_ACESSO
        # (esperado, informativo) nao sao pendencia (retorno Bruna).
        _INFO = {"OK", "SEM_ACESSO"}
        todos = [x for lst in self._by_mat.values() for x in lst]
        self.assertTrue(todos)
        for x in todos:
            self.assertEqual(x.situacao_acao, "OK" if x.status in _INFO else "PENDENTE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
