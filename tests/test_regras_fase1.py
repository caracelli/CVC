# -*- coding: utf-8 -*-
"""Suite de testes das regras da Fase 1 — inclusao/alteracao de acesso (SYSTUR).

Cobre: padronizacao, CDC do RH, regras de divergencia e a logica de status
da validacao de acessos (0 / 1 / 2+ perfis).

Roda sem dependencias extras:  python -m unittest discover -s tests
"""
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dominio.objetos_valor.cargo import Cargo
from dominio.objetos_valor.sistema import Sistema
from dominio.objetos_valor.tipo_divergencia import TipoDivergencia
from dominio.entidades.funcionario_ativo import FuncionarioAtivo
from dominio.entidades.perfil_acesso import PerfilAcesso
from dominio.entidades.perfil_esperado import PerfilEsperado
from dominio.servicos_dominio.servico_padronizacao import ServicoPadronizacao
from dominio.regras.regra_acesso_sem_vinculo import RegraAcessoSemVinculo
from dominio.regras.regra_perfil_invalido import RegraPerfilInvalido
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.repositorios.repositorio_funcionario_sqlite import RepositorioFuncionarioSqlite
from aplicacao.casos_de_uso.registrar_historico_rh import RegistrarHistoricoRh
from aplicacao.casos_de_uso.validar_acessos_sistema import ValidarAcessosSistema


def _cargo(cc="100", desc="ANALISTA"):
    return Cargo(codigo="CG1", descricao=desc, departamento="TI", centro_custo=cc)


def _ativo(matricula, cpf, cc="100", cargo="ANALISTA", nome="FULANO DE TAL"):
    return FuncionarioAtivo(
        matricula=matricula, nome=nome, cpf=cpf, cargo=_cargo(cc, cargo),
        email=None, data_admissao=date(2020, 1, 1), situacao="ATIVO",
    )


# ───────────────────────── Padronizacao ─────────────────────────
class TestServicoPadronizacao(unittest.TestCase):

    def setUp(self):
        self.p = ServicoPadronizacao()

    def test_cpf_remove_mascara_e_completa_11_digitos(self):
        self.assertEqual(self.p.normalizar_cpf("123.456.789-00"), "12345678900")
        self.assertEqual(self.p.normalizar_cpf("42949637"), "00042949637")
        self.assertEqual(self.p.normalizar_cpf(""), "")
        self.assertEqual(self.p.normalizar_cpf(None), "")

    def test_nome_maiusculo_sem_espacos_extras(self):
        self.assertEqual(self.p.normalizar_nome("  joão   silva  "), "JOÃO SILVA")

    def test_matricula_remove_zeros_a_esquerda(self):
        self.assertEqual(self.p.normalizar_matricula("00123"), "123")
        self.assertEqual(self.p.normalizar_matricula(" 45 "), "45")
        self.assertEqual(self.p.normalizar_matricula("0"), "0")
        self.assertEqual(self.p.normalizar_matricula("000"), "0")

    def test_situacao_mapeia_para_padrao(self):
        self.assertEqual(self.p.normalizar_situacao("A"), "ATIVO")
        self.assertEqual(self.p.normalizar_situacao("Atividade Normal"), "ATIVO")
        self.assertEqual(self.p.normalizar_situacao("RESCISÃO"), "DESLIGADO")
        self.assertEqual(self.p.normalizar_situacao("qualquer"), "QUALQUER")


# ──────────────────── Regra: acesso sem vinculo RH ────────────────────
class TestRegraAcessoSemVinculo(unittest.TestCase):

    def setUp(self):
        self.regra = RegraAcessoSemVinculo()

    def _acesso(self, cpf, matricula_vinc):
        return PerfilAcesso(
            usuario="login1", nome_usuario="FULANO", sistema=Sistema.SYSTUR,
            perfil="P1", situacao="ATIVO", cpf=cpf, matricula_vinculada=matricula_vinc,
        )

    def test_com_cpf_sem_vinculo_gera_divergencia(self):
        divs = self.regra.verificar([self._acesso("12345678900", None)])
        self.assertEqual(len(divs), 1)
        self.assertEqual(divs[0].tipo, TipoDivergencia.ACESSO_SEM_VINCULO_RH)

    def test_com_cpf_e_vinculo_nao_gera(self):
        self.assertEqual(self.regra.verificar([self._acesso("12345678900", "777")]), [])

    def test_sem_cpf_nao_gera(self):
        self.assertEqual(self.regra.verificar([self._acesso("", None)]), [])


# ──────────────────── Regra: perfil invalido ────────────────────
class TestRegraPerfilInvalido(unittest.TestCase):

    def _acesso(self, perfil, matricula_vinc="500"):
        return PerfilAcesso(
            usuario="login1", nome_usuario="FULANO", sistema=Sistema.SYSTUR,
            perfil=perfil, situacao="ATIVO", cpf="12345678900",
            matricula_vinculada=matricula_vinc,
        )

    def _perfil_esperado(self, perfil):
        # cargo_codigo guarda o centro de custo (mesma chave do RhAtivo)
        return PerfilEsperado(
            cargo_codigo="100", sistema=Sistema.SYSTUR, perfil=perfil,
            cargo_descricao="ANALISTA",
        )

    def test_perfil_fora_do_esperado_gera_divergencia(self):
        regra = RegraPerfilInvalido([self._perfil_esperado("PERFIL_OK")])
        divs = regra.verificar([self._acesso("PERFIL_ERRADO")], [_ativo("500", "12345678900")])
        self.assertEqual(len(divs), 1)
        self.assertEqual(divs[0].tipo, TipoDivergencia.PERFIL_INVALIDO)

    def test_perfil_dentro_do_esperado_nao_gera(self):
        regra = RegraPerfilInvalido([self._perfil_esperado("PERFIL_OK")])
        divs = regra.verificar([self._acesso("PERFIL_OK")], [_ativo("500", "12345678900")])
        self.assertEqual(divs, [])

    def test_acesso_sem_vinculo_nao_gera(self):
        regra = RegraPerfilInvalido([self._perfil_esperado("PERFIL_OK")])
        divs = regra.verificar([self._acesso("X", matricula_vinc=None)], [_ativo("500", "12345678900")])
        self.assertEqual(divs, [])


# ──────────── Logica de status da validacao (0 / 1 / 2+ perfis) ────────────
class TestValidacaoStatus(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="cvc_test_")
        conexao = ConexaoBancoDados(os.path.join(cls._tmp, "t.db"))
        conexao.inicializar()
        cls.uc = ValidarAcessosSistema(conexao)

    def _func(self):
        return SimpleNamespace(
            matricula="500", cpf="12345678900", nome="FULANO", email="",
            centro_custo_codigo="100", centro_custo_nome="TI",
            cargo_codigo="CG1", cargo_descricao="ANALISTA",
        )

    def _gerar(self, perfis, acessos_atuais, sistemas_com_dados=("SYSTUR",)):
        acessos = {"500": [("SYSTUR", p) for p in acessos_atuais]}
        return self.uc._gerar_registros_sistema(
            self._func(), "SYSTUR", perfis, acessos, set(sistemas_com_dados), "MATRIZ",
        )

    def test_um_perfil_sem_acesso(self):
        regs = self._gerar([("P1", False)], acessos_atuais=[])
        self.assertEqual(len(regs), 1)
        self.assertEqual(regs[0]["status"], "SEM_ACESSO")

    def test_um_perfil_aderente(self):
        regs = self._gerar([("P1", False)], acessos_atuais=["P1"])
        self.assertEqual(regs[0]["status"], "ADERENTE")

    def test_um_perfil_divergente(self):
        regs = self._gerar([("P1", False)], acessos_atuais=["P2"])
        self.assertEqual(regs[0]["status"], "DIVERGENTE")
        self.assertEqual(regs[0]["perfil_atual"], "P2")

    def test_sistema_sem_dados(self):
        regs = self._gerar([("P1", False)], acessos_atuais=[], sistemas_com_dados=())
        self.assertEqual(regs[0]["status"], "SEM_DADOS")

    def test_dois_perfis_em_analise_uma_linha_por_perfil(self):
        regs = self._gerar([("P1", False), ("P2", False)], acessos_atuais=[])
        self.assertEqual(len(regs), 2)
        self.assertTrue(all(r["status"] == "EM_ANALISE" for r in regs))


# ──────────────────── CDC do RH (NOVO / ALTERADO / REMOVIDO) ────────────────────
class TestCDCHistoricoRh(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_cdc_")
        self.conexao = ConexaoBancoDados(os.path.join(self._tmp, "cdc.db"))
        self.conexao.inicializar()
        self.repo = RepositorioFuncionarioSqlite(self.conexao)
        self.hist = RegistrarHistoricoRh(self.conexao)

    def test_novo_quando_matricula_inexistente(self):
        # banco vazio; CDC compara contra nada -> tudo NOVO
        r = self.hist.registrar_ativos([_ativo("100", "11111111111")])
        self.assertEqual(r["novos"], 1)
        self.assertEqual(r["alterados"], 0)
        self.assertEqual(r["removidos"], 0)

    def test_sem_mudanca_quando_registro_identico(self):
        f = _ativo("100", "11111111111")
        self.repo.salvar_ativos([f])               # estado anterior
        r = self.hist.registrar_ativos([f])         # mesma carga
        self.assertEqual((r["novos"], r["alterados"], r["removidos"]), (0, 0, 0))

    def test_alterado_quando_campo_muda(self):
        self.repo.salvar_ativos([_ativo("100", "11111111111", cargo="ANALISTA")])
        r = self.hist.registrar_ativos([_ativo("100", "11111111111", cargo="GERENTE")])
        self.assertEqual(r["alterados"], 1)
        self.assertEqual((r["novos"], r["removidos"]), (0, 0))

    def test_removido_quando_matricula_some_do_arquivo(self):
        self.repo.salvar_ativos([_ativo("100", "11111111111"), _ativo("200", "22222222222")])
        r = self.hist.registrar_ativos([_ativo("100", "11111111111")])
        self.assertEqual(r["removidos"], 1)
        self.assertEqual(r["total"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
