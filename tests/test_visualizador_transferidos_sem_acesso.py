# -*- coding: utf-8 -*-
"""Aba Transferidos: quem MUDOU mas nao tem acesso em sistema nenhum.

Medido na base real: das 18 pessoas detectadas numa carga, 10 tinham acesso
(viravam divergencia ACESSO_TRANSFERIDO) e 8 NAO — essas 8 mudaram de cargo ou
de gestor e nao apareciam em tela nenhuma do painel. Agora entram na aba com
sit="Sem acesso", FORA dos KPIs de revisao: e' movimentacao para conhecimento,
nao fila de trabalho.
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import visualizador.main as vm

_COLS_TRANSF = (
    "matricula TEXT, nome TEXT, campos_mudados TEXT, data_transferencia TEXT,"
    " cargo_codigo_anterior TEXT, cargo_anterior TEXT, departamento_anterior TEXT,"
    " centro_custo_anterior TEXT, gestor_anterior TEXT,"
    " cargo_codigo_atual TEXT, cargo_atual TEXT, departamento_atual TEXT,"
    " centro_custo_atual TEXT, gestor_atual TEXT, dt_importacao TEXT"
)


def _criar_db(db, transferidos=(), divergencias=(), com_transferidos=True):
    c = sqlite3.connect(db)
    c.executescript(
        "CREATE TABLE divergencias (tipo TEXT, sistema TEXT, usuario TEXT,"
        " nome_usuario TEXT, matricula TEXT, perfil_encontrado TEXT,"
        " data_identificacao TEXT, descricao TEXT);"
        "CREATE TABLE rh_ativos (matricula TEXT, nome TEXT, cargo_descricao TEXT,"
        " departamento TEXT, centro_custo_codigo TEXT, gestor TEXT);"
    )
    if com_transferidos:
        c.execute(f"CREATE TABLE transferidos ({_COLS_TRANSF})")
        c.executemany(
            "INSERT INTO transferidos VALUES (" + ",".join("?" * 15) + ")", transferidos)
    c.executemany("INSERT INTO divergencias VALUES (?,?,?,?,?,?,?,?)", divergencias)
    c.commit()
    c.close()


def _transf(mat, nome, campos="gestor", gestor_ant="CHEFE A", gestor_atu="CHEFE B",
            cargo_ant="ANALISTA", cargo_atu="ANALISTA"):
    return (mat, nome, campos, "2026-07-01",
            "CG", cargo_ant, "TI", "100", gestor_ant,
            "CG", cargo_atu, "TI", "100", gestor_atu, "")


def _div(mat, sistema="SYSTUR"):
    return ("ACESSO_TRANSFERIDO", sistema, "lg" + mat, "N" + mat, mat, "P1",
            "2026-07-01", f"Mudança de gestor — acesso pendente de revisão no sistema {sistema}")


class TestSemAcesso(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_transf_sa_")
        self._orig = (vm.DB_PATH, vm.SISTEMA, vm.PASTA_INTERACOES)
        vm.PASTA_INTERACOES = ""

    def tearDown(self):
        vm.DB_PATH, vm.SISTEMA, vm.PASTA_INTERACOES = self._orig

    def _rodar(self, transferidos, divergencias, sistema="", com_transferidos=True):
        db = os.path.join(self._tmp, f"t{len(os.listdir(self._tmp))}.db")
        _criar_db(db, transferidos, divergencias, com_transferidos)
        vm.DB_PATH = db
        vm.SISTEMA = sistema
        return vm.listar_transferidos()

    def test_quem_nao_tem_acesso_aparece_marcado(self):
        r = self._rodar([_transf("10", "COM ACESSO"), _transf("20", "SEM ACESSO")],
                        [_div("10")])
        por_mat = {d["m"]: d for d in r["lista"]}
        self.assertEqual(len(r["lista"]), 2)
        self.assertFalse(por_mat["10"].get("sem_acesso"))
        self.assertTrue(por_mat["20"]["sem_acesso"])
        self.assertEqual(por_mat["20"]["sit"], "Sem acesso")
        self.assertEqual(por_mat["20"]["acessos"], [])

    def test_sem_acesso_fica_fora_dos_kpis_de_revisao(self):
        r = self._rodar([_transf("10", "A"), _transf("20", "B"), _transf("30", "C")],
                        [_div("10")])
        self.assertEqual(r["kpis"]["revisar"], 1)
        self.assertEqual(r["kpis"]["total"], 1, "total = fila de revisao")
        self.assertEqual(r["kpis"]["sem_acesso"], 2)

    def test_sem_acesso_leva_o_de_para(self):
        r = self._rodar([_transf("20", "SEM ACESSO", gestor_ant="ANDREIA",
                                 gestor_atu="NATHALIA")], [])
        (d,) = r["lista"]
        self.assertEqual(d["de_para"], [{"campo": "gestor", "de": "ANDREIA",
                                         "para": "NATHALIA"}])
        self.assertEqual(d["gestor"], "NATHALIA", "mostra o gestor ATUAL na coluna")
        self.assertEqual(d["dt_mov"], "2026-07-01")

    def test_nao_duplica_quem_ja_esta_na_fila(self):
        r = self._rodar([_transf("10", "COM ACESSO")], [_div("10"), _div("10", "SIG")])
        self.assertEqual([d["m"] for d in r["lista"]], ["10"])
        self.assertEqual(len(r["lista"][0]["acessos"]), 2)

    def test_escopo_por_sistema_nao_lista_sem_acesso(self):
        # com <visualizador><sistema> a aba e' daquele sistema; quem nao tem
        # acesso NENHUM nao diz nada sobre ele — seria ruido.
        r = self._rodar([_transf("10", "A"), _transf("20", "B")],
                        [_div("10", "SYSTUR")], sistema="SYSTUR")
        self.assertEqual([d["m"] for d in r["lista"]], ["10"])
        self.assertEqual(r["kpis"].get("sem_acesso"), 0)

    def test_banco_sem_a_tabela_transferidos(self):
        # Processador anterior a esta versao: a aba segue com a fila normal
        r = self._rodar([], [_div("10")], com_transferidos=False)
        self.assertEqual([d["m"] for d in r["lista"]], ["10"])
        self.assertEqual(r["kpis"]["sem_acesso"], 0)

    def test_campos_mudados_vem_da_tabela_quando_nao_ha_divergencia(self):
        r = self._rodar([_transf("20", "SEM ACESSO", campos="cargo, gestor")], [])
        self.assertEqual(r["lista"][0]["campos"], "cargo, gestor")


if __name__ == "__main__":
    unittest.main(verbosity=2)
