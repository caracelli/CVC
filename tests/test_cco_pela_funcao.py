# -*- coding: utf-8 -*-
"""A CCO responde pela FUNCAO da pessoa, nao por todas as do gestor dela.

Retorno da area (documento de 22/09/2026, paginas 3 e 4), textual:

    "CCO esta vindo errado:
     Com base na matriz o usuario nao pode ter acesso ao SIG e os acessos nao
     esta validado tudo exemplo para Funcao a Receber 1 temos:"

O mapeamento CCO casa por (centro de custo, GESTOR) — nao por funcao. Um
gestor tem varias funcoes na equipe, e a pessoa recebia a UNIAO de todas.
Quem diz qual funcao e' a dela e' o perfil que ela tem no SYSTUR: as linhas de
'Systur' da propria CCO traduzem perfil <-> funcao.

CASO DO DOCUMENTO (e' um exemplo, nao o escopo): a matricula 34530984 tem
A_RECEBER_1 no SYSTUR; a funcao "A Receber 1" nao preve SIG; e ela recebia 14
perfis de SIG, vindos da funcao "A Receber 2 + SIG" do mesmo gestor.

MEDIDO na base de 15/09:
  2.929 linhas vinham de OUTRA funcao (SIG 2.244, SIGOT 336, SICA_RA 199,
  SICA_ESFERA 143, SYSTUR 7) contra 806 da funcao certa — 196 pessoas.
  Depois da regra: total de linhas 10.406 -> 7.580, e as pendencias caem de
  1.082 para 897 linhas MANTENDO as mesmas 818 pessoas. Zero pares deixaram
  de ser pendencia; zero viraram.

Quem NAO tem perfil no SYSTUR fica como estava: sem ele nao da' para saber a
funcao, e filtrar tiraria toda a previsao de 1.034 linhas.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import (
    RhAtivo, AcessoSistema, MatrizCcoModel, ValidacaoAcessoModel)
from aplicacao.casos_de_uso.validar_acessos_sistema import ValidarAcessosSistema

CC, GESTOR = "01.06.02.01", "FERNANDA DA SILVA AQUINO"


def _base(perfil_systur, acessos=(), com_systur_na_cco=True):
    """Duas funcoes no MESMO (cc, gestor), como na planilha real:
        "A Receber 1"       -> SICA_RA + SYSTUR, SEM SIG
        "A Receber 2 + SIG" -> SIG
    A pessoa tem A_RECEBER_1 no SYSTUR: nao pode receber o SIG da outra.
    """
    tmp = tempfile.mkdtemp(prefix="cvc_fun_")
    cx = ConexaoBancoDados(os.path.join(tmp, "d.db"))
    cx.inicializar()
    s = cx.sessao()
    s.add(RhAtivo(matricula="M1", nome="PESSOA UM", cpf="00000000001",
                  cargo_codigo="CG", cargo_descricao="ANALISTA FINANCEIRO SR",
                  centro_custo_codigo=CC, gestor=GESTOR, situacao="ATIVO",
                  tipo_vinculo="FUNCIONARIO"))
    # colega so' para os sistemas terem extrato
    s.add(RhAtivo(matricula="M2", nome="OUTRA", cpf="00000000002",
                  cargo_codigo="CG", cargo_descricao="OUTRO",
                  centro_custo_codigo="999", gestor="OUTRO", situacao="ATIVO",
                  tipo_vinculo="FUNCIONARIO"))
    for sis, p in (("SIG", "X"), ("SICA_RA", "Y"), ("SYSTUR", "Z")):
        s.add(AcessoSistema(sistema=sis, usuario="u2", perfil=p,
                            matricula_vinculada="M2", situacao="ATIVO"))

    if perfil_systur:
        s.add(AcessoSistema(sistema="SYSTUR", usuario="u1",
                            perfil=perfil_systur, matricula_vinculada="M1",
                            situacao="ATIVO"))
    for sis, p in acessos:
        s.add(AcessoSistema(sistema=sis, usuario="u1", perfil=p,
                            matricula_vinculada="M1", situacao="ATIVO"))

    def cco(funcao, sistema, perfil):
        s.add(MatrizCcoModel(cc=CC, gestor=GESTOR, funcao=funcao,
                             sistema=sistema, perfil=perfil))

    cco("A Receber 1", "SICA RA", "A Receber 1")
    if com_systur_na_cco:
        cco("A Receber 1", "Systur", "A_RECEBER_1")
    cco("A Receber 2 + SIG", "SIG", "ATD_LAZER")
    cco("A Receber 2 + SIG", "SIG", "FIN_INT")
    cco("A Receber 2 + SIG", "Systur", "A_RECEBER_2")
    s.commit(); s.close()
    return cx


def _por_sistema(cx, mat="M1"):
    s = cx.sessao()
    r = {}
    for x in s.query(ValidacaoAcessoModel).filter_by(matricula=mat).all():
        r.setdefault(x.sistema or "", []).append((x.status, x.perfil_esperado or "",
                                                  x.motivo_status or ""))
    s.close()
    return r


class ACcoSegueAFuncaoDaPessoa(unittest.TestCase):

    def test_nao_recebe_o_sig_de_outra_funcao(self):
        """⭐ O caso do documento. A funcao dela nao preve SIG."""
        cx = _base("A_RECEBER_1")
        uc = ValidarAcessosSistema(cx)
        uc.executar()
        self.assertNotIn("SIG", _por_sistema(cx),
                         "o SIG vem da funcao 'A Receber 2 + SIG', que nao e' a dela")
        self.assertGreaterEqual(uc._cco_outra_funcao, 2)

    def test_continua_recebendo_o_da_propria_funcao(self):
        cx = _base("A_RECEBER_1")
        ValidarAcessosSistema(cx).executar()
        self.assertEqual([x[1] for x in _por_sistema(cx)["SICA_RA"]],
                         ["A Receber 1"])

    def test_desligar_a_chave_devolve_o_comportamento_anterior(self):
        cx = _base("A_RECEBER_1")
        ValidarAcessosSistema(cx, cco_pela_funcao=False).executar()
        self.assertIn("SIG", _por_sistema(cx),
                      "com a chave desligada a pessoa volta a herdar tudo do gestor")

    def test_sem_perfil_no_systur_nada_e_filtrado(self):
        """Sem ele nao da' para saber a funcao. Filtrar tiraria TODA a previsao
        — 1.034 linhas na base de 15/09. Errar para o lado de mostrar."""
        cx = _base(None)
        uc = ValidarAcessosSistema(cx)
        uc.executar()
        self.assertIn("SIG", _por_sistema(cx))
        self.assertEqual(uc._cco_outra_funcao, 0)


class NinguemSomePorCausaDoFiltro(unittest.TestCase):
    """A guarda que fecha o risco desta regra: se a CCO so' falava daquele
    sistema por OUTRA funcao e a pessoa TEM acesso, a linha inteira sumiria e
    o acesso ficaria invisivel. Medido em 23/09: 3 pares (2 pessoas), todos
    ja' pendencia antes — some-los seria pior que a pendencia errada."""

    def test_acesso_sem_previsao_vira_pendencia_e_nao_desaparece(self):
        cx = _base("A_RECEBER_1", acessos=[("SIG", "ATD_LAZER")])
        uc = ValidarAcessosSistema(cx)
        uc.executar()
        sig = _por_sistema(cx).get("SIG")
        self.assertIsNotNone(sig, "o acesso nao pode sumir da tela")
        self.assertEqual(sig[0][0], "EM_ANALISE")
        self.assertIn("ACESSO_FORA_DA_FUNCAO", sig[0][2])
        self.assertEqual(uc._acesso_fora_da_funcao, 1)

    def test_a_linha_diz_o_que_a_pessoa_tem(self):
        cx = _base("A_RECEBER_1", acessos=[("SIG", "ATD_LAZER")])
        ValidarAcessosSistema(cx).executar()
        s = cx.sessao()
        atual = [x.perfil_atual for x in s.query(ValidacaoAcessoModel)
                 .filter_by(matricula="M1", sistema="SIG").all()]
        s.close()
        self.assertEqual(atual, ["ATD_LAZER"])

    def test_sem_acesso_nenhum_nao_inventa_linha(self):
        """O discriminador: a guarda e' para nao ESCONDER posse, nao para
        criar pendencia de quem nao tem nada."""
        cx = _base("A_RECEBER_1")
        uc = ValidarAcessosSistema(cx)
        uc.executar()
        self.assertEqual(uc._acesso_fora_da_funcao, 0)


class ATelaExplicaOMotivo(unittest.TestCase):

    def test_o_sql_do_painel_traduz(self):
        import visualizador.main as vm
        self.assertIn("ACESSO_FORA_DA_FUNCAO", vm._SQL_BI)
        self.assertIn("a funcao dela nao o preve", vm._SQL_BI)


if __name__ == "__main__":
    unittest.main()
