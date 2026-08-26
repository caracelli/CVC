# -*- coding: utf-8 -*-
"""Data-layer do Visualizador (client-facing): garantir_estrutura monta
bi_divergencias a partir de validacao_acessos + divergencias; _montar_base
calcula KPIs/sis_dist/acao_dist/users com o filtro de sistema do config.

Sem servidor: importa o modulo e faz monkeypatch dos globais (DB_PATH/SISTEMA),
como scripts/rodar_visualizador_selftest.py.
"""
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
SYSTUR = "SYSTUR"


def _seed(db):
    c = sqlite3.connect(db)
    c.executescript("""
        INSERT INTO rh_ativos (matricula,nome,cpf,cargo_descricao,
            centro_custo_codigo,centro_custo_nome,departamento,situacao,tipo_vinculo)
        VALUES ('M1','NOME M1','111','ANALISTA','100','FIN','D','ATIVO','FUNCIONARIO'),
               ('M2','NOME M2','222','GERENTE','200','COM','D','ATIVO','TERCEIRO');

        INSERT INTO validacao_acessos (matricula,nome,sistema,perfil_esperado,
            perfil_atual,status,situacao_acao,origem_matriz,dt_processamento)
        VALUES ('M1','NOME M1','IC_INTEGRADOR_CONTABIL','IC CONSULTA','','SEM_ACESSO',
                'PENDENTE','MATRIZ','2026-05-01 10:00:00'),
               ('M2','NOME M2','IC_INTEGRADOR_CONTABIL','IC CONSULTA','IC_APROVADOR',
                'DIVERGENTE','PENDENTE','CCO','2026-05-02 09:00:00'),
               ('M1','NOME M1','SYSTUR','S1','','EM_ANALISE','PENDENTE','MATRIZ',
                '2026-05-03 08:00:00');

        INSERT INTO divergencias (id,tipo,sistema,usuario,nome_usuario,matricula,
            perfil_encontrado,descricao,resolvida)
        VALUES ('d1','ACESSO_SEM_VINCULO_RH','IC_INTEGRADOR_CONTABIL','tercX',
                'TERCEIRO X','','PX','sem vinculo',0);
    """)
    c.commit()
    c.close()


class TestVisualizadorDataLayer(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="cvc_vis_")
        cls.db = os.path.join(cls._tmp, "iam.db")
        ConexaoBancoDados(cls.db).inicializar()
        _seed(cls.db)
        # monkeypatch dos globais do modulo
        cls._orig = (vm.DB_PATH, vm.SISTEMA, vm._BASE)
        vm.DB_PATH = cls.db
        vm.SISTEMA = ""
        vm._BASE = None
        vm.garantir_estrutura(force=True)

    @classmethod
    def tearDownClass(cls):
        vm.DB_PATH, vm.SISTEMA, vm._BASE = cls._orig

    def _base(self, sistema):
        vm.SISTEMA = sistema
        vm._BASE = None
        return vm._montar_base()

    # ---- bi_divergencias ----
    def test_bi_divergencias_une_validacao_e_sem_vinculo(self):
        c = sqlite3.connect(self.db)
        try:
            n = c.execute("SELECT COUNT(*) FROM bi_divergencias").fetchone()[0]
        finally:
            c.close()
        self.assertEqual(n, 4)   # 3 validacao + 1 ACESSO_SEM_VINCULO_RH

    # ---- KPIs (todos os sistemas) ----
    def test_kpis_todos_os_sistemas(self):
        b = self._base("")
        # total = PESSOAS distintas a tratar, nao a soma dos cards: M1 esta em DOIS
        # tipos (SEM_ACESSO no IC + EM_ANALISE no SYSTUR) e conta 1x -> total 3
        # (M1, M2, tercX), embora a soma dos cards seja 4.
        self.assertEqual(b["kpis"], {
            "sem_acesso": 1, "divergente": 1, "em_analise": 1,
            "nao_mapeado": 1, "ok": 0, "total": 3})

    def test_sis_dist(self):
        b = self._base("")
        self.assertEqual(b["sis_dist"], {IC: 3, SYSTUR: 1})

    def test_acao_dist_rotulos(self):
        b = self._base("")
        self.assertEqual(b["acao_dist"], {
            "Incluir Acesso": 1, "Alterar Perfil": 1,
            "Em Análise": 1, "Usuário Não Encontrado": 1})

    # ---- users / JOIN rh_ativos ----
    def test_users_estrutura_e_vinculo(self):
        b = self._base("")
        users = {u["u"]: u for u in b["users"]}
        self.assertEqual(set(users), {"M1", "M2", "tercX"})
        # M1 tem 2 divergencias (IC SEM_ACESSO + SYSTUR EM_ANALISE)
        self.assertEqual(len(users["M1"]["divs"]), 2)
        # M2 e' TERCEIRO no rh_ativos -> vinculo "Terceiro"
        self.assertEqual(users["M2"]["divs"][0]["vinc"], "Terceiro")
        # tercX nao esta no rh_ativos. Ate 25/08/2026 o default era
        # "Funcionário" — o painel afirmava um vinculo que ninguem apurou, e a
        # area apontou o efeito: login de franquia aparecendo como CLT. Agora a
        # coluna diz o que se sabe: nada.
        self.assertEqual(users["tercX"]["divs"][0]["vinc"], "Não identificado")

    # ---- Card 14: consolidacao multi-sistema + vinculo top-level (coluna das grids) ----
    def test_consolidacao_multisistema_e_vinculo_top(self):
        b = self._base("")
        users = {u["u"]: u for u in b["users"]}
        # CONSOLIDACAO: M1 aparece UMA vez com acessos em 2 sistemas (IC + SYSTUR)
        self.assertEqual({d["sis"] for d in users["M1"]["divs"]}, {IC, SYSTUR})
        # total global = PESSOAS distintas (multi-sistema conta 1x), nao a soma
        self.assertEqual(len(b["users"]), 3)
        # vinculo top-level por pessoa (fonte da coluna Vínculo nas grids)
        self.assertEqual(users["M1"]["vinc"], "Funcionário")
        self.assertEqual(users["M2"]["vinc"], "Terceiro")
        # idem no vinculo top-level (a coluna Categoria das grids)
        self.assertEqual(users["tercX"]["vinc"], "Não identificado")

    def test_origem_label_por_div(self):
        b = self._base("")
        m1 = next(u for u in b["users"] if u["u"] == "M1")
        origens = {d["o"] for d in m1["divs"]}
        self.assertIn("Matriz IC_INTEGRADOR_CONTABIL", origens)  # origem MATRIZ
        m2 = next(u for u in b["users"] if u["u"] == "M2")
        self.assertEqual(m2["divs"][0]["o"], "Matriz CCO")        # origem CCO
        terc = next(u for u in b["users"] if u["u"] == "tercX")
        self.assertEqual(terc["divs"][0]["o"], "—")               # sem origem

    # ---- filtro por sistema ----
    def test_filtro_sistema_ic(self):
        b = self._base(IC)
        # EM_ANALISE era do SYSTUR -> some; restam SEM_ACESSO/DIVERGENTE/nao_mapeado do IC.
        # total = pendencias: DIVERGENTE(1) + nao_mapeado(1) = 2. SEM_ACESSO deixou
        # de ser pendencia (retorno Bruna: informativo) -> fora do total.
        self.assertEqual(b["kpis"], {
            "sem_acesso": 1, "divergente": 1, "em_analise": 0,
            "nao_mapeado": 1, "ok": 0, "total": 2})
        # sis_dist NAO e' filtrado (sempre mostra a distribuicao completa)
        self.assertEqual(b["sis_dist"], {IC: 3, SYSTUR: 1})


class TestKpisContamUsuariosNaoAcessos(unittest.TestCase):
    """REGRA: o card conta USUARIOS a tratar (qualitativo), nao acessos
    (quantitativo). Um usuario com N opcoes Em Analise, ou varios acessos sem
    vinculo, conta como 1 — nao infla o KPI."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="cvc_vis_user_")
        cls.db = os.path.join(cls._tmp, "iam.db")
        ConexaoBancoDados(cls.db).inicializar()
        c = sqlite3.connect(cls.db)
        c.executescript("""
            -- M1: 3 opcoes EM_ANALISE (1 usuario, nao 3)
            INSERT INTO validacao_acessos (matricula,nome,sistema,perfil_esperado,
                perfil_atual,status,situacao_acao,origem_matriz,dt_processamento)
            VALUES ('M1','NOME M1','SYSTUR','P_A','','EM_ANALISE','PENDENTE','MATRIZ','2026-05-01 10:00:00'),
                   ('M1','NOME M1','SYSTUR','P_B','','EM_ANALISE','PENDENTE','MATRIZ','2026-05-01 10:00:00'),
                   ('M1','NOME M1','SYSTUR','P_C','','EM_ANALISE','PENDENTE','MATRIZ','2026-05-01 10:00:00');
            -- loginZ: 4 acessos sem vinculo RH (1 usuario, nao 4)
            INSERT INTO divergencias (id,tipo,sistema,usuario,nome_usuario,matricula,
                perfil_encontrado,descricao,resolvida)
            VALUES ('a','ACESSO_SEM_VINCULO_RH','SYSTUR','loginZ','Z','','P1','x',0),
                   ('b','ACESSO_SEM_VINCULO_RH','SYSTUR','loginZ','Z','','P2','x',0),
                   ('c','ACESSO_SEM_VINCULO_RH','SICA_RA','loginZ','Z','','P3','x',0),
                   ('d','ACESSO_SEM_VINCULO_RH','SICA_RA','loginZ','Z','','P4','x',0);
        """)
        c.commit(); c.close()
        cls._orig = (vm.DB_PATH, vm.SISTEMA, vm._BASE)
        vm.DB_PATH = cls.db; vm.SISTEMA = ""; vm._BASE = None
        vm.garantir_estrutura(force=True)

    @classmethod
    def tearDownClass(cls):
        vm.DB_PATH, vm.SISTEMA, vm._BASE = cls._orig

    def test_em_analise_e_nao_mapeado_contam_pessoas(self):
        vm.SISTEMA = ""; vm._BASE = None
        k = vm._montar_base()["kpis"]
        self.assertEqual(k["em_analise"], 1)    # M1: 3 opcoes -> 1 pessoa
        self.assertEqual(k["nao_mapeado"], 1)   # loginZ: 4 acessos -> 1 pessoa
        self.assertEqual(k["total"], 2)         # 1 + 1 (sem outros tipos)


if __name__ == "__main__":
    unittest.main(verbosity=2)
