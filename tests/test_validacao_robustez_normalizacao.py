# -*- coding: utf-8 -*-
"""Testes PROFUNDOS de robustez de normalizacao no casamento de acessos.

Classe de bug alvo (a mesma do 'ANALISTA_M_C' x 'Analista_M_C'): quando duas
fontes diferentes (RH, matriz, extrato, CCO) trazem o MESMO valor com pequenas
variacoes (caixa, acento, espaco sobrando, separador, zero a esquerda), o
casamento tem que continuar batendo. Senao vira divergencia/pendencia FALSA —
o tipo de bug silencioso que o cliente acaba apontando.

Cada teste monta o cenario minimo e roda o ValidarAcessosSistema de verdade.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import (
    RhAtivo, PerfilEsperadoModel, AcessoSistema, MatrizCcoModel, ValidacaoAcessoModel)
from aplicacao.casos_de_uso.validar_acessos_sistema import ValidarAcessosSistema

SYS = "SYSTUR"
IC = "IC_INTEGRADOR_CONTABIL"


class _Base(unittest.TestCase):

    def _validar(self, rh, perfis=(), acessos=(), cco=()):
        tmp = tempfile.mkdtemp(prefix="cvc_robnorm_")
        cx = ConexaoBancoDados(os.path.join(tmp, "d.db"))
        cx.inicializar()
        s = cx.sessao()
        s.add(RhAtivo(**rh))
        for pe in perfis:
            s.add(PerfilEsperadoModel(**pe))
        for a in acessos:
            s.add(AcessoSistema(**a))
        for r in cco:
            s.add(MatrizCcoModel(**r))
        s.commit(); s.close()
        ValidarAcessosSistema(cx).executar()
        s = cx.sessao()
        rows = [(r.status, r.sistema, r.perfil_esperado, r.perfil_atual)
                for r in s.query(ValidacaoAcessoModel).filter_by(matricula=rh["matricula"]).all()]
        s.close()
        return rows

    def _status(self, rows, sistema=SYS):
        return sorted(st for st, sis, *_ in rows if sis == sistema)

    # cenario padrao: 1 funcionario CLT, 1 perfil esperado pela matriz, 1 acesso
    def _rh(self, cc="100", cargo="ANALISTA", gestor=None, mat="M1"):
        return dict(matricula=mat, nome="FULANO", cpf="11111111111", cargo_codigo="CG",
                    cargo_descricao=cargo, centro_custo_codigo=cc, gestor=gestor, situacao="ATIVO")

    def _pe(self, perfil, cc="100", cargo="ANALISTA", sistema=SYS):
        return dict(cargo_codigo=cc, cargo_descricao=cargo, sistema=sistema, perfil=perfil)

    def _ac(self, perfil, mat="M1", sistema=SYS, usuario="u1"):
        return dict(sistema=sistema, usuario=usuario, perfil=perfil, matricula_vinculada=mat)


class TestPerfilNormalizacao(_Base):
    """Perfil esperado (matriz) x perfil atual (extrato)."""

    def test_caixa(self):
        r = self._validar(self._rh(), [self._pe("Analista_M_C")], [self._ac("ANALISTA_M_C")])
        self.assertEqual(self._status(r), ["OK"])

    def test_acento(self):
        r = self._validar(self._rh(), [self._pe("GESTÃO")], [self._ac("GESTAO")])
        self.assertEqual(self._status(r), ["OK"])

    def test_espaco_sobrando(self):
        r = self._validar(self._rh(), [self._pe("  PERFIL X ")], [self._ac("PERFIL X")])
        self.assertEqual(self._status(r), ["OK"])

    def test_ic_underscore_vs_espaco(self):
        # IC casa por aproximacao: 'IC CONSULTA' (matriz) x 'IC_CONSULTA' (extrato)
        r = self._validar(self._rh(cargo="ANALISTA"),
                          [self._pe("IC CONSULTA", sistema=IC)],
                          [self._ac("IC_CONSULTA", sistema=IC)])
        self.assertEqual(self._status(r, IC), ["OK"])

    def test_perfil_realmente_diferente_nao_casa(self):
        r = self._validar(self._rh(), [self._pe("PERFIL_A")], [self._ac("PERFIL_B")])
        self.assertIn("DIVERGENTE", self._status(r))


class TestCargoNormalizacao(_Base):
    """Cargo do RH x cargo da matriz (chave de lookup da matriz)."""

    def test_caixa(self):
        r = self._validar(self._rh(cargo="Analista"), [self._pe("P1", cargo="ANALISTA")],
                          [self._ac("P1")])
        self.assertEqual(self._status(r), ["OK"])

    def test_acento(self):
        r = self._validar(self._rh(cargo="TÉCNICO"), [self._pe("P1", cargo="TECNICO")],
                          [self._ac("P1")])
        self.assertEqual(self._status(r), ["OK"])

    def test_espaco_sobrando(self):
        r = self._validar(self._rh(cargo="ANALISTA  PL "), [self._pe("P1", cargo="ANALISTA PL")],
                          [self._ac("P1")])
        self.assertEqual(self._status(r), ["OK"])


class TestCentroCustoNormalizacao(_Base):
    """Centro de custo do RH x CC da matriz/CCO."""

    def test_espaco_sobrando_no_cc(self):
        # RH com CC '100 ' (espaco) deve casar com a matriz CC '100'
        r = self._validar(self._rh(cc="100 "), [self._pe("P1", cc="100")], [self._ac("P1")])
        self.assertEqual(self._status(r), ["OK"])

    def test_cc_identico_casa(self):
        r = self._validar(self._rh(cc="01.04.02"), [self._pe("P1", cc="01.04.02")],
                          [self._ac("P1")])
        self.assertEqual(self._status(r), ["OK"])


class TestCcoGestorNormalizacao(_Base):
    """CCO casa por (centro de custo + GESTOR). Gestor com variacao de caixa/
    acento/espaco deve continuar batendo."""

    def _cco(self, gestor, cc="200", perfil="P_CCO", sistema=SYS):
        return dict(cc=cc, cc_nome="X", gestor=gestor, funcao="F", sistema=sistema, perfil=perfil)

    def test_gestor_caixa(self):
        # cargo 'GERENTE' sem matriz -> perfil so vem da CCO
        r = self._validar(self._rh(cc="200", cargo="GERENTE", gestor="João Silva"),
                          perfis=(), acessos=[self._ac("P_CCO")],
                          cco=[self._cco("JOAO SILVA")])
        self.assertEqual(self._status(r), ["OK"])

    def test_gestor_acento_e_espaco(self):
        r = self._validar(self._rh(cc="200", cargo="GERENTE", gestor="  MARIA JOSÉ  "),
                          perfis=(), acessos=[self._ac("P_CCO")],
                          cco=[self._cco("MARIA JOSE")])
        self.assertEqual(self._status(r), ["OK"])

    def test_gestor_diferente_nao_casa(self):
        # gestor diferente -> a CCO daquele cc/gestor nao se aplica
        r = self._validar(self._rh(cc="200", cargo="GERENTE", gestor="OUTRO GESTOR"),
                          perfis=(), acessos=[self._ac("P_CCO")],
                          cco=[self._cco("JOAO SILVA")])
        # sem perfil esperado para ele -> NAO deve virar OK por engano
        self.assertNotIn("OK", self._status(r))


if __name__ == "__main__":
    unittest.main(verbosity=2)
