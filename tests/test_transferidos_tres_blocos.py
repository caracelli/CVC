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

23/09/2026 — MESMAS PERGUNTAS, OUTRA LEITURA. A área voltou ao tema:

    "Transferidos: Trazer em linhas ao invés de em uma única linha
     Se der pra trazer em colunas pode ser tbm"

e mandou o desenho: Sistema | Tem atualmente | mapeando nova área |
Incluir/excluir/alterar acesso.

Os três blocos respondiam às três perguntas dela, mas como texto corrido dentro
de uma célula — que é o "uma única linha" da reclamação. Viraram uma TABELA:
uma linha por sistema, uma coluna por pergunta. Percorre TODOS os sistemas,
inclusive aqueles em que a pessoa não tem nada: ela pediu uma "foto", e "no
SICA Esfera não há nada a fazer" é informação.

O conteúdo é o mesmo; os testes de formato mudaram junto e dizem por quê.
"""
import json
import os
import re
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
            "let _grpSeq = 0;\n"
            # Universo de sistemas: na tela sai de DB.users; aqui e' fixo. A
            # "foto por sistema" de 23/09 percorre TODOS, inclusive os que a
            # pessoa nao tem — e' o ponto do formato novo.
            "const _sisTodos = () => ['ORACLE_EBS','SICA_RA','SICA_ESFERA',"
            "'SIGOT','IC_INTEGRADOR_CONTABIL','SYSTUR','SIG'];\n")

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

    # ── formato de 23/09/2026 ────────────────────────────────────────────
    # A area voltou ao tema: "Transferidos: Trazer em linhas ao inves de em uma
    # unica linha / Se der pra trazer em colunas pode ser tbm", com o desenho
    # Sistema | Tem atualmente | mapeando nova area | Incluir/excluir/alterar
    # acesso.
    #
    # As TRES PERGUNTAS de 17/09 continuam as mesmas — o que ele tem, o que a
    # nova area preve, o que mudar. O que mudou foi a LEITURA: eram tres blocos
    # de texto corrido dentro de uma celula (o "uma unica linha" que ela
    # reclamou) e viraram uma linha por sistema, uma coluna por pergunta.
    # Os testes abaixo trocaram de forma pelo mesmo motivo; o CONTEUDO que eles
    # garantem e' o mesmo.

    def test_as_tres_perguntas_viraram_as_colunas_que_ela_desenhou(self):
        html = self._detalhe(REG)
        for coluna in ("Sistema", "Tem atualmente", "Mapeando nova área",
                       "Incluir/excluir/alterar acesso"):
            self.assertIn(f"<th>{coluna}</th>", html)
        i1 = html.index("<th>Tem atualmente</th>")
        i2 = html.index("<th>Mapeando nova área</th>")
        i3 = html.index("<th>Incluir/excluir/alterar acesso</th>")
        self.assertLess(i1, i2)
        self.assertLess(i2, i3)

    def test_uma_linha_por_sistema_inclusive_os_vazios(self):
        """⭐ O coracao do pedido. A area quer uma FOTO: o sistema em que nao ha'
        nada a fazer e' informacao, nao ausencia dela."""
        html = self._detalhe(REG)
        for sis in ("ORACLE_EBS", "SICA_RA", "SICA_ESFERA", "SIGOT",
                    "IC_INTEGRADOR_CONTABIL", "SYSTUR", "SIG"):
            self.assertIn(f'<td class="tr-sis">{sis}', html)

    def test_o_login_de_cada_sistema_nao_se_perde(self):
        """Quase se perdeu na troca de formato (23/09): o bloco antigo mostrava
        "login: X" por sistema e a primeira versao da tabela o deixou de fora.
        E' por ele que se acha a conta DENTRO do sistema — sem isso a analista
        sabe o que revogar, mas nao em qual conta."""
        html = self._detalhe(REG)
        self.assertIn("login: CORPC90000416", html)
        self.assertIn("login: corpc90000416", html)

    def test_a_acao_usa_as_palavras_dela(self):
        """O cabecalho que ela escreveu e' "Incluir/excluir/alterar acesso" —
        a coluna fala "Excluir"/"Incluir", nao mais "revogar"."""
        html = self._detalhe(REG)
        self.assertIn("Excluir", html)
        self.assertIn("Incluir", html)
        self.assertIn("Controle de pagamentos AP/AR", html,
                      "a função do CCO precisa aparecer")

    def test_a_acao_cai_na_linha_do_sistema_certo(self):
        """Sem isto a tabela seria so' enfeite: o SIGOT e' que tem o acesso a
        excluir, e o Oracle o a incluir."""
        html = self._detalhe(REG)
        linhas = dict(re.findall(
            r'<td class="tr-sis">([A-Z_]+)(?:<div[^>]*>.*?</div>)?</td>'
            r'(.*?)</tr>', html, re.S))
        self.assertIn("Excluir", linhas["SIGOT"])
        self.assertNotIn("Excluir", linhas["ORACLE_EBS"])
        self.assertIn("Incluir", linhas["ORACLE_EBS"])
        self.assertNotIn("Incluir", linhas["SYSTUR"])

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
        """Na base do cliente isso e' comum (o FILIPE tem 21 acessos so' no
        Oracle, a GILDA 46 no total).

        MUDOU DE PROPOSITO em 23/09: ate' aqui a lista dobrava em "+N perfis"
        porque era texto corrido e ficava ilegivel. Na tabela cada perfil e'
        uma linha DENTRO da celula do sistema — dobrar seria desfazer o pedido
        ("trazer em linhas ao inves de em uma unica linha")."""
        reg = dict(REG, acessos=[
            {"sis": "ORACLE_EBS", "login": "CORPC1", "perfil": f"CVC GL PERFIL {i}",
             "dt": "2026-09-15"} for i in range(6)])
        html = self._detalhe(reg)
        linha = re.search(r'<td class="tr-sis">ORACLE_EBS(?:<div[^>]*>.*?</div>)?</td>(.*?)</tr>',
                          html, re.S).group(1)
        for i in range(6):
            self.assertIn(f"CVC GL PERFIL {i}", linha,
                          "cada perfil precisa aparecer, um por linha")
        self.assertEqual(linha.count('class="tr-cel-i"'), 6 + (6 + 1) + 1,
                         "coluna 'tem': os 6; coluna 'nova area': os 6 que ele "
                         "mantem MAIS o que falta; coluna 'acao': o incluir. "
                         "O que falta conta duas vezes de proposito — ele e' "
                         "previsto na nova area E gera acao.")

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
