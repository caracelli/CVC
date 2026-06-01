# -*- coding: utf-8 -*-
"""Testes da feature de Atalhos (filtros salvos) — caminho de DOBRA.

Cobre a consolidacao das interacoes ATALHO (.jsonl da rede) na tabela
`atalhos` pelo Processador (DobrarInteracoes):

  - CRIAR  -> INSERT OR REPLACE (cria/atualiza)
  - EXCLUIR -> DELETE
  - dedup por (registro_id, data_acao): vence a interacao mais recente
  - idempotencia entre ciclos: refold do mesmo id nao duplica

A logica de servidor (criar_atalho/excluir_atalho/listar_atalhos em
src/visualizador/main.py) carrega config no import e e' coberta indiretamente:
o ENVELOPE que ela grava e' exatamente o exercitado aqui.
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.interacoes.repositorio_interacoes import gravar
from aplicacao.casos_de_uso.dobrar_interacoes import DobrarInteracoes


def _atalho(rid, acao="CRIAR", usuario="joao", data_acao="2026-05-29T10:00:00",
            nome=None, origem="incl", filtros=None):
    it = {
        "schema_version": 1,
        "tipo_interacao": "ATALHO",
        "registro_id": rid,
        "acao": acao,
        "usuario": usuario,
        "data_acao": data_acao,
        "extras": {},
    }
    if acao != "EXCLUIR":
        it["extras"] = {
            "nome": nome if nome is not None else rid,
            "origem": origem,
            "filtros": filtros if filtros is not None else [],
        }
    return it


class TestDobraAtalhos(unittest.TestCase):

    def setUp(self):
        self.tmpdb = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmpdb.close()
        self.pasta = tempfile.mkdtemp(prefix="interacoes_atl_")

    def tearDown(self):
        import shutil
        try:
            os.unlink(self.tmpdb.name)
        except Exception:
            pass
        shutil.rmtree(self.pasta, ignore_errors=True)
        # a dobra cria INTERACOES_processando irmao; limpa se sobrou
        proc = Path(self.pasta).with_name(Path(self.pasta).name + "_processando")
        shutil.rmtree(proc, ignore_errors=True)

    def _dobrar(self):
        DobrarInteracoes(caminho_banco=self.tmpdb.name,
                         pasta_interacoes=self.pasta).executar()

    def _atalhos(self):
        c = sqlite3.connect(self.tmpdb.name)
        c.row_factory = sqlite3.Row
        try:
            try:
                rows = c.execute("SELECT * FROM atalhos ORDER BY id").fetchall()
            except sqlite3.OperationalError:
                return []  # tabela nem criada
            return [dict(r) for r in rows]
        finally:
            c.close()

    # ------------------------------------------------------------------
    def test_criar_insere_na_tabela(self):
        gravar(self.pasta, _atalho(
            "atl_1", nome="Desligados SYSTUR",
            filtros=[["tipo", "Sem Vínculo RH"], ["sistema", "SYSTUR"]]),
            "joao")
        self._dobrar()
        rows = self._atalhos()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "atl_1")
        self.assertEqual(rows[0]["nome"], "Desligados SYSTUR")
        self.assertEqual(rows[0]["origem"], "incl")
        self.assertEqual(rows[0]["criado_por"], "joao")
        # filtros gravados como JSON, com acentos preservados
        self.assertIn("Sem Vínculo RH", rows[0]["filtros"])

    def test_excluir_remove_quando_mais_recente(self):
        gravar(self.pasta, _atalho("atl_1", acao="CRIAR",
                                   data_acao="2026-05-29T10:00:00"), "joao")
        gravar(self.pasta, _atalho("atl_1", acao="EXCLUIR",
                                   data_acao="2026-05-29T11:00:00"), "joao")
        self._dobrar()
        self.assertEqual(self._atalhos(), [],
                         "EXCLUIR mais recente vence -> tabela vazia")

    def test_criar_vence_excluir_mais_antigo(self):
        gravar(self.pasta, _atalho("atl_1", acao="EXCLUIR",
                                   data_acao="2026-05-29T10:00:00"), "joao")
        gravar(self.pasta, _atalho("atl_1", acao="CRIAR", nome="Recriado",
                                   data_acao="2026-05-29T12:00:00"), "joao")
        self._dobrar()
        rows = self._atalhos()
        self.assertEqual(len(rows), 1, "CRIAR mais recente vence")
        self.assertEqual(rows[0]["nome"], "Recriado")

    def test_dedup_dois_criar_vence_o_mais_recente(self):
        gravar(self.pasta, _atalho("atl_1", nome="Antigo",
                                   data_acao="2026-05-29T08:00:00"), "joao")
        gravar(self.pasta, _atalho("atl_1", nome="Novo",
                                   data_acao="2026-05-29T09:00:00"), "joao")
        self._dobrar()
        rows = self._atalhos()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["nome"], "Novo")

    def test_idempotente_refold_mesmo_id_nao_duplica(self):
        # 1o ciclo: cria atl_1
        gravar(self.pasta, _atalho("atl_1", nome="V1",
                                   data_acao="2026-05-29T08:00:00"), "joao")
        self._dobrar()
        self.assertEqual(len(self._atalhos()), 1)
        # 2o ciclo: novo CRIAR mesmo id (INSERT OR REPLACE) -> ainda 1 linha
        gravar(self.pasta, _atalho("atl_1", nome="V2",
                                   data_acao="2026-05-29T09:00:00"), "joao")
        self._dobrar()
        rows = self._atalhos()
        self.assertEqual(len(rows), 1, "refold do mesmo id nao duplica")
        self.assertEqual(rows[0]["nome"], "V2")

    def test_atalhos_de_usuarios_distintos_coexistem(self):
        gravar(self.pasta, _atalho("atl_joao", usuario="joao"), "joao")
        gravar(self.pasta, _atalho("atl_maria", usuario="maria"), "maria")
        self._dobrar()
        rows = self._atalhos()
        self.assertEqual(len(rows), 2)
        por_user = {r["criado_por"] for r in rows}
        self.assertEqual(por_user, {"joao", "maria"})


if __name__ == "__main__":
    unittest.main()
