# -*- coding: utf-8 -*-
"""CDC / trilha de auditoria (RegistrarHistorico) — edge cases profundos.

Vai alem do basico (NOVO/ALTERADO/REMOVIDO): confere campos_alterados exatos,
o JSON dados_anterior/dados_novo, que CPF reformatado NAO gera ALTERADO falso,
que campo fora da lista de comparacao nao gera trilha, normalizacao de
matricula (zeros a esquerda) e REMOVIDO so em desligados (ativos sao incrementais).
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import RhAtivo, RhDesligado, Historico, SnapshotRh
from dominio.objetos_valor.cargo import Cargo
from dominio.entidades.funcionario_ativo import FuncionarioAtivo
from dominio.entidades.funcionario_desligado import FuncionarioDesligado
from aplicacao.casos_de_uso.registrar_historico import RegistrarHistorico


def _orm_ativo(mat, nome="F1", cpf="11111111111", cargo_cod="CG1",
               cargo_desc="ANALISTA", cc="100", dep="TI", email="e@x",
               sit="ATIVO", adm=date(2020, 1, 1)):
    return RhAtivo(matricula=mat, nome=nome, cpf=cpf, cargo_codigo=cargo_cod,
                   cargo_descricao=cargo_desc, centro_custo_codigo=cc,
                   departamento=dep, data_admissao=adm, email=email, situacao=sit)


def _ent_ativo(mat, nome="F1", cpf="11111111111", cargo_cod="CG1",
               cargo_desc="ANALISTA", cc="100", dep="TI", email="e@x",
               sit="ATIVO", adm=date(2020, 1, 1), tipo_vinculo="FUNCIONARIO"):
    return FuncionarioAtivo(
        matricula=mat, nome=nome, cpf=cpf,
        cargo=Cargo(codigo=cargo_cod, descricao=cargo_desc, departamento=dep, centro_custo=cc),
        email=email, data_admissao=adm, situacao=sit, tipo_vinculo=tipo_vinculo)


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_cdc_")
        self.conexao = ConexaoBancoDados(os.path.join(self._tmp, "cdc.db"))
        self.conexao.inicializar()
        self.hist = RegistrarHistorico(self.conexao)

    def _seed(self, *orm):
        s = self.conexao.sessao()
        s.add_all(orm)
        s.commit()
        s.close()

    def _hist(self, **filtro):
        s = self.conexao.sessao()
        try:
            q = s.query(Historico)
            if filtro:
                q = q.filter_by(**filtro)
            return q.all()
        finally:
            s.close()


class TestCDCAlterado(_Base):

    def test_campos_alterados_lista_exatamente_o_que_mudou(self):
        self._seed(_orm_ativo("100", cargo_desc="ANALISTA"))
        r = self.hist.registrar_ativos([_ent_ativo("100", cargo_desc="GERENTE")])
        self.assertEqual(r["alterados"], 1)
        h = self._hist(tipo_mudanca="ALTERADO")
        self.assertEqual(len(h), 1)
        self.assertEqual(h[0].campos_alterados, "cargo_descricao")
        self.assertEqual(h[0].entidade, "RH_ATIVO")
        self.assertEqual(h[0].matricula, "100")

    def test_json_anterior_e_novo_refletem_o_antes_depois(self):
        self._seed(_orm_ativo("100", cargo_desc="ANALISTA", email="a@x"))
        self.hist.registrar_ativos([_ent_ativo("100", cargo_desc="GERENTE", email="b@x")])
        h = self._hist(tipo_mudanca="ALTERADO")[0]
        ant, nov = json.loads(h.dados_anterior), json.loads(h.dados_novo)
        self.assertEqual(ant["cargo_descricao"], "ANALISTA")
        self.assertEqual(nov["cargo_descricao"], "GERENTE")
        self.assertEqual(ant["email"], "a@x")
        self.assertEqual(nov["email"], "b@x")
        self.assertEqual(set(h.campos_alterados.split(",")), {"cargo_descricao", "email"})

    def test_cpf_reformatado_nao_gera_alterado_falso(self):
        self._seed(_orm_ativo("100", cpf="11111111111"))
        r = self.hist.registrar_ativos([_ent_ativo("100", cpf="111.111.111-11")])
        self.assertEqual(r["alterados"], 0)
        self.assertEqual(self._hist(tipo_mudanca="ALTERADO"), [])

    def test_campo_fora_da_comparacao_nao_gera_trilha(self):
        # tipo_vinculo NAO esta em _CAMPOS_ATIVO -> mudar nao gera ALTERADO
        self._seed(_orm_ativo("100"))
        r = self.hist.registrar_ativos([_ent_ativo("100", tipo_vinculo="TERCEIRO")])
        self.assertEqual(r["alterados"], 0)

    def test_situacao_normalizada_nao_gera_falso_alterado(self):
        # 'A' normaliza para 'ATIVO' -> igual ao anterior
        self._seed(_orm_ativo("100", sit="ATIVO"))
        r = self.hist.registrar_ativos([_ent_ativo("100", sit="A")])
        self.assertEqual(r["alterados"], 0)

    def test_registro_identico_nao_gera_nada(self):
        self._seed(_orm_ativo("100"))
        r = self.hist.registrar_ativos([_ent_ativo("100")])
        self.assertEqual((r["novos"], r["alterados"], r["removidos"]), (0, 0, 0))
        self.assertEqual(self._hist(), [])


class TestCDCNovoEChave(_Base):

    def test_novo_tem_dados_anterior_nulo(self):
        self._seed(_orm_ativo("100"))   # baseline nao-vazia
        self.hist.registrar_ativos([_ent_ativo("100"), _ent_ativo("200")])
        novos = self._hist(tipo_mudanca="NOVO")
        self.assertEqual(len(novos), 1)
        self.assertIsNone(novos[0].dados_anterior)
        self.assertIsNotNone(novos[0].dados_novo)
        self.assertEqual(novos[0].matricula, "200")

    def test_matricula_com_zeros_a_esquerda_casa_a_mesma_pessoa(self):
        # base tem '100'; lote traz '00100' -> mesma chave normalizada, sem NOVO
        self._seed(_orm_ativo("100"))
        r = self.hist.registrar_ativos([_ent_ativo("00100")])
        self.assertEqual(r["novos"], 0)
        self.assertEqual(self._hist(tipo_mudanca="NOVO"), [])

    def test_lote_misto_novo_alterado_inalterado(self):
        self._seed(_orm_ativo("100", cargo_desc="ANALISTA"),
                   _orm_ativo("101", cargo_desc="ASSISTENTE"))
        r = self.hist.registrar_ativos([
            _ent_ativo("100", cargo_desc="GERENTE"),     # ALTERADO
            _ent_ativo("101", cargo_desc="ASSISTENTE"),  # inalterado
            _ent_ativo("102", cargo_desc="ESTAGIARIO"),  # NOVO
        ])
        self.assertEqual((r["novos"], r["alterados"]), (1, 1))
        self.assertEqual(len(self._hist(tipo_mudanca="NOVO")), 1)
        self.assertEqual(len(self._hist(tipo_mudanca="ALTERADO")), 1)


class TestCDCRemocao(_Base):

    def test_ativos_nao_geram_removido_por_ausencia(self):
        self._seed(_orm_ativo("100"), _orm_ativo("200"))
        r = self.hist.registrar_ativos([_ent_ativo("100")])  # 200 ausente
        self.assertEqual(r["removidos"], 0)
        self.assertEqual(self._hist(tipo_mudanca="REMOVIDO"), [])

    def test_desligados_geram_removido_por_ausencia(self):
        # desligados sao SNAPSHOT (base inteira por ciclo) -> ausencia = REMOVIDO
        self._seed(
            RhDesligado(matricula="200", nome="D200", cpf="22222222222",
                        cargo_codigo="CG", cargo_descricao="X", centro_custo_codigo="1",
                        departamento="TI", data_admissao=date(2019, 1, 1),
                        data_desligamento=date(2026, 1, 1), email="d@x"),
            RhDesligado(matricula="201", nome="D201", cpf="33333333333",
                        cargo_codigo="CG", cargo_descricao="X", centro_custo_codigo="1",
                        departamento="TI", data_admissao=date(2019, 1, 1),
                        data_desligamento=date(2026, 1, 1), email="e@x"),
        )
        d200 = FuncionarioDesligado(
            matricula="200", nome="D200", cpf="22222222222",
            cargo=Cargo(codigo="CG", descricao="X", departamento="TI", centro_custo="1"),
            email="d@x", data_admissao=date(2019, 1, 1), data_desligamento=date(2026, 1, 1))
        r = self.hist.registrar_desligados([d200])  # 201 ausente
        self.assertEqual(r["removidos"], 1)
        rem = self._hist(tipo_mudanca="REMOVIDO")
        self.assertEqual(len(rem), 1)
        self.assertEqual(rem[0].entidade, "RH_DESLIGADO")
        self.assertEqual(rem[0].matricula, "201")
        self.assertIsNone(rem[0].dados_novo)
        self.assertIsNotNone(rem[0].dados_anterior)


class TestCDCSnapshot(_Base):

    def test_snapshot_registra_contadores(self):
        self._seed(_orm_ativo("100", cargo_desc="ANALISTA"))
        self.hist.registrar_ativos([
            _ent_ativo("100", cargo_desc="GERENTE"),   # alterado
            _ent_ativo("200"),                          # novo
        ])
        s = self.conexao.sessao()
        snaps = s.query(SnapshotRh).filter_by(tipo="ATIVO").all()
        s.close()
        self.assertEqual(len(snaps), 1)
        self.assertEqual((snaps[0].novos, snaps[0].alterados, snaps[0].removidos), (1, 1, 0))
        self.assertEqual(snaps[0].total_registros, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
