# -*- coding: utf-8 -*-
"""O JavaScript do painel INTEIRO precisa ser sintaticamente valido.

Por que este teste existe (22/09/2026): o popup de exportacao foi escrito com
as aspas mal escapadas —

    + '" onclick="_exportEscolher('agrupado')">'      # <- quebra a string

— e isso derrubou o painel TODO: a pagina carregava, mas nenhum script rodava,
entao a tela ficava vazia e as abas nao navegavam. O servidor respondia 200 em
tudo; o defeito era so' no navegador.

A suite nao pegou porque os testes do painel extraem UMA funcao por vez e a
rodam no node. Funcao que nenhum teste extrai nunca e' analisada — e era
exatamente o caso de `_exportFormato`.

Este teste fecha essa lacuna pela raiz: pega o bloco <script> inline inteiro e
manda o node so' CHECAR a sintaxe (`--check`, nao executa nada). Qualquer erro
de digitacao em qualquer funcao do arquivo cai aqui.
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

INDEX = (Path(__file__).resolve().parent.parent
         / "CVC_IAM_ANALYTICS" / "EXECUTAVEIS" / "REPORT" / "index.html")
NODE = shutil.which("node")


@unittest.skipUnless(NODE, "Node não disponível nesta máquina")
class SintaxeDoPainel(unittest.TestCase):

    def test_script_inline_e_valido(self):
        html = INDEX.read_text(encoding="utf-8")
        blocos = re.findall(
            r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.S)
        self.assertTrue(blocos, "nenhum <script> inline encontrado no index.html")
        script = max(blocos, key=len)
        self.assertGreater(len(script), 100_000,
                           "o bloco principal do painel encolheu demais — "
                           "a extração provavelmente pegou o script errado")

        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                         encoding="utf-8") as f:
            f.write(script)
            caminho = f.name
        try:
            r = subprocess.run(["node", "--check", caminho],
                               capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(
                r.returncode, 0,
                "O JavaScript do painel não compila — a tela abre VAZIA e as "
                "abas não navegam:\n" + (r.stderr or ""))
        finally:
            os.unlink(caminho)


if __name__ == "__main__":
    unittest.main()
