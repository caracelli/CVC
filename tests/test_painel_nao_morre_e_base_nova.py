# -*- coding: utf-8 -*-
"""O painel parava de responder quando a janela ia para segundo plano.

Retorno da area em 23/09/2026, textual:

    "O Programa ainda fica dando erro ao pular as janelas, ai precisa ficar
     fechando e abrindo ele de novo"

Investigado em 23/09 e eram DOIS defeitos somados:

1. WATCHDOG DE 300 s. O painel manda um sinal de vida a cada 4 s
   (setInterval no index.html), mas o navegador CONGELA a aba quando a janela
   fica atras de outra (guias em suspensao do Edge, congelamento do Chrome) —
   e a maquina bloqueada para tudo. Passados 5 minutos o servidor encerrava; a
   aba seguia aberta e TODA chamada passava a falhar.
   Reproduzido: parado o sinal, a porta deixava de atender em 300 s.

2. DOIS SERVIDORES NA MESMA PORTA. O `HTTPServer` do Python liga
   `allow_reuse_address`, e no WINDOWS isso deixa um segundo processo ligar na
   MESMA porta. Medido: duas instancias abriram em 127.0.0.1 sem erro nenhum.
   O navegador cai ora num ora no outro, e o beacon de "fechei a pagina" do
   painel VELHO pode ser entregue ao painel NOVO, que encerra na hora — ou
   seja, o proprio "fechar e abrir de novo" recriava o problema.

E, junto, o pedido do usuario no mesmo dia: "acho interessante um monitoramento
de a base alterou e se caso altere aparecer uma mensagem perguntando se quer
atualizar". O painel AVISA e pergunta; nao troca sozinho.
"""
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import visualizador.main as vm  # noqa: E402


class OWatchdogNaoDerrubaAJanelaEmSegundoPlano(unittest.TestCase):

    def _ocioso(self, xml):
        tmp = Path(tempfile.mkdtemp(prefix="cvc_oc_")) / "config.xml"
        tmp.write_text(xml, encoding="utf-8")
        antes = vm.CONFIG_PATH
        try:
            vm.CONFIG_PATH = str(tmp)
            return vm._ler_ocioso()
        finally:
            vm.CONFIG_PATH = antes

    def test_o_config_de_producao_da_horas_e_nao_minutos(self):
        """⭐ O numero que causava o defeito era 300. Qualquer valor abaixo de
        uma hora traz o problema de volta: a janela em segundo plano passa
        facil de 5, 10, 30 minutos."""
        antes = vm.CONFIG_PATH
        try:
            vm.CONFIG_PATH = str(
                RAIZ / "CVC_IAM_ANALYTICS/EXECUTAVEIS/CONFIG/config.xml")
            self.assertGreaterEqual(vm._ler_ocioso(), 3600)
        finally:
            vm.CONFIG_PATH = antes

    def test_zero_desliga_o_encerramento_por_ociosidade(self):
        self.assertEqual(self._ocioso(
            "<configuracao><visualizador><ociosidade_segundos>0"
            "</ociosidade_segundos></visualizador></configuracao>"), 0)

    def test_config_sem_a_chave_usa_o_padrao(self):
        self.assertEqual(
            self._ocioso("<configuracao><versao>1.0.0</versao></configuracao>"),
            vm._OCIOSO_PADRAO)

    def test_valor_invalido_cai_no_padrao(self):
        for v in ("abc", "", "-5"):
            with self.subTest(valor=v):
                self.assertEqual(self._ocioso(
                    "<configuracao><visualizador><ociosidade_segundos>"
                    f"{v}</ociosidade_segundos></visualizador></configuracao>"),
                    vm._OCIOSO_PADRAO)

    def test_o_padrao_do_codigo_nao_volta_a_ser_minutos(self):
        """Trava o numero no codigo, e nao so' no XML: um config perdido nao
        pode ressuscitar o defeito."""
        self.assertGreaterEqual(vm._OCIOSO_PADRAO, 3600)


class DuasCopiasNaoDisputamAPorta(unittest.TestCase):
    """No Windows o SO_REUSEADDR deixa dois processos ligarem na mesma porta.
    E' preciso que a segunda abertura receba um erro LIMPO."""

    def test_o_servidor_do_painel_desliga_o_reuso_de_endereco(self):
        from http.server import HTTPServer
        self.assertTrue(HTTPServer.allow_reuse_address,
                        "se o Python mudar o padrao, este teste perde o sentido")
        self.assertFalse(vm._Servidor.allow_reuse_address,
                         "com o reuso ligado, dois paineis dividem a porta")

    def test_a_segunda_abertura_recebe_erro(self):
        porta = 8971
        a = vm._Servidor((vm.HOST, porta), vm.H)
        try:
            with self.assertRaises(OSError):
                vm._Servidor((vm.HOST, porta), vm.H)
        finally:
            a.server_close()


class CederAPortaParaOPainelNovo(unittest.TestCase):
    """Com o watchdog em horas, uma copia esquecida pode continuar de pe'.
    Ate 23/09 isso fazia o exe FALHAR — trocava um transtorno por outro."""

    def test_nao_derruba_programa_que_nao_e_nosso(self):
        """So' pedimos a saida de quem se identifica como o Visualizador."""
        from http.server import BaseHTTPRequestHandler, HTTPServer

        class Outro(BaseHTTPRequestHandler):
            def do_GET(self):
                corpo = b'{"ok":true}'        # sem o campo `app`
                self.send_response(200)
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                self.wfile.write(corpo)

            def log_message(self, *a):
                pass

        porta, antes = 8972, vm.PORT
        srv = HTTPServer((vm.HOST, porta), Outro)
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        try:
            vm.PORT = porta
            self.assertFalse(vm._ceder_porta(espera_s=2),
                             "nao cabe a nos derrubar o programa de outra pessoa")
        finally:
            vm.PORT = antes
            srv.shutdown()
            srv.server_close()

    def test_porta_livre_tambem_devolve_falso(self):
        """Ninguem atendendo: nao ha' o que ceder (o bind vai falhar por outro
        motivo, e ai' a mensagem certa e' a de porta ocupada por terceiro)."""
        antes = vm.PORT
        try:
            vm.PORT = 8973
            self.assertFalse(vm._ceder_porta(espera_s=1))
        finally:
            vm.PORT = antes

    def test_o_ping_se_identifica(self):
        """E' o campo que permite reconhecer uma copia nossa."""
        self.assertEqual(vm._APP_ID, "cvc-iam-visualizador")
        self.assertIn('"app": _APP_ID',
                      (RAIZ / "src/visualizador/main.py").read_text(
                          encoding="utf-8"),
                      "o /api/ping precisa devolver o identificador")


class AvisarQueHaBaseNova(unittest.TestCase):
    """Pedido do usuario (23/09): avisar e PERGUNTAR, nao trocar sozinho.

    Seguro porque as tratativas nao moram no banco copiado — vao para os
    .jsonl da rede e sao lidas ao vivo."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cvc_bn_"))
        (self.tmp / "rede" / "DADOS" / "BANCO").mkdir(parents=True)
        (self.tmp / "local" / "DADOS" / "BANCO").mkdir(parents=True)
        self.rede_db = self.tmp / "rede" / "DADOS" / "BANCO" / "iam_analytics.db"
        cx = sqlite3.connect(self.rede_db)
        cx.execute("CREATE TABLE t (x TEXT)")
        cx.execute("INSERT INTO t VALUES ('carga 1')")
        cx.commit(); cx.close()
        self._salvo = (vm.REDE_RAIZ, vm.BANCO_SUB, vm.BANCO_LOCAL)
        vm.REDE_RAIZ = str(self.tmp / "rede")
        vm.BANCO_SUB = os.path.join("DADOS", "BANCO", "iam_analytics.db")
        vm.BANCO_LOCAL = str(self.tmp / "local" / "DADOS" / "BANCO"
                             / "iam_analytics.db")
        vm.sincronizar_banco()

    def tearDown(self):
        vm.REDE_RAIZ, vm.BANCO_SUB, vm.BANCO_LOCAL = self._salvo
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _nova_rodada(self, texto="carga 2"):
        time.sleep(1.1)          # mtime do SMB tem granularidade de segundo
        cx = sqlite3.connect(self.rede_db)
        cx.execute("INSERT INTO t VALUES (?)", (texto,))
        cx.commit(); cx.close()

    def test_sem_rodada_nova_nao_avisa(self):
        self.assertFalse(vm.base_da_rede_mudou())

    def test_rodada_nova_avisa(self):
        self._nova_rodada()
        self.assertTrue(vm.base_da_rede_mudou())

    def test_a_assinatura_muda_a_cada_rodada(self):
        """E' o que permite a tela lembrar o que foi dispensado, sem repetir a
        pergunta a cada 10 s — e voltar a perguntar na carga seguinte."""
        a = vm._assinatura_base_rede()
        self._nova_rodada()
        self.assertNotEqual(a, vm._assinatura_base_rede())

    def test_modo_local_nunca_avisa(self):
        salvo = vm.REDE_RAIZ
        try:
            vm.REDE_RAIZ = ""
            self.assertFalse(vm.base_da_rede_mudou())
            self.assertEqual(vm._assinatura_base_rede(), "")
        finally:
            vm.REDE_RAIZ = salvo

    def test_a_copia_e_atomica_e_a_falha_preserva_a_boa(self):
        """⭐ A copia ia DIRETO no cache local: rede caindo no meio destruia o
        banco que o painel estava servindo. Agora escreve ao lado e troca no
        fim."""
        tam = os.path.getsize(vm.BANCO_LOCAL)
        self._nova_rodada()
        os.rename(self.rede_db, str(self.rede_db) + ".sumiu")   # rede cai
        vm.sincronizar_banco()
        self.assertEqual(os.path.getsize(vm.BANCO_LOCAL), tam,
                         "a copia boa nao pode ser tocada quando a rede falha")
        cx = sqlite3.connect(vm.BANCO_LOCAL)
        self.assertEqual(cx.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        cx.close()
        self.assertFalse(os.path.exists(vm.BANCO_LOCAL + ".novo"),
                         "o arquivo temporario nao pode ficar para tras")

    def test_atualizar_traz_a_carga_nova(self):
        self._nova_rodada("carga 2")
        vm.sincronizar_banco()
        cx = sqlite3.connect(vm.BANCO_LOCAL)
        linhas = [r[0] for r in cx.execute("SELECT x FROM t").fetchall()]
        cx.close()
        self.assertIn("carga 2", linhas)
        self.assertFalse(vm.base_da_rede_mudou(), "depois de copiar, nao avisa mais")


class ATelaPerguntaAntesDeTrocar(unittest.TestCase):
    """A barra e' de aviso, nao janela modal: o Processador pode rodar enquanto
    alguem esta' no meio de uma analise."""

    @classmethod
    def setUpClass(cls):
        cls.html = (RAIZ / "CVC_IAM_ANALYTICS/EXECUTAVEIS/REPORT/index.html"
                    ).read_text(encoding="utf-8")

    def test_a_barra_existe_e_nasce_escondida(self):
        self.assertIn('id="base-nova"', self.html)
        self.assertRegex(self.html, r'id="base-nova"[^>]*style="display:none"')

    def test_tem_as_duas_escolhas(self):
        self.assertIn("aplicarBaseNova()", self.html)
        self.assertIn("dispensarBaseNova()", self.html)

    def test_nao_e_modal(self):
        """Se um dia virar modal, interrompe quem esta' trabalhando."""
        self.assertNotIn('id="base-nova" class="modal', self.html)

    def test_o_aviso_e_avaliado_nos_dois_caminhos_de_refresh(self):
        """O cliente so' pergunta /api/versao quando pode pular o download; sem
        avaliar tambem a resposta de /api/dados, o aviso sumiria no outro
        caminho."""
        corpo = self.html.split("async function refreshDB(")[1].split(
            "\n}")[0]
        self.assertIn("avaliarBaseNova(dv)", corpo,
                      "o caminho que so' pergunta a versao")
        self.assertIn("avaliarBaseNova(d)", corpo,
                      "o caminho do download completo")

    def test_atualizar_usa_o_caminho_que_preserva_filtros(self):
        trecho = self.html.split("async function aplicarBaseNova")[1][:1400]
        self.assertIn("recarregarAbaAtual()", trecho,
                      "redesenhar sem mexer em filtro nem scroll de quem "
                      "estava trabalhando")


if __name__ == "__main__":
    unittest.main()
