# -*- coding: utf-8 -*-
"""Card 22 — persistencia do "de -> para" do movimento (tabela `transferidos`).

Antes, o detector calculava cargo/gestor ANTERIORES e jogava fora: so o ROTULO
dos campos sobrevivia, dentro da descricao da divergencia. Quem revisa o acesso
via o valor ATUAL e o nome do campo, nunca de onde a pessoa veio.

Cobre: gravacao pelo AnalisarDivergencias, o caso de quem mudou mas NAO tem
acesso (nao gera divergencia e sumiria), o snapshot (nao acumula) e a leitura
do painel (_transferidos_depara), inclusive em banco SEM a tabela.
"""
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from aplicacao.casos_de_uso.analisar_divergencias import AnalisarDivergencias
from dominio.objetos_valor.sistema import Sistema
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import RhAtivo, AcessoSistema, Historico

SIS = Sistema.SYSTUR.value


def _ativo(mat, cargo="ANALISTA", cc="100", dep="TI", gestor="CHEFE A"):
    return RhAtivo(matricula=mat, nome="F" + mat, cpf="", cargo_codigo="CG",
                   cargo_descricao=cargo, centro_custo_codigo=cc, departamento=dep,
                   situacao="ATIVO", tipo_vinculo="FUNCIONARIO", gestor=gestor)


def _hist(mat, campos, ant, snap="2026-07-01"):
    return Historico(
        data_snapshot=date.fromisoformat(snap), entidade="RH_ATIVO",
        chave_entidade=mat, matricula=mat, tipo="ATIVO",
        tipo_mudanca="ALTERADO", campos_alterados=campos,
        dados_anterior=json.dumps(ant, ensure_ascii=False), dados_novo="{}")


def _acesso(mat):
    return AcessoSistema(sistema=SIS, usuario="u" + mat, perfil="P1",
                         nome_usuario="F" + mat, situacao="ATIVO",
                         matricula_vinculada=mat)


_BASE_ANT = {"cargo_codigo": "CG", "cargo_descricao": "ANALISTA",
             "centro_custo_codigo": "100", "departamento": "TI", "gestor": "CHEFE A"}


class _Db(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_depara_")
        self.caminho = os.path.join(self._tmp, "t.db")
        self.con = ConexaoBancoDados(self.caminho)
        self.con.inicializar()

    def _seed(self, *orm):
        s = self.con.sessao()
        s.add_all(orm)
        s.commit()
        s.close()

    def _linhas(self):
        c = sqlite3.connect(self.caminho)
        c.row_factory = sqlite3.Row
        try:
            return {r["matricula"]: dict(r)
                    for r in c.execute("SELECT * FROM transferidos")}
        finally:
            c.close()


class TestPersisteDePara(_Db):

    def test_grava_gestor_de_para(self):
        self._seed(_ativo("10", gestor="CHEFE NOVO"),
                   _hist("10", "gestor", dict(_BASE_ANT)),
                   _acesso("10"))
        AnalisarDivergencias(self.con).executar()
        r = self._linhas()["10"]
        self.assertEqual(r["gestor_anterior"], "CHEFE A")
        self.assertEqual(r["gestor_atual"], "CHEFE NOVO")
        self.assertEqual(r["campos_mudados"], "gestor")
        self.assertEqual(r["nome"], "F10")

    def test_grava_cargo_cc_e_departamento(self):
        self._seed(_ativo("11", cargo="COORDENADOR", cc="200", dep="COMERCIAL"),
                   _hist("11", "cargo_descricao,centro_custo_codigo,departamento",
                         dict(_BASE_ANT)),
                   _acesso("11"))
        AnalisarDivergencias(self.con).executar()
        r = self._linhas()["11"]
        self.assertEqual((r["cargo_anterior"], r["cargo_atual"]),
                         ("ANALISTA", "COORDENADOR"))
        self.assertEqual((r["centro_custo_anterior"], r["centro_custo_atual"]),
                         ("100", "200"))
        self.assertEqual((r["departamento_anterior"], r["departamento_atual"]),
                         ("TI", "COMERCIAL"))

    def test_quem_mudou_sem_acesso_tambem_e_gravado(self):
        """Era o buraco: sem acesso nao ha divergencia, entao a pessoa sumia do
        painel inteiro. A tabela guarda o MOVIMENTO, nao o acesso."""
        self._seed(_ativo("12", gestor="CHEFE NOVO"),
                   _hist("12", "gestor", dict(_BASE_ANT)))   # sem _acesso()
        AnalisarDivergencias(self.con).executar()
        self.assertIn("12", self._linhas())
        c = sqlite3.connect(self.caminho)
        n = c.execute("SELECT COUNT(*) FROM divergencias "
                      "WHERE tipo='ACESSO_TRANSFERIDO' AND matricula='12'").fetchone()[0]
        c.close()
        self.assertEqual(n, 0, "sem acesso nao pode gerar divergencia")

    def test_e_snapshot_nao_acumula(self):
        self._seed(_ativo("13", gestor="CHEFE NOVO"),
                   _hist("13", "gestor", dict(_BASE_ANT)),
                   _acesso("13"))
        AnalisarDivergencias(self.con).executar()
        AnalisarDivergencias(self.con).executar()
        c = sqlite3.connect(self.caminho)
        n = c.execute("SELECT COUNT(*) FROM transferidos").fetchone()[0]
        c.close()
        self.assertEqual(n, 1)

    def test_quem_nao_mudou_nada_relevante_fica_fora(self):
        self._seed(_ativo("14"),
                   _hist("14", "email", {"email": "a@x"}),
                   _acesso("14"))
        AnalisarDivergencias(self.con).executar()
        self.assertNotIn("14", self._linhas())


class TestLeituraPainel(_Db):
    """_transferidos_depara so devolve os campos que REALMENTE mudaram."""

    def _ler(self, mats):
        os.environ.setdefault("CVC_TESTE", "1")
        from visualizador.main import _transferidos_depara
        c = sqlite3.connect(self.caminho)
        c.row_factory = sqlite3.Row
        try:
            return _transferidos_depara(c, mats)
        finally:
            c.close()

    def test_par_so_do_campo_que_mudou(self):
        self._seed(_ativo("20", gestor="CHEFE NOVO"),
                   _hist("20", "gestor", dict(_BASE_ANT)),
                   _acesso("20"))
        AnalisarDivergencias(self.con).executar()
        d = self._ler(["20"])["20"]
        self.assertEqual([p["campo"] for p in d["pares"]], ["gestor"])
        self.assertEqual(d["pares"][0]["de"], "CHEFE A")
        self.assertEqual(d["pares"][0]["para"], "CHEFE NOVO")

    def test_dois_campos_viram_dois_pares(self):
        self._seed(_ativo("21", cc="200", dep="COMERCIAL"),
                   _hist("21", "centro_custo_codigo,departamento", dict(_BASE_ANT)),
                   _acesso("21"))
        AnalisarDivergencias(self.con).executar()
        pares = self._ler(["21"])["21"]["pares"]
        self.assertEqual({p["campo"] for p in pares},
                         {"departamento", "centro de custo"})

    def test_banco_sem_a_tabela_nao_quebra(self):
        """Painel novo sobre banco de Processador antigo: sem `transferidos`
        a aba tem de seguir funcionando, só sem o par."""
        outro = os.path.join(self._tmp, "velho.db")
        c = sqlite3.connect(outro)
        c.execute("CREATE TABLE divergencias (id TEXT)")
        c.commit()
        c.row_factory = sqlite3.Row
        from visualizador.main import _transferidos_depara
        try:
            self.assertEqual(_transferidos_depara(c, ["1"]), {})
        finally:
            c.close()

    def test_lista_vazia_nao_consulta(self):
        self.assertEqual(self._ler([]), {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
