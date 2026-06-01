# -*- coding: utf-8 -*-
"""Testes do RepositorioAcessoSqlite com nova PK (sistema, usuario, perfil)
e correcoes (email real, dedup por trio, gravacao de metodo/score).
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dominio.entidades.perfil_acesso import PerfilAcesso
from dominio.objetos_valor.sistema import Sistema
from dominio.servicos_dominio.servico_vinculacao_multi_chave import (
    FuncionarioRef, METODO_CPF,
)
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.repositorios.repositorio_acesso_sqlite import RepositorioAcessoSqlite


def _p(usuario, perfil, sistema=Sistema.SYSTUR, **kw):
    base = dict(
        usuario=usuario, nome_usuario=kw.get("nome", f"USER {usuario}"),
        sistema=sistema, perfil=perfil, situacao="ATIVO",
        cpf=kw.get("cpf"), email=kw.get("email"),
    )
    return PerfilAcesso(**base)


class TestPKMultiPerfilEEmail(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.cx = ConexaoBancoDados(self.tmp.name)
        self.cx.inicializar()
        self.repo = RepositorioAcessoSqlite(self.cx)

    def tearDown(self):
        try:
            self.cx.engine.dispose()
            os.unlink(self.tmp.name)
        except Exception:
            pass

    # ---- PK trio: usuario com varios perfis ----
    def test_multi_perfil_mesmo_usuario_todas_linhas_persistem(self):
        # ANTES: PK (sistema, usuario) so deixaria 1 sobreviver.
        # AGORA: PK (sistema, usuario, perfil) deixa todas.
        perfis = [
            _p("amneto", "ACESSO_HOTEL_NAC", cpf="11111111111", email="a@x.com"),
            _p("amneto", "ACESSO_CARRO_NAC", cpf="11111111111", email="a@x.com"),
            _p("amneto", "CAD_FORNECEDOR",   cpf="11111111111", email="a@x.com"),
        ]
        self.repo.substituir_sistema(Sistema.SYSTUR, perfis, "arquivo.csv")

        salvos = self.repo.obter_por_sistema(Sistema.SYSTUR)
        self.assertEqual(len(salvos), 3, "todos os 3 perfis devem persistir")
        perfis_salvos = sorted(p.perfil for p in salvos)
        self.assertEqual(perfis_salvos,
                         sorted(["ACESSO_HOTEL_NAC", "ACESSO_CARRO_NAC", "CAD_FORNECEDOR"]))

    def test_email_gravado_corretamente(self):
        # ANTES: o repositorio gravava email=None hardcoded.
        # AGORA: grava o que vem na entidade.
        self.repo.substituir_sistema(
            Sistema.SYSTUR,
            [_p("user1", "PERFIL_X", cpf="11111111111", email="joao@cvc.com")],
            "arq.csv",
        )
        salvos = self.repo.obter_por_sistema(Sistema.SYSTUR)
        self.assertEqual(salvos[0].email, "joao@cvc.com")

    def test_email_nulo_continua_nulo(self):
        # Casos com email vazio nao devem virar string vazia
        self.repo.substituir_sistema(
            Sistema.SYSTUR,
            [_p("user2", "PERFIL_Y", cpf="22222222222", email=None)],
            "arq.csv",
        )
        salvos = self.repo.obter_por_sistema(Sistema.SYSTUR)
        self.assertIsNone(salvos[0].email)

    # ---- Contagem ----
    def test_contar_por_sistema_bate_com_len_e_isola_sistema(self):
        self.repo.substituir_sistema(Sistema.SYSTUR, [
            _p("u1", "P1", cpf="1"), _p("u1", "P2", cpf="1"), _p("u2", "P1", cpf="2"),
        ], "systur.csv")
        self.repo.substituir_sistema(Sistema.SIGOT, [
            _p("u9", "PX", sistema=Sistema.SIGOT, cpf="9"),
        ], "sigot.csv")
        # bate com o len de obter_por_sistema
        self.assertEqual(self.repo.contar_por_sistema(Sistema.SYSTUR), 3)
        self.assertEqual(self.repo.contar_por_sistema(Sistema.SYSTUR),
                         len(self.repo.obter_por_sistema(Sistema.SYSTUR)))
        # isola por sistema
        self.assertEqual(self.repo.contar_por_sistema(Sistema.SIGOT), 1)

    # ---- Dedup ----
    def test_dedup_por_trio_mantem_ultimo(self):
        # Mesmo trio aparece 2x no arquivo: mantem o ultimo
        perfis = [
            _p("user3", "PERFIL_A", cpf="3", nome="V1"),
            _p("user3", "PERFIL_A", cpf="3", nome="V2"),  # ultimo
            _p("user3", "PERFIL_B", cpf="3"),
        ]
        self.repo.substituir_sistema(Sistema.SYSTUR, perfis, "arq.csv")
        salvos = self.repo.obter_por_sistema(Sistema.SYSTUR)
        # 2 linhas (PERFIL_A com nome=V2 + PERFIL_B)
        self.assertEqual(len(salvos), 2)
        a = next(p for p in salvos if p.perfil == "PERFIL_A")
        self.assertEqual(a.nome_usuario, "V2")

    def test_substituir_sistema_apaga_anterior(self):
        # Snapshot semantic: nova importacao substitui tudo do mesmo sistema
        self.repo.substituir_sistema(
            Sistema.SYSTUR, [_p("u1", "P1")], "arq1.csv")
        self.repo.substituir_sistema(
            Sistema.SYSTUR, [_p("u2", "P2")], "arq2.csv")
        salvos = self.repo.obter_por_sistema(Sistema.SYSTUR)
        self.assertEqual(len(salvos), 1)
        self.assertEqual(salvos[0].usuario, "u2")

    def test_substituir_sistema_nao_afeta_outros_sistemas(self):
        self.repo.substituir_sistema(Sistema.SYSTUR, [_p("u1", "P1")], "arq.csv")
        self.repo.substituir_sistema(
            Sistema.SIGOT, [_p("u2", "P2", sistema=Sistema.SIGOT)], "arq.csv")
        # Reimportar SYSTUR — SIGOT permanece
        self.repo.substituir_sistema(
            Sistema.SYSTUR, [_p("u1b", "P1b")], "arq2.csv")
        self.assertEqual(len(self.repo.obter_por_sistema(Sistema.SIGOT)), 1)
        self.assertEqual(len(self.repo.obter_por_sistema(Sistema.SYSTUR)), 1)


class TestVinculacao(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.cx = ConexaoBancoDados(self.tmp.name)
        self.cx.inicializar()
        self.repo = RepositorioAcessoSqlite(self.cx)

    def tearDown(self):
        try:
            self.cx.engine.dispose()
            os.unlink(self.tmp.name)
        except Exception:
            pass

    def test_vincular_por_cpf_legado_grava_metodo_e_score(self):
        self.repo.substituir_sistema(
            Sistema.SYSTUR,
            [_p("u1", "P1", cpf="11111111111"),
             _p("u2", "P2", cpf="22222222222")],
            "arq.csv",
        )
        mapa = {"11111111111": "MAT1", "22222222222": "MAT2"}
        n = self.repo.vincular_por_cpf(mapa)
        self.assertEqual(n, 2)
        # Verifica metodo e score
        salvos = sorted(self.repo.obter_por_sistema(Sistema.SYSTUR),
                        key=lambda p: p.usuario)
        for p in salvos:
            self.assertEqual(p.metodo_vinculacao, "CPF")
            self.assertEqual(p.score_vinculacao, 1.0)
            self.assertIsNone(p.candidatos_matricula)

    def test_vincular_multi_chave_cascata_completa(self):
        # 3 acessos com chaves diferentes: CPF, email, nome
        self.repo.substituir_sistema(
            Sistema.SYSTUR,
            [
                _p("u_cpf",   "P1", cpf="11111111111"),
                _p("u_email", "P2", email="maria@cvc.com"),
                _p("u_nome",  "P3", nome="PEDRO LIMA"),
                _p("u_sem",   "P4"),  # nada para vincular
            ],
            "arq.csv",
        )
        funcs = [
            FuncionarioRef(matricula="MAT_CPF",   cpf="11111111111"),
            FuncionarioRef(matricula="MAT_EMAIL", email="maria@cvc.com"),
            FuncionarioRef(matricula="MAT_NOME",  nome="PEDRO LIMA"),
        ]
        contagem = self.repo.vincular_multi_chave(funcs)
        self.assertEqual(contagem.get("CPF"), 1)
        self.assertEqual(contagem.get("EMAIL"), 1)
        self.assertEqual(contagem.get("NOME"), 1)
        self.assertEqual(contagem.get("NAO_VINCULADO"), 1)

        # Verifica que cada um foi vinculado a sua matricula correta
        salvos = {p.usuario: p for p in self.repo.obter_por_sistema(Sistema.SYSTUR)}
        self.assertEqual(salvos["u_cpf"].matricula_vinculada, "MAT_CPF")
        self.assertEqual(salvos["u_email"].matricula_vinculada, "MAT_EMAIL")
        self.assertEqual(salvos["u_nome"].matricula_vinculada, "MAT_NOME")
        self.assertIsNone(salvos["u_sem"].matricula_vinculada)


if __name__ == "__main__":
    unittest.main()
