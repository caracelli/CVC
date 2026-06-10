# -*- coding: utf-8 -*-
"""Overlay AO VIVO do construir_db (Visualizador): quarentena esconde o usuario
(tabela dobrada + interacao viva ENVIAR/RESOLVER); resolucao marca o usuario
como Resolvido (interacao viva vence a dobrada no banco).

Sem servidor: monkeypatch de DB_PATH/SISTEMA/PASTA_INTERACOES como o selftest.
"""
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
import visualizador.main as vm

IC = "IC_INTEGRADOR_CONTABIL"

_SQL_RES = """
CREATE TABLE IF NOT EXISTS resolucoes (
  registro_id TEXT PRIMARY KEY, ticket TEXT NOT NULL, ticket_url TEXT,
  descricao TEXT, pendencias TEXT, cargo TEXT, centro_custo TEXT, nome TEXT,
  resolvido_por TEXT, resolvido_em TEXT, dobrado_em TEXT)
"""


def _seed_validacao(db, matriculas):
    c = sqlite3.connect(db)
    for m in matriculas:
        c.execute(
            "INSERT INTO validacao_acessos (matricula,nome,sistema,perfil_esperado,"
            "perfil_atual,status,situacao_acao,origem_matriz,dt_processamento) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            [m, f"NOME {m}", IC, "IC CONSULTA", "", "SEM_ACESSO", "PENDENTE",
             "MATRIZ", "2026-05-01 10:00:00"])
    c.commit()
    c.close()


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_ovl_")
        self.db = os.path.join(self._tmp, "iam.db")
        self.inter = os.path.join(self._tmp, "INTERACOES")
        os.makedirs(self.inter)
        ConexaoBancoDados(self.db).inicializar()
        _seed_validacao(self.db, ["U1", "U2", "U3"])
        self._orig = (vm.DB_PATH, vm.SISTEMA, vm.PASTA_INTERACOES, vm._BASE)
        vm.DB_PATH = self.db
        vm.SISTEMA = ""
        vm.PASTA_INTERACOES = self.inter
        vm._BASE = None
        vm.garantir_estrutura(force=True)
        self.addCleanup(self._restaurar)

    def _restaurar(self):
        vm.DB_PATH, vm.SISTEMA, vm.PASTA_INTERACOES, vm._BASE = self._orig

    def _quar(self, usuario, data_fim="2099-12-31"):
        c = sqlite3.connect(self.db)
        c.execute(
            "INSERT INTO quarentena (usuario,nome_usuario,sistema,matricula,origem,"
            "data_inicio,data_fim,status,criado_por,criado_em) "
            "VALUES (?,?,?,?,?,?,?, 'Em quarentena', ?, ?)",
            [usuario, usuario, IC, usuario, "Inclusão", "2026-05-01", data_fim,
             "op", "2026-05-01"])
        c.commit()
        c.close()

    def _jsonl(self, it, arq="interacao_op.jsonl"):
        with open(os.path.join(self.inter, arq), "a", encoding="utf-8") as f:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")

    def _db(self):
        vm._BASE = None
        return vm.construir_db()


class TestQuarentenaOverlay(_Base):

    def test_quarentena_tabela_e_viva_escondem_usuarios(self):
        self._quar("U1")                              # dobrada na tabela
        self._jsonl({"tipo_interacao": "QUARENTENA", "registro_id": "U2",
                     "acao": "ENVIAR", "nome": "U2", "sistema": IC,
                     "data_acao": "2026-06-01T10:00:00", "usuario": "op"})
        d = self._db()
        usuarios = {u["u"] for u in d["users"]}
        self.assertEqual(usuarios, {"U3"})            # U1 e U2 escondidos
        self.assertEqual(d["vg"]["quarentena_ativa"], 2)

    def test_resolver_vivo_reexibe_quem_estava_na_tabela(self):
        self._quar("U1")
        self._jsonl({"tipo_interacao": "QUARENTENA", "registro_id": "U1",
                     "acao": "RESOLVER", "data_acao": "2026-06-05T10:00:00",
                     "usuario": "op"})
        usuarios = {u["u"] for u in self._db()["users"]}
        self.assertIn("U1", usuarios)                 # RESOLVER tira da quarentena


class TestResolucaoOverlay(_Base):

    def test_resolucao_viva_marca_resolvido(self):
        self._jsonl({"tipo_interacao": "RESOLUCAO", "registro_id": "U3",
                     "ticket": "IAM-NEW", "data_acao": "2026-06-02T10:00:00",
                     "usuario": "op", "pendencias": []})
        u3 = next(u for u in self._db()["users"] if u["u"] == "U3")
        self.assertTrue(u3.get("resolvido"))
        self.assertEqual(u3["resolucao"]["ticket"], "IAM-NEW")
        self.assertTrue(all(d["s"] == "Resolvido" for d in u3["divs"]))

    def test_resolucao_viva_vence_a_dobrada(self):
        # dobrada no banco com ticket antigo
        c = sqlite3.connect(self.db)
        c.executescript(_SQL_RES)
        c.execute("INSERT INTO resolucoes (registro_id,ticket,resolvido_em) "
                  "VALUES ('U3','IAM-OLD','2026-05-20T10:00:00')")
        c.commit()
        c.close()
        # interacao viva mais recente com ticket novo
        self._jsonl({"tipo_interacao": "RESOLUCAO", "registro_id": "U3",
                     "ticket": "IAM-NEW", "data_acao": "2026-06-02T10:00:00",
                     "usuario": "op", "pendencias": []})
        u3 = next(u for u in self._db()["users"] if u["u"] == "U3")
        self.assertEqual(u3["resolucao"]["ticket"], "IAM-NEW")

    def test_aderente_vence_resolucao_so_na_linha_OK(self):
        # Transicao Resolvido->Aderente, POR DIV: UMIX tem OK (IC) + pendencia
        # (SYSTUR). Com resolucao viva, a linha OK vira ADERENTE (vence o overlay)
        # e a pendencia vira RESOLVIDO. Sem isso, o aderente ficava preso em Resolvido.
        c = sqlite3.connect(self.db)
        c.execute(
            "INSERT INTO validacao_acessos (matricula,nome,sistema,perfil_esperado,"
            "perfil_atual,status,situacao_acao,origem_matriz,dt_processamento) VALUES "
            "('UMIX','NOME UMIX',?,'IC CONSULTA','IC CONSULTA','OK','OK','MATRIZ','2026-05-10'),"
            "('UMIX','NOME UMIX','SYSTUR','S1','','SEM_ACESSO','PENDENTE','MATRIZ','2026-05-10')",
            [IC])
        c.commit()
        c.close()
        vm.garantir_estrutura(force=True)   # rebuild bi com as 2 linhas de UMIX
        self._jsonl({"tipo_interacao": "RESOLUCAO", "registro_id": "UMIX",
                     "ticket": "IAM-MIX", "data_acao": "2026-06-03T10:00:00",
                     "usuario": "op", "pendencias": []})
        umix = next(u for u in self._db()["users"] if u["u"] == "UMIX")
        self.assertTrue(umix.get("resolvido"))               # tem o registro de resolucao
        por_tipo = {d["t"]: d["s"] for d in umix["divs"]}
        self.assertEqual(por_tipo["OK"], "Aderente")         # linha OK vence -> Aderente
        self.assertEqual(por_tipo["SEM_ACESSO"], "Resolvido")  # pendencia -> Resolvido


if __name__ == "__main__":
    unittest.main(verbosity=2)
