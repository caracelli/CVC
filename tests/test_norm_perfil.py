# -*- coding: utf-8 -*-
"""Testes profundos da normalizacao de perfil usada na APROXIMACAO do IC.

_norm_perfil casa nomes de perfil que diferem so por underscore/espaco/acento/
caixa/espacos repetidos — a regra que faz 'IC_CONSULTA' (extrato) == 'IC
CONSULTA' (matriz). E confere que a aproximacao e' ESCOPADA so ao IC.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from aplicacao.casos_de_uso.validar_acessos_sistema import (
    _norm, _norm_perfil, _SISTEMAS_PERFIL_APROXIMADO,
)
from dominio.objetos_valor.sistema import Sistema


class TestNormPerfil(unittest.TestCase):

    def test_underscore_vira_espaco(self):
        self.assertEqual(_norm_perfil("IC_CONSULTA"), "IC CONSULTA")

    def test_caixa_alta(self):
        self.assertEqual(_norm_perfil("ic consulta"), "IC CONSULTA")

    def test_trim_e_espacos_repetidos_colapsados(self):
        self.assertEqual(_norm_perfil("  IC   CONSULTA  "), "IC CONSULTA")

    def test_underscores_repetidos_colapsam(self):
        self.assertEqual(_norm_perfil("IC__CONSULTA"), "IC CONSULTA")

    def test_remove_acentos(self):
        self.assertEqual(_norm_perfil("IC CONSULTAÇÃO"), "IC CONSULTACAO")

    def test_misto_underscore_espaco_acento_caixa(self):
        self.assertEqual(_norm_perfil(" Ic_Aprovação "), "IC APROVACAO")

    def test_none_e_vazio(self):
        self.assertEqual(_norm_perfil(None), "")
        self.assertEqual(_norm_perfil(""), "")
        self.assertEqual(_norm_perfil("   "), "")

    # ---- equivalencias e nao-equivalencias (o que faz/quebra a aproximacao) ----
    def test_equivalencias_dos_4_perfis_reais_do_ic(self):
        pares = [
            ("IC_CONSULTA",      "IC CONSULTA"),
            ("IC_CADASTRO",      "IC CADASTRO"),
            ("IC_CADASTRO",      "IC_CADASTRO"),     # inconsistencia interna da matriz
            ("IC_CONTROLADORIA", "IC CONTROLADORIA"),
            ("IC_APROVADOR",     "IC APROVADOR"),
        ]
        for extrato, matriz in pares:
            self.assertEqual(_norm_perfil(extrato), _norm_perfil(matriz),
                             f"{extrato!r} deveria casar {matriz!r}")

    def test_perfis_realmente_diferentes_nao_casam(self):
        self.assertNotEqual(_norm_perfil("IC CONSULTA"), _norm_perfil("IC APROVADOR"))
        self.assertNotEqual(_norm_perfil("IC CADASTRO"), _norm_perfil("IC CONTROLADORIA"))

    def test_norm_base_nao_troca_underscore(self):
        # _norm (usado p/ cargo) NAO troca '_' por espaco — so _norm_perfil faz isso
        self.assertEqual(_norm("A_B"), "A_B")
        self.assertEqual(_norm_perfil("A_B"), "A B")


class TestEscopoAproximacao(unittest.TestCase):
    def test_so_o_ic_usa_aproximacao(self):
        self.assertIn(Sistema.IC_INTEGRADOR_CONTABIL.value, _SISTEMAS_PERFIL_APROXIMADO)

    def test_systur_nao_esta_no_escopo_de_aproximacao(self):
        self.assertNotIn(Sistema.SYSTUR.value, _SISTEMAS_PERFIL_APROXIMADO)

    def test_demais_sistemas_fora_da_aproximacao(self):
        for s in (Sistema.SIGOT, Sistema.SICA_RA, Sistema.SICA_ESFERA, Sistema.SIG):
            self.assertNotIn(s.value, _SISTEMAS_PERFIL_APROXIMADO)


if __name__ == "__main__":
    unittest.main(verbosity=2)
