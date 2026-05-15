from typing import Optional

import pandas as pd
from loguru import logger

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.escritores_arquivos.escritor_parquet import EscritorParquet
from infraestrutura.leitores_arquivos.leitor_matriz import LeitorMatrizOrganizacional, LeitorMatrizPerfis
from infraestrutura.repositorios.repositorio_matriz_sqlite import RepositorioMatrizSqlite


class ImportarMatrizes:

    def __init__(
        self,
        conexao: ConexaoBancoDados,
        pasta_perfis: str,
        pasta_org: str,
        pasta_parquet: str,
        pasta_processados: Optional[str] = None,
        pasta_erros: Optional[str] = None,
    ):
        self._leitor_perfis = LeitorMatrizPerfis(pasta_processados, pasta_erros)
        self._leitor_org = LeitorMatrizOrganizacional(pasta_processados, pasta_erros)
        self._repositorio = RepositorioMatrizSqlite(conexao)
        self._parquet = EscritorParquet()
        self._pasta_perfis = pasta_perfis
        self._pasta_org = pasta_org
        self._pasta_parquet = pasta_parquet

    def executar(self):
        logger.info("=== Importação Matrizes iniciada ===")

        perfis, arq_perfis = self._leitor_perfis.ler(self._pasta_perfis)
        if perfis:
            self._repositorio.salvar_perfis_esperados(perfis, ", ".join(arq_perfis))
            df = pd.DataFrame([{
                "centro_custo": p.cargo_codigo,
                "sistema": p.sistema.value,
                "perfil": p.perfil,
            } for p in perfis])
            self._parquet.salvar_fixo(df, f"{self._pasta_parquet}/MATRIZES", "perfis_esperados")

        cco, arq_cco = self._leitor_org.ler(self._pasta_org)
        if cco:
            self._repositorio.salvar_cco(cco, ", ".join(arq_cco))
            self._parquet.salvar_fixo(pd.DataFrame(cco), f"{self._pasta_parquet}/MATRIZES", "matriz_cco")

        logger.info(f"=== Matrizes: {len(perfis)} perfis esperados, {len(cco)} mapeamentos CCO ===")
        return len(perfis), len(cco)
