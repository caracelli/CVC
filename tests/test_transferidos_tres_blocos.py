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
class ResumoPorSistema(unittest.TestCase):
    """15/10/2026 — RESUMO POR SISTEMA (chamada com a Bruna; mockup aprovado).

    MUDOU DE PROPÓSITO: a tabela de 4 colunas de 23/09 (Sistema | Tem
    atualmente | Mapeando nova área | Incluir/excluir/alterar) deu lugar a um
    resumo no padrão da Consulta. "A visualização ficou boa, mas não está
    atendendo 100% ao processo": a pessoa com IC CADASTRO, que a nova área
    permite, aparecia com CONSULTA em "falta" e "Incluir". Agora cada sistema
    tem UMA situação — Aderente (+ "pode ter também"), Trocar, Incluir,
    Excluir, Sem mapeamento — e o detalhe vai para abas. O que os testes de
    23/09 garantiam e continua valendo (login por sistema, todos os sistemas
    na foto, a ação no sistema certo, "validado" sem diferença, contadores da
    revalidação) foi reescrito aqui sobre o formato novo."""

    def _js(self, corpo, multi_fora=("ORACLE_EBS",)):
        return (_BASE_JS
                + f"const DB = {{meta: {{multi_perfil_fora: {json.dumps(list(multi_fora))}}}}};\n"
                + f"{_funcao('_acessosPorSistema')}\n{_funcao('_transfResumoSis')}\n"
                + f"{_funcao('_transfMultiFora')}\n{_funcao('_transfAcoes')}\n"
                + f"{_funcao('_transfDetalhe')}\n" + corpo)

    def _detalhe(self, reg):
        return _node(self._js(f"const d = {json.dumps(reg)};\n"
                              "console.log(_transfDetalhe(d, d.acessos, d.sobrou||[]));"))

    def _resumo(self, reg):
        out = _node(self._js(f"const d = {json.dumps(reg)};\n"
                             "console.log(JSON.stringify(_transfResumoSis(d, _sisTodos(), _transfMultiFora())));"))
        return {x["s"]: x for x in json.loads(out)}

    def _linha(self, html, sis):
        m = re.search(r'<div class="tr-lin"><span><span class="h-sis">' + sis
                      + r'</span>.*?(?=<div class="tr-lin">|<div class="tr-nota">|<button)', html, re.S)
        self.assertTrue(m, f"linha do {sis} não encontrada")
        return m.group(0)

    # ── o caso da chamada ──────────────────────────────────────────────
    def test_tem_o_permitido_e_aderente_e_o_resto_e_pode_ter_tambem(self):
        """⭐ O caso da Bruna: tem IC CADASTRO, a nova área prevê CADASTRO ou
        CONSULTA. Não falta nada — CONSULTA é "pode ter também"."""
        reg = dict(REG, acessos=[{"sis": "IC_INTEGRADOR_CONTABIL", "login": "u1",
                                  "perfil": "IC_CADASTRO", "dt": ""}],
                   reval={"MANTEM": 1, "SOBROU": 0, "EXCESSO": 0, "FALTA": 1},
                   mantem=[{"sis": "IC_INTEGRADOR_CONTABIL", "perfil": "IC_CADASTRO", "fun": ""}],
                   sobrou=[], excesso=[],
                   falta=[{"sis": "IC_INTEGRADOR_CONTABIL", "perfil": "IC CONSULTA", "fun": ""}])
        r = self._resumo(reg)["IC_INTEGRADOR_CONTABIL"]
        self.assertEqual(r["st"], "ok")
        self.assertEqual([x["perfil"] for x in r["tambem"]], ["IC CONSULTA"])
        self.assertEqual(r["incluir"], [])
        html = self._detalhe(reg)
        linha = self._linha(html, "IC_INTEGRADOR_CONTABIL")
        self.assertIn("Aderente", linha)
        self.assertIn("pode ter também", linha)
        self.assertNotIn("Incluir", linha)
        self.assertIn("Aderente na nova área, nada a alterar", html)

    def test_sem_o_permitido_a_regra_e_trocar(self):
        """"Se ele não tiver o acesso, tem que excluir o que ele tem e colocar o
        novo": SOBROU + FALTA no mesmo sistema = Trocar."""
        reg = dict(REG, acessos=[{"sis": "SYSTUR", "login": "u1", "perfil": "VENDAS", "dt": ""}],
                   mantem=[], excesso=[],
                   sobrou=[{"sis": "SYSTUR", "perfil": "VENDAS", "fun": ""}],
                   falta=[{"sis": "SYSTUR", "perfil": "A_RECEBER_1", "fun": "A Receber 1"},
                          {"sis": "SYSTUR", "perfil": "A_RECEBER_2", "fun": "A Receber 1"}])
        r = self._resumo(reg)["SYSTUR"]
        self.assertEqual(r["st"], "troca")
        self.assertTrue(r["umDe"], "só um perfil por sistema: incluir UM das opções")
        linha = self._linha(self._detalhe(reg), "SYSTUR")
        self.assertIn("Trocar", linha)
        self.assertIn("Excluir", linha)
        self.assertIn("Incluir</span> um de:", linha)
        self.assertIn("A Receber 1", linha, "a função da CCO precisa aparecer")

    def test_fora_do_padrao_sem_o_permitido_tambem_e_troca(self):
        reg = dict(REG, acessos=[{"sis": "SYSTUR", "login": "u1", "perfil": "X", "dt": ""}],
                   mantem=[], sobrou=[], excesso=[{"sis": "SYSTUR", "perfil": "X"}],
                   falta=[{"sis": "SYSTUR", "perfil": "CUSTOS", "fun": ""}])
        r = self._resumo(reg)["SYSTUR"]
        self.assertEqual(r["st"], "troca")
        self.assertEqual([x["perfil"] for x in r["excluir"]], ["X"])

    def test_oracle_cada_perfil_e_um_acesso(self):
        """multi_perfil_fora: no Oracle ter um perfil não dispensa os outros —
        o que falta continua sendo Incluir, não "pode ter também"."""
        reg = dict(REG, acessos=[{"sis": "ORACLE_EBS", "login": "u1", "perfil": "A", "dt": ""}],
                   mantem=[{"sis": "ORACLE_EBS", "perfil": "A"}], sobrou=[], excesso=[],
                   falta=[{"sis": "ORACLE_EBS", "perfil": "B", "fun": ""},
                          {"sis": "ORACLE_EBS", "perfil": "C", "fun": ""}])
        r = self._resumo(reg)["ORACLE_EBS"]
        self.assertEqual(r["st"], "inc")
        self.assertFalse(r["umDe"])
        self.assertEqual(r["tambem"], [])

    def test_sig_espelho_cada_perfil_e_um_acesso(self):
        reg = dict(REG, acessos=[{"sis": "SIG", "login": "u1", "perfil": "A", "dt": ""}],
                   mantem=[{"sis": "SIG", "perfil": "A", "origem": "ESPELHO"}], sobrou=[], excesso=[],
                   falta=[{"sis": "SIG", "perfil": "B", "origem": "ESPELHO", "fun": ""}])
        self.assertEqual(self._resumo(reg)["SIG"]["st"], "inc")

    def test_a_acao_cai_no_sistema_certo(self):
        """Era a ação de antes e continua: o SIGOT tem o que excluir, o
        Oracle o que incluir, o SYSTUR nada."""
        html = self._detalhe(REG)
        self.assertIn("Excluir", self._linha(html, "SIGOT"))
        self.assertNotIn("Excluir", self._linha(html, "ORACLE_EBS"))
        self.assertIn("Incluir", self._linha(html, "ORACLE_EBS"))
        self.assertNotIn("Incluir", self._linha(html, "SYSTUR"))
        self.assertIn("Controle de pagamentos AP/AR", html, "a função do CCO precisa aparecer")

    def test_sistema_sem_extrato_nao_vira_acao(self):
        """Opera Operacional: a CCO prevê, mas não há extrato (fora de escopo).
        Igual à Consulta: informativo, fora da contagem de ações."""
        reg = dict(REG, acessos=[], mantem=[], sobrou=[], excesso=[],
                   falta=[{"sis": "OPERA_OPERACIONAL", "perfil": "P1", "fun": ""}])
        self.assertEqual(self._resumo(reg)["OPERA_OPERACIONAL"]["st"], "sext")
        html = self._detalhe(reg)
        self.assertIn("Sem extrato", html)
        self.assertNotIn("a fazer</span>", html.replace("nada a fazer", ""))

    # ── o que já valia e continua ──────────────────────────────────────
    def test_todos_os_sistemas_aparecem_inclusive_os_vazios(self):
        """A área pediu uma FOTO: o sistema sem nada é informação."""
        html = self._detalhe(REG)
        for sis in ("ORACLE_EBS", "SICA_RA", "SICA_ESFERA", "SIGOT",
                    "IC_INTEGRADOR_CONTABIL", "SYSTUR", "SIG"):
            self.assertIn(f">{sis}</span>", html)
        self.assertIn("Sem mapeamento", html)

    def test_o_login_de_cada_sistema_nao_se_perde(self):
        html = self._detalhe(REG)
        self.assertIn("login: CORPC90000416", html)
        self.assertIn("login: corpc90000416", html)

    def test_contadores_da_revalidacao_continuam_no_detalhe(self):
        html = self._detalhe(REG)
        self.assertIn("mantêm", html)
        self.assertIn("sobraram da anterior", html)
        self.assertIn("faltando na nova", html)

    def test_detalhe_em_quatro_abas(self):
        html = self._detalhe(REG)
        for aba in ("Tem hoje", "Previsto na nova área", "Sem mapeamento", "Funções previstas"):
            self.assertIn(f">{aba}</div>", html)

    def test_veredito_conta_as_acoes(self):
        self.assertIn("2 ações a fazer", self._detalhe(REG))

    def test_muitos_perfis_recolhem(self):
        """O Oracle chega a 45 perfis numa pessoa: a linha não pode estourar."""
        reg = dict(REG, acessos=[{"sis": "ORACLE_EBS", "login": "c", "perfil": f"P{i}", "dt": ""}
                                 for i in range(6)],
                   mantem=[{"sis": "ORACLE_EBS", "perfil": f"P{i}"} for i in range(6)])
        linha = self._linha(self._detalhe(reg), "ORACLE_EBS")
        self.assertIn("6 perfis", linha)
        for i in range(6):
            self.assertIn(f"P{i}", linha, "recolhido, mas nenhum some")

    def test_banco_anterior_sem_lista_mantem(self):
        """Sem `mantem` (visualizador novo, banco velho): o que tem e não sobrou,
        mantém — a conta de antes."""
        r = self._resumo(REG)
        self.assertEqual(r["SYSTUR"]["st"], "ok")
        self.assertEqual(r["SIGOT"]["st"], "exc")

    def test_selo_da_linha(self):
        out = _node(self._js(f"const d = {json.dumps(REG)};\n"
                             "console.log(_transfAcoes(d), _transfAcoes(Object.assign({}, d, {sem_acesso: true})));"))
        self.assertEqual(out.split(), ["2", "null"])


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


    def test_opcao_de_sistema_aderente_nao_sai_como_incluir(self):
        """15/10: na planilha, a outra opção do sistema em que ela já é
        aderente sai como "pode ter também", não "falta (incluir)"."""
        reg = dict(REG, mantem=[{"sis": "SYSTUR", "perfil": "INTEGRADOR_CONTABIL"}],
                   falta=REG["falta"] + [{"sis": "SYSTUR", "perfil": "CUSTOS", "fun": ""}])
        cap = self._export(reg)
        ic = cap["cols"].index("Situação do acesso")
        pc = cap["cols"].index("Perfil")
        sit = {l[pc]: l[ic] for l in cap["linhas"] if l[pc]}
        self.assertEqual(sit["CUSTOS"], "pode ter também (não precisa incluir)")
        self.assertEqual(sit["CVC AP BRASIL Consulta"], "falta (incluir)")

    def test_fora_do_padrao_nao_sai_como_mantem(self):
        reg = dict(REG, excesso=[{"sis": "SYSTUR", "perfil": "INTEGRADOR_CONTABIL"}])
        cap = self._export(reg)
        ic = cap["cols"].index("Situação do acesso")
        pc = cap["cols"].index("Perfil")
        sit = {l[pc]: l[ic] for l in cap["linhas"] if l[pc]}
        self.assertEqual(sit["INTEGRADOR_CONTABIL"], "fora do padrão")


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

    def test_mantem_e_excesso_vao_como_lista(self):
        """O resumo por sistema (15/10) precisa saber, sistema a sistema, se a
        pessoa já tem um perfil previsto: MANTEM e EXCESSO vão como lista."""
        c = sqlite3.connect(self.db)
        try:
            c.execute("INSERT INTO revalidacao_transferido (matricula, sistema, perfil, "
                      "situacao, origem) VALUES ('M1','SYSTUR','P1','MANTEM','MATRIZ/CCO'),"
                      "('M1','SYSTUR','P9','EXCESSO','MATRIZ/CCO')")
            c.commit()
        finally:
            c.close()
        p = vm.listar_transferidos()["lista"][0]
        self.assertEqual([x["perfil"] for x in p["mantem"]], ["P1"])
        self.assertEqual([x["perfil"] for x in p["excesso"]], ["P9"])
        self.assertEqual(p["reval"]["MANTEM"], 1)

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
