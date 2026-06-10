# -*- coding: utf-8 -*-
"""Leitores de extrato e de matriz com ARQUIVOS SINTETICOS.

Cria xlsx/csv minimos no formato real do IC e do SYSTUR e confere o parsing:
mapeamento de colunas, normalizacao de CPF, mapa de situacao, deteccao do
sistema pelo nome do arquivo, CCUSTO/CARGO/ACESSO MANUAL na matriz e o filtro
de sistemas_em_escopo.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.leitores_arquivos.leitor_sistema import LeitorSistema
from infraestrutura.leitores_arquivos.leitor_matriz import LeitorMatrizPerfis
from infraestrutura.leitores_arquivos.configs_sistemas import CONFIGS_SISTEMAS
from dominio.objetos_valor.sistema import Sistema


def _xlsx(path, header, linhas):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(header)
    for ln in linhas:
        ws.append(ln)
    wb.save(path)


class TestLeitorSistemaIC(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="cvc_leit_ic_")
        cls.arq = os.path.join(cls._tmp, "relatorio IC.xlsx")
        _xlsx(cls.arq,
              ["CD_PESSOA", "CD_LOGIN", "NM_PESSOA", "CD_EMAIL", "NM_GRUPO", "ST_HABILITACAO", "CPF"],
              [
                  [1, "CORP01", "ana silva", "ANA@CVC.COM", "IC_CONSULTA", "A", "294404948-83"],
                  [2, "CORP02", "BRUNO LIMA", "b@cvc.com", "IC_APROVADOR", "A", "11122233344"],
                  [3, "", "SEM LOGIN", "x@x.com", "IC_CONSULTA", "A", "123"],  # usuario vazio -> ignorado
              ])
        leitor = LeitorSistema(CONFIGS_SISTEMAS[Sistema.IC_INTEGRADOR_CONTABIL])
        cls.perfis = {p.usuario: p for p in leitor.ler_um(Path(cls.arq))}

    def test_ignora_linha_sem_usuario(self):
        self.assertEqual(set(self.perfis), {"CORP01", "CORP02"})

    def test_mapeamento_de_colunas_e_sistema(self):
        p = self.perfis["CORP01"]
        self.assertEqual(p.sistema, Sistema.IC_INTEGRADOR_CONTABIL)
        self.assertEqual(p.perfil, "IC_CONSULTA")
        self.assertEqual(p.email, "ANA@CVC.COM")

    def test_situacao_A_mapeia_para_ATIVO(self):
        self.assertEqual(self.perfis["CORP01"].situacao, "ATIVO")

    def test_cpf_normalizado_remove_mascara(self):
        # '294404948-83' -> 11 digitos
        self.assertEqual(self.perfis["CORP01"].cpf, "29440494883")

    def test_nome_normalizado_para_maiusculo(self):
        self.assertEqual(self.perfis["CORP01"].nome_usuario, "ANA SILVA")


class TestLeitorSistemaSYSTURcsv(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="cvc_leit_sy_")
        cls.arq = os.path.join(cls._tmp, "relatorio SYSTUR.csv")
        # SYSTUR le CSV com sep=';'; colunas conforme CONFIGS_SISTEMAS[SYSTUR]
        conteudo = (
            "CD_LOGIN;NM_PESSOA;CPF / CNPJ;EMAIL;CD_GRUPO_SIGLA;S\n"
            "LOG1;ANA;111.222.333-44;a@cvc.com;GRP1;A\n"
            ";SEM LOGIN;000;b@b.com;GRP2;A\n"   # usuario vazio -> ignorado
        )
        Path(cls.arq).write_text(conteudo, encoding="utf-8")
        leitor = LeitorSistema(CONFIGS_SISTEMAS[Sistema.SYSTUR])
        cls.perfis = {p.usuario: p for p in leitor.ler_um(Path(cls.arq))}

    def test_csv_lido_com_separador_ponto_e_virgula(self):
        self.assertEqual(set(self.perfis), {"LOG1"})

    def test_systur_mapeia_perfil_e_situacao(self):
        p = self.perfis["LOG1"]
        self.assertEqual(p.sistema, Sistema.SYSTUR)
        self.assertEqual(p.perfil, "GRP1")
        self.assertEqual(p.situacao, "ATIVO")
        self.assertEqual(p.cpf, "11122233344")


class TestLeitorMatrizIC(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_leit_mat_")
        self.pasta = os.path.join(self._tmp, "in")
        self.proc = os.path.join(self._tmp, "proc")
        self.err = os.path.join(self._tmp, "err")
        os.makedirs(self.pasta)
        # filename precisa conter 'IC Integrador Contabil' p/ deteccao do sistema
        self.arq = os.path.join(self.pasta, "Matriz de Perfil de Acesso - IC Integrador Contabil.xlsx")
        _xlsx(self.arq,
              ["ACESSO MANUAL ", "CARGO", "CCUSTO", "ÁREA", "PERFIL ACESSO"],
              [
                  ["NAO", "ANALISTA", "100", "B2B", "IC CONSULTA"],
                  ["SIM", "GERENTE",  "200", "B2C", "IC APROVADOR"],
              ])

    def _ler(self, escopo):
        leitor = LeitorMatrizPerfis(pasta_processados=self.proc, pasta_erros=self.err)
        return leitor.ler(self.pasta, sistemas_em_escopo=escopo)

    def test_le_matriz_ic_com_ccusto_cargo_perfil_e_manual(self):
        perfis, processados = self._ler({Sistema.IC_INTEGRADOR_CONTABIL})
        self.assertEqual(len(perfis), 2)
        por_perfil = {p.perfil: p for p in perfis}
        self.assertEqual(set(por_perfil), {"IC CONSULTA", "IC APROVADOR"})
        # CCUSTO vira cargo_codigo; CARGO vira cargo_descricao
        self.assertEqual(por_perfil["IC CONSULTA"].cargo_codigo, "100")
        self.assertEqual(por_perfil["IC CONSULTA"].cargo_descricao, "ANALISTA")
        self.assertEqual(por_perfil["IC CONSULTA"].sistema, Sistema.IC_INTEGRADOR_CONTABIL)
        # ACESSO MANUAL: 'SIM' -> True, 'NAO' -> False
        self.assertFalse(por_perfil["IC CONSULTA"].acesso_manual)
        self.assertTrue(por_perfil["IC APROVADOR"].acesso_manual)
        self.assertIn(Path(self.arq).name, processados)

    def test_fora_de_escopo_e_ignorada_sem_processar(self):
        # se o IC nao esta no escopo, a matriz e' ignorada em silencio
        perfis, processados = self._ler({Sistema.SYSTUR})
        self.assertEqual(perfis, [])
        self.assertEqual(processados, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
