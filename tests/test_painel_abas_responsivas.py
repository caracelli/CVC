# -*- coding: utf-8 -*-
"""As abas do painel nao podem exigir uma tela larga.

Retorno da area (27/08/2026): "os botoes das abas acabaram encavalando pela
questao de serem largos e nao caberem na tela do usuario".

Causa: `.tab` tinha `flex:0 0 auto` (proibido encolher) + `min-width:172px`.
Com 8 abas isso exigia ~1422px de largura MINIMA — medido no Edge headless.
Abaixo disso a barra transbordava, e como `.nav` nao tratava overflow as abas
saiam por cima do resto.

Correcao: `flex:1 1 auto` (crescem na tela larga, encolhem na estreita) +
`min-width:max-content` (o piso e' o PROPRIO rotulo, entao o texto nunca corta)
+ `max-width:172px` (na tela larga fica identico ao de antes) e `overflow-x:auto`
na `.nav` como ultimo recurso.

Medido no Edge headless depois da correcao, sem encavalamento, sem rotulo
cortado e sem rolagem em nenhuma delas:

    1920..1440px -> abas 172px (igual ao de antes)
    1366px       -> 151..171px
    1280px       -> 140..161px
    1100px       -> 118..138px
    1024px       -> 108..129px
     900px       ->  93..113px
     800px       ->  80..101px

Este teste NAO renderiza (seria lento e dependeria de navegador na maquina de
CI): ele fixa o CONTRATO do CSS. O que ele impede e' alguem devolver a largura
fixa sem perceber.
"""
import re
import unittest
from pathlib import Path

INDEX = (Path(__file__).resolve().parent.parent
         / "CVC_IAM_ANALYTICS" / "EXECUTAVEIS" / "REPORT" / "index.html")


def _regra(seletor):
    """Corpo da primeira regra CSS do seletor (ex.: '.tab')."""
    html = INDEX.read_text(encoding="utf-8")
    m = re.search(re.escape(seletor) + r"\{(.*?)\}", html, re.S)
    assert m, f"regra {seletor} nao encontrada"
    # tira comentarios: o contrato e' o que o navegador le, nao o que documenta
    return re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.S)


class AbasCabemNaTela(unittest.TestCase):

    def test_aba_pode_encolher(self):
        css = _regra(".tab")
        self.assertNotIn("flex:0 0 auto", css.replace(" ", ""),
                         "flex:0 0 auto proibe encolher — foi o que causou o encavalamento")
        self.assertRegex(css.replace(" ", ""), r"flex:1 ?1 ?auto".replace(" ", ""),
                         "a aba precisa poder crescer E encolher")

    def test_piso_e_o_proprio_rotulo(self):
        """min-width fixo em px volta a exigir tela larga; max-content nao."""
        css = _regra(".tab").replace(" ", "")
        self.assertIn("min-width:max-content", css)
        self.assertNotRegex(css, r"min-width:\d+px",
                            "min-width em px reintroduz a largura minima da barra")

    def test_teto_preserva_o_visual_em_tela_larga(self):
        self.assertIn("max-width:172px", _regra(".tab").replace(" ", ""))

    def test_rotulo_nao_quebra_linha(self):
        self.assertIn("white-space:nowrap", _regra(".tab").replace(" ", ""))

    def test_nav_rola_em_vez_de_transbordar(self):
        """Ultimo recurso: se nem os rotulos couberem, rola — nao encavalha."""
        self.assertIn("overflow-x:auto", _regra(".nav").replace(" ", ""))

    def test_as_8_abas_continuam_la(self):
        """Guarda contra o teste passar num painel que perdeu abas."""
        html = INDEX.read_text(encoding="utf-8")
        abas = re.findall(r'<div class="tab[^"]*"\s+data-tab="([^"]+)"', html)
        self.assertEqual(len(abas), 8, abas)


if __name__ == "__main__":
    unittest.main()
