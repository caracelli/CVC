# -*- coding: utf-8 -*-
"""Regressao PROFUNDA da frente de transferidos (Cards 22, 23 e 24).

Fase de finalizacao: aqui se cacam os erros que passam despercebidos numa
leitura de codigo — caixa/acento/espaco nas chaves, perfil escrito diferente
entre extrato e matriz, contagem que nao fecha entre banco e painel, efeito de
reprocessar duas vezes, e a convivencia com desligados/quarentena/tratamento.
"""
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import visualizador.main as vm
from aplicacao.casos_de_uso.analisar_divergencias import AnalisarDivergencias
from aplicacao.casos_de_uso.revalidar_transferidos import RevalidarTransferidos
from dominio.objetos_valor.sistema import Sistema
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import (
    AcessoSistema, Historico, MatrizCcoModel, PerfilEsperadoModel, RhAtivo,
    TransferidoModel)

SIG = Sistema.SIG.value
SYS = Sistema.SYSTUR.value
IC = Sistema.IC_INTEGRADOR_CONTABIL.value


def _ativo(mat, cc="100", gestor="CHEFE A", cargo="ANALISTA", vinc="FUNCIONARIO",
           empresa="", depto="TI"):
    return RhAtivo(matricula=mat, nome="F" + mat, cpf="", cargo_codigo="CG",
                   cargo_descricao=cargo, centro_custo_codigo=cc, departamento=depto,
                   situacao="ATIVO", tipo_vinculo=vinc, gestor=gestor, empresa=empresa)


def _acesso(mat, sistema, perfil):
    return AcessoSistema(sistema=sistema, usuario="u" + mat, perfil=perfil,
                         nome_usuario="F" + mat, situacao="ATIVO",
                         matricula_vinculada=mat)


def _mov(mat, cc_ant="100", cargo_ant="ANALISTA", gestor_ant="CHEFE A",
         cc_atu="100", cargo_atu="ANALISTA", gestor_atu="CHEFE B", campos="gestor"):
    return TransferidoModel(
        matricula=mat, nome="F" + mat, campos_mudados=campos,
        data_transferencia="2026-07-01",
        cargo_codigo_anterior="CG", cargo_anterior=cargo_ant,
        departamento_anterior="TI", centro_custo_anterior=cc_ant,
        gestor_anterior=gestor_ant,
        cargo_codigo_atual="CG", cargo_atual=cargo_atu,
        departamento_atual="TI", centro_custo_atual=cc_atu, gestor_atual=gestor_atu)


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_regprof_")
        self.caminho = os.path.join(self._tmp, "t.db")
        self.con = ConexaoBancoDados(self.caminho)
        self.con.inicializar()
        self._orig = (vm.DB_PATH, vm.SISTEMA, vm.PASTA_INTERACOES)
        vm.DB_PATH = self.caminho
        vm.SISTEMA = ""
        vm.PASTA_INTERACOES = ""

    def tearDown(self):
        vm.DB_PATH, vm.SISTEMA, vm.PASTA_INTERACOES = self._orig

    def _seed(self, *orm):
        s = self.con.sessao()
        s.add_all(orm)
        s.commit()
        s.close()

    def _sit(self, mat):
        c = sqlite3.connect(self.caminho)
        try:
            return {(p, s) for p, s in c.execute(
                "SELECT perfil, situacao FROM revalidacao_transferido "
                "WHERE matricula=?", (mat,))}
        finally:
            c.close()

    _seq = 0

    def _grupo_sig(self, gestor, perfis, quantos=2, cc="100", cargo="ANALISTA"):
        """Cria `quantos` colegas no grupo, todos com os mesmos perfis.
        Matricula por CONTADOR: derivar do nome do gestor fazia dois grupos
        colidirem quando os nomes terminavam com a mesma letra."""
        orm = []
        for _ in range(quantos):
            type(self)._seq += 1
            mat = f"G{type(self)._seq:03d}"
            orm.append(_ativo(mat, cc=cc, gestor=gestor, cargo=cargo))
            orm += [_acesso(mat, SIG, p) for p in perfis]
        self._seed(*orm)


# ---------------------------------------------------------------------------
class TestNormalizacaoDasChaves(_Base):
    """Caixa, acento e espaco NAO podem separar quem e' do mesmo grupo."""

    def test_gestor_com_caixa_e_acento_diferentes_e_o_mesmo_grupo(self):
        # colegas cadastrados com "JOSÉ DA SILVA"; o de/para grava "jose da silva"
        self._grupo_sig("JOSÉ DA SILVA", ["P_ANTIGO", "P_COMUM"])
        self._grupo_sig("MARIA SOUZA", ["P_NOVO", "P_COMUM"])
        self._seed(_ativo("10", gestor="MARIA SOUZA"),
                   _acesso("10", SIG, "P_ANTIGO"), _acesso("10", SIG, "P_COMUM"),
                   _mov("10", gestor_ant="  jose da silva  ", gestor_atu="maria souza"))
        RevalidarTransferidos(self.con).executar()
        r = self._sit("10")
        self.assertIn(("P_ANTIGO", "SOBROU"), r,
                      "gestor anterior com acento/caixa/espaco tem de casar o grupo")
        self.assertIn(("P_COMUM", "MANTEM"), r)

    def test_cargo_com_espaco_duplo_casa_a_matriz(self):
        self._seed(
            PerfilEsperadoModel(cargo_codigo="100", cargo_descricao="ANALISTA PL",
                                sistema=SYS, perfil="P_PL", acesso_manual=False),
            _ativo("11", cargo="ANALISTA  PL"),          # espaco duplo no RH
            _acesso("11", SYS, "P_PL"),
            _mov("11", cargo_ant="Analista Pl", cargo_atu="ANALISTA  PL",
                 gestor_ant="CHEFE A", gestor_atu="CHEFE A"))
        RevalidarTransferidos(self.con).executar()
        self.assertIn(("P_PL", "MANTEM"), self._sit("11"))

    def test_centro_de_custo_com_espaco_nas_pontas(self):
        self._seed(
            PerfilEsperadoModel(cargo_codigo="100", cargo_descricao="ANALISTA",
                                sistema=SYS, perfil="P_A", acesso_manual=False),
            _ativo("12"), _acesso("12", SYS, "P_A"),
            _mov("12", cc_ant=" 100 ", cc_atu="100 "))
        RevalidarTransferidos(self.con).executar()
        self.assertIn(("P_A", "MANTEM"), self._sit("12"))


class TestPerfilAproximado(_Base):
    """IC escreve 'IC_CONSULTA' no extrato e 'IC CONSULTA' na matriz."""

    def test_ic_casa_por_aproximacao(self):
        self._seed(
            PerfilEsperadoModel(cargo_codigo="100", cargo_descricao="ANALISTA",
                                sistema=IC, perfil="IC CONSULTA", acesso_manual=False),
            _ativo("13"), _acesso("13", IC, "IC_CONSULTA"),
            _mov("13"))
        RevalidarTransferidos(self.con).executar()
        self.assertIn(("IC_CONSULTA", "MANTEM"), self._sit("13"),
                      "underscore x espaco nao pode virar EXCESSO no IC")

    def test_ic_nao_duplica_em_falta(self):
        self._seed(
            PerfilEsperadoModel(cargo_codigo="100", cargo_descricao="ANALISTA",
                                sistema=IC, perfil="IC CONSULTA", acesso_manual=False),
            _ativo("14"), _acesso("14", IC, "IC_CONSULTA"), _mov("14"))
        RevalidarTransferidos(self.con).executar()
        self.assertEqual([s for _, s in self._sit("14")], ["MANTEM"],
                         "o mesmo perfil nao pode sair como MANTEM e FALTA")

    def test_systur_continua_exato(self):
        # SYSTUR NAO aproxima (perfil homologado) — underscore importa
        self._seed(
            PerfilEsperadoModel(cargo_codigo="100", cargo_descricao="ANALISTA",
                                sistema=SYS, perfil="VENDAS LAZER", acesso_manual=False),
            _ativo("15"), _acesso("15", SYS, "VENDAS_LAZER"), _mov("15"))
        RevalidarTransferidos(self.con).executar()
        self.assertIn(("VENDAS_LAZER", "EXCESSO"), self._sit("15"))


class TestLimiarDoEspelho(_Base):
    """O padrao e' perfil presente em >=70% dos colegas."""

    def test_dois_tercos_nao_e_padrao(self):
        # 3 colegas, 2 com P_X -> 66,7% < 70% -> nao e' padrao
        self._seed(_ativo("C1", gestor="CHEFE B"), _acesso("C1", SIG, "P_X"),
                   _acesso("C1", SIG, "P_TODOS"),
                   _ativo("C2", gestor="CHEFE B"), _acesso("C2", SIG, "P_X"),
                   _acesso("C2", SIG, "P_TODOS"),
                   _ativo("C3", gestor="CHEFE B"), _acesso("C3", SIG, "P_TODOS"))
        self._grupo_sig("CHEFE A", ["P_ANTIGO"])
        self._seed(_ativo("16", gestor="CHEFE B"), _acesso("16", SIG, "P_X"),
                   _mov("16"))
        RevalidarTransferidos(self.con).executar()
        self.assertIn(("P_X", "EXCESSO"), self._sit("16"))

    def test_setenta_por_cento_exato_e_padrao(self):
        # 10 colegas, 7 com P_X -> 70% -> e' padrao
        orm = []
        for i in range(10):
            m = f"D{i}"
            orm.append(_ativo(m, gestor="CHEFE B"))
            orm.append(_acesso(m, SIG, "P_TODOS"))
            if i < 7:
                orm.append(_acesso(m, SIG, "P_X"))
        self._seed(*orm)
        self._grupo_sig("CHEFE A", ["P_ANTIGO"])
        self._seed(_ativo("17", gestor="CHEFE B"), _acesso("17", SIG, "P_X"),
                   _mov("17"))
        RevalidarTransferidos(self.con).executar()
        self.assertIn(("P_X", "MANTEM"), self._sit("17"))


class TestPopulacoesEspeciais(_Base):

    def test_terceiro_nao_entra_no_espelho_do_sig(self):
        # terceiro tem espelho proprio; se entrasse aqui, contaminaria o padrao
        self._seed(_ativo("T1", gestor="CHEFE B", vinc="TERCEIRO"),
                   _acesso("T1", SIG, "P_TERC"),
                   _ativo("T2", gestor="CHEFE B", vinc="TERCEIRO"),
                   _acesso("T2", SIG, "P_TERC"),
                   _ativo("18", gestor="CHEFE B"), _acesso("18", SIG, "P_TERC"),
                   _mov("18"))
        RevalidarTransferidos(self.con).executar()
        # sem CLT no grupo -> sem padrao -> nada a dizer
        self.assertEqual(self._sit("18"), set())

    def test_gestor_vazio_nao_agrupa_todo_mundo(self):
        self._seed(_ativo("E1", gestor=""), _acesso("E1", SIG, "P_A"),
                   _ativo("E2", gestor=""), _acesso("E2", SIG, "P_A"),
                   _ativo("19", gestor=""), _acesso("19", SIG, "P_A"),
                   _mov("19", gestor_ant="", gestor_atu=""))
        RevalidarTransferidos(self.con).executar()
        # nao explode; e como antes==depois, o perfil se mantem
        self.assertIn(("P_A", "MANTEM"), self._sit("19"))


class TestIdempotenciaEConsistencia(_Base):

    def _cenario(self):
        self._grupo_sig("CHEFE A", ["P_ANTIGO", "P_COMUM"])
        self._grupo_sig("CHEFE B", ["P_NOVO", "P_COMUM"])
        self._seed(_ativo("20", gestor="CHEFE B"),
                   _acesso("20", SIG, "P_ANTIGO"), _acesso("20", SIG, "P_COMUM"),
                   _mov("20"))

    def test_reprocessar_nao_muda_o_resultado(self):
        self._cenario()
        RevalidarTransferidos(self.con).executar()
        antes = self._sit("20")
        RevalidarTransferidos(self.con).executar()
        RevalidarTransferidos(self.con).executar()
        self.assertEqual(antes, self._sit("20"))

    def test_cada_acesso_tem_exatamente_um_veredito(self):
        self._cenario()
        RevalidarTransferidos(self.con).executar()
        c = sqlite3.connect(self.caminho)
        dup = c.execute(
            "SELECT matricula, sistema, perfil, COUNT(*) n FROM revalidacao_transferido "
            "WHERE situacao <> 'FALTA' GROUP BY 1,2,3 HAVING n > 1").fetchall()
        c.close()
        self.assertEqual(dup, [], "acesso com mais de um veredito")

    def test_soma_bate_com_os_acessos_da_pessoa(self):
        self._cenario()
        RevalidarTransferidos(self.con).executar()
        c = sqlite3.connect(self.caminho)
        n_reval = c.execute(
            "SELECT COUNT(*) FROM revalidacao_transferido "
            "WHERE matricula='20' AND situacao <> 'FALTA'").fetchone()[0]
        n_acessos = c.execute(
            "SELECT COUNT(*) FROM acessos_sistemas WHERE matricula_vinculada='20' "
            "AND sistema='SIG'").fetchone()[0]
        c.close()
        self.assertEqual(n_reval, n_acessos)

    def test_painel_bate_com_o_banco(self):
        self._cenario()
        # a aba le de `divergencias`; cria a linha do transferido
        self._seed(*[__import__("infraestrutura.banco_dados.schema", fromlist=["x"])
                     .DivergenciaModel(
                         id=f"d{i}", tipo="ACESSO_TRANSFERIDO", sistema=SIG,
                         usuario="u20", nome_usuario="F20", matricula="20",
                         perfil_encontrado=p, descricao="Mudança de gestor — x")
                     for i, p in enumerate(("P_ANTIGO", "P_COMUM"))])
        RevalidarTransferidos(self.con).executar()
        r = vm.listar_transferidos()
        (d,) = [x for x in r["lista"] if x["m"] == "20"]
        c = sqlite3.connect(self.caminho)
        n_sobrou = c.execute("SELECT COUNT(*) FROM revalidacao_transferido "
                             "WHERE matricula='20' AND situacao='SOBROU'").fetchone()[0]
        c.close()
        self.assertEqual(len(d["sobrou"]), n_sobrou)
        self.assertEqual(r["kpis"]["sobrou"], n_sobrou)
        self.assertEqual(d["reval"]["SOBROU"], n_sobrou,
                         "contador e lista tem de dizer o mesmo numero")


class TestConvivencia(_Base):
    """A revalidacao nao pode atropelar o que ja existia."""

    def test_pipeline_completo_gera_transferido_e_revalidacao(self):
        self._grupo_sig("CHEFE A", ["P_ANTIGO", "P_COMUM"])
        self._grupo_sig("CHEFE B", ["P_NOVO", "P_COMUM"])
        self._seed(
            _ativo("21", gestor="CHEFE B"),
            _acesso("21", SIG, "P_ANTIGO"), _acesso("21", SIG, "P_COMUM"),
            Historico(data_snapshot=date(2026, 7, 1), entidade="RH_ATIVO",
                      chave_entidade="21", matricula="21", tipo="ATIVO",
                      tipo_mudanca="ALTERADO", campos_alterados="gestor",
                      dados_anterior=json.dumps({"gestor": "CHEFE A",
                                                 "cargo_codigo": "CG",
                                                 "cargo_descricao": "ANALISTA",
                                                 "centro_custo_codigo": "100",
                                                 "departamento": "TI"}),
                      dados_novo="{}"))
        AnalisarDivergencias(self.con).executar()
        RevalidarTransferidos(self.con).executar()
        self.assertIn(("P_ANTIGO", "SOBROU"), self._sit("21"))
        r = vm.listar_transferidos()
        self.assertTrue(any(x["m"] == "21" and x["sobrou"] for x in r["lista"]))

    def test_kpis_antigos_seguem_inteiros(self):
        self._cenario_min()
        r = vm.listar_transferidos()
        for k in ("revisar", "tratados", "total", "sem_acesso"):
            self.assertIn(k, r["kpis"])

    def _cenario_min(self):
        self._seed(_ativo("22"), _mov("22"))

    def test_banco_sem_a_tabela_de_revalidacao(self):
        # painel novo x banco de Processador anterior
        outro = os.path.join(self._tmp, "velho.db")
        c = sqlite3.connect(outro)
        c.executescript(
            "CREATE TABLE divergencias (tipo TEXT, sistema TEXT, usuario TEXT,"
            " nome_usuario TEXT, matricula TEXT, perfil_encontrado TEXT,"
            " data_identificacao TEXT, descricao TEXT);"
            "CREATE TABLE rh_ativos (matricula TEXT, nome TEXT, cargo_descricao TEXT,"
            " departamento TEXT, centro_custo_codigo TEXT, gestor TEXT);")
        c.execute("INSERT INTO divergencias VALUES ('ACESSO_TRANSFERIDO','SYSTUR',"
                  "'u1','N1','1','P1','2026-07-01','Mudança de gestor — x')")
        c.commit()
        c.close()
        vm.DB_PATH = outro
        r = vm.listar_transferidos()
        self.assertEqual(len(r["lista"]), 1)
        self.assertEqual(r["kpis"]["sobrou"], 0)
        self.assertEqual(r["lista"][0]["sobrou"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
