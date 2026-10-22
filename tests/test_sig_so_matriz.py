# -*- coding: utf-8 -*-
"""SIG SO' PELA MATRIZ (Bruna, Aplicacao_21_10 e conversa de 22/10/2026).

"O SIG nao tem matriz a nao ser que seja CCO: para consulta e pendencia vamos
olhar somente o que tiver mapeado na matriz. Para transferidos e desligados
olhamos o todo: bloqueada + so' com COM_INFORMATIVOS = a pessoa nao tem acesso;
bloqueada + com perfis diferentes de informativos = a pessoa esta 'ativa' (pode
ter sido um bloqueio de senha) — esses casos devem sempre trazer."

Pendencias de SIG ficam assim:
  - CCO, funcao preve SIG       -> segue a validacao de sempre;
  - CCO, funcao NAO preve SIG   -> conta ativa = pendencia, exceto OPERA
                                   previsto + so' COM_INFORMATIVOS;
  - qualquer pessoa ATIVA       -> login SHOP (ativo, ou bloqueado com perfis)
                                   e duplicidade (dois logins vivos);
  - o resto                     -> o SIG nao aparece (sai o espelho).
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from aplicacao.casos_de_uso.revalidar_transferidos import RevalidarTransferidos
from aplicacao.casos_de_uso.validar_acessos_sistema import ValidarAcessosSistema
from dominio.entidades.funcionario_ativo import FuncionarioAtivo
from dominio.entidades.funcionario_desligado import FuncionarioDesligado
from dominio.entidades.perfil_acesso import PerfilAcesso
from dominio.entidades.transferido import Transferido
from dominio.objetos_valor.cargo import Cargo
from dominio.objetos_valor.sistema import Sistema
from dominio.regras.regra_acesso_desligado import RegraAcessoDesligado
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import (
    AcessoSistema, MatrizCcoModel, RhAtivo, TransferidoModel, ValidacaoAcessoModel)

SIG, INFO = "SIG", "COM_INFORMATIVOS"


def _base():
    tmp = tempfile.mkdtemp(prefix="cvc_sig_matriz_")
    cx = ConexaoBancoDados(os.path.join(tmp, "d.db"))
    cx.inicializar()
    s = cx.sessao()

    def pessoa(mat, cc, gestor, cpf=None):
        s.add(RhAtivo(matricula=mat, nome=f"PESSOA {mat}", cpf=cpf or mat.rjust(11, "7"),
                      cargo_codigo="CG", cargo_descricao="ANALISTA",
                      centro_custo_codigo=cc, gestor=gestor, situacao="ATIVO",
                      tipo_vinculo="FUNCIONARIO"))

    def conta(login, mat, perfil, sit="ATIVO", sis=SIG, nome=None, cpf=""):
        s.add(AcessoSistema(sistema=sis, usuario=login, perfil=perfil, situacao=sit,
                            matricula_vinculada=mat, nome_usuario=nome or f"PESSOA {mat}",
                            cpf=cpf))

    # nao-CCO: espelho do SIG (A, B, Z com P1) — com a regra, nao aparece
    for m in ("A", "B", "Z"):
        pessoa(m, "100", "G1")
        conta("u" + m, m, "P1")
    # CCO, equipe 300/G3: F1 = Systur S1 + Opera O1 ; F2 = Systur S2 + SIG P9
    for f, sis, p in (("F1", "Systur", "S1"), ("F1", "Opera Operacional", "O1"),
                      ("F2", "Systur", "S2"), ("F2", "SIG", "P9")):
        s.add(MatrizCcoModel(cc="300", gestor="G3", funcao=f, sistema=sis, perfil=p))
    pessoa("C1", "300", "G3")                       # F1, SIG so' COM_INFORMATIVOS
    conta("c1sys", "C1", "S1", sis="SYSTUR")
    conta("c1", "C1", INFO)
    pessoa("C2", "300", "G3")                       # F1, SIG com perfil a mais
    conta("c2sys", "C2", "S2X", sis="SYSTUR")
    conta("c2sys", "C2", "S1", sis="SYSTUR")
    conta("c2", "C2", INFO)
    conta("c2", "C2", "PX")
    # CCO, equipe 400/G4: F3 = so' Systur S3 (sem SIG e sem OPERA)
    s.add(MatrizCcoModel(cc="400", gestor="G4", funcao="F3", sistema="Systur", perfil="S3"))
    pessoa("C3", "400", "G4")
    conta("c3sys", "C3", "S3", sis="SYSTUR")
    conta("c3", "C3", "PX")
    # SHOP (pessoa S, nao CCO)
    pessoa("S", "100", "G1")
    conta("sshop", "S", "PX", sit="BLOQUEADO")      # bloqueado com perfil -> vem
    conta("s2shop", "S", INFO, sit="BLOQUEADO")     # bloqueado so' info -> nao
    conta("s3shop", "S", INFO)                      # ativo -> sempre vem
    conta("xshop", "FORA", "PX", sit="BLOQUEADO")   # pessoa nao ativa -> nao
    # DUPLICIDADE (pessoa D): mesmo CPF em dois logins vivos
    pessoa("D", "100", "G1", cpf="12345678901")
    conta("dd", "D", "P1", cpf="12345678901")
    conta("dd2", "D", "PX", sit="BLOQUEADO", cpf="12345678901")
    conta("dd3", "D", INFO, sit="BLOQUEADO", cpf="12345678901")   # nao conta
    s.commit(); s.close()
    return cx


def _sig(cx, mat):
    s = cx.sessao()
    r = sorted((x.status, x.motivo_status or "", x.perfil_atual or "")
               for x in s.query(ValidacaoAcessoModel).filter_by(matricula=mat).all()
               if x.sistema == SIG)
    s.close()
    return r


class PendenciasDoSig(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cx = _base()
        ValidarAcessosSistema(cls.cx, sig_so_matriz=True).executar()

    def test_fora_da_cco_o_sig_nao_aparece(self):
        """Sai o espelho: A, B e Z tinham o padrao do grupo (Aderente)."""
        for m in ("A", "B", "Z"):
            self.assertEqual(_sig(self.cx, m), [], m)

    def test_cco_opera_previsto_so_informativo_nao_e_pendencia(self):
        """Exemplo 1 do documento."""
        self.assertEqual(_sig(self.cx, "C1"), [])

    def test_cco_opera_previsto_com_outros_perfis_e_pendencia(self):
        """Exemplo 2 do documento."""
        self.assertEqual(_sig(self.cx, "C2"),
                         [("EM_ANALISE", "SIG_NAO_PREVISTO_OPERA_PREVISTO", f"{INFO}, PX")])

    def test_cco_sem_sig_e_sem_opera_com_perfis_e_pendencia(self):
        """Confirmado pela Bruna em 22/10 ("Certo")."""
        self.assertEqual(_sig(self.cx, "C3"),
                         [("EM_ANALISE", "SIG_NAO_PREVISTO_NA_FUNCAO", "PX")])

    def test_login_shop(self):
        motivos = [m for _, m, _ in _sig(self.cx, "S")]
        self.assertIn("SIG_LOGIN_SHOP:sshop", motivos, "bloqueado com perfil vem")
        self.assertIn("SIG_LOGIN_SHOP:s3shop", motivos, "SHOP ativo esta' errado: sempre vem")
        self.assertNotIn("SIG_LOGIN_SHOP:s2shop", motivos, "bloqueado so' com informativo nao")

    def test_shop_de_pessoa_nao_ativa_nao_vem(self):
        self.assertEqual(_sig(self.cx, "FORA"), [])

    def test_duplicidade_de_logins_vivos(self):
        dup = [x for x in _sig(self.cx, "D") if x[1].startswith("SIG_DUPLICIDADE:")]
        self.assertEqual(len(dup), 1)
        self.assertEqual(dup[0][1], "SIG_DUPLICIDADE:dd,dd2",
                         "o login bloqueado so' com COM_INFORMATIVOS nao conta")
        self.assertIn("dd2 (bloqueado, 1 perfis)", dup[0][2])

    def test_com_a_chave_desligada_o_espelho_volta(self):
        """Nao-regressao: sem <sig><so_matriz> tudo fica como antes."""
        cx = _base()
        ValidarAcessosSistema(cx).executar()
        self.assertEqual(_sig(cx, "Z"), [("OK", "", "P1")])
        self.assertFalse(any(m.startswith("SIG_") for _, m, _ in _sig(cx, "S")))


def _cargo(dep="TI", cc="100", cod="CG"):
    return Cargo(codigo=cod, descricao="ANALISTA", departamento=dep, centro_custo=cc)


class DepartamentoNaoContaMais(unittest.TestCase):
    """Aplicacao_21_10: "Nao trazer alteracoes de departamento. Considerar
    apenas CENTRO de CUSTO, CARGO e GESTOR"."""

    def _t(self, cargo_ant, gestor_ant="G"):
        f = FuncionarioAtivo(matricula="1", nome="X", cpf="", cargo=_cargo(),
                             situacao="ATIVO", gestor="G")
        return Transferido(funcionario=f, cargo_anterior=cargo_ant,
                           data_transferencia=date(2026, 10, 1), gestor_anterior=gestor_ant)

    def test_so_departamento_nao_e_transferencia(self):
        t = self._t(_cargo(dep="FINANCEIRO"))
        self.assertFalse(t.precisa_revisao_acessos)
        self.assertEqual(t.campos_mudados, "")

    def test_departamento_sai_do_rotulo(self):
        t = self._t(_cargo(dep="FINANCEIRO", cc="200"), gestor_ant="OUTRO")
        self.assertTrue(t.precisa_revisao_acessos)
        self.assertEqual(t.campos_mudados, "centro de custo, gestor")


def _acesso(usuario, perfil, situacao, mat="D1"):
    return PerfilAcesso(sistema=Sistema.SIG, usuario=usuario, perfil=perfil,
                        nome_usuario="FULANO", cpf="", situacao=situacao,
                        matricula_vinculada=mat)


class DesligadoComSigBloqueado(unittest.TestCase):

    def setUp(self):
        self.deslig = [FuncionarioDesligado(matricula="D1", nome="FULANO", cpf="",
                                            cargo=_cargo(), data_desligamento=date(2018, 1, 1))]
        self.acessos = [_acesso("vivo", INFO, "BLOQUEADO"), _acesso("vivo", "PX", "BLOQUEADO"),
                        _acesso("morto", INFO, "BLOQUEADO")]

    def test_bloqueado_com_perfis_entra_em_desligados(self):
        div = RegraAcessoDesligado(sig_bloqueada_com_perfis_viva=True).verificar(
            self.acessos, self.deslig, [])
        self.assertEqual([(d.usuario, d.perfil_encontrado) for d in div], [("vivo", "PX")],
                         "so' o perfil alem do COM_INFORMATIVOS; o login 'morto' nao entra")

    def test_sem_a_regra_bloqueado_nao_e_acesso(self):
        self.assertEqual(RegraAcessoDesligado().verificar(self.acessos, self.deslig, []), [])


class TransferidoOlhaOSigTodo(unittest.TestCase):

    def test_sig_bloqueado_com_perfis_entra_e_informativo_nao(self):
        tmp = tempfile.mkdtemp(prefix="cvc_sig_transf_")
        caminho = os.path.join(tmp, "t.db")
        con = ConexaoBancoDados(caminho)
        con.inicializar()
        s = con.sessao()
        s.add(RhAtivo(matricula="T", nome="T", cpf="", cargo_codigo="CG",
                      cargo_descricao="ANALISTA", centro_custo_codigo="100",
                      situacao="ATIVO", tipo_vinculo="FUNCIONARIO", gestor="B"))
        for login, perfil, sit in (("t1", "PX", "BLOQUEADO"), ("t1", INFO, "BLOQUEADO"),
                                   ("t2", INFO, "BLOQUEADO")):
            s.add(AcessoSistema(sistema=SIG, usuario=login, perfil=perfil, situacao=sit,
                                matricula_vinculada="T", nome_usuario="T"))
        s.add(TransferidoModel(matricula="T", nome="T", campos_mudados="gestor",
                               data_transferencia="2026-10-01", cargo_codigo_anterior="CG",
                               cargo_anterior="ANALISTA", centro_custo_anterior="100",
                               gestor_anterior="A", cargo_codigo_atual="CG",
                               cargo_atual="ANALISTA", centro_custo_atual="100",
                               gestor_atual="B"))
        s.commit(); s.close()
        RevalidarTransferidos(con, sig_so_matriz=True).executar()
        c = sqlite3.connect(caminho)
        linhas = c.execute("SELECT sistema, perfil, situacao FROM revalidacao_transferido").fetchall()
        c.close()
        self.assertEqual(linhas, [("SIG", "PX", "EXCESSO")],
                         "sem esperado nos dois momentos o SIG aparece mesmo assim")


if __name__ == "__main__":
    unittest.main()
