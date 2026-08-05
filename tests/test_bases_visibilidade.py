# -*- coding: utf-8 -*-
"""Painel "Bases": toda base importada tem de APARECER com arquivo e data.

Motivo (usuario, 05/08/2026): "nem todos os arquivos vem automaticamente".
O motor ja processa o que tem e nao quebra com o que falta — mas se uma base
nao vier, a tela segue mostrando os dados da carga anterior. O painel "Bases"
e' o unico lugar onde se ve que uma base ficou para tras (arquivo e data
antigos). Quem NAO registra em log_importacoes fica invisivel nesse painel.

Estavam de fora: os tres exports do diretorio (AD) e o RH de desligados —
justamente bases que costumam faltar.
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import visualizador.main as vm
from aplicacao.casos_de_uso.importar_diretorio_ad import _TIPO_LOG, ImportarDiretorioAd
from infraestrutura.banco_dados.conexao import ConexaoBancoDados

_CSV_ATIVOS = ("Login;Nome;Email\n"
               "abc123;Fulano de Tal;fulano@cvc.com.br\n"
               "def456;Ciclana Souza;ciclana@cvc.com.br\n")
_CSV_DESLIG = ("Login;Nome;Email\n"
               "xyz789;Beltrano Lima;beltrano@cvc.com.br\n")


class TestBasesCobreTodasAsFontes(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_bases_")
        self.db = os.path.join(self._tmp, "t.db")
        self.con = ConexaoBancoDados(self.db)
        self.con.inicializar()
        self._orig = (vm.DB_PATH, vm.SISTEMA, vm.PASTA_INTERACOES)
        vm.DB_PATH = self.db
        vm.SISTEMA = ""
        vm.PASTA_INTERACOES = ""

    def tearDown(self):
        vm.DB_PATH, vm.SISTEMA, vm.PASTA_INTERACOES = self._orig

    def _pasta_ad(self, nome, conteudo):
        p = Path(self._tmp) / "AD" / "08-2026"
        p.mkdir(parents=True, exist_ok=True)
        (p / nome).write_text(conteudo, encoding="utf-8")
        return str(Path(self._tmp) / "AD")

    # ---------------------------------------------------------------
    def test_os_tres_tipos_do_ad_tem_rotulo_no_painel(self):
        for tipo in _TIPO_LOG.values():
            self.assertIn(tipo, vm._BASES_LABEL, f"{tipo} nao aparece no painel Bases")

    def test_rh_desligados_tem_rotulo(self):
        self.assertIn("RH_DESLIGADOS", vm._BASES_LABEL)

    def test_todo_grupo_usado_existe_na_lista_de_grupos(self):
        for tipo, (grupo, _) in vm._BASES_LABEL.items():
            self.assertIn(grupo, vm._BASES_GRUPOS, f"{tipo} usa grupo desconhecido")

    def test_import_do_ad_registra_no_log(self):
        pasta = self._pasta_ad("ou_franqueados_03_08_2026_10-00.csv", _CSV_ATIVOS)
        self._pasta_ad("ou_desligados_03_08_2026_11-00.csv", _CSV_DESLIG)
        ImportarDiretorioAd(conexao=self.con, pasta=pasta,
                            pasta_processados=os.path.join(self._tmp, "proc"),
                            processar=True).executar()
        c = sqlite3.connect(self.db)
        tipos = {r[0] for r in c.execute("SELECT tipo FROM log_importacoes")}
        c.close()
        self.assertIn("AD_FRANQUEADOS", tipos)
        self.assertIn("AD_DESLIGADOS", tipos)

    def test_o_ad_aparece_no_painel_com_arquivo_e_data(self):
        pasta = self._pasta_ad("ou_franqueados_03_08_2026_10-00.csv", _CSV_ATIVOS)
        ImportarDiretorioAd(conexao=self.con, pasta=pasta,
                            pasta_processados=os.path.join(self._tmp, "proc"),
                            processar=True).executar()
        bases = vm.listar_bases()
        achatado = []
        for g in (bases if isinstance(bases, list) else bases.get("grupos", [])):
            achatado.extend(g.get("itens", []) if isinstance(g, dict) else [])
        alvo = [i for i in achatado
                if "franqueado" in str(i.get("base", i.get("rotulo", ""))).lower()]
        self.assertTrue(alvo, f"Franqueados fora do painel Bases: {bases}")
        (item,) = alvo
        self.assertIn("ou_franqueados", str(item.get("arquivo", "")).lower())

    def test_erro_de_leitura_tambem_e_registrado(self):
        # arquivo ilegivel nao pode sumir do painel: tem de constar como ERRO
        pasta = self._pasta_ad("ou_prestadores_03_08_2026_12-00.csv", "")
        ImportarDiretorioAd(conexao=self.con, pasta=pasta,
                            pasta_processados=os.path.join(self._tmp, "proc"),
                            pasta_erros=os.path.join(self._tmp, "err"),
                            processar=True).executar()
        c = sqlite3.connect(self.db)
        n = c.execute("SELECT COUNT(*) FROM log_importacoes "
                      "WHERE tipo='AD_PRESTADORES'").fetchone()[0]
        c.close()
        self.assertGreaterEqual(n, 1, "arquivo problematico ficou invisivel")


if __name__ == "__main__":
    unittest.main(verbosity=2)
