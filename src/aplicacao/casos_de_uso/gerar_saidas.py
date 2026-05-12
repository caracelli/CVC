from datetime import datetime
from typing import Optional

import pandas as pd
from loguru import logger

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.escritores_arquivos.escritor_excel import EscritorExcel
from infraestrutura.escritores_arquivos.escritor_parquet import EscritorParquet
from infraestrutura.repositorios.repositorio_divergencia_sqlite import RepositorioDivergenciaSqlite


class GerarSaidas:

    def __init__(
        self,
        conexao: ConexaoBancoDados,
        pasta_saidas: str,
        pasta_parquet: str,
        pasta_processados: Optional[str] = None,
        pasta_erros: Optional[str] = None,
    ):
        self._repo_div = RepositorioDivergenciaSqlite(conexao)
        self._escritor_excel = EscritorExcel()
        self._escritor_parquet = EscritorParquet()
        self._pasta_saidas = pasta_saidas
        self._pasta_parquet = pasta_parquet

    def executar(self) -> int:
        logger.info("=== Geracao de Saidas iniciada ===")

        divergencias = self._repo_div.obter_todas()

        if not divergencias:
            logger.warning("Nenhuma divergencia encontrada — saidas nao geradas.")
            return 0

        # Excel com data/hora no nome
        caminho_excel = self._escritor_excel.salvar_divergencias(
            divergencias,
            self._pasta_saidas,
        )

        # Parquet fixo para Power BI
        df = pd.DataFrame([{
            "id":                d.id,
            "tipo":              d.tipo.value,
            "sistema":           d.sistema.value,
            "usuario":           d.usuario,
            "nome_usuario":      d.nome_usuario,
            "matricula":         d.matricula or "",
            "perfil_encontrado": d.perfil_encontrado or "",
            "perfil_esperado":   d.perfil_esperado or "",
            "descricao":         d.descricao,
            "data_identificacao": d.data_identificacao,
            "resolvida":         d.resolvida,
        } for d in divergencias])

        self._escritor_parquet.salvar_fixo(
            df,
            f"{self._pasta_parquet}/DIVERGENCIAS",
            "divergencias",
        )

        logger.info(f"=== Saidas geradas: {len(divergencias)} divergencias — {caminho_excel} ===")
        return len(divergencias)
