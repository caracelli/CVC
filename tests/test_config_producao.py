# -*- coding: utf-8 -*-
"""Regressao das DECISOES da entrega gravadas no config.xml de producao.

Pina o estado do CVC_IAM_ANALYTICS/EXECUTAVEIS/CONFIG/config.xml: versao 1.3.3,
SYSTUR ativo (IC e demais inativos), desligados/terceiros fora de escopo,
painel multi-sistema (visualizador/sistema vazio). Se alguem mexer nesses
flags sem querer, este teste acende.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.configuracao.leitor_config import LeitorConfig

CONFIG = (Path(__file__).resolve().parent.parent
          / "CVC_IAM_ANALYTICS" / "EXECUTAVEIS" / "CONFIG" / "config.xml")


class TestConfigProducao(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cfg = LeitorConfig(str(CONFIG)).carregar()

    def test_versao_1_3_4(self):
        self.assertEqual(self.cfg.versao, "1.3.4")

    def test_systur_ativo_ic_temporariamente_off(self):
        # SYSTUR ativo. IC DESATIVADO temporariamente (estava atrapalhando a
        # validacao do SYSTUR) — reativar com <ativo>true</ativo> no bloco IC.
        self.assertTrue(self.cfg.sistemas["SYSTUR"].ativo)
        self.assertFalse(self.cfg.sistemas["IC"].ativo)

    def test_demais_sistemas_inativos(self):
        for sid in ("SIGOT", "SICA_RA", "SICA_ESFERA", "SIG", "ORACLE_EBS"):
            self.assertFalse(self.cfg.sistemas[sid].ativo, f"{sid} deveria estar inativo")

    def test_desligados_e_terceiros_fora_de_escopo(self):
        self.assertFalse(self.cfg.rh_processar_desligados)
        self.assertFalse(self.cfg.rh_processar_terceiros)

    def test_painel_multi_sistema(self):
        # visualizador/sistema vazio = todos os sistemas ativos (SYSTUR + IC)
        self.assertEqual(self.cfg.visualizador_sistema, "")

    def test_quarentena_90_dias(self):
        self.assertEqual(self.cfg.visualizador_quarentena_dias, 90)


if __name__ == "__main__":
    unittest.main(verbosity=2)
