# -*- coding: utf-8 -*-
"""Exportar: escolher entre AGRUPADO e ANALITICO.

O defeito, relatado pela area em 22/09/2026: a planilha agrupada poe a PESSOA
na linha-pai e o SISTEMA na linha-filha. Quando ela aplica o autofiltro por
Sistema dentro do Excel, sobram so' as linhas-filhas — e elas vem com
Matricula, Nome, CPF e Cargo em BRANCO, porque esses valores moram no pai. O
filtro funciona e a identificacao some.

Trocar o formato nao resolvia: o agrupado e' melhor para LER e foi pedido dela
em 31/08 ("abrir por sistema"). Os dois formatos sao legitimos, para tarefas
diferentes, entao a escolha passou a ser dela no momento de exportar.

ANALITICO = uma linha por FOLHA da hierarquia, herdando dos ancestrais tudo o
que veio vazio. Um pai sem filho continua saindo (senao a pessoa sem nenhum
acesso sumiria da planilha — o defeito oposto).
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

INDEX = (Path(__file__).resolve().parent.parent
         / "CVC_IAM_ANALYTICS" / "EXECUTAVEIS" / "REPORT" / "index.html")
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


def _node(js):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                     encoding="utf-8") as f:
        f.write(js)
        caminho = f.name
    try:
        r = subprocess.run(["node", caminho], capture_output=True, text=True,
                           encoding="utf-8")
        if r.returncode != 0:
            raise AssertionError(r.stderr)
        return r.stdout
    finally:
        os.unlink(caminho)


@unittest.skipUnless(NODE, "Node não disponível nesta máquina")
class Achatar(unittest.TestCase):

    def _achatar(self, linhas, niveis):
        js = (_funcao("_exportAchatar") + "\n"
              + "console.log(JSON.stringify(_exportAchatar("
              + json.dumps(linhas) + "," + json.dumps(niveis) + ")));")
        return json.loads(_node(js))

    def test_o_caso_da_area(self):
        """Colunas da Consulta: a linha do sistema herda matrícula e nome, que
        é o que o filtro por Sistema fazia sumir."""
        cols_pessoa = ["1303", "MARCELO", "CORP01", "ANALISTA", "", 2]
        sis1 = ["", "", "", "", "SYSTUR", 1]
        sis2 = ["", "", "", "", "SIGOT", 1]
        r = self._achatar([cols_pessoa, sis1, sis2], [0, 1, 1])
        self.assertEqual(len(r), 2, "uma linha por sistema, sem a linha-pai")
        self.assertEqual(r[0], ["1303", "MARCELO", "CORP01", "ANALISTA", "SYSTUR", 1])
        self.assertEqual(r[1], ["1303", "MARCELO", "CORP01", "ANALISTA", "SIGOT", 1])

    def test_pai_sem_filho_continua_saindo(self):
        """A pessoa sem nenhum acesso não pode sumir da planilha."""
        r = self._achatar([["1", "ANA", ""], ["2", "BIA", ""], ["", "", "SIG"]],
                          [0, 0, 1])
        self.assertEqual(len(r), 2)
        self.assertEqual(r[0], ["1", "ANA", ""], "ANA não tem filho e fica")
        self.assertEqual(r[1], ["2", "BIA", "SIG"])

    def test_tres_niveis_herdam_a_cadeia_toda(self):
        """pessoa > sistema > perfil: a folha herda dos DOIS ancestrais."""
        r = self._achatar(
            [["7", "ROSE", "", ""], ["", "", "SYSTUR", ""],
             ["", "", "", "P1"], ["", "", "", "P2"]],
            [0, 1, 2, 2])
        self.assertEqual(r, [["7", "ROSE", "SYSTUR", "P1"],
                             ["7", "ROSE", "SYSTUR", "P2"]])

    def test_nao_inventa_valor(self):
        """Coluna vazia em toda a cadeia continua vazia — herdar não é chutar."""
        r = self._achatar([["1", "", ""], ["", "", "SIG"]], [0, 1])
        self.assertEqual(r, [["1", "", "SIG"]])

    def test_zero_nao_e_tratado_como_vazio(self):
        """Contadores valem 0 legitimamente; 0 não pode puxar o valor do pai."""
        r = self._achatar([["1", 9], ["", 0]], [0, 1])
        self.assertEqual(r, [["1", 0]], "o 0 da folha foi sobrescrito pelo 9 do pai")


@unittest.skipUnless(NODE, "Node não disponível nesta máquina")
class QuandoPerguntar(unittest.TestCase):

    def _tem_grupo(self, niveis):
        js = (_funcao("_exportTemGrupo") + "\n"
              + "console.log(JSON.stringify(_exportTemGrupo("
              + json.dumps(niveis) + ")));")
        return json.loads(_node(js))

    def test_pergunta_quando_ha_agrupamento(self):
        self.assertTrue(self._tem_grupo([0, 1, 1]))
        self.assertTrue(self._tem_grupo([0, 1, 2]))

    def test_nao_pergunta_no_export_ja_plano(self):
        """Aderentes manda níveis todos 0 e Sem Vínculo manda null: esses já são
        planos e não podem ganhar um popup à toa."""
        self.assertFalse(self._tem_grupo([0, 0, 0]))
        self.assertFalse(self._tem_grupo(None))
        self.assertFalse(self._tem_grupo([]))


class LigacaoNoPainel(unittest.TestCase):
    """Asserções no fonte: o que não dá para exercitar isolado no node."""

    def setUp(self):
        self.html = INDEX.read_text(encoding="utf-8")

    def test_baixar_excel_so_pergunta_se_houver_grupo(self):
        corpo = _funcao("baixarExcel")
        self.assertIn("_exportTemGrupo(niveis)", corpo)
        self.assertIn("_exportFormato(arquivo)", corpo)
        self.assertIn("_exportAchatar(linhas, niveis)", corpo)

    def test_analitico_manda_sem_niveis(self):
        """Se mandasse os níveis junto, o xlsx voltaria a sair agrupado."""
        corpo = _funcao("baixarExcel")
        self.assertIn("niveis = null", corpo)

    def test_cancelar_nao_baixa(self):
        corpo = _funcao("baixarExcel")
        self.assertIn("if (!op) return;", corpo)

    def test_consulta_passa_pelo_baixar_excel(self):
        """A Consulta chamava /api/exportar direto e escapava da pergunta."""
        corpo = _funcao("csExportar")
        self.assertIn("baixarExcel('consulta'", corpo)
        self.assertNotIn("/api/exportar", corpo)

    def test_fechar_modal_solta_a_promise(self):
        """Clique no fundo fecha o modal; sem soltar a promise, o await de
        baixarExcel ficaria pendurado e o botão pareceria travado."""
        corpo = _funcao("fecharModal")
        self.assertIn("_exportEscolha", corpo)

    def test_consulta_nao_perdeu_o_login_real(self):
        """Não-regressão do teste de 08/09 (export reflete a grid)."""
        self.assertIn("u.login", _funcao("csExportar"))


if __name__ == "__main__":
    unittest.main()
