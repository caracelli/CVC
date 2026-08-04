# -*- coding: utf-8 -*-
"""O schema so pode crescer: banco ANTIGO + codigo NOVO nao pode perder dado.

O cliente esta em homologacao com base viva desde 08/06/2026 — quarentenas,
resolucoes sob ticket e trilha de historico que NAO podem sumir num deploy.
Aqui simulamos bancos de versoes anteriores (sem as tabelas novas, com colunas
faltando) e provamos que `inicializar()` cria o que falta SEM tocar no que ja
existe, e que o painel novo le banco velho sem quebrar.
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import visualizador.main as vm
from infraestrutura.banco_dados.conexao import ConexaoBancoDados

# Tabelas criadas NESTA versao — sao elas que o deploy tem de acrescentar
_TABELAS_NOVAS = {"transferidos", "revalidacao_transferido"}

# Tabelas gravaveis do painel: nao vem do ORM do Processador (o visualizador as
# cria por SQL), mas EXISTEM na base do cliente e guardam o trabalho manual.
_SQL_PAINEL = """
CREATE TABLE quarentena (
  registro_id TEXT PRIMARY KEY, nome TEXT, sistema TEXT, motivo TEXT,
  dias INTEGER, movido_em TEXT, movido_por TEXT);
CREATE TABLE resolucoes (
  registro_id TEXT PRIMARY KEY, ticket TEXT, motivo TEXT, resolvido_por TEXT,
  resolvido_em TEXT);
"""


def _criar_schema_anterior(caminho):
    """Monta a base da versao ANTERIOR a partir do PROPRIO schema real, apenas
    removendo as tabelas novas. Escrever o CREATE TABLE a mao dava um schema que
    nunca existiu no campo — e os testes passavam a caçar defeito imaginario."""
    from sqlalchemy import create_engine
    from infraestrutura.banco_dados.schema import Base
    engine = create_engine(f"sqlite:///{caminho}")
    tabelas = [t for nome, t in Base.metadata.tables.items()
               if nome not in _TABELAS_NOVAS]
    Base.metadata.create_all(engine, tables=tabelas)
    engine.dispose()
    c = sqlite3.connect(caminho)
    c.executescript(_SQL_PAINEL)
    c.commit()
    c.close()

DADOS_VIVOS = {
    "quarentena": ("Q-1", "ANA", "SYSTUR", "aguardando area", 30,
                   "2026-06-10 10:00:00", "bruna"),
    "resolucoes": ("R-1", "IAM-123", "Exceção", "bruna", "2026-06-11 09:00:00"),
}


def _banco_antigo(caminho):
    _criar_schema_anterior(caminho)
    c = sqlite3.connect(caminho)
    c.execute("INSERT INTO rh_ativos (matricula,nome,cpf,cargo_codigo,"
              "cargo_descricao,centro_custo_codigo,departamento,situacao,email,"
              "gestor,tipo_vinculo) VALUES ('1','ANA','111','CG','ANALISTA',"
              "'100','TI','ATIVO','a@x','CHEFE','FUNCIONARIO')")
    c.execute("INSERT INTO rh_desligados (matricula,nome,cpf,cargo_descricao,"
              "data_desligamento) VALUES ('9','JOAO','999','ANALISTA','2026-01-01')")
    c.execute("INSERT INTO acessos_sistemas (sistema,usuario,perfil,nome_usuario,"
              "situacao,matricula_vinculada,metodo_vinculacao) "
              "VALUES ('SYSTUR','u1','P1','ANA','ATIVO','1','CPF')")
    c.execute("INSERT INTO validacao_acessos (matricula,nome,sistema,"
              "perfil_esperado,perfil_atual,status,situacao_acao,"
              "dt_processamento) VALUES ('1','ANA','SYSTUR','P1','P1','OK',"
              "'RESOLVIDO','2026-06-01')")
    c.execute("INSERT INTO divergencias (id,tipo,sistema,usuario,nome_usuario,"
              "matricula,perfil_encontrado,descricao,resolvida) VALUES "
              "('d1','ACESSO_DESLIGADO','SYSTUR','u9','JOAO','9','P1','desc',0)")
    c.execute("INSERT INTO quarentena VALUES (?,?,?,?,?,?,?)", DADOS_VIVOS["quarentena"])
    c.execute("INSERT INTO resolucoes VALUES (?,?,?,?,?)", DADOS_VIVOS["resolucoes"])
    c.commit()
    c.close()


class TestSchemaAditivo(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_aditivo_")
        self.caminho = os.path.join(self._tmp, "antigo.db")
        _banco_antigo(self.caminho)
        self._orig = (vm.DB_PATH, vm.SISTEMA, vm.PASTA_INTERACOES)

    def tearDown(self):
        vm.DB_PATH, vm.SISTEMA, vm.PASTA_INTERACOES = self._orig

    def _tabelas(self):
        c = sqlite3.connect(self.caminho)
        try:
            return {r[0] for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            c.close()

    def _linhas(self, tabela):
        c = sqlite3.connect(self.caminho)
        try:
            return c.execute(f"SELECT * FROM {tabela}").fetchall()
        finally:
            c.close()

    # ---------------------------------------------------------------
    def test_inicializar_cria_as_tabelas_novas(self):
        self.assertNotIn("transferidos", self._tabelas())
        ConexaoBancoDados(self.caminho).inicializar()
        tabs = self._tabelas()
        for nova in ("transferidos", "revalidacao_transferido"):
            self.assertIn(nova, tabs, f"{nova} deveria ter sido criada")

    def test_nao_perde_quarentena_nem_resolucao(self):
        ConexaoBancoDados(self.caminho).inicializar()
        self.assertEqual(len(self._linhas("quarentena")), 1)
        self.assertEqual(len(self._linhas("resolucoes")), 1)
        q = self._linhas("quarentena")[0]
        self.assertEqual(q[0], "Q-1")
        self.assertEqual(q[1], "ANA")
        r = self._linhas("resolucoes")[0]
        self.assertEqual((r[0], r[1], r[2]), ("R-1", "IAM-123", "Exceção"))

    def test_nao_perde_dados_operacionais(self):
        antes = {t: len(self._linhas(t)) for t in
                 ("rh_ativos", "rh_desligados", "acessos_sistemas", "divergencias")}
        ConexaoBancoDados(self.caminho).inicializar()
        for t, n in antes.items():
            self.assertEqual(len(self._linhas(t)), n, f"{t} perdeu linhas")

    def test_inicializar_e_idempotente(self):
        ConexaoBancoDados(self.caminho).inicializar()
        tabs1 = self._tabelas()
        n1 = {t: len(self._linhas(t)) for t in ("quarentena", "resolucoes")}
        ConexaoBancoDados(self.caminho).inicializar()
        ConexaoBancoDados(self.caminho).inicializar()
        self.assertEqual(self._tabelas(), tabs1)
        self.assertEqual({t: len(self._linhas(t)) for t in ("quarentena", "resolucoes")}, n1)

    def test_painel_novo_le_banco_antigo_sem_as_tabelas(self):
        # sem inicializar: o painel tem de degradar, nao levantar
        vm.DB_PATH = self.caminho
        vm.SISTEMA = ""
        vm.PASTA_INTERACOES = ""
        r = vm.listar_transferidos()
        self.assertEqual(r["lista"], [])
        self.assertEqual(r["kpis"]["sobrou"], 0)
        d = vm.listar_desligados()
        self.assertEqual(d["kpis"]["total"], 1)

    def test_visao_geral_em_banco_antigo(self):
        vm.DB_PATH = self.caminho
        vm.SISTEMA = ""
        vm.PASTA_INTERACOES = ""
        c = vm.conn_ro()
        try:
            vg = vm._calcular_visao_geral(c)
        finally:
            c.close()
        # campos novos existem com zero, em vez de sumir/quebrar
        self.assertEqual(vg["transf_sobrou"], 0)
        self.assertEqual(vg["transf_movimentos"], 0)
        self.assertEqual(vg["transf_pessoas"], 0)

    def test_nenhuma_tabela_e_removida(self):
        antes = self._tabelas()
        ConexaoBancoDados(self.caminho).inicializar()
        depois = self._tabelas()
        self.assertTrue(antes.issubset(depois),
                        f"tabelas sumiram: {antes - depois}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
