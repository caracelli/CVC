# -*- coding: utf-8 -*-
"""O detalhe da Consulta mora em UM lugar so'.

Retorno da area (28/08/2026, Teams): "acabou ficando muita informacao e esta
complicado tentar agrupar e expandir" / "sera que da para melhorar?".

O mapa deu razao a ela: o MESMO dado de perfil aparecia em TRES lugares —
colunas da grid, expansao da linha e drawer — e os dois ultimos chamavam a
MESMA funcao (`_csDetalheCategorias`). Dois caminhos para o mesmo conteudo era
o que fazia "se perder na divisao".

Agora: a expansao da linha e' um RESUMO de uma linha, e o detalhe completo mora
no drawer. Os 4 blocos por categoria NAO mudaram — foram pedido dela no 1o
retorno (29/07); mudou onde moram.

Medido no Edge headless depois da mudanca:
  expansao -> 67px de altura, texto "ACESSOS  1 nao localizados · 6 sem
              mapeamento   ver detalhe ->"
  clique   -> drawer abre com aba ATIVA = 'acessos' (nao 'ident') e o bloco
              "Sem mapeamento (6)" presente.

⚠️ O `_csSemMapeamento` so' existia na expansao. Mover o detalhe sem leva-lo
junto teria perdido a resposta ao "por que ela nao tem o IC?" (2o retorno,
10/08). O teste abaixo cobra isso.
"""
import re
import unittest
from pathlib import Path

INDEX = (Path(__file__).resolve().parent.parent
         / "CVC_IAM_ANALYTICS" / "EXECUTAVEIS" / "REPORT" / "index.html")


def _corpo(nome):
    html = INDEX.read_text(encoding="utf-8")
    i = html.index(f"function {nome}(")
    j, nivel = html.index("{", i), 0
    for k in range(j, len(html)):
        if html[k] == "{":
            nivel += 1
        elif html[k] == "}":
            nivel -= 1
            if nivel == 0:
                return html[i:k + 1]
    raise AssertionError(f"função {nome} não fecha")


class DetalheMoraEmUmLugar(unittest.TestCase):

    def test_expansao_nao_renderiza_mais_o_detalhe_completo(self):
        """Era a duplicacao: a expansao chamava a mesma funcao do drawer."""
        self.assertNotIn("_csDetalheCategorias", _corpo("_csMontarSub"),
                         "a expansão voltou a duplicar o detalhe do drawer")

    def test_expansao_leva_ao_drawer(self):
        corpo = _corpo("_csMontarSub")
        self.assertIn("csAbrirDrawer", corpo, "o resumo precisa levar ao detalhe")
        self.assertIn("'acessos'", corpo,
                      "abrir em 'ident' faria o usuário clicar duas vezes")

    def test_drawer_e_o_unico_com_o_detalhe(self):
        self.assertIn("_csDetalheCategorias", _corpo("csRenderDrawerBody"))

    def test_sem_mapeamento_veio_junto_para_o_drawer(self):
        """So' existia na expansao; mover sem ele perderia o bloco que responde
        "por que ela nao tem o IC?" (2o retorno)."""
        self.assertIn("_csSemMapeamento", _corpo("csRenderDrawerBody"))

    def test_drawer_respeita_a_aba_pedida(self):
        """Se `csAbrirDrawer` fixar 'ident', o botao do resumo cai na aba errada
        e o usuario tem de clicar de novo."""
        corpo = _corpo("csAbrirDrawer")
        self.assertIn("aba", corpo, "csAbrirDrawer precisa aceitar a aba de destino")
        self.assertIn("_csTab", corpo)
        self.assertNotIn("t.dataset.cstab === 'ident'", corpo,
                         "a aba visualmente ativa tem de seguir _csTab")

    def test_resumo_conta_todas_as_categorias(self):
        """O resumo nao pode esconder uma categoria inteira."""
        corpo = _corpo("_csMontarSub")
        self.assertIn("_CS_CATS", corpo)
        self.assertIn("sem mapeamento", corpo,
                      "sem mapeamento é calculado na tela e conta no resumo")

    def test_toda_categoria_tem_rotulo_curto(self):
        """O resumo usa `curto`; categoria sem ele sairia 'undefined' na tela."""
        html = INDEX.read_text(encoding="utf-8")
        m = re.search(r"const _CS_CATS = \[(.*?)\];", html, re.S)
        self.assertTrue(m)
        entradas = re.findall(r"\{k:'(\w+)'.*?\}", m.group(1), re.S)
        curtos = re.findall(r"curto:'([^']+)'", m.group(1))
        self.assertEqual(len(entradas), len(curtos),
                         f"categorias {entradas} x curtos {curtos}")


if __name__ == "__main__":
    unittest.main()
