# -*- coding: utf-8 -*-
"""O detalhe da Consulta nao pode despejar 260 perfis numa linha.

Retorno da area (28/08/2026, Teams):
    "entao ele se perde na parte da divisao as vezes ele traz a lista de perfis
     tipo esperado / ai ele lista tudo / encontrado / E lista os encontrados em
     oura 'coluna' / Da pra entender em alguns casos mais alguns ficam confusos"
    "sera que da para melhorar de alguma forma?"

Medido na base dela antes de mexer:

  perfis numa linha    linhas
  1                     5.062
  2-4                     210
  5-10                     51
  11-20                   182
  21+                     520      <- praticamente todas do SIG

  por sistema (max perfis numa linha):
    SIG 141 (mediana 39) · ORACLE_EBS 3 · SYSTUR 2 · os outros 4 sistemas: 1

Ou seja: o agrupamento esta certo para 6 dos 7 sistemas. O SIG e' matricial e
tem volume ~40x maior; o mesmo layout que serve para 1 perfil vira paredao.
Pior caso real: matricula 90000909, 134 perfis de um lado e 131 do outro — 265
despejados numa linha, e cabia a ela comparar de cabeca.

Duas regras entraram:

  1. TETO. Mostra os primeiros 6 e resume o resto ("+125 outros"), com a lista
     inteira no title. Antes: 262 linhas na tela. Depois: 7.
  2. DELTA. Com os dois lados presentes, mostra a DIFERENCA — o que falta e o
     que esta a mais — em vez das duas listas inteiras. E' o acionavel.
     Medido no caso 90000909: 265 perfis -> 3 linhas ("3 a mais: ...").

  Valvula: se a diferenca der vazia dos dois lados mas os textos diferirem, a
  divergencia e' so' de grafia — ai mostra os dois lados, porque esconder
  seria mentir sobre o motivo de a linha estar ali.
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
INDEX = RAIZ / "CVC_IAM_ANALYTICS" / "EXECUTAVEIS" / "REPORT" / "index.html"
NODE = shutil.which("node")


def _funcao(nome):
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


@unittest.skipUnless(NODE, "Node não disponível nesta máquina")
class VolumeDePerfis(unittest.TestCase):

    def _html(self, pe, pp):
        js = f"""
        const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;')
                                  .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
        {_funcao('_csListaPerfis')}
        {_funcao('_csDelta')}
        {_funcao('_csPerfilTxt')}
        console.log(_csPerfilTxt({json.dumps({"pe": pe, "pp": pp})}));
        """
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                         encoding="utf-8") as f:
            f.write(js)
            caminho = f.name
        try:
            r = subprocess.run([NODE, caminho], capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            self.assertEqual(r.returncode, 0, r.stderr)
            return r.stdout.strip()
        finally:
            os.unlink(caminho)

    def _n_linhas(self, html):
        return html.count("<br>") + 1

    # ── teto ──────────────────────────────────────────────────────────────
    def test_lista_curta_sai_inteira(self):
        h = self._html("", "A, B, C")
        self.assertNotIn("outros", h)
        for p in ("A", "B", "C"):
            self.assertIn(p, h)

    def test_lista_longa_e_resumida(self):
        perfis = ", ".join("PERFIL_%02d" % i for i in range(131))
        h = self._html("", perfis)
        self.assertIn("+125 outros", h, "131 perfis - 6 visiveis = 125")
        self.assertLessEqual(self._n_linhas(h), 7,
                             "o paredao de 131 tem de caber em 7 linhas")

    def test_a_lista_inteira_continua_acessivel(self):
        """Resumir nao pode ESCONDER: o title leva tudo."""
        perfis = ", ".join("PERFIL_%02d" % i for i in range(131))
        h = self._html("", perfis)
        self.assertIn("PERFIL_130", h, "o title tem de conter os 131")

    # ── delta ─────────────────────────────────────────────────────────────
    def test_dois_lados_mostram_a_DIFERENCA_e_nao_as_listas(self):
        """O caso real 90000909: 134 x 131 perfis, 3 de diferenca."""
        tem = ["P%03d" % i for i in range(134)]
        dev = ["P%03d" % i for i in range(131)]
        h = self._html(", ".join(tem), ", ".join(dev))
        self.assertIn("3 a mais", h)
        self.assertIn("P131", h)
        self.assertIn("P133", h)
        # Eram 4 ate 31/08. Passaram a 8 DE PROPOSITO: o retorno daquele dia
        # ("se faltam dois, algum ela possui — nao deveria vir em acessos
        # encontrados?") cobrou de volta o lado do que a pessoa TEM, que a
        # versao anterior descartava. O paredao segue barrado — 265 perfis
        # cabem em 8 linhas, com o resto a um clique.
        self.assertLessEqual(self._n_linhas(h), 8,
                             "265 perfis tem de caber em 8 linhas")
        self.assertIn("Tem 131", h, "o que ela JA TEM nao pode sumir da tela")

    def test_diz_o_que_FALTA(self):
        h = self._html("A, B", "A, B, C, D")
        self.assertIn("Faltam 2", h)
        self.assertIn("C", h)
        self.assertIn("D", h)

    def test_falta_no_singular(self):
        self.assertIn("Falta 1", self._html("A", "A, B"))

    def test_os_dois_sentidos_juntos(self):
        h = self._html("A, X", "A, B")
        self.assertIn("Falta 1", h)
        self.assertIn("1 a mais", h)

    # ── valvula de seguranca ──────────────────────────────────────────────
    def test_diferenca_so_de_grafia_mostra_os_dois_lados(self):
        """Se o delta some por normalizacao, esconder seria mentir sobre o
        motivo de a linha estar marcada como divergente."""
        h = self._html("perfil_a, PERFIL_B", "PERFIL_A, perfil_b")
        self.assertIn("Tem hoje", h)
        self.assertIn("Deveria ter", h)

    def test_aderente_nao_ganhou_rotulo(self):
        h = self._html("A, B", "A, B")
        self.assertNotIn("Falta", h)
        self.assertNotIn("a mais", h)
        self.assertNotIn("Tem hoje", h)


if __name__ == "__main__":
    unittest.main()
