# -*- coding: utf-8 -*-
"""Card 23 — revalidacao de acessos POS-TRANSFERENCIA.

O Card 22 marca TODOS os acessos do transferido para revisao ("olhe tudo").
Aqui cada acesso e' julgado contra o esperado da funcao/equipe NOVA e da ANTIGA:
MANTEM / SOBROU (so a antiga previa) / EXCESSO (nenhuma das duas) / FALTA (a
nova preve e a pessoa nao tem).

Cobre os DOIS criterios de "esperado", porque os sistemas nao sao iguais:
 - MATRIZ+CCO (cc+cargo / cc+gestor) para os sistemas com matriz;
 - ESPELHO do grupo para o SIG (cc+gestor+cargo, fallback cc+gestor, perfil em
   >=70% dos colegas que usam SIG, minimo 2 colegas).
Medido na base real: pelo espelho aparecem 45 "sobrou"; so pela matriz, 1.
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from aplicacao.casos_de_uso.revalidar_transferidos import RevalidarTransferidos
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import (
    AcessoSistema, MatrizCcoModel, PerfilEsperadoModel, RhAtivo, TransferidoModel)

SIG = "SIG"
SYS = "SYSTUR"


def _ativo(mat, cc="100", gestor="CHEFE A", cargo="ANALISTA", vinc="FUNCIONARIO"):
    return RhAtivo(matricula=mat, nome="F" + mat, cpf="", cargo_codigo="CG",
                   cargo_descricao=cargo, centro_custo_codigo=cc, departamento="TI",
                   situacao="ATIVO", tipo_vinculo=vinc, gestor=gestor)


def _acesso(mat, sistema, perfil):
    return AcessoSistema(sistema=sistema, usuario="u" + mat, perfil=perfil,
                         nome_usuario="F" + mat, situacao="ATIVO",
                         matricula_vinculada=mat)


def _mov(mat, cc_ant="100", cargo_ant="ANALISTA", gestor_ant="CHEFE A",
         cc_atu="100", cargo_atu="ANALISTA", gestor_atu="CHEFE B"):
    return TransferidoModel(
        matricula=mat, nome="F" + mat, campos_mudados="gestor",
        data_transferencia="2026-07-01",
        cargo_codigo_anterior="CG", cargo_anterior=cargo_ant,
        departamento_anterior="TI", centro_custo_anterior=cc_ant,
        gestor_anterior=gestor_ant,
        cargo_codigo_atual="CG", cargo_atual=cargo_atu,
        departamento_atual="TI", centro_custo_atual=cc_atu, gestor_atual=gestor_atu)


class _Db(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_reval_")
        self.caminho = os.path.join(self._tmp, "t.db")
        self.con = ConexaoBancoDados(self.caminho)
        self.con.inicializar()

    def _seed(self, *orm):
        s = self.con.sessao()
        s.add_all(orm)
        s.commit()
        s.close()

    def _resultado(self):
        c = sqlite3.connect(self.caminho)
        c.row_factory = sqlite3.Row
        try:
            out = {}
            for r in c.execute("SELECT * FROM revalidacao_transferido"):
                out.setdefault(r["matricula"], []).append(
                    (r["sistema"], r["perfil"], r["situacao"], r["origem"]))
            return out
        finally:
            c.close()


class TestEspelhoSig(_Db):
    """A pessoa troca de GRUPO; o padrao do grupo e' que julga o acesso."""

    def _cenario(self):
        # grupo ANTIGO (gestor A): 2 colegas, ambos com P_ANTIGO e P_COMUM
        self._seed(_ativo("A1", gestor="CHEFE A"), _ativo("A2", gestor="CHEFE A"),
                   _acesso("A1", SIG, "P_ANTIGO"), _acesso("A1", SIG, "P_COMUM"),
                   _acesso("A2", SIG, "P_ANTIGO"), _acesso("A2", SIG, "P_COMUM"))
        # grupo NOVO (gestor B): 2 colegas, ambos com P_NOVO e P_COMUM
        self._seed(_ativo("B1", gestor="CHEFE B"), _ativo("B2", gestor="CHEFE B"),
                   _acesso("B1", SIG, "P_NOVO"), _acesso("B1", SIG, "P_COMUM"),
                   _acesso("B2", SIG, "P_NOVO"), _acesso("B2", SIG, "P_COMUM"))

    def test_classifica_pelos_dois_grupos(self):
        self._cenario()
        # transferida: tem o do grupo antigo, o comum, e um perfil solto
        self._seed(_ativo("10", gestor="CHEFE B"),
                   _acesso("10", SIG, "P_ANTIGO"), _acesso("10", SIG, "P_COMUM"),
                   _acesso("10", SIG, "P_SOLTO"),
                   _mov("10"))
        RevalidarTransferidos(self.con).executar()
        r = {(p, s) for _, p, s, _ in self._resultado()["10"]}
        self.assertIn(("P_COMUM", "MANTEM"), r)
        self.assertIn(("P_ANTIGO", "SOBROU"), r, "perfil que so o grupo antigo tinha")
        self.assertIn(("P_SOLTO", "EXCESSO"), r)
        self.assertIn(("P_NOVO", "FALTA"), r, "o grupo novo tem e ela nao")

    def test_origem_espelho_e_tamanho_dos_grupos(self):
        self._cenario()
        self._seed(_ativo("10", gestor="CHEFE B"), _acesso("10", SIG, "P_ANTIGO"),
                   _mov("10"))
        RevalidarTransferidos(self.con).executar()
        c = sqlite3.connect(self.caminho)
        row = c.execute("SELECT origem, pares_antes, pares_depois FROM "
                        "revalidacao_transferido WHERE matricula='10' LIMIT 1").fetchone()
        c.close()
        self.assertEqual(row, ("ESPELHO", 2, 2))

    def test_grupo_pequeno_nao_inventa_veredito(self):
        # so 1 colega em cada lado -> sem padrao -> nada a dizer
        self._seed(_ativo("A1", gestor="CHEFE A"), _acesso("A1", SIG, "P_ANTIGO"),
                   _ativo("B1", gestor="CHEFE B"), _acesso("B1", SIG, "P_NOVO"),
                   _ativo("10", gestor="CHEFE B"), _acesso("10", SIG, "P_ANTIGO"),
                   _mov("10"))
        RevalidarTransferidos(self.con).executar()
        self.assertEqual(self._resultado(), {})

    def test_a_propria_pessoa_nao_entra_no_padrao_do_grupo(self):
        # 2 colegas no grupo novo SEM P_X; a transferida tem P_X. Se ela contasse
        # no proprio grupo, P_X poderia virar "padrao" e mascarar o excesso.
        self._seed(_ativo("B1", gestor="CHEFE B"), _acesso("B1", SIG, "P_COMUM"),
                   _ativo("B2", gestor="CHEFE B"), _acesso("B2", SIG, "P_COMUM"),
                   _ativo("A1", gestor="CHEFE A"), _acesso("A1", SIG, "P_COMUM"),
                   _ativo("A2", gestor="CHEFE A"), _acesso("A2", SIG, "P_COMUM"),
                   _ativo("10", gestor="CHEFE B"),
                   _acesso("10", SIG, "P_COMUM"), _acesso("10", SIG, "P_X"),
                   _mov("10"))
        RevalidarTransferidos(self.con).executar()
        r = {(p, s) for _, p, s, _ in self._resultado()["10"]}
        self.assertIn(("P_X", "EXCESSO"), r)


class TestMatriz(_Db):
    """Sistemas com matriz: compara (cc, cargo) antigo x novo."""

    def test_perfil_da_funcao_antiga_sobra(self):
        self._seed(
            PerfilEsperadoModel(cargo_codigo="100", cargo_descricao="ANALISTA",
                                sistema=SYS, perfil="P_ANALISTA", acesso_manual=False),
            PerfilEsperadoModel(cargo_codigo="100", cargo_descricao="COORDENADOR",
                                sistema=SYS, perfil="P_COORD", acesso_manual=False),
            _ativo("20", cargo="COORDENADOR"),
            _acesso("20", SYS, "P_ANALISTA"),
            _mov("20", cargo_ant="ANALISTA", cargo_atu="COORDENADOR",
                 gestor_ant="CHEFE A", gestor_atu="CHEFE A"))
        RevalidarTransferidos(self.con).executar()
        r = {(p, s) for _, p, s, _ in self._resultado()["20"]}
        self.assertIn(("P_ANALISTA", "SOBROU"), r)
        self.assertIn(("P_COORD", "FALTA"), r)

    def test_origem_matriz(self):
        self._seed(
            PerfilEsperadoModel(cargo_codigo="100", cargo_descricao="ANALISTA",
                                sistema=SYS, perfil="P_A", acesso_manual=False),
            _ativo("21", cargo="ANALISTA"), _acesso("21", SYS, "P_A"),
            _mov("21", gestor_ant="CHEFE A", gestor_atu="CHEFE B"))
        RevalidarTransferidos(self.con).executar()
        c = sqlite3.connect(self.caminho)
        origem = c.execute("SELECT origem FROM revalidacao_transferido "
                           "WHERE matricula='21' LIMIT 1").fetchone()[0]
        c.close()
        self.assertEqual(origem, "MATRIZ/CCO")

    def test_cco_do_gestor_novo_conta(self):
        self._seed(
            MatrizCcoModel(cc="100", gestor="CHEFE B", sistema=SYS, perfil="P_CCO"),
            _ativo("22", gestor="CHEFE B"), _acesso("22", SYS, "P_CCO"),
            _mov("22"))
        RevalidarTransferidos(self.con).executar()
        r = {(p, s) for _, p, s, _ in self._resultado()["22"]}
        self.assertIn(("P_CCO", "MANTEM"), r)


class TestComportamentoGeral(_Db):

    def test_sem_movimento_nao_grava_nada(self):
        self._seed(_ativo("30"), _acesso("30", SYS, "P"))
        self.assertEqual(RevalidarTransferidos(self.con).executar(), 0)
        self.assertEqual(self._resultado(), {})

    def test_e_snapshot_nao_acumula(self):
        self._seed(
            PerfilEsperadoModel(cargo_codigo="100", cargo_descricao="ANALISTA",
                                sistema=SYS, perfil="P_A", acesso_manual=False),
            _ativo("31", cargo="ANALISTA"), _acesso("31", SYS, "P_A"), _mov("31"))
        RevalidarTransferidos(self.con).executar()
        RevalidarTransferidos(self.con).executar()
        c = sqlite3.connect(self.caminho)
        n = c.execute("SELECT COUNT(*) FROM revalidacao_transferido").fetchone()[0]
        c.close()
        self.assertEqual(n, 1)

    def test_sistema_sem_esperado_nenhum_fica_de_fora(self):
        # sem matriz e sem espelho: a revalidacao nao tem o que dizer e NAO
        # inventa veredito (a regra geral ja trata esse acesso)
        self._seed(_ativo("32"), _acesso("32", SYS, "P_QUALQUER"), _mov("32"))
        RevalidarTransferidos(self.con).executar()
        self.assertEqual(self._resultado(), {})

    def test_retorno_conta_sobrou_mais_falta(self):
        self._seed(
            PerfilEsperadoModel(cargo_codigo="100", cargo_descricao="ANALISTA",
                                sistema=SYS, perfil="P_ANALISTA", acesso_manual=False),
            PerfilEsperadoModel(cargo_codigo="100", cargo_descricao="COORDENADOR",
                                sistema=SYS, perfil="P_COORD", acesso_manual=False),
            _ativo("33", cargo="COORDENADOR"), _acesso("33", SYS, "P_ANALISTA"),
            _mov("33", cargo_ant="ANALISTA", cargo_atu="COORDENADOR",
                 gestor_ant="CHEFE A", gestor_atu="CHEFE A"))
        self.assertEqual(RevalidarTransferidos(self.con).executar(), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
