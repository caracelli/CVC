# -*- coding: utf-8 -*-
"""Não Mapeado vale para todos os vinculos — menos o franqueado sem acesso.

Usuario, 15/09/2026: "a regra serve para todos". Terceiro/prestador que
terminava sem NENHUMA linha (sem conta, ou espelho sem padrao) sumia do painel,
como o CLT antes de 09/09. Passa a ter a linha informativa NAO_MAPEADO.

Franqueado sem acesso segue SEM linha: decisao de 04/09 (789268c, a area pediu
"e' para nao ter esse espelho de franqueados") que o usuario mandou manter.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import RhAtivo, AcessoSistema, ValidacaoAcessoModel
from aplicacao.casos_de_uso.validar_acessos_sistema import ValidarAcessosSistema

SYS = "SYSTUR"


class NaoMapeadoPorVinculo(unittest.TestCase):

    def _status(self, vinculo, com_conta=False):
        tmp = tempfile.mkdtemp(prefix="cvc_naomap_v_")
        cx = ConexaoBancoDados(os.path.join(tmp, "v.db"))
        cx.inicializar()
        s = cx.sessao()
        s.add(RhAtivo(matricula="M1", nome="X", cpf="11111111111", cargo_codigo="CG",
                      cargo_descricao="ATENDENTE", centro_custo_codigo="100",
                      situacao="ATIVO", tipo_vinculo=vinculo,
                      empresa="EMPRESA A", gestor="GESTOR A", departamento="SUP A"))
        # SYSTUR precisa ter dados (senao vira SEM_DADOS)
        s.add(AcessoSistema(situacao="ATIVO", sistema=SYS, usuario="z", perfil="ZZ",
                            matricula_vinculada="ZZ"))
        if com_conta:
            # conta sozinha no grupo: espelho sem par comparavel -> sem linha
            s.add(AcessoSistema(situacao="ATIVO", sistema=SYS, usuario="u1",
                                perfil="QUALQUER", matricula_vinculada="M1"))
        s.commit(); s.close()
        ValidarAcessosSistema(cx).executar()
        s = cx.sessao()
        try:
            return [r.status for r in
                    s.query(ValidacaoAcessoModel).filter_by(matricula="M1").all()]
        finally:
            s.close()

    def test_prestador_sem_conta_vira_nao_mapeado(self):
        self.assertEqual(self._status("PRESTADOR"), ["NAO_MAPEADO"])

    def test_terceiro_sem_conta_vira_nao_mapeado(self):
        self.assertEqual(self._status("TERCEIRO"), ["NAO_MAPEADO"])

    def test_prestador_com_conta_sem_padrao_de_espelho_nao_some(self):
        self.assertEqual(len(self._status("PRESTADOR", com_conta=True)), 1)

    def test_franqueado_sem_acesso_segue_sem_linha(self):
        """Decisao de 04/09 mantida pelo usuario em 15/09."""
        self.assertEqual(self._status("FRANQUEADO"), [])

    def test_clt_sem_matriz_continua_nao_mapeado(self):
        self.assertEqual(self._status("FUNCIONARIO"), ["NAO_MAPEADO"])


if __name__ == "__main__":
    unittest.main()
