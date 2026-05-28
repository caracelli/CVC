"""Vinculacao Acessos x RH com cascata multi-chave.

A cascata e' aplicada em todos os sistemas, mas e' especialmente importante
para sistemas com CPF mascarado/ausente (SICA_RA atual). Niveis:

  1. CPF exato (score 1.00)
  2. Email exato (score 0.95)
  3. CPF parcial + nome (score 0.90)
  4. Nome exato (score 0.70)
  5. Fuzzy nome (score 0.50, nao vincula — so candidatos)

Quando o sistema traz CPF limpo (SIGOT, SIG, IC), nivel 1 resolve >85%;
os outros niveis pegam casos residuais (terceirizados sem CPF, etc.).
"""
from loguru import logger

from dominio.servicos_dominio.servico_vinculacao_multi_chave import construir_universo
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.repositorios.repositorio_acesso_sqlite import RepositorioAcessoSqlite
from infraestrutura.repositorios.repositorio_funcionario_sqlite import RepositorioFuncionarioSqlite


class VincularAcessosRh:

    def __init__(self, conexao: ConexaoBancoDados):
        self._repo_acesso = RepositorioAcessoSqlite(conexao)
        self._repo_func = RepositorioFuncionarioSqlite(conexao)

    def executar(self) -> dict:
        logger.info("=== Vinculacao Acessos x RH iniciada (cascata multi-chave) ===")

        # Universo de matching: desligados primeiro (ativos sobrescrevem em colisoes).
        # Mesma logica de antes — ativo prevalece quando ha o mesmo CPF/email.
        funcionarios = []
        funcionarios.extend(self._repo_func.obter_desligados())
        funcionarios.extend(self._repo_func.obter_ativos())
        universo = construir_universo(funcionarios)

        contagem = self._repo_acesso.vincular_multi_chave(universo)

        # Log estruturado por metodo (auditavel)
        total = sum(contagem.values()) or 1
        for metodo in ("CPF", "EMAIL", "CPF_PARCIAL_NOME", "NOME", "FUZZY", "NAO_VINCULADO"):
            qt = contagem.get(metodo, 0)
            pct = 100 * qt / total
            if qt > 0:
                logger.info(f"  {metodo:<22} {qt:>6d}  ({pct:5.1f}%)")

        logger.info(f"=== Vinculacao: {total} acessos processados ===")
        return contagem
