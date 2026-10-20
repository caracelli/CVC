# -*- coding: utf-8 -*-
"""Processar numa copia local do banco e publicar no fim (20/10/2026).

Origem: a lentidao de 15/10 — gravar o SQLite pela rede custa ~9x (2,2 min
local x 19,6 min na rede) e, interrompido, deixou um -journal quente ao lado
do banco. Agora o Processador copia o banco, processa local e publica de uma
vez; se cair antes de publicar, o banco da rede fica intacto e os arquivos
movidos voltam a ENTRADA.
"""
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.banco_dados.processamento_local import preparar_copia_local, publicar
from infraestrutura.leitores_arquivos import leitor_base
from aplicacao.casos_de_uso.dobrar_interacoes import DobrarInteracoes


def _banco(caminho, valor="original", linhas=2000):
    con = sqlite3.connect(caminho)
    con.execute("PRAGMA journal_mode=DELETE")
    con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    con.executemany("INSERT INTO t (v) VALUES (?)", [(valor + "x" * 200,)] * linhas)
    con.commit()
    con.close()


def _valores(caminho):
    con = sqlite3.connect(caminho)
    try:
        return {r[0][:8] for r in con.execute("SELECT v FROM t")}
    finally:
        con.close()


class CopiaLocalEPublicacao(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="proc_local_"))
        self.rede = self.tmp / "rede" / "DADOS" / "BANCO" / "iam_analytics.db"
        self.rede.parent.mkdir(parents=True)
        self.local = self.tmp / "local"
        _banco(self.rede)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_gravacao_interrompida_e_desfeita_antes_de_copiar(self):
        """⭐ O caso de 15/10: banco com journal QUENTE ao lado (processamento
        caiu no meio). Copiar so' o .db levaria um banco pela metade; a copia
        tem que sair com o conteudo de ANTES da gravacao interrompida."""
        con = sqlite3.connect(self.rede)
        con.execute("PRAGMA cache_size=1")         # forca as paginas para o .db
        con.execute("BEGIN")
        con.execute("UPDATE t SET v = 'meio_gr' || v")
        quebrado = self.tmp / "quebrado"
        quebrado.mkdir()
        for ext in ("", "-journal"):               # "queda": copia no meio da gravacao
            shutil.copy2(str(self.rede) + ext, str(quebrado / ("iam_analytics.db" + ext)))
        con.rollback()
        con.close()
        banco_quebrado = quebrado / "iam_analytics.db"
        self.assertTrue(Path(str(banco_quebrado) + "-journal").exists())

        copia = preparar_copia_local(banco_quebrado, self.local)
        self.assertEqual(_valores(copia), {"original"})
        self.assertFalse(Path(str(banco_quebrado) + "-journal").exists(),
                         "o rollback do SQLite consome o journal quente")

    def test_copia_e_publica(self):
        copia = preparar_copia_local(self.rede, self.local)
        con = sqlite3.connect(copia)
        con.execute("UPDATE t SET v = 'novo' || v")
        con.commit()
        con.close()
        self.assertEqual(_valores(self.rede), {"original"}, "rede intacta ate' publicar")
        publicar(copia, self.rede)
        self.assertEqual({v[:4] for v in _valores(self.rede)}, {"novo"})
        self.assertFalse(Path(str(self.rede) + ".publicando").exists())

    def test_journal_orfao_nao_fica_ao_lado_do_banco_publicado(self):
        copia = preparar_copia_local(self.rede, self.local)
        orfao = Path(str(self.rede) + "-journal")
        orfao.write_bytes(b"lixo")
        publicar(copia, self.rede)
        self.assertFalse(orfao.exists(), "journal ao lado do banco novo o corromperia")
        self.assertTrue(list(self.rede.parent.glob("iam_analytics.db-journal.orfao_*")))

    def test_banco_corrompido_nao_e_publicado(self):
        copia = preparar_copia_local(self.rede, self.local)
        copia.write_bytes(b"SQLite format 3\x00" + b"\x00" * 200)
        with self.assertRaises(Exception):
            publicar(copia, self.rede)
        self.assertEqual(_valores(self.rede), {"original"})

    def test_primeira_carga_sem_banco_na_rede(self):
        self.rede.unlink()
        copia = preparar_copia_local(self.rede, self.local)
        self.assertFalse(copia.exists())


class DesfazerMovimentos(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mov_"))
        leitor_base.MOVIMENTOS.clear()

    def tearDown(self):
        leitor_base.MOVIMENTOS.clear()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_arquivos_movidos_voltam_para_a_entrada(self):
        """Caiu antes de publicar: o que ja' foi para PROCESSADOS/ERROS volta,
        para ser importado de novo na proxima execucao."""
        a = self.tmp / "view_systur_19_10.csv"
        b = self.tmp / "ruim.csv"
        a.write_text("x")
        b.write_text("y")
        leitor = leitor_base.LeitorArquivoBase.__new__(leitor_base.LeitorArquivoBase)
        leitor._pasta_erros = None
        leitor.mover_para_processados(a)
        leitor.mover_para_erros(b, "teste")
        self.assertFalse(a.exists())
        self.assertFalse(b.exists())
        self.assertEqual(leitor_base.desfazer_movimentos(), 2)
        self.assertTrue(a.exists())
        self.assertTrue(b.exists())
        self.assertEqual(leitor_base.MOVIMENTOS, [])


class DobraEmCopiaLocal(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dobra_local_"))
        self.banco = self.tmp / "b.db"
        self.inter = self.tmp / "INTERACOES"
        self.inter.mkdir()
        (self.inter / "u1.jsonl").write_text("", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_pasta_dobrada_so_some_depois_de_publicar(self):
        d = DobrarInteracoes(str(self.banco), str(self.inter), remover_ao_dobrar=False)
        d.executar()
        sobras = list(self.tmp.glob("INTERACOES_processando*"))
        self.assertEqual(len(sobras), 1, "a pasta dobrada fica ate' a publicacao")
        self.assertTrue(self.inter.exists(), "nova INTERACOES vazia para os paineis")
        d.remover_pastas_dobradas()
        self.assertEqual(list(self.tmp.glob("INTERACOES_processando*")), [])

    def test_sobra_de_execucao_que_caiu_e_recuperada(self):
        DobrarInteracoes(str(self.banco), str(self.inter), remover_ao_dobrar=False).executar()
        # a execucao caiu antes de publicar: a pasta sobrou. A proxima recupera.
        d2 = DobrarInteracoes(str(self.banco), str(self.inter), remover_ao_dobrar=False)
        d2.executar()
        d2.remover_pastas_dobradas()
        self.assertEqual(list(self.tmp.glob("INTERACOES_processando*")), [])

    def test_modo_rede_continua_removendo_na_hora(self):
        DobrarInteracoes(str(self.banco), str(self.inter)).executar()
        self.assertEqual(list(self.tmp.glob("INTERACOES_processando*")), [])


if __name__ == "__main__":
    unittest.main()
