# -*- coding: utf-8 -*-
"""Quando a MATRIZ por cargo cobre o sistema, a CCO nao entra.

Regra do usuario, dita duas vezes:

    22/09/2026 — "a pessoa nao precisa ter as duas origens, na regra quem nao
                  tem matriz tem cco"
    23/09/2026 — "regra primeiro matriz depois cco"

O QUE MUDOU
  antes: as duas origens eram SOMADAS num conjunto unico por sistema, e a
         matriz so' vencia no EMPATE de perfil (dedup por sistema+perfil).
         Resultado: quem ja' estava coberto pela matriz recebia, por cima,
         os perfis que a CCO previa para o (centro de custo, gestor) dele —
         dois catalogos diferentes misturados na mesma lista de esperados.
  agora: a CCO so' responde pelos sistemas sobre os quais a matriz CALOU.

Medido em 23/09/2026 na base de 15/09: 7 pessoas, 14 perfis da CCO, todos no
SYSTUR. As duas matrizes quase nao se sobrepoem — a regra e' de principio,
nao de volume.

NAO confundir com a ancora do SYSTUR (test_ancora_perfil_systur.py): aquela
FILTRA o esperado pelo perfil que a pessoa tem; esta decide QUAL CATALOGO
responde pelo sistema.
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

CC, CARGO, GESTOR = "100", "ANALISTA", "GESTOR X"
SYS, SIGOT = "SYSTUR", "SIGOT"


def _base(com_matriz_no_systur=True):
    """M1 tem matriz no SYSTUR (opcional) e CCO no SYSTUR e no SIGOT.

    O SIGOT existe para provar que a precedencia e' POR SISTEMA: a matriz
    calar sobre ele nao pode calar a CCO tambem.
    """
    tmp = tempfile.mkdtemp(prefix="cvc_prec_")
    cx = ConexaoBancoDados(os.path.join(tmp, "d.db"))
    cx.inicializar()
    s = cx.sessao()
    s.add(RhAtivo(matricula="M1", nome="PESSOA UM", cpf="00000000001",
                  cargo_codigo="CG", cargo_descricao=CARGO,
                  centro_custo_codigo=CC, gestor=GESTOR, situacao="ATIVO",
                  tipo_vinculo="FUNCIONARIO"))
    # M2 existe SO' para os dois sistemas terem extrato (sem dados a validacao
    # sai SEM_DADOS e nada e' julgado). Vai em OUTRO centro de custo e com
    # OUTRO gestor de proposito: assim nem a matriz nem a CCO se aplicam a ela
    # e os contadores do caso de teste falam so' da M1.
    s.add(RhAtivo(matricula="M2", nome="OUTRA", cpf="00000000002",
                  cargo_codigo="CG", cargo_descricao="OUTRO CARGO",
                  centro_custo_codigo="999", gestor="OUTRO GESTOR",
                  situacao="ATIVO", tipo_vinculo="FUNCIONARIO"))
    for sis, perf in ((SYS, "DA_MATRIZ"), (SIGOT, "DA_CCO_SIGOT")):
        s.add(AcessoSistema(sistema=sis, usuario="u2", perfil=perf,
                            matricula_vinculada="M2", situacao="ATIVO"))

    if com_matriz_no_systur:
        s.add(PerfilEsperadoModel(cargo_codigo=CC, cargo_descricao=CARGO,
                                  sistema=SYS, perfil="DA_MATRIZ"))
    s.add(MatrizCcoModel(cc=CC, gestor=GESTOR, funcao="Financeiro",
                         sistema="Systur", perfil="DA_CCO_SYSTUR"))
    s.add(MatrizCcoModel(cc=CC, gestor=GESTOR, funcao="Financeiro",
                         sistema="Sigot", perfil="DA_CCO_SIGOT"))
    s.commit(); s.close()
    return cx


def _esperados(cx, sistema):
    s = cx.sessao()
    r = sorted({x.perfil_esperado for x in s.query(ValidacaoAcessoModel)
                .filter_by(matricula="M1").all()
                if x.sistema == sistema and x.perfil_esperado})
    s.close()
    return r


def _origens(cx, sistema):
    s = cx.sessao()
    r = sorted({x.origem_matriz for x in s.query(ValidacaoAcessoModel)
                .filter_by(matricula="M1").all() if x.sistema == sistema})
    s.close()
    return r


class AMatrizResponde(unittest.TestCase):

    def test_a_cco_nao_acrescenta_onde_a_matriz_falou(self):
        """⭐ O coracao da regra: no SYSTUR quem responde e' a matriz, e o
        perfil que so' a CCO previa NAO entra na lista de esperados."""
        cx = _base(com_matriz_no_systur=True)
        uc = ValidarAcessosSistema(cx)
        uc.executar()
        self.assertEqual(_esperados(cx, SYS), ["DA_MATRIZ"])
        self.assertEqual(_origens(cx, SYS), ["MATRIZ"])
        self.assertEqual(uc._cco_apos_matriz, 1)

    def test_a_precedencia_e_por_sistema(self):
        """A matriz calar sobre o SIGOT nao pode calar a CCO tambem — senao a
        regra viraria "quem tem matriz em ALGUM sistema perde a CCO em TODOS"."""
        cx = _base(com_matriz_no_systur=True)
        ValidarAcessosSistema(cx).executar()
        self.assertEqual(_esperados(cx, SIGOT), ["DA_CCO_SIGOT"])
        self.assertEqual(_origens(cx, SIGOT), ["CCO"])

    def test_sem_matriz_a_cco_responde(self):
        """"quem nao tem matriz tem cco" — o outro lado da mesma regra."""
        cx = _base(com_matriz_no_systur=False)
        uc = ValidarAcessosSistema(cx)
        uc.executar()
        self.assertEqual(_esperados(cx, SYS), ["DA_CCO_SYSTUR"])
        self.assertEqual(_origens(cx, SYS), ["CCO"])
        self.assertEqual(uc._cco_apos_matriz, 0)


if __name__ == "__main__":
    unittest.main()
