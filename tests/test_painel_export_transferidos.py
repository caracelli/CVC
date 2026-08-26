# -*- coding: utf-8 -*-
"""O Excel de Transferidos tem de sobreviver ao filtro do Excel.

Retorno da area (25/08/2026): "Cargo e Gestor, que e' a validacao da matriz, nao
abre as informacoes, o relatorio no Excel nao e' funcional". O motivo era o
layout em arvore: a linha do funcionario trazia a identificacao e as linhas
seguintes (movimento, acessos) vinham com Nome/Matricula/Cargo/CC/Gestor
VAZIOS. Ao filtrar Mudanca = "gestor" no Excel sobravam linhas com De/Para e
nenhuma pista de quem era a pessoa.

O teste extrai a funcao real do index.html e a executa no Node com stubs — e'
a unica forma de fixar isso sem abrir o navegador. Pula se nao houver Node.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
INDEX = RAIZ / "CVC_IAM_ANALYTICS" / "EXECUTAVEIS" / "REPORT" / "index.html"
NODE = shutil.which("node")


def _funcao(nome):
    """Recorta `function <nome>(){...}` do index.html pelo balanceamento de {}."""
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
class ExportTransferidosIdentificaTodaLinha(unittest.TestCase):

    # um transferido com DUAS mudanças (gestor e centro de custo) e acessos em
    # dois sistemas — o caso que ela mandou no print
    REGISTRO = {
        "m": "34531437", "n": "BRUNA MAIARA DO NASCIMENTO",
        "cargo": "ANALISTA FINANCEIRO JR", "cc": "01.06.04.01",
        "gestor": "HELEN ANTONIA LA SPINA RUAS",
        "campos": "gestor, centro de custo", "dt_mov": "2026-08-05",
        "tratado": False, "tratamento": {},
        "de_para": [
            {"campo": "gestor", "de": "ADRIANA CELESTINO DA SILVA",
             "para": "DANIEL MARQUES GRANDINO"},
            {"campo": "centro de custo", "de": "01.06.02.01", "para": "01.06.04.01"},
        ],
        "acessos": [{"sis": "SYSTUR", "login": "bmnascimento",
                     "perfil": "ANT_OP_BKO_N2", "dt": "2026-08-05"}],
    }

    def _rodar(self):
        js = f"""
        const REG = {json.dumps(self.REGISTRO, ensure_ascii=False)};
        let CAPTURA = null;
        function fmtDate(d){{ return String(d || ''); }}
        function _transfFiltrados(){{ return [REG]; }}
        function _acessosPorSistema(acessos){{
          return (acessos || []).map(a => ({{
            sis: a.sis, login: a.login, perfis: [a.perfil], lista: [a], dt: a.dt
          }}));
        }}
        function baixarExcel(nome, cols, linhas, niveis, formatos){{
          CAPTURA = {{nome, cols, linhas, niveis, formatos}};
        }}
        {_funcao('exportarTransferidos')}
        exportarTransferidos();
        console.log(JSON.stringify(CAPTURA));
        """
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                         encoding="utf-8") as f:
            f.write(js)
            caminho = f.name
        try:
            saida = subprocess.run([NODE, caminho], capture_output=True, text=True,
                                   encoding="utf-8", timeout=60)
            self.assertEqual(saida.returncode, 0, saida.stderr)
            return json.loads(saida.stdout.strip().splitlines()[-1])
        finally:
            os.unlink(caminho)

    def setUp(self):
        self.x = self._rodar()
        self.cols = self.x["cols"]

    def test_toda_linha_diz_de_quem_e(self):
        """O coracao do apontamento: nenhuma linha anonima."""
        i_mat, i_nome = self.cols.index("Matrícula"), self.cols.index("Nome")
        for n, linha in enumerate(self.x["linhas"]):
            self.assertTrue(linha[i_mat], f"linha {n} sem matrícula")
            self.assertTrue(linha[i_nome], f"linha {n} sem nome")

    def test_de_para_virou_coluna_por_campo(self):
        """'Abrir os nomes em colunas, não em linhas' — o pedido literal."""
        for rot in ("Cargo", "Departamento", "Centro de Custo", "Gestor"):
            self.assertIn(f"{rot} (De)", self.cols)
            self.assertIn(f"{rot} (Para)", self.cols)
        pai = self.x["linhas"][0]
        self.assertEqual(pai[self.cols.index("Gestor (De)")],
                         "ADRIANA CELESTINO DA SILVA")
        self.assertEqual(pai[self.cols.index("Gestor (Para)")],
                         "DANIEL MARQUES GRANDINO")
        self.assertEqual(pai[self.cols.index("Centro de Custo (Para)")], "01.06.04.01")
        # campo que NAO mudou fica vazio, nao repete o valor atual
        self.assertEqual(pai[self.cols.index("Cargo (De)")], "")

    def test_filtrar_por_gestor_no_excel_ainda_mostra_a_pessoa(self):
        """Simula o filtro que ela aplicou: Gestor (Para) preenchido."""
        i = self.cols.index("Gestor (Para)")
        i_nome = self.cols.index("Nome")
        filtradas = [l for l in self.x["linhas"] if l[i]]
        self.assertTrue(filtradas, "o filtro por mudança de gestor não sobrou nada")
        for l in filtradas:
            self.assertEqual(l[i_nome], "BRUNA MAIARA DO NASCIMENTO")

    def test_acessos_continuam_no_relatorio(self):
        i_sis = self.cols.index("Sistema")
        self.assertIn("SYSTUR", [l[i_sis] for l in self.x["linhas"]])

    def test_formato_condicional_aponta_para_situacao(self):
        """A coluna mudou de posição: o formato tem de acompanhar, senão pinta
        a coluna errada."""
        self.assertEqual(self.x["formatos"][0]["col"], self.cols.index("Situação"))

    def test_agrupamento_preservado(self):
        self.assertEqual(self.x["niveis"][0], 0)
        self.assertIn(1, self.x["niveis"])


@unittest.skipUnless(NODE, "Node não disponível nesta máquina")
class ExportDesligadosIdentificaTodaLinha(unittest.TestCase):
    """Mesmo defeito do Excel de Transferidos, na aba Desligados.

    A área não chegou a apontar este — mas é o mesmo código e o mesmo efeito:
    as linhas de acesso saíam sem Matrícula/Nome/Cargo/Departamento/CC, e o
    filtro do Excel deixava uma lista de acessos sem dono. Como o Excel de
    desligados é o insumo do fluxo de chamados (Fase 2), o defeito ia doer lá.
    """

    REGISTRO = {
        "m": "9001", "n": "JOSE DA SILVA", "cargo": "ANALISTA",
        "depto": "TECNOLOGIA", "cc": "01.02.03.04", "dt_deslig": "2026-07-31",
        "sit": "Tratar", "tratado": False, "tratamento": {},
        "acessos": [
            {"sis": "SYSTUR", "login": "jsilva", "perfil": "P1",
             "dt": "2026-08-05", "resolvida": 0},
            {"sis": "SIGOT", "login": "jsilva", "perfil": "P2",
             "dt": "2026-08-05", "resolvida": 0},
        ],
    }

    def setUp(self):
        js = f"""
        const REG = {json.dumps(self.REGISTRO, ensure_ascii=False)};
        let CAPTURA = null;
        function fmtDate(d){{ return String(d || ''); }}
        function _deslFiltrados(){{ return [REG]; }}
        function _acessosPorSistema(acessos){{
          return (acessos || []).map(a => ({{
            sis: a.sis, login: a.login, perfis: [a.perfil], lista: [a], dt: a.dt
          }}));
        }}
        function baixarExcel(nome, cols, linhas, niveis, formatos){{
          CAPTURA = {{nome, cols, linhas, niveis, formatos}};
        }}
        {_funcao('exportarDesligados')}
        exportarDesligados();
        console.log(JSON.stringify(CAPTURA));
        """
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                         encoding="utf-8") as f:
            f.write(js)
            caminho = f.name
        try:
            saida = subprocess.run([NODE, caminho], capture_output=True, text=True,
                                   encoding="utf-8", timeout=60)
            self.assertEqual(saida.returncode, 0, saida.stderr)
            self.x = json.loads(saida.stdout.strip().splitlines()[-1])
        finally:
            os.unlink(caminho)
        self.cols = self.x["cols"]

    def test_toda_linha_diz_de_quem_e(self):
        i_mat, i_nome = self.cols.index("Matrícula"), self.cols.index("Nome")
        for n, linha in enumerate(self.x["linhas"]):
            self.assertTrue(linha[i_mat], f"linha {n} sem matrícula")
            self.assertTrue(linha[i_nome], f"linha {n} sem nome")

    def test_filtrar_por_sistema_ainda_mostra_a_pessoa(self):
        i_sis, i_nome = self.cols.index("Sistema"), self.cols.index("Nome")
        so_sigot = [l for l in self.x["linhas"] if l[i_sis] == "SIGOT"]
        self.assertTrue(so_sigot)
        for l in so_sigot:
            self.assertEqual(l[i_nome], "JOSE DA SILVA")

    def test_formato_condicional_aponta_para_situacao(self):
        self.assertEqual(self.x["formatos"][0]["col"], self.cols.index("Situação"))

    def test_agrupamento_preservado(self):
        self.assertEqual(self.x["niveis"][0], 0)
        self.assertIn(1, self.x["niveis"])


if __name__ == "__main__":
    unittest.main()
