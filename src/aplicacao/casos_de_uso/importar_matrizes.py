from typing import Optional

from loguru import logger

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.leitores_arquivos.leitor_matriz import LeitorMatrizOrganizacional, LeitorMatrizPerfis
from infraestrutura.repositorios.repositorio_matriz_sqlite import RepositorioMatrizSqlite
from infraestrutura.repositorios.repositorio_log_importacao import (
    RepositorioLogImportacao, mtimes_da_pasta,
)


class ImportarMatrizes:

    def __init__(
        self,
        conexao: ConexaoBancoDados,
        pasta_perfis: str,
        pasta_org: str,
        pasta_processados: Optional[str] = None,
        pasta_erros: Optional[str] = None,
        sistemas_em_escopo: Optional[set] = None,
    ):
        self._leitor_perfis = LeitorMatrizPerfis(pasta_processados, pasta_erros)
        self._leitor_org = LeitorMatrizOrganizacional(pasta_processados, pasta_erros)
        self._repositorio = RepositorioMatrizSqlite(conexao)
        self._log = RepositorioLogImportacao(conexao)
        self._pasta_perfis = pasta_perfis
        self._pasta_org = pasta_org
        # Sistemas implementados/em escopo nesta fase. Matrizes de sistemas
        # fora desse conjunto sao ignoradas (sem log/processamento). None =
        # todos (compat com chamadas antigas/testes).
        self._sistemas_em_escopo = sistemas_em_escopo

    def executar(self):
        logger.info("=== Importação Matrizes iniciada ===")

        # data dos PROPRIOS arquivos (disponibilizacao) — antes do leitor mover.
        mt_perfis = mtimes_da_pasta(self._pasta_perfis)
        mt_org = mtimes_da_pasta(self._pasta_org)

        perfis, arq_perfis = self._leitor_perfis.ler(
            self._pasta_perfis, self._sistemas_em_escopo)
        if perfis:
            self._repositorio.salvar_perfis_esperados(perfis, ", ".join(arq_perfis))
            for nome in arq_perfis:
                self._log.registrar(
                    arquivo=nome, tipo="MATRIZ_PERFIS", hash_arquivo="",
                    total_registros=len(perfis), status="SUCESSO",
                    dt_arquivo=mt_perfis.get(nome))

        cco, arq_cco = self._leitor_org.ler(self._pasta_org)
        if cco:
            self._repositorio.salvar_cco(cco, ", ".join(arq_cco))
            for nome in arq_cco:
                self._log.registrar(
                    arquivo=nome, tipo="MATRIZ_CCO", hash_arquivo="",
                    total_registros=len(cco), status="SUCESSO",
                    dt_arquivo=mt_org.get(nome))

        logger.info(f"=== Matrizes: {len(perfis)} perfis esperados, {len(cco)} mapeamentos CCO ===")
        return len(perfis), len(cco)
