# -*- coding: utf-8 -*-
"""ServicoPadronizacao — bordas: CPF mascarado/CNPJ, situacao variantes,
matricula e nome em casos limite."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dominio.servicos_dominio.servico_padronizacao import ServicoPadronizacao as P


class TestCpf(unittest.TestCase):
    def test_formatado_e_digitos(self):
        self.assertEqual(P.normalizar_cpf("123.456.789-00"), "12345678900")
        self.assertEqual(P.normalizar_cpf("12345678900"), "12345678900")

    def test_zfill_para_11(self):
        self.assertEqual(P.normalizar_cpf("1234567890"), "01234567890")
        self.assertEqual(P.normalizar_cpf("42949637"), "00042949637")

    def test_mascarado_e_preservado(self):
        # presenca de X/?/*/# preserva o original (cascata extrai parcial depois)
        for m in ("39328XXX", "393.28?-??", "1234*", "999#"):
            self.assertEqual(P.normalizar_cpf(m), m.upper())

    def test_cnpj_14_digitos_nao_e_truncado(self):
        # zfill nunca trunca: 14 digitos continuam 14
        self.assertEqual(P.normalizar_cpf("10.760.260/0001-19"), "10760260000119")

    def test_vazio_none(self):
        self.assertEqual(P.normalizar_cpf(""), "")
        self.assertEqual(P.normalizar_cpf(None), "")
        self.assertEqual(P.normalizar_cpf("   "), "")


class TestSituacao(unittest.TestCase):
    def test_ativos(self):
        for v in ("A", "ATIVO", "ativo", "Atividade Normal", "ATIVIDADE NORMAL"):
            self.assertEqual(P.normalizar_situacao(v), "ATIVO", v)

    def test_desligado_com_e_sem_acento(self):
        self.assertEqual(P.normalizar_situacao("RESCISÃO"), "DESLIGADO")
        self.assertEqual(P.normalizar_situacao("rescisao"), "DESLIGADO")

    def test_inativo_e_bloqueado(self):
        self.assertEqual(P.normalizar_situacao("I"), "INATIVO")
        self.assertEqual(P.normalizar_situacao("B"), "BLOQUEADO")

    def test_desconhecido_passa_em_maiusculo(self):
        self.assertEqual(P.normalizar_situacao("afastado"), "AFASTADO")

    def test_vazio_none(self):
        self.assertEqual(P.normalizar_situacao(""), "")
        self.assertEqual(P.normalizar_situacao(None), "")


class TestMatricula(unittest.TestCase):
    def test_remove_zeros_a_esquerda(self):
        self.assertEqual(P.normalizar_matricula("00123"), "123")

    def test_zero_puro_vira_zero(self):
        self.assertEqual(P.normalizar_matricula("0"), "0")
        self.assertEqual(P.normalizar_matricula("000"), "0")

    def test_trim(self):
        self.assertEqual(P.normalizar_matricula(" 45 "), "45")

    def test_vazio_none(self):
        self.assertEqual(P.normalizar_matricula(""), "")
        self.assertEqual(P.normalizar_matricula(None), "")


class TestNome(unittest.TestCase):
    def test_upper_e_colapsa_espacos_mantendo_acento(self):
        self.assertEqual(P.normalizar_nome("  joão   silva  "), "JOÃO SILVA")

    def test_tabs_e_quebras(self):
        self.assertEqual(P.normalizar_nome("ana\tmaria"), "ANA MARIA")

    def test_vazio_none(self):
        self.assertEqual(P.normalizar_nome(""), "")
        self.assertEqual(P.normalizar_nome(None), "")
        self.assertEqual(P.normalizar_nome("   "), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
