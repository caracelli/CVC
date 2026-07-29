# -*- coding: utf-8 -*-
"""Transferidos: detector (via historico do RH) + regra generalizada + prova de
ponta a ponta pelo AnalisarDivergencias.

Regra (área, 29/07): mudança de CARGO, CENTRO DE CUSTO, DEPARTAMENTO ou GESTOR
gera pendência de revisão dos acessos (tipo ACESSO_TRANSFERIDO). Sem arquivo de
entrada — 100% inferido do CDC (tabela historico).
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
from aplicacao.casos_de_uso.detectar_transferidos import DetectarTransferidos
from dominio.entidades.transferido import Transferido
from dominio.entidades.funcionario_ativo import FuncionarioAtivo
from dominio.objetos_valor.cargo import Cargo
from dominio.objetos_valor.sistema import Sistema
from dominio.objetos_valor.tipo_divergencia import TipoDivergencia
from dominio.regras.regra_acesso_transferido import RegraAcessoTransferido
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


def _acesso(mat, usuario="u"):
    return AcessoSistema(sistema=SIS, usuario=usuario + mat, perfil="P1",
                         nome_usuario="F" + mat, situacao="ATIVO",
                         matricula_vinculada=mat)


# ---- unidade: regra generalizada -----------------------------------------
class TestRegraGeneralizada(unittest.TestCase):
    def setUp(self):
        self.regra = RegraAcessoTransferido()

    def _t(self, **mud):
        # funcionario ATUAL x cargo/gestor ANTERIOR — só o que passar em `mud` muda
        atual = FuncionarioAtivo(matricula="1", nome="A", cpf="1",
                                 cargo=Cargo("CG", "ANALISTA", "TI", "100"),
                                 gestor="CHEFE A")
        ant = Cargo(mud.get("cargo_cod", "CG"), mud.get("cargo_desc", "ANALISTA"),
                    mud.get("dep", "TI"), mud.get("cc", "100"))
        return Transferido(funcionario=atual, cargo_anterior=ant,
                           gestor_anterior=mud.get("gestor", "CHEFE A"),
                           data_transferencia=date(2026, 1, 1))

    def test_gestor_dispara(self):
        self.assertTrue(self._t(gestor="CHEFE B").precisa_revisao_acessos)

    def test_centro_custo_dispara(self):
        self.assertTrue(self._t(cc="200").precisa_revisao_acessos)

    def test_cargo_dispara(self):
        self.assertTrue(self._t(cargo_desc="COORDENADOR").precisa_revisao_acessos)

    def test_departamento_dispara(self):
        self.assertTrue(self._t(dep="COMERCIAL").precisa_revisao_acessos)

    def test_nada_mudou_nao_dispara(self):
        self.assertFalse(self._t().precisa_revisao_acessos)

    def test_campos_mudados_lista_gestor(self):
        self.assertIn("gestor", self._t(gestor="X").campos_mudados)


class _Db(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_transf_")
        self.con = ConexaoBancoDados(os.path.join(self._tmp, "t.db"))
        self.con.inicializar()

    def _seed(self, *orm):
        s = self.con.sessao()
        s.add_all(orm)
        s.commit()
        s.close()


# ---- detector: le o historico -------------------------------------------
class TestDetector(_Db):

    def test_mudanca_de_gestor_vira_transferido(self):
        self._seed(_ativo("10", gestor="CHEFE NOVO"),
                   _hist("10", "gestor", {"gestor": "CHEFE VELHO",
                                          "cargo_codigo": "CG", "cargo_descricao": "ANALISTA",
                                          "centro_custo_codigo": "100", "departamento": "TI"}))
        ts = DetectarTransferidos(self.con).executar()
        self.assertEqual(len(ts), 1)
        self.assertEqual(ts[0].funcionario.matricula, "10")
        self.assertEqual(ts[0].gestor_anterior, "CHEFE VELHO")
        self.assertTrue(ts[0].precisa_revisao_acessos)
        self.assertEqual(ts[0].campos_mudados, "gestor")

    def test_mudanca_irrelevante_nao_entra(self):
        # so email/nome mudaram -> nao e' transferencia
        self._seed(_ativo("10"),
                   _hist("10", "email,nome", {"email": "a@x", "nome": "ANTIGO"}))
        self.assertEqual(DetectarTransferidos(self.con).executar(), [])

    def test_so_conta_quem_esta_ativo(self):
        # historico de mudanca, mas a pessoa nao esta mais em rh_ativos
        self._seed(_hist("77", "departamento", {"departamento": "TI"}))
        self.assertEqual(DetectarTransferidos(self.con).executar(), [])

    def test_apenas_a_mudanca_mais_recente_por_pessoa(self):
        self._seed(_ativo("10", dep="COMERCIAL"),
                   _hist("10", "departamento", {"departamento": "TI"}, snap="2026-05-01"),
                   _hist("10", "departamento", {"departamento": "RH"}, snap="2026-07-01"))
        ts = DetectarTransferidos(self.con).executar()
        self.assertEqual(len(ts), 1)
        # vence a mais recente (2026-07): anterior = RH
        self.assertEqual(ts[0].cargo_anterior.departamento, "RH")


# ---- E2E: AnalisarDivergencias gera ACESSO_TRANSFERIDO -------------------
class TestPipelineGeraTransferido(_Db):

    def test_gera_acesso_transferido_para_quem_mudou(self):
        self._seed(
            _ativo("10", gestor="CHEFE NOVO"),
            _hist("10", "gestor", {"gestor": "CHEFE VELHO"}),
            _acesso("10"),
            # pessoa sem mudança: nao gera
            _ativo("20"),
            _acesso("20"),
        )
        AnalisarDivergencias(self.con).executar()
        s = self.con.sessao()
        from infraestrutura.banco_dados.schema import DivergenciaModel as DivOrm
        tipos = [d.matricula for d in s.query(DivOrm)
                 .filter(DivOrm.tipo == TipoDivergencia.ACESSO_TRANSFERIDO.value).all()]
        s.close()
        self.assertIn("10", tipos)
        self.assertNotIn("20", tipos)


class TestFoldingTratamentoTransferido(unittest.TestCase):
    """O Processador persiste TRATAMENTO_TRANSFERIDO em tratamentos_transferido
    (senão a revisão sob ticket se perderia no reset da pasta INTERACOES)."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_ftt_")

    def test_folding_persiste(self):
        from aplicacao.casos_de_uso.dobrar_interacoes import DobrarInteracoes
        banco = os.path.join(self._tmp, "b.db")
        sqlite3.connect(banco).close()
        pasta = os.path.join(self._tmp, "INTERACOES")
        os.makedirs(pasta)
        with open(os.path.join(pasta, "u.jsonl"), "w", encoding="utf-8") as f:
            f.write(json.dumps({
                "tipo_interacao": "TRATAMENTO_TRANSFERIDO", "registro_id": "10",
                "acao": "TRATAR", "ticket": "IAM-42", "motivo": "Transferência de Área",
                "nome": "ANA", "usuario": "user",
                "data_acao": "2026-07-29T10:00:00"}) + "\n")
        DobrarInteracoes(caminho_banco=banco, pasta_interacoes=pasta).executar()
        c = sqlite3.connect(banco)
        row = c.execute("SELECT ticket, motivo FROM tratamentos_transferido "
                        "WHERE registro_id='10'").fetchone()
        c.close()
        self.assertEqual(row, ("IAM-42", "Transferência de Área"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
