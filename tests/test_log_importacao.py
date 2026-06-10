# -*- coding: utf-8 -*-
"""Log de importacao por hash (md5): deteccao de reimportacao do mesmo conteudo."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.repositorios.repositorio_log_importacao import (
    RepositorioLogImportacao, md5_arquivo, loga_se_reimportacao,
)


class TestMd5(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="cvc_md5_")

    def _arq(self, nome, conteudo):
        p = Path(self.dir) / nome
        p.write_text(conteudo, encoding="utf-8")
        return p

    def test_mesmo_conteudo_mesmo_hash(self):
        a = self._arq("a.csv", "linha1\nlinha2\n")
        b = self._arq("b.csv", "linha1\nlinha2\n")   # nome diferente, conteudo igual
        self.assertEqual(md5_arquivo(a), md5_arquivo(b))

    def test_conteudo_diferente_hash_diferente(self):
        a = self._arq("a.csv", "X")
        b = self._arq("b.csv", "Y")
        self.assertNotEqual(md5_arquivo(a), md5_arquivo(b))


class TestRepositorioLog(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_logimp_")
        self.conexao = ConexaoBancoDados(os.path.join(self._tmp, "l.db"))
        self.conexao.inicializar()
        self.repo = RepositorioLogImportacao(self.conexao)

    def test_registrar_e_encontrar_por_hash(self):
        self.repo.registrar(arquivo="systur.csv", tipo="SYSTUR",
                            hash_arquivo="abc123", total_registros=10, status="SUCESSO")
        self.assertEqual(self.repo.hash_ja_importado("abc123"), "systur.csv")

    def test_hash_inexistente_e_vazio_retornam_none(self):
        self.assertIsNone(self.repo.hash_ja_importado("naoexiste"))
        self.assertIsNone(self.repo.hash_ja_importado(""))

    def test_status_erro_nao_conta_como_importado(self):
        self.repo.registrar(arquivo="ruim.csv", tipo="SYSTUR",
                            hash_arquivo="errohash", status="ERRO",
                            mensagem_erro="falhou")
        self.assertIsNone(self.repo.hash_ja_importado("errohash"))

    def test_loga_se_reimportacao_devolve_hash_e_nao_bloqueia(self):
        p = Path(self._tmp) / "systur_30_04.csv"
        p.write_text("a;b;c\n1;2;3\n", encoding="utf-8")
        h = loga_se_reimportacao(self.repo, caminho=p, tipo="SYSTUR")
        self.assertEqual(h, md5_arquivo(p))
        # registra sob OUTRO nome e roda de novo: deve detectar reimportacao sem erro
        self.repo.registrar(arquivo="outro_nome.csv", tipo="SYSTUR",
                            hash_arquivo=h, status="SUCESSO")
        h2 = loga_se_reimportacao(self.repo, caminho=p, tipo="SYSTUR")
        self.assertEqual(h2, h)   # nao bloqueia, devolve o mesmo hash


if __name__ == "__main__":
    unittest.main(verbosity=2)
