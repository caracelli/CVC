# -*- coding: utf-8 -*-
"""Regra TEMPORARIA de provavel desligamento (sai na fase de desligados).

Criterio ate 15/09/2026: quem JA foi aderente num sistema (tinha o acesso) e
agora esta SEM NENHUM acesso era retirado da validacao. A regra nasceu em 12/06,
quando NAO havia base de desligados, e "perdeu o acesso" era a unica pista.

Desde 15/09 ela exige TAMBEM que a pessoa tenha SUMIDO do arquivo de ativos mais
recente (usuario: "se estao ativos e' porque ainda tem acesso, pode seguir
normalmente"). Motivo: a area listou ADMILSON (1152) e SILVIA (7550) entre os
"ativos que nao vem na aplicacao" — os dois no RH de 15/09, fora dos desligados
e com conta Oracle ativa, so' sem o SYSTUR que tinham em julho.

Quem NUNCA foi aderente (novo) continua SEM_ACESSO; quem TEM acesso (perfil
errado) continua DIVERGENTE.
"""
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy import text

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import (
    RhAtivo, PerfilEsperadoModel, AcessoSistema, ValidacaoAcessoModel)
from aplicacao.casos_de_uso.validar_acessos_sistema import ValidarAcessosSistema

SYS = "SYSTUR"
NOVO, VELHO = datetime(2026, 9, 15, 11, 0), datetime(2026, 7, 1, 14, 0)


class TestProvavelDesligamento(unittest.TestCase):

    def _run(self, foi_aderente, tem_acesso, n_perfis=1, sumiu_dos_ativos=True):
        """M1 e' o caso testado. Os outros 3 so' existem para definir qual e' o
        arquivo de ativos MAIS RECENTE (e para o corte de export parcial)."""
        tmp = tempfile.mkdtemp(prefix="cvc_deslig_")
        cx = ConexaoBancoDados(os.path.join(tmp, "d.db"))
        cx.inicializar()
        s = cx.sessao()
        arq_m1 = "VELHO.CSV" if sumiu_dos_ativos else "NOVO.CSV"
        s.add(RhAtivo(matricula="M1", nome="X", cpf="11111111111", cargo_codigo="CG",
                      cargo_descricao="ANALISTA", centro_custo_codigo="100",
                      situacao="ATIVO", arquivo_origem=arq_m1,
                      dt_importacao=VELHO if sumiu_dos_ativos else NOVO))
        for i in (2, 3, 4):      # maioria no arquivo novo
            s.add(RhAtivo(matricula=f"M{i}", nome=f"X{i}", cpf=f"2222222222{i}",
                          cargo_codigo="CG", cargo_descricao="OUTRO",
                          centro_custo_codigo="900", situacao="ATIVO",
                          arquivo_origem="NOVO.CSV", dt_importacao=NOVO))
        for i in range(n_perfis):
            s.add(PerfilEsperadoModel(cargo_codigo="100", cargo_descricao="ANALISTA",
                                      sistema=SYS, perfil=f"P{i+1}"))
        # SYSTUR precisa ter dados (senao vira SEM_DADOS)
        s.add(AcessoSistema(situacao="ATIVO", sistema=SYS, usuario="z", perfil="ZZ", matricula_vinculada="ZZ"))
        if tem_acesso:
            s.add(AcessoSistema(situacao="ATIVO", sistema=SYS, usuario="u1", perfil="OUTRO", matricula_vinculada="M1"))
        if foi_aderente:
            s.execute(text("INSERT INTO ciclo_vida_acesso (matricula,sistema,dt_aderente) "
                           "VALUES ('M1',:sis,'2026-06-10 10:00:00')"), {"sis": SYS})
        s.commit(); s.close()
        ValidarAcessosSistema(cx).executar()
        s = cx.sessao()
        rows = [r.status for r in s.query(ValidacaoAcessoModel).filter_by(matricula="M1").all()]
        s.close()
        return rows

    def test_foi_aderente_zero_acesso_e_sumiu_dos_ativos_e_retirado(self):
        self.assertEqual(self._run(foi_aderente=True, tem_acesso=False), [])

    def test_em_analise_zero_acesso_e_aderente_tambem_retira(self):
        # 2 perfis esperados + 0 acesso -> seria EM_ANALISE; mas foi aderente
        # E sumiu dos ativos -> retira
        self.assertEqual(self._run(foi_aderente=True, tem_acesso=False, n_perfis=2), [])

    def test_quem_segue_no_arquivo_de_ativos_nao_e_provavel_desligamento(self):
        """O caso ADMILSON/SILVIA: perdeu o acesso, mas continua ativo no RH —
        a pendencia REAL e' reincluir o acesso."""
        self.assertEqual(
            self._run(foi_aderente=True, tem_acesso=False, sumiu_dos_ativos=False),
            ["SEM_ACESSO"])

    def test_nunca_foi_aderente_continua_sem_acesso(self):
        # novo funcionario (nunca aderente) sem acesso -> pendencia REAL
        self.assertEqual(self._run(foi_aderente=False, tem_acesso=False), ["SEM_ACESSO"])

    def test_foi_aderente_mas_tem_acesso_continua_divergente(self):
        # tem acesso (perfil errado) -> nao e' desligamento -> DIVERGENTE normal
        self.assertEqual(self._run(foi_aderente=True, tem_acesso=True), ["DIVERGENTE"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
