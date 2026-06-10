# -*- coding: utf-8 -*-
"""Pipeline end-to-end com dataset sintetico MAIOR + invariantes/propriedades.

Gera dezenas de funcionarios/acessos (IC + SYSTUR + terceiros), roda os casos
de uso reais em sequencia e verifica propriedades que devem valer SEMPRE:
conservacao da vinculacao, sem-vinculo <=> acesso com CPF e sem matricula,
idempotencia e determinismo, particao de status, aproximacao do IC consistente.
Mais ancoras de resultado conhecido (ADERENTE/DIVERGENTE/SEM_ACESSO/EM_ANALISE).
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import (
    RhAtivo, PerfilEsperadoModel, AcessoSistema, ValidacaoAcessoModel,
)
from infraestrutura.repositorios.repositorio_acesso_sqlite import RepositorioAcessoSqlite
from infraestrutura.repositorios.repositorio_divergencia_sqlite import RepositorioDivergenciaSqlite
from aplicacao.casos_de_uso.vincular_acessos_rh import VincularAcessosRh
from aplicacao.casos_de_uso.analisar_divergencias import AnalisarDivergencias
from aplicacao.casos_de_uso.validar_acessos_sistema import ValidarAcessosSistema, _norm_perfil
from dominio.objetos_valor.tipo_divergencia import TipoDivergencia

IC = "IC_INTEGRADOR_CONTABIL"
SYSTUR = "SYSTUR"
_ACAO = {"SEM_ACESSO", "DIVERGENTE", "EM_ANALISE"}


def _rh(mat, cpf, cc, cargo):
    return RhAtivo(matricula=mat, nome=f"NOME {mat}", cpf=cpf, cargo_codigo="CG",
                   cargo_descricao=cargo, centro_custo_codigo=cc, departamento="D",
                   situacao="ATIVO")


def _ac(sistema, usuario, perfil, cpf):
    return AcessoSistema(sistema=sistema, usuario=usuario, perfil=perfil,
                         nome_usuario=usuario, cpf=cpf, situacao="ATIVO")


class TestPipelineInvariantes(unittest.TestCase):

    N = 30          # funcionarios "bulk"
    TERCEIROS = 5   # acessos sem RH

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="cvc_inv_")
        cls.conexao = ConexaoBancoDados(os.path.join(cls._tmp, "inv.db"))
        cls.conexao.inicializar()

        rh, perfis, acessos = [], [], []

        # matriz: cc 100/ANALISTA -> IC 1 perfil + SYSTUR; cc 200/GERENTE -> IC 2 perfis (EM_ANALISE)
        perfis += [
            PerfilEsperadoModel(cargo_codigo="100", cargo_descricao="ANALISTA", sistema=IC, perfil="IC CONSULTA"),
            PerfilEsperadoModel(cargo_codigo="100", cargo_descricao="ANALISTA", sistema=SYSTUR, perfil="S1"),
            PerfilEsperadoModel(cargo_codigo="200", cargo_descricao="GERENTE", sistema=IC, perfil="IC CONSULTA"),
            PerfilEsperadoModel(cargo_codigo="200", cargo_descricao="GERENTE", sistema=IC, perfil="IC APROVADOR"),
        ]

        for i in range(1, cls.N + 1):
            cpf = str(i).zfill(11)
            cc = "100" if i % 2 == 0 else "200"
            cargo = "ANALISTA" if cc == "100" else "GERENTE"
            rh.append(_rh(f"E{i}", cpf, cc, cargo))
            m = i % 3
            if m == 0:
                acessos.append(_ac(IC, f"ic{i}", "IC_CONSULTA", cpf))
            elif m == 1:
                acessos.append(_ac(IC, f"ic{i}", "IC_APROVADOR", cpf))
            # m == 2: sem acesso IC
            if cc == "100":
                acessos.append(_ac(SYSTUR, f"sy{i}", "S1" if i % 4 == 0 else "S2", cpf))

        # Ancoras de resultado conhecido (cc 100/ANALISTA)
        rh += [
            _rh("ADE", "10000000001", "100", "ANALISTA"),   # ADERENTE
            _rh("DIV", "10000000002", "100", "ANALISTA"),   # DIVERGENTE
            _rh("SEM", "10000000003", "100", "ANALISTA"),   # SEM_ACESSO
            _rh("EMA", "10000000004", "200", "GERENTE"),    # EM_ANALISE
        ]
        acessos += [
            _ac(IC, "icADE", "IC_CONSULTA", "10000000001"),  # casa por aproximacao
            _ac(IC, "icDIV", "IC_APROVADOR", "10000000002"),  # perfil diferente
            # SEM: sem acesso IC
            _ac(IC, "icEMA", "IC_OUTRO", "10000000004"),  # nao casa nenhum -> EM_ANALISE
        ]

        # Terceiros: CPF fora do RH -> NAO_VINCULADO -> ACESSO_SEM_VINCULO_RH
        for j in range(1, cls.TERCEIROS + 1):
            acessos.append(_ac(IC, f"terc{j}", "IC_CONSULTA", f"8888888880{j}"))

        cls._n_acessos = len(acessos)
        s = cls.conexao.sessao()
        s.add_all(rh + perfis + acessos)
        s.commit()
        s.close()

        cls.contagem = VincularAcessosRh(cls.conexao).executar()
        AnalisarDivergencias(cls.conexao).executar()
        ValidarAcessosSistema(cls.conexao).executar()

    # ---------- helpers ----------
    def _validacoes(self):
        s = self.conexao.sessao()
        try:
            return s.query(ValidacaoAcessoModel).all()
        finally:
            s.close()

    def _por_mat(self):
        d = {}
        for v in self._validacoes():
            d.setdefault(v.matricula, []).append(v)
        return d

    # ---------- INVARIANTES ----------
    def test_inv_vinculacao_conserva_total(self):
        self.assertEqual(sum(self.contagem.values()), self._n_acessos)

    def test_inv_terceiros_viram_sem_vinculo(self):
        divs = RepositorioDivergenciaSqlite(self.conexao).obter_todas()
        sem_vinc = [d for d in divs if d.tipo == TipoDivergencia.ACESSO_SEM_VINCULO_RH]
        self.assertEqual(len(sem_vinc), self.TERCEIROS)
        self.assertEqual(self.contagem.get("NAO_VINCULADO", 0), self.TERCEIROS)

    def test_inv_sem_vinculo_sse_cpf_sem_matricula(self):
        # ACESSO_SEM_VINCULO_RH <=> acesso com CPF e sem matricula_vinculada
        acessos = RepositorioAcessoSqlite(self.conexao).obter_todos()
        esperado = {a.usuario for a in acessos if a.cpf and not a.matricula_vinculada}
        divs = RepositorioDivergenciaSqlite(self.conexao).obter_todas()
        obtido = {d.usuario for d in divs if d.tipo == TipoDivergencia.ACESSO_SEM_VINCULO_RH}
        self.assertEqual(obtido, esperado)

    def test_inv_status_gravados_sao_de_acao_ou_ok(self):
        vs = self._validacoes()
        self.assertTrue(vs)
        # gravamos pendencias (acao) E os OK/Aderente
        self.assertTrue(all(v.status in (_ACAO | {"OK"}) for v in vs))
        # pendencia -> PENDENTE; OK -> situacao_acao OK
        for v in vs:
            self.assertEqual(v.situacao_acao, "OK" if v.status == "OK" else "PENDENTE")

    def test_inv_em_analise_so_quando_multiplos_perfis(self):
        # EM_ANALISE so para (cc, cargo) com >1 perfil esperado = cc 200/GERENTE
        for v in self._validacoes():
            if v.status == "EM_ANALISE":
                self.assertEqual(v.sistema, IC)
                self.assertEqual(v.centro_custo_codigo, "200")

    def test_inv_aproximacao_ic_divergente_so_quando_nao_casa(self):
        # toda DIVERGENTE do IC: o esperado normalizado NAO esta entre os atuais
        for v in self._validacoes():
            if v.sistema == IC and v.status == "DIVERGENTE":
                atuais = {_norm_perfil(p) for p in (v.perfil_atual or "").split(",")}
                self.assertNotIn(_norm_perfil(v.perfil_esperado), atuais)

    def test_inv_validacao_idempotente(self):
        antes = sorted((v.matricula, v.sistema, v.perfil_esperado, v.status)
                       for v in self._validacoes())
        ValidarAcessosSistema(self.conexao).executar()   # roda de novo
        depois = sorted((v.matricula, v.sistema, v.perfil_esperado, v.status)
                        for v in self._validacoes())
        self.assertEqual(antes, depois)

    def test_inv_vinculacao_deterministica(self):
        mapa1 = {a.usuario: a.matricula_vinculada
                 for a in RepositorioAcessoSqlite(self.conexao).obter_todos()}
        VincularAcessosRh(self.conexao).executar()  # roda de novo
        mapa2 = {a.usuario: a.matricula_vinculada
                 for a in RepositorioAcessoSqlite(self.conexao).obter_todos()}
        self.assertEqual(mapa1, mapa2)

    # ---------- ANCORAS (filtradas ao sistema IC; cc 100 tambem tem SYSTUR) ----------
    def _ic(self, mat):
        return [v for v in self._por_mat().get(mat, []) if v.sistema == IC]

    def test_ancora_aderente_vira_ok(self):
        r = self._ic("ADE")
        self.assertEqual([x.status for x in r], ["OK"])

    def test_ancora_divergente(self):
        r = self._ic("DIV")
        self.assertEqual([x.status for x in r], ["DIVERGENTE"])
        self.assertIn("IC_APROVADOR", r[0].perfil_atual)

    def test_ancora_sem_acesso(self):
        r = self._ic("SEM")
        self.assertEqual([x.status for x in r], ["SEM_ACESSO"])

    def test_ancora_em_analise(self):
        r = self._ic("EMA")
        self.assertTrue(r)
        self.assertTrue(all(x.status == "EM_ANALISE" for x in r))
        self.assertEqual({x.perfil_esperado for x in r}, {"IC CONSULTA", "IC APROVADOR"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
