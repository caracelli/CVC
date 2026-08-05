from loguru import logger

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.leitores_arquivos.leitor_rh import LeitorRh
from infraestrutura.repositorios.repositorio_funcionario_sqlite import RepositorioFuncionarioSqlite
from infraestrutura.repositorios.repositorio_log_importacao import (
    RepositorioLogImportacao, mtimes_da_pasta,
)
from aplicacao.casos_de_uso.registrar_historico import RegistrarHistorico


class ImportarRh:

    def __init__(
        self,
        conexao: ConexaoBancoDados,
        pasta_ativos: str,
        pasta_desligados: str,
        pasta_processados: str = None,
        pasta_erros: str = None,
        processar_desligados: bool = True,
        processar_terceiros: bool = True,
    ):
        self._leitor = LeitorRh(
            pasta_processados=pasta_processados,
            pasta_erros=pasta_erros,
            processar_terceiros=processar_terceiros,
        )
        self._repositorio = RepositorioFuncionarioSqlite(conexao)
        self._historico = RegistrarHistorico(conexao)
        self._log = RepositorioLogImportacao(conexao)
        self._pasta_ativos = pasta_ativos
        self._pasta_desligados = pasta_desligados
        self._processar_desligados = processar_desligados

    def executar(self):
        logger.info("=== Importação RH iniciada ===")

        # data dos PROPRIOS arquivos (disponibilizacao) — capturada antes de o
        # leitor mover os arquivos para PROCESSADOS.
        mtimes = mtimes_da_pasta(self._pasta_ativos)
        ativos, arq_ativos = self._leitor.ler_ativos(self._pasta_ativos)
        if ativos:
            # CDC antes do merge: o estado anterior ainda está intacto no banco
            self._historico.registrar_ativos(ativos)
            self._repositorio.salvar_ativos(ativos, ", ".join(arq_ativos))
            for nome in arq_ativos:
                self._log.registrar(
                    arquivo=nome, tipo="RH_ATIVOS", hash_arquivo="",
                    total_registros=len(ativos), status="SUCESSO",
                    dt_arquivo=mtimes.get(nome))

        desligados = []
        if self._processar_desligados:
            mtimes_desl = mtimes_da_pasta(self._pasta_desligados)
            desligados, arq_desligados = self._leitor.ler_desligados(self._pasta_desligados)
            if desligados:
                # Desligados fora do escopo da trilha de ouvidoria (Fase 1):
                # atualiza só a base, sem registrar histórico de movimentação.
                self._repositorio.salvar_desligados(desligados, ", ".join(arq_desligados))
                # registra no log de importacoes para o painel "Bases" mostrar
                # que arquivo/data alimentou os desligados — sem isto, uma
                # entrega SEM o arquivo de desligados passa despercebida.
                for nome in arq_desligados:
                    self._log.registrar(
                        arquivo=nome, tipo="RH_DESLIGADOS", hash_arquivo="",
                        total_registros=len(desligados), status="SUCESSO",
                        dt_arquivo=mtimes_desl.get(nome))
        else:
            # Escopo da fase: SYSTUR inclusão/alteração não trata desligados.
            # A pasta não é lida, mesmo que haja arquivo (revogação é fluxo
            # separado). Ver config rh/desligados/processar.
            logger.info("Desligados fora de escopo nesta fase — ignorado.")

        logger.info(f"=== Importação RH concluída: {len(ativos)} ativos, {len(desligados)} desligados ===")
        return len(ativos), len(desligados)
