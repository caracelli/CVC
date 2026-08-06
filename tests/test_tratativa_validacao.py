# -*- coding: utf-8 -*-
"""Regra da TRATATIVA INTERNA (decidida em 05/08/2026).

Antes: o Nº do ticket do Jira era OBRIGATORIO nos tres fluxos de tratativa
(resolver pendencia, tratar desligado, revisar transferido).

A regra nova separa dois caminhos no mesmo formulario:
  RESOLVER      — o analista trata internamente e registra o que decidiu;
  ABRIR CHAMADO — abre o ticket no Jira pela API (ainda nao implementado).

Exigir o ticket impediria o primeiro caminho: nao daria para registrar uma
tratativa sem antes existir chamado — exatamente o que a regra nova criou.
Agora o obrigatorio e' o que PROVA a tratativa (motivo + parecer do analista);
ticket e link sao referencia externa e ficam opcionais.

O front valida igual (_validarTratativa no index.html), mas quem garante e' o
servidor: estes casos travam a regra no backend.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from visualizador.main import _validar_tratativa


class TestObrigatorios(unittest.TestCase):

    def test_motivo_e_parecer_bastam(self):
        self.assertIsNone(_validar_tratativa("123", "Exceção", "Verificado com o gestor."))

    def test_sem_ticket_e_valido(self):
        """O ponto da regra nova: tratativa interna nao depende do Jira."""
        self.assertIsNone(_validar_tratativa("123", "Acesso Indevido", "Revogado."))

    def test_sem_registro_recusa(self):
        self.assertIn("registro", _validar_tratativa("", "Exceção", "ok"))

    def test_sem_motivo_recusa_na_pendencia(self):
        erro = _validar_tratativa("123", "", "ok")
        self.assertIsNotNone(erro)
        self.assertIn("motivo", erro.lower())

    def test_sem_motivo_ACEITA_onde_o_campo_nao_existe(self):
        # desligado e transferido chamam com exige_motivo=False
        self.assertIsNone(_validar_tratativa("123", "", "ok", exige_motivo=False))

    def test_parecer_continua_obrigatorio_mesmo_sem_motivo(self):
        self.assertIsNotNone(_validar_tratativa("123", "", "", exige_motivo=False))

    def test_sem_parecer_recusa(self):
        erro = _validar_tratativa("123", "Exceção", "")
        self.assertIsNotNone(erro)
        self.assertIn("parecer", erro.lower())

    def test_parecer_so_com_espacos_recusa(self):
        self.assertIsNotNone(_validar_tratativa("123", "Exceção", "   \n\t "))

    def test_parecer_none_recusa(self):
        self.assertIsNotNone(_validar_tratativa("123", "Exceção", None))


class TestFormatoDoErro(unittest.TestCase):
    """O erro vai para a tela do analista: precisa ser JSON valido e legivel."""

    def test_erro_e_json_valido(self):
        import json
        for args in (("", "m", "p"), ("1", "", "p"), ("1", "m", "")):
            erro = _validar_tratativa(*args)
            d = json.loads(erro)
            self.assertFalse(d["ok"])
            self.assertTrue(d["erro"])

    def test_mensagem_diz_o_que_fazer(self):
        import json
        msg = json.loads(_validar_tratativa("1", "m", ""))["erro"]
        self.assertIn("verificado", msg.lower())


class TestGravadorConcordaComOValidador(unittest.TestCase):
    """A validacao da rota e a funcao que GRAVA precisam concordar.

    Achado no E2E do pacote: a rota ja aceitava sem ticket (HTTP 200), mas
    `resolver_pendencia` continuava exigindo `tk` por dentro e devolvia 0 —
    "falha ao resolver", sem explicacao. Testar so o validador nao pegava:
    eram duas regras, em dois lugares, discordando.
    """

    def setUp(self):
        import os
        import sqlite3
        import tempfile
        import visualizador.main as vm
        self.vm = vm
        self._orig = (vm.DB_PATH, vm.PASTA_INTERACOES, vm.SISTEMA)
        self._tmp = tempfile.mkdtemp(prefix="cvc_trat_")
        # banco minimo: as funcoes leem metadados para o snapshot de auditoria
        db = os.path.join(self._tmp, "t.db")
        c = sqlite3.connect(db)
        c.executescript(
            "CREATE TABLE bi_divergencias (usuario TEXT, nome_usuario TEXT,"
            " sistema TEXT, matricula TEXT, tipo TEXT, acao TEXT,"
            " perfil_encontrado TEXT, perfil_esperado TEXT, origem TEXT);"
            "CREATE TABLE rh_ativos (matricula TEXT, cargo_descricao TEXT,"
            " centro_custo_codigo TEXT, centro_custo_nome TEXT);"
            "CREATE TABLE rh_desligados (matricula TEXT, nome TEXT,"
            " cargo_descricao TEXT, centro_custo_codigo TEXT);"
            "CREATE TABLE divergencias (tipo TEXT, sistema TEXT, usuario TEXT,"
            " matricula TEXT, perfil_encontrado TEXT);")
        c.commit()
        c.close()
        vm.DB_PATH = db
        vm.PASTA_INTERACOES = self._tmp
        vm.SISTEMA = ""

    def tearDown(self):
        self.vm.DB_PATH, self.vm.PASTA_INTERACOES, self.vm.SISTEMA = self._orig

    def _funcoes(self):
        return (self.vm.resolver_pendencia, self.vm.tratar_desligado,
                self.vm.tratar_transferido)

    def test_gravam_SEM_ticket(self):
        for fn in self._funcoes():
            self.assertEqual(
                fn("123", "", "", "Parecer do analista.", "Exceção"), 1,
                f"{fn.__name__} recusou tratativa sem ticket")

    def test_nao_gravam_sem_parecer(self):
        for fn in self._funcoes():
            self.assertEqual(fn("123", "IAM-1", "", "", "Exceção"), 0,
                             f"{fn.__name__} gravou sem parecer")

    def test_pendencia_exige_motivo(self):
        """So a PENDENCIA tem a lista fechada — e' dela que sai o grafico."""
        self.assertEqual(
            self.vm.resolver_pendencia("123", "IAM-1", "", "Parecer.", ""), 0)

    def test_desligado_e_transferido_NAO_exigem_motivo(self):
        """Decisao de 06/08: no desligado o desfecho e' sempre revogar, e no
        transferido o motivo so repetiria o rotulo da aba. Campo obrigatorio de
        resposta unica e' atrito, nao dado."""
        for fn in (self.vm.tratar_desligado, self.vm.tratar_transferido):
            self.assertEqual(fn("123", "IAM-1", "", "Parecer.", ""), 1,
                             f"{fn.__name__} ainda exige motivo")

    def test_com_ticket_continua_gravando(self):
        for fn in self._funcoes():
            self.assertEqual(fn("123", "IAM-1", "", "Parecer.", "Exceção"), 1)


class TestOsTresFluxosUsamAMesmaRegra(unittest.TestCase):
    """resolver / tratar-desligado / tratar-transferido nao podem divergir."""

    def test_endpoints_chamam_o_validador(self):
        fonte = (Path(__file__).resolve().parent.parent
                 / "src" / "visualizador" / "main.py").read_text(encoding="utf-8")
        # so as CHAMADAS (a definicao da funcao casa o mesmo texto)
        self.assertEqual(fonte.count("erro = _validar_tratativa(rid, motivo"), 3)

    def test_nao_sobrou_exigencia_de_ticket(self):
        fonte = (Path(__file__).resolve().parent.parent
                 / "src" / "visualizador" / "main.py").read_text(encoding="utf-8")
        self.assertNotIn("id, ticket e motivo obrigatorios", fonte)


if __name__ == "__main__":
    unittest.main(verbosity=2)
