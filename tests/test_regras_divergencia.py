# -*- coding: utf-8 -*-
"""Regras de divergencia (camada de dominio) — profundidade.

Cobre RegraAcessoDesligado, RegraAcessoTransferido, RegraAcessoSemVinculo e o
ServicoAnaliseDivergencias que as orquestra (todas as regras juntas).
"""
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dominio.objetos_valor.cargo import Cargo
from dominio.objetos_valor.sistema import Sistema
from dominio.objetos_valor.tipo_divergencia import TipoDivergencia
from dominio.entidades.funcionario_ativo import FuncionarioAtivo
from dominio.entidades.funcionario_desligado import FuncionarioDesligado
from dominio.entidades.transferido import Transferido
from dominio.entidades.perfil_acesso import PerfilAcesso
from dominio.entidades.perfil_esperado import PerfilEsperado
from dominio.regras.regra_acesso_desligado import RegraAcessoDesligado
from dominio.regras.regra_acesso_transferido import RegraAcessoTransferido
from dominio.regras.regra_acesso_sem_vinculo import RegraAcessoSemVinculo
from dominio.servicos_dominio.servico_analise_divergencias import ServicoAnaliseDivergencias


def _cargo(cc="100", desc="ANALISTA", dep="TI"):
    return Cargo(codigo="CG", descricao=desc, departamento=dep, centro_custo=cc)


def _ativo(mat, cpf="111", cc="100", desc="ANALISTA", dep="TI"):
    return FuncionarioAtivo(matricula=mat, nome=f"F{mat}", cpf=cpf,
                            cargo=_cargo(cc, desc, dep), situacao="ATIVO")


def _desligado(mat, cpf="222"):
    return FuncionarioDesligado(matricula=mat, nome=f"D{mat}", cpf=cpf,
                                cargo=_cargo(), data_desligamento=date(2026, 1, 1))


def _acesso(usuario, perfil="P1", cpf="", vinc=None, sistema=Sistema.SYSTUR):
    return PerfilAcesso(usuario=usuario, nome_usuario="N", sistema=sistema,
                        perfil=perfil, situacao="ATIVO", cpf=cpf, matricula_vinculada=vinc)


# ───────────────── RegraAcessoDesligado ─────────────────
class TestRegraAcessoDesligado(unittest.TestCase):
    def setUp(self):
        self.regra = RegraAcessoDesligado()

    def test_acesso_de_desligado_gera_divergencia(self):
        divs = self.regra.verificar([_acesso("u1", vinc="20")], [_desligado("20")])
        self.assertEqual(len(divs), 1)
        self.assertEqual(divs[0].tipo, TipoDivergencia.ACESSO_DESLIGADO)
        self.assertEqual(divs[0].matricula, "20")

    def test_acesso_de_ativo_nao_gera(self):
        divs = self.regra.verificar([_acesso("u1", vinc="10")], [_desligado("20")])
        self.assertEqual(divs, [])

    def test_acesso_sem_vinculo_nao_gera(self):
        divs = self.regra.verificar([_acesso("u1", cpf="999", vinc=None)], [_desligado("20")])
        self.assertEqual(divs, [])

    def test_varios_acessos_do_mesmo_desligado(self):
        divs = self.regra.verificar(
            [_acesso("u1", vinc="20"), _acesso("u2", vinc="20", sistema=Sistema.IC_INTEGRADOR_CONTABIL)],
            [_desligado("20")])
        self.assertEqual(len(divs), 2)
        self.assertTrue(all(d.tipo == TipoDivergencia.ACESSO_DESLIGADO for d in divs))


# ───────────────── RegraAcessoTransferido ─────────────────
class TestRegraAcessoTransferido(unittest.TestCase):
    def setUp(self):
        self.regra = RegraAcessoTransferido()

    def _transf(self, mat, dep_novo, dep_antigo):
        func = _ativo(mat, dep=dep_novo)
        return Transferido(funcionario=func, cargo_anterior=_cargo(dep=dep_antigo),
                           data_transferencia=date(2026, 1, 1))

    def test_mudanca_de_departamento_gera_revisao(self):
        t = self._transf("30", dep_novo="Comercial", dep_antigo="TI")
        divs = self.regra.verificar([_acesso("u1", vinc="30")], [t])
        self.assertEqual(len(divs), 1)
        self.assertEqual(divs[0].tipo, TipoDivergencia.ACESSO_TRANSFERIDO)

    def test_mesmo_departamento_nao_gera(self):
        t = self._transf("30", dep_novo="TI", dep_antigo="TI")
        divs = self.regra.verificar([_acesso("u1", vinc="30")], [t])
        self.assertEqual(divs, [])

    def test_acesso_de_nao_transferido_nao_gera(self):
        t = self._transf("30", dep_novo="Comercial", dep_antigo="TI")
        divs = self.regra.verificar([_acesso("u1", vinc="99")], [t])
        self.assertEqual(divs, [])


# ───────────────── RegraAcessoSemVinculo (bordas) ─────────────────
class TestRegraAcessoSemVinculoBordas(unittest.TestCase):
    def setUp(self):
        self.regra = RegraAcessoSemVinculo()

    def test_cpf_vazio_nao_gera(self):
        self.assertEqual(self.regra.verificar([_acesso("u1", cpf="", vinc=None)]), [])

    def test_cpf_com_vinculo_nao_gera(self):
        self.assertEqual(self.regra.verificar([_acesso("u1", cpf="999", vinc="10")]), [])

    def test_varios_sem_vinculo(self):
        divs = self.regra.verificar([
            _acesso("u1", cpf="999", vinc=None),
            _acesso("u2", cpf="888", vinc=None),
        ])
        self.assertEqual(len(divs), 2)
        self.assertTrue(all(d.tipo == TipoDivergencia.ACESSO_SEM_VINCULO_RH for d in divs))


# ───────────────── ServicoAnaliseDivergencias (orquestracao) ─────────────────
class TestServicoAnaliseDivergencias(unittest.TestCase):
    def test_combina_todas_as_regras_uma_de_cada(self):
        ativos = [_ativo("10", cc="100", desc="ANALISTA"),
                  _ativo("30", cc="200", desc="GERENTE", dep="Comercial")]
        desligados = [_desligado("20")]
        transf = Transferido(funcionario=_ativo("30", cc="200", desc="GERENTE", dep="Comercial"),
                             cargo_anterior=_cargo(cc="200", desc="GERENTE", dep="TI"),
                             data_transferencia=date(2026, 1, 1))
        perfis = [PerfilEsperado(cargo_codigo="100", sistema=Sistema.SYSTUR,
                                 perfil="OK", cargo_descricao="ANALISTA")]
        acessos = [
            _acesso("uDes", vinc="20"),                       # ACESSO_DESLIGADO
            _acesso("uSem", cpf="999", vinc=None),            # ACESSO_SEM_VINCULO_RH
            _acesso("uPerf", perfil="X", cpf="111", vinc="10"),  # PERFIL_INVALIDO
            _acesso("uTransf", vinc="30"),                    # ACESSO_TRANSFERIDO
        ]
        servico = ServicoAnaliseDivergencias(perfis)
        divs = servico.analisar(acessos=acessos, ativos=ativos,
                                desligados=desligados, transferidos=[transf])
        tipos = {d.tipo for d in divs}
        self.assertIn(TipoDivergencia.ACESSO_DESLIGADO, tipos)
        self.assertIn(TipoDivergencia.ACESSO_SEM_VINCULO_RH, tipos)
        self.assertIn(TipoDivergencia.PERFIL_INVALIDO, tipos)
        self.assertIn(TipoDivergencia.ACESSO_TRANSFERIDO, tipos)


if __name__ == "__main__":
    unittest.main(verbosity=2)
