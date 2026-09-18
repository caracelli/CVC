# -*- coding: utf-8 -*-
"""Aba Bases: contador "lidas no arquivo x carregadas na aplicação".

Pedido da área (18/09/2026): "tipo SIGOT eu li a base e tem 45 linhas, na
aplicação ele faz ou não a referência às mesmas 45?". O usuário pediu o
contador em TODAS as bases, mesmo quando a diferença é zero — é a confirmação
que ela quer ver.

A regra que nao pode se perder: extrato de sistema e matriz sao SUBSTITUICAO
(tem de bater), RH e diretorio AD sao INCREMENTAIS (merge, bc7af3e) e o total
do banco e' MAIOR que o do arquivo por desenho — ali comparar 1:1 inventaria um
erro inexistente.
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
import visualizador.main as vm


class ContadorDeBases(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cvc_bases_")
        self.db = os.path.join(self.tmp, "iam.db")
        ConexaoBancoDados(self.db).inicializar()
        self._orig = (vm.DB_PATH, vm.SISTEMA)
        vm.DB_PATH, vm.SISTEMA = self.db, ""
        c = sqlite3.connect(self.db)
        try:
            def log(arquivo, tipo, total, dt):
                c.execute("INSERT INTO log_importacoes (arquivo, tipo, total_registros, "
                          "status, dt_importacao) VALUES (?,?,?,'SUCESSO',?)",
                          [arquivo, tipo, total, dt])
            log("SIGOT_15_09.csv", "SIGOT", 45, "2026-09-15 10:00:00")
            log("view_systur.csv", "SYSTUR", 3, "2026-09-15 10:01:00")
            log("PROJETOIAM.CSV", "RH_ATIVOS", 2, "2026-09-15 10:02:00")
            for i in range(45):     # SIGOT: bate com o arquivo
                c.execute("INSERT INTO acessos_sistemas (sistema, usuario, perfil) "
                          "VALUES ('SIGOT', ?, 'P')", [f"u{i}"])
            for i in range(2):      # SYSTUR: 3 no arquivo, 2 no banco (1 duplicada)
                c.execute("INSERT INTO acessos_sistemas (sistema, usuario, perfil) "
                          "VALUES ('SYSTUR', ?, 'P')", [f"s{i}"])
            for i in range(5):      # RH: acumulado de cargas anteriores
                c.execute("INSERT INTO rh_ativos (matricula, nome, cpf, tipo_vinculo) "
                          "VALUES (?, 'X', ?, 'FUNCIONARIO')", [f"m{i}", f"{i}" * 11])
            c.commit()
        finally:
            c.close()

    def tearDown(self):
        vm.DB_PATH, vm.SISTEMA = self._orig

    def _itens(self):
        return {it["tipo"]: it for g in vm.listar_bases() for it in g["itens"]}

    def test_extrato_que_bate(self):
        it = self._itens()["SIGOT"]
        self.assertEqual((it["registros"], it["na_app"]), (45, 45))
        self.assertFalse(it["acumula"], "extrato e' substituicao, nao acumula")

    def test_extrato_com_diferenca_aparece(self):
        """O caso que justifica o contador: o arquivo tinha 3 e so' 2 entraram."""
        it = self._itens()["SYSTUR"]
        self.assertEqual((it["registros"], it["na_app"]), (3, 2))

    def test_rh_e_marcado_como_acumulado(self):
        it = self._itens()["RH_ATIVOS"]
        self.assertEqual(it["registros"], 2)
        self.assertEqual(it["na_app"], 5)
        self.assertTrue(it["acumula"],
                        "RH e' incremental: sem esta marca a tela acusaria erro inexistente")

    def test_banco_sem_a_tabela_nao_derruba_a_tela(self):
        """Processador antigo pode nao ter uma tabela — a base fica sem contagem,
        mas a lista continua de pe (mesmo principio do achado de 06/08)."""
        c = sqlite3.connect(self.db)
        try:
            c.execute("DROP TABLE acessos_sistemas")
            c.commit()
        finally:
            c.close()
        itens = self._itens()
        self.assertIn("SIGOT", itens)
        self.assertEqual(itens["SIGOT"]["na_app"], "")

    def test_o_painel_desenha_o_contador(self):
        """Guarda contra o fix ficar so' no servidor: o index.html precisa
        consumir na_app/acumula (foi o erro de 26/08 — codigo morto na tela)."""
        html = (Path(__file__).resolve().parent.parent / "CVC_IAM_ANALYTICS"
                / "EXECUTAVEIS" / "REPORT" / "index.html").read_text(encoding="utf-8")
        self.assertIn("_basesContador(it)", html, "o contador nao e' chamado na linha da base")
        self.assertIn("it.na_app", html)
        self.assertIn("it.acumula", html)


if __name__ == "__main__":
    unittest.main()
