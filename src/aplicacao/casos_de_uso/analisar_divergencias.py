from loguru import logger

from dominio.servicos_dominio.servico_analise_divergencias import ServicoAnaliseDivergencias
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.repositorios.repositorio_acesso_sqlite import RepositorioAcessoSqlite
from infraestrutura.repositorios.repositorio_divergencia_sqlite import RepositorioDivergenciaSqlite
from infraestrutura.repositorios.repositorio_funcionario_sqlite import RepositorioFuncionarioSqlite
from infraestrutura.repositorios.repositorio_matriz_sqlite import RepositorioMatrizSqlite


class AnalisarDivergencias:

    def __init__(self, conexao: ConexaoBancoDados):
        self._repo_func = RepositorioFuncionarioSqlite(conexao)
        self._repo_acesso = RepositorioAcessoSqlite(conexao)
        self._repo_matriz = RepositorioMatrizSqlite(conexao)
        self._repo_div = RepositorioDivergenciaSqlite(conexao)

    def executar(self) -> int:
        logger.info("=== Analise de Divergencias iniciada ===")

        ativos = self._repo_func.obter_ativos()
        desligados = self._repo_func.obter_desligados()
        perfis_esperados = self._repo_matriz.obter_perfis_esperados()
        acessos = self._repo_acesso.obter_todos()

        servico = ServicoAnaliseDivergencias(perfis_esperados)
        divergencias = servico.analisar(
            acessos=acessos,
            ativos=ativos,
            desligados=desligados,
            transferidos=[],
        )

        self._repo_div.salvar_lote(divergencias)

        por_tipo = {}
        for d in divergencias:
            por_tipo[d.tipo.value] = por_tipo.get(d.tipo.value, 0) + 1

        resumo = ", ".join(f"{t}={n}" for t, n in sorted(por_tipo.items()))
        logger.info(f"=== Divergencias encontradas: {len(divergencias)} ({resumo}) ===")
        return len(divergencias)
