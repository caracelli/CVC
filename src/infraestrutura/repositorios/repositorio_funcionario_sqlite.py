from datetime import datetime
from typing import List, Optional

from loguru import logger

from dominio.entidades.funcionario_ativo import FuncionarioAtivo
from dominio.entidades.funcionario_desligado import FuncionarioDesligado
from dominio.interfaces.i_repositorio_funcionario import IRepositorioFuncionario
from dominio.objetos_valor.cargo import Cargo
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import RhAtivo, RhDesligado


class RepositorioFuncionarioSqlite(IRepositorioFuncionario):

    def __init__(self, conexao: ConexaoBancoDados):
        self._conexao = conexao

    def salvar_ativos(self, ativos: List[FuncionarioAtivo], arquivo_origem: str = ""):
        with self._conexao.sessao() as sessao:
            for f in ativos:
                sessao.merge(RhAtivo(
                    matricula=f.matricula,
                    nome=f.nome,
                    cpf=f.cpf,
                    cargo_codigo=f.cargo.codigo,
                    cargo_descricao=f.cargo.descricao,
                    centro_custo_codigo=f.cargo.centro_custo,
                    departamento=f.cargo.departamento,
                    data_admissao=f.data_admissao,
                    email=f.email,
                    situacao=f.situacao,
                    arquivo_origem=arquivo_origem,
                    dt_importacao=datetime.now(),
                ))
            sessao.commit()
        logger.info(f"{len(ativos)} ativos gravados no banco.")

    def salvar_desligados(self, desligados: List[FuncionarioDesligado], arquivo_origem: str = ""):
        with self._conexao.sessao() as sessao:
            for f in desligados:
                sessao.merge(RhDesligado(
                    matricula=f.matricula,
                    nome=f.nome,
                    cpf=f.cpf,
                    cargo_codigo=f.cargo.codigo,
                    cargo_descricao=f.cargo.descricao,
                    centro_custo_codigo=f.cargo.centro_custo,
                    departamento=f.cargo.departamento,
                    data_admissao=f.data_admissao,
                    data_desligamento=f.data_desligamento,
                    email=f.email,
                    arquivo_origem=arquivo_origem,
                    dt_importacao=datetime.now(),
                ))
            sessao.commit()
        logger.info(f"{len(desligados)} desligados gravados no banco.")

    def obter_ativos(self) -> List[FuncionarioAtivo]:
        with self._conexao.sessao() as sessao:
            return [self._para_ativo(r) for r in sessao.query(RhAtivo).all()]

    def obter_desligados(self) -> List[FuncionarioDesligado]:
        with self._conexao.sessao() as sessao:
            return [self._para_desligado(r) for r in sessao.query(RhDesligado).all()]

    def buscar_por_matricula(self, matricula: str) -> Optional[FuncionarioAtivo]:
        with self._conexao.sessao() as sessao:
            r = sessao.get(RhAtivo, matricula)
            return self._para_ativo(r) if r else None

    def buscar_por_cpf(self, cpf: str) -> Optional[FuncionarioAtivo]:
        with self._conexao.sessao() as sessao:
            r = sessao.query(RhAtivo).filter_by(cpf=cpf).first()
            return self._para_ativo(r) if r else None

    def buscar_desligado_por_cpf(self, cpf: str) -> Optional[FuncionarioDesligado]:
        with self._conexao.sessao() as sessao:
            r = sessao.query(RhDesligado).filter_by(cpf=cpf).first()
            return self._para_desligado(r) if r else None

    def _para_ativo(self, r: RhAtivo) -> FuncionarioAtivo:
        return FuncionarioAtivo(
            matricula=r.matricula,
            nome=r.nome,
            cpf=r.cpf,
            cargo=Cargo(r.cargo_codigo or "", r.cargo_descricao or "", r.departamento or "", r.centro_custo_codigo or ""),
            email=r.email,
            data_admissao=r.data_admissao,
            situacao=r.situacao or "ATIVO",
        )

    def _para_desligado(self, r: RhDesligado) -> FuncionarioDesligado:
        return FuncionarioDesligado(
            matricula=r.matricula,
            nome=r.nome,
            cpf=r.cpf,
            cargo=Cargo(r.cargo_codigo or "", r.cargo_descricao or "", r.departamento or "", r.centro_custo_codigo or ""),
            email=r.email,
            data_admissao=r.data_admissao,
            data_desligamento=r.data_desligamento,
        )
