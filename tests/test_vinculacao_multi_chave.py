# -*- coding: utf-8 -*-
"""Testes da cascata de matching multi-chave (CPF -> email -> CPF parcial+nome -> nome -> fuzzy).

Niveis (do mais confiavel pro menos):
  1. CPF exato         -> score 1.00, metodo=CPF
  2. Email exato       -> score 0.95, metodo=EMAIL
  3. CPF parcial+nome  -> score 0.90, metodo=CPF_PARCIAL_NOME
  4. Nome exato        -> score 0.70, metodo=NOME (com flag se ambiguo)
  5. Fuzzy nome        -> score 0.50, metodo=FUZZY (NAO vincula, so candidatos)
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dominio.servicos_dominio.servico_vinculacao_multi_chave import (
    FuncionarioRef, ServicoVinculacaoMultiChave,
    METODO_CPF, METODO_EMAIL, METODO_CPF_PARCIAL_NOME, METODO_NOME,
    METODO_FUZZY, METODO_NAO_VINCULADO,
    SCORE_CPF, SCORE_EMAIL, SCORE_CPF_PARCIAL_NOME, SCORE_NOME, SCORE_FUZZY,
    normalizar_cpf, normalizar_nome, normalizar_email, extrair_cpf_parcial,
    construir_universo,
)


def _f(matricula, cpf="", email="", nome=""):
    return FuncionarioRef(
        matricula=matricula,
        cpf=normalizar_cpf(cpf),
        email=normalizar_email(email),
        nome=normalizar_nome(nome),
    )


class TestNormalizacao(unittest.TestCase):
    def test_normalizar_cpf_formatado(self):
        self.assertEqual(normalizar_cpf("123.456.789-00"), "12345678900")

    def test_normalizar_cpf_so_digitos(self):
        self.assertEqual(normalizar_cpf("12345678900"), "12345678900")

    def test_normalizar_cpf_com_zero_a_esquerda_faltando(self):
        # 10 digitos -> 11 com zfill
        self.assertEqual(normalizar_cpf("1234567890"), "01234567890")

    def test_normalizar_cpf_vazio(self):
        self.assertEqual(normalizar_cpf(""), "")
        self.assertEqual(normalizar_cpf(None), "")

    def test_extrair_cpf_parcial_mascarado(self):
        # SICA_RA real: '39328XXX'
        self.assertEqual(extrair_cpf_parcial("39328XXX"), "39328")

    def test_extrair_cpf_parcial_muito_curto_retorna_vazio(self):
        # Menos que 5 digitos contiguos = nao serve
        self.assertEqual(extrair_cpf_parcial("39X"), "")

    def test_normalizar_nome_remove_acento_e_upper(self):
        self.assertEqual(normalizar_nome("João Silva"), "JOAO SILVA")

    def test_normalizar_nome_colapsa_espacos(self):
        self.assertEqual(normalizar_nome("  ANA   MARIA  "), "ANA MARIA")

    def test_normalizar_email_lower_trim(self):
        self.assertEqual(normalizar_email("  Foo@Bar.com  "), "foo@bar.com")

    def test_normalizar_cpf_mascarado_e_preservado(self):
        # SICA_RA real: '39328XXX' nao deve virar '00000039328' (zfill).
        # Preservar o mascaramento permite extrair_cpf_parcial achar '39328'
        # depois, e impede falso match no nivel 1 (CPF exato).
        self.assertEqual(normalizar_cpf("39328XXX"), "39328XXX")
        self.assertEqual(normalizar_cpf("393.28?-??"), "393.28?-??")

    def test_extrair_cpf_parcial_funciona_com_mascarado_preservado(self):
        # Pipeline real: normalizar preserva mascarado, extrair_cpf_parcial
        # devolve os digitos contiguos.
        s = normalizar_cpf("39328XXX")
        self.assertEqual(extrair_cpf_parcial(s), "39328")


class TestCascataMatching(unittest.TestCase):
    """Cada teste exercita um nivel da cascata isoladamente."""

    def setUp(self):
        # Universo: 4 funcionarios bem distintos
        self.funcs = [
            _f("MAT1", cpf="11111111111", email="joao@cvc.com", nome="JOAO SILVA"),
            _f("MAT2", cpf="22222222222", email="maria@cvc.com", nome="MARIA SOUZA"),
            _f("MAT3", cpf="33333333333", email="pedro@cvc.com", nome="PEDRO LIMA"),
            _f("MAT4", cpf="44444444444", email="ana@cvc.com", nome="ANA COSTA"),
        ]
        self.s = ServicoVinculacaoMultiChave(self.funcs)

    # ---- Nivel 1: CPF exato ----
    def test_n1_cpf_exato_unico(self):
        r = self.s.vincular(cpf="11111111111")
        self.assertEqual(r.metodo, METODO_CPF)
        self.assertEqual(r.score, SCORE_CPF)
        self.assertEqual(r.matricula, "MAT1")
        self.assertIsNone(r.candidatos)

    def test_n1_cpf_formatado_funciona(self):
        r = self.s.vincular(cpf="111.111.111-11")
        self.assertEqual(r.matricula, "MAT1")

    def test_n1_cpf_zero_a_esquerda(self):
        # Funcionario tem CPF '00012345678'
        funcs = [_f("X", cpf="00012345678", nome="TESTE")]
        s = ServicoVinculacaoMultiChave(funcs)
        # Acesso veio com '12345678' (zero comido pelo Excel)
        r = s.vincular(cpf="12345678")
        self.assertEqual(r.metodo, METODO_CPF)
        self.assertEqual(r.matricula, "X")

    def test_n1_cpf_invalido_cai_pros_proximos_niveis(self):
        # CPF nao existe -> cai pra email
        r = self.s.vincular(cpf="99999999999", email="joao@cvc.com")
        self.assertEqual(r.metodo, METODO_EMAIL)

    # ---- Nivel 2: Email exato ----
    def test_n2_email_exato(self):
        r = self.s.vincular(email="MARIA@cvc.com")  # case insensitive
        self.assertEqual(r.metodo, METODO_EMAIL)
        self.assertEqual(r.score, SCORE_EMAIL)
        self.assertEqual(r.matricula, "MAT2")

    def test_n2_email_nao_encontrado_cai_pros_proximos(self):
        r = self.s.vincular(email="ninguem@x.com", nome="JOAO SILVA")
        self.assertEqual(r.metodo, METODO_NOME)

    # ---- Nivel 3: CPF parcial + nome ----
    def test_n3_cpf_parcial_mais_nome(self):
        # SICA_RA tipico: cpf vem mascarado, mas tem os 5 primeiros
        # MAT1 tem cpf '11111111111' (5 primeiros = '11111')
        r = self.s.vincular(cpf_mascarado="11111XXX", nome="JOAO SILVA")
        self.assertEqual(r.metodo, METODO_CPF_PARCIAL_NOME)
        self.assertEqual(r.score, SCORE_CPF_PARCIAL_NOME)
        self.assertEqual(r.matricula, "MAT1")

    def test_n3_pipeline_real_cpf_mascarado_preservado(self):
        # Cenario real do SICA_RA: vincular_multi_chave passa o CPF como veio
        # do banco (preservado mascarado). Cascata deve pular nivel 1
        # (len != 11), pular nivel 2 (sem email) e cair em nivel 3.
        r = self.s.vincular(cpf="11111XXX", cpf_mascarado="11111XXX",
                            nome="JOAO SILVA")
        self.assertEqual(r.metodo, METODO_CPF_PARCIAL_NOME)
        self.assertEqual(r.matricula, "MAT1")

    def test_n3_cpf_parcial_sem_nome_nao_resolve(self):
        # Sem nome, parcial sozinho nao vincula
        r = self.s.vincular(cpf_mascarado="11111XXX")
        self.assertEqual(r.metodo, METODO_NAO_VINCULADO)

    # ---- Nivel 4: Nome exato ----
    def test_n4_nome_exato_unico(self):
        r = self.s.vincular(nome="JOAO SILVA")
        self.assertEqual(r.metodo, METODO_NOME)
        self.assertEqual(r.score, SCORE_NOME)
        self.assertEqual(r.matricula, "MAT1")

    def test_n4_nome_ambiguo_lista_candidatos(self):
        # 2 funcionarios com o mesmo nome — comum (JOAO SILVA)
        funcs = [
            _f("MAT1", nome="JOAO SILVA"),
            _f("MAT99", nome="JOAO SILVA"),
        ]
        s = ServicoVinculacaoMultiChave(funcs)
        r = s.vincular(nome="JOAO SILVA")
        self.assertEqual(r.metodo, METODO_NOME)
        self.assertIsNotNone(r.candidatos)
        self.assertEqual(set(r.candidatos), {"MAT1", "MAT99"})

    def test_n4_nome_com_acento_e_caso_diferentes(self):
        r = self.s.vincular(nome="João silva")  # acentuacao + lower
        self.assertEqual(r.metodo, METODO_NOME)
        self.assertEqual(r.matricula, "MAT1")

    # ---- Nivel 5: Fuzzy ----
    def test_n5_fuzzy_nao_vincula_mas_devolve_candidato(self):
        # 1 letra de diferenca
        r = self.s.vincular(nome="JOAO SILVAA")
        self.assertEqual(r.metodo, METODO_FUZZY)
        self.assertEqual(r.score, SCORE_FUZZY)
        self.assertIsNone(r.matricula)  # fuzzy NAO vincula
        self.assertIn("MAT1", r.candidatos)

    def test_n5_fuzzy_abaixo_threshold_cai_nao_vinculado(self):
        # Nome muito diferente
        r = self.s.vincular(nome="XAVIER XAVERO")
        self.assertEqual(r.metodo, METODO_NAO_VINCULADO)
        self.assertEqual(r.score, 0.0)
        self.assertIsNone(r.matricula)

    # ---- Casos vazios / borda ----
    def test_nada_informado_nao_vincula(self):
        r = self.s.vincular()
        self.assertEqual(r.metodo, METODO_NAO_VINCULADO)

    def test_ordem_da_cascata_cpf_vence_email(self):
        # Quando CPF e email apontam para matriculas diferentes (cenario
        # absurdo, mas garantia de ordem)
        funcs = [
            _f("MAT_X", cpf="55555555555", email=""),
            _f("MAT_Y", cpf="",            email="conflito@cvc.com"),
        ]
        s = ServicoVinculacaoMultiChave(funcs)
        r = s.vincular(cpf="55555555555", email="conflito@cvc.com")
        self.assertEqual(r.metodo, METODO_CPF)
        self.assertEqual(r.matricula, "MAT_X")


class TestConstruirUniverso(unittest.TestCase):
    def test_constroi_a_partir_de_objetos_brutos(self):
        from types import SimpleNamespace
        objs = [
            SimpleNamespace(matricula="M1", cpf="111.111.111-11",
                            email="A@X.com", nome="João"),
            SimpleNamespace(matricula="M2", cpf="22222222222",
                            email=None, nome=None),
        ]
        u = construir_universo(objs)
        self.assertEqual(len(u), 2)
        self.assertEqual(u[0].cpf, "11111111111")
        self.assertEqual(u[0].email, "a@x.com")
        self.assertEqual(u[0].nome, "JOAO")
        self.assertEqual(u[1].cpf, "22222222222")
        self.assertEqual(u[1].email, "")
        self.assertEqual(u[1].nome, "")


if __name__ == "__main__":
    unittest.main()
