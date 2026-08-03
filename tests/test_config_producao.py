# -*- coding: utf-8 -*-
"""Regressao das DECISOES da entrega gravadas no config.xml de producao.

Pina o estado do CVC_IAM_ANALYTICS/EXECUTAVEIS/CONFIG/config.xml: versao 1.0.0,
os 7 sistemas da Fase 1 ativos (OPERA fora de escopo), terceiros e desligados EM
escopo, painel multi-sistema (visualizador/sistema vazio). Se alguem mexer nesses
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

    def test_versao_1_0_0(self):
        # RESET da numeracao para a entrega da Fase 1 (03/08/2026), como ja
        # tinha sido feito em 08/06 na 1a entrega oficial. O pacote local da
        # Bruna (build_entrega_bruna.py) carrega a MESMA versao.
        self.assertEqual(self.cfg.versao, "1.0.0")

    def test_todos_os_sistemas_da_fase1_ativos(self):
        # Fase 1 completa p/ homologacao: os 7 sistemas em escopo (Cards 6-13).
        for sid in ("SYSTUR", "IC", "SICA_RA", "SIGOT", "ORACLE_EBS", "SIG", "SICA_ESFERA"):
            self.assertTrue(self.cfg.sistemas[sid].ativo, f"{sid} deveria estar ativo")

    def test_opera_fora_de_escopo(self):
        # OPERA_OPERACIONAL nao esta no cronograma -> fora de escopo (inativo).
        self.assertFalse(self.cfg.sistemas["OPERA_OPERACIONAL"].ativo)

    def test_terceiros_e_desligados_em_escopo(self):
        # Terceiros ENTRARAM na Fase 1 (espelho). Desligados: motor ATIVADO
        # (Card 19) — processa a pasta e gera as divergencias ACESSO_DESLIGADO.
        self.assertTrue(self.cfg.rh_processar_terceiros)
        self.assertTrue(self.cfg.rh_processar_desligados)

    def test_painel_multi_sistema(self):
        # visualizador/sistema vazio = todos os sistemas ativos (SYSTUR + IC)
        self.assertEqual(self.cfg.visualizador_sistema, "")

    def test_quarentena_90_dias(self):
        self.assertEqual(self.cfg.visualizador_quarentena_dias, 90)


if __name__ == "__main__":
    unittest.main(verbosity=2)
