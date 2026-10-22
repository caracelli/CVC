# -*- coding: utf-8 -*-
"""Testes do lock de processamento do Processador.

Impede duas execucoes simultaneas (escrita concorrente corromperia o banco da
rede).

20/10/2026 — SINAL DE VIDA. Em 15/10 o lock "antigo" (20 min de idade) foi
assumido com o dono ainda rodando, e varios Processadores gravaram no mesmo
banco. Agora o dono reescreve o lock a cada minuto; o lock so' e' abandonado
apos 10 min SEM SINAL. Lock de versao anterior (sem "batimento=") segue a regra
antiga de 20 min de idade.
"""
import shutil
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from processador.main import _verificar_e_criar_lock
from infraestrutura.banco_dados.processamento_local import BatimentoLock, ProcessamentoCancelado


def _ha(minutos):
    return (datetime.now() - timedelta(minutes=minutos)).isoformat(timespec="seconds")


class TestLockProcessamento(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="lock_test_")
        self.banco = Path(self.tmp) / "BANCO" / "iam_analytics.db"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_adquire_e_libera(self):
        ok, lock, fixo = _verificar_e_criar_lock(self.banco)
        self.assertTrue(ok)
        self.assertIsNotNone(lock)
        self.assertTrue(lock.exists())
        self.assertIn("usuario=", fixo)
        self.assertIn("maquina=", fixo)
        lock.unlink()
        ok2, _, _ = _verificar_e_criar_lock(self.banco)
        self.assertTrue(ok2, "apos liberar, readquire")

    def test_execucao_paralela_aborta(self):
        ok, lock, _ = _verificar_e_criar_lock(self.banco)
        self.assertTrue(ok)
        ok2, lock2, _ = _verificar_e_criar_lock(self.banco)
        self.assertFalse(ok2, "lock recente -> aborta a 2a execucao")
        self.assertIsNone(lock2)

    def test_com_sinal_de_vida_recente_aborta_mesmo_iniciado_ha_horas(self):
        """⭐ O caso de 15/10: o dono comecou ha' 3 h e continua vivo. Pela regra
        antiga (idade > 20 min) o lock seria assumido; agora vale o sinal."""
        _, lock, _ = _verificar_e_criar_lock(self.banco)
        lock.write_text(f"{_ha(1)}\nbatimento={_ha(1)}\ninicio={_ha(180)}\nusuario=x\n",
                        encoding="utf-8")
        ok2, _, _ = _verificar_e_criar_lock(self.banco)
        self.assertFalse(ok2)

    def test_sem_sinal_ha_mais_de_10_min_e_assumido(self):
        _, lock, _ = _verificar_e_criar_lock(self.banco)
        lock.write_text(f"{_ha(12)}\nbatimento={_ha(12)}\nusuario=x\n", encoding="utf-8")
        ok2, lock2, _ = _verificar_e_criar_lock(self.banco)
        self.assertTrue(ok2, "dono sem sinal ha' 12 min -> caiu, assume")
        self.assertIsNotNone(lock2)

    def test_lock_legado_de_5_min_aborta(self):
        _, lock, _ = _verificar_e_criar_lock(self.banco)
        lock.write_text(_ha(5) + "\nusuario=x\n", encoding="utf-8")
        ok2, _, _ = _verificar_e_criar_lock(self.banco)
        self.assertFalse(ok2, "lock de versao anterior, 5 min -> aborta")

    def test_lock_legado_de_15_min_ainda_aborta(self):
        """Lock sem sinal de vida (versao anterior) mantem a regra de 20 min —
        os 10 min valem so' para quem bate o sinal."""
        _, lock, _ = _verificar_e_criar_lock(self.banco)
        lock.write_text(_ha(15) + "\nusuario=x\n", encoding="utf-8")
        ok2, _, _ = _verificar_e_criar_lock(self.banco)
        self.assertFalse(ok2)

    def test_lock_legado_antigo_e_assumido(self):
        _, lock, _ = _verificar_e_criar_lock(self.banco)
        lock.write_text(_ha(35) + "\nusuario=x\n", encoding="utf-8")
        ok2, lock2, _ = _verificar_e_criar_lock(self.banco)
        self.assertTrue(ok2, "lock antigo (execucao interrompida) -> assume e prossegue")
        self.assertIsNotNone(lock2)

    def test_batimento_atualiza_a_primeira_linha(self):
        """A 1a linha e' o ultimo sinal: e' o que o Visualizador e as versoes
        anteriores leem."""
        _, lock, fixo = _verificar_e_criar_lock(self.banco)
        lock.write_text(f"{_ha(30)}\nbatimento={_ha(30)}\n{fixo}", encoding="utf-8")
        b = BatimentoLock(lock, fixo, intervalo=0.05).iniciar()
        time.sleep(0.3)
        b.parar()
        primeira = lock.read_text(encoding="utf-8").splitlines()[0]
        idade = (datetime.now() - datetime.fromisoformat(primeira)).total_seconds()
        self.assertLess(idade, 5)
        self.assertIn("usuario=", lock.read_text(encoding="utf-8"))


class TestCancelarApagandoOLock(unittest.TestCase):
    """20/10/2026 — o lock e' o "arquivo de processando": apagado, o
    Processador para no proximo passo e nao o recria."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="lock_cancel_")
        self.banco = Path(self.tmp) / "BANCO" / "iam_analytics.db"
        _, self.lock, self.fixo = _verificar_e_criar_lock(self.banco)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_com_o_lock_no_lugar_segue(self):
        BatimentoLock(self.lock, self.fixo).conferir("Importacao RH")

    def test_lock_apagado_para_no_proximo_passo(self):
        b = BatimentoLock(self.lock, self.fixo)
        self.lock.unlink()
        with self.assertRaises(ProcessamentoCancelado) as cm:
            b.conferir("Validacao")
        self.assertIn("Validacao", str(cm.exception))

    def test_batimento_nao_recria_lock_apagado(self):
        b = BatimentoLock(self.lock, self.fixo, intervalo=0.05).iniciar()
        self.lock.unlink()
        time.sleep(0.3)
        b.parar()
        self.assertFalse(self.lock.exists(), "o sinal de vida recriaria o arquivo apagado")
        self.assertTrue(b.perdido)

    def test_lock_tomado_por_outra_execucao_tambem_para(self):
        b = BatimentoLock(self.lock, self.fixo)
        outro = f"{_ha(0)}\nbatimento={_ha(0)}\ninicio={_ha(0)}\nusuario=outra\nmaquina=X\n"
        self.lock.write_text(outro, encoding="utf-8")
        with self.assertRaises(ProcessamentoCancelado):
            b.conferir()
        b.liberar()
        self.assertEqual(self.lock.read_text(encoding="utf-8"), outro,
                         "nao apaga nem sobrescreve o lock de outra execucao")

    def test_fim_normal_apaga_o_proprio_lock(self):
        b = BatimentoLock(self.lock, self.fixo, intervalo=0.05).iniciar()
        time.sleep(0.15)
        b.conferir()
        b.liberar()
        self.assertFalse(self.lock.exists())


if __name__ == "__main__":
    unittest.main()
