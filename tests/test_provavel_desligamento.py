# -*- coding: utf-8 -*-
"""Regra TEMPORARIA de provavel desligamento (sai na fase de desligados):
quem JA foi aderente num sistema (tinha o acesso) e agora esta SEM NENHUM acesso
e' retirado da validacao (nao gera pendencia) — sinal forte de desligamento sem
o arquivo de desligados. Quem NUNCA foi aderente (novo) continua SEM_ACESSO;
quem TEM acesso (perfil errado) continua DIVERGENTE.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy import text

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import (
    RhAtivo, PerfilEsperadoModel, AcessoSistema, ValidacaoAcessoModel)
from aplicacao.casos_de_uso.validar_acessos_sistema import ValidarAcessosSistema

SYS = "SYSTUR"


class TestProvavelDesligamento(unittest.TestCase):

    def _run(self, foi_aderente, tem_acesso, n_perfis=1):
        tmp = tempfile.mkdtemp(prefix="cvc_deslig_")
        cx = ConexaoBancoDados(os.path.join(tmp, "d.db"))
        cx.inicializar()
        s = cx.sessao()
        s.add(RhAtivo(matricula="M1", nome="X", cpf="11111111111", cargo_codigo="CG",
                      cargo_descricao="ANALISTA", centro_custo_codigo="100", situacao="ATIVO"))
        for i in range(n_perfis):
            s.add(PerfilEsperadoModel(cargo_codigo="100", cargo_descricao="ANALISTA",
                                      sistema=SYS, perfil=f"P{i+1}"))
        # SYSTUR precisa ter dados (senao vira SEM_DADOS)
        s.add(AcessoSistema(sistema=SYS, usuario="z", perfil="ZZ", matricula_vinculada="ZZ"))
        if tem_acesso:
            s.add(AcessoSistema(sistema=SYS, usuario="u1", perfil="OUTRO", matricula_vinculada="M1"))
        if foi_aderente:
            s.execute(text("INSERT INTO ciclo_vida_acesso (matricula,sistema,dt_aderente) "
                           "VALUES ('M1',:sis,'2026-06-10 10:00:00')"), {"sis": SYS})
        s.commit(); s.close()
        ValidarAcessosSistema(cx).executar()
        s = cx.sessao()
        rows = [r.status for r in s.query(ValidacaoAcessoModel).filter_by(matricula="M1").all()]
        s.close()
        return rows

    def test_foi_aderente_e_zero_acesso_e_retirado(self):
        self.assertEqual(self._run(foi_aderente=True, tem_acesso=False), [])

    def test_em_analise_zero_acesso_e_aderente_tambem_retira(self):
        # 2 perfis esperados + 0 acesso -> seria EM_ANALISE; mas foi aderente -> retira
        self.assertEqual(self._run(foi_aderente=True, tem_acesso=False, n_perfis=2), [])

    def test_nunca_foi_aderente_continua_sem_acesso(self):
        # novo funcionario (nunca aderente) sem acesso -> pendencia REAL
        self.assertEqual(self._run(foi_aderente=False, tem_acesso=False), ["SEM_ACESSO"])

    def test_foi_aderente_mas_tem_acesso_continua_divergente(self):
        # tem acesso (perfil errado) -> nao e' desligamento -> DIVERGENTE normal
        self.assertEqual(self._run(foi_aderente=True, tem_acesso=True), ["DIVERGENTE"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
