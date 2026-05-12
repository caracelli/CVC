from loguru import logger

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.repositorios.repositorio_acesso_sqlite import RepositorioAcessoSqlite
from infraestrutura.repositorios.repositorio_funcionario_sqlite import RepositorioFuncionarioSqlite


class VincularAcessosRh:

    def __init__(self, conexao: ConexaoBancoDados):
        self._repo_acesso = RepositorioAcessoSqlite(conexao)
        self._repo_func = RepositorioFuncionarioSqlite(conexao)

    def executar(self) -> int:
        logger.info("=== Vinculação Acessos x RH iniciada ===")

        ativos = self._repo_func.obter_ativos()
        desligados = self._repo_func.obter_desligados()

        # Build CPF → matrícula map; desligados can coexist with separate CPFs
        mapa: dict = {}
        for f in desligados:
            if f.cpf:
                mapa[f.cpf] = f.matricula
        for f in ativos:
            if f.cpf:
                mapa[f.cpf] = f.matricula  # ativos override desligados on same CPF

        vinculados = self._repo_acesso.vincular_por_cpf(mapa)
        logger.info(f"=== Vinculacao: {vinculados} acessos vinculados a matriculas RH ===")
        return vinculados
