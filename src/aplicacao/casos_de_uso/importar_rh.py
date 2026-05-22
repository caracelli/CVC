from loguru import logger

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.leitores_arquivos.leitor_rh import LeitorRh
from infraestrutura.repositorios.repositorio_funcionario_sqlite import RepositorioFuncionarioSqlite
from aplicacao.casos_de_uso.registrar_historico_rh import RegistrarHistoricoRh


class ImportarRh:

    def __init__(
        self,
        conexao: ConexaoBancoDados,
        pasta_ativos: str,
        pasta_desligados: str,
        pasta_processados: str = None,
        pasta_erros: str = None,
    ):
        self._leitor = LeitorRh(pasta_processados=pasta_processados, pasta_erros=pasta_erros)
        self._repositorio = RepositorioFuncionarioSqlite(conexao)
        self._historico = RegistrarHistoricoRh(conexao)
        self._pasta_ativos = pasta_ativos
        self._pasta_desligados = pasta_desligados

    def executar(self):
        logger.info("=== Importação RH iniciada ===")

        ativos, arq_ativos = self._leitor.ler_ativos(self._pasta_ativos)
        if ativos:
            # CDC antes do merge: o estado anterior ainda está intacto no banco
            self._historico.registrar_ativos(ativos)
            self._repositorio.salvar_ativos(ativos, ", ".join(arq_ativos))

        desligados, arq_desligados = self._leitor.ler_desligados(self._pasta_desligados)
        if desligados:
            # Desligados fora do escopo da trilha de ouvidoria (Fase 1):
            # atualiza só a base, sem registrar histórico de movimentação.
            self._repositorio.salvar_desligados(desligados, ", ".join(arq_desligados))

        logger.info(f"=== Importação RH concluída: {len(ativos)} ativos, {len(desligados)} desligados ===")
        return len(ativos), len(desligados)
