# -*- coding: utf-8 -*-
"""Repositorio de interacoes multiusuario (.jsonl por usuario) — escrita com
envelope v1, isolamento por usuario, leitura tolerante e consolidacao.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.interacoes import repositorio_interacoes as ri


class TestEnvelopeEEscrita(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="cvc_int_")

    def _ler_linhas(self, usuario):
        p = ri.arquivo_do_usuario(self.dir, usuario)
        return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]

    def test_gravar_aplica_envelope_v1(self):
        ri.gravar(self.dir, {"tipo_interacao": "QUARENTENA", "registro_id": "R1",
                             "acao": "ENVIAR", "usuario": "op"}, "op")
        it = self._ler_linhas("op")[0]
        self.assertEqual(it["schema_version"], ri.SCHEMA_VERSION)   # 1
        self.assertEqual(it["extras"], {})
        self.assertIn("data_acao", it)                              # injetado

    def test_data_acao_preservada_se_fornecida(self):
        ri.gravar(self.dir, {"tipo_interacao": "RESOLUCAO", "registro_id": "R2",
                             "acao": "RESOLVER", "data_acao": "2026-06-01T10:00:00"}, "op")
        self.assertEqual(self._ler_linhas("op")[0]["data_acao"], "2026-06-01T10:00:00")

    def test_isolamento_por_usuario(self):
        ri.gravar(self.dir, {"tipo_interacao": "QUARENTENA", "registro_id": "A"}, "alice")
        ri.gravar(self.dir, {"tipo_interacao": "QUARENTENA", "registro_id": "B"}, "bob")
        self.assertTrue(Path(ri.arquivo_do_usuario(self.dir, "alice")).exists())
        self.assertTrue(Path(ri.arquivo_do_usuario(self.dir, "bob")).exists())
        rids = {x["registro_id"] for x in ri.ler_todas(self.dir)}
        self.assertEqual(rids, {"A", "B"})

    def test_sanitiza_nome_de_usuario(self):
        p = ri.arquivo_do_usuario(self.dir, "DOMAIN\\joao da silva")
        self.assertIn("interacao_DOMAIN_joao_da_silva.jsonl", p)

    def test_append_nao_sobrescreve(self):
        ri.gravar(self.dir, {"registro_id": "R1"}, "op")
        ri.gravar(self.dir, {"registro_id": "R2"}, "op")
        self.assertEqual(len(self._ler_linhas("op")), 2)


class TestLerTodas(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="cvc_int2_")

    def test_pasta_inexistente_retorna_vazio(self):
        self.assertEqual(ri.ler_todas(os.path.join(self.dir, "nope")), [])

    def test_tolerante_a_linha_corrompida_e_em_branco(self):
        p = os.path.join(self.dir, "interacao_op.jsonl")
        with open(p, "w", encoding="utf-8") as f:
            f.write(json.dumps({"registro_id": "OK", "schema_version": 1}) + "\n")
            f.write("\n")                 # linha em branco
            f.write("{linha corrompida\n") # json invalido
        lidas = ri.ler_todas(self.dir)
        self.assertEqual(len(lidas), 1)
        self.assertEqual(lidas[0]["registro_id"], "OK")

    def test_legado_v0_recebe_schema_version_zero(self):
        p = os.path.join(self.dir, "interacao_op.jsonl")
        with open(p, "w", encoding="utf-8") as f:
            f.write(json.dumps({"tipo_interacao": "QUARENTENA", "registro_id": "V0"}) + "\n")
        it = ri.ler_todas(self.dir)[0]
        self.assertEqual(it["schema_version"], 0)   # legado implicito
        self.assertEqual(it["extras"], {})


class TestConsolidar(unittest.TestCase):
    def test_vence_o_mais_recente_por_registro(self):
        its = [
            {"tipo_interacao": "QUARENTENA", "registro_id": "R1", "acao": "ENVIAR",
             "data_acao": "2026-06-01T10:00:00"},
            {"tipo_interacao": "QUARENTENA", "registro_id": "R1", "acao": "RESOLVER",
             "data_acao": "2026-06-05T10:00:00"},
        ]
        cons = ri.consolidar(its, tipo="QUARENTENA")
        self.assertEqual(cons["R1"]["acao"], "RESOLVER")

    def test_filtra_por_tipo(self):
        its = [
            {"tipo_interacao": "QUARENTENA", "registro_id": "R1", "data_acao": "1"},
            {"tipo_interacao": "RESOLUCAO", "registro_id": "R2", "data_acao": "1"},
        ]
        self.assertEqual(set(ri.consolidar(its, tipo="RESOLUCAO")), {"R2"})

    def test_ignora_sem_registro_id(self):
        its = [{"tipo_interacao": "QUARENTENA", "data_acao": "1"}]
        self.assertEqual(ri.consolidar(its), {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
