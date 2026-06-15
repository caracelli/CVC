# -*- coding: utf-8 -*-
"""_calcular_visao_geral do Visualizador: janela movel de 30 dias (chamados,
movimentacao RH), aging por faixa, cobertura de vinculacao, acessos de
desligado e desligados urgentes. Datas relativas a hoje (janela nao quebra).
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
import visualizador.main as vm

IC = "IC_INTEGRADOR_CONTABIL"

_SQL_RES = """
CREATE TABLE IF NOT EXISTS resolucoes (
  registro_id TEXT PRIMARY KEY, ticket TEXT, ticket_url TEXT, descricao TEXT,
  pendencias TEXT, cargo TEXT, centro_custo TEXT, nome TEXT,
  resolvido_por TEXT, resolvido_em TEXT, dobrado_em TEXT)
"""


def _d(days):
    return (date.today() - timedelta(days=days)).isoformat()


def _dt(days):
    return _d(days) + " 10:00:00"


class TestVisaoGeral(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="cvc_vg_")
        cls.db = os.path.join(cls._tmp, "iam.db")
        ConexaoBancoDados(cls.db).inicializar()
        c = sqlite3.connect(cls.db)
        # RH
        c.executescript(
            "INSERT INTO rh_ativos (matricula,nome,cpf,situacao) VALUES "
            "('M1','ANA','111','ATIVO'),('M2','BRUNO','222','ATIVO');"
            "INSERT INTO rh_desligados (matricula,nome,cpf,cargo_descricao,data_desligamento) "
            "VALUES ('D1','CARLOS','333','ASSIST','%s');" % _d(10)
        )
        # validacao (aging + chamados.identificados): 4 idades distintas, todas PENDENTE
        for i, age in enumerate((0, 20, 60, 200)):
            c.execute(
                "INSERT INTO validacao_acessos (matricula,nome,sistema,perfil_esperado,"
                "status,situacao_acao,dt_processamento) VALUES (?,?,?,?,?,?,?)",
                [f"V{i}", f"V{i}", IC, "IC CONSULTA", "SEM_ACESSO", "PENDENTE", _dt(age)])
        # acessos: 3 vinculaveis (CPF/EMAIL/CPF) + 1 NAO_VINCULADO; a4 -> desligado D1
        c.executescript(
            "INSERT INTO acessos_sistemas (sistema,usuario,perfil,matricula_vinculada,metodo_vinculacao) VALUES "
            "('%s','u1','P','M1','CPF'),"
            "('%s','u2','P','M2','EMAIL'),"
            "('%s','u3','P',NULL,'NAO_VINCULADO'),"
            "('%s','u4','P','D1','CPF');" % (IC, IC, IC, IC)
        )
        # divergencias (div_tipos / div_sistemas)
        c.executescript(
            "INSERT INTO divergencias (id,tipo,sistema,usuario,nome_usuario,descricao,resolvida) VALUES "
            "('d1','ACESSO_SEM_VINCULO_RH','%s','u3','U3','x',0),"
            "('d2','PERFIL_INVALIDO','%s','u4','U4','x',0);" % (IC, IC)
        )
        # historico (mov_rh ultimos 30d): 2 admissoes + 1 alteracao + 1 desligamento recentes; 1 antigo ignorado
        c.executescript(
            "INSERT INTO historico (data_snapshot,entidade,chave_entidade,tipo_mudanca) VALUES "
            "('%s','RH_ATIVO','M1','NOVO'),"
            "('%s','RH_ATIVO','M2','NOVO'),"
            "('%s','RH_ATIVO','M1','ALTERADO'),"
            "('%s','RH_DESLIGADO','D1','NOVO'),"
            "('%s','RH_ATIVO','MX','NOVO');" % (_d(2), _d(2), _d(2), _d(2), _d(40))
        )
        # resolucoes (chamados.resolvidos ultimos 30d): 1 recente + 1 antigo
        c.executescript(_SQL_RES)
        c.execute("INSERT INTO resolucoes (registro_id,resolvido_em) VALUES ('V0',?)", [_dt(5)])
        c.execute("INSERT INTO resolucoes (registro_id,resolvido_em) VALUES ('V1',?)", [_dt(40)])
        c.commit()
        c.close()

        # bi_divergencias via garantir_estrutura (monkeypatch)
        cls._orig = (vm.DB_PATH, vm.SISTEMA, vm._BASE)
        vm.DB_PATH = cls.db
        vm.SISTEMA = ""
        vm._BASE = None
        vm.garantir_estrutura(force=True)

        cls.conn = sqlite3.connect(cls.db)
        cls.vg = vm._calcular_visao_geral(cls.conn, sistema="")

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        vm.DB_PATH, vm.SISTEMA, vm._BASE = cls._orig

    def test_chamados_janela_30d(self):
        self.assertEqual(self.vg["chamados"]["identificados"], 2)   # idades 0 e 20
        self.assertEqual(self.vg["chamados"]["resolvidos"], 1)      # so o de 5 dias

    def test_aging_por_faixa(self):
        self.assertEqual(self.vg["aging"], {"0-7": 1, "8-30": 1, "31-90": 1, "90+": 1})

    def test_movimentacao_rh_30d(self):
        self.assertEqual(self.vg["mov_rh"],
                         {"admissoes": 2, "alteracoes": 1, "desligamentos": 1})

    def test_cobertura_vinculacao(self):
        self.assertEqual(self.vg["total_acessos"], 4)
        self.assertEqual(self.vg["acessos_vinc"], 3)   # CPF/EMAIL/CPF (NAO_VINCULADO fora)
        self.assertEqual(self.vg["cobertura_pct"], 75.0)

    def test_acessos_de_desligado(self):
        self.assertEqual(self.vg["acessos_deslig"], 1)   # u4 -> D1

    def test_universo_rh(self):
        self.assertEqual(self.vg["rh_ativos"], 2)
        self.assertEqual(self.vg["rh_desligados"], 1)

    def test_divergencias_por_tipo_e_sistema(self):
        # div_tipos/div_sistemas vem da fonte unificada (bi_divergencias) e contam
        # USUARIOS distintos por tipo/sistema, excluindo OK — consistente com os
        # cards do topo. bi = 4 SEM_ACESSO (V0-V3) + 1 ACESSO_SEM_VINCULO_RH (u3);
        # PERFIL_INVALIDO da tabela 'divergencias' nao entra no bi.
        self.assertEqual(self.vg["div_tipos"],
                         {"SEM_ACESSO": 4, "ACESSO_SEM_VINCULO_RH": 1})
        self.assertEqual(self.vg["div_sistemas"], {IC: 5})

    def test_top_urgentes_desligado_com_acesso(self):
        top = self.vg["top_urgentes"]
        self.assertEqual(len(top), 1)
        self.assertEqual(top[0]["nome"], "CARLOS")
        self.assertEqual(top[0]["dias"], 10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
