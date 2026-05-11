from pathlib import Path

import pandas as pd
from loguru import logger

from dominio.objetos_valor.sistema import Sistema
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.escritores_arquivos.escritor_parquet import EscritorParquet
from infraestrutura.leitores_arquivos.configs_sistemas import CONFIGS_SISTEMAS
from infraestrutura.leitores_arquivos.leitor_sistema import LeitorSistema
from infraestrutura.repositorios.repositorio_acesso_sqlite import RepositorioAcessoSqlite


class ImportarSistema:

    def __init__(
        self,
        conexao: ConexaoBancoDados,
        sistema: Sistema,
        pasta_entrada: str,
        pasta_parquet: str,
    ):
        cfg = CONFIGS_SISTEMAS[sistema]
        self._leitor = LeitorSistema(cfg)
        self._repositorio = RepositorioAcessoSqlite(conexao)
        self._parquet = EscritorParquet()
        self._sistema = sistema
        self._pasta_entrada = pasta_entrada
        self._pasta_parquet = pasta_parquet

    def executar(self) -> int:
        logger.info(f"=== Importação {self._sistema.value} iniciada ===")

        perfis, processados = self._leitor.ler(self._pasta_entrada)

        if not perfis:
            logger.warning(f"{self._sistema.value}: nenhum arquivo encontrado.")
            return 0

        self._repositorio.salvar_lote(perfis, ", ".join(processados))

        df = pd.DataFrame([{
            "sistema":    p.sistema.value,
            "usuario":    p.usuario,
            "nome":       p.nome_usuario,
            "perfil":     p.perfil,
            "situacao":   p.situacao,
            "data_criacao":   str(p.data_criacao) if p.data_criacao else None,
            "ultimo_acesso":  str(p.ultimo_acesso) if p.ultimo_acesso else None,
        } for p in perfis])

        nome = self._sistema.value.lower()
        self._parquet.salvar_fixo(df, self._pasta_parquet, nome)

        logger.info(f"=== {self._sistema.value}: {len(perfis)} registros importados ===")
        return len(perfis)
