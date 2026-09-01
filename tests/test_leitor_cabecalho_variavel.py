# -*- coding: utf-8 -*-
"""O MESMO sistema chegando em layouts diferentes.

O SICA_RA provou o problema na pratica: em 30/04 veio como relatorio
(';', 4 linhas de preambulo, colunas 'Nome'/'Grupo'/'Status') e em 01/09 como
dump da tabela (',', cabecalho na 1a linha, colunas 'User-Name'/'grupo'/
'ustatus'). Com skiprows e separador fixos no config, o segundo lia ZERO
acesso em silencio.

Aqui esta' provado que a linha do cabecalho e o separador sao LOCALIZADOS a
partir dos nomes de coluna esperados, que o nome casa em forma canonica
(acento/caixa/BOM/mojibake) e que os layouts que ja funcionavam continuam
identicos.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import openpyxl

from infraestrutura.leitores_arquivos.leitor_base import (
    ler_tabela, normalizar_nome_coluna,
)
from infraestrutura.leitores_arquivos.leitor_sistema import (
    LeitorSistema, _parse_datetime,
)
from infraestrutura.leitores_arquivos.configs_sistemas import CONFIGS_SISTEMAS
from dominio.objetos_valor.sistema import Sistema

# --- os dois layouts REAIS do SICA_RA, com os mesmos 2 usuarios -------------

PREAMBULO = [
    "                           Planilha de Usuarios: A",
    "30/04/26;Relatorio de Usuarios",
    "",
]
HDR_RELATORIO = ("Usuario;Data de Criaçăo;Nome;CPF;ADM;CfAut;CancFat;E-mail;"
                 "Ultimo Acesso;Expiracao;#LOG;Filial;Padrao;Grupo;SU;Status")
LIN_RELATORIO = [
    "anabello;13/11/23;ANA CAROLINE JARDIM BELLO;39328XXX;S;S;S;"
    "ana.bello@cvccorp.com.br;30/04/2026 07:37:04,853-03:00;"
    "21/06/2026 00:00:00,000-03:00;5;SAO;Sim;POS FAT ESFERA;N;Ativo",
    "brunasilva;29/05/24;BRUNA OLIVEIRA FERREIRA;33259XXX;S;S;S;"
    "bruna.silva@cvccorp.com.br;29/04/2026 08:02:24,556-03:00;"
    "24/05/2026 00:00:00,000-03:00;2;SAO;Sim;POS FAT TERRESTE;N;Ativo",
]

HDR_DUMP = ('"usuario","Create_date","User-Name","Description","confaut",'
            '"Last_login","filial","padrao","grupo","superuser","ustatus",'
            '"adm","email","login"')
LIN_DUMP = [
    'anabello,"2023-11-13 09:00:00:000 - 03:00",ANA CAROLINE JARDIM BELLO,'
    '"39328XXXXX1",S,"2026-04-30 07:37:04:853 - 03:00","",1,POS FAT ESFERA,'
    '0,Ativo,S,ana.bello@cvccorp.com.br,2',
    'brunasilva,"2024-05-29 09:00:00:000 - 03:00",BRUNA OLIVEIRA FERREIRA,'
    '"33259XXXXX7",S,"2026-04-29 08:02:24:556 - 03:00","",1,POS FAT TERRESTE,'
    '0,Inativo,S,bruna.silva@cvccorp.com.br,2',
]


def _escrever(pasta, nome, linhas, encoding="utf-8"):
    p = Path(pasta) / nome
    p.write_text("\n".join(linhas) + "\n", encoding=encoding)
    return p


class TestSicaRaDoisLayouts(unittest.TestCase):
    """O caso que originou a mudanca, com o config de producao."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_hdr_")
        self._leitor = LeitorSistema(CONFIGS_SISTEMAS[Sistema.SICA_RA])

    def test_relatorio_com_preambulo(self):
        p = _escrever(self._tmp, "sica_relatorio.csv",
                      PREAMBULO + [HDR_RELATORIO] + LIN_RELATORIO)
        ps = self._leitor.ler_um(p)
        self.assertEqual(len(ps), 2)
        self.assertEqual(ps[0].usuario, "anabello")
        self.assertEqual(ps[0].perfil, "POS FAT ESFERA")
        self.assertEqual(ps[0].situacao, "ATIVO")
        self.assertEqual(ps[0].cpf, "39328XXX")
        self.assertEqual(ps[0].email, "ana.bello@cvccorp.com.br")
        self.assertIsNotNone(ps[0].ultimo_acesso)

    def test_dump_da_tabela(self):
        """Mesma informacao, outro layout: nomes de coluna diferentes,
        virgula em vez de ';' e cabecalho na 1a linha."""
        p = _escrever(self._tmp, "sicara 1.csv", [HDR_DUMP] + LIN_DUMP)
        ps = self._leitor.ler_um(p)
        self.assertEqual(len(ps), 2)
        self.assertEqual(ps[0].usuario, "anabello")
        self.assertEqual(ps[0].nome_usuario, "ANA CAROLINE JARDIM BELLO")
        self.assertEqual(ps[0].perfil, "POS FAT ESFERA")
        self.assertEqual(ps[0].email, "ana.bello@cvccorp.com.br")

    def test_os_dois_layouts_produzem_o_mesmo_acesso(self):
        a = self._leitor.ler_um(_escrever(
            self._tmp, "a.csv", PREAMBULO + [HDR_RELATORIO] + LIN_RELATORIO))
        b = self._leitor.ler_um(_escrever(
            self._tmp, "b.csv", [HDR_DUMP] + LIN_DUMP))
        self.assertEqual(len(a), len(b))
        for x, y in zip(a, b):
            self.assertEqual(x.usuario, y.usuario)
            self.assertEqual(x.nome_usuario, y.nome_usuario)
            self.assertEqual(x.perfil, y.perfil)
            self.assertEqual(x.email, y.email)
            # o ultimo acesso e' a MESMA hora escrita de dois jeitos
            self.assertEqual(x.ultimo_acesso, y.ultimo_acesso)

    def test_status_inativo_e_bloqueado_chegam_do_dump(self):
        """O dump traz conta morta; o relatorio antigo so' trazia ativa.
        Se o status se perdesse, conta inativa entraria como acesso vivo."""
        extra = ('x1,"2024-01-01 09:00:00:000 - 03:00",FULANO,"11111XXXXX1",S,'
                 '"2026-01-01 09:00:00:000 - 03:00","",1,GRUPO X,0,Bloqueado,S,'
                 'fulano@cvccorp.com.br,2')
        p = _escrever(self._tmp, "st.csv", [HDR_DUMP] + LIN_DUMP + [extra])
        situacoes = {x.usuario: x.situacao for x in self._leitor.ler_um(p)}
        self.assertEqual(situacoes["anabello"], "ATIVO")
        self.assertEqual(situacoes["brunasilva"], "INATIVO")
        self.assertEqual(situacoes["x1"], "BLOQUEADO")

    def test_cpf_mascarado_dos_dois_jeitos_da_o_mesmo_parcial(self):
        from dominio.servicos_dominio.servico_vinculacao_multi_chave import (
            extrair_cpf_parcial,
        )
        a = self._leitor.ler_um(_escrever(
            self._tmp, "c1.csv", PREAMBULO + [HDR_RELATORIO] + LIN_RELATORIO))
        b = self._leitor.ler_um(_escrever(
            self._tmp, "c2.csv", [HDR_DUMP] + LIN_DUMP))
        # '39328XXX' e '39328XXXXX1' -> mesma chave parcial de vinculacao
        self.assertEqual(extrair_cpf_parcial(a[0].cpf), "39328")
        self.assertEqual(extrair_cpf_parcial(b[0].cpf), "39328")


class TestCabecalhoEmQualquerLinha(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_hdr2_")
        self._leitor = LeitorSistema(CONFIGS_SISTEMAS[Sistema.SICA_RA])

    def test_preambulo_de_qualquer_tamanho(self):
        """O config aponta 4 linhas; o arquivo pode vir com 0, 2 ou 9."""
        for n in (0, 2, 4, 9):
            with self.subTest(preambulo=n):
                linhas = ["relatorio;linha de titulo"] * n
                p = _escrever(self._tmp, "pre%d.csv" % n,
                              linhas + [HDR_RELATORIO] + LIN_RELATORIO)
                ps = self._leitor.ler_um(p)
                self.assertEqual(len(ps), 2, "preambulo de %d linhas" % n)
                self.assertEqual(ps[0].usuario, "anabello")

    def test_separador_tab(self):
        p = _escrever(self._tmp, "tab.csv",
                      [HDR_RELATORIO.replace(";", "\t")]
                      + [l.replace(";", "\t") for l in LIN_RELATORIO])
        ps = self._leitor.ler_um(p)
        self.assertEqual(len(ps), 2)
        self.assertEqual(ps[0].perfil, "POS FAT ESFERA")

    def test_cabecalho_em_caixa_e_acento_diferentes(self):
        """So' o que muda de PALAVRA precisa de alias; caixa e acento nao."""
        hdr = HDR_RELATORIO.upper().replace("DATA DE CRIAÇĂO", "Data de Criação")
        p = _escrever(self._tmp, "caixa.csv",
                      PREAMBULO + [hdr] + LIN_RELATORIO)
        ps = self._leitor.ler_um(p)
        self.assertEqual(len(ps), 2)
        self.assertEqual(ps[0].perfil, "POS FAT ESFERA")
        self.assertIsNotNone(ps[0].data_criacao)

    def test_bom_no_primeiro_nome_de_coluna(self):
        p = _escrever(self._tmp, "bom.csv", [HDR_DUMP] + LIN_DUMP,
                      encoding="utf-8-sig")
        ps = self._leitor.ler_um(p)
        self.assertEqual(len(ps), 2)
        self.assertEqual(ps[0].usuario, "anabello")

    def test_xlsx_com_titulo_antes_do_cabecalho(self):
        p = Path(self._tmp) / "sica.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Relatorio de Usuarios"])
        ws.append([])
        ws.append(HDR_RELATORIO.split(";"))
        for l in LIN_RELATORIO:
            ws.append(l.split(";"))
        wb.save(p)
        ps = self._leitor.ler_um(p)
        self.assertEqual(len(ps), 2)
        self.assertEqual(ps[0].usuario, "anabello")

    def test_arquivo_irreconhecivel_nao_explode(self):
        """Nenhuma coluna esperada -> cai no skiprows do config e devolve
        vazio, sem excecao (o arquivo vai para ERROS pelo caso de uso)."""
        p = _escrever(self._tmp, "outro.csv",
                      ["a;b;c", "1;2;3", "4;5;6", "7;8;9", "10;11;12"])
        self.assertEqual(self._leitor.ler_um(p), [])


class TestNomeCanonicoDeColuna(unittest.TestCase):

    def test_acento_caixa_espaco_e_bom_colapsam(self):
        for a, b in [
            ("Data de Criação", "DATA DE CRIACAO"),
            ("Data de Criaçăo", "DATA DE CRIACAO"),     # mojibake do extrato
            ("  Ultimo  Acesso ", "ULTIMO ACESSO"),
            ("﻿usuario", "USUARIO"),
            ('"grupo"', "GRUPO"),
        ]:
            with self.subTest(nome=a):
                self.assertEqual(normalizar_nome_coluna(a), b)

    def test_nomes_distintos_nao_colidem(self):
        self.assertNotEqual(normalizar_nome_coluna("USUÁRIO"),
                            normalizar_nome_coluna("NM_USUÁRIO"))
        self.assertNotEqual(normalizar_nome_coluna("E-mail"),
                            normalizar_nome_coluna("email"))


class TestTimestampVariavel(unittest.TestCase):
    """O ultimo acesso se perdia em 86% das linhas do dump de 01/09."""

    def test_milissegundo_com_dois_pontos_e_fuso_com_espaco(self):
        d = _parse_datetime("2026-03-27 12:16:39:165 - 03:00")
        self.assertIsNotNone(d)
        self.assertEqual((d.year, d.month, d.day, d.hour, d.minute),
                         (2026, 3, 27, 12, 16))

    def test_formato_antigo_continua(self):
        d = _parse_datetime("30/04/2026 07:37:04,853-03:00")
        self.assertIsNotNone(d)
        self.assertEqual((d.year, d.month, d.day, d.hour), (2026, 4, 30, 7))

    def test_a_mesma_hora_nos_dois_formatos_e_igual(self):
        self.assertEqual(_parse_datetime("30/04/2026 07:37:04,853-03:00"),
                         _parse_datetime("2026-04-30 07:37:04:853 - 03:00"))

    def test_vazio_e_lixo_viram_none(self):
        for v in ("", "   ", "nan", None, "sem data"):
            with self.subTest(valor=v):
                self.assertIsNone(_parse_datetime(v))


class TestSemRegressaoNosDemaisSistemas(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_hdr3_")

    def test_systur_cabecalho_na_primeira_linha(self):
        p = _escrever(self._tmp, "systur.csv", [
            "CD_LOGIN;NM_PESSOA;CPF / CNPJ;EMAIL;CD_GRUPO_SIGLA;S",
            "u1;FULANO DE TAL;12345678900;f@cvc.com.br;ATEND_PUBLIC;A",
        ])
        ps = LeitorSistema(CONFIGS_SISTEMAS[Sistema.SYSTUR]).ler_um(p)
        self.assertEqual(len(ps), 1)
        self.assertEqual(ps[0].perfil, "ATEND_PUBLIC")
        self.assertEqual(ps[0].situacao, "ATIVO")

    def test_sigot_despivot_continua_com_grupos_repetidos(self):
        """Despivot passou a casar o nome em forma canonica; os blocos
        Grupo/Grupo.1 tem de continuar virando um acesso cada."""
        p = _escrever(self._tmp, "sigot.csv", [
            "linha de titulo 1", "linha de titulo 2",
            "Usuario;Nome;CPF;E-mail;Filial;Grupo;Filial;Grupo;Status do Usuário",
            "u9;FULANO;12345678900;f@cvc.com.br;SAO;GRUPO A;SAO;GRUPO B;Ativo",
        ], encoding="cp1252")
        ps = LeitorSistema(CONFIGS_SISTEMAS[Sistema.SIGOT]).ler_um(p)
        self.assertEqual(sorted(x.perfil for x in ps), ["GRUPO A", "GRUPO B"])

    def test_ic_largura_fixa_continua(self):
        """Sem delimitador no cabecalho o arquivo e' de largura fixa —
        a deteccao nao pode roubar esse caminho."""
        p = _escrever(self._tmp, "ic.csv", [
            "CD_LOGIN   NM_PESSOA        CPF          CD_EMAIL      NM_GRUPO   S",
            "u5         FULANO DE TAL    12345678900  f@cvc.com.br  CONTABIL   A",
        ])
        cfg = CONFIGS_SISTEMAS[Sistema.IC_INTEGRADOR_CONTABIL]
        df = ler_tabela(p, dtype=str, colunas_esperadas=list(cfg.colunas.values()))
        self.assertIn("CD_LOGIN", [str(c) for c in df.columns])
        self.assertEqual(len(df), 1)


if __name__ == "__main__":
    unittest.main()


class TestOrdemComExtratoCumulativo(unittest.TestCase):
    """O extrato do SICA_RA e' CUMULATIVO e a importacao e' SNAPSHOT
    (substituir_sistema): vale o ULTIMO arquivo da fila. Arquivo sem data no
    nome ia para o INICIO — o dump novo era sobrescrito pelo relatorio velho
    em silencio, e o painel terminava com a foto de abril."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_ord_")
        self._leitor = LeitorSistema(CONFIGS_SISTEMAS[Sistema.SICA_RA])

    def _com_mtime(self, nome, linhas, quando):
        import os
        import time
        p = _escrever(self._tmp, nome, linhas)
        t = time.mktime(quando.timetuple())
        os.utime(p, (t, t))
        return p

    def test_sem_data_no_nome_usa_a_data_de_modificacao(self):
        from datetime import datetime as dt
        self._com_mtime("SICA_RA_30_04.csv",
                        PREAMBULO + [HDR_RELATORIO] + LIN_RELATORIO,
                        dt(2026, 4, 30, 10, 0))
        self._com_mtime("sicara 1.csv", [HDR_DUMP] + LIN_DUMP,
                        dt(2026, 9, 1, 14, 38))
        ordem = [p.name for p in self._leitor.listar_ordenado(self._tmp)]
        self.assertEqual(ordem[-1], "sicara 1.csv",
                         "o mais novo tem de ser o ULTIMO a importar")

    def test_data_no_nome_continua_mandando(self):
        from datetime import datetime as dt
        # mtime invertido de proposito: o nome vence
        self._com_mtime("SICA_RA_01_09_2026.csv", [HDR_DUMP] + LIN_DUMP,
                        dt(2020, 1, 1, 0, 0))
        self._com_mtime("SICA_RA_30_04_2026.csv",
                        PREAMBULO + [HDR_RELATORIO] + LIN_RELATORIO,
                        dt(2026, 12, 31, 0, 0))
        ordem = [p.name for p in self._leitor.listar_ordenado(self._tmp)]
        self.assertEqual(ordem, ["SICA_RA_30_04_2026.csv", "SICA_RA_01_09_2026.csv"])

    def test_conta_inativa_do_cumulativo_nao_e_acesso_efetivo(self):
        """O cumulativo traz a conta morta junto. Ela entra no banco, mas
        situacao_conta ja a tira de toda regra — nao vira acesso vivo."""
        from dominio.objetos_valor import situacao_conta
        ps = self._leitor.ler_um(_escrever(
            self._tmp, "cum.csv", [HDR_DUMP] + LIN_DUMP))
        viva = [p for p in ps if situacao_conta.conta_ativa(p.situacao)]
        self.assertEqual([p.usuario for p in viva], ["anabello"])
