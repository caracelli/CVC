# -*- coding: utf-8 -*-
"""Reprocessar tem de mudar a tela.

`bi_divergencias` e' um snapshot materializado de `validacao_acessos` +
`divergencias`. Ate 25/08/2026 ela so' era refeita se FALTASSE (ou com o
argumento `refresh` na linha de comando — que ninguem passa: o analista abre o
.exe). Entao o Processador rodava, o banco mudava, e o painel seguia servindo o
cenario anterior. Todo ajuste de motor parecia nao ter efeito nenhum.

Achado ao repor os extratos de SIGOT/SICA_RA/SICA_ESFERA no sandbox: as 905
validacoes novas entraram em `validacao_acessos` e a tela nao viu uma.
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


class SnapshotAcompanhaOProcessador(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cvc_snap_")
        self.db = os.path.join(self.tmp, "iam.db")
        ConexaoBancoDados(self.db).inicializar()
        self._orig = (vm.DB_PATH, vm.SISTEMA)
        vm.DB_PATH, vm.SISTEMA = self.db, ""
        vm._BASE = None
        self._validacao("SYSTUR", "M1", "2026-08-05 10:00:00")
        vm.garantir_estrutura(force=True)      # snapshot do cenário inicial

    def tearDown(self):
        vm.DB_PATH, vm.SISTEMA = self._orig
        vm._BASE = None

    def _validacao(self, sistema, matricula, dt):
        c = sqlite3.connect(self.db)
        try:
            cols = [r[1] for r in c.execute("PRAGMA table_info(validacao_acessos)")]
            vals = {"matricula": matricula, "nome": "FULANO " + matricula,
                    "cpf": "0" * 11, "sistema": sistema, "perfil_esperado": "P1",
                    "perfil_atual": "P1", "status": "OK",
                    "dt_processamento": dt}
            usar = [k for k in vals if k in cols]
            c.execute(f"INSERT INTO validacao_acessos ({','.join(usar)}) "
                      f"VALUES ({','.join('?' * len(usar))})", [vals[k] for k in usar])
            c.commit()
        finally:
            c.close()

    def _sistemas_no_snapshot(self):
        c = sqlite3.connect(self.db)
        try:
            return {r[0] for r in c.execute("SELECT DISTINCT sistema FROM bi_divergencias")}
        finally:
            c.close()

    def test_snapshot_inicial(self):
        self.assertEqual(self._sistemas_no_snapshot(), {"SYSTUR"})

    def test_reprocesso_aparece_sem_force(self):
        """O caso real: extrato novo entra, o Processador roda, o painel abre."""
        self._validacao("SIGOT", "M2", "2026-08-25 15:19:00")
        vm.garantir_estrutura()                # sem force — como o .exe faz
        self.assertIn("SIGOT", self._sistemas_no_snapshot(),
                      "reprocessou e a tela não viu")

    def test_cache_do_painel_morre_junto(self):
        """Refazer a tabela sem limpar `_BASE` serviria o cenário velho de novo."""
        vm._BASE = {"marcador": "cenário antigo"}
        self._validacao("SIGOT", "M2", "2026-08-25 15:19:00")
        vm.garantir_estrutura()
        self.assertIsNone(vm._BASE)

    def test_sem_reprocesso_nao_refaz(self):
        """Sem carimbo novo o snapshot fica quieto — abrir o painel não pode
        custar um rebuild a cada vez."""
        c = sqlite3.connect(self.db)
        try:
            c.execute("INSERT INTO bi_divergencias (id, tipo, sistema, usuario, "
                      "nome_usuario, matricula, perfil_encontrado, perfil_esperado, "
                      "descricao, motivo, data_identificacao, resolvida, acao, "
                      "origem, login) VALUES ('marca','OK','MARCA','x','x','x','','','','',"
                      "'2026-08-05 10:00:00',0,'Aderente','','')")
            c.commit()
        finally:
            c.close()
        vm.garantir_estrutura()
        self.assertIn("MARCA", self._sistemas_no_snapshot(),
                      "o snapshot foi refeito sem o Processador ter rodado")


if __name__ == "__main__":
    unittest.main()
