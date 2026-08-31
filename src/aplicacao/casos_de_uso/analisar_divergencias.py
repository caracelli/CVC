from loguru import logger

from aplicacao.casos_de_uso.detectar_transferidos import DetectarTransferidos
from dominio.servicos_dominio.servico_analise_divergencias import ServicoAnaliseDivergencias
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.repositorios.repositorio_acesso_sqlite import RepositorioAcessoSqlite
from infraestrutura.repositorios.repositorio_divergencia_sqlite import RepositorioDivergenciaSqlite
from infraestrutura.repositorios.repositorio_funcionario_sqlite import RepositorioFuncionarioSqlite
from infraestrutura.repositorios.repositorio_matriz_sqlite import RepositorioMatrizSqlite
from infraestrutura.repositorios.repositorio_transferido_sqlite import RepositorioTransferidoSqlite


class AnalisarDivergencias:

    def __init__(self, conexao: ConexaoBancoDados, prefixos_conta_servico=None):
        # Prefixos de login de CONTA DE SERVICO (config validacao/conta_servico).
        # Vazio = regra desligada.
        self._prefixos_conta_servico = prefixos_conta_servico or []
        self._repo_func = RepositorioFuncionarioSqlite(conexao)
        self._repo_acesso = RepositorioAcessoSqlite(conexao)
        self._repo_matriz = RepositorioMatrizSqlite(conexao)
        self._repo_div = RepositorioDivergenciaSqlite(conexao)
        self._repo_transf = RepositorioTransferidoSqlite(conexao)
        self._detectar_transferidos = DetectarTransferidos(conexao)

    def executar(self) -> int:
        logger.info("=== Analise de Divergencias iniciada ===")

        ativos = self._repo_func.obter_ativos()
        desligados = self._repo_func.obter_desligados()
        perfis_esperados = self._repo_matriz.obter_perfis_esperados()
        acessos = self._repo_acesso.obter_todos()
        # Transferidos: inferidos do historico do RH (mudanca cargo/CC/dep/gestor).
        transferidos = self._detectar_transferidos.executar()
        # Persiste o de/para ANTES de analisar: quem mudou mas NAO tem acesso
        # nenhum nao gera divergencia, e sumiria do painel se dependessemos so
        # da saida da regra. A tabela guarda o movimento; a regra guarda o acesso.
        self._repo_transf.salvar_lote(transferidos)

        servico = ServicoAnaliseDivergencias(
            perfis_esperados, prefixos_conta_servico=self._prefixos_conta_servico)
        divergencias = servico.analisar(
            acessos=acessos,
            ativos=ativos,
            desligados=desligados,
            transferidos=transferidos,
        )

        self._repo_div.salvar_lote(divergencias)

        # Auditavel: quantos ACESSOS nao entraram como "de desligado" porque a
        # conta pertence a alguem ATIVO (a pessoa trocou de matricula e segue
        # usando a mesma conta) — ver RegraAcessoDesligado. Numero alto e'
        # esperado nesta base: 99,8% de quem volta mantem o mesmo usuario.
        _recontratados = getattr(servico, "recontratados_suprimidos", 0)
        if _recontratados:
            logger.info(
                f"[desligados] {_recontratados} acesso(s) fora da conta: a conta "
                f"e' de alguem ATIVO hoje (matricula nova, MESMO login)."
            )
        # O outro lado da regra da area: ativo com login DIFERENTE e' apontado.
        # E' o caso com algo a revogar — identidade antiga que sobrou viva.
        _login_dif = getattr(servico, "login_diferente_apontado", 0)
        if _login_dif:
            logger.info(
                f"[desligados] {_login_dif} acesso(s) APONTADO(S): a pessoa esta "
                f"ativa, mas com login DIFERENTE (identidade antiga viva)."
            )

        # CONTA DE SERVICO: robo que casou com desligado pelo e-mail de quem o
        # criou. Saiu da revogacao (tipo proprio), mas NAO sumiu — e' consultavel.
        _servico = getattr(servico, "contas_servico", 0)
        if _servico:
            logger.info(
                f"[desligados] {_servico} acesso(s) reclassificado(s) como CONTA "
                f"DE SERVICO (prefixo {self._prefixos_conta_servico}): fora da "
                f"lista de revogacao, visiveis na categoria propria."
            )
        # Conferencia da premissa: prefixo e nome discordaram. Zero na base
        # medida; acima de zero e' pedido de revisao da lista de prefixos.
        _dif = getattr(servico, "divergiu_do_nome", 0)
        if _dif:
            logger.warning(
                f"[desligados] {_dif} caso(s) em que o PREFIXO e o NOME "
                f"discordam sobre ser conta de servico — revisar "
                f"validacao/conta_servico/prefixos_login no config.xml."
            )

        por_tipo = {}
        for d in divergencias:
            por_tipo[d.tipo.value] = por_tipo.get(d.tipo.value, 0) + 1

        resumo = ", ".join(f"{t}={n}" for t, n in sorted(por_tipo.items()))
        logger.info(f"=== Divergencias encontradas: {len(divergencias)} ({resumo}) ===")
        return len(divergencias)
