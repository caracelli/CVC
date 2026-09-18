# -*- coding: utf-8 -*-
"""Funções da matriz CCO na Consulta (retorno da área, 17/09/2026, item 1).

"Pelo Perfil que ela tem esse perfil no systur... pela lógica ali ela tem acesso
à função Atendimento a fornecedores CVC e VISUAL. Aí precisaria ter uma lista
nessa visualização em baixo: Funções disponíveis e uma possibilidade de expandir
e ver os acessos."

Na CCO o acesso vem por FUNÇÃO (centro de custo + gestor -> funções; cada função
= vários perfis em vários sistemas). Até 18/09 a função existia só no arquivo do
cliente e na tabela matriz_cco: a validação guardava o perfil e perdia a função,
então a tela listava perfis soltos. Agora a função viaja até o painel.
"""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
import visualizador.main as vm

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


class FuncaoChegaAoPainel(unittest.TestCase):
    """De ponta a ponta no servidor: validacao_acessos.funcao -> payload."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cvc_fun_")
        self.db = os.path.join(self.tmp, "iam.db")
        ConexaoBancoDados(self.db).inicializar()
        self._orig = (vm.DB_PATH, vm.SISTEMA)
        vm.DB_PATH, vm.SISTEMA, vm._BASE = self.db, "", None
        c = sqlite3.connect(self.db)
        try:
            cols = [r[1] for r in c.execute("PRAGMA table_info(validacao_acessos)")]
            self.assertIn("funcao", cols, "a coluna funcao precisa existir (migração aditiva)")
            for sistema, perfil, status, funcao in (
                    ("SYSTUR", "ATD_FOR_CVC_VISUAL_CP", "OK", "Atendimento a fornecedores  CVC e VISUAL"),
                    ("ORACLE_EBS", "CVC AP BRASIL Consulta", "SEM_ACESSO", "Atendimento a fornecedores  CVC e VISUAL"),
                    ("SIGOT", "ATD_FOR", "SEM_ACESSO", "Atendimento a fornecedores")):
                c.execute("INSERT INTO validacao_acessos (matricula, nome, cpf, sistema, "
                          "perfil_esperado, perfil_atual, status, situacao_acao, funcao, "
                          "dt_processamento) VALUES ('1','BRENDA','00000000001',?,?,?,?, 'OK', ?, "
                          "'2026-09-18 10:00:00')",
                          [sistema, perfil, perfil if status == "OK" else "", status, funcao])
            c.commit()
        finally:
            c.close()
        vm.garantir_estrutura(force=True)

    def tearDown(self):
        vm.DB_PATH, vm.SISTEMA = self._orig
        vm._BASE = None

    def test_payload_leva_a_funcao(self):
        u = vm.construir_db()["users"][0]
        self.assertEqual({d["fun"] for d in u["divs"]},
                         {"Atendimento a fornecedores  CVC e VISUAL",
                          "Atendimento a fornecedores"})

    def test_linha_sem_cco_fica_sem_funcao(self):
        """Matriz por CARGO não tem função — o campo vem vazio, não inventado."""
        c = sqlite3.connect(self.db)
        try:
            c.execute("INSERT INTO validacao_acessos (matricula, nome, cpf, sistema, "
                      "perfil_esperado, status, situacao_acao, dt_processamento) "
                      "VALUES ('2','OUTRO','00000000002','SIG','P','SEM_ACESSO','OK',"
                      "'2026-09-18 10:00:00')")
            c.commit()
        finally:
            c.close()
        vm._BASE = None
        vm.garantir_estrutura(force=True)
        u = [x for x in vm.construir_db()["users"] if x["m"] == "2"][0]
        self.assertEqual([d["fun"] for d in u["divs"]], [""])


@unittest.skipUnless(NODE, "Node não disponível nesta máquina")
class ListaDeFuncoesNaTela(unittest.TestCase):

    def _html(self, divs):
        js = ("const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;')"
              ".replace(/>/g,'&gt;').replace(/\"/g,'&quot;');\n"
              f"{_funcao('_csFuncoesCco')}\n"
              f"console.log(_csFuncoesCco({json.dumps(divs)}));")
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                         encoding="utf-8") as f:
            f.write(js)
            caminho = f.name
        try:
            r = subprocess.run([NODE, caminho], capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            if r.returncode:
                raise AssertionError(r.stderr)
            return r.stdout
        finally:
            os.unlink(caminho)

    TEM = {"fun": "Func completa", "a": "Aderente", "sis": "SYSTUR", "pp": "P1", "pe": "P1"}
    FALTA1 = {"fun": "Func com falta", "a": "Incluir Acesso", "sis": "ORACLE_EBS", "pp": "P2", "pe": ""}
    FALTA2 = {"fun": "Func com falta", "a": "Incluir Acesso", "sis": "SIGOT", "pp": "P3", "pe": ""}
    SEM_FUN = {"fun": "", "a": "Incluir Acesso", "sis": "SIG", "pp": "P9", "pe": ""}

    def test_sem_cco_nao_mostra_o_bloco(self):
        """Quem só tem matriz por cargo não ganha uma seção vazia na tela."""
        self.assertEqual(self._html([self.SEM_FUN]).strip(), "")

    def test_agrupa_por_funcao_e_conta(self):
        html = self._html([self.TEM, self.FALTA1, self.FALTA2])
        self.assertIn("Funções previstas (2)", html)
        self.assertIn("Func com falta", html)
        self.assertIn("faltam 2", html)
        self.assertIn("completa", html)

    def test_o_que_falta_vem_primeiro(self):
        """Precedente de 28/08: o acionável antes."""
        html = self._html([self.TEM, self.FALTA1, self.FALTA2])
        self.assertLess(html.index("Func com falta"), html.index("Func completa"))

    def test_expande_mostrando_sistema_perfil_e_estado(self):
        html = self._html([self.TEM, self.FALTA1])
        self.assertIn("ORACLE_EBS", html)
        self.assertIn("P2", html)
        self.assertIn(">falta<", html)
        self.assertIn(">tem<", html)

    def test_funcao_parcial_mostra_quanto_ela_ja_tem(self):
        """"Se faltam dois, algum ela possui" (retorno de 31/08) — o parcial diz
        quanto ela tem, não só o que falta."""
        parcial = dict(self.FALTA1, fun="Func completa")
        self.assertIn("tem 1 de 2", self._html([self.TEM, parcial]))

    def test_o_drawer_chama_a_lista(self):
        """Guarda contra o fix virar código morto (achado de 26/08)."""
        html = INDEX.read_text(encoding="utf-8")
        self.assertIn("_csFuncoesCco(u.divs)", html)


if __name__ == "__main__":
    unittest.main()
