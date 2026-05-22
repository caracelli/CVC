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
        pasta_processados: str = None,
        pasta_erros: str = None,
    ):
        cfg = CONFIGS_SISTEMAS[sistema]
        self._leitor = LeitorSistema(cfg, pasta_processados=pasta_processados, pasta_erros=pasta_erros)
        self._repositorio = RepositorioAcessoSqlite(conexao)
        self._parquet = EscritorParquet()
        self._sistema = sistema
        self._pasta_entrada = pasta_entrada
        self._pasta_parquet = pasta_parquet

    def executar(self) -> int:
        logger.info(f"=== Importação {self._sistema.value} iniciada ===")

        # varredura recursiva da pasta de entrada, ordenada pela data no nome
        arquivos = self._leitor.listar_ordenado(self._pasta_entrada)
        if not arquivos:
            logger.warning(f"{self._sistema.value}: nenhum arquivo encontrado.")
            return 0

        # PROCESSADOS na raiz da pasta do sistema (ex.: .../SYSTUR/PROCESSADOS)
        destino_proc = Path(self._pasta_entrada) / "PROCESSADOS"

        for arquivo in arquivos:
            try:
                perfis = self._leitor.ler_um(arquivo)
            except Exception as e:
                logger.error(f"Erro lendo '{arquivo.name}': {e!r}")
                self._leitor.mover_para_erros(arquivo, str(e))
                continue
            # substituição (snapshot): remove os dados do sistema da
            # importação anterior e grava os do arquivo atual
            self._repositorio.substituir_sistema(self._sistema, perfis, arquivo.name)
            self._leitor.mover_para_processados(arquivo, destino=destino_proc)
            logger.success(
                f"{self._sistema.value}: '{arquivo.name}' processado "
                f"({len(perfis)} linhas) e movido para PROCESSADOS."
            )

        # parquet reflete o estado final do banco (último arquivo da ordem)
        perfis_final = self._repositorio.obter_por_sistema(self._sistema)
        if perfis_final:
            df = pd.DataFrame([{
                "sistema":       p.sistema.value,
                "usuario":       p.usuario,
                "nome":          p.nome_usuario,
                "perfil":        p.perfil,
                "situacao":      p.situacao,
                "data_criacao":  str(p.data_criacao) if p.data_criacao else None,
                "ultimo_acesso": str(p.ultimo_acesso) if p.ultimo_acesso else None,
            } for p in perfis_final])
            self._parquet.salvar_fixo(df, self._pasta_parquet, self._sistema.value.lower())

        logger.info(
            f"=== {self._sistema.value}: {len(arquivos)} arquivo(s) processado(s); "
            f"{len(perfis_final)} acessos no banco (estado final) ==="
        )
        return len(perfis_final)
