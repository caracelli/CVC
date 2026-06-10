# -*- coding: utf-8 -*-
"""Pipeline IC INTEGRADO: vinculacao -> divergencias -> validacao.

Semeia RH + matriz + acessos SEM vinculo previo e roda os casos de uso reais
em sequencia (como o Processador):
  1. VincularAcessosRh   -> liga acessos ao RH por CPF/email (cascata)
  2. AnalisarDivergencias-> gera ACESSO_SEM_VINCULO_RH para terceiros
  3. ValidarAcessosSistema-> status com a APROXIMACAO de perfil do IC

Tambem documenta o LIMITE: RegraPerfilInvalido (tabela divergencias) usa
casamento EXATO — mas isso nao chega ao cliente, pois o painel usa
validacao_acessos e o Excel exclui PERFIL_INVALIDO.
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
from infraestrutura.repositorios.repositorio_divergencia_sqlite import RepositorioDivergenciaSqlite
from aplicacao.casos_de_uso.vincular_acessos_rh import VincularAcessosRh
from aplicacao.casos_de_uso.analisar_divergencias import AnalisarDivergencias
from aplicacao.casos_de_uso.validar_acessos_sistema import ValidarAcessosSistema
from dominio.objetos_valor.tipo_divergencia import TipoDivergencia

IC = "IC_INTEGRADOR_CONTABIL"


class TestPipelineICIntegrado(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="cvc_pipe_")
        cls.conexao = ConexaoBancoDados(os.path.join(cls._tmp, "pipe.db"))
        cls.conexao.inicializar()

        s = cls.conexao.sessao()
        s.add_all([
            # RH
            RhAtivo(matricula="A1", nome="ANA SILVA", cpf="11111111111",
                    email="ana@cvc.com", cargo_codigo="CG", cargo_descricao="ANALISTA",
                    centro_custo_codigo="100", situacao="ATIVO"),
            RhAtivo(matricula="A2", nome="BRUNO LIMA", cpf="22222222222",
                    email="bruno@cvc.com", cargo_codigo="CG", cargo_descricao="ANALISTA",
                    centro_custo_codigo="100", situacao="ATIVO"),
            # matriz IC
            PerfilEsperadoModel(cargo_codigo="100", cargo_descricao="ANALISTA",
                                sistema=IC, perfil="IC CONSULTA", acesso_manual=False),
            # acessos SEM vinculo previo
            #  u1: casa A1 por CPF; perfil 'IC_CONSULTA' (underscore) -> ADERENTE (aprox)
            AcessoSistema(sistema=IC, usuario="u1", perfil="IC_CONSULTA",
                          nome_usuario="ANA SILVA", cpf="11111111111", situacao="ATIVO"),
            #  u2: casa A2 por EMAIL (sem cpf); perfil 'IC_APROVADOR' -> DIVERGENTE
            AcessoSistema(sistema=IC, usuario="u2", perfil="IC_APROVADOR",
                          nome_usuario="BRUNO LIMA", email="bruno@cvc.com", situacao="ATIVO"),
            #  u3: terceiro — CPF nao existe no RH -> NAO_VINCULADO -> ACESSO_SEM_VINCULO_RH
            AcessoSistema(sistema=IC, usuario="u3", perfil="IC_CONSULTA",
                          nome_usuario="TERCEIRO EXTERNO", cpf="99999999999", situacao="ATIVO"),
        ])
        s.commit()
        s.close()

        cls.contagem = VincularAcessosRh(cls.conexao).executar()
        AnalisarDivergencias(cls.conexao).executar()
        ValidarAcessosSistema(cls.conexao).executar()

        cls.divs = RepositorioDivergenciaSqlite(cls.conexao).obter_todas()
        s = cls.conexao.sessao()
        cls.validacoes = s.query(ValidacaoAcessoModel).all()
        s.close()

    # ---- 1) Vinculacao (cascata) ----
    def test_vinculacao_cpf_email_e_nao_vinculado(self):
        self.assertEqual(self.contagem.get("CPF", 0), 1)
        self.assertEqual(self.contagem.get("EMAIL", 0), 1)
        self.assertEqual(self.contagem.get("NAO_VINCULADO", 0), 1)

    # ---- 2) Divergencias ----
    def test_terceiro_vira_acesso_sem_vinculo_rh(self):
        sem_vinculo = [d for d in self.divs
                       if d.tipo == TipoDivergencia.ACESSO_SEM_VINCULO_RH]
        self.assertEqual(len(sem_vinculo), 1)
        self.assertEqual(sem_vinculo[0].usuario, "u3")

    def test_vinculados_nao_geram_sem_vinculo(self):
        usuarios_sem_vinculo = {
            d.usuario for d in self.divs
            if d.tipo == TipoDivergencia.ACESSO_SEM_VINCULO_RH
        }
        self.assertNotIn("u1", usuarios_sem_vinculo)
        self.assertNotIn("u2", usuarios_sem_vinculo)

    # ---- 3) Validacao (com aproximacao) ----
    def _val(self, matricula):
        return [v for v in self.validacoes if v.matricula == matricula]

    def test_a1_aderente_por_aproximacao_apos_vinculo_por_cpf(self):
        # ligado por CPF; 'IC_CONSULTA' casa 'IC CONSULTA' -> OK/Aderente (visivel,
        # situacao_acao=OK, nao e' pendencia)
        r = self._val("A1")
        self.assertEqual([v.status for v in r], ["OK"])
        self.assertEqual(r[0].situacao_acao, "OK")

    def test_a2_divergente_apos_vinculo_por_email(self):
        r = self._val("A2")
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0].status, "DIVERGENTE")
        self.assertIn("IC_APROVADOR", r[0].perfil_atual)

    # ---- LIMITE conhecido: divergencias usa casamento EXATO (nao chega ao cliente) ----
    def test_limite_perfil_invalido_exato_existe_mas_nao_e_client_facing(self):
        # RegraPerfilInvalido compara exato: 'IC_CONSULTA' != 'IC CONSULTA',
        # entao A1 (ADERENTE na validacao) AINDA aparece como PERFIL_INVALIDO na
        # tabela divergencias. Isso NAO chega ao cliente: o painel usa
        # validacao_acessos (com aproximacao) e o GerarSaidas exclui
        # PERFIL_INVALIDO do Excel. Este teste documenta/guarda esse limite.
        perfil_invalido_mats = {
            d.matricula for d in self.divs
            if d.tipo == TipoDivergencia.PERFIL_INVALIDO
        }
        self.assertIn("A1", perfil_invalido_mats)        # falso-positivo na tabela bruta
        # mas a validacao diz OK/Aderente (nao e' pendencia)
        self.assertEqual([v.status for v in self._val("A1")], ["OK"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
