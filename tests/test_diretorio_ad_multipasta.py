# -*- coding: utf-8 -*-
"""Diretorio AD em VARIAS pastas (mudanca de layout do cliente, 05/08/2026).

Ate 03/08 os tres exports vinham numa pasta unica (ENTRADA/RH/AD). Na entrega
de 05/08 o cliente passou a separar por populacao —
ENTRADA/SISTEMAS/AD_FRANQUEADOS, AD_PRESTADORES, AD_DESLIGADOS — cada uma com
subpasta por mes (07-2026, 08-2026), e os nomes vieram em minusculo e por
extenso (`ou_franqueados_...` em vez de `OU_Franq...`).

Com o config apontando so para a pasta antiga, o Processador registraria
"Diretorio AD: 0 identidades" — e sem o AD os orfaos voltam de 1,3% para 17%.
"""
import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from aplicacao.casos_de_uso.importar_diretorio_ad import _populacao
from infraestrutura.configuracao.leitor_config import LeitorConfig

CONFIG_REAL = (Path(__file__).resolve().parent.parent
               / "CVC_IAM_ANALYTICS" / "EXECUTAVEIS" / "CONFIG" / "config.xml")


class TestRoteamentoPeloNome(unittest.TestCase):
    """O nome e' que classifica — a pasta nao. Nomes NOVOS e ANTIGOS."""

    def test_nomes_novos_do_cliente(self):
        self.assertEqual(_populacao("ou_franqueados_29_07_2026_15-09.csv"), "FRANQUEADO")
        self.assertEqual(_populacao("ou_prestadores_03_08_2026_16-50.csv"), "PRESTADOR")
        self.assertEqual(_populacao("ou_desligados_29_07_2026_17-10.csv"), "DESLIGADOS")

    def test_nomes_antigos_continuam(self):
        self.assertEqual(_populacao("OU_Franq_Bruna.csv"), "FRANQUEADO")
        self.assertEqual(_populacao("OU_Prest_Bruna.csv"), "PRESTADOR")
        self.assertEqual(_populacao("OU_Desligados_Bruna.csv"), "DESLIGADOS")

    def test_arquivo_alheio_nao_e_classificado(self):
        # se a pasta apontada tiver outra coisa, nao pode virar identidade
        self.assertIsNone(_populacao("relatorio systur 30.04.xlsx"))
        self.assertIsNone(_populacao("PROJETOIAM.CSV"))


class TestConfigVariosCaminhos(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_admulti_")

    def _cfg(self, bloco_ad):
        p = os.path.join(self._tmp, "config.xml")
        with open(p, "w", encoding="utf-8") as f:
            f.write("<configuracao><versao>1.0.0</versao><rh>"
                    + bloco_ad +
                    "</rh><processamento/></configuracao>")
        return LeitorConfig(p).carregar()

    def test_varios_caminhos(self):
        cfg = self._cfg("<diretorio_ad><processar>true</processar>"
                        "<caminho>A</caminho><caminho>B</caminho><caminho>C</caminho>"
                        "</diretorio_ad>")
        self.assertEqual(cfg.rh_diretorio_ad_caminhos, ["A", "B", "C"])
        self.assertEqual(cfg.rh_diretorio_ad_caminho, "A", "compatibilidade: o 1o")

    def test_um_caminho_so_continua_valendo(self):
        cfg = self._cfg("<diretorio_ad><processar>true</processar>"
                        "<caminho>ENTRADA/RH/AD</caminho></diretorio_ad>")
        self.assertEqual(cfg.rh_diretorio_ad_caminhos, ["ENTRADA/RH/AD"])

    def test_sem_o_bloco_usa_o_padrao(self):
        cfg = self._cfg("")
        self.assertEqual(cfg.rh_diretorio_ad_caminhos, ["ENTRADA/RH/AD"])

    def test_caminho_vazio_nao_vira_raiz_do_app(self):
        # <caminho/> solto resolveria para a raiz e varreria o app inteiro
        cfg = self._cfg("<diretorio_ad><processar>true</processar>"
                        "<caminho></caminho><caminho>ENTRADA/RH/AD</caminho>"
                        "</diretorio_ad>")
        self.assertEqual(cfg.rh_diretorio_ad_caminhos, ["ENTRADA/RH/AD"])

    def test_espacos_sao_aparados(self):
        cfg = self._cfg("<diretorio_ad><caminho>  ENTRADA/RH/AD  </caminho></diretorio_ad>")
        self.assertEqual(cfg.rh_diretorio_ad_caminhos, ["ENTRADA/RH/AD"])


class TestConfigDeProducao(unittest.TestCase):
    """Trava o layout que o cliente passou a usar em 05/08/2026."""

    def setUp(self):
        self.cfg = LeitorConfig(str(CONFIG_REAL)).carregar()

    def test_as_tres_pastas_de_populacao_estao_no_config(self):
        caminhos = [c.upper() for c in self.cfg.rh_diretorio_ad_caminhos]
        for pasta in ("ENTRADA/SISTEMAS/AD_FRANQUEADOS",
                      "ENTRADA/SISTEMAS/AD_PRESTADORES",
                      "ENTRADA/SISTEMAS/AD_DESLIGADOS"):
            self.assertIn(pasta, caminhos, f"{pasta} fora do config")

    def test_pasta_antiga_preservada(self):
        # bases ja existentes seguem funcionando
        self.assertIn("ENTRADA/RH/AD", self.cfg.rh_diretorio_ad_caminhos)

    def test_ad_continua_ligado(self):
        self.assertTrue(self.cfg.rh_processar_diretorio_ad)

    def test_nenhum_caminho_aponta_para_a_raiz_de_sistemas(self):
        # ENTRADA/SISTEMAS inteiro faria o AD varrer SYSTUR/IC/SIG/Oracle
        for c in self.cfg.rh_diretorio_ad_caminhos:
            self.assertNotEqual(c.strip().upper().rstrip("/"), "ENTRADA/SISTEMAS")


if __name__ == "__main__":
    unittest.main(verbosity=2)
