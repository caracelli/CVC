# -*- coding: utf-8 -*-
"""Robustez dos leitores: BOM, encoding, skiprows, linhas malformadas,
ordenacao por data no nome, parsing de data e dedup do substituir_sistema.
"""
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.leitores_arquivos.leitor_sistema import (
    LeitorSistema, chave_data_arquivo, _parse_data, _parse_datetime,
)
from infraestrutura.leitores_arquivos.configs_sistemas import (
    ConfigLeitorSistema, CONFIGS_SISTEMAS,
)
from infraestrutura.repositorios.repositorio_acesso_sqlite import RepositorioAcessoSqlite
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from dominio.entidades.perfil_acesso import PerfilAcesso
from dominio.objetos_valor.sistema import Sistema

IC = Sistema.IC_INTEGRADOR_CONTABIL
HEADER_SYSTUR = "CD_LOGIN;NM_PESSOA;CPF / CNPJ;EMAIL;CD_GRUPO_SIGLA;S"


def _cfg_systur():
    return CONFIGS_SISTEMAS[Sistema.SYSTUR]


class TestLeitorEncodingBom(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_enc_")

    def _arq(self, nome, conteudo, encoding):
        p = Path(self._tmp) / nome
        p.write_text(conteudo, encoding=encoding)
        return p

    def test_bom_no_cabecalho_e_removido(self):
        # utf-8-sig escreve BOM; a 1a coluna viria 'CD_LOGIN' com BOM colado
        p = self._arq("bom.csv", HEADER_SYSTUR + "\nLOG1;ANA;1;a@x;G1;A\n", "utf-8-sig")
        perfis = LeitorSistema(_cfg_systur()).ler_um(p)
        self.assertEqual([x.usuario for x in perfis], ["LOG1"])
        self.assertEqual(perfis[0].perfil, "G1")

    def test_utf8_decodifica_acento_no_nome(self):
        p = self._arq("utf8.csv", HEADER_SYSTUR + "\nLOG1;JOSÉ DA SILVA;1;a@x;G1;A\n", "utf-8")
        perfis = LeitorSistema(_cfg_systur()).ler_um(p)
        self.assertEqual(perfis[0].nome_usuario, "JOSÉ DA SILVA")

    def test_latin1_le_campos_ascii_sem_crash(self):
        # arquivo legado em latin-1: campos ASCII (login/perfil) devem sair certos
        conteudo = HEADER_SYSTUR + "\nLOG9;JOÃO ÇÉDULA;1;a@x;G9;A\n" * 1
        p = self._arq("latin.csv", conteudo, "latin-1")
        perfis = LeitorSistema(_cfg_systur()).ler_um(p)
        self.assertEqual(perfis[0].usuario, "LOG9")
        self.assertEqual(perfis[0].perfil, "G9")


class TestLeitorSkiprowsMalformado(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_skip_")

    def _arq(self, nome, conteudo):
        p = Path(self._tmp) / nome
        p.write_text(conteudo, encoding="utf-8")
        return p

    def test_skiprows_pula_cabecalho_de_relatorio(self):
        cfg = ConfigLeitorSistema(
            sistema=Sistema.SYSTUR, skiprows=2,
            colunas={"usuario": "LOGIN", "perfil": "PERFIL", "situacao": "ST"},
            separador=";")
        p = self._arq("rep.csv",
                      "titulo do relatorio\ngerado em 30/04\nLOGIN;PERFIL;ST\nu1;P1;A\nu2;P2;A\n")
        perfis = LeitorSistema(cfg).ler_um(p)
        self.assertEqual({x.usuario for x in perfis}, {"u1", "u2"})
        self.assertEqual(perfis[0].situacao, "ATIVO")

    def test_linha_malformada_e_ignorada(self):
        # on_bad_lines='skip': linha com colunas DEMAIS e' pulada, resto fica
        conteudo = (HEADER_SYSTUR
                    + "\nu1;N;1;e@x;G1;A"
                    + "\nuBAD;N;1;e@x;G1;A;EXTRA;MAIS"   # campos a mais -> skip
                    + "\nu2;N;2;e@x;G2;A\n")
        p = self._arq("bad.csv", conteudo)
        perfis = LeitorSistema(_cfg_systur()).ler_um(p)
        self.assertEqual({x.usuario for x in perfis}, {"u1", "u2"})


class TestOrdenacaoEParsingData(unittest.TestCase):
    def test_chave_data_arquivo_formatos(self):
        self.assertEqual(chave_data_arquivo("SICA_30_04_2026.csv"), (2026, 4, 30, 0, 0))
        self.assertEqual(chave_data_arquivo("rel_30_04.xlsx"), (0, 4, 30, 0, 0))
        self.assertEqual(chave_data_arquivo("x_30_04_2026_10-30.csv"), (2026, 4, 30, 10, 30))
        self.assertEqual(chave_data_arquivo("sem_data.csv"), (0, 0, 0, 0, 0))

    def test_listar_ordenado_por_data_no_nome(self):
        tmp = tempfile.mkdtemp(prefix="cvc_ord_")
        for nome in ["x_30_04_2026_10-30.csv", "sem_data.csv",
                     "SICA_30_04_2026.csv", "rel_30_04.csv"]:
            (Path(tmp) / nome).write_text("x", encoding="utf-8")
        ordenados = [p.name for p in LeitorSistema(_cfg_systur()).listar_ordenado(tmp)]
        self.assertEqual(ordenados, [
            "sem_data.csv", "rel_30_04.csv",
            "SICA_30_04_2026.csv", "x_30_04_2026_10-30.csv",
        ])

    def test_parse_data(self):
        self.assertEqual(_parse_data("01/02/2026"), date(2026, 2, 1))
        self.assertEqual(_parse_data("2026-02-01"), date(2026, 2, 1))
        self.assertIsNone(_parse_data(""))
        self.assertIsNone(_parse_data("lixo"))

    def test_parse_datetime_dayfirst(self):
        dt = _parse_datetime("01/02/2026 10:30")
        self.assertEqual((dt.year, dt.month, dt.day), (2026, 2, 1))
        self.assertIsNone(_parse_datetime(""))


class TestListarIgnoraSubpastas(unittest.TestCase):
    def test_listar_arquivos_ignora_processados_e_erros(self):
        tmp = tempfile.mkdtemp(prefix="cvc_lst_")
        (Path(tmp) / "cur.csv").write_text("x", encoding="utf-8")
        for sub in ("PROCESSADOS", "ERROS"):
            d = Path(tmp) / sub
            d.mkdir()
            (d / "old.csv").write_text("x", encoding="utf-8")
        nomes = [p.name for p in LeitorSistema(_cfg_systur()).listar_arquivos(tmp)]
        self.assertEqual(nomes, ["cur.csv"])


class TestDedupSubstituirSistema(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_dedup_")
        self.conexao = ConexaoBancoDados(os.path.join(self._tmp, "d.db"))
        self.conexao.inicializar()
        self.repo = RepositorioAcessoSqlite(self.conexao)

    def _p(self, usuario, perfil, situacao):
        return PerfilAcesso(usuario=usuario, nome_usuario="N", sistema=IC,
                            perfil=perfil, situacao=situacao)

    def test_trio_duplicado_mantem_o_ultimo(self):
        n = self.repo.substituir_sistema(IC, [
            self._p("u1", "P1", "ATIVO"),
            self._p("u1", "P1", "INATIVO"),   # mesmo (sistema,usuario,perfil) -> ultimo vence
            self._p("u1", "P2", "ATIVO"),     # perfil diferente -> linha propria
        ])
        self.assertEqual(n, 2)
        acessos = {(a.usuario, a.perfil): a for a in self.repo.obter_por_sistema(IC)}
        self.assertEqual(acessos[("u1", "P1")].situacao, "INATIVO")
        self.assertIn(("u1", "P2"), acessos)

    def test_substituir_remove_importacao_anterior(self):
        self.repo.substituir_sistema(IC, [self._p("u1", "P1", "ATIVO")])
        self.repo.substituir_sistema(IC, [self._p("u2", "P9", "ATIVO")])
        acessos = self.repo.obter_por_sistema(IC)
        self.assertEqual([(a.usuario, a.perfil) for a in acessos], [("u2", "P9")])


if __name__ == "__main__":
    unittest.main(verbosity=2)
