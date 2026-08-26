# -*- coding: utf-8 -*-
""""Aderente" na Consulta nao pode ser o `else` de todo mundo.

Retorno da area (25/08/2026), sobre o usuario sistemico BRCVCSRVSYSINT:
"Usuario sistemico vindo como aderente? Qual conceito". No print a linha trazia
o pino verde "Aderente" e, na mesma linha, a coluna Pendencias marcando **2** em
vermelho — os dois acessos listados como "nao localizados".

Causa: o pino tinha 3 estados e o ultimo era um `else`. Quem tinha pendencia JA
TRATADA (status != Pendente) nao entrava em "pendente" nem em "incluir acessos",
e caia em "Aderente". Aderente e' quem NAO tem pendencia; quem teve e tratou e'
RESOLVIDO.

Roda a funcao real extraida do index.html no Node. Pula se nao houver Node.
"""
import json
import shutil
import subprocess
import tempfile
import os
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


def _div(acao, situacao="Pendente"):
    return {"a": acao, "s": situacao}


@unittest.skipUnless(NODE, "Node não disponível nesta máquina")
class PinoDaConsulta(unittest.TestCase):

    def _pino(self, divs):
        js = f"""
        {_funcao('_csPino')}
        console.log(JSON.stringify(_csPino({{divs: {json.dumps(divs)}}})));
        """
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                         encoding="utf-8") as f:
            f.write(js)
            caminho = f.name
        try:
            r = subprocess.run([NODE, caminho], capture_output=True, text=True,
                               encoding="utf-8", timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr)
            return json.loads(r.stdout.strip().splitlines()[-1])
        finally:
            os.unlink(caminho)

    def test_sistemico_com_pendencias_tratadas_e_resolvido(self):
        """O caso do print: 2 acessos sem vínculo, ambos já tratados."""
        p = self._pino([_div("Usuário Não Encontrado", "Resolvido"),
                        _div("Usuário Não Encontrado", "Resolvido")])
        self.assertEqual(p["lbl"], "2 resolvidas")
        self.assertNotEqual(p["cls"], "ok", "não pode pintar como aderente")

    def test_uma_pendencia_tratada(self):
        self.assertEqual(
            self._pino([_div("Em Análise", "Resolvido")])["lbl"], "Resolvido")

    def test_aderente_de_verdade(self):
        p = self._pino([_div("Aderente", "Aderente")])
        self.assertEqual((p["cls"], p["lbl"]), ("ok", "Aderente"))

    def test_pendencia_aberta_continua_mandando(self):
        p = self._pino([_div("Em Análise", "Pendente"),
                        _div("Em Análise", "Resolvido")])
        self.assertEqual((p["cls"], p["lbl"]), ("pend", "1 pendente"))

    def test_incluir_acesso_nao_e_pendencia_nem_aderencia(self):
        p = self._pino([_div("Incluir Acesso", "Pendente")])
        self.assertEqual((p["cls"], p["lbl"]), ("incluir", "Incluir acessos"))

    def test_incluir_vence_resolvido(self):
        """Ação em aberto na frente do que já foi tratado."""
        p = self._pino([_div("Incluir Acesso", "Pendente"),
                        _div("Em Análise", "Resolvido")])
        self.assertEqual(p["cls"], "incluir")


@unittest.skipUnless(NODE, "Node não disponível nesta máquina")
class FunilDaColunaAbas(unittest.TestCase):
    """As três regras de "tem pendência?" na mesma linha da Consulta — funil da
    coluna Abas, botão P e a coluna Pendências — precisam concordar.

    O funil contava QUALQUER coisa != Aderente, e portanto incluía "Incluir
    Acesso"; os outros dois excluem. Filtrar por "Pendência" trazia gente sem
    botão P, e o número da coluna não fechava com a lista filtrada.
    """

    def _abas(self, divs, matricula="M1", hist=(), desl=()):
        js = f"""
        let _histMats = new Set({json.dumps(list(hist))});
        let _deslMats = new Set({json.dumps(list(desl))});
        {_funcao('_csAbasOf')}
        console.log(JSON.stringify(_csAbasOf(
          {{m: {json.dumps(matricula)}, divs: {json.dumps(divs)}}})));
        """
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                         encoding="utf-8") as f:
            f.write(js)
            caminho = f.name
        try:
            r = subprocess.run([NODE, caminho], capture_output=True, text=True,
                               encoding="utf-8", timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr)
            return json.loads(r.stdout.strip().splitlines()[-1])
        finally:
            os.unlink(caminho)

    def test_so_incluir_acesso_nao_e_pendencia(self):
        """O caso da divergência: antes entrava no funil "Pendência" sem ter o
        botão P."""
        abas = self._abas([_div("Incluir Acesso")])
        self.assertNotIn("Pendência", abas)
        self.assertIn("Incluir acessos", abas)

    def test_pendencia_de_verdade_entra(self):
        self.assertIn("Pendência", self._abas([_div("Em Análise")]))

    def test_os_dois_convivem(self):
        abas = self._abas([_div("Em Análise"), _div("Incluir Acesso")])
        self.assertIn("Pendência", abas)
        self.assertIn("Incluir acessos", abas)

    def test_aderente_exige_matricula(self):
        """Regra pré-existente que não pode ser perdida no ajuste."""
        self.assertNotIn("Aderente", self._abas([_div("Aderente", "Aderente")],
                                                matricula=""))
        self.assertIn("Aderente", self._abas([_div("Aderente", "Aderente")]))

    def test_historico_e_desligado_seguem_pela_matricula(self):
        abas = self._abas([_div("Aderente", "Aderente")], hist=["M1"], desl=["M1"])
        self.assertIn("Histórico", abas)
        self.assertIn("Desligado", abas)

    def test_funil_oferece_a_opcao_nova(self):
        """A opção tem de existir no menu, senão o atributo fica inalcançável."""
        html = INDEX.read_text(encoding="utf-8")
        i = html.index("function _csAbasMenu(")
        trecho = html[i:i + 900]
        self.assertIn("'Incluir acessos'", trecho)


if __name__ == "__main__":
    unittest.main()
