# -*- coding: utf-8 -*-
"""Testes do lock de processamento do Processador.

Impede duas execucoes simultaneas (escrita concorrente corromperia o banco da
rede). Lock antigo (execucao interrompida) e' assumido apos algumas horas.
"""
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from processador.main import _verificar_e_criar_lock


class TestLockProcessamento(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="lock_test_")
        self.banco = Path(self.tmp) / "BANCO" / "iam_analytics.db"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_adquire_e_libera(self):
        ok, lock = _verificar_e_criar_lock(self.banco)
        self.assertTrue(ok)
        self.assertIsNotNone(lock)
        self.assertTrue(lock.exists())
        lock.unlink()
        ok2, lock2 = _verificar_e_criar_lock(self.banco)
        self.assertTrue(ok2, "apos liberar, readquire")

    def test_execucao_paralela_aborta(self):
        ok, lock = _verificar_e_criar_lock(self.banco)
        self.assertTrue(ok)
        ok2, lock2 = _verificar_e_criar_lock(self.banco)
        self.assertFalse(ok2, "lock recente -> aborta a 2a execucao")
        self.assertIsNone(lock2)

    def test_lock_recente_aborta(self):
        ok, lock = _verificar_e_criar_lock(self.banco)
        self.assertTrue(ok)
        # 5 min atras: dentro do STALE_MIN=30 -> ainda considerado em andamento
        recente = (datetime.now() - timedelta(minutes=5)).isoformat(timespec="seconds")
        lock.write_text(recente + "\nusuario=x\n", encoding="utf-8")
        ok2, _ = _verificar_e_criar_lock(self.banco)
        self.assertFalse(ok2, "lock de 5 min -> aborta (provavelmente rodando)")

    def test_lock_antigo_e_assumido(self):
        ok, lock = _verificar_e_criar_lock(self.banco)
        self.assertTrue(ok)
        # 35 min atras: alem do STALE_MIN=30 -> execucao interrompida, assume
        velho = (datetime.now() - timedelta(minutes=35)).isoformat(timespec="seconds")
        lock.write_text(velho + "\nusuario=x\n", encoding="utf-8")
        ok2, lock2 = _verificar_e_criar_lock(self.banco)
        self.assertTrue(ok2, "lock antigo (execucao interrompida) -> assume e prossegue")
        self.assertIsNotNone(lock2)


if __name__ == "__main__":
    unittest.main()
