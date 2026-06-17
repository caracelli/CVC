# -*- coding: utf-8 -*-
"""Regressao das DECISOES da entrega gravadas no config.xml de producao.

Pina o estado do CVC_IAM_ANALYTICS/EXECUTAVEIS/CONFIG/config.xml: versao 1.2.0,
entrega multi-sistema ate Oracle EBS (SYSTUR+IC+SICA_RA+SIGOT+ORACLE_EBS ativos;
SICA_ESFERA/SIG/OPERA inativos), desligados/terceiros fora de escopo, painel
multi-sistema (visualizador/sistema vazio). Se alguem mexer nesses flags sem
querer, este teste acende.
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

    def test_versao_1_2_0(self):
        self.assertEqual(self.cfg.versao, "1.2.0")

    def test_sistemas_ate_oracle_ativos(self):
        # Entrega multi-sistema ate Oracle EBS (Cards 6-11).
        for sid in ("SYSTUR", "IC", "SICA_RA", "SIGOT", "ORACLE_EBS"):
            self.assertTrue(self.cfg.sistemas[sid].ativo, f"{sid} deveria estar ativo")

    def test_demais_sistemas_inativos(self):
        # Fora do escopo desta entrega (entram nas proximas fases).
        for sid in ("SICA_ESFERA", "SIG", "OPERA_OPERACIONAL"):
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
