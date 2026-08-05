# -*- coding: utf-8 -*-
"""Memoizacao da cascata de vinculacao — otimizacao que NAO pode mudar nada.

Medido na base real (05/08/2026): a vinculacao era 68% do tempo de execucao do
Processador (81s de 145s). Nao havia varredura — os indices ja eram O(1). O
custo era REPETICAO: 92.794 acessos para apenas 12.170 chaves distintas (87%
de trabalho repetido), porque o SIG e' matricial e a mesma pessoa aparece numa
linha por perfil — ate 141 vezes com a mesma entrada.

Como a cascata e' funcao PURA das chaves de entrada mais o indice (imutavel
apos o __init__), memorizar por entrada e' equivalente. Resultado medido:
73,1s -> 5,4s (13,6x), IDENTICO nos 92.794 acessos.

Estes testes travam as duas coisas que importam: o resultado nao muda, e cada
chamada recebe um objeto proprio.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dominio.servicos_dominio.servico_vinculacao_multi_chave import (
    METODO_CPF, METODO_EMAIL, METODO_LOGIN, METODO_NAO_VINCULADO, METODO_NOME,
    FuncionarioRef, ServicoVinculacaoMultiChave)

UNIVERSO = [
    FuncionarioRef(matricula="1", cpf="11122233344", email="ana@cvc.com.br",
                   nome="ANA MARIA SOUZA"),
    FuncionarioRef(matricula="2", cpf="55566677788", email="bruno@cvc.com.br",
                   nome="BRUNO LIMA"),
    FuncionarioRef(matricula="FRANQ-XPTO01", nome="CARLA DIAS", login="XPTO01"),
    # homonimo: forca o caminho de ambiguidade (candidatos)
    FuncionarioRef(matricula="3", cpf="99988877766", nome="BRUNO LIMA"),
]

CASOS = [
    dict(cpf="11122233344", email="", nome="", cpf_mascarado="", login=""),
    dict(cpf="", email="ana@cvc.com.br", nome="", cpf_mascarado="", login=""),
    dict(cpf="", email="", nome="", cpf_mascarado="", login="xpto01"),
    dict(cpf="", email="", nome="BRUNO LIMA", cpf_mascarado="", login=""),
    dict(cpf="", email="", nome="ANA MARIA SOUZA", cpf_mascarado="", login=""),
    dict(cpf="", email="", nome="ANA MARIA SOUSA", cpf_mascarado="", login=""),  # fuzzy
    dict(cpf="", email="", nome="ZZZ INEXISTENTE", cpf_mascarado="", login=""),
    dict(cpf="", email="", nome="", cpf_mascarado="", login=""),
]


def _campos(r):
    return (r.metodo, r.score, r.matricula, tuple(r.candidatos or ()))


class TestMemoriaNaoMudaResultado(unittest.TestCase):

    def setUp(self):
        self.s = ServicoVinculacaoMultiChave(UNIVERSO)

    def test_memoria_bate_com_a_cascata_crua(self):
        for caso in CASOS:
            com = _campos(self.s.vincular(**caso))
            sem = _campos(self.s._resolver(caso["cpf"], caso["email"], caso["nome"],
                                           caso["cpf_mascarado"], caso["login"]))
            self.assertEqual(com, sem, f"divergiu em {caso}")

    def test_repetir_da_o_mesmo(self):
        for caso in CASOS:
            primeiro = _campos(self.s.vincular(**caso))
            for _ in range(5):
                self.assertEqual(_campos(self.s.vincular(**caso)), primeiro)

    def test_cascata_continua_correta(self):
        v = self.s.vincular(cpf="11122233344")
        self.assertEqual((v.metodo, v.matricula), (METODO_CPF, "1"))
        v = self.s.vincular(email="ana@cvc.com.br")
        self.assertEqual((v.metodo, v.matricula), (METODO_EMAIL, "1"))
        v = self.s.vincular(login="xpto01")
        self.assertEqual((v.metodo, v.matricula), (METODO_LOGIN, "FRANQ-XPTO01"))
        v = self.s.vincular(nome="ANA MARIA SOUZA")
        self.assertEqual((v.metodo, v.matricula), (METODO_NOME, "1"))
        v = self.s.vincular(nome="ZZZ INEXISTENTE")
        self.assertEqual(v.metodo, METODO_NAO_VINCULADO)

    def test_ambiguidade_preserva_candidatos(self):
        v1 = self.s.vincular(nome="BRUNO LIMA")
        v2 = self.s.vincular(nome="BRUNO LIMA")
        self.assertEqual(v1.candidatos, ["2", "3"])
        self.assertEqual(v1.candidatos, v2.candidatos)


class TestObjetosIndependentes(unittest.TestCase):
    """Cada chamada recebe o SEU objeto: alterar um nao pode afetar outro nem o
    que esta guardado na memoria."""

    def setUp(self):
        self.s = ServicoVinculacaoMultiChave(UNIVERSO)

    def test_alterar_resultado_nao_contamina(self):
        a = self.s.vincular(cpf="11122233344")
        b = self.s.vincular(cpf="11122233344")
        self.assertIsNot(a, b)
        a.matricula = "ALTERADO"
        self.assertEqual(b.matricula, "1")
        self.assertEqual(self.s.vincular(cpf="11122233344").matricula, "1")

    def test_alterar_lista_de_candidatos_nao_contamina(self):
        a = self.s.vincular(nome="BRUNO LIMA")
        a.candidatos.append("INVENTADO")
        self.assertEqual(self.s.vincular(nome="BRUNO LIMA").candidatos, ["2", "3"])


class TestMemoriaDeFato(unittest.TestCase):

    def test_so_guarda_chaves_distintas(self):
        s = ServicoVinculacaoMultiChave(UNIVERSO)
        for _ in range(50):
            s.vincular(cpf="11122233344")
            s.vincular(email="ana@cvc.com.br")
        self.assertEqual(len(s._memo), 2, "deveria guardar 2 chaves, nao 100")

    def test_entradas_diferentes_nao_colidem(self):
        s = ServicoVinculacaoMultiChave(UNIVERSO)
        a = s.vincular(cpf="11122233344")
        b = s.vincular(cpf="55566677788")
        self.assertNotEqual(a.matricula, b.matricula)

    def test_none_e_vazio_sao_a_mesma_chave(self):
        s = ServicoVinculacaoMultiChave(UNIVERSO)
        s.vincular(cpf=None, email=None, nome=None, cpf_mascarado=None, login=None)
        s.vincular(cpf="", email="", nome="", cpf_mascarado="", login="")
        self.assertEqual(len(s._memo), 1)

    def test_memoria_e_por_instancia(self):
        # universo novo (RH mudou) => servico novo => memoria nova
        s1 = ServicoVinculacaoMultiChave(UNIVERSO)
        s1.vincular(cpf="11122233344")
        s2 = ServicoVinculacaoMultiChave(
            [FuncionarioRef(matricula="OUTRA", cpf="11122233344")])
        self.assertEqual(s2.vincular(cpf="11122233344").matricula, "OUTRA")


if __name__ == "__main__":
    unittest.main(verbosity=2)
