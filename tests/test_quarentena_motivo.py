# -*- coding: utf-8 -*-
"""Quarentena com MOTIVO em lista (retorno de 07/10/2026, Aplicacao_CVC_07_10):
"Trazer uma opcao Motivo e adicionar as opcoes: Excecao, Ferias/Cobertura de
ferias, Usuario sistemico". Obrigatorio; o texto livre virou "Detalhe".

Vai no MESMO campo `motivo` do servidor ("Opcao — detalhe"), entao o historico
da quarentena e o que o servidor grava nao mudam.
"""
import re
import unittest
from pathlib import Path

INDEX = (Path(__file__).resolve().parent.parent
         / "CVC_IAM_ANALYTICS" / "EXECUTAVEIS" / "REPORT" / "index.html")


def _funcao(html, nome):
    i = html.index(f"function {nome}(")
    j, nivel = html.index("{", i), 0
    for k in range(j, len(html)):
        if html[k] == "{":
            nivel += 1
        elif html[k] == "}":
            nivel -= 1
            if nivel == 0:
                return html[i:k + 1]
    raise AssertionError(f"funcao {nome} nao fecha")


class QuarentenaMotivo(unittest.TestCase):

    def setUp(self):
        self.html = INDEX.read_text(encoding="utf-8")

    def test_as_tres_opcoes_da_area(self):
        m = re.search(r"const QUAR_MOTIVOS = \[([^\]]*)\]", self.html)
        self.assertIsNotNone(m)
        self.assertEqual(re.findall(r"'([^']*)'", m.group(1)),
                         ["Exceção", "Férias/Cobertura de férias", "Usuário sistêmico"])

    def test_formulario_tem_a_lista_obrigatoria_e_o_detalhe(self):
        corpo = _funcao(self.html, "quarentenar")
        self.assertIn('id="quar-motivo-op"', corpo)
        self.assertIn("Motivo <span class=\"req\">*</span>", corpo)
        self.assertIn("Detalhe (opcional)", corpo)

    def test_sem_motivo_nao_envia(self):
        corpo = _funcao(self.html, "confirmarQuarentena")
        self.assertIn("if(!motivoOp)", corpo)
        self.assertIn("Selecione o motivo da quarentena.", corpo)

    def test_grava_opcao_e_detalhe_no_mesmo_campo(self):
        corpo = _funcao(self.html, "confirmarQuarentena")
        self.assertIn("motivoOp + (detalhe ? ' — ' + detalhe : '')", corpo)
        self.assertIn("motivo:motivo", corpo, "o payload continua com o campo motivo")


if __name__ == "__main__":
    unittest.main()
