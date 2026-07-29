"""Vinculacao Acessos x RH com cascata multi-chave.

A cascata e' aplicada em todos os sistemas, mas e' especialmente importante
para sistemas com CPF mascarado/ausente (SICA_RA atual). Niveis:

  1. CPF exato (score 1.00)
  2. Email exato (score 0.95)
  3. Login exato (score 0.93) — identidades do diretorio AD (franq/prest)
  4. CPF parcial + nome (score 0.90)
  5. Nome exato (score 0.70)
  6. Fuzzy nome (score 0.50, nao vincula — so candidatos)

Quando o sistema traz CPF limpo (SIGOT, SIG, IC), nivel 1 resolve >85%;
os outros niveis pegam casos residuais (terceirizados sem CPF, etc.).
"""
from loguru import logger

from dominio.servicos_dominio.servico_vinculacao_multi_chave import (
    ORDEM_METODOS, construir_universo,
)
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.repositorios.repositorio_acesso_sqlite import RepositorioAcessoSqlite
from infraestrutura.repositorios.repositorio_funcionario_sqlite import RepositorioFuncionarioSqlite


class VincularAcessosRh:

    def __init__(self, conexao: ConexaoBancoDados):
        self._repo_acesso = RepositorioAcessoSqlite(conexao)
        self._repo_func = RepositorioFuncionarioSqlite(conexao)

    def executar(self) -> dict:
        logger.info("=== Vinculacao Acessos x RH iniciada (cascata multi-chave) ===")

        # Universo de matching: ATIVOS primeiro. A cascata indexa numa lista e,
        # em colisao (mesmo CPF/email/nome em ativo e desligado), escolhe o
        # PRIMEIRO da lista (cand[0]) — entao o ativo prevalece, e o desligado
        # entra so como candidato para revisao. Caso tipico: re-contratacao
        # (mesma pessoa com matricula nova ativa); o acesso deve ligar ao cargo
        # ATUAL, nao ao vinculo desligado.
        # Dentro dos ativos, a precedencia e' EXPLICITA (nao depende da ordem de
        # insercao no banco): CLT/terceiro antes das identidades de diretorio
        # (FRANQUEADO/PRESTADOR). Assim, um CPF que exista nos dois mundos liga
        # ao vinculo empregaticio, e o AD fica so como candidato. Sem isso, a
        # ordem do pipeline de importacao decidiria o vencedor por acidente.
        ativos = self._repo_func.obter_ativos()
        de_diretorio = {"FRANQUEADO", "PRESTADOR"}
        funcionarios = [f for f in ativos
                        if getattr(f, "tipo_vinculo", "") not in de_diretorio]
        funcionarios.extend(f for f in ativos
                            if getattr(f, "tipo_vinculo", "") in de_diretorio)
        funcionarios.extend(self._repo_func.obter_desligados())
        universo = construir_universo(funcionarios)

        contagem = self._repo_acesso.vincular_multi_chave(universo)

        # Log estruturado por metodo (auditavel)
        total = sum(contagem.values()) or 1
        for metodo in ORDEM_METODOS:
            qt = contagem.get(metodo, 0)
            pct = 100 * qt / total
            if qt > 0:
                logger.info(f"  {metodo:<22} {qt:>6d}  ({pct:5.1f}%)")

        logger.info(f"=== Vinculacao: {total} acessos processados ===")
        return contagem
