# -*- coding: utf-8 -*-
"""A linha de acesso tem de ser DUAS COLUNAS, nao texto colado na borda direita.

Retorno da area em 28/08/2026 (Teams, com print marcado de vermelho):
  "porque aqui a visao aparentemente esta desalinhada"
  "porque hoje ta com a impressao de coisas 'soltas'"
  "tipo criar dois quadrados esperados e eles estarem juntos, esperados no
   esperados"

A causa era CSS, nao dado: `.cs-acc-p` usava
`display:flex; justify-content:space-between`, entao a badge do sistema ia para
a esquerda e o VALOR era empurrado ate a borda DIREITA. Como cada valor tem
largura diferente, cada linha comecava num x diferente — nada alinhava
verticalmente, e era exatamente isso que os dois quadrados dela circulavam.

MEDIDO no Edge headless, mesma pessoa (matricula 34532032), antes e depois:
  antes  — 4 linhas comecando em x = 1407, 807, 1365, 1381 (amplitude 600px)
  depois — 7 linhas, TODAS em x = 961 (amplitude 0)

A badge mais larga dos 7 sistemas e' IC_INTEGRADOR_CONTABIL, medida em 162px;
a coluna e' fixa em 172px. Fixa e NAO `max-content` porque cada linha e' um
grid proprio — so' largura igual em todas faz as colunas baterem entre linhas.
"""
import re
import unittest
from pathlib import Path

INDEX = (Path(__file__).resolve().parent.parent
         / "CVC_IAM_ANALYTICS" / "EXECUTAVEIS" / "REPORT" / "index.html")

LINHAS = (".cs-sub-acc-p", ".cs-drawer-bd .cs-acc-p")


def _regra(sel):
    html = INDEX.read_text(encoding="utf-8")
    i = html.index(sel + "{font:500 11.5px")
    return html[i:html.index("}", i) + 1]


class LinhaDeAcessoEmDuasColunas(unittest.TestCase):

    def test_nao_usa_mais_space_between(self):
        """A causa exata do 'solto'. Se voltar, o valor volta a colar na direita."""
        for sel in LINHAS:
            self.assertNotIn("justify-content:space-between", _regra(sel), sel)

    def test_e_grid_de_duas_colunas(self):
        for sel in LINHAS:
            r = _regra(sel)
            self.assertIn("display:grid", r, sel)
            self.assertIn("grid-template-columns:172px", r,
                          f"{sel}: a coluna do sistema tem de ser FIXA — "
                          "max-content nao alinha entre linhas")

    def test_coluna_cabe_no_maior_sistema(self):
        """IC_INTEGRADOR_CONTABIL mede 162px; abaixo disso a badge transborda."""
        for sel in LINHAS:
            larg = int(re.search(r"grid-template-columns:(\d+)px",
                                 _regra(sel)).group(1))
            self.assertGreaterEqual(larg, 162, sel)

    def test_valor_vem_num_elemento_so(self):
        """No grid, cada no solto viraria uma celula propria e a coluna
        quebraria. O valor precisa estar dentro de UM span."""
        html = INDEX.read_text(encoding="utf-8")
        i = html.index("function _csDetalheCategorias(")
        corpo = html[i:i + 3000]
        self.assertIn('-v">', corpo,
                      "o valor voltou a ser texto solto dentro da linha")

    def test_sem_mapeamento_segue_o_mesmo_molde(self):
        """Usa a MESMA classe de linha; sem o invólucro ficaria desalinhado
        justamente no bloco que responde 'por que ela nao tem o IC?'."""
        html = INDEX.read_text(encoding="utf-8")
        i = html.index("function _csSemMapeamento(")
        corpo = html[i:i + 900]
        self.assertIn("cs-sub-acc-p", corpo)
        self.assertIn("cs-sub-acc-v", corpo)


class VolumePorSistema(unittest.TestCase):
    """O teto de `_csListaPerfis` age DENTRO de uma linha. O estouro aqui vem de
    outro lado: um sistema com dezenas de LINHAS (uma por perfil esperado).
    Caso real: ORACLE_EBS com "Acessos esperados (51)" — 51 perfis em texto
    corrido. Depois do teto: 6 + "+43 outros", drawer inteiro em 610px."""

    def test_ha_teto_por_sistema(self):
        html = INDEX.read_text(encoding="utf-8")
        i = html.index("function _csDetalheCategorias(")
        corpo = html[i:i + 3000]
        self.assertIn("_TETO_SIS", corpo)
        self.assertIn("outros</span>", corpo)

    def test_o_resto_nao_se_perde(self):
        """Cortar sem guardar seria esconder dado da auditoria — o excedente
        tem de continuar acessivel no title."""
        html = INDEX.read_text(encoding="utf-8")
        i = html.index("function _csDetalheCategorias(")
        corpo = html[i:i + 3000]
        self.assertIn("title=", corpo)
        self.assertIn("_resto", corpo)


if __name__ == "__main__":
    unittest.main()
