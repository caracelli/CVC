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

    def test_sem_motivo_recusa(self):
        erro = _validar_tratativa("123", "", "ok")
        self.assertIsNotNone(erro)
        self.assertIn("motivo", erro.lower())

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
