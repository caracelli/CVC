# -*- coding: utf-8 -*-
"""Testes do LeitorSig (despivot do extrato matricial + de-para de codigos)
e LeitorCatalogoSig (de-para ID -> NM_ROLE).
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dominio.objetos_valor.sistema import Sistema
from infraestrutura.leitores_arquivos.leitor_sig import (
    LeitorCatalogoSig, LeitorSig,
)


def _criar_xlsx(linhas):
    """Cria XLSX temporario com as linhas dadas. Devolve caminho."""
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp.close()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Select tb_sys_sec_user"  # nome dinamico — leitor deve ignorar
    for linha in linhas:
        ws.append(linha)
    wb.save(tmp.name)
    wb.close()
    return Path(tmp.name)


class TestLeitorCatalogoSig(unittest.TestCase):
    def setUp(self):
        self.leitor = LeitorCatalogoSig()

    def _depara_xlsx(self, linhas):
        return _criar_xlsx(linhas)

    def test_le_de_para_basico(self):
        arq = self._depara_xlsx([
            ["ID", "NM_ROLE"],
            [1, "SIG_ADM"],
            [10, "DIRECAO"],
            [55106, "ACESSO_HOTEL_NAC_RESERVAS_EM_TRANSITO"],
        ])
        try:
            mapa = self.leitor.ler(arq)
            self.assertEqual(mapa["1"], "SIG_ADM")
            self.assertEqual(mapa["10"], "DIRECAO")
            self.assertEqual(mapa["55106"], "ACESSO_HOTEL_NAC_RESERVAS_EM_TRANSITO")
            self.assertEqual(len(mapa), 3)
        finally:
            os.unlink(arq)

    def test_codigo_numerico_vira_string_sem_ponto_zero(self):
        # Excel as vezes le numeros como float ('15.0')
        arq = self._depara_xlsx([["ID", "NM_ROLE"], [15.0, "PERFIL_X"]])
        try:
            mapa = self.leitor.ler(arq)
            self.assertIn("15", mapa)
            self.assertNotIn("15.0", mapa)
        finally:
            os.unlink(arq)

    def test_le_primeira_aba_mesmo_que_nome_seja_outro(self):
        # Garante que nome de aba nao importa (so a primeira)
        tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
        tmp.close()
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "QualquerNomeNovoDaQuery"
        ws.append(["ID", "NM_ROLE"])
        ws.append([1, "TESTE"])
        wb.save(tmp.name)
        wb.close()
        try:
            mapa = self.leitor.ler(Path(tmp.name))
            self.assertEqual(mapa["1"], "TESTE")
        finally:
            os.unlink(tmp.name)


class TestLeitorSig(unittest.TestCase):
    def setUp(self):
        self.catalogo = {
            "10": "DIRECAO",
            "12": "GERENCIA_GERAL",
            "15": "PERFIL_AUX",
            "55106": "ACESSO_HOTEL_NAC_RESERVAS",
        }
        self.leitor = LeitorSig(catalogo=self.catalogo)

    def _extrato_xlsx(self, linhas):
        return _criar_xlsx(linhas)

    def test_despivot_basico(self):
        # 2 usuarios x 3 codigos
        arq = self._extrato_xlsx([
            ["LOGIN", "NM_USER", "STATUS", "CPF", "EMAIL", "10", "12", "15"],
            ["john", "JOHN", "ATIVO", "123.456.789-00", "j@x", "X", "",  "X"],
            ["mary", "MARY", "ATIVO", "98765432100",    "m@x", "",  "X", "X"],
        ])
        try:
            perfis = self.leitor.ler_um(arq)
            self.assertEqual(len(perfis), 4)  # john 2 + mary 2
            # john: DIRECAO + PERFIL_AUX
            johns = [p for p in perfis if p.usuario == "john"]
            self.assertEqual(len(johns), 2)
            self.assertEqual({p.perfil for p in johns}, {"DIRECAO", "PERFIL_AUX"})
            # nome normalizado
            self.assertEqual(johns[0].nome_usuario, "JOHN")
            # CPF formatado normalizado pra 11 dig
            self.assertEqual(johns[0].cpf, "12345678900")
            self.assertEqual(johns[0].email, "j@x")
            self.assertEqual(johns[0].sistema, Sistema.SIG)
        finally:
            os.unlink(arq)

    def test_codigo_sem_traducao_usa_fallback(self):
        arq = self._extrato_xlsx([
            ["LOGIN", "NM_USER", "STATUS", "CPF", "EMAIL", "9999"],
            ["x", "X", "ATIVO", "111", "", "X"],
        ])
        try:
            perfis = self.leitor.ler_um(arq)
            self.assertEqual(len(perfis), 1)
            # codigo nao tem no catalogo -> usa codigo cru como fallback
            self.assertEqual(perfis[0].perfil, "9999")
        finally:
            os.unlink(arq)

    def test_linha_sem_login_e_ignorada(self):
        arq = self._extrato_xlsx([
            ["LOGIN", "NM_USER", "STATUS", "CPF", "EMAIL", "10"],
            ["", "FANTASMA", "ATIVO", "", "", "X"],
            ["x", "X", "ATIVO", "111", "", "X"],
        ])
        try:
            perfis = self.leitor.ler_um(arq)
            self.assertEqual(len(perfis), 1)
            self.assertEqual(perfis[0].usuario, "x")
        finally:
            os.unlink(arq)

    def test_celula_vazia_nao_gera_acesso(self):
        # Confirmacao explicita: so 'X' (e variantes) geram acesso
        arq = self._extrato_xlsx([
            ["LOGIN", "NM_USER", "STATUS", "CPF", "EMAIL", "10", "12", "15"],
            ["x", "X", "ATIVO", "1", "", "", None, "0"],
        ])
        try:
            perfis = self.leitor.ler_um(arq)
            self.assertEqual(len(perfis), 0)
        finally:
            os.unlink(arq)

    def test_status_bloqueado_preservado(self):
        # Conta BLOQUEADO nao pode virar ATIVO (bug: ~90% do SIG e' bloqueado).
        arq = self._extrato_xlsx([
            ["LOGIN", "NM_USER", "STATUS", "CPF", "EMAIL", "10", "12"],
            ["ativo1", "A", "ATIVO", "1", "", "X", ""],
            ["bloq1", "B", "BLOQUEADO", "2", "", "X", "X"],
        ])
        try:
            perfis = self.leitor.ler_um(arq)
            sit = {p.usuario: p.situacao for p in perfis}
            self.assertEqual(sit["ativo1"], "ATIVO")
            self.assertEqual(sit["bloq1"], "BLOQUEADO")
        finally:
            os.unlink(arq)

    def test_aceita_marcadores_alternativos(self):
        # X, x, 1, SIM tambem marcam
        arq = self._extrato_xlsx([
            ["LOGIN", "NM_USER", "STATUS", "CPF", "EMAIL", "10", "12", "15"],
            ["x", "X", "ATIVO", "1", "", "X", "1", "SIM"],
        ])
        try:
            perfis = self.leitor.ler_um(arq)
            self.assertEqual(len(perfis), 3)
        finally:
            os.unlink(arq)

    def test_sem_coluna_login_quebra_explicitamente(self):
        arq = self._extrato_xlsx([
            ["USUARIO", "NM_USER", "STATUS", "CPF", "EMAIL", "10"],
            ["x", "X", "ATIVO", "1", "", "X"],
        ])
        try:
            with self.assertRaises(ValueError) as ctx:
                self.leitor.ler_um(arq)
            self.assertIn("LOGIN", str(ctx.exception))
        finally:
            os.unlink(arq)


class TestLeitorSigComArquivoReal(unittest.TestCase):
    """Le os arquivos reais de Arquivos_origem (se presentes) — smoke test."""

    def test_extrato_real_e_de_para_real(self):
        origem = Path(__file__).resolve().parent.parent / "Arquivos_origem"
        extrato = origem / "SIG_18.05.26.xlsx"
        de_para = origem / "ID_x_Perfis_SIG 19.08.xlsx"
        if not extrato.exists() or not de_para.exists():
            self.skipTest("arquivos reais nao presentes")

        # Carrega de-para
        catalogo = LeitorCatalogoSig().ler(de_para)
        self.assertEqual(len(catalogo), 399)

        # Le extrato — esperado: 523 usuarios x mediana 88 perfis = ~33k linhas
        perfis = LeitorSig(catalogo=catalogo).ler_um(extrato)
        self.assertGreater(len(perfis), 30000, "esperado ~33k perfis no real")
        # Conferencia de schema
        amostra = perfis[0]
        self.assertEqual(amostra.sistema, Sistema.SIG)
        # Cada perfil traduzido (nao deveria sobrar codigo numerico cru)
        # Como casamento e' 100%, nenhum codigo no cabecalho fica sem nome:
        crus = [p for p in perfis if p.perfil.isdigit()]
        self.assertEqual(len(crus), 0, f"sobraram {len(crus)} perfis sem traducao")


if __name__ == "__main__":
    unittest.main()
