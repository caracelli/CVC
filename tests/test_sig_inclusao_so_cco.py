# -*- coding: utf-8 -*-
"""SIG: quem diz o que a pessoa DEVERIA ter e' so' a matriz CCO.

Regra definida pela area em 23/09/2026, textual:

    "o SIG nao tem matriz, a principio eu tiraria ele do processo de inclusao,
     deixaria ele exclusivamente para o CCO. (...) ou criar uma regra especifica
     do sistema SIG, tipo ele nao validar se a pessoa precisa ter, mas se
     alguem tiver, ele fazer as validacoes que colocamos."

    "SIG — incluir: basear na matriz CCO, se tiver ok, se nao, nao realizar
     nenhuma outra validacao. Se for matriz func ou franqueado, validar se a
     pessoa tem acesso; se tiver acesso aplicar a regra que definimos la, que ai
     ele vai trazer os perfis que as pessoas tem e nao deveria ter, ou que pode
     ter e tem a mais."

O QUE MUDOU
  antes: o espelho dos colegas sugeria INCLUSAO de SIG para quem nao tinha
         acesso — 377 linhas na base de 15/09, sendo 226 de prestador.
  agora: o SIG entra na CCO (era explicitamente pulado) e o espelho deixa de
         sugerir inclusao. Quem TEM acesso continua sendo julgado pelo espelho,
         igual a antes.

Desligados e transferidos nao sao tocados: passam por outro caminho.
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

SIG = "SIG"


def _base():
    """Grupo-espelho real + uma pessoa coberta pela CCO.

    cc=100 / gestor=G1 / cargo=ANALISTA
        A e B  -> tem SIG P1 (dois colegas, padrao = {P1})
        X      -> NAO tem SIG e NAO esta na CCO
        Z      -> tem SIG P1
    cc=200 / gestor=G2
        Y      -> CCO preve SIG P9; nao tem acesso
    """
    tmp = tempfile.mkdtemp(prefix="cvc_sig_")
    cx = ConexaoBancoDados(os.path.join(tmp, "d.db"))
    cx.inicializar()
    s = cx.sessao()

    def pessoa(mat, cc, gestor):
        s.add(RhAtivo(matricula=mat, nome=f"P{mat}", cpf=mat.rjust(11, "0"),
                      cargo_codigo="CG", cargo_descricao="ANALISTA",
                      centro_custo_codigo=cc, gestor=gestor, situacao="ATIVO",
                      tipo_vinculo="FUNCIONARIO"))

    for m in ("A", "B", "X", "Z"):
        pessoa(m, "100", "G1")
    pessoa("Y", "200", "G2")

    for m in ("A", "B", "Z"):
        s.add(AcessoSistema(sistema=SIG, usuario=f"u{m}", perfil="P1",
                            matricula_vinculada=m, situacao="ATIVO"))

    s.add(MatrizCcoModel(cc="200", gestor="G2", funcao="Financeiro",
                         sistema="SIG", perfil="P9"))
    s.commit(); s.close()
    return cx


def _linhas(cx, mat):
    """So' as linhas de SIG.

    Quem nao tem matriz nem CCO ganha tambem a linha informativa "Nao Mapeado"
    (regra #29), que nasce no laco por pessoa, antes do espelho rodar. Ela e'
    anterior a esta regra e nao e' o que estes testes julgam."""
    s = cx.sessao()
    r = [(x.sistema, x.status, x.origem_matriz, x.perfil_esperado or "")
         for x in s.query(ValidacaoAcessoModel).filter_by(matricula=mat).all()
         if x.sistema == SIG]
    s.close()
    return r


class SigInclusaoSoPelaCco(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cx = _base()
        cls.uc = ValidarAcessosSistema(cls.cx)
        cls.uc.executar()

    def test_quem_esta_na_cco_recebe_a_inclusao(self):
        """Y nao tem SIG e a CCO preve: vira Incluir Acesso, origem CCO."""
        self.assertEqual(_linhas(self.cx, "Y"),
                         [(SIG, "SEM_ACESSO", "CCO", "P9")])

    def test_quem_nao_esta_na_cco_e_nao_tem_acesso_nao_recebe_nada(self):
        """⭐ O coracao da regra. X tem dois colegas com o padrao P1 — antes de
        23/09 isso virava 'Incluir Acesso' tirado do espelho. Agora nao."""
        self.assertEqual(_linhas(self.cx, "X"), [])

    def test_quem_tem_acesso_continua_sendo_validado(self):
        """'se alguem tiver, ele fazer as validacoes que colocamos': Z tem
        exatamente o padrao do grupo -> segue Aderente pelo espelho."""
        self.assertEqual(_linhas(self.cx, "Z"),
                         [(SIG, "OK", "ESPELHO", "P1")])

    def test_quem_veio_da_cco_nao_sai_duas_vezes(self):
        """Y nao pode receber uma segunda linha pelo espelho."""
        self.assertEqual(len([x for x in _linhas(self.cx, "Y") if x[0] == SIG]), 1)

    def test_o_contador_registra_a_supressao(self):
        self.assertGreaterEqual(self.uc._sig_inclusao_suprimida, 1)


class ORestoDoSigNaoMuda(unittest.TestCase):
    """Nao-regressao: o espelho continua julgando quem TEM acesso."""

    def test_excesso_continua_indo_para_analise(self):
        cx = _base()
        s = cx.sessao()
        s.add(AcessoSistema(sistema=SIG, usuario="uZ2", perfil="SOBRA",
                            matricula_vinculada="Z", situacao="ATIVO"))
        s.commit(); s.close()
        ValidarAcessosSistema(cx).executar()
        self.assertEqual([x[1] for x in _linhas(cx, "Z")], ["EM_ANALISE"])
        # e o excesso continua sendo o motivo: ela tem P1 (padrao) + SOBRA
        self.assertEqual(len(_linhas(cx, "Z")), 1)


if __name__ == "__main__":
    unittest.main()
