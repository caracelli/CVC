# -*- coding: utf-8 -*-
"""Regras de validacao de acesso confirmadas com DADOS SIMULADOS.

Monta um cenario sintetico (RH + matriz de perfis + acessos ja vinculados),
roda o caso de uso REAL ValidarAcessosSistema.executar() e confere o que foi
gravado em validacao_acessos.

Cobre, ponta a ponta:
  - ADERENTE      -> nao gera pendencia (nao e' gravado, por design)
  - DIVERGENTE    -> gravado, com perfil_atual e situacao_acao=PENDENTE
  - SEM_ACESSO    -> gravado
  - EM_ANALISE    -> gravado, 1 linha por perfil possivel
  - NAO_MAPEADO   -> nao gera pendencia (nao e' gravado)
  - APROXIMACAO de perfil escopada ao IC ('IC_CONSULTA' == 'IC CONSULTA')
    versus casamento EXATO do SYSTUR ('P_1' != 'P 1').

Roda sem dependencias extras:  python -m unittest discover -s tests
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import (
    RhAtivo, PerfilEsperadoModel, AcessoSistema, ValidacaoAcessoModel,
)
from aplicacao.casos_de_uso.validar_acessos_sistema import ValidarAcessosSistema

IC = "IC_INTEGRADOR_CONTABIL"
SYSTUR = "SYSTUR"


def _rh(mat, cc, cargo):
    return RhAtivo(
        matricula=mat, nome=f"FUNCIONARIO {mat}", cpf=mat.rjust(11, "0"),
        cargo_codigo="CG", cargo_descricao=cargo,
        centro_custo_codigo=cc, centro_custo_nome="CENTRO", situacao="ATIVO",
    )


def _pe(cc, cargo, sistema, perfil):
    # cargo_codigo guarda o CCUSTO (mesma chave do RhAtivo.centro_custo_codigo)
    return PerfilEsperadoModel(
        cargo_codigo=cc, cargo_descricao=cargo,
        sistema=sistema, perfil=perfil, acesso_manual=False,
    )


def _acesso(sistema, usuario, perfil, matricula):
    return AcessoSistema(
        sistema=sistema, usuario=usuario, perfil=perfil,
        nome_usuario="N", situacao="ATIVO", matricula_vinculada=matricula,
    )


class TestRegrasValidacaoSimulada(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="cvc_sim_")
        cls.conexao = ConexaoBancoDados(os.path.join(cls._tmp, "sim.db"))
        cls.conexao.inicializar()

        s = cls.conexao.sessao()
        s.add_all([
            # ---- RH (funcionarios) ----
            _rh("1", "100", "ANALISTA"),     # IC ADERENTE (aproximacao)
            _rh("2", "100", "ANALISTA"),     # IC DIVERGENTE
            _rh("3", "100", "ANALISTA"),     # IC SEM_ACESSO
            _rh("4", "200", "GERENTE"),      # IC EM_ANALISE (2 perfis)
            _rh("5", "999", "DESCONHECIDO"), # NAO_MAPEADO (sem matriz)
            _rh("6", "300", "VENDEDOR"),     # SYSTUR DIVERGENTE (exato, '_' != ' ')
            _rh("7", "300", "VENDEDOR"),     # SYSTUR ADERENTE (exato)
            # ---- Matriz de perfis esperados ----
            _pe("100", "ANALISTA", IC, "IC CONSULTA"),
            _pe("200", "GERENTE",  IC, "IC CONSULTA"),
            _pe("200", "GERENTE",  IC, "IC APROVADOR"),
            _pe("300", "VENDEDOR", SYSTUR, "P 1"),
            # ---- Acessos ja vinculados ao RH ----
            _acesso(IC, "u1", "IC_CONSULTA", "1"),   # underscore (extrato)
            _acesso(IC, "u2", "IC_APROVADOR", "2"),  # perfil diferente do esperado
            _acesso(IC, "u4", "IC_OUTRO", "4"),   # F4 NAO tem nenhum dos esperados -> EM_ANALISE
            _acesso(SYSTUR, "u6", "P_1", "6"),       # underscore: NAO casa "P 1" (exato)
            _acesso(SYSTUR, "u7", "P 1", "7"),       # casa exato
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

    # ---------------- IC (aproximacao de perfil) ----------------
    def test_ic_aderente_por_aproximacao_vira_ok(self):
        # 'IC_CONSULTA' (extrato) casa 'IC CONSULTA' (matriz) -> OK (conforme),
        # aparece na grid mas situacao_acao=OK (nao e' pendencia).
        r = self.regs("1")
        self.assertEqual([x.status for x in r], ["OK"])
        self.assertEqual(r[0].situacao_acao, "OK")

    def test_ic_divergente_grava_com_perfil_atual_e_pendente(self):
        r = self.regs("2")
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0].status, "DIVERGENTE")
        self.assertIn("IC_APROVADOR", r[0].perfil_atual)
        self.assertEqual(r[0].perfil_esperado, "IC CONSULTA")
        self.assertEqual(r[0].situacao_acao, "PENDENTE")

    def test_ic_sem_acesso(self):
        r = self.regs("3")
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0].status, "SEM_ACESSO")

    def test_ic_em_analise_uma_linha_por_perfil(self):
        r = self.regs("4")
        self.assertEqual(len(r), 2)
        self.assertTrue(all(x.status == "EM_ANALISE" for x in r))
        self.assertEqual({x.perfil_esperado for x in r}, {"IC CONSULTA", "IC APROVADOR"})

    def test_nao_mapeado_nao_gera_pendencia(self):
        # funcionario sem nenhum perfil esperado em nenhuma matriz
        self.assertEqual(self.regs("5"), [])

    # ---------------- SYSTUR (casamento EXATO) ----------------
    def test_systur_nao_usa_aproximacao_diverge(self):
        # 'P_1' (acesso) != 'P 1' (matriz) -> DIVERGENTE (sem aproximacao no SYSTUR)
        r = self.regs("6")
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0].status, "DIVERGENTE")

    def test_systur_exato_aderente_vira_ok(self):
        # 'P 1' == 'P 1' -> OK (conforme), visivel mas nao e' pendencia
        r = self.regs("7")
        self.assertEqual([x.status for x in r], ["OK"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
