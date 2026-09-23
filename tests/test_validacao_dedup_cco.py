# -*- coding: utf-8 -*-
"""Regressao do bug de pendencia em DOBRO: matriz de perfis + CCO cobrindo o
mesmo (sistema, perfil) gerava duas linhas. Fix: a matriz vence; a CCO so
adiciona o que a matriz nao cobriu. (IC nao usa CCO — so SYSTUR e afins.)

23/09/2026 — A PRECEDENCIA FICOU MAIS FORTE. Regra do usuario: "regra primeiro
matriz depois cco" (e, em 22/09, "quem nao tem matriz tem cco"). A matriz nao
vence mais so' no EMPATE de perfil: quando ela fala de um sistema para aquela
pessoa, a CCO nao entra NAQUELE sistema. A precedencia e' POR SISTEMA — a
matriz calar sobre o SIGOT nao cala a CCO sobre ele.

Medido na base de 15/09: 14 perfis da CCO descartados, e UMA pessoa deixou de
ser aderente (CLAUDIA 90001433 — detalhe no teste correspondente). 23 das 25
combinacoes (sistema, status) ficaram identicas.

A garantia central da classe nao mudou: a mesma pessoa nunca sai OK por uma
origem e DIVERGENTE pela outra no mesmo run.
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

    def test_cco_nao_acrescenta_onde_a_matriz_falou(self):
        """MUDOU EM 23/09/2026. Ate' aqui a CCO ACRESCENTAVA o perfil que a
        matriz nao tinha (PA da matriz + PB da CCO = 2 linhas). O usuario
        definiu outra regra: "regra primeiro matriz depois cco" — a CCO so'
        responde pelos sistemas sobre os quais a matriz calou.

        O caso M1 (mesmo par nos dois catalogos) continua valendo igual; o que
        muda e' este, o de perfis DIFERENTES."""
        r = self.by_mat["M2"]
        self.assertEqual([(x.perfil_esperado, x.origem_matriz) for x in r],
                         [("PA", "MATRIZ")])

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

    def test_nunca_ok_e_divergente_ao_mesmo_tempo(self):
        """A GARANTIA ORIGINAL desta classe, que continua valendo: a mesma
        pessoa nao pode sair OK por uma origem e DIVERGENTE pela outra no
        mesmo run. Antes isso era garantido JUNTANDO as duas num conjunto
        unico; desde 23/09 e' garantido porque so' UMA origem responde pelo
        sistema. O defeito e' estruturalmente impossivel nos dois desenhos.

        MUDOU O VEREDITO: a M5 tem o perfil que a CCO previa (PG) e a matriz
        do cargo dela preve outro (PF) — antes saia OK pela CCO, agora sai
        pendencia, porque quem responde pelo sistema e' a matriz.

        Caso real medido em 23/09 na base de 15/09, e foi o UNICO: CLAUDIA DA
        LUZ SALIDO RIVERO (90001433), ANALISTA FINANCEIRO JR. A matriz do
        cargo preve TESOURARIA e CUSTOS; a CCO da gestora preve
        ATD_FOR_TREND_N2, que e' o que ela tem. Virou pendencia."""
        r = self.by_mat["M5"]
        status = {x.status for x in r}
        self.assertNotIn("OK", status)
        self.assertEqual({x.origem_matriz for x in r}, {"MATRIZ"})
        self.assertEqual([x.perfil_esperado for x in r], ["PF"])
        self.assertTrue(all(x.perfil_atual == "PG" for x in r),
                        "a linha tem de dizer o que ela REALMENTE tem")

    def test_aderencia_vence_em_analise_da_cco(self):
        # Tem o perfil da matriz; a CCO ofereceria 2 opcoes (sozinha = EM_ANALISE)
        # -> no conjunto unico a aderencia vence: SO OK.
        r = self.by_mat["M6"]
        self.assertEqual([x.status for x in r], ["OK"])
        self.assertEqual((r[0].perfil_esperado, r[0].origem_matriz), ("PH", "MATRIZ"))

    def test_so_a_matriz_responde_quando_ela_fala(self):
        """MUDOU EM 23/09/2026. Antes: matriz(PK) + cco(PL,PM) = 3 esperados e
        3 linhas EM_ANALISE. Agora a matriz responde sozinha por SYSTUR, entao
        sobra so' PK — e com 1 esperado e 1 acesso que nao casam o veredito e'
        DIVERGENTE ("perfil errado"), nao EM_ANALISE ("ambiguidade").

        O que NAO mudou, e importa: a linha continua dizendo o que a pessoa
        REALMENTE tem (PZ) em perfil_atual."""
        r = self.by_mat["M7"]
        self.assertEqual([x.perfil_esperado for x in r], ["PK"])
        self.assertEqual([x.origem_matriz for x in r], ["MATRIZ"])
        self.assertEqual([x.status for x in r], ["DIVERGENTE"])
        self.assertTrue(all(x.perfil_atual == "PZ" for x in r))

    def test_o_comportamento_anterior_ainda_e_alcancavel(self):
        """A precedencia e' um parametro do motor, nao uma reescrita. Este
        teste exercita o desenho ANTIGO (as duas origens somadas) — serve para
        provar que a diferenca e' so' essa chave, e para medir o efeito na base
        real sem manter duas versoes do motor."""
        import tempfile as _tmp
        cx = ConexaoBancoDados(os.path.join(_tmp.mkdtemp(prefix="cvc_prec0_"), "d.db"))
        cx.inicializar()
        s = cx.sessao()
        s.add_all([
            _rh("X1", "900", "ANALISTA"),
            PerfilEsperadoModel(cargo_codigo="900", cargo_descricao="ANALISTA",
                                sistema=SYSTUR, perfil="PA"),
            MatrizCcoModel(cc="900", funcao="ANALISTA", sistema="Systur", perfil="PB"),
            AcessoSistema(situacao="ATIVO", sistema=SYSTUR, usuario="z",
                          perfil="ZZ", matricula_vinculada="ZZ"),
        ])
        s.commit(); s.close()
        ValidarAcessosSistema(cx, matriz_tem_precedencia=False).executar()
        s = cx.sessao()
        r = sorted((x.perfil_esperado, x.origem_matriz)
                   for x in s.query(ValidacaoAcessoModel).filter_by(matricula="X1").all())
        s.close()
        self.assertEqual(r, [("PA", "MATRIZ"), ("PB", "CCO")])

    def test_cco_para_sistema_sem_dados_nao_vira_em_analise(self):
        # CCO de sistema fora de escopo (sem extrato) -> SEM_DADOS, que NAO e'
        # salvo. M8 nao pode aparecer com NENHUMA pendencia (nem EM_ANALISE).
        self.assertNotIn("M8", self.by_mat)


if __name__ == "__main__":
    unittest.main(verbosity=2)
