# -*- coding: utf-8 -*-
"""Regressao do bug de pendencia em DOBRO: matriz de perfis + CCO cobrindo o
mesmo (sistema, perfil) gerava duas linhas. Fix: a matriz vence; a CCO so
adiciona o que a matriz nao cobriu. (IC nao usa CCO — so SYSTUR e afins.)
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import (
    RhAtivo, PerfilEsperadoModel, MatrizCcoModel, AcessoSistema, ValidacaoAcessoModel,
)
from aplicacao.casos_de_uso.validar_acessos_sistema import ValidarAcessosSistema

SYSTUR = "SYSTUR"


def _rh(mat, cc, cargo):
    return RhAtivo(matricula=mat, nome=mat, cpf=mat.rjust(11, "0"), cargo_codigo="CG",
                   cargo_descricao=cargo, centro_custo_codigo=cc, situacao="ATIVO")


class TestDedupCCO(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="cvc_dedup_")
        cls.conexao = ConexaoBancoDados(os.path.join(cls._tmp, "d.db"))
        cls.conexao.inicializar()
        s = cls.conexao.sessao()
        s.add_all([
            # M1: matriz e CCO cobrem o MESMO (SYSTUR, P1) -> 1 linha (MATRIZ)
            _rh("M1", "100", "ANALISTA"),
            PerfilEsperadoModel(cargo_codigo="100", cargo_descricao="ANALISTA", sistema=SYSTUR, perfil="P1"),
            MatrizCcoModel(cc="100", funcao="ANALISTA", sistema="Systur", perfil="P1"),
            # M2: matriz tem PA; CCO tem PB (diferente) -> 2 linhas (MATRIZ + CCO)
            _rh("M2", "200", "GERENTE"),
            PerfilEsperadoModel(cargo_codigo="200", cargo_descricao="GERENTE", sistema=SYSTUR, perfil="PA"),
            MatrizCcoModel(cc="200", funcao="GERENTE", sistema="Systur", perfil="PB"),
            # M3: so CCO (sem matriz) -> 1 linha origem CCO
            _rh("M3", "300", "OPERADOR"),
            MatrizCcoModel(cc="300", funcao="OPERADOR", sistema="Systur", perfil="PC"),
            # M4 (caso EMERSON): matriz espera PD; CCO espera PE; a pessoa TEM PD.
            # Antes do merge: OK (matriz) + DIVERGENTE (cco) juntos. Agora: SO OK.
            _rh("M4", "400", "DIRETOR"),
            PerfilEsperadoModel(cargo_codigo="400", cargo_descricao="DIRETOR", sistema=SYSTUR, perfil="PD"),
            MatrizCcoModel(cc="400", funcao="DIRETOR", sistema="Systur", perfil="PE"),
            AcessoSistema(situacao="ATIVO", sistema=SYSTUR, usuario="m4", perfil="PD", matricula_vinculada="M4"),
            # M5 (simetrico): matriz espera PF; CCO espera PG; a pessoa TEM PG
            # (aderente pela CCO). Antes: DIVERGENTE (matriz) + OK (cco). Agora: SO OK.
            _rh("M5", "500", "SUPERVISOR"),
            PerfilEsperadoModel(cargo_codigo="500", cargo_descricao="SUPERVISOR", sistema=SYSTUR, perfil="PF"),
            MatrizCcoModel(cc="500", funcao="SUPERVISOR", sistema="Systur", perfil="PG"),
            AcessoSistema(situacao="ATIVO", sistema=SYSTUR, usuario="m5", perfil="PG", matricula_vinculada="M5"),
            # M6: aderencia VENCE o EM_ANALISE da CCO. Matriz espera PH (a pessoa
            # TEM PH); CCO oferece PI e PJ (2 opcoes -> sozinha seria EM_ANALISE).
            # No conjunto unico: tem PH aderente -> SO OK.
            _rh("M6", "600", "COORD"),
            PerfilEsperadoModel(cargo_codigo="600", cargo_descricao="COORD", sistema=SYSTUR, perfil="PH"),
            MatrizCcoModel(cc="600", funcao="COORD", sistema="Systur", perfil="PI"),
            MatrizCcoModel(cc="600", funcao="COORD", sistema="Systur", perfil="PJ"),
            AcessoSistema(situacao="ATIVO", sistema=SYSTUR, usuario="m6", perfil="PH", matricula_vinculada="M6"),
            # M7: matriz(PK) + cco(PL,PM) = 3 esperados; a pessoa tem PZ (nenhum
            # aderente) -> EM_ANALISE nos 3, perfil_atual = o que ela tem (PZ).
            _rh("M7", "700", "ASSIST"),
            PerfilEsperadoModel(cargo_codigo="700", cargo_descricao="ASSIST", sistema=SYSTUR, perfil="PK"),
            MatrizCcoModel(cc="700", funcao="ASSIST", sistema="Systur", perfil="PL"),
            MatrizCcoModel(cc="700", funcao="ASSIST", sistema="Systur", perfil="PM"),
            AcessoSistema(situacao="ATIVO", sistema=SYSTUR, usuario="m7", perfil="PZ", matricula_vinculada="M7"),
            # M8: CCO aponta perfis para um sistema SEM dados de acesso (SIGOT,
            # fora de escopo). Tem que virar SEM_DADOS (NAO salvo) — e NAO uma
            # enxurrada de EM_ANALISE falso. Regressao da "explosao de EM_ANALISE".
            _rh("M8", "800", "EXTERNO"),
            MatrizCcoModel(cc="800", funcao="EXTERNO", sistema="Sigot", perfil="PQ"),
            MatrizCcoModel(cc="800", funcao="EXTERNO", sistema="Sigot", perfil="PR"),
            # garante SYSTUR com dados (status SEM_ACESSO, nao SEM_DADOS)
            AcessoSistema(situacao="ATIVO", sistema=SYSTUR, usuario="x", perfil="ZZ", matricula_vinculada="ZZ"),
        ])
        s.commit()
        s.close()
        ValidarAcessosSistema(cls.conexao).executar()
        s = cls.conexao.sessao()
        cls.by_mat = {}
        for r in s.query(ValidacaoAcessoModel).all():
            cls.by_mat.setdefault(r.matricula, []).append(r)
        s.close()

    def test_matriz_e_cco_mesmo_par_nao_duplica(self):
        r = self.by_mat["M1"]
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0].origem_matriz, "MATRIZ")
        self.assertEqual(r[0].perfil_esperado, "P1")

    def test_cco_com_perfil_diferente_e_adicionado(self):
        r = sorted(self.by_mat["M2"], key=lambda x: x.perfil_esperado)
        self.assertEqual([(x.perfil_esperado, x.origem_matriz) for x in r],
                         [("PA", "MATRIZ"), ("PB", "CCO")])

    def test_cco_sozinho_ainda_funciona(self):
        r = self.by_mat["M3"]
        self.assertEqual(len(r), 1)
        self.assertEqual((r[0].perfil_esperado, r[0].origem_matriz), ("PC", "CCO"))

    def test_aderente_a_matriz_nao_gera_divergente_pela_cco(self):
        # Caso EMERSON: tem o perfil da MATRIZ; a CCO espera outro -> SO OK,
        # sem a pendencia fantasma (matriz+cco avaliados como conjunto unico).
        r = self.by_mat["M4"]
        self.assertEqual([x.status for x in r], ["OK"])
        self.assertEqual(r[0].perfil_esperado, "PD")
        self.assertEqual(r[0].origem_matriz, "MATRIZ")

    def test_aderente_a_cco_nao_gera_divergente_pela_matriz(self):
        # Simetrico: tem o perfil da CCO; a matriz espera outro -> SO OK (origem CCO).
        r = self.by_mat["M5"]
        self.assertEqual([x.status for x in r], ["OK"])
        self.assertEqual(r[0].perfil_esperado, "PG")
        self.assertEqual(r[0].origem_matriz, "CCO")

    def test_aderencia_vence_em_analise_da_cco(self):
        # Tem o perfil da matriz; a CCO ofereceria 2 opcoes (sozinha = EM_ANALISE)
        # -> no conjunto unico a aderencia vence: SO OK.
        r = self.by_mat["M6"]
        self.assertEqual([x.status for x in r], ["OK"])
        self.assertEqual((r[0].perfil_esperado, r[0].origem_matriz), ("PH", "MATRIZ"))

    def test_merge_matriz_cco_vira_em_analise_com_todos_esperados(self):
        # matriz(1) + cco(2) = 3 esperados, nenhum aderente -> EM_ANALISE nos 3,
        # carregando o perfil que a pessoa realmente tem (PZ) em perfil_atual.
        r = self.by_mat["M7"]
        self.assertEqual(sorted(x.status for x in r), ["EM_ANALISE"] * 3)
        self.assertEqual(sorted(x.perfil_esperado for x in r), ["PK", "PL", "PM"])
        self.assertTrue(all(x.perfil_atual == "PZ" for x in r))
        # origem preservada por perfil: PK veio da MATRIZ, PL/PM da CCO
        origem = {x.perfil_esperado: x.origem_matriz for x in r}
        self.assertEqual(origem, {"PK": "MATRIZ", "PL": "CCO", "PM": "CCO"})

    def test_cco_para_sistema_sem_dados_nao_vira_em_analise(self):
        # CCO de sistema fora de escopo (sem extrato) -> SEM_DADOS, que NAO e'
        # salvo. M8 nao pode aparecer com NENHUMA pendencia (nem EM_ANALISE).
        self.assertNotIn("M8", self.by_mat)


if __name__ == "__main__":
    unittest.main(verbosity=2)
