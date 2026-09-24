# -*- coding: utf-8 -*-
"""OPERA OPERACIONAL SO' PELA CCO (usuario, 24/09/2026).

    "opera operacional pode trazer no painel so para cco"

Nao ha extrato do Opera. O que a CCO preve para a funcao da pessoa sai como
linha INFORMATIVA (status NAO_MAPEADO, motivo SEM_EXTRATO_OPERA_OPERACIONAL),
um perfil por linha, com a funcao carimbada — a tela agrupa em "Funcoes
previstas" e escreve "sem extrato". Nunca pendencia, nunca "incluir".

Antes disso o sistema tinha saido do enum (cb29ec9, 23/09) e as 33 linhas da
CCO eram ignoradas; e, mesmo com o enum, o caminho normal gerava SEM_DADOS,
que nao e' salvo — a linha nunca chegou ao painel.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import (
    RhAtivo, AcessoSistema, MatrizCcoModel, PerfilEsperadoModel,
    ValidacaoAcessoModel)
from aplicacao.casos_de_uso.validar_acessos_sistema import ValidarAcessosSistema
from dominio.objetos_valor.sistema import Sistema, sistema_do_texto

OPERA = "OPERA_OPERACIONAL"
CC = "07.01.02"


def _base(com_cco=True, perfil_systur="OPER_B2B"):
    tmp = tempfile.mkdtemp(prefix="cvc_opera_")
    cx = ConexaoBancoDados(os.path.join(tmp, "d.db"))
    cx.inicializar()
    s = cx.sessao()
    s.add(RhAtivo(matricula="M1", nome="PESSOA UM", cpf="00000000001",
                  cargo_codigo="CG", cargo_descricao="ANALISTA OPERACOES",
                  centro_custo_codigo=CC, gestor="GESTORA Y", situacao="ATIVO",
                  tipo_vinculo="FUNCIONARIO"))
    if perfil_systur:
        s.add(AcessoSistema(sistema="SYSTUR", usuario="s1", perfil=perfil_systur,
                            matricula_vinculada="M1", situacao="ATIVO"))
    if com_cco:
        for sis, perfil in (("Systur", "OPER_B2B"),
                            ("Opera Operacional", "OPER_B2B")):
            s.add(MatrizCcoModel(cc=CC, gestor="GESTORA Y", funcao="Operacional",
                                 sistema=sis, perfil=perfil))
        # outra funcao da mesma gestora — nao e' dela
        for sis, perfil in (("Systur", "SUPERV_OPER"),
                            ("Opera Operacional", "SUPERV_OPER")):
            s.add(MatrizCcoModel(cc=CC, gestor="GESTORA Y",
                                 funcao="Supervisor de Operacoes",
                                 sistema=sis, perfil=perfil))
    s.commit(); s.close()
    return cx


def _opera(cx):
    ValidarAcessosSistema(cx).executar()
    s = cx.sessao()
    r = sorted((x.status, x.perfil_esperado, x.motivo_status, x.funcao,
                x.situacao_acao)
               for x in s.query(ValidacaoAcessoModel)
               .filter_by(matricula="M1", sistema=OPERA).all())
    s.close()
    return r


class OperaSoPelaCco(unittest.TestCase):

    def test_a_cco_reconhece_o_opera(self):
        self.assertIs(sistema_do_texto("Opera Operacional"),
                      Sistema.OPERA_OPERACIONAL)

    def test_sai_o_que_a_funcao_dela_preve(self):
        """⭐ O pedido: a linha chega ao painel, com a funcao dela."""
        self.assertEqual(_opera(_base()), [
            ("NAO_MAPEADO", "OPER_B2B", "SEM_EXTRATO_OPERA_OPERACIONAL",
             "Operacional", "OK")])

    def test_nao_e_pendencia(self):
        self.assertEqual({r[4] for r in _opera(_base())}, {"OK"})

    def test_sem_cco_nao_sai_nada(self):
        """So' para CCO: sem CCO o Opera nao aparece."""
        self.assertEqual(_opera(_base(com_cco=False)), [])

    def test_sem_perfil_no_systur_vem_as_funcoes_da_equipe(self):
        """Sem SYSTUR nao ha' como saber a funcao — mesma regra do resto da
        CCO: mostra as da equipe, nao esconde."""
        self.assertEqual(sorted(r[1] for r in _opera(_base(perfil_systur=None))),
                         ["OPER_B2B", "SUPERV_OPER"])


class TelaTraduzSemExtrato(unittest.TestCase):

    def test_texto_no_sql_do_painel(self):
        import sqlite3
        tmp = tempfile.mkdtemp(prefix="cvc_bi_op_")
        db = os.path.join(tmp, "iam.db")
        ConexaoBancoDados(db).inicializar()
        c = sqlite3.connect(db)
        try:
            c.execute(
                "INSERT INTO validacao_acessos (matricula, nome, sistema,"
                " perfil_esperado, perfil_atual, status, motivo_status,"
                " dt_processamento) VALUES (?,?,?,?,?,?,?,?)",
                ("M1", "PESSOA", OPERA, "OPER_B2B", "", "NAO_MAPEADO",
                 "SEM_EXTRATO_OPERA_OPERACIONAL", "2026-09-24 09:00:00"))
            c.commit()
            import visualizador.main as vm
            c.executescript(vm._SQL_BI)
            motivo, acao = c.execute(
                "SELECT motivo, acao FROM bi_divergencias").fetchone()
        finally:
            c.close()
        self.assertIn("nao da para conferir", motivo)
        self.assertEqual(acao, "Não Mapeado",
                         "a tela decide 'informativo' por este rotulo")


if __name__ == "__main__":
    unittest.main()
