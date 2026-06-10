# -*- coding: utf-8 -*-
"""Dobra das interacoes multiusuario — idempotencia, quarentena, multiusuario,
recuperacao de pasta orfa, rename atomico e atalhos.
"""
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from aplicacao.casos_de_uso.dobrar_interacoes import DobrarInteracoes


def _q_enviar(rid, nome="ANA", data="2026-06-01T10:00:00", usuario="op1"):
    return {"tipo_interacao": "QUARENTENA", "registro_id": rid, "acao": "ENVIAR",
            "nome": nome, "sistema": "SYSTUR", "origem": "Inclusão / Alteração",
            "usuario": usuario, "data_acao": data}


def _q_resolver(rid, data="2026-06-02T10:00:00", usuario="op2"):
    return {"tipo_interacao": "QUARENTENA", "registro_id": rid, "acao": "RESOLVER",
            "usuario": usuario, "data_acao": data}


def _atalho(rid, acao="CRIAR", nome="filtro X", data="2026-06-01T10:00:00", usuario="op1"):
    return {"tipo_interacao": "ATALHO", "registro_id": rid, "acao": acao,
            "extras": {"nome": nome, "origem": "incl", "filtros": [{"id": "sistema"}]},
            "usuario": usuario, "data_acao": data}


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_dobra_")
        self._db = os.path.join(self._tmp, "iam.db")
        self._inter = os.path.join(self._tmp, "INTERACOES")
        os.makedirs(self._inter)

    def _gravar(self, interacao, arquivo="interacao_op.jsonl", pasta=None):
        pasta = pasta or self._inter
        os.makedirs(pasta, exist_ok=True)
        with open(os.path.join(pasta, arquivo), "a", encoding="utf-8") as f:
            f.write(json.dumps(interacao, ensure_ascii=False) + "\n")

    def _dobrar(self):
        DobrarInteracoes(self._db, self._inter).executar()

    def _rows(self, tabela):
        c = sqlite3.connect(self._db)
        c.row_factory = sqlite3.Row
        try:
            existe = c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                               [tabela]).fetchone()
            return [dict(r) for r in c.execute(f"SELECT * FROM {tabela}")] if existe else []
        finally:
            c.close()


class TestQuarentenaFluxo(_Base):

    def test_enviar_insere_na_quarentena(self):
        self._gravar(_q_enviar("R1"))
        self._dobrar()
        q = self._rows("quarentena")
        self.assertEqual(len(q), 1)
        self.assertEqual(q[0]["usuario"], "R1")
        self.assertEqual(q[0]["data_inicio"], "2026-06-01")

    def test_enviar_idempotente_nao_duplica(self):
        self._gravar(_q_enviar("R1"))
        self._dobrar()
        # mesma interacao chega de novo num novo ciclo
        self._gravar(_q_enviar("R1"))
        self._dobrar()
        self.assertEqual(len(self._rows("quarentena")), 1)

    def test_resolver_move_para_historico(self):
        self._gravar(_q_enviar("R1"))
        self._dobrar()
        self._gravar(_q_resolver("R1"))
        self._dobrar()
        self.assertEqual(self._rows("quarentena"), [])
        hist = self._rows("quarentena_historico")
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist[0]["usuario"], "R1")
        self.assertEqual(hist[0]["motivo"], "Resolvido")


class TestMultiusuarioEOrfao(_Base):

    def test_multiusuario_consolida_dois_arquivos(self):
        self._gravar(_q_enviar("R1"), arquivo="interacao_userA.jsonl")
        self._gravar(_q_enviar("R2"), arquivo="interacao_userB.jsonl")
        self._dobrar()
        usuarios = {r["usuario"] for r in self._rows("quarentena")}
        self.assertEqual(usuarios, {"R1", "R2"})

    def test_recupera_pasta_processando_orfa(self):
        # simula crash anterior: INTERACOES_processando com 1 envio
        orfa = self._tmp + os.sep + "INTERACOES_processando"
        self._gravar(_q_enviar("ORF"), arquivo="interacao_x.jsonl", pasta=orfa)
        # e uma interacao nova na INTERACOES atual
        self._gravar(_q_enviar("NEW"))
        self._dobrar()
        usuarios = {r["usuario"] for r in self._rows("quarentena")}
        self.assertEqual(usuarios, {"ORF", "NEW"})

    def test_rename_atomico_reseta_pasta(self):
        self._gravar(_q_enviar("R1"))
        self._dobrar()
        # INTERACOES volta a existir vazia; _processando foi removida
        self.assertTrue(Path(self._inter).exists())
        self.assertEqual(list(Path(self._inter).glob("*.jsonl")), [])
        self.assertFalse(Path(self._tmp, "INTERACOES_processando").exists())


class TestAtalhos(_Base):

    def test_atalho_criar_e_persistido(self):
        self._gravar(_atalho("A1", acao="CRIAR"))
        self._dobrar()
        a = self._rows("atalhos")
        self.assertEqual(len(a), 1)
        self.assertEqual(a[0]["id"], "A1")
        self.assertEqual(a[0]["nome"], "filtro X")

    def test_atalho_excluir_vence_criar_anterior(self):
        # CRIAR (antigo) + EXCLUIR (recente) no mesmo lote -> exclusao vence
        self._gravar(_atalho("A1", acao="CRIAR", data="2026-06-01T10:00:00"))
        self._gravar(_atalho("A1", acao="EXCLUIR", data="2026-06-02T10:00:00"))
        self._dobrar()
        self.assertEqual(self._rows("atalhos"), [])

    def test_dobra_idempotente_sem_novas_interacoes(self):
        self._gravar(_atalho("A1"))
        self._dobrar()
        self._dobrar()   # nada novo
        self.assertEqual(len(self._rows("atalhos")), 1)


class TestReaberturaEOrdem(_Base):

    def test_reabertura_enviar_resolver_enviar(self):
        # 3 ciclos de dobra: ENVIAR -> RESOLVER -> ENVIAR (reabertura)
        self._gravar(_q_enviar("R1", data="2026-06-01T10:00:00"))
        self._dobrar()
        self.assertEqual(len(self._rows("quarentena")), 1)
        self._gravar(_q_resolver("R1", data="2026-06-02T10:00:00"))
        self._dobrar()
        self.assertEqual(self._rows("quarentena"), [])
        self.assertEqual(len(self._rows("quarentena_historico")), 1)
        # reabertura
        self._gravar(_q_enviar("R1", data="2026-06-03T10:00:00"))
        self._dobrar()
        self.assertEqual(len(self._rows("quarentena")), 1)            # de volta
        self.assertEqual(len(self._rows("quarentena_historico")), 1)  # historico preservado

    def test_no_mesmo_lote_vence_o_mais_recente(self):
        # ENVIAR(t1) + RESOLVER(t2) + ENVIAR(t3) no MESMO arquivo -> ultima = ENVIAR
        self._gravar(_q_enviar("R1", data="2026-06-01T10:00:00"))
        self._gravar(_q_resolver("R1", data="2026-06-02T10:00:00"))
        self._gravar(_q_enviar("R1", data="2026-06-03T10:00:00"))
        self._dobrar()
        self.assertEqual(len(self._rows("quarentena")), 1)            # acao mais recente
        self.assertEqual(self._rows("quarentena_historico"), [])      # RESOLVER intermediario ignorado

    def test_resolver_orfao_sem_envio_previo(self):
        # RESOLVER sem ENVIAR previo: gera linha de historico, sem quebrar
        self._gravar(_q_resolver("R9", data="2026-06-02T10:00:00"))
        self._dobrar()
        self.assertEqual(self._rows("quarentena"), [])
        self.assertEqual(len(self._rows("quarentena_historico")), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
