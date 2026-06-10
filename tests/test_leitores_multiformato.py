# -*- coding: utf-8 -*-
"""Importacao agnostica de formato: gera os MESMOS dados em XLSX, CSV (virgula)
e CSV (ponto-e-virgula) e prova que cada leitor importa identico. Garante que a
unificacao (ler_tabela) cobre o maximo de opcoes sem quebrar os arquivos atuais.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import openpyxl

from infraestrutura.leitores_arquivos.leitor_base import ler_tabela
from infraestrutura.leitores_arquivos.leitor_rh import LeitorRh
from infraestrutura.leitores_arquivos.leitor_matriz import LeitorMatrizPerfis
from dominio.objetos_valor.sistema import Sistema


def _xlsx(path, header, linhas, titulo=None):
    wb = openpyxl.Workbook(); ws = wb.active
    if titulo is not None:
        ws.append([titulo])
    ws.append(list(header))
    for ln in linhas:
        ws.append(list(ln))
    wb.save(path)


def _csv(path, header, linhas, sep, titulo=None):
    out = []
    if titulo is not None:
        out.append(titulo)
    out.append(sep.join(header))
    out += [sep.join(ln) for ln in linhas]
    Path(path).write_text("\n".join(out), encoding="utf-8")


def _gerar_todos(pasta, base, header, linhas, titulo=None):
    """Cria base.xlsx, base_virgula.csv, base_ponto.csv. Devolve os 3 caminhos."""
    p_xlsx = os.path.join(pasta, base + ".xlsx")
    p_csvv = os.path.join(pasta, base + "_virgula.csv")
    p_csvp = os.path.join(pasta, base + "_ponto.csv")
    _xlsx(p_xlsx, header, linhas, titulo)
    _csv(p_csvv, header, linhas, ",", titulo)
    _csv(p_csvp, header, linhas, ";", titulo)
    return [Path(p) for p in (p_xlsx, p_csvv, p_csvp)]


HEADER = ["A", "B", "C"]
LINHAS = [["1", "x", "foo"], ["10", "y", "bar"]]


class TestLerTabelaFormatos(unittest.TestCase):
    """Nivel do helper: xlsx / csv(virgula) / csv(ponto-virgula) / csv(tab)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cvc_mf_helper_")

    def test_formatos_e_separadores_produzem_mesma_tabela(self):
        caminhos = _gerar_todos(self.tmp, "t", HEADER, LINHAS)
        # + um CSV com TAB
        p_tab = os.path.join(self.tmp, "t_tab.csv")
        _csv(p_tab, HEADER, LINHAS, "\t")
        caminhos.append(Path(p_tab))
        for p in caminhos:
            df = ler_tabela(p)
            self.assertEqual(list(df.columns), HEADER, f"colunas divergiram em {p.name}")
            self.assertEqual(df.values.tolist(), LINHAS, f"dados divergiram em {p.name}")

    def test_header_na_segunda_linha(self):
        # titulo fundido na 1a linha; cabecalho real na 2a (estilo matriz org)
        px = os.path.join(self.tmp, "h.xlsx"); _xlsx(px, HEADER, LINHAS, titulo="TITULO")
        pc = os.path.join(self.tmp, "h.csv"); _csv(pc, HEADER, LINHAS, ";", titulo="TITULO")
        for p in (px, pc):
            df = ler_tabela(Path(p), header=1)
            self.assertEqual(list(df.columns), HEADER)
            self.assertEqual(df.values.tolist(), LINHAS)


_RH_HEADER = ["MATRICULA", "NOME", "CPF", "CARGO_CODIGO", "CARGO_DESCRICAO",
              "CENTRO_CUSTO", "DEPARTAMENTO", "DATA_ADMISSAO", "EMAIL", "SITUACAO"]
_RH_LINHAS = [
    ["100", "ANA SILVA", "11111111111", "CG1", "ANALISTA", "CC1", "TI",
     "01/02/2020", "ana@x.com", "Atividade Normal"],
    ["101", "BRUNO LIMA", "22222222222", "CG2", "GERENTE", "CC2", "COM",
     "02/03/2019", "bruno@x.com", "Atividade Normal"],
]


class TestRhMultiformato(unittest.TestCase):

    def _ler_ativos(self, arquivo: Path):
        # cada arquivo numa pasta isolada (ler_ativos move p/ PROCESSADOS)
        base = tempfile.mkdtemp(prefix="cvc_mf_rh_")
        pasta = os.path.join(base, "in"); os.makedirs(pasta)
        destino = os.path.join(pasta, arquivo.name)
        Path(destino).write_bytes(arquivo.read_bytes())
        leitor = LeitorRh(pasta_processados=os.path.join(base, "proc"),
                          pasta_erros=os.path.join(base, "err"))
        ativos, _ = leitor.ler_ativos(pasta)
        return ativos

    def test_clt_importa_igual_em_xlsx_e_csv(self):
        tmp = tempfile.mkdtemp(prefix="cvc_mf_rhgen_")
        for arq in _gerar_todos(tmp, "clt", _RH_HEADER, _RH_LINHAS):
            ativos = self._ler_ativos(arq)
            mats = sorted(a.matricula for a in ativos)
            self.assertEqual(mats, ["100", "101"], f"RH divergiu em {arq.name}")


_MAT_HEADER = ["ACESSO MANUAL ", "CARGO", "CCUSTO", "ÁREA", "PERFIL ACESSO"]
_MAT_LINHAS = [
    ["NAO", "ANALISTA", "100", "B2B", "IC CONSULTA"],
    ["SIM", "GERENTE", "200", "B2C", "IC APROVADOR"],
]


class TestMatrizPerfisMultiformato(unittest.TestCase):

    def _ler(self, arquivo: Path):
        base = tempfile.mkdtemp(prefix="cvc_mf_mat_")
        pasta = os.path.join(base, "in"); os.makedirs(pasta)
        Path(os.path.join(pasta, arquivo.name)).write_bytes(arquivo.read_bytes())
        leitor = LeitorMatrizPerfis(pasta_processados=os.path.join(base, "proc"),
                                    pasta_erros=os.path.join(base, "err"))
        perfis, _ = leitor.ler(pasta, sistemas_em_escopo={Sistema.IC_INTEGRADOR_CONTABIL})
        return perfis

    def test_matriz_importa_igual_em_xlsx_e_csv(self):
        tmp = tempfile.mkdtemp(prefix="cvc_mf_matgen_")
        # nome precisa conter 'IC Integrador Contabil' p/ deteccao do sistema
        for arq in _gerar_todos(tmp, "Matriz - IC Integrador Contabil",
                                _MAT_HEADER, _MAT_LINHAS):
            perfis = self._ler(arq)
            por = {p.perfil for p in perfis}
            self.assertEqual(por, {"IC CONSULTA", "IC APROVADOR"},
                             f"matriz divergiu em {arq.name}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
