# -*- coding: utf-8 -*-
"""Testes do CDC (trilha de auditoria) — registrar_historico.

Foco no comportamento INCREMENTAL do RH ativos:
  - carga inicial = baseline (nao gera trilha)
  - 2o lote: NOVO (admissao) e ALTERADO (mudanca de campo) sao detectados
  - ausencia de uma matricula no lote incremental NAO vira REMOVIDO
    (senao todo ativo fora do incremento viraria falso REMOVIDO)
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dominio.entidades.funcionario_ativo import FuncionarioAtivo
from dominio.objetos_valor.cargo import Cargo
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.repositorios.repositorio_funcionario_sqlite import RepositorioFuncionarioSqlite
from aplicacao.casos_de_uso.registrar_historico import RegistrarHistorico


def _ativo(matricula, nome="JOAO SILVA", cargo_desc="ANALISTA"):
    return FuncionarioAtivo(
        matricula=matricula, nome=nome, cpf="11111111111",
        cargo=Cargo(codigo="CG1", descricao=cargo_desc,
                    departamento="TI", centro_custo="100"),
        email=f"{matricula}@cvc.com", data_admissao=date(2020, 1, 1),
        situacao="ATIVO",
    )


class TestCdcRhAtivosIncremental(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.cx = ConexaoBancoDados(self.tmp.name)
        self.cx.inicializar()
        self.repo = RepositorioFuncionarioSqlite(self.cx)
        self.hist = RegistrarHistorico(self.cx)

    def tearDown(self):
        try:
            self.cx.engine.dispose()
            os.unlink(self.tmp.name)
        except Exception:
            pass

    def _historico(self):
        c = sqlite3.connect(self.tmp.name)
        try:
            rows = c.execute(
                "SELECT entidade, tipo_mudanca, matricula FROM historico "
                "ORDER BY id").fetchall()
        finally:
            c.close()
        return rows

    def test_carga_inicial_nao_gera_trilha(self):
        res = self.hist.registrar_ativos([_ativo("MAT1"), _ativo("MAT2")])
        self.assertTrue(res["carga_inicial"])
        self.repo.salvar_ativos([_ativo("MAT1"), _ativo("MAT2")])
        self.assertEqual(self._historico(), [], "baseline nao gera trilha")

    def test_incremental_novo_e_alterado_sem_falso_removido(self):
        # 1) baseline com MAT1 e MAT2
        self.hist.registrar_ativos([_ativo("MAT1"), _ativo("MAT2")])
        self.repo.salvar_ativos([_ativo("MAT1"), _ativo("MAT2")])

        # 2) lote incremental: MAT3 novo + MAT1 com cargo alterado.
        #    MAT2 NAO vem no lote (mas continua ativo — incremental).
        lote = [
            _ativo("MAT1", cargo_desc="COORDENADOR"),  # ALTERADO
            _ativo("MAT3"),                            # NOVO
        ]
        res = self.hist.registrar_ativos(lote)
        self.repo.salvar_ativos(lote)

        self.assertEqual(res["novos"], 1, "MAT3 admitido")
        self.assertEqual(res["alterados"], 1, "MAT1 mudou de cargo")
        self.assertEqual(res["removidos"], 0,
                         "MAT2 ausente do incremento NAO pode virar REMOVIDO")

        tipos = [r[1] for r in self._historico()]
        self.assertIn("NOVO", tipos)
        self.assertIn("ALTERADO", tipos)
        self.assertNotIn("REMOVIDO", tipos)
        # MAT2 segue ativo na base
        self.assertIsNotNone(self.repo.buscar_por_matricula("MAT2"))

    def test_sem_mudanca_nao_gera_trilha(self):
        self.hist.registrar_ativos([_ativo("MAT1")])
        self.repo.salvar_ativos([_ativo("MAT1")])
        # reenviar o mesmo registro identico
        res = self.hist.registrar_ativos([_ativo("MAT1")])
        self.assertEqual(res["novos"], 0)
        self.assertEqual(res["alterados"], 0)
        self.assertEqual(res["removidos"], 0)
        self.assertEqual(self._historico(), [], "registro identico nao gera trilha")


def _com_depto(depto):
    f = _ativo("MAT1")
    f.cargo = Cargo(codigo="CG1", descricao="ANALISTA",
                    departamento=depto, centro_custo="100")
    return f


class TestCdcSoGrafiaNaoEMovimentacao(TestCdcRhAtivosIncremental):
    """Retorno de 28/09/2026: corrigida a leitura cp1250 -> cp1252, a 1a carga
    compararia 'CONCILIAÇĂO' (gravado errado) com 'CONCILIAÇÃO' e a admissao
    vazia com a preenchida — ~2 mil ALTERADO e 328 transferidos falsos."""

    def _base_e_lote(self, antes, depois):
        self.hist.registrar_ativos([antes])
        self.repo.salvar_ativos([antes])
        return self.hist.registrar_ativos([depois])

    def test_departamento_so_no_acento_nao_muda(self):
        a, d = _com_depto("CONCILIAÇĂO"), _com_depto("CONCILIAÇÃO")
        res = self._base_e_lote(a, d)
        self.assertEqual(res["alterados"], 0)
        self.assertEqual(self._historico(), [])

    def test_cargo_so_no_acento_nao_muda(self):
        res = self._base_e_lote(_ativo("MAT1", cargo_desc="DIRETOR INOVAÇĂO"),
                                _ativo("MAT1", cargo_desc="DIRETOR INOVAÇÃO"))
        self.assertEqual(res["alterados"], 0)

    def test_admissao_que_passou_a_vir_nao_muda(self):
        a, d = _ativo("MAT1"), _ativo("MAT1")
        a.data_admissao = None
        res = self._base_e_lote(a, d)
        self.assertEqual(res["alterados"], 0)

    def test_troca_real_continua_detectada(self):
        a, d = _com_depto("CONCILIAÇĂO"), _com_depto("CONTABILIDADE")
        self.assertEqual(self._base_e_lote(a, d)["alterados"], 1)

    def test_admissao_trocada_continua_detectada(self):
        a, d = _ativo("MAT1"), _ativo("MAT1")
        d.data_admissao = date(2024, 5, 1)
        self.assertEqual(self._base_e_lote(a, d)["alterados"], 1)


if __name__ == "__main__":
    unittest.main()
