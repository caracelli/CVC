# -*- coding: utf-8 -*-
"""Launcher principal: antes de subir o core, mata TODAS as instancias antigas
do alvo e VERIFICA (via tasklist) que zerou. Mocka subprocess/tasklist — nao
toca em processos reais.
"""
import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from launcher import principal as P


def _ns(**kw):
    return types.SimpleNamespace(**kw)


class FakeProc:
    """Simula tasklist/taskkill. Comeca com `vivos` instancias; o taskkill zera."""
    def __init__(self, vivos=2):
        self.vivos = vivos
        self.taskkill_calls = 0
        self.tasklist_calls = 0

    def run(self, args, **kw):
        prog = args[0].lower()
        if prog == "tasklist":
            self.tasklist_calls += 1
            if self.vivos > 0:
                out = "".join(
                    "launcher_visualizador.exe   {}  Console  1  10.000 K\n".format(1000 + i)
                    for i in range(self.vivos))
            else:
                out = "INFO: No tasks are running which match the specified criteria.\n"
            return _ns(stdout=out, stderr="", returncode=0)
        if prog == "taskkill":
            self.taskkill_calls += 1
            self.vivos = 0            # /F /T /IM derruba todas as instancias
            return _ns(stdout="", stderr="", returncode=0)
        return _ns(stdout="", stderr="", returncode=0)


class TestMatarProcessos(unittest.TestCase):
    def setUp(self):
        self._orig_run = P.subprocess.run
        self._orig_sleep = P.time.sleep
        self._orig_plat = P.sys.platform
        P.time.sleep = lambda *_a, **_k: None
        P.sys.platform = "win32"
        self.addCleanup(self._restore)

    def _restore(self):
        P.subprocess.run = self._orig_run
        P.time.sleep = self._orig_sleep
        P.sys.platform = self._orig_plat

    def test_contar_instancias(self):
        fake = FakeProc(vivos=3); P.subprocess.run = fake.run
        self.assertEqual(P._contar_instancias("launcher_visualizador.exe"), 3)
        fake.vivos = 0
        self.assertEqual(P._contar_instancias("launcher_visualizador.exe"), 0)

    def test_mata_varias_e_verifica_zerou(self):
        fake = FakeProc(vivos=3); P.subprocess.run = fake.run
        P._matar_processos_anteriores("visualizador")
        self.assertGreaterEqual(fake.taskkill_calls, 1)        # matou
        # VERIFICOU: chamou tasklist apos o kill e confirmou zero
        self.assertEqual(fake.vivos, 0)
        self.assertGreaterEqual(fake.tasklist_calls, 2)        # antes e depois

    def test_nada_rodando_nao_chama_taskkill(self):
        fake = FakeProc(vivos=0); P.subprocess.run = fake.run
        P._matar_processos_anteriores("processador")
        self.assertEqual(fake.taskkill_calls, 0)               # nada a matar
        self.assertEqual(fake.tasklist_calls, 1)               # so a verificacao inicial

    def test_so_mata_o_alvo_pedido(self):
        # abrir 'processador' usa o nome launcher_processador.exe (nao o visualizador)
        capturado = {}
        def run(args, **kw):
            if args[0].lower() == "tasklist":
                capturado["tasklist_img"] = args[2]
                return _ns(stdout="INFO: No tasks...\n", stderr="", returncode=0)
            return _ns(stdout="", stderr="", returncode=0)
        P.subprocess.run = run
        P._matar_processos_anteriores("processador")
        self.assertIn("launcher_processador.exe", capturado["tasklist_img"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
