# -*- coding: utf-8 -*-
"""O de-para do SIG nao pode depender de vir em TODA entrega.

Retorno da area (25/08/2026): "antes estava vindo os nomes dos perfis do SIG,
agora esta vindo so o codigo". A tela passou a mostrar `100`, `55001` onde antes
mostrava ACESSO_SISTEMA_BACKOFFICE.

Causa: `_carregar_catalogo` lia o de-para SO' do arquivo. A ENTRADA de 05/08 nao
trouxe a pasta DE_PARA, e o catalogo que JA ESTAVA gravado em `catalogo_perfis`
era ignorado — a traducao inteira sumia. O de-para e' tabela de REFERENCIA, nao
extrato diario: uma vez conhecido, continua valendo.

Contrato fixado aqui:
  - arquivo presente  -> manda (substitui o catalogo)
  - arquivo ausente   -> vale o catalogo gravado
  - arquivo ilegivel/vazio -> NAO apaga o catalogo bom
  - nada em lugar nenhum -> codigo cru, e o log diz o que fazer
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from aplicacao.casos_de_uso.importar_sig import ImportarSig
from dominio.objetos_valor.sistema import Sistema
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.repositorios.repositorio_catalogo_perfil import (
    RepositorioCatalogoPerfil,
)


class CatalogoDoSigSobrevive(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cvc_sig_")
        self.conexao = ConexaoBancoDados(os.path.join(self.tmp, "iam.db"))
        self.conexao.inicializar()
        self.repo = RepositorioCatalogoPerfil(self.conexao)
        self.pasta_dp = os.path.join(self.tmp, "DE_PARA")
        self.pasta_ext = os.path.join(self.tmp, "SIG")
        os.makedirs(self.pasta_ext, exist_ok=True)

    def _de_para(self, linhas, nome="ID_x_Perfis_SIG.xlsx"):
        os.makedirs(self.pasta_dp, exist_ok=True)
        wb = openpyxl.Workbook()
        ws = wb.active
        for l in linhas:
            ws.append(l)
        caminho = os.path.join(self.pasta_dp, nome)
        wb.save(caminho)
        wb.close()
        return caminho

    def _importador(self):
        return ImportarSig(
            conexao=self.conexao,
            pasta_extratos=self.pasta_ext,
            pasta_de_para=self.pasta_dp,
            pasta_processados=os.path.join(self.tmp, "PROC"),
            pasta_erros=os.path.join(self.tmp, "ERR"),
        )

    def test_arquivo_presente_alimenta_o_catalogo(self):
        self._de_para([["ID", "NM_ROLE"], [100, "ACESSO_SISTEMA_BACKOFFICE"],
                       [55001, "ATD_HOTEIS_NACIONAIS"]])
        mapa = self._importador()._carregar_catalogo()
        self.assertEqual(mapa.get("100"), "ACESSO_SISTEMA_BACKOFFICE")
        self.assertEqual(self.repo.obter_mapa(Sistema.SIG).get("55001"),
                         "ATD_HOTEIS_NACIONAIS")

    def test_entrega_sem_de_para_mantem_os_nomes(self):
        """O caso do retorno: uma entrega sem a pasta DE_PARA."""
        self._de_para([["ID", "NM_ROLE"], [100, "ACESSO_SISTEMA_BACKOFFICE"]])
        self._importador()._carregar_catalogo()          # 1a rodada: com arquivo
        for f in Path(self.pasta_dp).glob("*.xlsx"):     # a entrega seguinte
            f.unlink()                                   # nao traz o de-para
        mapa = self._importador()._carregar_catalogo()
        self.assertEqual(mapa.get("100"), "ACESSO_SISTEMA_BACKOFFICE",
                         "sem o de-para na entrega, os nomes do SIG sumiram")

    def test_pasta_de_para_inexistente_tambem_usa_o_gravado(self):
        self._de_para([["ID", "NM_ROLE"], [100, "ACESSO_SISTEMA_BACKOFFICE"]])
        self._importador()._carregar_catalogo()
        import shutil
        shutil.rmtree(self.pasta_dp)
        self.assertEqual(self._importador()._carregar_catalogo().get("100"),
                         "ACESSO_SISTEMA_BACKOFFICE")

    def test_de_para_vazio_nao_apaga_o_catalogo_bom(self):
        self._de_para([["ID", "NM_ROLE"], [100, "ACESSO_SISTEMA_BACKOFFICE"]])
        self._importador()._carregar_catalogo()
        for f in Path(self.pasta_dp).glob("*.xlsx"):
            f.unlink()
        self._de_para([["ID", "NM_ROLE"]], nome="ID_x_Perfis_SIG_vazio.xlsx")
        mapa = self._importador()._carregar_catalogo()
        self.assertEqual(mapa.get("100"), "ACESSO_SISTEMA_BACKOFFICE")
        self.assertEqual(self.repo.obter_mapa(Sistema.SIG).get("100"),
                         "ACESSO_SISTEMA_BACKOFFICE")

    def test_arquivo_novo_continua_mandando(self):
        """Fallback nao pode congelar o de-para: entrega nova substitui."""
        self._de_para([["ID", "NM_ROLE"], [100, "NOME_ANTIGO"]])
        self._importador()._carregar_catalogo()
        for f in Path(self.pasta_dp).glob("*.xlsx"):
            f.unlink()
        self._de_para([["ID", "NM_ROLE"], [100, "NOME_NOVO"]],
                      nome="ID_x_Perfis_SIG 19.08.xlsx")
        self.assertEqual(self._importador()._carregar_catalogo().get("100"),
                         "NOME_NOVO")

    def test_sem_de_para_e_sem_catalogo_devolve_vazio(self):
        self.assertEqual(self._importador()._carregar_catalogo(), {})


if __name__ == "__main__":
    unittest.main()
