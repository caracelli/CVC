"""Abertura de chamado no Jira — fluxo de desligados (Cards 25-26).

Cobre o que NAO pode quebrar em silencio:
  - o texto exato dos 3 campos do formulario 8819
  - a leitura do jira.xml e os estados de configuracao
  - a guarda de duplicata (a que impede dois chamados para o mesmo registro)
  - a consolidacao no Processador: PRIMEIRO vence e reprocessar nao reescreve

O Visualizador e' standalone (nao importavel como pacote), entao e' carregado
por caminho, como os demais testes de painel deste projeto.
"""
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))


def _carregar_visualizador():
    spec = importlib.util.spec_from_file_location(
        "vis_jira", str(RAIZ / "src" / "visualizador" / "main.py"))
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except SystemExit:
        pass
    return mod


VIS = _carregar_visualizador()


class TextoDoChamado(unittest.TestCase):
    """O texto vai para o cliente. Mudanca aqui e' mudanca de contrato com a
    area — se um destes quebrar, foi intencional ou e' regressao."""

    def test_titulo_identifica_na_fila(self):
        self.assertEqual(
            VIS.jira_titulo("SYSTUR", "AGATHA DIAS"),
            "Sanitização - SYSTUR - AGATHA DIAS")

    def test_titulo_trunca_em_255(self):
        t = VIS.jira_titulo("SYSTUR", "X" * 400)
        self.assertLessEqual(len(t), 255)

    def test_titulo_sem_dados_nao_quebra(self):
        self.assertEqual(VIS.jira_titulo("", ""), "Sanitização - ? - ?")

    def test_descricao_um_perfil(self):
        d = VIS.jira_descricao([("AGATHA DIAS", "INTADM333", "UX_E_UI")],
                               "Desligamento: 30/06/2025", "Revogar.")
        self.assertEqual(d, "\n".join([
            "Prezados,", "Revogar o usuario abaixo:", "",
            "NOME | LOGIN | PERFIL",
            "AGATHA DIAS | INTADM333 | UX_E_UI",
            "", "Desligamento: 30/06/2025",
            "", "Parecer do analista:", "Revogar."]))

    def test_descricao_varios_perfis_uma_linha_cada(self):
        """Um chamado por (usuario, sistema): N perfis viram N linhas, nao N
        chamados."""
        d = VIS.jira_descricao(
            [("LETICIA", "CORPC1", "PAGAMENTOS_NACIONAIS_CP"),
             ("LETICIA", "CORPC1", "SUPORTE_N1_CP")], "", "")
        self.assertIn("LETICIA | CORPC1 | PAGAMENTOS_NACIONAIS_CP", d)
        self.assertIn("LETICIA | CORPC1 | SUPORTE_N1_CP", d)

    def test_descricao_sem_contexto_nem_parecer(self):
        d = VIS.jira_descricao([("A", "B", "C")])
        self.assertNotIn("Parecer do analista", d)
        self.assertTrue(d.endswith("A | B | C"))

    def test_data_br(self):
        self.assertEqual(VIS._data_br("2025-06-30"), "30/06/2025")
        self.assertEqual(VIS._data_br("2025-06-30 00:00:00"), "30/06/2025")
        self.assertEqual(VIS._data_br(""), "")
        self.assertEqual(VIS._data_br("30/06/2025"), "30/06/2025")


class Configuracao(unittest.TestCase):
    """Sem tela de teste, o jira.xml errado so' aparece no diagnostico."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self._xml = VIS.JIRA_XML_LOCAL
        self._rede = VIS.REDE_RAIZ
        self._jira = VIS.JIRA
        VIS.JIRA_XML_LOCAL = os.path.join(self.dir, "jira.xml")
        VIS.REDE_RAIZ = ""

    def tearDown(self):
        VIS.JIRA_XML_LOCAL, VIS.REDE_RAIZ, VIS.JIRA = self._xml, self._rede, self._jira

    def _escrever(self, conteudo):
        with open(VIS.JIRA_XML_LOCAL, "w", encoding="utf-8") as f:
            f.write(conteudo)

    def _diag(self):
        VIS.JIRA = VIS.carregar_config_jira()
        return VIS.jira_diagnostico()

    def test_sem_arquivo(self):
        self.assertIn("nao configurado", self._diag())
        self.assertFalse(VIS.jira_habilitado())

    def test_desligado_mesmo_com_credencial(self):
        self._escrever("<jira><ativo>false</ativo><usuario>a@b</usuario>"
                       "<token>t</token><url>u</url>"
                       "<service_desk_id>9</service_desk_id>"
                       "<request_type_id>8819</request_type_id></jira>")
        self.assertIn("desligado", self._diag())
        self.assertFalse(VIS.jira_habilitado())

    def test_ativo_sem_token_nao_habilita(self):
        self._escrever("<jira><ativo>true</ativo><usuario>a@b</usuario>"
                       "<url>u</url><service_desk_id>9</service_desk_id>"
                       "<request_type_id>8819</request_type_id></jira>")
        self.assertIn("INCOMPLETO", self._diag())
        self.assertIn("token", self._diag())
        self.assertFalse(VIS.jira_habilitado())

    def test_completo_habilita(self):
        self._escrever("<jira><ativo>true</ativo><usuario>svc@cvc</usuario>"
                       "<token>t</token><url>https://x</url>"
                       "<service_desk_id>9</service_desk_id>"
                       "<request_type_id>8819</request_type_id></jira>")
        self.assertIn("ativo", self._diag())
        self.assertTrue(VIS.jira_habilitado())

    def test_xml_invalido_nao_derruba_o_painel(self):
        self._escrever("<jira><ativo>true")
        self.assertIn("ERRO", self._diag())
        self.assertFalse(VIS.jira_habilitado())


class GuardaDeDuplicata(unittest.TestCase):
    """A trava e' no SERVIDOR: a tela de um analista nao sabe do clique do
    outro, e o painel roda em varias maquinas contra a mesma pasta."""

    def setUp(self):
        self._orig = VIS.chamados_abertos
        self._post = VIS.jira_abrir_chamado
        self._jira = VIS.JIRA
        VIS.JIRA = dict(VIS.JIRA, ativo=True, url="https://x",
                        service_desk_id="9", request_type_id="8819",
                        usuario="svc@x", token="t")

    def tearDown(self):
        VIS.chamados_abertos = self._orig
        VIS.jira_abrir_chamado = self._post
        VIS.JIRA = self._jira

    def test_ja_existe_barra_antes_do_post(self):
        chamou = []
        VIS.jira_abrir_chamado = lambda t, d: chamou.append(1)
        VIS.chamados_abertos = lambda i=None: {
            "34531584": {"ticket": "GAAR-1487", "por": "bruna", "em": "2026-08-11"}}
        with self.assertRaises(VIS.JiraErro) as ctx:
            VIS.abrir_chamado_desligado("34531584", "parecer")
        self.assertIn("GAAR-1487", str(ctx.exception))
        self.assertEqual(chamou, [], "nao pode chamar o Jira se ja existe chamado")

    def test_sem_parecer_nao_abre(self):
        VIS.chamados_abertos = lambda i=None: {}
        with self.assertRaises(VIS.JiraErro):
            VIS.abrir_chamado_desligado("34531584", "   ")

    def test_sem_registro_nao_abre(self):
        with self.assertRaises(VIS.JiraErro):
            VIS.abrir_chamado_desligado("", "parecer")

    def test_primeiro_vence_e_le_de_todos_os_analistas(self):
        VIS.conn_ro = lambda: (_ for _ in ()).throw(Exception("sem banco"))
        VIS.REDE_RAIZ = ""
        inter = [
            {"tipo_interacao": "CHAMADO_ABERTO", "registro_id": "1",
             "ticket": "GAAR-2", "usuario": "joao",
             "data_acao": "2026-08-11T11:00:00"},
            {"tipo_interacao": "CHAMADO_ABERTO", "registro_id": "1",
             "ticket": "GAAR-1", "usuario": "bruna",
             "data_acao": "2026-08-11T09:00:00"},
        ]
        r = VIS.chamados_abertos(inter)
        self.assertEqual(r["1"]["ticket"], "GAAR-1")
        self.assertEqual(r["1"]["por"], "bruna")

    def test_interacao_sem_ticket_e_ignorada(self):
        VIS.conn_ro = lambda: (_ for _ in ()).throw(Exception("sem banco"))
        VIS.REDE_RAIZ = ""
        r = VIS.chamados_abertos(
            [{"tipo_interacao": "CHAMADO_ABERTO", "registro_id": "1", "ticket": ""}])
        self.assertEqual(r, {})


class ConsolidacaoNoProcessador(unittest.TestCase):
    """A tabela e' o que faz a guarda sobreviver ao reset da pasta INTERACOES."""

    def setUp(self):
        from aplicacao.casos_de_uso.dobrar_interacoes import _SQL_CHAMADOS
        self.db = os.path.join(tempfile.mkdtemp(), "t.db")
        self.c = sqlite3.connect(self.db)
        self.c.executescript(_SQL_CHAMADOS)

    def tearDown(self):
        self.c.close()

    def _inserir(self, rid, ticket):
        self.c.execute(
            "INSERT OR IGNORE INTO chamados_abertos (registro_id,fluxo,ticket,"
            "acessos) VALUES (?,?,?,?)", [rid, "DESLIGADO", ticket, json.dumps([])])

    def test_primeiro_vence(self):
        self._inserir("34531584", "GAAR-1")
        self._inserir("34531584", "GAAR-2")
        r = self.c.execute("SELECT ticket FROM chamados_abertos").fetchall()
        self.assertEqual(r, [("GAAR-1",)])

    def test_reprocessar_nao_duplica(self):
        for _ in range(3):
            self._inserir("34531584", "GAAR-1")
        n = self.c.execute("SELECT COUNT(*) FROM chamados_abertos").fetchone()[0]
        self.assertEqual(n, 1)


if __name__ == "__main__":
    unittest.main()
