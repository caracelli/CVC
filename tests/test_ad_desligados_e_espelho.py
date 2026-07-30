# -*- coding: utf-8 -*-
"""Decisoes da usuaria em 29/07/2026:

  B2 = SIM -> o OU_Desligados do diretorio AD alimenta o motor de desligados.
  Como o export do AD nao tem matricula de RH, a chave e' o LOGIN: a regra de
  acesso de desligado passou a casar por matricula OU cpf OU login.

  Franqueado/Prestador = validados por ESPELHO (como os terceiros), agora com
  chave (Empresa + Gestor) -> fallback (Gestor), em TODOS os sistemas.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from aplicacao.casos_de_uso.validar_acessos_sistema import ValidarAcessosSistema
from dominio.entidades.funcionario_desligado import FuncionarioDesligado
from dominio.entidades.perfil_acesso import PerfilAcesso
from dominio.objetos_valor.cargo import Cargo
from dominio.objetos_valor.sistema import Sistema
from dominio.regras.regra_acesso_desligado import RegraAcessoDesligado
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import (
    AcessoSistema, RhAtivo, ValidacaoAcessoModel)
from infraestrutura.leitores_arquivos.leitor_diretorio_ad import LeitorDiretorioAd

SYS = "SYSTUR"
CAB = ("Nome;Email;Login;CPF;Escritorio;Cargo;Departamento;Empresa;"
       "Status;Manager;Criacao")


def _csv_ad(linhas):
    tmp = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False,
                                      encoding="cp1252", newline="")
    tmp.write(CAB + "\n")
    for l in linhas:
        tmp.write(";".join(l) + "\n")
    tmp.close()
    return Path(tmp.name)


def _acesso(usuario, perfil="P1", cpf="", situacao="ATIVO", matricula=None):
    return PerfilAcesso(usuario=usuario, nome_usuario=usuario.upper(),
                        sistema=Sistema.SYSTUR, perfil=perfil, situacao=situacao,
                        cpf=cpf, matricula_vinculada=matricula)


class TestAdDesligadosViramDesligados(unittest.TestCase):

    def test_leitor_gera_desligado_com_login_e_matricula_namespaced(self):
        arq = _csv_ad([["ANA SOUZA", "ana@x.com", "corpp001", "11122233344",
                        "SP", "AGENTE", "VENDAS", "ACME", "DESLIGADO", "CHEFE", ""]])
        saiu = LeitorDiretorioAd().ler_desligados(arq)
        self.assertEqual(len(saiu), 1)
        d = saiu[0]
        self.assertIsInstance(d, FuncionarioDesligado)
        self.assertEqual(d.login, "corpp001")
        self.assertTrue(d.matricula.startswith("ADESL-"),
                        f"matricula deve ser namespaced, veio {d.matricula}")

    def test_dedup_por_login(self):
        arq = _csv_ad([
            ["ANA", "a@x", "corpp001", "111", "SP", "C", "D", "E", "X", "M", ""],
            ["ANA", "a@x", "CORPP001", "111", "SP", "C", "D", "E", "X", "M", ""],
        ])
        self.assertEqual(len(LeitorDiretorioAd().ler_desligados(arq)), 1)


class TestRegraDesligadoPorLogin(unittest.TestCase):

    def _desligado(self, matricula="ADESL-corpp001", cpf="", login="corpp001"):
        return FuncionarioDesligado(matricula=matricula, nome="ANA", cpf=cpf,
                                    cargo=Cargo("", "", "", ""), login=login)

    def test_casa_por_login_quando_nao_ha_matricula_nem_cpf(self):
        divs = RegraAcessoDesligado().verificar(
            [_acesso("corpp001")], [self._desligado()])
        self.assertEqual(len(divs), 1)
        self.assertEqual(divs[0].matricula, "ADESL-corpp001")

    def test_login_ignora_caixa(self):
        divs = RegraAcessoDesligado().verificar(
            [_acesso("CORPP001")], [self._desligado()])
        self.assertEqual(len(divs), 1)

    def test_conta_bloqueada_do_desligado_nao_e_divergencia(self):
        divs = RegraAcessoDesligado().verificar(
            [_acesso("corpp001", situacao="BLOQUEADO")], [self._desligado()])
        self.assertEqual(divs, [])

    def test_login_de_ativo_nao_gera_divergencia(self):
        divs = RegraAcessoDesligado().verificar(
            [_acesso("outro_login")], [self._desligado()])
        self.assertEqual(divs, [])

    def test_uma_divergencia_quando_bate_por_varias_chaves(self):
        # mesma pessoa: casa por matricula, cpf E login -> 1 divergencia so
        d = self._desligado(matricula="M9", cpf="11122233344", login="corpp001")
        divs = RegraAcessoDesligado().verificar(
            [_acesso("corpp001", cpf="11122233344", matricula="M9")], [d])
        self.assertEqual(len(divs), 1)


class TestEspelhoFranqueadoPrestador(unittest.TestCase):
    """Franqueado/prestador nao tem cargo na matriz: espelham com os pares da
    MESMA populacao por (Empresa + Gestor)."""

    def _cx(self, vinculo):
        tmp = tempfile.mkdtemp(prefix="cvc_esp_")
        cx = ConexaoBancoDados(os.path.join(tmp, "d.db"))
        cx.inicializar()
        s = cx.sessao()
        # 3 pares da mesma empresa/gestor com o MESMO perfil = padrao do grupo
        for i in (1, 2, 3):
            s.add(RhAtivo(matricula=f"{vinculo[:4]}-{i}", nome=f"P{i}",
                          cpf=f"1112223334{i}", situacao="ATIVO",
                          tipo_vinculo=vinculo, empresa="ACME", gestor="CHEFE",
                          departamento="OPS", centro_custo_codigo=""))
            s.add(AcessoSistema(sistema=SYS, usuario=f"u{i}", perfil="P_PADRAO",
                                matricula_vinculada=f"{vinculo[:4]}-{i}",
                                situacao="ATIVO"))
        s.commit(); s.close()
        return cx

    def _status(self, cx, matricula):
        s = cx.sessao()
        rows = [(r.status, r.origem_matriz) for r in
                s.query(ValidacaoAcessoModel).filter_by(matricula=matricula).all()]
        s.close()
        return rows

    def _add(self, cx, vinculo, matricula, perfil=None):
        s = cx.sessao()
        s.add(RhAtivo(matricula=matricula, nome="NOVO", cpf="99988877766",
                      situacao="ATIVO", tipo_vinculo=vinculo, empresa="ACME",
                      gestor="CHEFE", departamento="OPS", centro_custo_codigo=""))
        if perfil:
            s.add(AcessoSistema(sistema=SYS, usuario="unovo", perfil=perfil,
                                matricula_vinculada=matricula, situacao="ATIVO"))
        s.commit(); s.close()

    def test_franqueado_sem_o_padrao_vira_inclusao(self):
        cx = self._cx("FRANQUEADO")
        self._add(cx, "FRANQUEADO", "FRANQ-9")          # sem nenhum acesso
        ValidarAcessosSistema(cx).executar()
        st = self._status(cx, "FRANQ-9")
        self.assertEqual([s for s, _ in st], ["SEM_ACESSO"])
        self.assertEqual(st[0][1], "ESPELHO_FRANQUEADO")

    def test_franqueado_com_o_padrao_e_aderente(self):
        cx = self._cx("FRANQUEADO")
        self._add(cx, "FRANQUEADO", "FRANQ-9", perfil="P_PADRAO")
        ValidarAcessosSistema(cx).executar()
        self.assertEqual([s for s, _ in self._status(cx, "FRANQ-9")], ["OK"])

    def test_prestador_com_perfil_a_mais_vai_para_analise(self):
        cx = self._cx("PRESTADOR")
        self._add(cx, "PRESTADOR", "PREST-9", perfil="P_EXTRA")
        ValidarAcessosSistema(cx).executar()
        st = self._status(cx, "PREST-9")
        self.assertEqual([s for s, _ in st], ["EM_ANALISE"])
        self.assertEqual(st[0][1], "ESPELHO_PRESTADOR")

    def test_nao_espelha_entre_populacoes_diferentes(self):
        # prestador sozinho no grupo de franqueados: sem par -> nao vira Inclusao
        cx = self._cx("FRANQUEADO")
        self._add(cx, "PRESTADOR", "PREST-1")
        ValidarAcessosSistema(cx).executar()
        self.assertEqual(self._status(cx, "PREST-1"), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
