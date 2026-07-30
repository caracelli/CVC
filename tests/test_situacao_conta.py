# -*- coding: utf-8 -*-
"""Status da conta: semantica unica + efeito nas regras (decisao da area 22/07,
significado do A/P/D/I do IC provado nos dados em 29/07/2026).

  - BLOQUEADO/INATIVO = conta ja revogada -> NAO e' acesso em nenhuma regra
    (antes a validacao de perfil ignorava o status e tratava como acesso vivo);
  - vazio ou 'P' (pendente) = INDEFINIDO -> nao se assume ativo: o resultado
    daquele (matricula, sistema) vira "Em Analise";
  - 'D' = desligado, mas a conta continua VIVA (o motor de desligados a pega);
  - orfao ("Sem Vinculo RH") so conta se a conta estiver ativa, e agora carrega
    os perfis do login (antes o painel mostrava "—").
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dominio.entidades.perfil_acesso import PerfilAcesso
from dominio.objetos_valor import situacao_conta as sit
from dominio.objetos_valor.sistema import Sistema
from dominio.regras.regra_acesso_sem_vinculo import RegraAcessoSemVinculo
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import (
    RhAtivo, PerfilEsperadoModel, AcessoSistema, ValidacaoAcessoModel)
from infraestrutura.leitores_arquivos.configs_sistemas import CONFIGS_SISTEMAS
from aplicacao.casos_de_uso.validar_acessos_sistema import ValidarAcessosSistema

SYS = "SYSTUR"


class TestSemanticaStatus(unittest.TestCase):

    def test_sem_acesso_efetivo(self):
        for v in ("BLOQUEADO", "bloqueado", " INATIVO ", "I", "B", "SUSPENSO"):
            self.assertTrue(sit.sem_acesso_efetivo(v), v)
            self.assertFalse(sit.conta_ativa(v), v)

    def test_ativa(self):
        for v in ("ATIVO", "ativo", "A", "ACTIVE"):
            self.assertTrue(sit.conta_ativa(v))
            self.assertFalse(sit.indefinida(v))

    def test_desligada_continua_sendo_acesso(self):
        # 'D' do IC: pessoa saiu mas a conta existe -> e' acesso (vai pro motor
        # de desligados), e NAO e' indefinido
        for v in ("D", "DESLIGADO"):
            self.assertTrue(sit.conta_ativa(v))
            self.assertFalse(sit.indefinida(v))

    def test_indefinida(self):
        for v in ("", None, "P", "PENDENTE", "XPTO"):
            self.assertTrue(sit.indefinida(v), repr(v))
            self.assertTrue(sit.conta_ativa(v), repr(v))   # existe como acesso


class TestLeitorICLeStatus(unittest.TestCase):

    def test_config_ic_aceita_os_dois_nomes_de_coluna(self):
        cfg = CONFIGS_SISTEMAS[Sistema.IC_INTEGRADOR_CONTABIL]
        col = cfg.colunas["situacao"]
        self.assertIn("S", col, "layout de largura fixa usa a coluna 'S'")
        self.assertIn("ST_HABILITACAO", col, "XLSX antigo usa ST_HABILITACAO")

    def test_mapa_de_situacao_do_ic(self):
        cfg = CONFIGS_SISTEMAS[Sistema.IC_INTEGRADOR_CONTABIL]
        self.assertEqual(cfg.mapa_situacao["A"], "ATIVO")
        self.assertEqual(cfg.mapa_situacao["D"], "DESLIGADO")
        self.assertEqual(cfg.mapa_situacao["P"], "PENDENTE")
        self.assertEqual(cfg.mapa_situacao["I"], "INATIVO")

    def test_valor_usa_o_alias_presente(self):
        import pandas as pd
        from infraestrutura.leitores_arquivos.leitor_sistema import LeitorSistema
        leitor = LeitorSistema(CONFIGS_SISTEMAS[Sistema.IC_INTEGRADOR_CONTABIL])
        # layout novo (largura fixa): so tem 'S'
        linha = pd.Series({"CD_LOGIN": "u1", "S": "D"})
        self.assertEqual(leitor._normalizar_situacao(leitor._valor(linha, "situacao")),
                         "DESLIGADO")
        # layout antigo: so tem 'ST_HABILITACAO'
        linha = pd.Series({"CD_LOGIN": "u1", "ST_HABILITACAO": "A"})
        self.assertEqual(leitor._normalizar_situacao(leitor._valor(linha, "situacao")),
                         "ATIVO")


class TestValidacaoHonraStatus(unittest.TestCase):

    def _run(self, situacao_do_acesso):
        tmp = tempfile.mkdtemp(prefix="cvc_stat_")
        cx = ConexaoBancoDados(os.path.join(tmp, "d.db"))
        cx.inicializar()
        s = cx.sessao()
        s.add(RhAtivo(matricula="M1", nome="ANA", cpf="11111111111", cargo_codigo="CG",
                      cargo_descricao="ANALISTA", centro_custo_codigo="100", situacao="ATIVO"))
        s.add(PerfilEsperadoModel(cargo_codigo="100", cargo_descricao="ANALISTA",
                                  sistema=SYS, perfil="P1"))
        # colega com acesso ativo: mantem a adesao do cargo alta (regra B1)
        s.add(RhAtivo(matricula="M2", nome="BIA", cpf="22222222222", cargo_codigo="CG",
                      cargo_descricao="ANALISTA", centro_custo_codigo="100", situacao="ATIVO"))
        s.add(AcessoSistema(sistema=SYS, usuario="u2", perfil="P1",
                            matricula_vinculada="M2", situacao="ATIVO"))
        s.add(AcessoSistema(sistema=SYS, usuario="u1", perfil="P1",
                            matricula_vinculada="M1", situacao=situacao_do_acesso))
        s.commit(); s.close()
        ValidarAcessosSistema(cx).executar()
        s = cx.sessao()
        rows = [r.status for r in s.query(ValidacaoAcessoModel).filter_by(matricula="M1").all()]
        s.close()
        return rows

    def test_conta_ativa_e_aderente(self):
        self.assertEqual(self._run("ATIVO"), ["OK"])

    def test_conta_bloqueada_nao_conta_como_acesso(self):
        # a conta esta revogada -> a pessoa esta SEM o acesso que o cargo preve
        self.assertEqual(self._run("BLOQUEADO"), ["SEM_ACESSO"])

    def test_status_vazio_vira_em_analise(self):
        # nao se assume ativo (regra da area): revisao humana
        self.assertEqual(self._run(""), ["EM_ANALISE"])

    def test_status_pendente_vira_em_analise(self):
        self.assertEqual(self._run("PENDENTE"), ["EM_ANALISE"])

    def test_conta_de_desligado_continua_valendo_como_acesso(self):
        self.assertEqual(self._run("DESLIGADO"), ["OK"])


class TestOrfaoCarregaPerfis(unittest.TestCase):

    def _acesso(self, perfil, situacao="ATIVO", usuario="jsilva"):
        return PerfilAcesso(usuario=usuario, nome_usuario="J SILVA",
                            sistema=Sistema.SYSTUR, perfil=perfil,
                            situacao=situacao, cpf="99999999999",
                            matricula_vinculada=None)

    def test_um_achado_por_login_com_todos_os_perfis(self):
        divs = RegraAcessoSemVinculo().verificar(
            [self._acesso("P_B"), self._acesso("P_A"), self._acesso("P_A")])
        self.assertEqual(len(divs), 1, "1 achado por login/sistema")
        self.assertEqual(divs[0].perfil_encontrado, "P_A, P_B")

    def test_conta_bloqueada_nao_vira_orfao(self):
        divs = RegraAcessoSemVinculo().verificar(
            [self._acesso("P_A", situacao="BLOQUEADO")])
        self.assertEqual(divs, [])

    def test_logins_distintos_geram_achados_distintos(self):
        divs = RegraAcessoSemVinculo().verificar(
            [self._acesso("P_A", usuario="jsilva"),
             self._acesso("P_Z", usuario="msouza")])
        self.assertEqual(len(divs), 2)
        self.assertEqual({d.perfil_encontrado for d in divs}, {"P_A", "P_Z"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
