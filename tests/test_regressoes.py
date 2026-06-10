# -*- coding: utf-8 -*-
"""Regressoes de decisoes/comportamentos estabelecidos (guardas).

- Aproximacao de perfil escopada EXATAMENTE ao IC.
- Mapeamento de sistema a partir do texto da matriz CCO.
- Rotulos de acao do GerarSaidas.
- GerarSaidas exclui PERFIL_INVALIDO e ACESSO_DESLIGADO do Excel (decisao 21/05).
"""
import glob
import os
import sys
import tempfile
import unittest
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import warnings

from aplicacao.casos_de_uso.validar_acessos_sistema import _SISTEMAS_PERFIL_APROXIMADO
from aplicacao.casos_de_uso.gerar_saidas import GerarSaidas, _STATUS_LABEL
from infraestrutura.configuracao.leitor_config import LeitorConfig
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.repositorios.repositorio_divergencia_sqlite import RepositorioDivergenciaSqlite
from dominio.entidades.divergencia import Divergencia
from dominio.objetos_valor.sistema import Sistema, sistema_do_texto
from dominio.objetos_valor.tipo_divergencia import TipoDivergencia


class TestAproximacaoEscopoFixo(unittest.TestCase):
    def test_aproximacao_so_no_ic(self):
        # guarda: ninguem deve adicionar SYSTUR/outros a aproximacao sem querer
        self.assertEqual(_SISTEMAS_PERFIL_APROXIMADO, {Sistema.IC_INTEGRADOR_CONTABIL.value})


class TestSistemaDoTexto(unittest.TestCase):
    def test_variantes_da_cco_mapeiam_certo(self):
        casos = {
            "Systur": Sistema.SYSTUR, "SYSTUR": Sistema.SYSTUR,
            "Sigot": Sistema.SIGOT,
            "SICA RA": Sistema.SICA_RA, "Sica RA": Sistema.SICA_RA,
            "SICA ESFERA": Sistema.SICA_ESFERA, "Sica Esfera": Sistema.SICA_ESFERA,
            "SIG": Sistema.SIG,
            "Oracle EBS": Sistema.ORACLE_EBS,
            "Opera Operacional": Sistema.OPERA_OPERACIONAL,
        }
        for texto, esperado in casos.items():
            self.assertEqual(sistema_do_texto(texto), esperado, texto)

    def test_texto_desconhecido_e_vazio_retornam_none(self):
        # a CCO nao referencia IC -> sistema_do_texto('IC') e' None (coberto pela matriz propria)
        self.assertIsNone(sistema_do_texto("IC"))
        self.assertIsNone(sistema_do_texto("Integrador Contabil"))
        self.assertIsNone(sistema_do_texto("xpto"))
        self.assertIsNone(sistema_do_texto(""))


class TestStatusLabel(unittest.TestCase):
    def test_rotulos_de_acao(self):
        self.assertEqual(_STATUS_LABEL["SEM_ACESSO"], "Incluir Acesso")
        self.assertEqual(_STATUS_LABEL["DIVERGENTE"], "Alterar Perfil")
        self.assertEqual(_STATUS_LABEL["EM_ANALISE"], "Em Análise")
        self.assertEqual(_STATUS_LABEL["NAO_MAPEADO"], "Não Mapeado")


class TestGerarSaidasExcluiPerfilInvalido(unittest.TestCase):
    def _div(self, tipo, usuario):
        return Divergencia(id=f"{tipo.value}-{usuario}", tipo=tipo, sistema=Sistema.IC_INTEGRADOR_CONTABIL,
                           usuario=usuario, nome_usuario=usuario, descricao="x")

    def test_excel_nao_traz_perfil_invalido_nem_desligado(self):
        tmp = tempfile.mkdtemp(prefix="cvc_reg_saidas_")
        conexao = ConexaoBancoDados(os.path.join(tmp, "s.db"))
        conexao.inicializar()
        RepositorioDivergenciaSqlite(conexao).salvar_lote([
            self._div(TipoDivergencia.ACESSO_SEM_VINCULO_RH, "u1"),
            self._div(TipoDivergencia.PERFIL_INVALIDO, "u2"),
            self._div(TipoDivergencia.ACESSO_DESLIGADO, "u3"),
        ])
        saidas = os.path.join(tmp, "OUT")
        GerarSaidas(conexao=conexao, pasta_saidas=saidas).executar()

        arqs = glob.glob(os.path.join(saidas, "DIVERGENCIAS_*.xlsx"))
        self.assertEqual(len(arqs), 1)
        wb = openpyxl.load_workbook(arqs[0], read_only=True)
        ws = wb["TODAS"]
        linhas = list(ws.iter_rows(values_only=True))
        wb.close()
        header = list(linhas[0])
        i_tipo = header.index("Tipo")
        tipos = {r[i_tipo] for r in linhas[1:] if r[i_tipo]}
        self.assertIn("ACESSO_SEM_VINCULO_RH", tipos)
        self.assertNotIn("PERFIL_INVALIDO", tipos)
        self.assertNotIn("ACESSO_DESLIGADO", tipos)


class TestConfigSemDeprecationElementTree(unittest.TestCase):
    """Regressao: testar truthiness de Element do ElementTree e' deprecado.
    LeitorConfig deve usar 'is not None' — config com <colunas/> vazio e sem
    <processamento> carrega com defaults e SEM deprecation de truth value."""

    def test_colunas_vazias_e_sem_processamento_sem_warning(self):
        xml = (
            "<configuracao><versao>9.9.9</versao><cliente>T</cliente>"
            "<rede><raiz></raiz></rede>"
            "<sistemas><sistema id='X'><nome>SYSTUR</nome><ativo>true</ativo>"
            "<colunas></colunas></sistema></sistemas>"
            "<visualizador><sistema></sistema></visualizador></configuracao>"
        )
        tmp = tempfile.mkdtemp(prefix="cvc_reg_cfg_")
        p = os.path.join(tmp, "config.xml")
        Path(p).write_text(xml, encoding="utf-8")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            cfg = LeitorConfig(p).carregar()

        self.assertEqual(cfg.versao, "9.9.9")
        self.assertEqual(cfg.encoding_padrao, "utf-8")     # default: sem <processamento>
        self.assertEqual(cfg.sistemas["X"].colunas, {})    # <colunas/> vazio
        truthiness = [str(x.message) for x in w if "truth value" in str(x.message)]
        self.assertEqual(truthiness, [], f"deprecation de truthiness do ET: {truthiness}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
