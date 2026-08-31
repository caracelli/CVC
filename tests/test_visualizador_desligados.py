# -*- coding: utf-8 -*-
"""Aba Desligados do Visualizador (listar_desligados).

Regra pedida pela area: cada pessoa desligada cai em uma de duas situacoes —
"Tratar" (ainda tem acesso ativo em algum sistema) ou "OK" (nenhum acesso).
A fonte do acesso e' a SAIDA do motor (divergencias ACESSO_DESLIGADO), a mesma
da Visao Geral — a aba NAO reimplementa a regra de desligados.
"""
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import visualizador.main as vm
from aplicacao.casos_de_uso.dobrar_interacoes import DobrarInteracoes


def _criar_db(db, desligados, divergencias):
    c = sqlite3.connect(db)
    c.executescript(
        "CREATE TABLE rh_desligados (matricula TEXT, nome TEXT, cpf TEXT,"
        " cargo_descricao TEXT, departamento TEXT, centro_custo_codigo TEXT,"
        " centro_custo_nome TEXT, data_desligamento TEXT, email TEXT, empresa TEXT);"
        "CREATE TABLE divergencias (tipo TEXT, sistema TEXT, usuario TEXT,"
        " nome_usuario TEXT,"
        " matricula TEXT, perfil_encontrado TEXT, data_identificacao TEXT,"
        " resolvida INTEGER);"
    )
    c.executemany("INSERT INTO rh_desligados VALUES (?,?,?,?,?,?,?,?,?,?)", desligados)
    c.executemany("INSERT INTO divergencias VALUES (?,?,?,?,?,?,?,?)", divergencias)
    c.commit()
    c.close()


def _deslig(mat, nome, dt="2026-06-01"):
    return (mat, nome, "11122233344", "ANALISTA", "TI", "100", "MATRIZ", dt,
            "x@cvc.com.br", "CVC")


def _div_deslig(mat, sistema, login="lg", perfil="P1", resolvida=0, nome="N"):
    return ("ACESSO_DESLIGADO", sistema, login, nome, mat, perfil,
            "2026-06-10", resolvida)


def _div_servico(mat, sistema, login="SIST0230", perfil="P1",
                 nome="USUARIO SISTEMICO MONITORAMENTO ROTEIROS"):
    """Linha que o motor reclassificou como conta de servico (robo)."""
    return ("ACESSO_CONTA_SERVICO", sistema, login, nome, mat, perfil,
            "2026-06-10", 0)


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_deslig_")
        self._orig = (vm.DB_PATH, vm.SISTEMA, vm.PASTA_INTERACOES)
        vm.PASTA_INTERACOES = ""   # isola: sem interacoes vivas da rede

    def tearDown(self):
        vm.DB_PATH, vm.SISTEMA, vm.PASTA_INTERACOES = self._orig

    def _rodar(self, desligados, divergencias, sistema=""):
        db = os.path.join(self._tmp, f"d{len(os.listdir(self._tmp))}.db")
        _criar_db(db, desligados, divergencias)
        vm.DB_PATH = db
        vm.SISTEMA = sistema
        return vm.listar_desligados()


class TestSituacaoDesligado(_Base):

    def test_com_acesso_vira_tratar(self):
        r = self._rodar([_deslig("100", "ANA")], [_div_deslig("100", "SYSTUR")])
        (d,) = r["lista"]
        self.assertEqual(d["sit"], "Tratar")
        self.assertEqual(d["m"], "100")
        self.assertEqual([a["sis"] for a in d["acessos"]], ["SYSTUR"])

    def test_sem_acesso_vira_ok(self):
        r = self._rodar([_deslig("100", "ANA")], [])
        (d,) = r["lista"]
        self.assertEqual(d["sit"], "OK")
        self.assertEqual(d["acessos"], [])

    def test_multiplos_sistemas_na_mesma_pessoa(self):
        # o SIG e' matricial: a mesma pessoa aparece varias vezes. A aba conta
        # PESSOAS (1 linha) e lista os acessos dentro dela.
        r = self._rodar(
            [_deslig("100", "ANA")],
            [_div_deslig("100", "SYSTUR"), _div_deslig("100", "SIG"),
             _div_deslig("100", "SIG", perfil="P2")])
        self.assertEqual(len(r["lista"]), 1)
        self.assertEqual(len(r["lista"][0]["acessos"]), 3)
        self.assertEqual(r["kpis"]["tratar"], 1)

    def test_kpis_separam_tratar_e_ok(self):
        r = self._rodar(
            [_deslig("100", "ANA"), _deslig("200", "BIA"), _deslig("300", "CID")],
            [_div_deslig("100", "SYSTUR")])
        self.assertEqual(r["kpis"],
                         {"tratar": 1, "tratados": 0, "ok": 2, "total": 3,
                          "servico": 0})


class TestAcessoSemRh(_Base):
    """Acesso de desligado cuja matricula sumiu do rh_desligados: e' o caso de
    MAIOR risco (ninguem responde por ele) — nao pode ser engolido pelo JOIN."""

    def test_acesso_orfao_aparece_como_tratar(self):
        r = self._rodar([_deslig("100", "ANA")],
                        [_div_deslig("100", "SYSTUR"),
                         _div_deslig("999", "SIGOT", login="fantasma")])
        self.assertEqual(r["kpis"]["total"], 2)
        orfao = next(d for d in r["lista"] if d["m"] == "999")
        self.assertEqual(orfao["sit"], "Tratar")
        self.assertTrue(orfao["sem_rh"])
        self.assertEqual(orfao["n"], "fantasma")   # sem nome de RH, mostra o login


class TestEscopoESchema(_Base):

    def test_respeita_sistema_do_escopo(self):
        # com escopo SYSTUR, o acesso no SIGOT nao conta -> a pessoa fica OK
        r = self._rodar([_deslig("100", "ANA")],
                        [_div_deslig("100", "SIGOT")], sistema="SYSTUR")
        (d,) = r["lista"]
        self.assertEqual(d["sit"], "OK")

    def test_outros_tipos_de_divergencia_nao_contam(self):
        r = self._rodar([_deslig("100", "ANA")],
                        [("DIVERGENTE", "SYSTUR", "lg", "N", "100", "P1",
                          "2026-06-10", 0)])
        self.assertEqual(r["lista"][0]["sit"], "OK")

    def test_banco_sem_as_tabelas_nao_derruba_a_aba(self):
        # banco de schema antigo: a aba degrada para vazia, nao levanta
        db = os.path.join(self._tmp, "vazio.db")
        sqlite3.connect(db).close()
        vm.DB_PATH = db
        vm.SISTEMA = ""
        r = vm.listar_desligados()
        self.assertEqual(r["lista"], [])
        self.assertEqual(r["kpis"]["total"], 0)


def _seed_tratamento(db, registro_id, ticket="IAM-1", motivo="Acesso Indevido"):
    """Insere um tratamento ja dobrado (tabela tratamentos_desligado)."""
    c = sqlite3.connect(db)
    c.executescript(
        "CREATE TABLE IF NOT EXISTS tratamentos_desligado (registro_id TEXT PRIMARY KEY,"
        " ticket TEXT, ticket_url TEXT, descricao TEXT, motivo TEXT, acessos TEXT,"
        " cargo TEXT, centro_custo TEXT, nome TEXT, tratado_por TEXT, tratado_em TEXT,"
        " dobrado_em TEXT)")
    c.execute("INSERT OR REPLACE INTO tratamentos_desligado (registro_id,ticket,motivo,"
              "tratado_por,tratado_em) VALUES (?,?,?,?,?)",
              (registro_id, ticket, motivo, "user", "2026-07-29 10:00:00"))
    c.commit()
    c.close()


class TestTratamentoReflexo(_Base):
    """Tratar um desligado (mesmo padrao da resolucao) tira do 'Tratar' pendente
    e marca 'tratado', com os dados do ticket."""

    def test_tratado_sai_do_tratar_e_ganha_dados(self):
        db = os.path.join(self._tmp, "t.db")
        _criar_db(db, [_deslig("100", "ANA")], [_div_deslig("100", "SYSTUR")])
        _seed_tratamento(db, "100", ticket="IAM-77", motivo="Transferência de Área")
        vm.DB_PATH = db
        vm.SISTEMA = ""
        r = vm.listar_desligados()
        (d,) = r["lista"]
        self.assertTrue(d["tratado"])
        self.assertEqual(d["tratamento"]["ticket"], "IAM-77")
        self.assertEqual(d["tratamento"]["motivo"], "Transferência de Área")
        # KPIs: sai do 'tratar' pendente, entra em 'tratados'; segue com acesso
        self.assertEqual(r["kpis"]["tratar"], 0)
        self.assertEqual(r["kpis"]["tratados"], 1)
        self.assertEqual(r["kpis"]["ok"], 0)

    def test_sem_tratamento_continua_a_tratar(self):
        r = self._rodar([_deslig("100", "ANA")], [_div_deslig("100", "SYSTUR")])
        (d,) = r["lista"]
        self.assertFalse(d.get("tratado", False))
        self.assertEqual(r["kpis"]["tratar"], 1)
        self.assertEqual(r["kpis"].get("tratados", 0), 0)


class TestFoldingTratamento(unittest.TestCase):
    """O Processador (DobrarInteracoes) persiste a interacao TRATAMENTO_DESLIGADO
    na tabela tratamentos_desligado — senao ela se perderia no reset da pasta."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_fold_")

    def test_folding_persiste_o_tratamento(self):
        banco = os.path.join(self._tmp, "b.db")
        sqlite3.connect(banco).close()
        pasta = os.path.join(self._tmp, "INTERACOES")
        os.makedirs(pasta)
        with open(os.path.join(pasta, "user.jsonl"), "w", encoding="utf-8") as f:
            f.write(json.dumps({
                "tipo_interacao": "TRATAMENTO_DESLIGADO", "registro_id": "100",
                "acao": "TRATAR", "ticket": "IAM-9", "motivo": "Acesso Indevido",
                "acessos": [{"sistema": "SYSTUR", "login": "asouza", "perfil": "P1"}],
                "nome": "ANA", "usuario": "user",
                "data_acao": "2026-07-29T10:00:00"}) + "\n")
        DobrarInteracoes(caminho_banco=banco, pasta_interacoes=pasta).executar()
        c = sqlite3.connect(banco)
        row = c.execute("SELECT ticket, motivo, nome, tratado_por FROM "
                        "tratamentos_desligado WHERE registro_id='100'").fetchone()
        c.close()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "IAM-9")
        self.assertEqual(row[1], "Acesso Indevido")
        # a pasta foi resetada (rename atomico) — a interacao so sobrevive no banco
        self.assertFalse(os.listdir(pasta))


class TestContaServicoNaAba(_Base):
    """A conta de servico sai da COBRANCA e continua na TELA.

    Retorno da area (28 e 31/08/2026): o robo cadastrado com o e-mail de quem o
    criou aparecia como acesso a revogar de uma pessoa desligada. O motor passou
    a reclassifica-lo (ACESSO_CONTA_SERVICO); a aba precisa refletir as duas
    metades da decisao — fora do "Tratar", dentro da conferencia.
    """

    def test_robo_nao_entra_no_tratar(self):
        r = self._rodar([_deslig("100", "KEITI")],
                        [_div_servico("100", "SYSTUR")])
        self.assertEqual(r["kpis"]["tratar"], 0)
        self.assertEqual(r["lista"][0]["sit"], "OK")

    def test_robo_aparece_na_categoria_propria(self):
        """Sumir seria esconder uma classificacao errada — o ponto da decisao."""
        r = self._rodar([_deslig("100", "KEITI")],
                        [_div_servico("100", "SYSTUR", login="SIST0230")])
        self.assertEqual(r["kpis"]["servico"], 1)
        self.assertEqual(len(r["servico"]), 1)
        a = r["servico"][0]
        self.assertEqual(a["login"], "SIST0230")
        self.assertEqual(a["m"], "100")
        # o NOME e' o que deixa a conferencia possivel a olho: "USUARIO
        # SISTEMICO MONITORAMENTO ROTEIROS" diz sozinho que nao e' gente.
        self.assertIn("SISTEMICO", a["n"])

    def test_pessoa_e_robo_convivem_sem_se_contaminar(self):
        r = self._rodar(
            [_deslig("100", "KEITI"), _deslig("200", "RAFAELA")],
            [_div_servico("100", "SYSTUR"),
             _div_deslig("200", "SYSTUR", login="corpc90000395")])
        self.assertEqual(r["kpis"]["tratar"], 1)      # so' a pessoa
        self.assertEqual(r["kpis"]["servico"], 1)     # so' o robo
        tratar = [d for d in r["lista"] if d["sit"] == "Tratar"]
        self.assertEqual([d["m"] for d in tratar], ["200"])

    def test_escopo_de_sistema_vale_para_a_categoria(self):
        """Como as demais grids, respeita o <sistema> do config."""
        r = self._rodar([_deslig("100", "KEITI")],
                        [_div_servico("100", "SIGOT")], sistema="SYSTUR")
        self.assertEqual(r["kpis"]["servico"], 0)
        self.assertEqual(r["servico"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
