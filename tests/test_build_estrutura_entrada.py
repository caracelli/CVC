# -*- coding: utf-8 -*-
"""Todo pacote tem de criar a pasta do de-para do SIG.

O de-para (`ID_x_Perfis_SIG*.xlsx`) traduz o codigo do perfil no nome
(100 -> ATD_HOTEIS_NACIONAIS). Sem a pasta em `ENTRADA/MATRIZES/PERFIS_SISTEMAS/
SIG/DE_PARA`, o cliente nao tem onde deposita-lo — e a tela mostra o codigo cru.

Em 25/08/2026, 3 dos 6 builds nao criavam a pasta, incluindo o de PRODUCAO. Nao
era erro de nenhum deles isoladamente: a lista e' copiada de um build para o
outro, e a pasta entrou so' em alguns. Este teste varre `deploy/` e cobra todos —
inclusive os que forem criados depois.
"""
import re
import unittest
from pathlib import Path

DEPLOY = Path(__file__).resolve().parent.parent / "deploy"
DE_PARA = "MATRIZES/PERFIS_SISTEMAS/SIG/DE_PARA"


def _builds_com_entrada():
    """Scripts de deploy que montam a árvore de ENTRADA."""
    return [p for p in sorted(DEPLOY.glob("build_*.py"))
            if "ENTRADA_SUBDIRS" in p.read_text(encoding="utf-8")]


class PacotesCriamAPastaDoDePara(unittest.TestCase):

    def test_ha_builds_para_conferir(self):
        """Guarda contra o teste virar no-op se a constante for renomeada."""
        self.assertGreaterEqual(len(_builds_com_entrada()), 4)

    def test_todo_build_cria_a_pasta(self):
        faltando = [p.name for p in _builds_com_entrada()
                    if DE_PARA not in p.read_text(encoding="utf-8")]
        self.assertEqual(faltando, [],
                         f"builds sem a pasta do de-para do SIG: {faltando}")

    def test_a_pasta_esta_dentro_da_lista_de_subdirs(self):
        """Estar no arquivo não basta — tem de estar na lista que vira mkdir."""
        for p in _builds_com_entrada():
            txt = p.read_text(encoding="utf-8")
            # o nome varia: build_mockup_systur usa ENTRADA_SUBDIRS_VAZIAS
            listas = re.findall(r"ENTRADA_SUBDIRS\w*\s*=\s*\[(.*?)\]", txt, re.S)
            self.assertTrue(listas, f"{p.name}: ENTRADA_SUBDIRS não é uma lista literal")
            self.assertTrue(any(DE_PARA in l for l in listas),
                            f"{p.name}: a pasta está no arquivo mas fora de ENTRADA_SUBDIRS")


if __name__ == "__main__":
    unittest.main()
