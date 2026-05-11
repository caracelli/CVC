from datetime import date

import pandas as pd
from loguru import logger

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.leitores_arquivos.leitor_rh import LeitorRh
from infraestrutura.repositorios.repositorio_funcionario_sqlite import RepositorioFuncionarioSqlite
from infraestrutura.escritores_arquivos.escritor_parquet import EscritorParquet


class ImportarRh:

    def __init__(
        self,
        conexao: ConexaoBancoDados,
        pasta_ativos: str,
        pasta_desligados: str,
        pasta_parquet_rh: str,
    ):
        self._leitor = LeitorRh()
        self._repositorio = RepositorioFuncionarioSqlite(conexao)
        self._parquet = EscritorParquet()
        self._pasta_ativos = pasta_ativos
        self._pasta_desligados = pasta_desligados
        self._pasta_parquet = pasta_parquet_rh

    def executar(self):
        logger.info("=== Importação RH iniciada ===")

        ativos, arq_ativos = self._leitor.ler_ativos(self._pasta_ativos)
        if ativos:
            self._repositorio.salvar_ativos(ativos, ", ".join(arq_ativos))
            df = pd.DataFrame([{
                "matricula": f.matricula,
                "nome": f.nome,
                "cpf": f.cpf,
                "cargo_codigo": f.cargo.codigo,
                "cargo_descricao": f.cargo.descricao,
                "departamento": f.cargo.departamento,
                "centro_custo": f.cargo.centro_custo,
                "data_admissao": str(f.data_admissao) if f.data_admissao else None,
                "email": f.email,
                "situacao": f.situacao,
            } for f in ativos])
            self._parquet.salvar_fixo(df, self._pasta_parquet, "rh_ativos")

        desligados, arq_desligados = self._leitor.ler_desligados(self._pasta_desligados)
        if desligados:
            self._repositorio.salvar_desligados(desligados, ", ".join(arq_desligados))
            df = pd.DataFrame([{
                "matricula": f.matricula,
                "nome": f.nome,
                "cpf": f.cpf,
                "cargo_codigo": f.cargo.codigo,
                "cargo_descricao": f.cargo.descricao,
                "data_admissao": str(f.data_admissao) if f.data_admissao else None,
                "data_desligamento": str(f.data_desligamento) if f.data_desligamento else None,
            } for f in desligados])
            self._parquet.salvar_fixo(df, self._pasta_parquet, "rh_desligados")

        logger.info(f"=== Importação RH concluída: {len(ativos)} ativos, {len(desligados)} desligados ===")
        return len(ativos), len(desligados)
