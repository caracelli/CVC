# -*- coding: utf-8 -*-
"""Transferidos em 3 blocos + planilha alinhada (retorno da área, 17/09/2026).

"Essa visualização está muito confusa. Quando o usuário é transferido precisamos
ter uma foto: o que ele tem de acesso; o que, cruzando com as matrizes, ele pode
ter segundo os novos cargos, gestores e cc; e os acessos que precisa alterar — a
diferença. Qual a matriz de acessos (cco ou sistema), qual a função? Se a pessoa
não tiver alterações... trazer ok apenas para validação. Obs.: a informação que
vem na planilha vem mais confusa que na visualização."

O dado já existia (`transferidos` e `revalidacao_transferido`, Card 23); o que
faltava era a LEITURA. Nada do que a aba mostrava saiu — os contadores e a lista
por sistema continuam, agora dentro dos blocos.
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


def _node(js):
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


_BASE_JS = ("const esc = s => String(s == null ? '' : s);\n"
            "const fmtDate = s => String(s || '');\n"
            # `_perfisCel` usa este contador global ao dobrar a lista em "+N
            # perfis" (mais de 4 no mesmo sistema). Sem ele o teste só exercita
            # o caminho curto — foi o que a bateria na base real pegou em 18/09.
            "let _grpSeq = 0;\n")

REG = {
    "m": "90000416", "n": "FILIPE NOGUEIRA", "cargo": "ANALISTA CONTABIL PL",
    "cc": "01.02.02.11", "gestor": "LAERCIO WASQUES", "campos": "cargo, departamento",
    "dt_mov": "2026-08-18", "tratado": False, "tratamento": {},
    "de_para": [{"campo": "cargo", "de": "ANALISTA CUSTOS PL", "para": "ANALISTA CONTABIL PL"}],
    "acessos": [
        {"sis": "SYSTUR", "login": "CORPC90000416", "perfil": "INTEGRADOR_CONTABIL", "dt": "2026-09-15"},
        {"sis": "SIGOT", "login": "corpc90000416", "perfil": "Contabil1", "dt": "2026-09-15"},
    ],
    "reval": {"MANTEM": 1, "SOBROU": 1, "EXCESSO": 0, "FALTA": 1},
    "sobrou": [{"sis": "SIGOT", "perfil": "Contabil1", "origem": "", "fun": "Custos"}],
    "falta": [{"sis": "ORACLE_EBS", "perfil": "CVC AP BRASIL Consulta", "origem": "",
               "fun": "Controle de pagamentos AP/AR"}],
    "pares": [4, 6],
}


@unittest.skipUnless(NODE, "Node não disponível nesta máquina")
class TresBlocosNaTela(unittest.TestCase):

    def _detalhe(self, reg):
        js = (_BASE_JS
              + f"{_funcao('_acessosPorSistema')}\n{_funcao('_perfisCel')}\n"
              + f"{_funcao('_transfChave')}\n{_funcao('_transfTit')}\n"
              + f"{_funcao('_transfItem')}\n{_funcao('_transfDetalhe')}\n"
              + f"const d = {json.dumps(reg)};\n"
              + "console.log(_transfDetalhe(d, d.acessos, d.sobrou||[]));")
        return _node(js)

    def test_os_tres_blocos_na_ordem_que_ela_pediu(self):
        html = self._detalhe(REG)
        i1 = html.index("acessos que o colaborador tem")
        i2 = html.index("acessos que deveria ter na nova área")
        i3 = html.index("o que precisa alterar")
        self.assertLess(i1, i2)
        self.assertLess(i2, i3)

    def test_o_que_alterar_diz_revogar_incluir_e_a_funcao(self):
        html = self._detalhe(REG)
        self.assertIn("revogar", html)
        self.assertIn("incluir", html)
        self.assertIn("Controle de pagamentos AP/AR", html, "a função do CCO precisa aparecer")

    def test_o_que_ele_tem_continua_listado_por_sistema(self):
        """O que já existia não pode sumir: a lista por sistema continua."""
        html = self._detalhe(REG)
        self.assertIn("SYSTUR", html)
        self.assertIn("SIGOT", html)

    def test_contadores_da_revalidacao_continuam(self):
        html = self._detalhe(REG)
        self.assertIn("mantêm", html)
        self.assertIn("sobraram da anterior", html)
        self.assertIn("faltando na nova", html)

    def test_muitos_perfis_no_mesmo_sistema(self):
        """Mais de 4 perfis no mesmo sistema dobra a lista em "+N perfis" — na
        base do cliente isso é comum (o FILIPE tem 21 acessos só no Oracle)."""
        reg = dict(REG, acessos=[
            {"sis": "ORACLE_EBS", "login": "CORPC1", "perfil": f"CVC GL PERFIL {i}",
             "dt": "2026-09-15"} for i in range(6)])
        html = self._detalhe(reg)
        self.assertIn("perfis", html)
        self.assertIn("acessos que o colaborador tem (6)", html)

    def test_sem_diferenca_diz_validado(self):
        """"Se a pessoa não tiver alterações... trazer ok apenas para validação"."""
        reg = dict(REG, sobrou=[], falta=[], reval={"MANTEM": 2, "SOBROU": 0,
                                                    "EXCESSO": 0, "FALTA": 0})
        html = self._detalhe(reg)
        self.assertIn("Validado", html)
        self.assertNotIn("o que precisa alterar", html)


@unittest.skipUnless(NODE, "Node não disponível nesta máquina")
class PlanilhaAlinhadaComATela(unittest.TestCase):

    def _export(self, reg):
        js = (_BASE_JS
              + f"{_funcao('_acessosPorSistema')}\n{_funcao('_transfChave')}\n"
              + f"const _recs = [{json.dumps(reg)}];\n"
              + "function _transfFiltrados(){ return _recs; }\n"
              + "let capturado = null;\n"
              + "function baixarExcel(nome, cols, linhas, niveis, formatos){"
              + " capturado = {cols: cols, linhas: linhas, niveis: niveis}; }\n"
              + f"{_funcao('exportarTransferidos')}\n"
              + "exportarTransferidos();\nconsole.log(JSON.stringify(capturado));")
        return json.loads(_node(js))

    def test_toda_linha_tem_o_tamanho_do_cabecalho(self):
        """Acrescentar coluna e esquecer uma linha desalinha a planilha inteira."""
        cap = self._export(REG)
        for i, l in enumerate(cap["linhas"]):
            self.assertEqual(len(l), len(cap["cols"]), f"linha {i} desalinhada")

    def test_colunas_antigas_nao_mudam_de_posicao(self):
        """Quem já tem filtro salvo na planilha continua funcionando."""
        cap = self._export(REG)
        self.assertEqual(cap["cols"][:6],
                         ["Matrícula", "Nome", "Cargo", "Centro de Custo", "Gestor", "Mudança"])
        self.assertEqual(cap["cols"][-2:], ["Situação do acesso", "Função (CCO)"])

    def test_planilha_diz_manter_revogar_e_incluir(self):
        cap = self._export(REG)
        sits = {l[cap["cols"].index("Situação do acesso")] for l in cap["linhas"]}
        self.assertIn("mantém", sits)
        self.assertIn("sobrou (revogar)", sits)
        self.assertIn("falta (incluir)", sits)

    def test_a_funcao_vai_na_linha_do_que_falta(self):
        cap = self._export(REG)
        ic = cap["cols"].index("Situação do acesso")
        fc = cap["cols"].index("Função (CCO)")
        falta = [l for l in cap["linhas"] if l[ic] == "falta (incluir)"]
        self.assertTrue(falta)
        self.assertEqual(falta[0][fc], "Controle de pagamentos AP/AR")


class FuncaoNoVeredito(unittest.TestCase):
    """O servidor precisa achar a função do CCO pelo (cc, gestor) da pessoa."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cvc_transf_")
        self.db = os.path.join(self.tmp, "iam.db")
        ConexaoBancoDados(self.db).inicializar()
        self._orig = (vm.DB_PATH, vm.SISTEMA)
        vm.DB_PATH, vm.SISTEMA = self.db, ""
        c = sqlite3.connect(self.db)
        try:
            c.execute("INSERT INTO rh_ativos (matricula, nome, cpf, cargo_descricao, "
                      "centro_custo_codigo, gestor, situacao) VALUES "
                      "('M1','FULANO','00000000001','ANALISTA','01.06.04.01','HELEN','ATIVO')")
            c.execute("INSERT INTO matriz_cco (cc, cc_nome, gestor, funcao, sistema, perfil) "
                      "VALUES ('01.06.04.01','CONTAS A PAGAR','HELEN',"
                      "'Atendimento a fornecedores  CVC e VISUAL','Oracle EBS','CVC AP BRASIL Consulta')")
            c.execute("INSERT INTO divergencias (id, tipo, sistema, usuario, nome_usuario, "
                      "matricula, perfil_encontrado, data_identificacao, resolvida, descricao) "
                      "VALUES ('d1','ACESSO_TRANSFERIDO','SYSTUR','u1','FULANO','M1','P1',"
                      "'2026-09-15',0,'Mudança de cargo — x')")
            c.execute("INSERT INTO revalidacao_transferido (matricula, sistema, perfil, "
                      "situacao, origem, pares_antes, pares_depois) VALUES "
                      "('M1','ORACLE_EBS','CVC AP BRASIL Consulta','FALTA','',4,6)")
            c.commit()
        finally:
            c.close()

    def tearDown(self):
        vm.DB_PATH, vm.SISTEMA = self._orig

    def test_falta_vem_com_a_funcao_da_cco(self):
        d = vm.listar_transferidos()
        pessoa = d["lista"][0]
        self.assertEqual(pessoa["falta"][0]["fun"],
                         "Atendimento a fornecedores  CVC e VISUAL")

    def test_sem_cco_o_campo_fica_vazio_sem_quebrar(self):
        c = sqlite3.connect(self.db)
        try:
            c.execute("DELETE FROM matriz_cco")
            c.commit()
        finally:
            c.close()
        self.assertEqual(vm.listar_transferidos()["lista"][0]["falta"][0]["fun"], "")


if __name__ == "__main__":
    unittest.main()
