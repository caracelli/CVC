# -*- coding: utf-8 -*-
"""O painel so' pode baixar os 5,5 MB quando algo mudou de verdade.

Retorno da area em 28/08/2026 (Teams 12:42):
  "quando a gente navega entre as abas tem vezes que ele nao carrega os dados
   e tem que fechar e abrir de novo"
  "ele da umas travadas e so' fechando tudo e abrindo de novo"

O que acontecia: `showPage` fazia `await refreshDB()` a CADA troca de aba
(index.html:1685) e o timer refazia a cada 10s (REFRESH_MS). `refreshDB`
baixava `/api/dados` INCONDICIONALMENTE.

MEDIDO no Edge, uma volta pelas 8 abas do painel (banco dos 7 sistemas, 2.664
usuarios / 5.821 linhas):
    antes  — 8 chamadas de /api/dados, **38,35 MB**
    depois — 2 chamadas, **10,96 MB**, mais 6 de /api/versao somando 0,42 KB
             (queda de 71%; as 2 cheias sao a carga inicial e a rede de
             seguranca do 6o ciclo)

O risco desta mudanca e' UM: se o token nao enxergar alguma fonte de mudanca, a
tela fica velha SEM AVISAR — pior que lenta. Por isso os testes abaixo cobram
cada escritor da arquitetura multiusuario, e o cliente tem `_FORCA_A_CADA`.

⚠️ Ao testar isto a mao, `PASTA_INTERACOES` e' resolvida no IMPORT do modulo
(`caminho_interacoes()`), antes de qualquer monkeypatch de caminho — eu perdi
tempo escrevendo .jsonl na pasta errada e concluindo que o token estava cego.
"""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import visualizador.main as vm

INDEX = (Path(__file__).resolve().parent.parent
         / "CVC_IAM_ANALYTICS" / "EXECUTAVEIS" / "REPORT" / "index.html")


class TokenEnxergaOsDoisEscritores(unittest.TestCase):
    """Banco (Processador) e .jsonl (analistas) — ver docs/ARQUITETURA_MULTIUSUARIO."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cvc_tok_")
        self.db = os.path.join(self.tmp, "iam.db")
        with open(self.db, "wb") as f:
            f.write(b"x" * 100)
        self.inter = os.path.join(self.tmp, "INTERACOES")
        os.makedirs(self.inter)
        self._db_orig, self._int_orig = vm.DB_PATH, vm.PASTA_INTERACOES
        vm.DB_PATH, vm.PASTA_INTERACOES = self.db, self.inter

    def tearDown(self):
        vm.DB_PATH, vm.PASTA_INTERACOES = self._db_orig, self._int_orig

    def _jsonl(self, nome, modo="w"):
        with open(os.path.join(self.inter, nome), modo, encoding="utf-8") as f:
            f.write(json.dumps({"v": 1, "acao": "T"}) + "\n")

    def test_parado_o_token_nao_muda(self):
        """Se oscilasse, o painel baixaria 5,5 MB a toa — o bug de volta."""
        t = vm.token_mudanca()
        self.assertEqual(t, vm.token_mudanca())
        self.assertEqual(t, vm.token_mudanca())

    def test_ve_jsonl_novo(self):
        t0 = vm.token_mudanca()
        self._jsonl("user_a.jsonl")
        self.assertNotEqual(vm.token_mudanca(), t0)

    def test_ve_append_no_mesmo_jsonl(self):
        """⭐ O caso dificil. Os .jsonl sao APPEND-ONLY: a tratativa nova entra
        no arquivo que ja' existe. Sobre SMB o mtime pode nao mudar na
        granularidade do relogio — por isso o TAMANHO entra no token."""
        self._jsonl("user_a.jsonl")
        t0 = vm.token_mudanca()
        time.sleep(0.05)
        self._jsonl("user_a.jsonl", modo="a")
        self.assertNotEqual(vm.token_mudanca(), t0,
                            "append invisivel = tratativa de colega nunca aparece")

    def test_ve_remocao(self):
        self._jsonl("user_a.jsonl")
        t0 = vm.token_mudanca()
        os.remove(os.path.join(self.inter, "user_a.jsonl"))
        self.assertNotEqual(vm.token_mudanca(), t0)

    def test_ve_o_banco_mudar(self):
        """O Processador reescreve o banco — sem isto, reprocessar nao apareceria."""
        t0 = vm.token_mudanca()
        with open(self.db, "ab") as f:
            f.write(b"y" * 50)
        self.assertNotEqual(vm.token_mudanca(), t0)

    def test_sem_banco_nao_estoura(self):
        vm.DB_PATH = os.path.join(self.tmp, "nao_existe.db")
        self.assertIsInstance(vm.token_mudanca(), str)

    def test_sem_pasta_de_interacoes_nao_estoura(self):
        """Modo local sem INTERACOES/ ainda tem de responder."""
        vm.PASTA_INTERACOES = os.path.join(self.tmp, "nao_existe")
        self.assertIsInstance(vm.token_mudanca(), str)

    def test_token_e_funcao_pura_do_estado(self):
        """Voltando ao estado anterior, o token volta — prova que ele descreve
        o ESTADO e nao acumula historia."""
        t0 = vm.token_mudanca()
        self._jsonl("tmp.jsonl")
        self.assertNotEqual(vm.token_mudanca(), t0)
        os.remove(os.path.join(self.inter, "tmp.jsonl"))
        self.assertEqual(vm.token_mudanca(), t0)


class ClienteSoBaixaQuandoPrecisa(unittest.TestCase):

    def _fonte(self):
        return INDEX.read_text(encoding="utf-8")

    def test_refresh_consulta_a_versao_antes(self):
        html = self._fonte()
        i = html.index("async function refreshDB(")
        corpo = html[i:i + 1400]
        self.assertIn("/api/versao", corpo)
        self.assertIn("_tokenDB", corpo)

    def test_ha_rede_de_seguranca_periodica(self):
        """Sem ela, uma fonte de mudanca esquecida deixaria a tela velha PARA
        SEMPRE. Com ela, o pior caso e' ~1 minuto."""
        html = self._fonte()
        self.assertIn("_FORCA_A_CADA", html)
        i = html.index("async function refreshDB(")
        self.assertIn("_FORCA_A_CADA", html[i:i + 1400],
                      "a constante existe mas refreshDB nao a usa")

    def test_da_para_forcar(self):
        html = self._fonte()
        self.assertIn("async function refreshDB(forcar)", html)

    def test_servidor_manda_o_token_junto_com_os_dados(self):
        """Buscar o token numa segunda ida poderia correr com uma escrita no
        meio e gravar assinatura de dado que nao e' o que esta na tela."""
        src = (Path(__file__).resolve().parent.parent
               / "src" / "visualizador" / "main.py").read_text(encoding="utf-8-sig")
        i = src.index('elif self.path == "/api/dados":')
        self.assertIn('["token"]', src[i:i + 700])

    def test_endpoint_versao_existe(self):
        src = (Path(__file__).resolve().parent.parent
               / "src" / "visualizador" / "main.py").read_text(encoding="utf-8-sig")
        self.assertIn('elif self.path == "/api/versao":', src)


if __name__ == "__main__":
    unittest.main()
